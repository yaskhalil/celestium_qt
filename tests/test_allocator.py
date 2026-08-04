import pytest
from src.core.allocator import Allocator
from src.config import settings


def test_zero_size_below_threshold():
    alloc = Allocator()
    size = alloc.calculate_size(probability=settings.SIGNAL_THRESHOLD - 0.01,
                                atr=20.0, balance=50000.0, current_price=100.0)
    assert size == 0


def test_size_scales_with_confidence():
    alloc = Allocator()
    low = alloc.calculate_size(probability=0.5, atr=20.0, balance=50000.0, current_price=100.0)
    high = alloc.calculate_size(probability=0.9, atr=20.0, balance=50000.0, current_price=100.0)
    assert high > low > 0


def test_position_pct_cap_binds():
    """Size must never exceed MAX_POSITION_PCT of balance."""
    alloc = Allocator()
    # 30% of 50k = $15k max position; at $1,000/share that is 15 shares max
    size = alloc.calculate_size(probability=0.9, atr=2.0, balance=50000.0, current_price=1000.0)
    assert size <= (50000.0 * settings.MAX_POSITION_PCT) / 1000.0


def test_risk_halved_in_drawdown():
    alloc = Allocator()
    flat = alloc.calculate_size(probability=0.9, atr=20.0, balance=50000.0,
                                current_price=100.0, daily_pnl=0.0)
    losing = alloc.calculate_size(probability=0.9, atr=20.0, balance=50000.0,
                                  current_price=100.0, daily_pnl=-500.0)
    assert losing < flat


def test_min_fractional_size_on_strong_signal():
    alloc = Allocator()
    # Extremely expensive underlying: risk-based size would be < 0.01
    size = alloc.calculate_size(probability=0.9, atr=5.0, balance=50000.0,
                                current_price=50000.0)
    assert size >= 0.01
