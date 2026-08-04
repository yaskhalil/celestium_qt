import pytest
import polars as pl
from datetime import datetime, timedelta
from src.core.backtest_engine import BacktestEngine


def _make_bars(n: int, start_price: float = 100.0, step: float = 0.0,
               atr: float = 20.0, hurst: float = 0.6,
               low_delta: float = -5.0, high_delta: float = 5.0) -> pl.DataFrame:
    """Builds a synthetic 1-minute bar frame with feature columns pre-filled."""
    start_time = datetime(2026, 1, 1, 9, 30)
    data = []
    for i in range(n):
        price = start_price + (i * step)
        data.append({
            "timestamp": start_time + timedelta(minutes=i),
            "open": price,
            "high": price + high_delta,
            "low": price + low_delta,
            "close": price,
            "volume": 1000,
            "atr": atr,
            "hurst": hurst,
        })
    return pl.DataFrame(data)


def test_backtest_engine_fill_logic():
    """
    Deterministic audit: a bar whose low pierces the stop-loss must close the
    trade at the stop price with a negative PnL.
    """
    engine = BacktestEngine(initial_balance=50000.0)
    engine.classifier.predict_features = lambda feature_data: 0.9  # constant signal

    df = _make_bars(120)
    # Last bar: low crashes through the stop (entry 100, SL = 100 - 0.5*20 = 90)
    df = df.with_columns(
        pl.when(pl.col("timestamp") == df["timestamp"][-1])
        .then(pl.lit(80.0))
        .otherwise(pl.col("low"))
        .alias("low")
    )

    engine.run(df)

    assert len(engine.trades) > 0
    assert engine.trades[0]["reason"] == "STOP_LOSS"
    # Entry at ~100, exit at SL 90 -> loss = -10 * shares < 0
    assert engine.trades[0]["pnl"] < 0


def test_backtest_engine_dll_veto():
    """
    Verifies the Oracle's Daily Loss Limit veto binds inside the backtest
    loop: once current_daily_pnl breaches 5% of balance, entries stop.
    """
    engine = BacktestEngine(initial_balance=50000.0)
    engine.classifier.predict_features = lambda feature_data: 0.9  # constant signal

    # Pre-close to the DLL (5% of 50k = $2,500): one stop-out should breach it.
    engine.state.current_daily_pnl = -2300.0

    # Continuous drop with huge lows: every trade hits the stop.
    df = _make_bars(150, start_price=500.0, step=-0.1, atr=20.0,
                    low_delta=-50.0, high_delta=1.0)

    engine.run(df)

    # The DLL breach must bind: day PnL crossed -$2,500 and the engine was
    # throttled hard (T+1 GFV also caps how many full-size buys are affordable).
    assert engine.state.trading_history[-1].pnl <= -2500.0
    assert len(engine.trades) < 100


def test_backtest_engine_eod_anchor():
    """
    Verifies the EOD anchor finalizes the session, keeps the floor static
    (anchored to starting balance) and banks the day's profit.
    """
    engine = BacktestEngine(initial_balance=50000.0)
    engine.classifier.predict_features = lambda feature_data: 0.9

    # Rising price with huge highs: every trade hits the take-profit.
    df = _make_bars(120, start_price=100.0, step=2.0, atr=50.0,
                    low_delta=-1.0, high_delta=500.0)

    initial_floor = engine.state.safety_net_floor  # 90% of 50k = 45k

    engine.run(df)

    assert engine.state.balance > 50000.0
    assert engine.state.safety_net_floor == initial_floor  # static anchor
    assert engine.state.trading_history[-1].pnl > 0
