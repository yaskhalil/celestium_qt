"""Edge case tests for robustness — boundary conditions and failure modes."""
import pytest
import polars as pl
import math
from datetime import datetime, time
from src.core.allocator import Allocator
from src.core.oracle import Oracle, AccountState
from src.models.classifier import Classifier
from src.core.regime_filter import RegimeFilter


class TestAllocatorEdgeCases:
    """Boundary conditions for position sizing."""

    def test_zero_balance(self):
        """Allocator should return minimum fractional size on strong signal even with zero balance."""
        alloc = Allocator()
        size = alloc.calculate_size(probability=0.9, atr=20.0, balance=0.0, current_price=100.0)
        # Min fractional size applies: ensures we can still trade tiny amounts
        assert size == 0.01

    def test_zero_price(self):
        """Allocator should handle zero price gracefully."""
        alloc = Allocator()
        size = alloc.calculate_size(probability=0.9, atr=20.0, balance=50000.0, current_price=0.0)
        # Should not crash, should return 0 or small value
        assert size >= 0

    def test_extreme_atr(self):
        """Allocator should handle extremely large ATR."""
        alloc = Allocator()
        size = alloc.calculate_size(probability=0.9, atr=10000.0, balance=50000.0, current_price=100.0)
        # With huge ATR, stop loss distance is huge, size should be tiny
        assert size >= 0

    def test_negative_daily_pnl_extreme(self):
        """Risk should scale down significantly on big losses."""
        alloc = Allocator()
        size_flat = alloc.calculate_size(probability=0.9, atr=20.0, balance=50000.0,
                                         current_price=100.0, daily_pnl=0.0)
        size_huge_loss = alloc.calculate_size(probability=0.9, atr=20.0, balance=50000.0,
                                              current_price=100.0, daily_pnl=-10000.0)
        assert size_huge_loss <= size_flat


class TestOracleEdgeCases:
    """Boundary conditions for the risk firewall."""

    def test_balance_exactly_at_floor(self):
        """Oracle should reject when balance exactly equals floor."""
        state = AccountState(
            balance=22500.0,  # exactly 90% of 25k
            equity=22500.0,
            initial_starting_balance=25000.0
        )
        oracle = Oracle(state)
        approved, _ = oracle.validate_trade(1, 100.0, "BUY", current_time=time(10, 0), current_hurst=0.6)
        assert approved is False

    def test_dll_exactly_at_limit(self):
        """Oracle should reject when DLL exactly reached."""
        state = AccountState(
            balance=27000.0,
            equity=27000.0,
            current_daily_pnl=-1350.0  # exactly 5% of 27k
        )
        oracle = Oracle(state)
        approved, _ = oracle.validate_trade(1, 100.0, "BUY", current_time=time(10, 0), current_hurst=0.6)
        assert approved is False

    def test_profit_ceiling_exactly_met(self):
        """Oracle should reject when profit ceiling exactly reached."""
        state = AccountState(
            balance=27000.0,
            equity=27000.0,
            current_daily_pnl=1620.0  # exactly 6% of 27k
        )
        oracle = Oracle(state)
        approved, _ = oracle.validate_trade(1, 100.0, "BUY", current_time=time(10, 0), current_hurst=0.6)
        assert approved is False

    def test_hurst_exactly_at_threshold(self):
        """Oracle should allow when Hurst exactly at threshold."""
        state = AccountState(balance=27000.0, equity=27000.0)
        oracle = Oracle(state)
        approved, _ = oracle.validate_trade(1, 100.0, "BUY", current_time=time(10, 0),
                                           current_hurst=state.hurst_threshold)
        assert approved is True

    def test_hurst_just_below_threshold(self):
        """Oracle should reject when Hurst just below threshold."""
        state = AccountState(balance=27000.0, equity=27000.0)
        oracle = Oracle(state)
        approved, _ = oracle.validate_trade(1, 100.0, "BUY", current_time=time(10, 0),
                                           current_hurst=state.hurst_threshold - 0.001)
        assert approved is False

    def test_vix_exactly_at_circuit_breaker(self):
        """Oracle should allow when VIX exactly at 30 (circuit breaker is > 30)."""
        state = AccountState(balance=27000.0, equity=27000.0)
        oracle = Oracle(state)
        approved, _ = oracle.validate_trade(1, 100.0, "BUY", current_time=time(10, 0),
                                           current_hurst=0.6, current_vix=30.0)
        assert approved is True

    def test_vix_above_circuit_breaker(self):
        """Oracle should reject when VIX above 30."""
        state = AccountState(balance=27000.0, equity=27000.0)
        oracle = Oracle(state)
        approved, _ = oracle.validate_trade(1, 100.0, "BUY", current_time=time(10, 0),
                                           current_hurst=0.6, current_vix=30.01)
        assert approved is False


