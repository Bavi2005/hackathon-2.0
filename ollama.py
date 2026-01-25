import pandas as pd
import requests
import json
from datetime import datetime, timezone

# ======================
# CONFIG
# ======================

API_URL = "http://localhost:8000/decision/json"

CSV_FILES = {
    "loan": "data/loan_application/loan_applications_raw.csv",
    "job": "data/job_profiles/job_profiles_raw.csv",
    "insurance": "data/insurance_claims/insurance_customers_raw.csv",
    "credit": "data/credit_histories/credit_histories_raw.csv",
}

# ======================
# UTIL
# ======================

def now_utc():
    return datetime.now(timezone.utc).isoformat()

def post_records(records):
    response = requests.post(API_URL, json=records, timeout=300)
    response.raise_for_status()
    return response.json()

# ======================
# PIPELINE
# ======================

def process_csv(domain, path):
    print(f"📄 Loading {path}")
    df = pd.read_csv(path)

    # Convert NaN to None (important for JSON)
    records = df.where(pd.notnull(df), None).to_dict(orient="records")

    print(f"🚀 Sending {len(records)} {domain} records to API")
    results = post_records(records)

    wrapped = []
    for i, result in enumerate(results if isinstance(results, list) else [results]):
        wrapped.append({
            "decision_id": f"{domain}_{i}",
            "domain": domain,
            "timestamp": now_utc(),
            "input": records[i],
            "output": result
        })

    return wrapped

# ======================
# MAIN
# ======================

def main():
    for domain, csv_file in CSV_FILES.items():
        print(f"\n==== {domain.upper()} ====")

        output = process_csv(domain, csv_file)

        out_file = f"{domain}_decisions.json"
        with open(out_file, "w") as f:
            json.dump(output, f, indent=2)

        print(f"✅ Saved {out_file}")

if __name__ == "__main__":
    main()
