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
        balance = initial_balance or settings.STARTING_BALANCE
        self.state = AccountState(
            balance=balance,
            equity=balance,
            safety_net_floor=settings.BALANCE_FLOOR,
            daily_loss_limit=settings.DAILY_LOSS_LIMIT,
            soft_kill_switch=settings.SOFT_KILL_SWITCH,
            daily_profit_ceiling=settings.DAILY_PROFIT_CEILING,
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
        days = df["date"].unique().sort()

        for date in days:
            day_data = df.filter(pl.col("date") == date)
            self._simulate_day(day_data)
            self._process_eod(date)

        return self.get_report()

    def _simulate_day(self, day_data: pl.DataFrame):
        """Simulates one session with UTC compliance."""
        for i in range(110, len(day_data)):
            bar = day_data.row(i, named=True)
            timestamp = bar["timestamp"]
            
            # Update current hurst for Oracle check
            if "hurst" in day_data.columns:
                self.current_hurst = bar["hurst"]

            # 1. Exit Logic (Bracket + 30s Hold Simulation)
            if self.current_position != 0:
                self._check_exit(bar)
                if self.current_position != 0: continue

            # 2. Daily Time Guard (ET Mapping)
            # Standard Market Hours: 9:30 AM to 4:00 PM ET
            if timestamp.time() < time(9, 30) or timestamp.time() >= time(16, 0):
                if self.current_position != 0 and timestamp.time() >= time(16, 55):
                    self._exit_trade(bar["close"], timestamp, "EOD_FLATTEN")
                continue

            # 3. Oracle Compliance Check (Includes Hurst + Trade Cap)
            # Signal Generation
            context = day_data.slice(i - 110, 111)
            signal_prob = self.classifier.predict(context)
            atr = bar["atr"] if "atr" in bar else settings.REFERENCE_ATR
            
            size = self.allocator.calculate_size(signal_prob, atr, self.state.balance)

            if size > 0 and self.oracle.validate_trade(size, bar["close"], "BUY", 
                                             current_hurst=self.current_hurst,
                                             current_time=timestamp.time()):
                self._enter_trade(size, bar["close"], timestamp, atr)

    def _enter_trade(self, size: float, price: float, timestamp: datetime, atr: float):
        self.current_position = size
        self.entry_price = price
        self.entry_time = timestamp
        
        self.take_profit = price + (atr * settings.PT_MULTIPLIER)
        self.stop_loss = price - (atr * settings.SL_MULTIPLIER)

        # Deduct cost from settled cash (T+1 logic)
        cost = size * price
        self.oracle.update_session(cash_flow=cost, quantity=size, side="BUY")

        logger.debug("Trade Entered", price=price, size=size, tp=self.take_profit, sl=self.stop_loss)

    def _check_exit(self, bar: Dict):
        # 30s Hold Check (Simulated in 1m bars - inherently > 30s unless same bar)
        # For 1m bars, a trade entering and exiting in different bars is > 30s.
        
        if bar["low"] <= self.stop_loss:
            self._exit_trade(self.stop_loss, bar["timestamp"], "STOP_LOSS")
        elif bar["high"] >= self.take_profit:
            self._exit_trade(self.take_profit, bar["timestamp"], "TAKE_PROFIT")

    def _exit_trade(self, exit_price: float, timestamp: datetime, reason: str):
        pnl = (exit_price - self.entry_price) * self.current_position * settings.TICK_VALUE
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
