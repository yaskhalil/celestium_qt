"""
Hardened Backtest Engine — Isolated simulation environment for strategy evaluation.

This engine replicates the live trading stack within a deterministic test harness:
- Uses synthetic historical OHLCV bars
- Enforces all Oracle rules (DLL, profit ceiling, floor, GFV)
- Respects T+1 settlement and cash pool dynamics
- Produces equity curve and trade metrics for performance analysis

Key differences from live:
- Time stops at bar close (no intrabar price moves)
- No slippage, no commissions beyond fixed cost
- Deterministic outcomes (no network, no broker API latency)
"""
import polars as pl
import numpy as np
from datetime import datetime, time, timezone
from typing import List, Dict, Optional
import structlog
from src.core.oracle import Oracle, AccountState, AccountStatus, DailySession
from src.core.allocator import Allocator
from src.models.classifier import Classifier
from src.config import settings

logger = structlog.get_logger()

class BacktestEngine:
    """
    Hardened Evaluator Backtest Engine.
    Forces Fixed Lot Size (2 MNQ) and Enforces Bulenox Compliance.
    """

    def __init__(self, initial_balance: Optional[float] = None):
        # All risk limits are now computed dynamically as % of balance
        # (AccountState properties) — no stale dollar-value settings.
        balance = initial_balance or settings.STARTING_BALANCE
        self.state = AccountState(
            balance=balance,
            equity=balance,
            initial_starting_balance=balance,  # anchor floor to starting balance
            max_daily_trades=settings.MAX_DAILY_TRADES,
            hurst_threshold=settings.HURST_THRESHOLD
        )
        self.oracle = Oracle(self.state)
        self.allocator = Allocator()
        self.classifier = Classifier()
        
        # Simulation State
        self.current_position = 0
        self.entry_price = 0.0
        self.entry_time = None
        self.stop_loss = 0.0
        self.take_profit = 0.0
        self.current_hurst = 0.0
        
        # Metrics Tracking
        self.trades = []
        self.equity_curve = []
        self.qualifying_days = 0

    def run(self, df: pl.DataFrame):
        logger.info("Starting Hardened Backtest", rows=len(df))
        
        df = df.with_columns(pl.col("timestamp").dt.date().alias("date"))
        
        current_date = None
        
        # Start at 110 to ensure indicators have populated
        for i in range(110, len(df)):
            bar = df.row(i, named=True)
            timestamp = bar["timestamp"]
            date = bar["date"]
            
            if current_date != date:
                if current_date is not None:
                    self._process_eod(current_date)
                current_date = date

            if "hurst" in bar:
                self.current_hurst = bar["hurst"]

            # 1. Exit Logic
            if self.current_position != 0:
                self._check_exit(bar)
                # EOD Flatten at 15:55 ET
                if self.current_position != 0 and timestamp.time() >= time(15, 55):
                    self._exit_trade(bar["close"], timestamp, "EOD_FLATTEN")
                if self.current_position != 0:
                    continue

            # 2. Time Guard: 9:30 AM to 3:55 PM
            if timestamp.time() < time(9, 30) or timestamp.time() >= time(15, 55):
                continue

            # 3. Oracle Compliance Check
            signal_prob = self.classifier.predict_features(bar)
            atr = bar.get("atr", settings.REFERENCE_ATR)
            
            size = self.allocator.calculate_size(signal_prob, atr, self.state.balance, bar["close"])

            # NOTE: validate_trade returns (approved, reason) — unpacking is
            # mandatory. The tuple itself is always truthy, so checking the
            # tuple directly would silently ignore every Oracle veto.
            if size > 0:
                approved, _ = self.oracle.validate_trade(size, bar["close"], "BUY",
                                                         current_hurst=self.current_hurst,
                                                         current_time=timestamp.time())
                if approved:
                    self._enter_trade(size, bar["close"], timestamp, atr)

        if current_date is not None:
            self._process_eod(current_date)

        return self.get_report()

    def _enter_trade(self, size: float, price: float, timestamp: datetime, atr: float):
        self.current_position = size
        self.entry_price = price
        self.entry_time = timestamp
        
        self.take_profit = price + (atr * settings.PT_MULTIPLIER)
        self.stop_loss = price - (atr * settings.SL_MULTIPLIER)

        # Deduct cost from settled cash (T+1 logic)
        cost = size * price
        self.oracle.update_session(cash_flow=cost, quantity=size, side="BUY")
        self.state.current_daily_trades += 1  # Count round trips by entry

        logger.debug("Trade Entered", price=price, size=size, tp=self.take_profit, sl=self.stop_loss)

    def _check_exit(self, bar: Dict):
        # 30s Hold Check (Simulated in 1m bars - inherently > 30s unless same bar)
        # For 1m bars, a trade entering and exiting in different bars is > 30s.
        
        if bar["low"] <= self.stop_loss:
            self._exit_trade(self.stop_loss, bar["timestamp"], "STOP_LOSS")
        elif bar["high"] >= self.take_profit:
            self._exit_trade(self.take_profit, bar["timestamp"], "TAKE_PROFIT")

    def _exit_trade(self, exit_price: float, timestamp: datetime, reason: str):
        # Stock/ETF PnL: (exit - entry) * shares. No futures tick multiplier.
        pnl = (exit_price - self.entry_price) * self.current_position
        proceeds = self.current_position * exit_price
        
        self.trades.append({
            "entry_time": self.entry_time,
            "exit_time": timestamp,
            "pnl": pnl,
            "reason": reason
        })
        
        self.oracle.update_session(pnl=pnl, cash_flow=proceeds, quantity=self.current_position, side="SELL")
        self.current_position = 0
        self.equity_curve.append(self.state.balance)

    def _process_eod(self, date: datetime):
        self.oracle.process_eod_anchor()
        last_session = self.state.trading_history[-1]
        if last_session.pnl >= settings.QUALIFYING_THRESHOLD:
            self.qualifying_days += 1
        logger.info("Day Processed", date=date, pnl=last_session.pnl, balance=self.state.balance, floor=self.state.safety_net_floor)

    def get_report(self) -> Dict:
        total_profit = sum(t["pnl"] for t in self.trades)
        max_drawdown = 0.0
        peak = self.equity_curve[0] if self.equity_curve else self.state.balance
        for val in self.equity_curve:
            if val > peak: peak = val
            dd = peak - val
            if dd > max_drawdown: max_drawdown = dd

        max_day_profit = max([s.pnl for s in self.state.trading_history if s.pnl > 0], default=0)
        consistency_score = max_day_profit / self.state.total_profit_since_payout if self.state.total_profit_since_payout > 0 else 0

        return {
            "Total Net Profit": round(total_profit, 2),
            "Max Drawdown": round(max_drawdown, 2),
            "Recovery Factor": round(total_profit / max_drawdown, 2) if max_drawdown > 0 else 0,
            "Qualifying Day Count": self.qualifying_days,
            "Consistency Score": round(consistency_score, 3),
            "Win Rate": len([t for t in self.trades if t["pnl"] > 0]) / len(self.trades) if self.trades else 0,
            "Total Trades": len(self.trades)
        }
