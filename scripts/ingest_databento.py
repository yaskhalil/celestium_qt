import databento as db
import polars as pl
import os
import structlog
from datetime import datetime, timedelta
from src.config import settings

logger = structlog.get_logger()

def ingest_historical_data(days: int = 30):
    """
    Ingests historical 1-minute OHLCV data from Databento using parent symbology.
    This automatically handles contract rolls for NQ and MNQ.
    """
    api_key = settings.DATABENTO_API_KEY
    if api_key == "YOUR_DATABENTO_KEY":
        logger.error("Databento API Key not set. Skipping ingestion.")
        return

    client = db.Historical(api_key)
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Symbols: NQ.FUT and MNQ.FUT are the parent symbols for continuous futures
    targets = ["NQ.FUT", "MNQ.FUT"]
    dataset = "GLBX.MDP3"

    for symbol in targets:
        logger.info(f"Databento: Ingesting continuous data for {symbol}", start=start_date.date(), end=end_date.date())
        
        try:
            # Directly use stype_in='parent' to get the continuous front-month data
            data = client.timeseries.get_range(
                dataset=dataset,
                symbols=symbol,
                schema="ohlcv-1m",
                stype_in="parent",
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d")
            )

            df_raw = data.to_df()
            if df_raw.empty:
                logger.warning(f"No data returned for {symbol}")
                continue

            # Databento's to_df() for OHLCV-1m usually has a MultiIndex or just 'ts_event'
            # We'll reset index to get the timestamp
            df = pl.from_pandas(df_raw.reset_index())
            
            # Map columns to CelestiumQT schema
            # Databento OHLCV-1m schema: ts_event, open, high, low, close, volume
            df = df.select([
                pl.col("ts_event").alias("timestamp"),
                pl.col("open").cast(pl.Float64),
                pl.col("high").cast(pl.Float64),
                pl.col("low").cast(pl.Float64),
                pl.col("close").cast(pl.Float64),
                pl.col("volume").cast(pl.Int64)
            ])

            # Save to data/raw
            raw_dir = "data/raw"
            os.makedirs(raw_dir, exist_ok=True)
            safe_name = symbol.replace(".", "_")
            output_path = os.path.join(raw_dir, f"{safe_name}_historical.parquet")
            
            df.write_parquet(output_path)
            logger.info(f"Databento: Ingested {symbol} successfully", path=output_path, rows=len(df))

        except Exception as e:
            logger.error(f"Databento: Ingestion failed for {symbol}", error=str(e))

if __name__ == "__main__":
    ingest_historical_data()
