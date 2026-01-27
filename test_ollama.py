import asyncio
import httpx
import sys

# Configuration matches xai_agent.py
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:3b"

async def test_ai():
    print(f"Testing connection to {OLLAMA_URL} with model {MODEL_NAME}...")
    
    prompt = """
    SYSTEM: You are a JSON-only response bot.
    TASK: Say hello.
    OUTPUT: {"message": "hello"}
    """
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                OLLAMA_URL,
                json={
                    "model": MODEL_NAME, 
                    "prompt": prompt, 
                    "stream": False,
                    "format": "json"
                }
            )
            
            if response.status_code == 200:
                print("✅ Connection Successful!")
                data = response.json()
                print(f"Response: {data.get('response')}")
            else:
                print(f"❌ Server returned status: {response.status_code}")
                print(response.text)
                
    except httpx.ConnectError:
        print("❌ Connection Failed. Is Ollama running?")
        print("Try running: 'ollama serve' in a separate terminal.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_ai())
