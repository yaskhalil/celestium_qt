import asyncio
import uuid
import structlog
from datetime import datetime, timezone
from typing import Optional
from src.config import settings
from src.core.oracle import AccountState
from src.execution.alpaca_client import AlpacaClient

logger = structlog.get_logger()

class AlpacaRouter:
    def __init__(self, client: AlpacaClient, state: AccountState):
        self.client = client
        self.state = state
        self.current_position = 0
        self.min_hold_seconds = 30

    async def _verify_position(self, symbol: str):
        """Syncs the router's current position with the broker."""
        try:
            self.current_position = await self.client.get_position(symbol)
            logger.info("Router: Position Verified", symbol=symbol, position=self.current_position)
        except Exception as e:
            logger.error("Router: Position Verification Error", error=str(e))

    async def execute_trade(self, symbol: str, quantity: float, side: str, price: float):
        """Executes a trade via Alpaca API."""
        await self._verify_position(symbol)
        
        if settings.SHADOW_MODE:
            logger.info("Router: SHADOW MODE - Order would be placed", symbol=symbol, side=side, qty=quantity, price=price)
            return "shadow_order_id"

        try:
            # Alpaca handles fractional shares natively
            res = await self.client.place_order(
                symbol=symbol,
                qty=quantity,
                side=side,
                order_type="limit" if side == "BUY" else "market", # Use limit for entry, market for exit usually
                limit_price=round(price, 2) if side == "BUY" else None
            )
            order_id = res.get("id")
            logger.info("Router: Order Placed", order_id=order_id, symbol=symbol, side=side, qty=quantity)
            return order_id
        except Exception as e:
            logger.error("Router: Execution Error", error=str(e))
            return None
