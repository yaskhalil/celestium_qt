import polars as pl
import structlog
from src.data.duck_storage import DuckDBStorage
from typing import Optional

logger = structlog.get_logger()

class DuckDBBuffer:
    """
    DuckDB Buffer: Queries DuckDB for historical OHLCV data.
    Provides context windows for feature calculation.
    """
    def __init__(self):
        self.storage = DuckDBStorage()

    def get_context(self, symbol: str, window: int = 150) -> pl.DataFrame:
        """
        Query DuckDB for the last N bars for the given symbol.
        Returns the result as a Polars DataFrame.
        """
        return self.storage.fetch_ohlcv(symbol, limit=window)
