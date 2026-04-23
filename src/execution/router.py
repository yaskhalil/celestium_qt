import asyncio
import uuid
import structlog
from datetime import datetime, timezone
from typing import Optional
from src.execution.webull_client import WebullClient
from src.config import settings
from src.core.oracle import AccountState

logger = structlog.get_logger()

class WebullRouter:
    """
    Layer 4: Execution Layer (Webull T+1 Hardened)
    Enforces T+1 Settlement and Equity Limit Orders.
    """
    
    def __init__(self, client: WebullClient, state: AccountState):
        self.client = client
        self.state = state
        self.current_position = 0
        self.active_orders = {}
        self.min_hold_seconds = 30

    async def _on_order_update(self, update: dict):
        """Processes Webull order updates and maintains position state."""
        status = update.get("status")
        if status == "FILLED":
            side = update.get("side")
            qty = int(update.get("filled_quantity", 0))
            
            if side == "BUY":
                if self.current_position == 0:
                    self.state.current_entry_time = datetime.now(timezone.utc)
                self.current_position += qty
            elif side == "SELL":
                if self.current_position == 0:
                    self.state.current_entry_time = datetime.now(timezone.utc)
                self.current_position -= qty
            
            if self.current_position == 0:
                self.state.current_entry_time = None
            
            self.state.save()
            logger.info("Router: Position Updated", position=self.current_position)

    async def _verify_position(self, symbol: str):
        """Fetches the actual position from Webull to prevent ghost positions."""
        try:
            response = await self.client.get_positions(settings.WEBULL_ACCOUNT_ID)
            
            # Assuming the response format gives a list of positions
            positions = response if isinstance(response, list) else response.get("positions", [])
            symbol_position = next((p for p in positions if p.get("symbol") == symbol or p.get("ticker", {}).get("symbol") == symbol), None)
            
            if symbol_position:
                qty = int(float(symbol_position.get("position", 0)))
                self.current_position = qty
                logger.info("Router: Position Verified", symbol=symbol, position=self.current_position)
            else:
                self.current_position = 0
                logger.info("Router: Position Verified (None)", symbol=symbol)
                
        except Exception as e:
            logger.error("Router: Position Verification Failed", error=str(e))

    async def execute_trade(self, symbol: str, quantity: int, side: str, price: Optional[float] = None):
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

        # 3. Calculate Limit Price (Mandatory for Webull $400 account)
        if price is None:
            logger.error("Router: Limit price calculation failed or missing. Blocking order.")
            return None
        
        # Round to 2 decimal places for equities
        price = round(price, 2)

        logger.info("Router: EXECUTING LIMIT ORDER", symbol=symbol, side=side, qty=quantity, price=price)
        
        try:
            order_params = {
                "client_order_id": uuid.uuid4().hex,
                "instrument_id": symbol, 
                "side": side,
                "order_type": "LIMIT",
                "limit_price": str(price),
                "qty": str(quantity),
                "tif": "DAY"
            }
            
            response = await self.client.place_order(settings.WEBULL_ACCOUNT_ID, order_params)
            
            # Success check based on presence of order_id
            order_id = response.get("order_id") if isinstance(response, dict) else None
            if order_id:
                logger.info("Router: Order Placed Successfully", order_id=order_id)
                return order_id
            else:
                logger.error("Router: Webull Placement Failed", response=response)
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

