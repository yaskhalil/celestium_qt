import os
import json
import asyncio
from unittest.mock import MagicMock, patch
from webull.core.client import ApiClient

# Monkeypatch the generator to see the string to sign
import webull.core.auth.composer.default_signature_composer as composer

original_build = composer._build_sign_string

def build_with_print(params, uri, body_string):
    res = original_build(params, uri, body_string)
    print(f"--- STRING TO SIGN (RAW) ---\n{res}\n")
    from urllib.parse import quote
    print(f"--- ENCODED STRING TO SIGN ---\n{quote(res, safe='')}\n")
    return res

composer._build_sign_string = build_with_print

def test_token_request_building():
    app_key = "test_key"
    app_secret = "test_secret"
    api_client = ApiClient(app_key, app_secret, "us")
    api_client._resolve_endpoint = MagicMock(return_value="api.webull.com")
    
    from webull.core.request import ApiRequest
    class CreateTokenRequest(ApiRequest):
        def __init__(self):
            super().__init__("/openapi/auth/token/create", version='v2', method="POST")

    req = CreateTokenRequest()
    
    with patch('requests.Session.request') as mock_request:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"token": "xyz"}'
        mock_request.return_value = mock_response
        
        api_client.get_response(req)

if __name__ == "__main__":
    test_token_request_building()
