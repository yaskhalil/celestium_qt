import hashlib
import hmac
import base64
import httpx
import uuid
import json
import polars as pl
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from urllib.parse import quote

class WebullClient:
    def __init__(self, app_key: str, app_secret: str, access_token: Optional[str] = None, 
                 base_url: str = "https://api.webull.com"):
        self.app_key = app_key
        self.app_secret = app_secret
        self.access_token = access_token
        self.base_url = base_url
        self.host = base_url.replace("https://", "").replace("http://", "").split("/")[0]

    def _generate_signature(
        self, 
        uri: str, 
        params: Dict[str, Any], 
        timestamp: str, 
        nonce: str, 
        host: str,
        body: Optional[str] = None
    ) -> str:
        # SDK-like (v1) Signature Format
        sign_params = {
            "x-app-key": self.app_key,
            "x-timestamp": timestamp,
            "x-signature-version": "1.0",
            "x-signature-algorithm": "HMAC-SHA1",
            "x-signature-nonce": nonce,
            "host": host
        }
        for k, v in params.items():
            sign_params[k.lower()] = str(v)
            
        sorted_keys = sorted(sign_params.keys())
        sorted_params_str = "&".join([f"{k}={sign_params[k]}" for k in sorted_keys])
        
        body_str = body if body else ""
        body_md5 = hashlib.md5(body_str.encode("utf-8")).hexdigest().upper()
        
        # Format: uri&params&body_md5
        source_string = f"{uri}&{sorted_params_str}&{body_md5}"
        encoded_string = quote(source_string, safe='')
        
        key = (self.app_secret + "&").encode("utf-8")
        signature = hmac.new(key, encoded_string.encode("utf-8"), hashlib.sha1).digest()
        return base64.b64encode(signature).decode("utf-8")

    async def request(
        self, 
        method: str, 
        uri: str, 
        params: Optional[Dict[str, Any]] = None, 
        body: Optional[Dict[str, Any]] = None,
        version: str = "v1"
    ) -> Dict[str, Any]:
        params = params or {}
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        nonce = str(uuid.uuid4())
        
        body_str = json.dumps(body, separators=(',', ':')) if body is not None else None
        
        signature = self._generate_signature(
            uri=uri, 
            params=params, 
            timestamp=timestamp, 
            nonce=nonce, 
            host=self.host, 
            body=body_str
        )
        
        headers = {
            "x-app-key": self.app_key,
            "x-timestamp": timestamp,
            "x-signature-nonce": nonce,
            "x-signature-algorithm": "HMAC-SHA1",
            "x-signature-version": "1.0",
            "x-signature": signature,
            "x-version": version,
            "Content-Type": "application/json",
            "x-webull-client-source": "sdk",
            "Host": self.host
        }
        if self.access_token:
            headers["x-access-token"] = self.access_token
        
        url = self.base_url + uri
        
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method, 
                url=url, 
                params=params, 
                content=body_str, 
                headers=headers,
                timeout=10.0
            )
            if response.status_code != 200:
                response.raise_for_status()
            return response.json()

    async def subscribe_quotes(self, symbols: list[str], category: str = "US_STOCK"):
        """Subscribes to market data (required for some symbols to return data in snapshots)."""
        try:
            payload = {
                "session_id": str(uuid.uuid4()),
                "symbols": symbols,
                "category": category,
                "sub_types": ["SNAPSHOT", "QUOTE", "TICK"],
                "grab": True
            }
            return await self.request("POST", "/openapi/market-data/streaming/subscribe", 
                                     body=payload, version="v2")
        except Exception as e:
            # print(f"Failed to subscribe to quotes: {e}")
            return None

    async def get_last_price(self, symbol: str) -> Optional[float]:
        """Fetches the latest price for a symbol from Webull."""
        try:
            await self.subscribe_quotes([symbol])
            
            res = await self.request("GET", "/openapi/market-data/snapshot", 
                                     params={"symbols": symbol, "category": "US_STOCK"},
                                     version="v2")
            snapshots = res.get("data", [])
            if snapshots:
                return float(snapshots[0].get("last_price", 0))
            return None
        except Exception as e:
            print(f"Failed to fetch price from Webull: {e}")
            return None

    async def get_bars(self, symbol: str, timespan: str = "M1", count: int = 200) -> pl.DataFrame:
        """Fetches historical bars from Webull."""
        try:
            res = await self.request("GET", "/openapi/market-data/bars", 
                                     params={"symbols": symbol, "category": "US_STOCK", "timespan": timespan, "count": count},
                                     version="v2")
            data_list = res.get("data", [])
            if not data_list:
                return pl.DataFrame()
            
            bars = []
            for item in data_list:
                bars.append({
                    "timestamp": datetime.fromisoformat(item["time"].replace("Z", "+00:00")),
                    "symbol": symbol,
                    "open": float(item["open"]),
                    "high": float(item["high"]),
                    "low": float(item["low"]),
                    "close": float(item["close"]),
                    "volume": int(item["volume"])
                })
            return pl.from_dicts(bars)
        except Exception as e:
            print(f"Failed to fetch bars from Webull: {e}")
            return pl.DataFrame()

    async def close(self):
        pass
