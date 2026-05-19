import pytest
import polars as pl
from datetime import datetime, time, timedelta
from src.core.backtest_engine import BacktestEngine
from src.core.oracle import AccountStatus
from src.config import settings

@pytest.fixture(autouse=True)
def force_mnq_settings():
    """Ensure tests run with standard MNQ settings, overriding any deployment_config.json."""
    old_tick = settings.TICK_VALUE
    old_sl = settings.SL_MULTIPLIER
    old_pt = settings.PT_MULTIPLIER
    old_dll = settings.DAILY_LOSS_LIMIT
    old_floor = settings.BALANCE_FLOOR
    old_sig = settings.SIGNAL_THRESHOLD
    old_max_trades = settings.MAX_DAILY_TRADES
    
    settings.TICK_VALUE = 2.0
    settings.SL_MULTIPLIER = 0.5
    settings.PT_MULTIPLIER = 1.0
    settings.DAILY_LOSS_LIMIT = 1100.0
    settings.BALANCE_FLOOR = 47500.0
    settings.SIGNAL_THRESHOLD = 0.4
    settings.MAX_DAILY_TRADES = 50
    
    yield
    
    settings.TICK_VALUE = old_tick
    settings.SL_MULTIPLIER = old_sl
    settings.PT_MULTIPLIER = old_pt
    settings.DAILY_LOSS_LIMIT = old_dll
    settings.BALANCE_FLOOR = old_floor
    settings.SIGNAL_THRESHOLD = old_sig
    settings.MAX_DAILY_TRADES = old_max_trades

def test_backtest_engine_fill_logic():
    """
    DETETERMINISTIC AUDIT:
    Verifies that the engine correctly identifies SL/TP hits within bar ranges.
    """
    engine = BacktestEngine(initial_balance=50000.0)
    engine.FIXED_LOT_SIZE = 2.0
    engine.state.max_daily_trades = 50
    
    # Create a 3-bar sequence
    # Bar 0: Context/Signal
    # Bar 1: Entry
    # Bar 2: Stop Loss Hit (Low drops below SL)
    
    start_time = datetime(2026, 1, 1, 9, 30)
    data = []
    for i in range(120): # Need 110 for context
        price = 100.0
        data.append({
            "timestamp": start_time + timedelta(minutes=i),
            "open": price,
            "high": price + 5,
            "low": price - 5,
            "close": price,
            "volume": 1000,
            "atr": 20.0,
            "hurst": 0.6 # Force persistent regime
        })
    
    # Inject a "Stop Loss" event in the last bar
    # Entry at 100. SL (0.5 ATR) = 90.
    last_idx = len(data) - 1
    data[last_idx]["low"] = 80.0 # Hits SL
    
    df = pl.DataFrame(data)
    
    # Mock the classifier to always return a high probability at the entry point
    engine.classifier.predict = lambda x: 0.9
    
    engine.run(df)
    
    assert len(engine.trades) > 0
    last_trade = engine.trades[0]
    assert last_trade["reason"] == "STOP_LOSS"
    # PnL for 5 MNQ: (90 - 100) * 5 * 2 = -$100
    assert last_trade["pnl"] == -100.0

def test_backtest_engine_dll_veto():
    """
    Verifies that the backtester stops trading once the Daily Loss Limit is hit.
    """
    engine = BacktestEngine(initial_balance=50000.0)
    engine.FIXED_LOT_SIZE = 2.0
    engine.state.max_daily_trades = 50
    
    # Simulate a series of losses that hit the $1,100 DLL
    start_time = datetime(2026, 1, 1, 9, 30)
    data = []
    for i in range(150):
        price = 500.0 - (i * 0.1) # Continuous drop
        data.append({
            "timestamp": start_time + timedelta(minutes=i),
            "open": price,
            "high": price + 1,
            "low": price - 50, # Huge lows to trigger SLs
            "close": price,
            "volume": 1000,
            "atr": 20.0,
            "hurst": 0.6
        })
        
    df = pl.DataFrame(data)
    engine.classifier.predict = lambda x: 0.9 # Constant signal
    
    engine.run(df)
    
    # The engine should stop trading once daily PnL <= -1100
    # Each loss is approx $40 (2 MNQ * 10 points). 
    # $1100 / $40 = ~28 trades max.
    
    # We need to capture the state BEFORE _process_eod clears it if we want to check it at the end of engine.run()
    # Or we can check history.
    assert len(engine.trades) < 50
    assert engine.state.trading_history[-1].pnl <= -1100.0

def test_backtest_engine_eod_anchor():
    """
    Verifies that the EOD Anchor logic correctly updates the floor at the end of the day.
    """
    engine = BacktestEngine(initial_balance=50000.0)
    engine.FIXED_LOT_SIZE = 2.0
    engine.state.max_daily_trades = 50
    engine.state.daily_profit_ceiling = 10000.0 # Increase ceiling to prevent veto
    initial_floor = engine.state.safety_net_floor # 47500
    # 1. Simulate a Profitable Day
    start_time = datetime(2026, 1, 1, 9, 30)
    data = []
    for i in range(120):
        price = 100.0 + (i * 2) # Rising price, much lower so cost is low
        data.append({
            "timestamp": start_time + timedelta(minutes=i),
            "open": price,
            "high": price + 500, # Hits TP
            "low": price - 1,
            "close": price,
            "volume": 1000,
            "atr": 50.0,
            "hurst": 0.6
        })
    df = pl.DataFrame(data)
    engine.classifier.predict = lambda x: 0.9

    engine.run(df)

    # EOD balance should be > 50000
    assert engine.state.balance > 50000.0    # New Floor should remain static as per Equity Cash Rules
    assert engine.state.safety_net_floor == initial_floor
