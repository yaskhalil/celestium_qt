import os
import json
import asyncio
from dotenv import load_dotenv
from webull.core.client import ApiClient

load_dotenv()

async def test_token():
    app_key = os.getenv("WEBULL_APP_KEY")
    app_secret = os.getenv("WEBULL_APP_SECRET")
    
    print(f"Testing with Key: {app_key}")
    
    api_client = ApiClient(app_key, app_secret, "us")
    # Try creating a token request manually
    from webull.trade.request.v2.get_account_list import GetAccountList
    
    req = GetAccountList()
    try:
        res = await asyncio.to_thread(api_client.get_response, req)
        print(f"Status: {res.status_code}")
        print(f"Body: {res.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_token())
