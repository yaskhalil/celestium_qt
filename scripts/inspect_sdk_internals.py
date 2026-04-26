import os
import json
import asyncio
from dotenv import load_dotenv
from webull.core.client import ApiClient
from webull.trade.request.v2.get_account_list import GetAccountList

load_dotenv()

async def inspect_sdk():
    app_key = os.getenv("WEBULL_APP_KEY")
    app_secret = os.getenv("WEBULL_APP_SECRET")
    
    api_client = ApiClient(app_key, app_secret, "us")
    
    # We will use a mock signer or similar to see what's happening
    # But easier: just use the real SDK and catch the request it builds
    from webull.core.request import ApiRequest
    
    class FakeRequest(ApiRequest):
        def __init__(self):
            super().__init__("/openapi/account/list", version='v2', method="GET")

    req = FakeRequest()
    # ApiClient._build_request is where it happens
    request_obj = api_client._build_request(req)
    
    print("--- SDK REQUEST DETAILS ---")
    print(f"Method: {request_obj._method}")
    print(f"URL: {request_obj.get_endpoint()}{request_obj.get_uri()}")
    print(f"Headers: {json.dumps(request_obj._header, indent=2)}")
    
    # To see the string to sign, we'd need to look at the signer
    signer = api_client._signer_factory.get_signer(api_client._signer_spec)
    # The signature composer is where the string is built
    from webull.core.auth.composer import default_signature_composer
    # We can't easily see it without printing from inside the composer
    
if __name__ == "__main__":
    asyncio.run(inspect_sdk())
