import asyncio
import uuid
import structlog
from datetime import datetime, timezone
from typing import Optional
from src.config import settings
from src.core.oracle import AccountState
from src.execution.alpaca_client import AlpacaClient
from src.core.notifier import TelegramNotifier

logger = structlog.get_logger()

class AlpacaRouter:
    def __init__(self, client: AlpacaClient, state: AccountState):
        self.client = client
        self.state = state
        self.notifier = TelegramNotifier()
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

        # Compliance: Minimum Hold Time (prevent GFV)
        if side == "SELL" and self.current_position > 0:
            if self.state.current_entry_time:
                elapsed = (datetime.now(timezone.utc) - self.state.current_entry_time).total_seconds()
                if elapsed < self.min_hold_seconds:
                    wait_time = self.min_hold_seconds - elapsed
                    logger.warning("Router: Minimum hold not met. Waiting.", wait=round(wait_time, 2))
                    await asyncio.sleep(wait_time)
        
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
            
            # Send Notification
            await self.notifier.notify_trade(symbol, side, quantity, price, order_id or "N/A")

            # Update state with entry time for sell check
            if side == "BUY":
                self.state.current_entry_time = datetime.now(timezone.utc)
            else:
                self.state.current_entry_time = None

            return order_id
        except Exception as e:
            logger.error("Router: Execution Error", error=str(e))
            return None
