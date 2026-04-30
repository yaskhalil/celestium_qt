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
                 base_url: str = "https://api.webull.com",
                 quotes_url: str = "https://usquotes-api.webullfintech.com"):
        self.app_key = app_key
        self.app_secret = app_secret
        self.access_token = access_token
        self.base_url = base_url
        self.quotes_url = quotes_url
        self.client = httpx.AsyncClient()

    def _generate_signature(
        self, 
        uri: str, 
        params: Dict[str, Any], 
        timestamp: str, 
        nonce: str, 
        host: str,
        body: Optional[str] = None
    ) -> str:
        sign_params = {
            "x-app-key": self.app_key,
            "x-timestamp": timestamp,
            "x-signature-version": "1.0",
            "x-signature-algorithm": "HMAC-SHA1",
            "x-signature-nonce": nonce,
            "host": host
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
        body: Optional[Dict[str, Any]] = None,
        is_quote: bool = False,
        version: str = "v1"
    ) -> Dict[str, Any]:
        params = params or {}
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        nonce = str(uuid.uuid4())
        
        target_base = self.quotes_url if is_quote else self.base_url
        host = target_base.replace("https://", "").replace("http://", "").split("/")[0]
        
        body_str = json.dumps(body, separators=(',', ':')) if body is not None else None
        
        signature = self._generate_signature(uri=uri, params=params, timestamp=timestamp, nonce=nonce, host=host, body=body_str)
        
        headers = {
            "Host": host,
            "x-app-key": self.app_key,
            "x-timestamp": timestamp,
            "x-signature-nonce": nonce,
            "x-signature-algorithm": "HMAC-SHA1",
            "x-signature-version": "1.0",
            "x-signature": signature,
            "x-version": version,
            "Content-Type": "application/json",
            "x-webull-client-source": "sdk"
        }
        if self.access_token:
            headers["x-access-token"] = self.access_token
        
        url = target_base + uri
        response = await self.client.request(method=method, url=url, params=params, content=body_str, headers=headers)
        if response.status_code != 200:
            print(f"Request Failed: {response.status_code} {response.text} URL: {url} Version: {version}")
        response.raise_for_status()
        return response.json()

    async def subscribe_quotes(self, symbols: list[str], category: str = "US_STOCK"):
        """Subscribes to market data (required for some symbols to return data in snapshots)."""
        try:
            # We use a dummy session_id as we are using HTTP polling, not MQTT
            # But the Subscribe call with grab=true can sometimes trigger data activation
            payload = {
                "session_id": str(uuid.uuid4()),
                "symbols": symbols,
                "category": category,
                "sub_types": ["SNAPSHOT", "QUOTE", "TICK"],
                "grab": True
            }
            return await self.request("POST", "/openapi/market-data/streaming/subscribe", 
                                     body=payload, is_quote=True, version="v2")
        except Exception as e:
            print(f"Failed to subscribe to quotes: {e}")
            return None

    async def get_last_price(self, symbol: str) -> Optional[float]:
        """Fetches the latest price for a symbol from Webull."""
        try:
            # First ensure we are 'subscribed' to activate the data feed
            await self.subscribe_quotes([symbol])
            
            res = await self.request("GET", "/openapi/market-data/snapshot", 
                                     params={"symbols": symbol, "category": "US_STOCK"},
                                     is_quote=True, version="v2")
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
                                     is_quote=True, version="v2")
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
        await self.client.aclose()
