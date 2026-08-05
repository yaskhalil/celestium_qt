"""
Position Manager — Execution router managing position lifecycle and broker integration.

Responsibilities:
1. Order placement: BUY/SELL to Alpaca (with shadow mode fallback)
2. Position tracking: Syncs qty, entry price, stop/limit levels
3. Exit monitoring: Checks for SL/TP hits, validates through Oracle
4. GFV compliance: Enforces 30-second minimum hold before sells
5. State updates: Feeds PnL and cash flow into Oracle/AccountState

The position manager is the single point of broker integration.
Shadow mode allows strategy testing without real market impact.
"""
import asyncio
import structlog
from datetime import datetime, timezone
from typing import Optional, Tuple
from src.config import settings
from src.core.oracle import AccountState, Oracle
from src.execution.alpaca_client import AlpacaClient
from src.core.notifier import TelegramNotifier

logger = structlog.get_logger()

class PositionManager:
    """Execution module managing positions, stops, limits, and broker integration."""

    def __init__(self, client: AlpacaClient, state: AccountState,
                 oracle: Oracle, notifier: Optional[TelegramNotifier] = None):
        self.client = client
        self.state = state
        self.oracle = oracle
        self.notifier = notifier or TelegramNotifier()
        self.current_position = 0
        self.min_hold_seconds = 30

        self.entry_price = 0.0
        self.stop_loss = 0.0
        self.take_profit = 0.0

    async def sync_position(self, symbol: str):
        """Reconcile position and market value from broker. Call on startup and every monitor tick."""
        try:
            self.current_position = await self.client.get_position(symbol)
            market_value = await self.client.get_position_market_value(symbol)
            self.state.position_market_value = market_value
            self.state.equity = self.state.balance + market_value
            logger.info("Position synced", symbol=symbol,
                       qty=self.current_position, market_value=market_value)
        except Exception as e:
            logger.error("Position sync failed", error=str(e))

    async def _verify_position(self, symbol: str):
        """Legacy alias for sync_position."""
        await self.sync_position(symbol)

    async def update_price(self, symbol: str, price: float):
        """Monitor price and exit if stops/limits hit — validates SELL via Oracle."""
        await self.sync_position(symbol)
        if self.current_position == 0:
            return

        should_exit = False
        exit_reason = ""

        if self.stop_loss > 0 and price <= self.stop_loss:
            should_exit = True
            exit_reason = "STOP LOSS"
        elif self.take_profit > 0 and price >= self.take_profit:
            should_exit = True
            exit_reason = "TAKE PROFIT"

        if should_exit:
            # Validate SELL through Oracle
            approved, reason = self.oracle.validate_sell(abs(self.current_position), price)
            if not approved:
                logger.warning("Oracle blocked SELL", reason=reason, exit_reason=exit_reason)
                return

            logger.info(f"PositionManager: {exit_reason} HIT", price=price)
            await self.execute_trade(symbol, abs(self.current_position), "SELL", price=price)

    async def flatten(self, symbol: str, price: float):
        """Unconditional position exit (EOD or emergency)."""
        await self.sync_position(symbol)
        if self.current_position == 0:
            return

        # Validate SELL through Oracle
        approved, reason = self.oracle.validate_sell(abs(self.current_position), price)
        if not approved:
            logger.warning("Oracle blocked flatten", reason=reason)
            return

        logger.warning("Flatten triggered", symbol=symbol,
                      qty=self.current_position, price=price)
        await self.execute_trade(symbol, abs(self.current_position), "SELL", price=price)

    async def execute_trade(self, symbol: str, quantity: float, side: str,
                            price: float, tp: float = 0.0, sl: float = 0.0) -> Optional[str]:
        """Execute trade — validates BUY via Oracle, SELL via validate_sell()."""
        await self.sync_position(symbol)

        # Compliance: minimum hold time (GFV prevention)
        if side.upper() == "SELL" and self.current_position > 0:
            if self.state.current_entry_time:
                elapsed = (datetime.now(timezone.utc) - self.state.current_entry_time).total_seconds()
                if elapsed < self.min_hold_seconds:
                    wait = self.min_hold_seconds - elapsed
                    logger.warning("Min hold not met, waiting", wait=round(wait, 2))
                    await asyncio.sleep(wait)

        if settings.SHADOW_MODE:
            qty_label = f"{quantity:.4f}" if quantity < 1 else f"{quantity:.2f}"
            logger.info("SHADOW MODE", symbol=symbol, side=side, qty=qty_label, price=price)
            await self.notifier.notify_trade(symbol, side, quantity, price,
                                            "shadow_order_id", tp=tp, sl=sl)
            self._update_local_state(quantity, side, price, tp, sl)
            return "shadow_order_id"

        try:
            res = await self.client.place_order(
                symbol=symbol, qty=quantity, side=side
            )
            order_id = res.get("id", "unknown")
            logger.info("Order placed", symbol=symbol, side=side,
                       qty=quantity, order_id=order_id)
            await self.notifier.notify_trade(symbol, side, quantity, price,
                                            order_id, tp=tp, sl=sl)
            self._update_local_state(quantity, side, price, tp, sl)
            return order_id
        except Exception as e:
            logger.error("Order failed", error=str(e))
            await self.notifier.notify(f"❌ Order failed: {symbol} {side} {quantity} — {e}")
            return None

    def _update_local_state(self, quantity: float, side: str, price: float,
                            tp: float = 0.0, sl: float = 0.0):
        """Update local tracking after trade execution."""
        cost = quantity * price
        self.state.current_daily_trades += 1

        if side.upper() == "BUY":
            self.current_position += quantity
            self.entry_price = price
            self.take_profit = tp
            self.stop_loss = sl
            self.state.current_entry_time = datetime.now(timezone.utc)
            # Update Oracle state
            self.oracle.update_session(pnl=0.0, cash_flow=cost, quantity=quantity,
                                      side="BUY", position_value=cost)
        elif side.upper() == "SELL":
            self.current_position = 0
            estimated_pnl = quantity * (price - self.entry_price)
            self.oracle.update_session(pnl=estimated_pnl, cash_flow=cost, quantity=quantity,
                                      side="SELL", position_value=0)
            self.entry_price = 0.0
            self.take_profit = 0.0
            self.stop_loss = 0.0
            self.state.current_entry_time = None
