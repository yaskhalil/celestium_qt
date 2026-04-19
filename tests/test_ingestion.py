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

@patch("src.data.ingestion.kx.SyncQConnection")
@patch("src.data.ingestion.API")
def test_webull_ingestor_fetch_and_persist(mock_api_class, mock_kx_conn_class):
    mock_api_client = MagicMock()
    mock_api_instance = mock_api_class.return_value
    mock_kx_conn_instance = mock_kx_conn_class.return_value
    
    # Mock API response
    mock_api_instance.get_bars.return_value = [
        {"timestamp": "2026-04-17T09:00:00Z", "open": 150.0, "high": 155.0, "low": 149.0, "close": 153.0, "volume": 1000},
        {"timestamp": "2026-04-17T10:00:00Z", "open": 153.0, "high": 156.0, "low": 152.0, "close": 154.0, "volume": 1200},
    ]
    
    ingestor = WebullIngestor(mock_api_client)
    ingestor.fetch_and_persist("AAPL")
    
    # Verify Webull API call
    mock_api_instance.get_bars.assert_called_once_with("AAPL", interval="1h")
    
    # Verify KDB+ insert call
    mock_kx_conn_instance.insert.assert_called_once()
    args, _ = mock_kx_conn_instance.insert.call_args
    assert args[0] == "ohlcv"
    # The second arg should be the result of kx.toq(...)
    # Since we mocked kx, kx.toq will return a mock
