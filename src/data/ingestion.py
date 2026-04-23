import structlog
import polars as pl
from src.data.duck_storage import DuckDBStorage
from src.execution.webull_client import WebullClient

logger = structlog.get_logger()

class WebullIngestor:
    """
    The 'Eyes': Fetches historical and real-time bars from Webull API
    and persists them to DuckDB for the analytical pipeline.
    """
    
    def __init__(self, client: WebullClient):
        self.client = client
        self.storage = DuckDBStorage()

    async def fetch_and_persist(self, symbol: str):
        """
        Fetches hourly bars from Webull and inserts them into DuckDB 'ohlcv' table.
        """
        logger.info("Ingestor: Fetching data from Webull", symbol=symbol)
        try:
            # Fetch hourly bars from Webull
            response = await self.client.get_bars(symbol, interval="1h")
            
            # Extract bars from response (adjusting for likely API format)
            bars = response if isinstance(response, list) else response.get("bars", [])
            
            if not bars:
                logger.warning("Ingestor: No bars returned from Webull", symbol=symbol)
                return

            # Convert to Polars
            df = pl.from_dicts(bars)
            
            # Map columns to match CelestiumQT schema
            if "symbol" not in df.columns:
                df = df.with_columns(pl.lit(symbol).alias("symbol"))
            
            # Ensure timestamp is datetime
            if "timestamp" in df.columns:
                if df["timestamp"].dtype == pl.String:
                    df = df.with_columns(pl.col("timestamp").str.to_datetime())
                elif df["timestamp"].dtype in [pl.Int64, pl.Float64]:
                    # Assuming milliseconds if it's a large integer
                    df = df.with_columns(pl.from_epoch("timestamp", time_unit="ms"))

            # Persist to DuckDB
            self.storage.insert_ohlcv(df)
            logger.info("Ingestor: Data persisted to DuckDB", symbol=symbol, count=len(df))
            
        except Exception as e:
            logger.error("Ingestor: Fetch and Persist failed", symbol=symbol, error=str(e))
            raise
