import asyncio
import structlog
from typing import Optional
from async_rithmic import RithmicClient
from src.config import settings
from src.core.oracle import AccountState, AccountStatus

logger = structlog.get_logger()

class Router:
    """
    Layer 4: Execution & Reconciliation.
    Handles order routing via Rithmic and maintains the live position state.
    """
    
    def __init__(self, client: RithmicClient, state: AccountState):
        self.client = client
        self.state = state
        self.current_position = 0
        self.active_orders = {} # order_id -> status

    async def connect(self):
        """Ensures the Order Plant is ready."""
        if not self.client.is_connected:
            await self.client.connect()
        logger.info("Router: Order Plant Connected")

    async def _on_order_update(self, update):
        """Callback for Rithmic order status updates (Fills, Cancels)."""
        logger.info("Order Update Received", 
                    id=update.order_id, 
                    status=update.status, 
                    fill_qty=update.fill_quantity)
        
        # Reconciliation Logic
        if update.status == "FILLED":
            if update.side == "BUY":
                self.current_position += update.fill_quantity
            else:
                self.current_position -= update.fill_quantity
                
        self.active_orders[update.order_id] = update.status
        logger.info("Position Synced", net_pos=self.current_position)

    async def execute_trade(self, symbol: str, quantity: int, side: str, price: Optional[float] = None):
        """
        Places a Market or Limit order via Rithmic.
        """
        logger.info("Router: EXECUTING ORDER", symbol=symbol, side=side, qty=quantity)
        
        try:
            # Note: async-rithmic uses different methods for Market/Limit
            if price:
                order = await self.client.order.place_limit_order(
                    symbol=symbol,
                    exchange=settings.EXCHANGE,
                    quantity=quantity,
                    price=price,
                    side=side,
                    callback=self._on_order_update
                )
            else:
                order = await self.client.order.place_market_order(
                    symbol=symbol,
                    exchange=settings.EXCHANGE,
                    quantity=quantity,
                    side=side,
                    callback=self._on_order_update
                )
                
            self.active_orders[order.order_id] = "SUBMITTED"
            return order.order_id
            
        except Exception as e:
            logger.error("Router: Execution Failed", error=str(e))
            return None

    async def panic_flatten(self, symbol: str):
        """Hard exit for all positions. Used for EOD or Risk Vetoes."""
        if self.current_position == 0:
            return
            
        side = "SELL" if self.current_position > 0 else "BUY"
        qty = abs(self.current_position)
        
        logger.warning("PANIC FLATTEN TRIGGERED", symbol=symbol, qty=qty)
        await self.execute_trade(symbol, qty, side)
