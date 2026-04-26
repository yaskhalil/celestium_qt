import sys
from unittest.mock import MagicMock

# Mock dependencies that are not installed
mock_kx = MagicMock()
sys.modules["pykx"] = mock_kx
mock_webull = MagicMock()
sys.modules["webullsdktrade"] = mock_webull
sys.modules["webullsdktrade.api"] = mock_webull.api
mock_webull_core = MagicMock()
sys.modules["webullsdkcore"] = mock_webull_core
sys.modules["webullsdkcore.client"] = mock_webull_core.client

import pytest
from unittest.mock import patch
import polars as pl
from src.data.ingestion import WebullIngestor

@patch("src.data.ingestion.DuckDBStorage")
def test_webull_ingestor_fetch_and_persist(mock_duckdb_class):
    mock_api_client = MagicMock()
    mock_duckdb_instance = mock_duckdb_class.return_value
    
    # Mock API response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "bars": [
            {"timestamp": "2026-04-17T09:00:00Z", "open": 150.0, "high": 155.0, "low": 149.0, "close": 153.0, "volume": 1000},
            {"timestamp": "2026-04-17T10:00:00Z", "open": 153.0, "high": 156.0, "low": 152.0, "close": 154.0, "volume": 1200},
        ]
    }
    
    # In asyncio.to_thread, get_response is called
    mock_api_client.get_response.return_value = mock_response
    
    import asyncio
    ingestor = WebullIngestor(mock_api_client)
    asyncio.run(ingestor.fetch_and_persist("AAPL"))
    
    # Verify Webull API call
    mock_api_client.get_response.assert_called_once()
    req = mock_api_client.get_response.call_args[0][0]
    assert req._method == "GET"
    assert req._params.get("symbols") == "AAPL" or getattr(req, "query_string", "") == "symbols=AAPL"
    
    # Verify DuckDB insert call
    mock_duckdb_instance.insert_ohlcv.assert_called_once()
    args, _ = mock_duckdb_instance.insert_ohlcv.call_args
    df = args[0]
    assert len(df) == 2
    assert "symbol" in df.columns
