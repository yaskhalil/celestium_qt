import pytest
import polars as pl
from unittest.mock import MagicMock, patch
from src.data.ingestion import DatabentoIngestor

@pytest.mark.asyncio
async def test_databento_ingestor_fetch_success():
    # Mock Databento Client
    mock_db_client = MagicMock()
    mock_data = MagicMock()
    # Mocking to_df to return a pandas DF that Polars can consume
    import pandas as pd
    mock_df = pd.DataFrame({
        "ts_event": [pd.Timestamp("2026-04-28 10:00:00")],
        "open": [100.0],
        "high": [101.0],
        "low": [99.0],
        "close": [100.5],
        "volume": [1000]
    }).set_index("ts_event")
    mock_data.to_df.return_value = mock_df
    mock_db_client.timeseries.get_range.return_value = mock_data

    with patch("databento.Historical", return_value=mock_db_client):
        ingestor = DatabentoIngestor(api_key="fake_key")
        ingestor.storage = MagicMock() # Mock DuckDB storage
        await ingestor.fetch_and_persist("SPLG")
        
        # Verify get_range call
        mock_db_client.timeseries.get_range.assert_called_once()
        # Verify storage insertion
        ingestor.storage.insert_ohlcv.assert_called_once()
        inserted_df = ingestor.storage.insert_ohlcv.call_args[0][0]
        assert len(inserted_df) == 1
        assert inserted_df["symbol"][0] == "SPLG"
