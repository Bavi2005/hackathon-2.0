import pandas as pd
import json
from datetime import datetime
import uuid

# -----------------------------
# 1️⃣ Load CSVs
# -----------------------------
loan_df = pd.read_csv("data/loan_application/loan_applications_raw.csv")
job_df = pd.read_csv("data/job_profiles/job_profiles_raw.csv")
insurance_df = pd.read_csv("data/insurance_claims/insurance_customers_raw.csv")
credit_df = pd.read_csv("data/credit_histories/credit_histories_raw.csv")

# -----------------------------
# 2️⃣ Mock AI / placeholder decision function
# -----------------------------

def mock_loan_decision(row):
    # Simple rules placeholder
    label = "approved" if row['credit_score'] > 650 and row['existing_debt'] < row['monthly_income']*3 else "rejected"
    explanation = f"Decision based on credit_score={row['credit_score']} and existing_debt={row['existing_debt']}"
    counterfactual = f"If credit_score increased to 651, the decision would be 'approved'"
    return label, explanation, counterfactual

def mock_job_decision(row):
    label = "hired" if row['skill_score'] > 65 else "rejected"
    explanation = f"Decision based on skill_score={row['skill_score']}"
    counterfactual = f"If skill_score increased to 66, the decision would be 'hired'"
    return label, explanation, counterfactual

def mock_insurance_decision(row):
    label = "approved" if row['claim_amount'] < 10000 else "denied"
    explanation = f"Decision based on claim_amount={row['claim_amount']}"
    counterfactual = f"If claim_amount decreased to 9999, decision would be 'approved'"
    return label, explanation, counterfactual

def mock_credit_decision(row):
    label = "low_risk" if row['credit_score'] > 650 and row['credit_utilization'] < 0.8 else "high_risk"
    explanation = f"Decision based on credit_score={row['credit_score']} and credit_utilization={row['credit_utilization']}"
    counterfactual = f"If credit_score increased to 651, risk would be 'low_risk'"
    return label, explanation, counterfactual

# -----------------------------
# 3️⃣ Apply placeholder AI and build decision schema
# -----------------------------
def build_decisions(df, domain, mock_func):
    decisions = []
    for _, row in df.iterrows():
        label, explanation, counterfactual = mock_func(row)
        decision = {
            "decision_id": str(uuid.uuid4()),
            "domain": domain,
            "timestamp": datetime.utcnow().isoformat(),
            "input_features": row.to_dict(),
            "model_output": {
                "label": label,
                "confidence": None  # placeholder for now
            },
            "explanation": {
                "summary": explanation,
            },
            "counterfactual": counterfactual,
            "fairness_flags": []  # optional, can calculate later
        }
        decisions.append(decision)
    return decisions

loan_decisions = build_decisions(loan_df, "loan", mock_loan_decision)
job_decisions = build_decisions(job_df, "job", mock_job_decision)
insurance_decisions = build_decisions(insurance_df, "insurance", mock_insurance_decision)
credit_decisions = build_decisions(credit_df, "credit", mock_credit_decision)

# -----------------------------
# 4️⃣ Save JSON files for frontend
# -----------------------------
with open("loan_decisions.json", "w") as f:
    json.dump(loan_decisions, f, indent=2)

with open("job_decisions.json", "w") as f:
    json.dump(job_decisions, f, indent=2)

with open("insurance_decisions.json", "w") as f:
    json.dump(insurance_decisions, f, indent=2)

with open("credit_decisions.json", "w") as f:
    json.dump(credit_decisions, f, indent=2)

print("✅ Mock decision JSON files created for all 4 domains!")
