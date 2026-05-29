import databento as db
import polars as pl
import os
import structlog
from datetime import datetime, timedelta, timezone
from src.config import settings

logger = structlog.get_logger()

def ingest_historical_data(days: int = 365):
    """
    Ingests historical 1-minute OHLCV data from Databento using parent symbology.
    This automatically handles contract rolls for NQ and MNQ.
    """
    api_key = settings.DATABENTO_API_KEY
    if api_key == "YOUR_DATABENTO_KEY":
        logger.error("Databento API Key not set. Skipping ingestion.")
        return

    client = db.Historical(api_key)
    
    # Target dynamic symbol on US Equities dataset
    targets = [settings.SYMBOL]
    dataset = "DBEQ.BASIC"

    try:
        dataset_range = client.metadata.get_dataset_range(dataset=dataset)
        available_end_str = dataset_range.get("end")
        if available_end_str:
            end_date = datetime.strptime(available_end_str[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        else:
            end_date = datetime.now(timezone.utc)
    except Exception as e:
        logger.warning(f"Could not fetch dataset range: {e}")
        end_date = datetime.now(timezone.utc)
        
    start_date = end_date - timedelta(days=days)

    for symbol in targets:
        logger.info(f"Databento: Ingesting continuous data for {symbol}", start=start_date.date(), end=end_date.date())
        
        try:
            # DBEQ.MAX for equities does not need stype_in="parent"
            data = client.timeseries.get_range(
                dataset=dataset,
                symbols=symbol,
                schema="ohlcv-1m",
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d")
            )

            df_raw = data.to_df()
            if df_raw.empty:
                logger.warning(f"No data returned for {symbol}")
                continue

            df = pl.from_pandas(df_raw.reset_index())
            
            df = df.select([
                pl.col("ts_event").alias("timestamp"),
                pl.col("open").cast(pl.Float64),
                pl.col("high").cast(pl.Float64),
                pl.col("low").cast(pl.Float64),
                pl.col("close").cast(pl.Float64),
                pl.col("volume").cast(pl.Int64)
            ])

            # Resample to 5-minute bars
            df = df.sort("timestamp").group_by_dynamic(
                "timestamp",
                every="5m"
            ).agg([
                pl.col("open").first(),
                pl.col("high").max(),
                pl.col("low").min(),
                pl.col("close").last(),
                pl.col("volume").sum()
            ])

            # Save to data/processed for backtest
            proc_dir = "data/processed"
            os.makedirs(proc_dir, exist_ok=True)
            output_path = os.path.join(proc_dir, f"databento_{symbol.lower()}.parquet")
            
            df.write_parquet(output_path)
            logger.info(f"Databento: Ingested and resampled {symbol} to 5m successfully", path=output_path, rows=len(df))

        except Exception as e:
            logger.error(f"Databento: Ingestion failed for {symbol}", error=str(e))

if __name__ == "__main__":
    ingest_historical_data()
