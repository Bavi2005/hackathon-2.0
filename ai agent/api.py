from fastapi import FastAPI, HTTPException, Query, Body, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import random
import uuid
import pandas as pd
from io import BytesIO

# Import logic from xai_agent
# Note: This implies xai_agent.py is in the same directory
from xai_agent import (
    ai_decision, 
    DecisionType, 
    policy_memory, 
    build_override_prompt, 
    call_ai,
    extract_json
)
from database import SimpleDB

app = FastAPI(title="Explainable AI Decision Engine (Hackathon 2.0)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

db = SimpleDB()

# =====================================================
# BACKGROUND TASKS
# =====================================================
async def process_override_explanation(app_id: str, prompt: str):
    try:
        explanation = await call_ai(prompt)
        
        # Read-Modify-Write DB
        # Note: In a real app, use a real DB with row locking
        all_apps = db._read_db()
        for i, a in enumerate(all_apps):
            if a["id"] == app_id:
                all_apps[i]["override_explanation"] = explanation
                break
        db._write_db(all_apps)
        print(f"DEBUG: Override explanation generated for {app_id}")
    except Exception as e:
        print(f"ERROR: Failed to generate override explanation: {e}")

# =====================================================
# APPLICATIONS ENDPOINTS
# =====================================================

@app.post("/applications")
async def create_application(
    decision_type: str = Query(...),
    payload: Dict[str, Any] = Body(...)
):
    """
    Submit a new application for AI review.
    """
    try:
        dtype = DecisionType(decision_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid decision_type. Must be one of {[e.value for e in DecisionType]}")
    
    # 1. Run AI Decision
    # Add timestamp to payload if not present (helps with ordering)
    if "created_at" not in payload:
        payload["created_at"] = datetime.now(timezone.utc).isoformat()
        
    # Generate a friendly ID like APP-1234
    short_id = f"APP-{random.randint(1000, 9999)}"
    
    # 2. Call AI
    result = await ai_decision(dtype, payload)
    
    # 3. Construct Application Record
    application = {
        "id": short_id,
        "domain": decision_type,
        "data": payload,
        "status": "approved" if result["decision"]["status"].upper() == "APPROVED" else "rejected", 
        "ai_result": result,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    # For user workflow, usually goes to pending human review if not auto-approved
    # But user wants "Perfect". Let's say: if rejected, it stays rejected unless human overrides. 
    # If approved, it's approved.
    # Frontend logic has tabs: "Pending Review" and "History".
    # Pending usually means "Needs Human Action". 
    # Let's map ALL to "pending_human" initially so they show up.
    application["status"] = "pending_human"
    
    # Save to DB
    saved_app = db.save_application(application)
    
    return saved_app

@app.get("/applications")
async def list_applications(status: Optional[str] = None):
    apps = db._read_db() # Accessing internal method for speed/simplicity
    if status:
        # Filter logic
        if status == "pending":
            return [a for a in apps if a.get("status") in ["pending_human", "pending_ai"]]
        elif status == "history":
             return [a for a in apps if a.get("status") not in ["pending_human", "pending_ai"]]
        else:
            return [a for a in apps if a.get("status") == status]
            
    # Return all, sorted by timestamp desc
    apps.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return apps

@app.get("/applications/{app_id}")
async def get_application(app_id: str):
    app_record = db.get_application(app_id)
    if not app_record:
        raise HTTPException(status_code=404, detail="Application not found")
    return app_record

@app.post("/applications/{app_id}/review")
async def review_application(
    app_id: str,
    background_tasks: BackgroundTasks,
    decision: str = Query(..., regex="^(approved|rejected)$"),
    comment: Optional[str] = Query(None)
):
    app_record = db.get_application(app_id)
    if not app_record:
        raise HTTPException(status_code=404, detail="Application not found")
        
    # Valid decision
    app_record["status"] = decision # approved or rejected
    app_record["reviewer_comment"] = comment
    app_record["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    app_record["final_decision"] = decision
    
    # Save immediate state first
    all_apps = db._read_db()
    for i, a in enumerate(all_apps):
        if a["id"] == app_id:
            all_apps[i] = app_record
            break
    db._write_db(all_apps)
    
    # AI Override Explanation Check
    # If human decision differs from AI decision
    ai_status = app_record.get("ai_result", {}).get("decision", {}).get("status", "").lower()
    human_status = decision.lower()
    
    if ai_status and ai_status != human_status:
        # Mark as override immediately
        app_record["is_override"] = True
        
        # Re-save "is_override" flag
        all_apps = db._read_db()
        for i, a in enumerate(all_apps):
            if a["id"] == app_id:
                all_apps[i] = app_record
                break
        db._write_db(all_apps)

        # Generate explanation in background
        try:
            dtype = DecisionType(app_record["domain"])
            prompt = build_override_prompt(
                dtype, 
                app_record["data"],
                ai_status,
                human_status,
                comment
            )
            # Add to background tasks
            background_tasks.add_task(process_override_explanation, app_id, prompt)
            
        except Exception as e:
            print(f"Error preparing override explanation task: {e}")
            
    # Update DB - effectively we need to replace the record
    # SimpleDB doesn't have update, so we read-modify-write manually
    # db.save_application appends... we need an update method.
    # Let's implement a quick update in this logic
    all_apps = db._read_db()
    for i, a in enumerate(all_apps):
        if a["id"] == app_id:
            all_apps[i] = app_record
            break
    db._write_db(all_apps)
    
    return app_record

@app.put("/applications/{app_id}/explanation")
async def update_explanation(
    app_id: str,
    payload: Dict[str, str] = Body(...)
):
    app_record = db.get_application(app_id)
    if not app_record:
        raise HTTPException(status_code=404, detail="Application not found")
        
    explanation_text = payload.get("explanation")
    if not explanation_text:
        raise HTTPException(status_code=400, detail="Missing explanation text")

    # Update explanation
    app_record["agent_explanation"] = explanation_text
    app_record["explanation_edited"] = True
    
    # Update DB
    all_apps = db._read_db()
    for i, a in enumerate(all_apps):
        if a["id"] == app_id:
            all_apps[i] = app_record
            break
    db._write_db(all_apps)
    
    return app_record

# =====================================================
# POLICIES ENDPOINTS
# =====================================================

@app.get("/policies")
async def get_policies(domain: Optional[str] = None):
    return policy_memory.get_policies(domain)

@app.post("/policies")
async def add_policy(domain: str = Query(...), policy_text: str = Query(...)):
    try:
        return policy_memory.add_policy(domain, policy_text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/policies/{domain}/{policy_id}")
async def delete_policy(domain: str, policy_id: str):
    success = policy_memory.remove_policy(domain, policy_id)
    if not success:
        raise HTTPException(status_code=404, detail="Policy not found")
    return {"status": "success"}

# =====================================================
# UTILS
# =====================================================

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}

@app.post("/applications/batch_upload")
async def batch_upload(
    decision_type: str = Query(...),
    file: UploadFile = File(...)
):
    try:
        dtype = DecisionType(decision_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid decision type")

    contents = await file.read()
    try:
        # Check if CSV
        df = pd.read_csv(BytesIO(contents))
        records = df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV: {str(e)}")
    
    processed_count = 0
    
    # Process max 10 for demo speed
    for row in records[:10]:
        # Filter NaNs
        payload = {k: v for k, v in row.items() if pd.notna(v)}
        
        # Normailze fields
        if "full_name" not in payload:
            for k in ["name", "applicant_name", "customer_name"]:
                if k in payload:
                    payload["full_name"] = payload[k]
                    break
        
        # Create ID
        short_id = f"APP-{random.randint(10000, 99999)}"
        
        # Run AI (awaiting sequentially for simplicity/stability)
        try:
            result = await ai_decision(dtype, payload)
            status = "pending_human"
        except Exception as e:
            print(f"Batch AI Error: {e}")
            status = "error"
            result = None
            
        app_entry = {
            "id": short_id,
            "domain": decision_type,
            "data": payload,
            "status": status,
            "ai_result": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        db.save_application(app_entry)
        processed_count += 1
        
    return {"message": "Batch processing completed", "count": processed_count}
