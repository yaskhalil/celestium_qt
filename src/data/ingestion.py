import structlog
import pykx as kx
import polars as pl
from webullsdktrade.api import API
from webullsdkcore.client import ApiClient
from src.config import settings

logger = structlog.get_logger()

class WebullIngestor:
    """
    The 'Eyes': Fetches historical and real-time bars from Webull API
    and persists them to KDB+ for the analytical pipeline.
    """
    
    def __init__(self, api_client: ApiClient):
        self.api = API(api_client)
        try:
            self.kx_conn = kx.SyncQConnection(host=settings.KDB_HOST, port=settings.KDB_PORT)
            logger.info("Ingestor: Connected to KDB+", host=settings.KDB_HOST, port=settings.KDB_PORT)
        except Exception as e:
            logger.error("Ingestor: KDB+ Connection Failed", error=str(e))
            raise

    def fetch_and_persist(self, symbol: str):
        """
        Fetches hourly bars from Webull and inserts them into KDB+ 'ohlcv' table.
        Schema: [timestamp, sym, open, high, low, close, volume]
        """
        logger.info("Ingestor: Fetching data from Webull", symbol=symbol)
        try:
            # Fetch hourly bars from Webull
            bars = self.api.get_bars(symbol, interval="1h")
            if not bars:
                logger.warning("Ingestor: No bars returned from Webull", symbol=symbol)
                return

            # Convert to Polars -> PyArrow -> KDB+
            df = pl.from_dicts(bars)
            
            # Ensure 'sym' column exists for KDB+ schema if not returned by API
            if "sym" not in df.columns:
                df = df.with_columns(pl.lit(symbol).alias("sym"))
            
            # Map columns to match KDB+ schema if necessary
            # Standard Webull bar keys are often 'open', 'high', 'low', 'close', 'volume', 'timestamp'
            # The requested schema: [timestamp, sym, open, high, low, close, volume]
            
            # Persist to KDB+ using PyArrow for efficiency
            self.kx_conn.insert("ohlcv", kx.toq(df.to_arrow()))
            logger.info("Ingestor: Data persisted to KDB+", symbol=symbol, count=len(df))
            
        except Exception as e:
            logger.error("Ingestor: Fetch and Persist failed", symbol=symbol, error=str(e))
            raise
