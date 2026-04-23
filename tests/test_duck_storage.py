import pytest
import polars as pl
from datetime import datetime
import os
from src.data.duck_storage import DuckDBStorage

@pytest.fixture
def temp_db():
    db_path = "data/test_celestium.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    storage = DuckDBStorage(db_path=db_path)
    yield storage
    storage.close()
    if os.path.exists(db_path):
        os.remove(db_path)

def test_duck_storage_insert_and_fetch(temp_db):
    df = pl.DataFrame({
        "timestamp": [datetime(2026, 1, 1, 10, 0), datetime(2026, 1, 1, 11, 0)],
        "symbol": ["AAPL", "AAPL"],
        "open": [150.0, 151.0],
        "high": [152.0, 153.0],
        "low": [149.0, 150.0],
        "close": [151.0, 152.0],
        "volume": [1000, 1100]
    })
    
    temp_db.insert_ohlcv(df)
    
    fetched = temp_db.fetch_ohlcv("AAPL", limit=10)
    assert len(fetched) == 2
    assert fetched["close"][0] == 151.0
    assert fetched["close"][1] == 152.0
    assert fetched["symbol"][0] == "AAPL"

def test_duck_storage_conflict(temp_db):
    df1 = pl.DataFrame({
        "timestamp": [datetime(2026, 1, 1, 10, 0)],
        "symbol": ["AAPL"],
        "open": [150.0],
        "high": [152.0],
        "low": [149.0],
        "close": [151.0],
        "volume": [1000]
    })
    
    temp_db.insert_ohlcv(df1)
    
    # Conflict update
    df2 = pl.DataFrame({
        "timestamp": [datetime(2026, 1, 1, 10, 0)],
        "symbol": ["AAPL"],
        "open": [150.0],
        "high": [152.0],
        "low": [149.0],
        "close": [155.0], # Changed
        "volume": [1000]
    })
    
    temp_db.insert_ohlcv(df2)
    
    fetched = temp_db.fetch_ohlcv("AAPL", limit=10)
    assert len(fetched) == 1
    assert fetched["close"][0] == 155.0
