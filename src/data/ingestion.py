import polars as pl
import structlog
import asyncio
from datetime import datetime, timezone
from src.data.duck_storage import DuckDBStorage
from src.execution.alpaca_client import AlpacaClient

logger = structlog.get_logger()

class AlpacaIngestor:
    def __init__(self, client: AlpacaClient):
        self.client = client
        self.storage = DuckDBStorage()

    async def fetch_and_persist(self, symbol: str, lookback_minutes: int = 60):
        """
        Fetches historical data from Alpaca and persists to DuckDB.
        Replaces the Databento ingestor to save costs.
        """
        logger.info("Ingestor: Fetching data from Alpaca", symbol=symbol)
        try:
            # Note: limit=lookback_minutes assumes roughly 1 bar per minute.
            # We'll fetch a bit extra to be safe.
            df = await self.client.get_bars(symbol, timeframe="1Min", limit=lookback_minutes + 10)
            
            if df.is_empty():
                logger.warning("Ingestor: No data returned from Alpaca", symbol=symbol)
                return

            # AlpacaClient already returns a Polars DataFrame with the correct schema
            # We must convert the timezone to NY and strip it for DuckDB TIMESTAMP_NS
            df = df.with_columns(
                pl.col("timestamp").dt.convert_time_zone("America/New_York").dt.replace_time_zone(None)
            )

            # Ensure it matches the DuckDB storage expectations
            df = df.select([
                pl.col("timestamp"),
                pl.col("symbol"),
                pl.col("open"),
                pl.col("high"),
                pl.col("low"),
                pl.col("close"),
                pl.col("volume")
            ])

            self.storage.insert_ohlcv(df)
            logger.info("Ingestor: Data persisted to DuckDB", symbol=symbol, count=len(df))

        except Exception as e:
            logger.error("Ingestor: Alpaca Fetch Error", symbol=symbol, error=str(e))
            raise
