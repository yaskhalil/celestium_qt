import os
import json
import asyncio
from dotenv import load_dotenv
from webull.core.client import ApiClient

load_dotenv()

async def create_token():
    app_key = os.getenv("WEBULL_APP_KEY")
    app_secret = os.getenv("WEBULL_APP_SECRET")
    
    api_client = ApiClient(app_key, app_secret, "us")
    api_client.add_endpoint("us", "us-openapi-alb.uat.webullbroker.com")
    
    # Manually construct CreateToken request
    from webull.core.request import ApiRequest
    
    class CreateTokenRequest(ApiRequest):
        def __init__(self):
            super().__init__("/openapi/auth/token/create", version='v2', method="POST")

    req = CreateTokenRequest()
    try:
        res = await asyncio.to_thread(api_client.get_response, req)
        print(f"Status: {res.status_code}")
        print(f"Body: {res.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(create_token())
