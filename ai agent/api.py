from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import csv
import io
from typing import Union, List
import json
import os
from uuid import uuid4
from datetime import datetime, timezone

app = FastAPI(title="Explainable AI Decision Engine")

# Allow all origins for simple UI testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# =========================
# POST JSON directly
# =========================
@app.post("/decision/json")
async def decision_json(payload: Union[dict, List[dict]]):
    """
    Accepts a single record or list of records
    """
    if isinstance(payload, list):
        results = explain_decision_batch(payload)
    else:
        results = explain_decision(payload)
    return JSONResponse(results)

# =========================
# POST CSV file
# =========================
@app.post("/decision/csv")
async def decision_csv(file: UploadFile = File(...)):
    """
    Accepts CSV, converts to dicts, runs decision engine
    """
    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    records = []
    for row in reader:
        numeric_row = {}
        for k, v in row.items():
            try:
                numeric_row[k] = float(v)
            except ValueError:
                numeric_row[k] = v
        records.append(numeric_row)
    results = explain_decision_batch(records)
    return JSONResponse(results)

# =========================
# POST Form Input
# =========================
@app.post("/decision/form")
async def decision_form(
    age: float = Form(...),
    income: float = Form(...),
    credit_score: float = Form(...),
    existing_loans: float = Form(...),
    employment_years: float = Form(...)
):
    """
    Accepts standard form fields
    """
    record = {
        "age": age,
        "income": income,
        "credit_score": credit_score,
        "existing_loans": existing_loans,
        "employment_years": employment_years
    }
    result = explain_decision(record)
    return JSONResponse(result)

#Zep Code

ALLOWED_DOMAINS = {"loan", "job", "credit", "insurance"}

@app.post("/inquiry")
async def inquiry(payload: dict):
    domain = payload.get("domain")
    data = payload.get("data")

    # ✅ Validation
    if not domain or not data:
        return JSONResponse(
            status_code=400,
            content={"error": "Missing domain or data"}
        )
    if domain not in ALLOWED_DOMAINS:
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid domain '{domain}'"}
        )

    inquiry_id = f"inq_{uuid4().hex[:8]}"
    record = {
        "id": inquiry_id,
        "domain": domain,
        "data": data,
        "status": "received",
        "timestamp": now_utc()
    }

    save_inquiry(record)

    return JSONResponse({
        "message": "Inquiry received",
        "inquiry_id": inquiry_id
    })

DATA_FILE = "inquiries.json"

def now_utc():
    return datetime.now(timezone.utc).isoformat()

def save_inquiry(record):
    data = []
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)

    data.append(record)

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
