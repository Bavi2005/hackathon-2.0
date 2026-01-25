import json
import requests

IN_FILE = "ai agent/inquiries.json"
OUT_FILE = "inquiries_with_decisions.json"

# Ollama API URL (your uvicorn server running Ollama model)
OLLAMA_URL = "http://127.0.0.1:8000/decision/json"

def run_ai_on_inquiry(inquiry):
    """
    Sends a single inquiry to Ollama AI and returns the AI response.
    """
    payload = inquiry["data"]
    params = {"decision_type": inquiry["domain"]}

    try:
        response = requests.post(OLLAMA_URL, params=params, json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error for inquiry {inquiry['id']}: {e}")
        return {"error": str(e)}

def main():
    # Load inquiries
    with open(IN_FILE, "r") as f:
        inquiries = json.load(f)

    updated_inquiries = []

    for inquiry in inquiries:
        print(f"Processing inquiry {inquiry['id']} ({inquiry['domain']})...")
        ai_result = run_ai_on_inquiry(inquiry)
        # Save AI result into the record
        inquiry["ai_result"] = ai_result
        updated_inquiries.append(inquiry)

    # Save to new JSON
    with open(OUT_FILE, "w") as f:
        json.dump(updated_inquiries, f, indent=2)

    print(f"Done! Results saved to {OUT_FILE}")

if __name__ == "__main__":
    main()
