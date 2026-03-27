from pydantic import BaseModel, field_validator
from typing import Dict, Any
import structlog
from src.config import settings

logger = structlog.get_logger()

class TradeRequest(BaseModel):
    symbol: str
    action: str
    quantity: int
    current_balance: float
    daily_pnl: float
    unrealized_pnl: float

class Oracle:
    """The Risk Firewall (Apex 2026 Rules)"""
    
    def __init__(self):
        self.rules = {
            "balance_floor": settings.BALANCE_FLOOR,
            "daily_loss_limit": settings.DAILY_LOSS_LIMIT,
            "max_quantity": settings.MAX_POSITION_SIZE,
        }

    def validate_trade(self, trade: TradeRequest) -> bool:
        """Determines if a trade is safe to execute."""
        
        # Rule 1: Balance Floor
        if trade.current_balance <= self.rules["balance_floor"]:
            logger.error("VETO: Balance below floor!", floor=self.rules["balance_floor"], balance=trade.current_balance)
            return False

        # Rule 2: Daily Loss Limit
        if trade.daily_pnl <= -self.rules["daily_loss_limit"]:
            logger.error("VETO: Daily loss limit hit!", limit=self.rules["daily_loss_limit"], pnl=trade.daily_pnl)
            return False

        # Rule 3: Quantity Limit
        if trade.quantity > self.rules["max_quantity"]:
            logger.error("VETO: Exceeds max position size!", max=self.rules["max_quantity"], quantity=trade.quantity)
            return False

        logger.info("Oracle: Trade Approved", symbol=trade.symbol, action=trade.action)
        return True
