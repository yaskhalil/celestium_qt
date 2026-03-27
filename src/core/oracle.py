from enum import Enum
from datetime import datetime, time
from typing import List, Optional, Annotated
from pydantic import BaseModel, Field, field_validator, ConfigDict
import structlog
import json
import os
from src.config import settings

logger = structlog.get_logger()

STATE_FILE = "data/account_state.json"

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
    max_drawdown_limit: float = 25000.0
    safety_net_floor: float = 26100.0
    daily_loss_limit: float = 500.0
    
    current_daily_pnl: float = 0.0
    total_profit_since_payout: float = 0.0
    trading_history: List[DailySession] = []
    
    status: AccountStatus = AccountStatus.ACTIVE
    last_updated: datetime = Field(default_factory=datetime.now)

    @property
    def is_trading_allowed(self) -> bool:
        now_et = datetime.now().time()
        if now_et >= time(16, 55) and now_et <= time(18, 0):
            return False
        return self.status == AccountStatus.ACTIVE

    def save(self):
        """Persists state to local JSON file."""
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w") as f:
            f.write(self.model_dump_json())
        logger.debug("AccountState: Persisted to disk")

    @classmethod
    def load(cls) -> "AccountState":
        """Loads state from local JSON file or returns default."""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    return cls.model_validate_json(f.read())
            except Exception as e:
                logger.error("Failed to load state, starting fresh", error=str(e))
        
        # Default state if no file exists
        return cls(
            balance=27000.0, 
            equity=27000.0,
            safety_net_floor=settings.BALANCE_FLOOR,
            daily_loss_limit=settings.DAILY_LOSS_LIMIT
        )

class Oracle:
    """The Risk Firewall (Apex 4.0 Rules - 2026 Edition)"""
    
    def __init__(self, state: AccountState):
        self.state = state

    def validate_trade(self, quantity: int, price: float, side: str) -> bool:
        """Enforces Apex 4.0 Safety Net, 50% Consistency, and 2026 DLL Pausing."""
        logger.info("Oracle: Validating Trade Request", quantity=quantity, side=side, status=self.state.status)

        if not self.state.is_trading_allowed:
            logger.error("VETO: Trading not allowed", status=self.state.status)
            return False

        if self.state.current_daily_pnl <= -self.state.daily_loss_limit:
            self.state.status = AccountStatus.PAUSED_DAILY_LOSS
            self.state.save()
            logger.error("VETO: Daily Loss Limit Breached.", limit=self.state.daily_loss_limit)
            return False

        if self.state.balance <= self.state.safety_net_floor:
            logger.error("VETO: Safety Net Floor reached!", balance=self.state.balance)
            return False

        projected_total_profit = self.state.total_profit_since_payout + max(0, self.state.current_daily_pnl)
        if projected_total_profit > 0:
            consistency_ratio = self.state.current_daily_pnl / projected_total_profit
            if consistency_ratio > 0.50 and len(self.state.trading_history) < 5:
                logger.warning("CONSISTENCY ALERT: Today's profit > 50% of total.", ratio=consistency_ratio)

        if quantity > settings.MAX_POSITION_SIZE:
             logger.error("VETO: Max position size exceeded", max=settings.MAX_POSITION_SIZE, requested=quantity)
             return False

        logger.info("Oracle: Trade VALIDATED")
        return True

    def update_session(self, pnl: float):
        """Updates the internal state and persists to disk."""
        self.state.current_daily_pnl += pnl
        self.state.balance += pnl
        self.state.equity = self.state.balance
        
        if self.state.current_daily_pnl <= -self.state.daily_loss_limit:
            self.state.status = AccountStatus.PAUSED_DAILY_LOSS
            
        self.state.last_updated = datetime.now()
        self.state.save() # Auto-persist
