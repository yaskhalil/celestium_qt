import pytest
import polars as pl
from datetime import datetime
from unittest.mock import MagicMock, patch
from src.data.pipeline import DuckDBBuffer

def test_duckdb_buffer_get_context():
    """Confirms DuckDBBuffer queries DuckDB and returns a Polars DataFrame."""
    with patch("src.data.pipeline.DuckDBStorage") as mock_storage_class:
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage
        
        # Create a sample Polars DataFrame
        df_data = pl.DataFrame({
            "timestamp": [datetime(2026, 1, 1, 9, 0)],
            "open": [100.0],
            "high": [105.0],
            "low": [95.0],
            "close": [102.0],
            "volume": [1000]
        })
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
        assert context["close"][0] == 102.0