class TestClassifierEdgeCases:
    """Edge cases for model inference."""

    def test_classifier_empty_frame(self):
        """Classifier should return 0 for empty frame."""
        clf = Classifier()
        prob = clf.predict(pl.DataFrame())
        assert prob == 0.0

    def test_classifier_insufficient_data(self):
        """Classifier should return 0 for insufficient bars."""
        clf = Classifier()
        # Only 100 bars; need 110 for feature window
        df = pl.DataFrame({
            "close": [100.0 + i * 0.1 for i in range(100)],
            "high": [101.0 + i * 0.1 for i in range(100)],
            "low": [99.0 + i * 0.1 for i in range(100)],
            "open": [100.5 + i * 0.1 for i in range(100)],
            "volume": [1000] * 100
        })
        prob = clf.predict(df)
        assert prob == 0.0

    def test_classifier_missing_model(self):
        """Classifier should gracefully degrade if model file missing."""
        clf = Classifier(model_path="nonexistent_model.ubj")
        # Create valid frame with enough bars
        df = pl.DataFrame({
            "close": [100.0 + i * 0.1 for i in range(150)],
            "high": [101.0 + i * 0.1 for i in range(150)],
            "low": [99.0 + i * 0.1 for i in range(150)],
            "open": [100.5 + i * 0.1 for i in range(150)],
            "volume": [1000] * 150
        })
        prob = clf.predict(df)
        # Should return 0 if model not found
        assert prob == 0.0


class TestRegimeFilterEdgeCases:
    """Edge cases for trend regime gate."""

    def test_price_exactly_at_sma20(self):
        """Gate should reject when price exactly equals SMA20 (not above)."""
        df = pl.DataFrame({
            "close": [100.0],
            "sma_20": [100.0],
            "hurst": [0.6],
            "adx": [30.0]
        })
        assert RegimeFilter().is_trending(df) is False

    def test_price_just_above_sma20(self):
        """Gate should accept when price just above SMA20."""
        df = pl.DataFrame({
            "close": [100.01],
            "sma_20": [100.0],
            "hurst": [0.6],
            "adx": [30.0]
        })
        assert RegimeFilter().is_trending(df) is True

    def test_hurst_exactly_at_threshold(self):
        """Gate should accept when Hurst exactly at threshold."""
        from src.config import settings
        df = pl.DataFrame({
            "close": [105.0],
            "sma_20": [100.0],
            "hurst": [settings.HURST_THRESHOLD],
            "adx": [30.0]
        })
        assert RegimeFilter().is_trending(df) is True

    def test_adx_exactly_at_threshold(self):
        """Gate should accept when ADX exactly at threshold."""
        from src.config import settings
        df = pl.DataFrame({
            "close": [105.0],
            "sma_20": [100.0],
            "hurst": [0.6],
            "adx": [settings.ADX_THRESHOLD]
        })
        assert RegimeFilter().is_trending(df) is True

    def test_nan_in_multiple_columns(self):
        """Gate should fail closed when multiple columns have NaN."""
        df = pl.DataFrame({
            "close": [float("nan")],
            "sma_20": [float("nan")],
            "hurst": [0.6],
            "adx": [30.0]
        })
        assert RegimeFilter().is_trending(df) is False

    def test_none_values_fail_closed(self):
        """Gate should handle None values gracefully."""
        df = pl.DataFrame({
            "close": [None],
            "sma_20": [None],
            "hurst": [0.6],
            "adx": [30.0]
        })
        assert RegimeFilter().is_trending(df) is False
