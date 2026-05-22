from enum import Enum
from datetime import datetime, time, timezone
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field, ConfigDict, model_validator
import structlog
import os
import asyncio
from src.config import settings
from src.core.notifier import TelegramNotifier

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
    trade_count: int = 0
    is_closed: bool = False

class AccountState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    balance: float = Field(default_factory=lambda: settings.STARTING_BALANCE)
    equity: float = Field(default_factory=lambda: settings.STARTING_BALANCE)
    settled_cash: float = 0.0
    unsettled_cash: float = 0.0
    safety_net_floor: float = Field(default_factory=lambda: settings.BALANCE_FLOOR)
    daily_loss_limit: float = Field(default_factory=lambda: settings.DAILY_LOSS_LIMIT)
    soft_kill_switch: float = Field(default_factory=lambda: settings.SOFT_KILL_SWITCH)
    reserve_threshold: float = Field(default_factory=lambda: settings.SAFETY_THRESHOLD_RESERVE)
    daily_profit_ceiling: float = Field(default_factory=lambda: settings.DAILY_PROFIT_CEILING)
    
    current_daily_pnl: float = 0.0
    current_daily_trades: int = 0
    max_daily_trades: int = Field(default_factory=lambda: settings.MAX_DAILY_TRADES)
    hurst_threshold: float = Field(default_factory=lambda: settings.HURST_THRESHOLD)
    current_entry_time: Optional[datetime] = None
    
    total_profit_since_payout: float = 0.0
    trading_history: List[DailySession] = []
    
    status: AccountStatus = AccountStatus.ACTIVE
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode='after')
    def sync_cash_on_init(self) -> 'AccountState':
        if self.settled_cash == 0.0 and self.unsettled_cash == 0.0:
            self.settled_cash = self.balance
        return self

    @property
    def liquid_payout_capital(self) -> float:
        return max(0.0, self.equity - (settings.STARTING_BALANCE + self.reserve_threshold))

    def is_trading_allowed(self, current_time: Optional[time] = None) -> bool:
        # Note: Bulenox times are ET, Rithmic uses UTC. 
        # For simplicity in this logic, we use time of day.
        now_et = current_time or datetime.now(timezone.utc).time()
        if now_et >= time(16, 55) and now_et <= time(18, 0):
            return False
        return self.status == AccountStatus.ACTIVE

    def save(self):
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w") as f:
            f.write(self.model_dump_json())

    @classmethod
    def load(cls) -> "AccountState":
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    return cls.model_validate_json(f.read())
            except Exception as e:
                logger.error("Failed to load state", error=str(e))
        return cls(
            daily_profit_ceiling=settings.DAILY_PROFIT_CEILING,
            hurst_threshold=getattr(settings, 'HURST_THRESHOLD', 0.42),
            max_daily_trades=getattr(settings, 'MAX_DAILY_TRADES', 50)
        )

class Oracle:
    """The Risk Firewall (Bulenox 50K EOD - 2026 Edition)"""
    
    def __init__(self, state: AccountState):
        self.state = state
        self.notifier = TelegramNotifier()

    def validate_trade(self, quantity: float, price: float, side: str, 
                       current_hurst: float = 0.0, 
                       current_time: Optional[time] = None) -> bool:
        """Enforces Hardened Evaluator Rules: DLL, Daily Cap, Trade Cap, Hurst."""
        
        if not self.state.is_trading_allowed(current_time):
            logger.error("VETO: Trading not allowed", status=self.state.status)
            return False

        # 1. Daily Signal Cap (Compliance)
        if self.state.current_daily_trades >= self.state.max_daily_trades:
            logger.error("VETO: Daily Trade Cap Reached", count=self.state.current_daily_trades)
            return False

        # 2. Hurst Gate (Regime Persistence)
        if current_hurst < self.state.hurst_threshold:
            logger.debug("VETO: Hurst below threshold", hurst=current_hurst, min=self.state.hurst_threshold)
            return False

        # 3. DLL and Profit Ceiling
        if self.state.current_daily_pnl <= -self.state.daily_loss_limit:
            self.state.status = AccountStatus.PAUSED_DAILY_LOSS
            self.state.save()
            logger.error("VETO: Hard DLL Breached")
            self._safe_notify("❌ HARD DLL BREACHED - Trading Paused")
            return False
            
        if self.state.current_daily_pnl >= self.state.daily_profit_ceiling:
            logger.error("VETO: Daily Profit Ceiling Reached")
            self._safe_notify("✅ Daily Profit Ceiling Reached - Session Closed")
            return False

        # 4. EOD Floor
        if self.state.balance <= self.state.safety_net_floor:
            logger.error("VETO: Floor Breached")
            self._safe_notify("🚨 ACCOUNT FLOOR BREACHED")
            return False

        # 5. GFV Protection (T+1 Settlement for $400 Equity Account)
        if side == "BUY":
            cost = quantity * price
            if cost > self.state.settled_cash:
                logger.error("VETO: GFV Risk - Insufficient Settled Cash", 
                             required=cost, available=self.state.settled_cash)
                return False

        return True

    def _safe_notify(self, message: str):
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.notifier.notify_risk_veto(message))
        except RuntimeError:
            pass # No event loop running (e.g. during synchronous backtest)

    def process_eod_anchor(self):
        """Finalizes daily session and handles T+1 cash settlement."""
        # For Equity Cash Accounts, we don't have a trailing drawdown floor like Bulenox.
        # The floor remains static or increases only if manually adjusted in settings.
        
        # T+1 Settlement: Unsettled cash from today becomes settled for tomorrow
        self.state.settled_cash += self.state.unsettled_cash
        self.state.unsettled_cash = 0.0
        
        session = DailySession(
            date=datetime.now(timezone.utc), 
            pnl=self.state.current_daily_pnl, 
            trade_count=self.state.current_daily_trades,
            is_closed=True
        )
        self.state.trading_history.append(session)
        self.state.total_profit_since_payout += max(0, self.state.current_daily_pnl)

        # Reset daily PnL and trade count
        self.state.current_daily_pnl = 0.0
        self.state.current_daily_trades = 0
        
        # Reset status if it was just paused for the day
        if self.state.status == AccountStatus.PAUSED_DAILY_LOSS:
            self.state.status = AccountStatus.ACTIVE
            
        self.state.save()

    def update_session(self, pnl: float = 0.0, cash_flow: float = 0.0, quantity: float = 0.0, side: str = "BUY"):
        """Updates intraday balance and manages T+1 cash pools."""
        commissions = quantity * settings.COMMISSION_PER_LOT

        # 1. Update Daily PnL (Closed trades only for SELL side usually)
        self.state.current_daily_pnl += pnl

        # 2. Update Cash Pools
        if side == "BUY":
            # cash_flow is the cost (positive value)
            self.state.settled_cash -= (cash_flow + commissions)
        elif side == "SELL":
            # cash_flow is the proceeds (positive value)
            self.state.unsettled_cash += (cash_flow - commissions)

        # 3. Sync Balance
        self.state.balance = self.state.settled_cash + self.state.unsettled_cash
        self.state.equity = self.state.balance
        self.state.current_daily_trades += 1

        # Check DLL directly upon update
        if self.state.current_daily_pnl <= -self.state.daily_loss_limit:
            self.state.status = AccountStatus.PAUSED_DAILY_LOSS

        self.state.save()
