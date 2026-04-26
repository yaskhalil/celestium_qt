import os
import json
import asyncio
from unittest.mock import MagicMock, patch
from webull.core.client import ApiClient

def test_token_request_building():
    app_key = "test_key"
    app_secret = "test_secret"
    api_client = ApiClient(app_key, app_secret, "us")
    
    # Mock endpoint resolution to avoid /openapi/config call
    api_client._resolve_endpoint = MagicMock(return_value="api.webull.com")
    
    from webull.core.request import ApiRequest
    class CreateTokenRequest(ApiRequest):
        def __init__(self):
            super().__init__("/openapi/auth/token/create", version='v2', method="POST")

    req = CreateTokenRequest()
    
    # Mocking the HTTP call to see what was sent
    with patch('requests.Session.request') as mock_request:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"token": "xyz", "expires": 123, "status": "PENDING"}'
        mock_request.return_value = mock_response
        
        api_client.get_response(req)
        
        # Capture the call
        args, kwargs = mock_request.call_args
        print("--- CAPTURED REQUEST ---")
        print(f"Method: {kwargs.get('method')}")
        print(f"URL: {kwargs.get('url')}")
        print(f"Headers: {json.dumps(kwargs.get('headers'), indent=2)}")
        print(f"Data: {kwargs.get('data')}")

if __name__ == "__main__":
    test_token_request_building()
