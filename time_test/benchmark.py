import sys
import os
import time
import asyncio
import json
import random

# Add parent directory to path to import xai_agent
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "ai agent"))

try:
    from xai_agent import ai_decision, DecisionType
except ImportError as e:
    print(f"Error importing xai_agent: {e}")
    sys.exit(1)

async def benchmark():
    print("Starting AI Benchmark...")
    results = []

    # 1. Single JSON Test
    print("\n--- Test 1: Single JSON Request (Loan) ---")
    payload = {
        "applicant_id": "TEST-001",
        "monthly_income": 5000,
        "credit_score": 720,
        "loan_amount": 10000,
        "employment_years": 5
    }
    
    start_time = time.time()
    try:
        await ai_decision(DecisionType.loan, payload)
        duration = time.time() - start_time
        print(f"✅ Single JSON: {duration:.2f} seconds")
        results.append(f"Single JSON Decision: {duration:.2f} seconds")
    except Exception as e:
        print(f"❌ Single JSON Failed: {e}")
        results.append(f"Single JSON Decision: FAILED ({e})")

    # 2. Batch Simulated Test (5 records)
    print("\n--- Test 2: Batch CSV Simulation (5 records) ---")
    start_time = time.time()
    batch_size = 5
    tasks = []
    for i in range(batch_size):
        p = payload.copy()
        p["applicant_id"] = f"TEST-BATCH-{i}"
        p["credit_score"] = random.randint(600, 800)
        tasks.append(ai_decision(DecisionType.loan, p))
    
    try:
        await asyncio.gather(*tasks)
        duration = time.time() - start_time
        print(f"✅ Batch (5 items): {duration:.2f} seconds")
        print(f"   Avg per item: {duration/batch_size:.2f} seconds")
        results.append(f"Batch ({batch_size} records): {duration:.2f} seconds (Avg {duration/batch_size:.2f}s/item)")
    except Exception as e:
        print(f"❌ Batch Failed: {e}")
        results.append(f"Batch Test: FAILED ({e})")

    # Write results
    with open("time_test/timing.txt", "w") as f:
        f.write("\n".join(results))
    print("\nResults saved to time_test/timing.txt")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(benchmark())
