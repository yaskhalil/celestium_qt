import hashlib
import hmac
import base64
import httpx
import uuid
import json
from datetime import datetime, timezone
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

    async def request(
        self, 
        method: str, 
        uri: str, 
        params: Optional[Dict[str, Any]] = None, 
        body: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        params = params or {}
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        nonce = str(uuid.uuid4())
        
        body_str = json.dumps(body) if body is not None else None
        
        signature = self._generate_signature(
            uri=uri,
            params=params,
            timestamp=timestamp,
            nonce=nonce,
            body=body_str
        )
        
        headers = {
            "x-app-key": self.app_key,
            "x-timestamp": timestamp,
            "x-signature-nonce": nonce,
            "x-signature-algorithm": "HMAC-SHA1",
            "x-signature-version": "1.0",
            "x-signature": signature,
            "Content-Type": "application/json"
        }
        
        response = await self.client.request(
            method=method,
            url=uri,
            params=params,
            content=body_str,
            headers=headers
        )
        response.raise_for_status()
        return response.json()

    async def get_account_balance(self, account_id: str) -> Dict[str, Any]:
        return await self.request("GET", "/openapi/account/balance", params={"account_id": account_id})

    async def get_positions(self, account_id: str) -> Dict[str, Any]:
        return await self.request("GET", "/openapi/account/positions", params={"account_id": account_id})

    async def place_order(self, account_id: str, order_params: Dict[str, Any]) -> Dict[str, Any]:
        return await self.request(
            "POST", 
            "/openapi/account/orders/place", 
            params={"account_id": account_id}, 
            body=order_params
        )

    async def get_bars(self, symbol: str, interval: str, count: int = 150) -> Dict[str, Any]:
        params = {
            "symbol": symbol,
            "timespan": interval,
            "count": count
        }
        return await self.request("GET", "/market-data/bars", params=params)

    async def close(self):
        await self.client.aclose()
