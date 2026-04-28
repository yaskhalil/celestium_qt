import databento as db
import polars as pl
import structlog
from datetime import datetime, timedelta
from src.data.duck_storage import DuckDBStorage

logger = structlog.get_logger()

class DatabentoIngestor:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.storage = DuckDBStorage()

    async def fetch_and_persist(self, symbol: str, lookback_minutes: int = 60):
        logger.info("Ingestor: Fetching data from Databento", symbol=symbol)
        try:
            client = db.Historical(self.api_key)
            end = datetime.now()
            start = end - timedelta(minutes=lookback_minutes)
            
            # Continuous Futures use 'parent', Stocks use 'raw_symbol'
            stype = "parent" if ".FUT" in symbol else "raw_symbol"
            
            # API call is blocking in SDK, run in thread
            import asyncio
            data = await asyncio.to_thread(
                client.timeseries.get_range,
                dataset="GLBX.MDP3" if ".FUT" in symbol else "XNAS.ITCH",
                symbols=symbol,
                schema="ohlcv-1m",
                stype_in=stype,
                start=start.strftime("%Y-%m-%dT%H:%M:%S"),
                end=end.strftime("%Y-%m-%dT%H:%M:%S")
            )

            df_raw = data.to_df()
            if df_raw.empty:
                logger.warning("Ingestor: No data returned from Databento", symbol=symbol)
                return

            # Reset index to get ts_event as a column
            df = pl.from_pandas(df_raw.reset_index())
            
            # Map Databento schema to Celestium schema
            df = df.select([
                pl.col("ts_event").alias("timestamp"),
                pl.lit(symbol).alias("symbol"),
                pl.col("open").cast(pl.Float64),
                pl.col("high").cast(pl.Float64),
                pl.col("low").cast(pl.Float64),
                pl.col("close").cast(pl.Float64),
                pl.col("volume").cast(pl.Int64)
            ])

            self.storage.insert_ohlcv(df)
            logger.info("Ingestor: Data persisted to DuckDB", symbol=symbol, count=len(df))

        except Exception as e:
            logger.error("Ingestor: Databento Fetch Error", symbol=symbol, error=str(e))
            raise
