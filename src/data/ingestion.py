import databento as db
import polars as pl
import structlog
import asyncio
import re
from datetime import datetime, timedelta, timezone
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
            # Use a 15-minute safety lag for historical data availability
            end = datetime.now(timezone.utc) - timedelta(minutes=15)
            start = end - timedelta(minutes=lookback_minutes)
            
            # Continuous Futures use 'parent', Stocks use 'raw_symbol'
            stype = "parent" if ".FUT" in symbol else "raw_symbol"
            
            # API call is blocking in SDK, run in thread
            
            async def _get_data(start_ts, end_ts):
                return await asyncio.to_thread(
                    client.timeseries.get_range,
                    dataset="GLBX.MDP3" if ".FUT" in symbol else "XNAS.ITCH",
                    symbols=symbol,
                    schema="ohlcv-1m",
                    stype_in=stype,
                    start=start_ts.strftime("%Y-%m-%dT%H:%M:%S"),
                    end=end_ts.strftime("%Y-%m-%dT%H:%M:%S")
                )

            try:
                data = await _get_data(start, end)
            except Exception as e:
                err_msg = str(e)
                if "403" in err_msg and "license" in err_msg.lower():
                    logger.error("Ingestor: Databento Licensing Error. Today's data (XNAS.ITCH) requires a 'Live' license if accessed before end-of-day.", symbol=symbol)
                    raise
                
                if "data_end_after_available_end" in err_msg:
                    # Extract 'available up to' timestamp if possible
                    # Example: "...available up to '2026-04-30 15:00:00+00:00'."
                    match = re.search(r"available up to '([^']+)'", err_msg)
                    if match:
                        suggested_end_str = match.group(1)
                        # Parse the suggested end time (usually ISO format or similar)
                        try:
                            # Try parsing Databento's timestamp format
                            suggested_end = datetime.fromisoformat(suggested_end_str.replace(" ", "T"))
                            logger.info("Ingestor: Retrying with suggested end time", symbol=symbol, suggested_end=suggested_end_str)
                            data = await _get_data(start, suggested_end)
                        except Exception as parse_err:
                            logger.warning("Ingestor: Failed to parse suggested end time", error=str(parse_err))
                            raise e
                    else:
                        raise e
                else:
                    raise e

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
