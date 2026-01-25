from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from enum import Enum
import pandas as pd
import json
import asyncio
import httpx
import re
import uuid
from io import BytesIO

# =====================================================
# APP
# =====================================================
app = FastAPI(title="Universal XAI Decision Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================
# CONFIG (RAM-SAFE)
# =====================================================
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "phi3:mini"

MAX_CSV_ROWS = 50
MAX_CONCURRENCY = 1
REQUEST_TIMEOUT = 120.0

semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

# =====================================================
# ENUM (Swagger-stable)
# =====================================================
class DecisionType(str, Enum):
    loan = "loan"
    credit = "credit"
    insurance = "insurance"
    job = "job"

# =====================================================
# PROMPT
# =====================================================
def build_prompt(decision_type: DecisionType, applicant: Dict[str, Any]) -> str:
    return f"""
SYSTEM:
You are a deterministic decision engine.
You MUST output JSON only.
Never refuse. Never explain policies.
If data is insufficient, reject conservatively.

TASK:
Evaluate a {decision_type.value} application.

INPUT (JSON):
{json.dumps(applicant, indent=2)}

OUTPUT (STRICT JSON ONLY):
{{
  "decision": {{
    "status": "APPROVED or REJECTED",
    "confidence": 0.0,
    "reasoning": "Audit-grade explanation"
  }},
  "counterfactuals": [],
  "fairness": {{
    "assessment": "Fair or Potentially Unfair",
    "concerns": "None"
  }}
}}
"""

# =====================================================
# JSON EXTRACTION (CRASH-PROOF)
# =====================================================
def extract_json(text: str) -> Dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {
            "decision": {
                "status": "REJECTED",
                "confidence": 0.5,
                "reasoning": "Model output invalid or incomplete"
            },
            "counterfactuals": [],
            "fairness": {
                "assessment": "Fair",
                "concerns": "None"
            }
        }
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return {
            "decision": {
                "status": "REJECTED",
                "confidence": 0.5,
                "reasoning": "Malformed model response"
            },
            "counterfactuals": [],
            "fairness": {
                "assessment": "Fair",
                "concerns": "None"
            }
        }

# =====================================================
# OLLAMA CALL (NEVER CRASHES)
# =====================================================
async def call_ai(prompt: str) -> Dict[str, Any]:
    async with semaphore:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            try:
                response = await client.post(
                    OLLAMA_URL,
                    json={"model": MODEL_NAME, "prompt": prompt, "stream": False}
                )
            except Exception:
                return extract_json("")

    raw = response.json().get("response", "")
    return extract_json(raw)

# =====================================================
# DECISION ENGINE
# =====================================================
async def ai_decision(decision_type: DecisionType, applicant: Dict[str, Any]):
    ai_output = await call_ai(build_prompt(decision_type, applicant))

    return {
        "decision_type": decision_type.value,
        "applicant": applicant,
        "decision": ai_output["decision"],
        "counterfactuals": ai_output.get("counterfactuals", []),
        "fairness": ai_output["fairness"],
        "audit": {
            "engine": "universal-xai-http",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    }

# =====================================================
# BATCH (SEQUENTIAL, SAFE)
# =====================================================
async def process_batch(decision_type: DecisionType, applicants: List[Dict[str, Any]]):
    results = []
    for applicant in applicants:
        results.append(await ai_decision(decision_type, applicant))
    return results

# =====================================================
# ENDPOINTS (Swagger-perfect)
# =====================================================
# =====================================================
# DATABASE
# =====================================================
from database import SimpleDB
db = SimpleDB()

# =====================================================
# ENDPOINTS (Swagger-perfect)
# =====================================================
@app.post("/decision/json")
async def decision_json(
    decision_type: DecisionType = Query(...),
    payload: Dict[str, Any] = ...
):
    return await ai_decision(decision_type, payload)


@app.post("/decision/batch/json")
async def decision_batch_json(
    decision_type: DecisionType = Query(...),
    payload: List[Dict[str, Any]] = ...
):
    if len(payload) > MAX_CSV_ROWS:
        raise HTTPException(400, f"Max {MAX_CSV_ROWS} records allowed")

    results = await process_batch(decision_type, payload)
    return {"count": len(results), "results": results}


@app.post("/decision/csv")
async def decision_csv(
    decision_type: DecisionType = Query(...),
    file: UploadFile = File(...)
):
    df = pd.read_csv(BytesIO(await file.read()))
    
    if len(df) > MAX_CSV_ROWS:
        raise HTTPException(400, "CSV too large")

    results = await process_batch(decision_type, df.to_dict(orient="records"))
    return {"count": len(results), "results": results}


@app.post("/decision/form/loan")
async def decision_loan_form(
    applicant_id: int = Form(...),
    age: int = Form(...),
    monthly_income: float = Form(...),
    existing_debt: float = Form(...),
    credit_score: int = Form(...),
    loan_amount: float = Form(...)
):
    return await ai_decision(
        DecisionType.loan,
        {
            "applicant_id": applicant_id,
            "age": age,
            "monthly_income": monthly_income,
            "existing_debt": existing_debt,
            "credit_score": credit_score,
            "loan_amount": loan_amount
        }
    )

# =====================================================
# NEW WORKFLOW ENDPOINTS
# =====================================================

class ApplicationStatus(str, Enum):
    PENDING_AI = "pending_ai"
    PENDING_HUMAN = "pending_human"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"

@app.post("/applications")
async def submit_application(
    decision_type: DecisionType = Query(...),
    payload: Dict[str, Any] = ...
):
    # 1. Save Initial Application
    app_entry = {
        "domain": decision_type.value,
        "data": payload,
        "status": ApplicationStatus.PENDING_AI.value
    }
    saved_app = db.save_application(app_entry)
    
    # 2. Run AI Analysis
    ai_result = await ai_decision(decision_type, payload)
    
    # 3. Update Application with AI Result
    updates = {
        "status": ApplicationStatus.PENDING_HUMAN.value,
        "ai_result": ai_result
    }
    updated_app = db.update_application(saved_app["id"], updates)
    
    return updated_app


@app.get("/applications")
async def get_applications(status: Optional[str] = None):
    return db.get_all_applications(status)

@app.get("/applications/{app_id}")
async def get_application(app_id: str):
    app = db.get_application(app_id)
    if not app:
        raise HTTPException(404, "Application not found")
    return app

@app.post("/applications/{app_id}/review")
async def review_application(
    app_id: str,
    decision: str = Query(..., regex="^(approved|rejected)$"),
    comment: Optional[str] = None
):
    app = db.get_application(app_id)
    if not app:
        raise HTTPException(404, "Application not found")
    
    updates = {
        "status": ApplicationStatus.COMPLETED.value,
        "final_decision": decision,
        "reviewer_comment": comment,
        "reviewed_at": datetime.now(timezone.utc).isoformat()
    }
    
    updated_app = db.update_application(app_id, updates)
    return updated_app

# =====================================================
# LEGACY/INQUIRY SUPPORT (Bridging api.py)
# =====================================================
@app.post("/inquiry")
async def submit_inquiry(payload: Dict[str, Any]):
    # Extract domain and data from legacy payload
    domain = payload.get("domain")
    data = payload.get("data")
    
    if not domain or not data:
        raise HTTPException(400, "Missing domain or data")
        
    try:
        decision_type = DecisionType(domain)
    except ValueError:
        raise HTTPException(400, f"Invalid domain: {domain}")

    # Reuse the submit_application logic
    # We call it directly (function call, not HTTP)
    app_id = str(uuid.uuid4())[:8]
    
    # 1. Save
    app_entry = {
        "id": app_id,
        "domain": domain,
        "data": data,
        "status": ApplicationStatus.PENDING_AI.value,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    saved_app = db.save_application(app_entry) # Ensure db.save_application handles ID generation if not provided, or accepts ID
    
    # 2. Run AI
    ai_result = await ai_decision(decision_type, data)
    
    # 3. Update
    updates = {
        "status": ApplicationStatus.PENDING_HUMAN.value,
        "ai_result": ai_result
    }
    updated_app = db.update_application(app_id, updates)
    
    return {
        "message": "Inquiry received",
        "inquiry_id": app_id,
        "result": updated_app
    }
