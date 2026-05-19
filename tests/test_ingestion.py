import pytest
import polars as pl
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timezone
from src.data.ingestion import AlpacaIngestor
from src.execution.alpaca_client import AlpacaClient

@pytest.mark.asyncio
async def test_alpaca_ingestor_fetch_success():
    # Mock Alpaca Client
    mock_client = MagicMock(spec=AlpacaClient)
    
    # Create mock data in Polars format
    mock_df = pl.DataFrame({
        "timestamp": [datetime(2026, 4, 28, 10, 0, 0, tzinfo=timezone.utc)],
        "symbol": ["SPLG"],
        "open": [100.0],
        "high": [101.0],
        "low": [99.0],
        "close": [100.5],
        "volume": [1000]
    })
    
    mock_client.get_bars = AsyncMock(return_value=mock_df)

    ingestor = AlpacaIngestor(client=mock_client)
    ingestor.storage = MagicMock() # Mock DuckDB storage
    
    await ingestor.fetch_and_persist("SPLG")
    
    # Verify get_bars call
    mock_client.get_bars.assert_called_once()
    # Verify storage insertion
    ingestor.storage.insert_ohlcv.assert_called_once()
    inserted_df = ingestor.storage.insert_ohlcv.call_args[0][0]
    
    # Verify timestamp transformation (should be naive NY time)
    ts = inserted_df["timestamp"][0]
    assert ts.tzinfo is None
    # UTC 10:00:00 should be NY 05:00:00 or 06:00:00 depending on DST
    # In 2026 April, it's EDT (UTC-4), so 10:00 UTC is 06:00 EDT.
    assert ts.hour == 6
    
    assert len(inserted_df) == 1
    assert inserted_df["symbol"][0] == "SPLG"
    assert inserted_df["close"][0] == 100.5
