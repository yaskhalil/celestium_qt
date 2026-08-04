from enum import Enum
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
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
    PAUSED = "paused"

class DailySession(BaseModel):
    date: datetime
    pnl: float
    trade_count: int = 0
    is_closed: bool = False

class AccountState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    # Core balance — synced from broker at startup and periodically
    initial_starting_balance: float = 0.0
    balance: float = 0.0
    equity: float = 0.0
    position_market_value: float = 0.0  # Market value of open positions
    
    # Cash pools (T+1 settlement)
    settled_cash: float = 0.0
    unsettled_cash: float = 0.0
    
    # Dynamic limits (computed from balance as percentages)
    # Stored here for audit/logging; computed fresh each validation
    _daily_loss_limit: float = 0.0
    _daily_profit_ceiling: float = 0.0
    _safety_net_floor: float = 0.0
    _reserve_threshold: float = 0.0
    _soft_kill_switch: float = 0.0
    
    # State
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
        if self.settled_cash == 0.0 and self.unsettled_cash == 0.0 and self.balance > 0:
            self.settled_cash = self.balance
        return self

    # ── Dynamic Risk Limit Computations ────────────────────────────────
    # All limits are % of actual balance, not hardcoded dollar values.
    # This ensures the system works correctly for any account size ($358 or $50K).

    @property
    def daily_loss_limit(self) -> float:
        """5% of balance by default."""
        return self.balance * settings.DLL_PCT

    @property
    def daily_profit_ceiling(self) -> float:
        """6% of balance by default."""
        return self.balance * settings.PROFIT_CEILING_PCT

    @property
    def safety_net_floor(self) -> float:
        """90% of starting balance = 10% max total drawdown."""
        base = self.initial_starting_balance if self.initial_starting_balance > 0 else self.balance
        return base * settings.FLOOR_PCT

    @property
    def reserve_threshold(self) -> float:
        """5% of balance held back."""
        return self.balance * settings.RESERVE_PCT

    @property
    def soft_kill_switch(self) -> float:
        """85% of daily loss limit triggers early flatten."""
        return self.daily_loss_limit * settings.SOFT_KILL_PCT

    @property
    def max_position_value(self) -> float:
        """Max 30% of balance in a single position."""
        return self.balance * settings.MAX_POSITION_PCT

    @property
    def liquid_payout_capital(self) -> float:
        base = self.initial_starting_balance if self.initial_starting_balance > 0 else self.balance
        return max(0.0, self.equity - (base + self.reserve_threshold))

    def is_trading_allowed(self, current_time: Optional[time] = None) -> bool:
        now_et = current_time or datetime.now(ZoneInfo("America/New_York")).time()
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
        return cls()

    def to_dict(self) -> dict:
        """Return computed limits for logging/telegram reports."""
        return {
            "balance": round(self.balance, 2),
            "equity": round(self.equity, 2),
            "settled_cash": round(self.settled_cash, 2),
            "daily_loss_limit": round(self.daily_loss_limit, 2),
            "daily_profit_ceiling": round(self.daily_profit_ceiling, 2),
            "safety_net_floor": round(self.safety_net_floor, 2),
            "daily_pnl": round(self.current_daily_pnl, 2),
            "trades_today": self.current_daily_trades,
            "status": self.status.value,
        }


