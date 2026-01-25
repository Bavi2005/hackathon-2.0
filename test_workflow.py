import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def test_full_workflow():
    print("--- 1. Submitting Application ---")
    payload = {
        "age": 30,
        "monthly_income": 5000,
        "credit_score": 700,
        "loan_amount": 10000
    }
    # Submit as a "loan" application
    params = {"decision_type": "loan"}
    response = requests.post(f"{BASE_URL}/applications", params=params, json=payload)
    if response.status_code != 200:
        print(f"FAILED to submit: {response.text}")
        return
    
    app_data = response.json()
    app_id = app_data["id"]
    print(f"Application Created! ID: {app_id}")
    print(f"Initial Status: {app_data['status']}")
    print(f"AI Decision: {app_data['ai_result']['decision']['status']}")
    
    # Verify it is in the pending list
    print("\n--- 2. Checking Pending List ---")
    response = requests.get(f"{BASE_URL}/applications")
    apps = response.json()
    found = False
    for app in apps:
        if app["id"] == app_id:
            found = True
            print(f"Found app in list with status: {app['status']}")
            break
    
    if not found:
        print("FAILED: App not found in list")
        return

    # Simulate Human Review
    print("\n--- 3. Submitting Human Review ---")
    review_params = {"decision": "approved", "comment": "Looks good to me"}
    response = requests.post(f"{BASE_URL}/applications/{app_id}/review", params=review_params)
    if response.status_code != 200:
        print(f"FAILED to review: {response.text}")
        return

    reviewed_app = response.json()
    print(f"Review Submitted. New Status: {reviewed_app['status']}")
    print(f"Final Decision: {reviewed_app.get('final_decision')}")

    # Verify final state
    print("\n--- 4. Verifying Final State ---")
    response = requests.get(f"{BASE_URL}/applications/{app_id}")
    final_app = response.json()
    if final_app["status"] == "completed" and final_app["final_decision"] == "approved":
        print("SUCCESS: Workflow verified!")
    else:
        print(f"FAILED: Unexpected final state: {final_app}")

if __name__ == "__main__":
    test_full_workflow()
