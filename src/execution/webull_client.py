import hashlib
import hmac
import base64
import httpx
from typing import Optional, Dict, Any

class WebullClient:
    def __init__(self, app_key: str, app_secret: str, base_url: str = "https://openapi.webull.com"):
        self.app_key = app_key
        self.app_secret = app_secret
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url)

    def _generate_signature(
        self, 
        uri: str, 
        params: Dict[str, Any], 
        timestamp: str, 
        nonce: str, 
        body: Optional[str] = None
    ) -> str:
        """
        Webull Signature Logic:
        1. Headers required: x-app-key, x-timestamp, x-signature-nonce, x-signature-algorithm, x-signature-version.
        2. Sort parameters (lower-cased header keys + query params) alphabetically.
        3. String to sign: uri + "&" + sorted_params + "&" + body_md5 (if body exists).
        4. Sign with HMAC-SHA1 using (app_secret + "&") as key.
        5. Base64 encode the result.
        """
        sig_headers = {
            "x-app-key": self.app_key,
            "x-timestamp": timestamp,
            "x-signature-nonce": nonce,
            "x-signature-algorithm": "HMAC-SHA1",
            "x-signature-version": "1.0",
        }
        
        # Combine signature headers and query params
        all_params = {**sig_headers, **params}
        
        # Sort by key alphabetically
        sorted_keys = sorted(all_params.keys())
        sorted_params_str = "&".join([f"{k}={all_params[k]}" for k in sorted_keys])
        
        # Construct string to sign
        string_to_sign = f"{uri}&{sorted_params_str}"
        if body:
            body_md5 = hashlib.md5(body.encode("utf-8")).hexdigest()
            string_to_sign += f"&{body_md5}"
            
        # Signing
        key = (self.app_secret + "&").encode("utf-8")
        signature = hmac.new(
            key, 
            string_to_sign.encode("utf-8"), 
            hashlib.sha1
        ).digest()
        
        return base64.b64encode(signature).decode("utf-8")

    async def close(self):
        await self.client.aclose()
