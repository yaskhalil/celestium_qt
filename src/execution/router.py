import asyncio
import uuid
import structlog
from datetime import datetime, timezone
from typing import Optional
from src.config import settings
from src.core.oracle import AccountState
from src.execution.webull_client import WebullClient # Use our native client

logger = structlog.get_logger()

class WebullRouter:
    def __init__(self, client: WebullClient, state: AccountState):
        self.client = client
        self.state = state
        self.current_position = 0
        self.min_hold_seconds = 30

    async def _verify_position(self, symbol: str):
        try:
            # Native client uses async request
            res = await self.client.request("GET", "/openapi/account/positions", params={"account_id": settings.WEBULL_ACCOUNT_ID})
            
            # Webull OpenAPI v1/v2 response structure varies, adjust based on actual discovery
            positions = res.get("data", []) if isinstance(res, dict) else []
            symbol_position = next((p for p in positions if p.get("symbol") == symbol), None)
            
            if symbol_position:
                self.current_position = float(symbol_position.get("position", 0))
            else:
                self.current_position = 0
            logger.info("Router: Position Verified", symbol=symbol, position=self.current_position)
        except Exception as e:
            logger.error("Router: Position Verification Error", error=str(e))

    async def execute_trade(self, symbol: str, quantity: float, side: str, price: float):
        await self._verify_position(symbol)
        
        if settings.SHADOW_MODE:
            logger.info("Router: SHADOW MODE - Order would be placed", symbol=symbol, side=side, qty=quantity, price=price)
            return "shadow_order_id"

        try:
            order_params = {
                "account_id": settings.WEBULL_ACCOUNT_ID,
                "client_order_id": uuid.uuid4().hex,
                "symbol": symbol,
                "side": side,
                "order_type": "LIMIT",
                "limit_price": str(round(price, 2)),
                "quantity": str(round(quantity, 2)),
                "time_in_force": "DAY"
            }
            res = await self.client.request("POST", "/openapi/order/place", body=order_params)
            order_id = res.get("order_id")
            logger.info("Router: Order Placed", order_id=order_id)
            return order_id
        except Exception as e:
            logger.error("Router: Execution Error", error=str(e))
            return None
