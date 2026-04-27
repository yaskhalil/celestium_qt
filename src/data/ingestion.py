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
                    super().__init__("/openapi/market-data/stock/batch-bars", version='v2', method="POST", body_params={})
                    self.add_body_params("symbols", [symbol])
                    self.add_body_params("timespan", "M60") # Hourly
                    self.add_body_params("count", 200)
                    self.add_body_params("category", "US_STOCK")

            req = BatchBarsRequest(symbol)
            res = await asyncio.to_thread(self.api_client.get_response, req)
            
            if res.status_code == 200:
                data = res.json()
                # v2 batch-bars typically returns a list in 'data' or 'bars' at root
                bars = []
                if isinstance(data, dict):
                    if "bars" in data:
                        bars = data["bars"]
                    elif "data" in data:
                        # Find the bars for the requested symbol in the batch response
                        for item in data["data"]:
                            if item.get("symbol") == symbol:
                                bars = item.get("bars", [])
                                break
                
                if not bars:
                    logger.warning("Ingestor: No bars returned from Webull", symbol=symbol)
                    return

                # Convert to Polars
                df = pl.from_dicts(bars)
                
                # Map Webull v2 columns (t, o, h, l, c, v) to schema
                rename_map = {
                    "t": "timestamp",
                    "o": "open",
                    "h": "high",
                    "l": "low",
                    "c": "close",
                    "v": "volume"
                }
                rename_map = {k: v for k, v in rename_map.items() if k in df.columns}
                if rename_map:
                    df = df.rename(rename_map)

                # Map columns to match CelestiumQT schema
                if "symbol" not in df.columns:
                    df = df.with_columns(pl.lit(symbol).alias("symbol"))
                
                # Ensure timestamp is datetime
                if "timestamp" in df.columns:
                    if df["timestamp"].dtype in [pl.Int64, pl.Float64]:
                        # Webull 't' is in milliseconds
                        df = df.with_columns(pl.from_epoch(pl.col("timestamp"), time_unit="ms"))
                    elif df["timestamp"].dtype == pl.String:
                        df = df.with_columns(pl.col("timestamp").str.replace("Z", "").str.to_datetime("%Y-%m-%dT%H:%M:%S", strict=False))

                # Persist to DuckDB
                # Ensure we only have the columns expected by DuckDBStorage
                expected_cols = ["timestamp", "symbol", "open", "high", "low", "close", "volume"]
                df = df.select([col for col in expected_cols if col in df.columns])
                self.storage.insert_ohlcv(df)
                logger.info("Ingestor: Data persisted to DuckDB", symbol=symbol, count=len(df))
            else:
                logger.error("Ingestor: Fetch failed", status=res.status_code, error=res.text)
            
        except Exception as e:
            logger.error("Ingestor: Fetch and Persist Error", symbol=symbol, error=str(e))
            raise
