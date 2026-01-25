import pandas as pd
import json
import uuid
from datetime import datetime
from dotenv import load_dotenv
import os

# -----------------------------
# 1️⃣ Load .env and GEMINI_API_KEY
# -----------------------------
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("⚠️ Warning: GEMINI_API_KEY not found in .env")

# -----------------------------
# 2️⃣ Load CSV files
# -----------------------------
loan_df = pd.read_csv("data/loan_application/loan_applications_raw.csv")
job_df = pd.read_csv("data/job_profiles/job_profiles_raw.csv")
insurance_df = pd.read_csv("data/insurance_claims/insurance_customers_raw.csv")
credit_df = pd.read_csv("data/credit_histories/credit_histories_raw.csv")

# -----------------------------
# 3️⃣ Placeholder "AI" function using GEMINI_API_KEY
# -----------------------------
def call_gemini_placeholder(input_features, domain):
    """
    Simulates AI decisions. Replace with real Ollama API call later.
    """
    if domain == "loan":
        label = "approved" if input_features['credit_score'] > 650 and input_features['existing_debt'] < input_features['monthly_income']*3 else "rejected"
        explanation = f"Based on credit_score={input_features['credit_score']} and existing_debt={input_features['existing_debt']}"
        counterfactual = f"If credit_score increased to 651, decision would change"
    elif domain == "job":
        label = "hired" if input_features['skill_score'] > 65 else "rejected"
        explanation = f"Based on skill_score={input_features['skill_score']}"
        counterfactual = f"If skill_score increased to 66, decision would change"
    elif domain == "insurance":
        label = "approved" if input_features['claim_amount'] < 10000 else "denied"
        explanation = f"Based on claim_amount={input_features['claim_amount']}"
        counterfactual = f"If claim_amount decreased to 9999, decision would change"
    elif domain == "credit":
        label = "low_risk" if input_features['credit_score'] > 650 and input_features['credit_utilization'] < 0.8 else "high_risk"
        explanation = f"Based on credit_score={input_features['credit_score']} and credit_utilization={input_features['credit_utilization']}"
        counterfactual = f"If credit_score increased to 651, risk would be 'low_risk'"
    else:
        label = "unknown"
        explanation = "No rules defined"
        counterfactual = "N/A"
        
    return {
        "label": label,
        "explanation": explanation,
        "counterfactual": counterfactual,
        "confidence": None  # placeholder for now
    }

# -----------------------------
# 4️⃣ Build decision JSONs
# -----------------------------
def build_decisions(df, domain):
    decisions = []
    for _, row in df.iterrows():
        input_features = row.to_dict()
        ai_output = call_gemini_placeholder(input_features, domain)
        decision = {
            "decision_id": str(uuid.uuid4()),
            "domain": domain,
            "timestamp": datetime.utcnow().isoformat(),
            "input_features": input_features,
            "model_output": {
                "label": ai_output['label'],
                "confidence": ai_output['confidence']
            },
            "explanation": {
                "summary": ai_output['explanation']
            },
            "counterfactual": ai_output['counterfactual'],
            "fairness_flags": []  # optional for now
        }
        decisions.append(decision)
    return decisions

# -----------------------------
# 5️⃣ Generate JSON files for frontend
# -----------------------------
datasets = [
    ("loan", loan_df),
    ("job", job_df),
    ("insurance", insurance_df),
    ("credit", credit_df)
]

for domain, df in datasets:
    decisions = build_decisions(df, domain)
    filename = f"{domain}_decisions.json"
    with open(filename, "w") as f:
        json.dump(decisions, f, indent=2)
    print(f"✅ {filename} created with {len(decisions)} decisions")

print("🎉 All decision JSON files are ready for frontend integration!")
