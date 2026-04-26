import asyncio
import os
import json
from dotenv import load_dotenv
from src.execution.webull_client import WebullClient

load_dotenv()

async def test_verified_token():
    app_key = os.getenv("WEBULL_APP_KEY")
    app_secret = os.getenv("WEBULL_APP_SECRET")
    token = os.getenv("WEBULL_ACCESS_TOKEN")
    
    print(f"Testing Token: {token}")
    client = WebullClient(app_key, app_secret, access_token=token)
    
    try:
        print("--- Fetching Account List ---")
        res = await client.get_account_list()
        print("SUCCESS!")
        print(json.dumps(res, indent=2))
    except Exception as e:
        print(f"FAILED: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(test_verified_token())
