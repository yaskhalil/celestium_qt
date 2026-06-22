import asyncio
import structlog
from datetime import datetime, timezone
from typing import Optional
from src.config import settings
from src.core.oracle import AccountState, Oracle
from src.execution.alpaca_client import AlpacaClient
from src.core.notifier import TelegramNotifier

logger = structlog.get_logger()

class PositionManager:
    """
    Deep execution module managing active positions, stops, limits, 
    compliance hold rules, and broker execution logic.
    """
    def __init__(self, client: AlpacaClient, state: AccountState, oracle: Oracle, notifier: Optional[TelegramNotifier] = None):
        self.client = client
        self.state = state
        self.oracle = oracle
        self.notifier = notifier or TelegramNotifier()
        self.current_position = 0
        self.min_hold_seconds = 30
        
        # Local position tracking
        self.entry_price = 0.0
        self.stop_loss = 0.0
        self.take_profit = 0.0

    async def _verify_position(self, symbol: str):
        """Syncs the current position with the broker."""
        try:
            self.current_position = await self.client.get_position(symbol)
            logger.info("PositionManager: Position Verified", symbol=symbol, position=self.current_position)
        except Exception as e:
            logger.error("PositionManager: Position Verification Error", error=str(e))

    async def update_price(self, symbol: str, price: float):
        """Monitors current market price and exits position if stops/limits hit."""
        await self._verify_position(symbol)
        if self.current_position != 0:
            if price <= self.stop_loss:
                logger.warning("PositionManager: STOP LOSS HIT", price=self.stop_loss, current=price)
                await self.execute_trade(symbol, abs(self.current_position), "SELL", price=price)
            elif price >= self.take_profit:
                logger.info("PositionManager: TAKE PROFIT HIT", price=self.take_profit, current=price)
                await self.execute_trade(symbol, abs(self.current_position), "SELL", price=price)

    async def flatten(self, symbol: str, price: float):
        """Unconditionally exits active position (e.g. EOD or emergency)."""
        await self._verify_position(symbol)
        if self.current_position != 0:
            logger.warning("PositionManager: Unconditional flatten triggered", symbol=symbol, position=self.current_position, price=price)
            await self.execute_trade(symbol, abs(self.current_position), "SELL", price=price)

    async def execute_trade(self, symbol: str, quantity: float, side: str, price: float, tp: float = 0.0, sl: float = 0.0):
        """Executes a trade via Alpaca API and updates local and Oracle state."""
        await self._verify_position(symbol)

        # Compliance: Minimum Hold Time (prevent GFV)
        if side == "SELL" and self.current_position > 0:
            if self.state.current_entry_time:
                elapsed = (datetime.now(timezone.utc) - self.state.current_entry_time).total_seconds()
                if elapsed < self.min_hold_seconds:
                    wait_time = self.min_hold_seconds - elapsed
                    logger.warning("PositionManager: Minimum hold not met. Waiting.", wait=round(wait_time, 2))
                    await asyncio.sleep(wait_time)
        
        if settings.SHADOW_MODE:
            logger.info("PositionManager: SHADOW MODE - Order would be placed", symbol=symbol, side=side, qty=quantity, price=price)
            await self.notifier.notify_trade(symbol, side, quantity, price, "shadow_order_id", tp=tp, sl=sl)
            
            # Update local tracking and oracle session for Shadow Mode
            self._update_local_and_oracle_state(quantity, side, price, tp, sl)
            return "shadow_order_id"

        try:
            res = await self.client.place_order(
                symbol=symbol,
                qty=quantity,
                side=side,
                order_type="limit" if side == "BUY" else "market",
                limit_price=round(price, 2) if side == "BUY" else None
            )
            order_id = res.get("id")
            logger.info("PositionManager: Order Placed", order_id=order_id, symbol=symbol, side=side, qty=quantity)
            
            # Send Notification
            await self.notifier.notify_trade(symbol, side, quantity, price, order_id or "N/A", tp=tp, sl=sl)

            # Update local tracking and oracle session
            self._update_local_and_oracle_state(quantity, side, price, tp, sl)
            return order_id
        except Exception as e:
            logger.error("PositionManager: Execution Error", error=str(e))
            return None

    def _update_local_and_oracle_state(self, quantity: float, side: str, price: float, tp: float, sl: float):
        """Helper to sync positions and Oracle session cash flows."""
        if side == "BUY":
            self.entry_price = price
            self.take_profit = tp
            self.stop_loss = sl
            self.state.current_entry_time = datetime.now(timezone.utc)
            
            self.oracle.update_session(cash_flow=quantity * price, quantity=quantity, side="BUY")
        else:
            # Calculate PnL on exit
            pnl = (price - self.entry_price) * self.current_position * settings.TICK_VALUE
            self.oracle.update_session(pnl=pnl, cash_flow=quantity * price, quantity=quantity, side="SELL")
            
            self.entry_price = 0.0
            self.take_profit = 0.0
            self.stop_loss = 0.0
            self.current_position = 0
            self.state.current_entry_time = None
