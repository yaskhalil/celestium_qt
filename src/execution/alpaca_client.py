import httpx
import polars as pl
import structlog
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Callable
from src.config import settings

logger = structlog.get_logger()

def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0,
          ignore_statuses: Optional[list] = None):
    """Retry decorator for transient API failures with exponential backoff."""
    if ignore_statuses is None:
        ignore_statuses = [404]
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            last_exc = None
            wait = delay
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except httpx.HTTPStatusError as e:
                    last_exc = e
                    if e.response.status_code in ignore_statuses:
                        raise  # Don't retry 404s, 400s
                    if attempt == max_attempts - 1:
                        raise
                    logger.warning("Retryable API error", status=e.response.status_code,
                                   attempt=attempt + 1, wait=wait)
                except (httpx.TimeoutException, httpx.ConnectError) as e:
                    last_exc = e
                    if attempt == max_attempts - 1:
                        raise
                    logger.warning("Transient API error", error=str(e),
                                   attempt=attempt + 1, wait=wait)
                await asyncio.sleep(wait)
                wait *= backoff
            raise last_exc  # type: ignore
        return wrapper
    return decorator


class AlpacaClient:
    def __init__(self, api_key: str, secret_key: str, base_url: str = "https://paper-api.alpaca.markets"):
        self.api_key = api_key.strip()
        self.secret_key = secret_key.strip()
        self.base_url = base_url

        key_prefix = self.api_key[:4] if len(self.api_key) >= 4 else "NONE"
        logger.info("AlpacaClient initialized", base_url=self.base_url, key_prefix=key_prefix)

        self.data_url = "https://data.alpaca.markets/v2"
        self.headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Accept": "application/json"
        }

        # Shared connection pool — one client for all requests
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Return shared httpx client with connection pooling."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=self.headers,
                timeout=httpx.Timeout(15.0, connect=5.0),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._client

    @retry(max_attempts=3, delay=1.0)
    async def _request(self, method: str, url: str,
                       params: Optional[Dict[str, Any]] = None,
                       body: Optional[Dict[str, Any]] = None,
                       ignore_status: Optional[list] = None) -> Dict[str, Any]:
        if ignore_status is None:
            ignore_status = []
        client = await self._get_client()
        response = await client.request(
            method=method,
            url=url,
            params=params,
            json=body,
            timeout=15.0,
        )
        if not response.is_success:
            if response.status_code not in ignore_status:
                logger.error("Alpaca API Error", status=response.status_code,
                             text=response.text[:200], url=url)
            response.raise_for_status()

        if response.status_code == 204:
            return {}
        return response.json()

    async def test_connection(self) -> bool:
        """Test if API keys are valid by fetching account. Returns True if OK."""
        try:
            acc = await self.get_account()
            if acc.get("id"):
                logger.info("Alpaca connection OK", account_id=acc["id"][:8])
                return True
            return False
        except Exception as e:
            logger.error("Alpaca connection FAILED", error=str(e))
            return False

    async def sync_account(self) -> dict:
        """Fetch account and return {equity, cash, buying_power}. Returns None dict on failure."""
        try:
            acc = await self.get_account()
            return {
                "equity": float(acc.get("equity", 0)),
                "cash": float(acc.get("cash", 0)),
                "buying_power": float(acc.get("buying_power", 0)),
                "status": acc.get("status", "unknown"),
            }
        except Exception as e:
            logger.error("Alpaca: Account sync failed", error=str(e))
            return {"equity": 0, "cash": 0, "buying_power": 0, "status": "error"}

    async def get_bars(self, symbol: str, timeframe: str = "5Min", limit: int = 200) -> pl.DataFrame:
        """Fetches historical bars. Returns empty DataFrame on failure."""
        start_time = (datetime.now(timezone.utc) - timedelta(days=5)).strftime('%Y-%m-%dT%H:%M:%SZ')
        url = f"{self.data_url}/stocks/bars"
        params = {
            "symbols": symbol,
            "timeframe": timeframe,
            "start": start_time,
            "limit": limit,
            "adjustment": "all",
            "feed": "iex"
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
                    "volume": int(b["v"]),
                })
            return pl.from_dicts(bars)
        except Exception as e:
            logger.error("Alpaca: Failed to fetch bars", symbol=symbol, error=str(e))
            return pl.DataFrame()

    async def get_last_price(self, symbol: str) -> Optional[float]:
        """Fetches latest trade price. Returns None on failure."""
        url = f"{self.data_url}/stocks/trades/latest"
        params = {"symbols": symbol, "feed": "iex"}
        try:
            res = await self._request("GET", url, params=params)
            trade = res.get("trades", {}).get(symbol, {})
            return float(trade.get("p", 0)) if trade else None
        except Exception as e:
            logger.error("Alpaca: Failed to fetch last price", symbol=symbol, error=str(e))
            return None

    async def get_last_price_conservative(self, symbol: str, default_if_fail: float = 30.0) -> float:
        """Get last price with conservative fallback (high = circuit breaker, not low)."""
        price = await self.get_last_price(symbol)
        if price is None:
            logger.warning("Alpaca: Price fetch failed, using conservative default",
                          symbol=symbol, default=default_if_fail)
            return default_if_fail
        return price

    async def get_account(self) -> Dict[str, Any]:
        url = f"{self.base_url}/v2/account"
        return await self._request("GET", url)

    async def get_position(self, symbol: str) -> float:
        url = f"{self.base_url}/v2/positions/{symbol}"
        try:
            res = await self._request("GET", url, ignore_status=[404])
            return float(res.get("qty", 0))
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return 0.0
            raise

    async def get_position_market_value(self, symbol: str) -> float:
        """Get current market value of position. Returns 0.0 if flat."""
        url = f"{self.base_url}/v2/positions/{symbol}"
        try:
            res = await self._request("GET", url, ignore_status=[404])
            return float(res.get("market_value", 0))
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return 0.0
            raise

    async def place_order(self, symbol: str, qty: float, side: str,
                          order_type: str = "market", time_in_force: str = "day",
                          limit_price: Optional[float] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/v2/orders"
        body = {
            "symbol": symbol,
            "qty": str(qty),
            "side": side.lower(),
            "type": order_type.lower(),
            "time_in_force": time_in_force,
        }
        if order_type.lower() == "limit" and limit_price:
            body["limit_price"] = str(limit_price)
        return await self._request("POST", url, body=body)

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
