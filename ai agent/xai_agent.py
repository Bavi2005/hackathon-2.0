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
import os
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
MODEL_NAME = "qwen2.5:1.5b"

MAX_CSV_ROWS = 50
MAX_CONCURRENCY = 5  # Increased for parallel batch processing
REQUEST_TIMEOUT = 120.0

semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

# File paths
POLICIES_FILE = "../data/policies.json"
AI_MEMORY_FILE = "../data/ai_memory.json"
EXPLANATIONS_FILE = "../data/explanations.json"

# =====================================================
# ENUM (Swagger-stable)
# =====================================================
class DecisionType(str, Enum):
    loan = "loan"
    credit = "credit"
    insurance = "insurance"
    job = "job"

# =====================================================
# POLICY MEMORY (RAG-like)
# =====================================================
class PolicyMemory:
    def __init__(self, file_path: str = POLICIES_FILE):
        self.file_path = file_path
        self._ensure_file()
    
    def _ensure_file(self):
        if not os.path.exists(self.file_path):
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with open(self.file_path, "w") as f:
                json.dump({
                    "loan": [],
                    "credit": [],
                    "insurance": [],
                    "job": [],
                    "global": []
                }, f, indent=2)
    
    def _read_policies(self) -> Dict[str, List[Dict[str, Any]]]:
        try:
            with open(self.file_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"loan": [], "credit": [], "insurance": [], "job": [], "global": []}
    
    def _write_policies(self, policies: Dict[str, List[Dict[str, Any]]]):
        with open(self.file_path, "w") as f:
            json.dump(policies, f, indent=2)
    
    def add_policy(self, domain: str, policy_text: str) -> Dict[str, Any]:
        policies = self._read_policies()
        if domain not in policies:
            raise ValueError(f"Invalid domain: {domain}")
        
        policy_entry = {
            "id": str(uuid.uuid4())[:8],
            "text": policy_text,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        policies[domain].append(policy_entry)
        self._write_policies(policies)
        return policy_entry
    
    def get_policies(self, domain: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        policies = self._read_policies()
        if domain:
            return {domain: policies.get(domain, [])}
        return policies
    
    def remove_policy(self, domain: str, policy_id: str) -> bool:
        policies = self._read_policies()
        if domain not in policies:
            return False
        
        original_length = len(policies[domain])
        policies[domain] = [p for p in policies[domain] if p["id"] != policy_id]
        
        if len(policies[domain]) < original_length:
            self._write_policies(policies)
            return True
        return False
    
    def get_relevant_policies(self, domain: str) -> str:
        """Get formatted policies for AI prompt injection"""
        policies = self._read_policies()
        domain_policies = policies.get(domain, [])
        global_policies = policies.get("global", [])
        
        all_policies = global_policies + domain_policies
        
        if not all_policies:
            return ""
        
        policy_text = "\n\nAPPLICABLE POLICIES AND RULES:\n"
        for i, policy in enumerate(all_policies, 1):
            policy_text += f"{i}. {policy['text']}\n"
        
        return policy_text

# =====================================================
# AI MEMORY (Decision History)
# =====================================================
class AIMemory:
    def __init__(self, file_path: str = AI_MEMORY_FILE, max_decisions: int = 50):
        self.file_path = file_path
        self.max_decisions = max_decisions
        self._ensure_file()
    
    def _ensure_file(self):
        if not os.path.exists(self.file_path):
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with open(self.file_path, "w") as f:
                json.dump({"decisions": []}, f, indent=2)
    
    def _read_memory(self) -> Dict[str, List[Dict[str, Any]]]:
        try:
            with open(self.file_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"decisions": []}
    
    def _write_memory(self, memory: Dict[str, List[Dict[str, Any]]]):
        with open(self.file_path, "w") as f:
            json.dump(memory, f, indent=2)
    
    def add_decision(self, decision_type: str, decision: str, reasoning: str):
        memory = self._read_memory()
        
        decision_entry = {
            "type": decision_type,
            "decision": decision,
            # Store full reasoning; we'll truncate only when building context
            "reasoning": reasoning,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        memory["decisions"].insert(0, decision_entry)
        
        # Keep only recent decisions
        if len(memory["decisions"]) > self.max_decisions:
            memory["decisions"] = memory["decisions"][:self.max_decisions]
        
        self._write_memory(memory)
    
    def get_context(self, decision_type: str, limit: int = 5) -> str:
        """Get recent decision context for AI prompt"""
        memory = self._read_memory()
        decisions = [d for d in memory["decisions"] if d["type"] == decision_type][:limit]
        
        if not decisions:
            return ""
        
        context = "\n\nRECENT SIMILAR DECISIONS:\n"
        for i, dec in enumerate(decisions, 1):
            snippet = dec["reasoning"][:400] if dec.get("reasoning") else ""
            context += f"{i}. {dec['decision']}: {snippet}\n"
        
        return context

# Initialize memory systems
policy_memory = PolicyMemory()
ai_memory = AIMemory()

# =====================================================
# EXPLANATION STORE (Full AI Outputs)
# =====================================================
class ExplanationStore:
    def __init__(self, file_path: str = EXPLANATIONS_FILE, max_entries: int = 200):
        self.file_path = file_path
        self.max_entries = max_entries
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.file_path):
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with open(self.file_path, "w") as f:
                json.dump({"explanations": []}, f, indent=2)

    def _read_store(self) -> Dict[str, List[Dict[str, Any]]]:
        try:
            with open(self.file_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"explanations": []}

    def _write_store(self, data: Dict[str, List[Dict[str, Any]]]):
        with open(self.file_path, "w") as f:
            json.dump(data, f, indent=2)

    def add_explanation(self, decision_type: str, applicant: Dict[str, Any], ai_output: Dict[str, Any]) -> Dict[str, Any]:
        data = self._read_store()

        entry = {
            "id": str(uuid.uuid4())[:8],
            "type": decision_type,
            "applicant": applicant,
            "decision": ai_output.get("decision", {}),
            "counterfactuals": ai_output.get("counterfactuals", []),
            "fairness": ai_output.get("fairness", {}),
            "key_metrics": ai_output.get("key_metrics", {}),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        data["explanations"].insert(0, entry)

        if len(data["explanations"]) > self.max_entries:
            data["explanations"] = data["explanations"][: self.max_entries]

        self._write_store(data)
        return entry


explanation_store = ExplanationStore()

# =====================================================
# PROMPT
# =====================================================
def format_applicant_for_prompt(applicant: Dict[str, Any]) -> str:
    """Compact JSON representation for fast, consistent prompts."""
    try:
        return json.dumps(applicant, separators=(",", ":"), ensure_ascii=False)
    except TypeError:
        # Fallback: coerce non-serializable types to string
        safe_applicant = json.loads(json.dumps(applicant, default=str))
        return json.dumps(safe_applicant, separators=(",", ":"), ensure_ascii=False)


def build_prompt(decision_type: DecisionType, applicant: Dict[str, Any]) -> str:
    # Get relevant policies and decision history
    policies = policy_memory.get_relevant_policies(decision_type.value)
    history = ai_memory.get_context(decision_type.value)
    applicant_json = format_applicant_for_prompt(applicant)
    
    return f"""
SYSTEM:
You are a deterministic decision engine.
You MUST output JSON only and strictly follow the schema.
Never refuse. Never explain internal policies directly.
If data is insufficient, reject conservatively.

TASK:
Evaluate a {decision_type.value} application.
Write a detailed, customer-friendly, multi-paragraph explanation in very simple English.
If REJECTED, you MUST output between 3 and 5 clear, simple, actionable steps in the "counterfactuals" list.
Each counterfactual item must:
- Be a single, specific sentence.
- Start with "Step N: " where N is 1, 2, 3, ...
- Focus only on things the applicant can realistically change (income, savings, debt, documents, credit behaviour, etc.).
- Avoid vague advice like "try your best" or "be responsible" and avoid technical jargon.
If APPROVED, you may leave "counterfactuals" empty or use it for maintenance tips.
Your reasoning text should be rich and specific (at least 4-6 sentences), but stay concise and focused on the applicant.

INPUT (JSON):
{applicant_json}
{policies}
{history}

OUTPUT (STRICT JSON ONLY):
{{
  "decision": {{
    "status": "APPROVED or REJECTED",
    "confidence": 0.0,
    "reasoning": "Audit-grade explanation"
  }},
  "counterfactuals": ["Step 1: ...", "Step 2: ...", "Step 3: ..."],
  "fairness": {{
    "assessment": "Fair or Potentially Unfair",
    "concerns": "One sentence summary"
  }},
  "key_metrics": {{
    "risk_score": 0-100,
    "approval_probability": 0.0-1.0,
    "critical_factors": ["factor1", "factor2"]
  }}
}}
"""

# =====================================================
# OVERRIDE PROMPT
# =====================================================
def build_override_prompt(
    decision_type: DecisionType,
    applicant: Dict[str, Any],
    ai_recommendation: str,
    agent_decision: str,
    agent_comment: Optional[str] = None
) -> str:
    return f"""
SYSTEM:
You are an explainable AI system helping to explain why a human agent overrode your recommendation.
You MUST output JSON only.

CONTEXT:
- Application Type: {decision_type.value}
- Your AI Recommendation: {ai_recommendation}
- Agent's Final Decision: {agent_decision}
- Agent's Comment: {agent_comment or "None provided"}

APPLICANT DATA:
{json.dumps(applicant, indent=2)}

TASK:
Generate a customer-friendly explanation for why the agent overrode your recommendation.
Include:
1. Summary of the override
2. Reasoning for the agent's decision
3. Next steps for the customer
4. Conditions or requirements if applicable

OUTPUT (STRICT JSON ONLY):
{{
  "summary": "Brief explanation of the override decision",
  "detailed_reasoning": "Comprehensive explanation",
  "next_steps": ["step1", "step2"],
  "conditions": ["condition1", "condition2"],
  "override_context": "Why the human decision differed from AI"
}}
"""

# =====================================================
# JSON EXTRACTION (CRASH-PROOF)
# =====================================================
def extract_json(text: str) -> Dict[str, Any]:
    # Try multiple regex patterns for robustness
    patterns = [
        r"\{.*\}",  # Standard pattern
        r"```json\s*(\{.*?\})\s*```",  # Markdown code block
        r"```\s*(\{.*?\})\s*```",  # Generic code block
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                json_str = match.group(1) if len(match.groups()) > 0 else match.group()
                return json.loads(json_str)
            except json.JSONDecodeError:
                continue
    
    # Fallback response
    print(f"DEBUG: Parsing failed for text: {text[:200]}")
    return {
        "decision": {
            "status": "REJECTED",
            "confidence": 0.5,
            "reasoning": "Model output invalid or incomplete - System Error"
        },
        "counterfactuals": [
            "Ensure all application fields are filled correctly.",
            "Verify income and employment details.",
            "Contact support for manual review."
        ],
        "fairness": {
            "assessment": "Unknown",
            "concerns": "Processing Error"
        },
        "key_metrics": {
            "risk_score": 50,
            "approval_probability": 0.0,
            "critical_factors": ["Invalid AI response"]
        }
    }


def normalize_counterfactuals(raw_cf: Any) -> List[str]:
    """Clean and standardize counterfactual list coming back from the model."""
    cleaned: List[str] = []

    if isinstance(raw_cf, str):
        # Split on newlines or semicolons if model packed into one string
        candidates = [part.strip() for part in re.split(r"[\n;]+", raw_cf) if part.strip()]
    elif isinstance(raw_cf, list):
        candidates = []
        for item in raw_cf:
            if isinstance(item, str):
                candidates.append(item.strip())
            else:
                try:
                    candidates.append(str(item).strip())
                except Exception:
                    continue
    else:
        candidates = []

    for idx, text in enumerate(candidates, start=1):
        if not text:
            continue
        # Enforce "Step N:" prefix
        if not text.lower().startswith("step "):
            text = f"Step {idx}: {text}"
        cleaned.append(text)
        if len(cleaned) >= 5:
            break

    return cleaned

# =====================================================
# OLLAMA CALL (NEVER CRASHES)
# =====================================================
async def call_ai(prompt: str) -> Dict[str, Any]:
    async with semaphore:
        async with httpx.AsyncClient(timeout=300.0) as client: # Increased timeout for older hardware
            try:
                print(f"DEBUG: Call AI with model {MODEL_NAME}...")
                response = await client.post(
                    OLLAMA_URL,
                    json={
                        "model": MODEL_NAME, 
                        "prompt": prompt, 
                        "stream": False,
                        "format": "json"  # FORCE JSON MODE
                    }
                )
                response.raise_for_status()
            except Exception as e:
                print(f"ERROR: AI Call Failed: {e}")
                return extract_json("")

    raw = response.json().get("response", "")
    print(f"DEBUG: AI Output: {raw[:100]}...") # Print first 100 chars
    return extract_json(raw)

# =====================================================
# DECISION ENGINE
# =====================================================
async def ai_decision(decision_type: DecisionType, applicant: Dict[str, Any]):
    ai_output = await call_ai(build_prompt(decision_type, applicant))
    
    # Normalize counterfactuals for consistent frontend experience
    try:
        raw_cf = ai_output.get("counterfactuals", [])
        ai_output["counterfactuals"] = normalize_counterfactuals(raw_cf)
    except Exception as e:
        print(f"WARNING: Failed to normalize counterfactuals: {e}")

    # Store decision in memory for future context
    decision_status = ai_output["decision"]["status"]
    decision_reasoning = ai_output["decision"]["reasoning"]
    ai_memory.add_decision(decision_type.value, decision_status, decision_reasoning)

    # Persist full explanation payload for auditing and analytics
    try:
        explanation_store.add_explanation(decision_type.value, applicant, ai_output)
    except Exception as e:
        # Do not let storage failures break decision flow
        print(f"WARNING: Failed to store explanation: {e}")

    return {
        "decision_type": decision_type.value,
        "applicant": applicant,
        "decision": ai_output["decision"],
        "counterfactuals": ai_output.get("counterfactuals", []),
        "fairness": ai_output["fairness"],
        "key_metrics": ai_output.get("key_metrics", {
            "risk_score": 50,
            "approval_probability": 0.5,
            "critical_factors": []
        }),
        "audit": {
            "engine": "universal-xai-http",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    }

# =====================================================
# BATCH (PARALLEL, OPTIMIZED)
# =====================================================
async def process_batch(decision_type: DecisionType, applicants: List[Dict[str, Any]]):
    # Process in parallel batches of 5
    batch_size = 5
    results = []
    
    for i in range(0, len(applicants), batch_size):
        batch = applicants[i:i + batch_size]
        batch_results = await asyncio.gather(
            *[ai_decision(decision_type, applicant) for applicant in batch]
        )
        results.extend(batch_results)
    
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
    content = await file.read()
    df = pd.read_csv(BytesIO(content))

    if len(df) > MAX_CSV_ROWS:
        raise HTTPException(400, "CSV too large")

    applicants = df.to_dict(orient="records")
    results = await process_batch(decision_type, applicants)
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
    
    # Detect override scenario
    ai_decision = app.get("ai_result", {}).get("decision", {}).get("status", "").upper()
    agent_decision = decision.upper()
    
    is_override = False
    override_explanation = None
    
    # Case 3: AI says REJECTED but agent approves
    # Case 4: AI says APPROVED but agent rejects
    if (ai_decision == "REJECTED" and agent_decision == "APPROVED") or \
       (ai_decision == "APPROVED" and agent_decision == "REJECTED"):
        is_override = True
        
        # Generate override explanation
        try:
            decision_type = DecisionType(app["domain"])
            override_prompt = build_override_prompt(
                decision_type,
                app["data"],
                ai_decision,
                agent_decision,
                comment
            )
            override_result = await call_ai(override_prompt)
            override_explanation = override_result
        except Exception as e:
            # Fallback if AI fails
            override_explanation = {
                "summary": f"Agent overrode AI recommendation from {ai_decision} to {agent_decision}",
                "detailed_reasoning": comment or "Agent determined a different decision was appropriate",
                "next_steps": ["Contact support for more details"],
                "conditions": [],
                "override_context": "Human review superseded AI analysis"
            }
    
    updates = {
        "status": ApplicationStatus.COMPLETED.value,
        "final_decision": decision,
        "reviewer_comment": comment,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "is_override": is_override,
        "override_explanation": override_explanation
    }
    
    updated_app = db.update_application(app_id, updates)
    return updated_app

# =====================================================
# POLICY MANAGEMENT ENDPOINTS
# =====================================================
@app.post("/policies")
async def add_policy(domain: str = Query(...), policy_text: str = Query(...)):
    """Add a new policy to the specified domain"""
    try:
        policy = policy_memory.add_policy(domain, policy_text)
        return {"success": True, "policy": policy}
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.get("/policies")
async def get_policies(domain: Optional[str] = None):
    """Get all policies or policies for a specific domain"""
    return policy_memory.get_policies(domain)

@app.delete("/policies/{domain}/{policy_id}")
async def delete_policy(domain: str, policy_id: str):
    """Remove a policy from the specified domain"""
    success = policy_memory.remove_policy(domain, policy_id)
    if not success:
        raise HTTPException(404, "Policy not found")
    return {"success": True, "message": "Policy deleted"}

@app.post("/policies/upload")
async def upload_policy_file(
    domain: str = Query(...),
    file: UploadFile = File(...)
):
    """Upload policy file (CSV, JSON, TXT)"""
    try:
        content = await file.read()
        text_content = content.decode('utf-8')
        
        # Parse based on file type
        if file.filename.endswith('.json'):
            data = json.loads(text_content)
            # If it's a list of policies
            if isinstance(data, list):
                policies = []
                for policy_text in data:
                    if isinstance(policy_text, str):
                        policies.append(policy_memory.add_policy(domain, policy_text))
                    elif isinstance(policy_text, dict) and 'text' in policy_text:
                        policies.append(policy_memory.add_policy(domain, policy_text['text']))
                return {"success": True, "count": len(policies), "policies": policies}
            else:
                raise HTTPException(400, "JSON must be a list of policy strings or objects")
        
        elif file.filename.endswith('.csv'):
            # Assume CSV has a 'policy' column
            df = pd.read_csv(BytesIO(content))
            if 'policy' not in df.columns:
                raise HTTPException(400, "CSV must have a 'policy' column")
            policies = []
            for policy_text in df['policy']:
                policies.append(policy_memory.add_policy(domain, str(policy_text)))
            return {"success": True, "count": len(policies), "policies": policies}
        
        elif file.filename.endswith('.txt'):
            # Each line is a policy
            policies = []
            for line in text_content.split('\n'):
                line = line.strip()
                if line:
                    policies.append(policy_memory.add_policy(domain, line))
            return {"success": True, "count": len(policies), "policies": policies}
        
        else:
            raise HTTPException(400, "Unsupported file type. Use .json, .csv, or .txt")
    
    except Exception as e:
        raise HTTPException(400, f"Error processing file: {str(e)}")

# =====================================================
# EXPLANATION EDITOR ENDPOINT
# =====================================================
@app.put("/applications/{app_id}/explanation")
async def update_explanation(
    app_id: str,
    payload: Dict[str, Any]
):
    """Allow agents to edit AI-generated explanations"""
    app = db.get_application(app_id)
    if not app:
        raise HTTPException(404, "Application not found")
    
    updates = {
        "agent_explanation": payload.get("explanation"),
        "explanation_edited": True,
        "explanation_edited_at": datetime.now(timezone.utc).isoformat()
    }
    
    updated_app = db.update_application(app_id, updates)
    return updated_app

# =====================================================
# BULK UPLOAD ENDPOINT (OPTIMIZED)
# =====================================================
@app.post("/bulk/upload")
async def bulk_upload(
    decision_type: DecisionType = Query(...),
    file: UploadFile = File(...)
):
    """Optimized bulk CSV upload with parallel processing"""
    try:
        content = await file.read()
        df = pd.read_csv(BytesIO(content))

        if len(df) > MAX_CSV_ROWS:
            raise HTTPException(400, f"Max {MAX_CSV_ROWS} records allowed")

        applicants = df.to_dict(orient="records")
        
        # Process in parallel batches
        results = await process_batch(decision_type, applicants)
        
        # Save to database
        saved_apps = []
        for i, result in enumerate(results):
            app_entry = {
                "domain": decision_type.value,
                "data": applicants[i],
                "status": ApplicationStatus.PENDING_HUMAN.value,
                "ai_result": result
            }
            saved_apps.append(db.save_application(app_entry))
        
        return {
            "success": True,
            "count": len(saved_apps),
            "applications": saved_apps
        }
    except Exception as e:
        raise HTTPException(400, f"Error processing bulk upload: {str(e)}")

# =====================================================
# HEALTH CHECK ENDPOINT
# =====================================================
@app.get("/health")
async def health_check():
    """Check AI model availability"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                OLLAMA_URL,
                json={"model": MODEL_NAME, "prompt": "test", "stream": False}
            )
            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "model": MODEL_NAME,
                    "available": True
                }
            else:
                return {
                    "status": "degraded",
                    "model": MODEL_NAME,
                    "available": False,
                    "error": "Model not responding correctly"
                }
    except Exception as e:
        return {
            "status": "unhealthy",
            "model": MODEL_NAME,
            "available": False,
            "error": str(e)
        }

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