class Oracle:
    """The Risk Firewall — trade validation with dynamic, balance-based limits."""

    def __init__(self, state: AccountState, notifier: Optional[TelegramNotifier] = None):
        self.state = state
        self.notifier = notifier or TelegramNotifier()

    def validate_trade(self, quantity: float, price: float, side: str,
                       current_hurst: float = 0.0,
                       current_vix: float = 0.0,
                       current_time: Optional[time] = None) -> Tuple[bool, str]:
        """
        Enforces risk rules. Returns (approved: bool, reason: str).
        All limits are dynamic % of current balance.
        """
        now_et = current_time or datetime.now(ZoneInfo("America/New_York")).time()

        # 0. Hard cutoff — no trading after 4:55 PM ET
        if now_et >= time(16, 55):
            return False, "Past market close (4:55 PM ET cutoff)"

        if not self.state.is_trading_allowed(current_time):
            return False, f"Account status: {self.state.status.value}"

        # 1. Daily trade cap
        if self.state.current_daily_trades >= self.state.max_daily_trades:
            return False, f"Daily trade cap reached ({self.state.current_daily_trades})"

        # 2. Hurst gate (regime filter)
        if current_hurst < self.state.hurst_threshold:
            return False, f"Hurst below threshold ({current_hurst:.3f} < {self.state.hurst_threshold})"

        # 3. Circuit breaker (volatility protection)
        if current_vix > 30.0:
            self._safe_notify("⚡️ CIRCUIT BREAKER — High Volatility (VIXY > 30)")
            return False, f"Circuit breaker: VIXY={current_vix:.1f} > 30"

        # 4. Daily loss limit (dynamic % of balance)
        if self.state.current_daily_pnl <= -self.state.daily_loss_limit:
            self.state.status = AccountStatus.PAUSED_DAILY_LOSS
            self.state.save()
            self._safe_notify("❌ DAILY LOSS LIMIT BREACHED — Trading Paused")
            return False, f"DLL breached: {self.state.current_daily_pnl:.2f} <= -{self.state.daily_loss_limit:.2f}"

        # 5. Daily profit ceiling
        if self.state.current_daily_pnl >= self.state.daily_profit_ceiling:
            self._safe_notify("✅ Daily Profit Ceiling Reached — Session Locked")
            return False, f"Profit ceiling: {self.state.current_daily_pnl:.2f} >= {self.state.daily_profit_ceiling:.2f}"

        # 6. Account floor (max total drawdown)
        if self.state.balance <= self.state.safety_net_floor:
            self._safe_notify("🚨 ACCOUNT FLOOR BREACHED")
            return False, f"Balance {self.state.balance:.2f} <= floor {self.state.safety_net_floor:.2f}"

        # 7. Position size limit (dynamic % of balance)
        cost = quantity * price
        if cost > self.state.max_position_value:
            return False, f"Position ${cost:.2f} exceeds max ${self.state.max_position_value:.2f} ({(settings.MAX_POSITION_PCT*100):.0f}% of balance)"

        # 8. GFV Protection (T+1 settlement)
        if side.upper() == "BUY" and cost > self.state.settled_cash:
            return False, f"GFV risk: ${cost:.2f} cost exceeds ${self.state.settled_cash:.2f} settled cash"

        return True, "Approved"

    def validate_sell(self, quantity: float, price: float) -> Tuple[bool, str]:
        """
        Validates SELL exits — still checks account status and balance floor.
        Prevents exits when account is already liquidated.
        """
        if self.state.status in (AccountStatus.LIQUIDATED, AccountStatus.PAUSED):
            return False, f"Account {self.state.status.value} — sell blocked"

        if self.state.balance <= self.state.safety_net_floor and self.state.current_daily_pnl <= -self.state.daily_loss_limit:
            return False, "Account at floor with DLL breached — manual intervention required"

        return True, "Approved"

    def _safe_notify(self, message: str):
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.notifier.notify_risk_veto(message))
        except RuntimeError:
            pass

    def process_eod_anchor(self):
        """Finalizes daily session with T+1 settlement."""
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

        self.state.current_daily_pnl = 0.0
        self.state.current_daily_trades = 0

        if self.state.status == AccountStatus.PAUSED_DAILY_LOSS:
            self.state.status = AccountStatus.ACTIVE

        self.state.save()

    def update_session(self, pnl: float = 0.0, cash_flow: float = 0.0,
                       quantity: float = 0.0, side: str = "BUY",
                       position_value: float = 0.0):
        """Updates intraday state after a trade."""
        commissions = quantity * settings.COMMISSION_PER_LOT

        self.state.current_daily_pnl += pnl

        if side.upper() == "BUY":
            self.state.settled_cash -= (cash_flow + commissions)
            self.state.position_market_value += position_value
        elif side.upper() == "SELL":
            self.state.unsettled_cash += (cash_flow - commissions)
            self.state.position_market_value = max(0, self.state.position_market_value - position_value)

        # Balance = cash only (T+1 pools)
        self.state.balance = self.state.settled_cash + self.state.unsettled_cash
        # Equity = cash + market value of open positions
        self.state.equity = self.state.balance + self.state.position_market_value
        # NOTE: trade counting is the caller's job (entry sides only), so a
        # round trip counts once against MAX_DAILY_TRADES. Callers:
        # position_manager._update_local_state and backtest_engine._enter_trade.

        if self.state.current_daily_pnl <= -self.state.daily_loss_limit:
            self.state.status = AccountStatus.PAUSED_DAILY_LOSS

        self.state.save()
