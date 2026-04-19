import polars as pl
import pykx as kx
from src.config import settings
import structlog
from typing import Optional

logger = structlog.get_logger()

class KDBBuffer:
    """
    KDB+ Buffer: Queries KDB+ for historical OHLCV data.
    Provides context windows for feature calculation.
    """
    def __init__(self):
        self.kx_conn = kx.SyncQConnection(host=settings.KDB_HOST, port=settings.KDB_PORT)

    def get_context(self, symbol: str, window: int = 150) -> pl.DataFrame:
        """
        Query KDB+ for the last N bars for the given symbol.
        Returns the result as a Polars DataFrame.
        """
        query = f"neg[{window}] sublist select from ohlcv where sym=`{symbol}"
        q_table = self.kx_conn(query)
        return pl.from_arrow(q_table.to_arrow())
