import pytest
import polars as pl
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from src.data.pipeline import DuckDBBuffer


def _synthetic_bars(n: int) -> pl.DataFrame:
    start = datetime(2026, 1, 1, 9, 30)
    return pl.DataFrame({
        "timestamp": [start + timedelta(minutes=i) for i in range(n)],
        "open": [100.0 + i for i in range(n)],
        "high": [102.0 + i for i in range(n)],
        "low": [98.0 + i for i in range(n)],
        "close": [100.0 + i for i in range(n)],
        "volume": [1000] * n,
    })


def test_duckdb_buffer_get_context():
    """Confirms DuckDBBuffer queries DuckDB and returns a Polars DataFrame."""
    with patch("src.data.pipeline.DuckDBStorage") as mock_storage_class:
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage
        
        df_data = _synthetic_bars(1)
        mock_storage.fetch_ohlcv.return_value = df_data
        
        buffer = DuckDBBuffer()
        context = buffer.get_context("AAPL", window=100)
        
        # Verify storage was initialized
        mock_storage_class.assert_called_once()
        
        # Verify fetch_ohlcv was called correctly
        mock_storage.fetch_ohlcv.assert_called_once_with("AAPL", limit=100)
        
        # Verify result is a Polars DataFrame
        assert isinstance(context, pl.DataFrame)
        assert len(context) == 1
        assert context["close"][0] == 100.0


def test_get_context_enriches_features_for_signal_windows():
    """
    The live path must see real statistical features. Windows >= 110 bars
    are enriched with add_regime_features() so the strategy and Oracle gates
    read actual hurst/adx/atr/sma_20 instead of silent defaults.
    """
    with patch("src.data.pipeline.DuckDBStorage") as mock_storage_class:
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage
        mock_storage.fetch_ohlcv.return_value = _synthetic_bars(150)
        
        buffer = DuckDBBuffer()
        context = buffer.get_context("SPYM", window=150)
        
        for col in ("hurst", "adx", "atr", "sma_20"):
            assert col in context.columns, f"missing feature column: {col}"
        # Last bar should carry real values (non-null on a 150-bar frame)
        assert context["sma_20"].tail(1).item() is not None


def test_get_context_skips_enrichment_for_monitor_windows():
    """
    Short monitor windows (5 bars) skip enrichment: the rolling indicators
    need history, and the monitor path only reads 'close'.
    """
    with patch("src.data.pipeline.DuckDBStorage") as mock_storage_class:
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage
        mock_storage.fetch_ohlcv.return_value = _synthetic_bars(5)
        
        buffer = DuckDBBuffer()
        context = buffer.get_context("SPYM", window=5)
        
        assert "hurst" not in context.columns
