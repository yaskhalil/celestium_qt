import asyncio
import os
import json
from dotenv import load_dotenv
from src.execution.webull_client import WebullClient

load_dotenv()

async def test():
    app_key = os.getenv("WEBULL_APP_KEY")
    app_secret = os.getenv("WEBULL_APP_SECRET")
    client = WebullClient(app_key, app_secret)
    
    print(f"Testing with Key: {app_key}")
    
    try:
        print("\n--- Attempting to Create Token ---")
        res = await client.create_token()
        print(f"Success! {json.dumps(res, indent=2)}")
    except Exception as e:
        print(f"Token creation failed: {e}")
        
    try:
        print("\n--- Attempting Account List (Expecting 401 INVALID_TOKEN) ---")
        res = await client.get_account_list()
        print(f"Success! {json.dumps(res, indent=2)}")
    except Exception as e:
        print(f"Account list failed (Expected if no token): {e}")

    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(test())
