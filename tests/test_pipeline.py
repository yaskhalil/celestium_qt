import pytest
import polars as pl
from datetime import datetime
from unittest.mock import MagicMock, patch
import pyarrow as pa
from src.data.pipeline import KDBBuffer

def test_kdb_buffer_get_context():
    """Confirms KDBBuffer queries KDB+ and returns a Polars DataFrame."""
    with patch("pykx.SyncQConnection") as mock_conn_class:
        mock_conn = MagicMock()
        mock_conn_class.return_value = mock_conn
        
        # Mock the Q table returned by KDB+
        mock_q_table = MagicMock()
        mock_conn.return_value = mock_q_table
        
        # Create a sample pyarrow table
        df_data = pl.DataFrame({
            "timestamp": [datetime(2026, 1, 1, 9, 0)],
            "open": [100.0],
            "high": [105.0],
            "low": [95.0],
            "close": [102.0],
            "volume": [1000]
        })
        mock_q_table.to_arrow.return_value = df_data.to_arrow()
        
        buffer = KDBBuffer()
        context = buffer.get_context("AAPL", window=100)
        
        # Verify connection was initialized
        # Note: Depending on where KDBBuffer is defined, we might need to adjust the patch path
        mock_conn_class.assert_called_once()
        
        # Verify query was called correctly for KDB+
        expected_query = "neg[100] sublist select from ohlcv where sym=`AAPL"
        mock_conn.assert_called_once_with(expected_query)
        
        # Verify result is a Polars DataFrame
        assert isinstance(context, pl.DataFrame)
        assert len(context) == 1
        assert context["close"][0] == 102.0
