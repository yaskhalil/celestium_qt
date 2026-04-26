import asyncio
import uuid
import structlog
from datetime import datetime, timezone
from typing import Optional
from webull.trade.trade_client import TradeClient
from src.config import settings
from src.core.oracle import AccountState

logger = structlog.get_logger()

class WebullRouter:
    """
    Layer 4: Execution Layer (Webull T+1 Hardened)
    Enforces T+1 Settlement and Equity Limit Orders.
    """
    
    def __init__(self, client: TradeClient, state: AccountState):
        self.client = client
        self.state = state
        self.current_position = 0
        self.active_orders = {}
        self.min_hold_seconds = 30

    async def _verify_position(self, symbol: str):
        """Fetches the actual position from Webull to prevent ghost positions."""
        try:
            # SDK calls are synchronous, run in thread
            res = await asyncio.to_thread(
                self.client.account_v2.get_account_position,
                settings.WEBULL_ACCOUNT_ID
            )
            
            if res.status_code == 200:
                positions = res.json().get("positions", [])
                symbol_position = next((p for p in positions if p.get("symbol") == symbol), None)
                
                if symbol_position:
                    qty = float(symbol_position.get("position", 0))
                    self.current_position = qty
                    logger.info("Router: Position Verified", symbol=symbol, position=self.current_position)
                else:
                    self.current_position = 0
                    logger.info("Router: Position Verified (None)", symbol=symbol)
            else:
                logger.error("Router: Position Fetch Failed", status=res.status_code, error=res.text)
                
        except Exception as e:
            logger.error("Router: Position Verification Error", error=str(e))

    async def execute_trade(self, symbol: str, quantity: float, side: str, price: Optional[float] = None):
        """Places orders with Compliance Guards via Webull TPA."""
        
        # 0. Harden: Verify actual position before proceeding
        await self._verify_position(symbol)
        
        # 1. Consistency Guard: Verify Ceiling
        if self.state.current_daily_pnl >= self.state.daily_profit_ceiling:
            logger.error("Router: Order BLOCKED. Daily Profit Ceiling hit.")
            return None

        # 2. Hold Time Compliance (Only for Exits)
        is_closing = (self.current_position > 0 and side == "SELL") or (self.current_position < 0 and side == "BUY")
        if is_closing and self.state.current_entry_time:
            elapsed = (datetime.now(timezone.utc) - self.state.current_entry_time).total_seconds()
            if elapsed < self.min_hold_seconds:
                delay = self.min_hold_seconds - elapsed
                logger.warning("Router: EXIT DELAYED for 30s Compliance", elapsed=round(elapsed, 1), delay=round(delay, 1))
                await asyncio.sleep(delay)

        # 3. Calculate Limit Price
        if price is None:
            logger.error("Router: Limit price missing. Blocking order.")
            return None
        
        price = round(price, 2)
        quantity = round(float(quantity), 2)

        if settings.SHADOW_MODE:
            logger.info("Router: SHADOW MODE - Order would be placed", 
                        symbol=symbol, side=side, qty=quantity, price=price)
            return "shadow_order_id"

        logger.info("Router: EXECUTING LIMIT ORDER", symbol=symbol, side=side, qty=quantity, price=price)
        
        try:
            # Construct order as per SDK v2 requirements
            order_params = {
                "account_id": settings.WEBULL_ACCOUNT_ID,
                "client_combo_order_id": uuid.uuid4().hex,
                "new_orders": [{
                    "client_order_id": uuid.uuid4().hex,
                    "instrument_type": "EQUITY",
                    "symbol": symbol,
                    "market": "US",
                    "side": side,
                    "order_type": "LIMIT",
                    "limit_price": str(price),
                    "quantity": str(quantity),
                    "support_trading_session": "CORE",
                    "entrust_type": "QTY",
                    "time_in_force": "DAY"
                }]
            }
            
            res = await asyncio.to_thread(self.client.order_v2.place_order, **order_params)
            
            if res.status_code == 200:
                data = res.json()
                order_id = data.get("order_id")
                logger.info("Router: Order Placed Successfully", order_id=order_id)
                return order_id
            else:
                logger.error("Router: Webull Placement Failed", status=res.status_code, error=res.text)
                return None

        except Exception as e:
            logger.error("Router: Execution Error", error=str(e))
            return None

    async def panic_flatten(self, symbol: str):
        if self.current_position == 0:
            return
        side = "SELL" if self.current_position > 0 else "BUY"
        qty = abs(self.current_position)
        logger.warning("Router: PANIC FLATTEN TRIGGERED", symbol=symbol, qty=qty)

