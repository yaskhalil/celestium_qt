import httpx
import polars as pl
import structlog
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from src.config import settings

logger = structlog.get_logger()

class AlpacaClient:
    def __init__(self, api_key: str, secret_key: str, base_url: str = "https://paper-api.alpaca.markets"):
        self.api_key = api_key.strip()
        self.secret_key = secret_key.strip()
        self.base_url = base_url

        # Log key prefix for diagnostic purposes
        key_prefix = self.api_key[:4] if len(self.api_key) >= 4 else "NONE"
        logger.info("AlpacaClient initialized", base_url=self.base_url, key_prefix=key_prefix)

        # Data API is separate from Trading API
        self.data_url = "https://data.alpaca.markets/v2"
        self.headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Accept": "application/json"
        }

    async def _request(self, method: str, url: str, params: Optional[Dict[str, Any]] = None, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                params=params,
                json=body,
                headers=self.headers,
                timeout=10.0
            )
            if response.status_code != 200:
                logger.error("Alpaca API Error", status=response.status_code, text=response.text, url=url)
                response.raise_for_status()
            return response.json()

    async def get_bars(self, symbol: str, timeframe: str = "1Min", limit: int = 200) -> pl.DataFrame:
        """Fetches historical bars from Alpaca Market Data API v2."""
        url = f"{self.data_url}/stocks/bars"
        params = {
            "symbols": symbol,
            "timeframe": timeframe,
            "limit": limit,
            "adjustment": "all",
            "feed": "iex" # Use 'iex' for free tier, 'sip' for paid
        }
        try:
            res = await self._request("GET", url, params=params)
            bars_data = res.get("bars", {}).get(symbol, [])
            if not bars_data:
                return pl.DataFrame()

            bars = []
            for b in bars_data:
                bars.append({
                    "timestamp": datetime.fromisoformat(b["t"].replace("Z", "+00:00")),
                    "symbol": symbol,
                    "open": float(b["o"]),
                    "high": float(b["h"]),
                    "low": float(b["l"]),
                    "close": float(b["c"]),
                    "volume": int(b["v"])
                })
            return pl.from_dicts(bars)
        except Exception as e:
            logger.error("Alpaca: Failed to fetch bars", symbol=symbol, error=str(e))
            return pl.DataFrame()

    async def get_last_price(self, symbol: str) -> Optional[float]:
        """Fetches latest trade price from Alpaca Market Data API v2."""
        url = f"{self.data_url}/stocks/trades/latest"
        params = {"symbols": symbol, "feed": "iex"}
        try:
            res = await self._request("GET", url, params=params)
            trade = res.get("trades", {}).get(symbol, {})
            return float(trade.get("p", 0)) if trade else None
        except Exception as e:
            logger.error("Alpaca: Failed to fetch last price", symbol=symbol, error=str(e))
            return None

    async def get_account(self) -> Dict[str, Any]:
        """Fetches account details (equity, cash, etc.)."""
        url = f"{self.base_url}/v2/account"
        return await self._request("GET", url)

    async def get_position(self, symbol: str) -> float:
        """Fetches current position for a symbol."""
        url = f"{self.base_url}/v2/positions/{symbol}"
        try:
            res = await self._request("GET", url)
            return float(res.get("qty", 0))
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return 0.0
            raise e

    async def place_order(self, symbol: str, qty: float, side: str, order_type: str = "market", time_in_force: str = "day", limit_price: Optional[float] = None) -> Dict[str, Any]:
        """Places an order (supports fractional shares)."""
        url = f"{self.base_url}/v2/orders"
        body = {
            "symbol": symbol,
            "qty": str(qty), # Alpaca requires string for decimal precision
            "side": side.lower(),
            "type": order_type.lower(),
            "time_in_force": time_in_force
        }
        if order_type.lower() == "limit" and limit_price:
            body["limit_price"] = str(limit_price)
            
        return await self._request("POST", url, body=body)

    async def close(self):
        pass
