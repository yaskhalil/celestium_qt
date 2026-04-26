import hashlib
import hmac
import base64
import httpx
import uuid
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from urllib.parse import quote

class WebullClient:
    def __init__(self, app_key: str, app_secret: str, access_token: Optional[str] = None, base_url: str = "https://api.webull.com"):
        self.app_key = app_key
        self.app_secret = app_secret
        self.access_token = access_token
        self.base_url = base_url
        self.host = base_url.replace("https://", "").replace("http://", "").split("/")[0]
        self.client = httpx.AsyncClient(base_url=base_url)

    def _generate_signature(
        self, 
        uri: str, 
        params: Dict[str, Any], 
        timestamp: str, 
        nonce: str, 
        body: Optional[str] = None
    ) -> str:
        sign_params = {
            "x-app-key": self.app_key,
            "x-timestamp": timestamp,
            "x-signature-version": "1.0",
            "x-signature-algorithm": "HMAC-SHA1",
            "x-signature-nonce": nonce,
            "host": self.host
        }
        for k, v in params.items():
            k_lower = k.lower()
            if k_lower in sign_params:
                sign_params[k_lower] = f"{sign_params[k_lower]}&{v}"
            else:
                sign_params[k_lower] = str(v)
        
        sorted_keys = sorted(sign_params.keys())
        sorted_array = [f"{k}={sign_params[k]}" for k in sorted_keys]
        
        string_to_sign = uri
        if string_to_sign:
            string_to_sign += "&" + "&".join(sorted_array)
        else:
            string_to_sign = "&".join(sorted_array)
            
        if body:
            body_md5 = hashlib.md5(body.encode("utf-8")).hexdigest().upper()
            string_to_sign += "&" + body_md5
            
        encoded_string = quote(string_to_sign, safe='')
        key = (self.app_secret + "&").encode("utf-8")
        signature = hmac.new(key, encoded_string.encode("utf-8"), hashlib.sha1).digest()
        return base64.b64encode(signature).decode("utf-8")

    async def request(
        self, 
        method: str, 
        uri: str, 
        params: Optional[Dict[str, Any]] = None, 
        body: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        params = params or {}
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        nonce = str(uuid.uuid4()) # Keep hyphens

        
        # If method is POST and body is None, use empty dict to ensure BodyMD5 is generated if needed
        # Or check if Webull expects no body
        body_str = json.dumps(body, separators=(',', ':')) if body is not None else None
        
        signature = self._generate_signature(uri=uri, params=params, timestamp=timestamp, nonce=nonce, body=body_str)
        
        headers = {
            "Host": self.host,
            "x-app-key": self.app_key,
            "x-timestamp": timestamp,
            "x-signature-nonce": nonce,
            "x-signature-algorithm": "HMAC-SHA1",
            "x-signature-version": "1.0",
            "x-signature": signature,
            "x-version": "v1",
            "Content-Type": "application/json",
            "x-webull-client-source": "sdk"
        }
        if self.access_token:
            headers["x-access-token"] = self.access_token
        
        response = await self.client.request(method=method, url=uri, params=params, content=body_str, headers=headers)
        if response.status_code != 200:
            print(f"Request Failed: {response.status_code} {response.text}")
        response.raise_for_status()
        return response.json()

    async def create_token(self) -> Dict[str, Any]:
        # Try passing empty dict as body for POST
        return await self.request("POST", "/openapi/auth/token/create", body={})

    async def get_account_list(self) -> Dict[str, Any]:
        return await self.request("GET", "/openapi/account/list")

    async def close(self):
        await self.client.aclose()
