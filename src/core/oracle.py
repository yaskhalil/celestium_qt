from enum import Enum
from datetime import datetime, time
from typing import List, Optional, Annotated
from pydantic import BaseModel, Field, field_validator, ConfigDict
import structlog
from src.config import settings

logger = structlog.get_logger()

class AccountStatus(str, Enum):
    ACTIVE = "active"
    PAUSED_DAILY_LOSS = "paused_daily_loss"
    FLATTENING_REQUIRED = "flattening_required"
    LIQUIDATED = "liquidated"

class DailySession(BaseModel):
    date: datetime
    pnl: float
    is_closed: bool = False

class AccountState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    balance: float
    equity: float
    max_drawdown_limit: float = 25000.0  # $25k Account floor (Static for EOD usually)
    safety_net_floor: float = 26100.0   # Apex 4.0 $26.1k threshold
    daily_loss_limit: float = 500.0
    
    current_daily_pnl: float = 0.0
    total_profit_since_payout: float = 0.0
    trading_history: List[DailySession] = []
    
    status: AccountStatus = AccountStatus.ACTIVE
    last_updated: datetime = Field(default_factory=datetime.now)

    @property
    def is_trading_allowed(self) -> bool:
        # Check current time for Apex 4:59 PM ET Flat Rule
        now_et = datetime.now().time() # Simplified: assume system time is ET or handled via pytz
        if now_et >= time(16, 55) and now_et <= time(18, 0):
            return False
        return self.status == AccountStatus.ACTIVE

class Oracle:
    """The Risk Firewall (Apex 4.0 Rules - 2026 Edition)"""
    
    def __init__(self, state: AccountState):
        self.state = state

    def validate_trade(self, quantity: int, price: float, side: str) -> bool:
        """
        Pydantic-driven state machine validation.
        Enforces Apex 4.0 Safety Net, 50% Consistency, and 2026 DLL Pausing.
        """
        logger.info("Oracle: Validating Trade Request", quantity=quantity, side=side, status=self.state.status)

        # 1. Status Check (DLL Pausing Logic)
        if not self.state.is_trading_allowed:
            logger.error("VETO: Trading not allowed", status=self.state.status)
            return False

        # 2. Daily Loss Limit Check (2026 Pausing Logic)
        # If this trade could potentially breach DLL, or we are already near it.
        if self.state.current_daily_pnl <= -self.state.daily_loss_limit:
            self.state.status = AccountStatus.PAUSED_DAILY_LOSS
            logger.error("VETO: Daily Loss Limit Breached. Pausing for session.", limit=self.state.daily_loss_limit)
            return False

        # 3. Apex 4.0 Safety Net ($26,100 Floor)
        if self.state.balance <= self.state.safety_net_floor:
            # In Apex 4.0, falling below the floor often means failure, 
            # but we treat it as a hard-stop before the broker liquidates.
            logger.error("VETO: Safety Net Floor reached!", floor=self.state.safety_net_floor, balance=self.state.balance)
            return False

        # 4. 50% Consistency Rule (Profit Dilution Check)
        # Rule: No single day > 50% of total profit.
        # If we have a massive win today, we can continue, but future payouts are blocked.
        # However, for *execution* logic, we block NEW entries if today's profit 
        # already makes up > 50% of the *projected* total to prevent 'gambling' the payout.
        
        projected_total_profit = self.state.total_profit_since_payout + max(0, self.state.current_daily_pnl)
        if projected_total_profit > 0:
            consistency_ratio = self.state.current_daily_pnl / projected_total_profit
            if consistency_ratio > 0.50 and len(self.state.trading_history) < 5:
                logger.warning("CONSISTENCY ALERT: Today's profit > 50% of total.", ratio=consistency_ratio)
                # We don't necessarily VETO here unless requested, as you can 'dilute' later.
                # But we log it as a critical warning for Layer 4 Advisor.

        # 5. Quantity / Max Position Size
        if quantity > settings.MAX_POSITION_SIZE:
             logger.error("VETO: Max position size exceeded", max=settings.MAX_POSITION_SIZE, requested=quantity)
             return False

        logger.info("Oracle: Trade VALIDATED", side=side, quantity=quantity)
        return True

    def update_session(self, pnl: float):
        """Updates the internal state after a trade or session close."""
        self.state.current_daily_pnl += pnl
        self.state.balance += pnl
        self.state.equity = self.state.balance # Simplified for EOD
        
        if self.state.current_daily_pnl <= -self.state.daily_loss_limit:
            self.state.status = AccountStatus.PAUSED_DAILY_LOSS
            
        self.state.last_updated = datetime.now()
