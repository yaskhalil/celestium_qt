import structlog
import polars as pl
import asyncio
from src.data.duck_storage import DuckDBStorage
from webull.core.client import ApiClient

logger = structlog.get_logger()

class WebullIngestor:
    """
    The 'Eyes': Fetches historical and real-time bars from Webull API
    and persists them to DuckDB for the analytical pipeline.
    """
    
    def __init__(self, api_client: ApiClient):
        self.api_client = api_client
        self.storage = DuckDBStorage()

    async def fetch_and_persist(self, symbol: str):
        """
        Fetches hourly bars from Webull and inserts them into DuckDB 'ohlcv' table.
        """
        logger.info("Ingestor: Fetching data from Webull", symbol=symbol)
        try:
            # Construct request manually as SDK might not have v2 market data wrappers yet
            from webull.core.request import ApiRequest
            
            class BatchBarsRequest(ApiRequest):
                def __init__(self, symbol: str):
                    super().__init__("/openapi/market-data/stock/batch-bars", version='v2', method="GET")
                    self.add_query_param("symbols", symbol)
                    self.add_query_param("timespan", "1h")
                    self.add_query_param("count", "200")
                    self.add_query_param("category", "STOCK")

            req = BatchBarsRequest(symbol)
            res = await asyncio.to_thread(self.api_client.get_response, req)
            
            if res.status_code == 200:
                data = res.json()
                # The response is usually a list of tickers or a specific dict
                # Adjusting based on common Webull v2 response format
                bars = data.get("bars", []) if isinstance(data, dict) else []
                
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
                        df = df.with_columns(pl.col("timestamp").str.replace("Z", "").str.to_datetime("%Y-%m-%dT%H:%M:%S", strict=False))
                    elif df["timestamp"].dtype in [pl.Int64, pl.Float64]:
                        df = df.with_columns(pl.from_epoch("timestamp", time_unit="ms"))

                # Persist to DuckDB
                self.storage.insert_ohlcv(df)
                logger.info("Ingestor: Data persisted to DuckDB", symbol=symbol, count=len(df))
            else:
                logger.error("Ingestor: Fetch failed", status=res.status_code, error=res.text)
            
        except Exception as e:
            logger.error("Ingestor: Fetch and Persist Error", symbol=symbol, error=str(e))
            raise
