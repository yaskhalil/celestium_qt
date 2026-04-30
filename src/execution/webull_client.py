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
        method: str,
        uri: str, 
        params: Dict[str, Any], 
        timestamp: str, 
        nonce: str, 
        host: str,
        body: Optional[str] = None
    ) -> str:
        # Step 1: Query Params string (sorted)
        sorted_query = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        
        # Step 2: Specific Headers string (sorted)
        sign_headers = {
            "x-app-key": self.app_key,
            "x-timestamp": timestamp,
            "x-signature-nonce": nonce,
            "x-signature-version": "1.0",
            "x-signature-algorithm": "HMAC-SHA1",
            "host": host
        }
        sorted_headers = "&".join([f"{k}={v}" for k, v in sorted(sign_headers.items())])
        
        # Step 3: Body string
        body_str = body if body else ""
        
        # Step 4: Canonical string
        # Format: METHOD|URI|QUERY_PARAMS|HEADERS|BODY
        source_param = f"{method.upper()}|{uri}|{sorted_query}|{sorted_headers}|{body_str}"
        
        # Step 5: Sign
        key = (self.app_secret + "&").encode("utf-8")
        signature = hmac.new(key, source_param.encode("utf-8"), hashlib.sha1).digest()
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
        
        signature = self._generate_signature(
            method=method,
            uri=uri, 
            params=params, 
            timestamp=timestamp, 
            nonce=nonce, 
            host=host, 
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
            "x-webull-client-source": "sdk"
        }
        if self.access_token:
            headers["x-access-token"] = self.access_token
        
        url = target_base + uri
        try:
            response = await self.client.request(
                method=method, 
                url=url, 
                params=params, 
                content=body_str, 
                headers=headers,
                timeout=10.0
            )
            if response.status_code != 200:
                print(f"Request Failed: {response.status_code} {response.text} URL: {url} Version: {version}")
                response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            # More descriptive logging for HTTP errors
            print(f"Webull API HTTP Error: {e} for {method} {url}")
            raise
        except Exception as e:
            print(f"Webull API Unexpected Error: {e} type={type(e)} for {method} {url}")
            raise

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
