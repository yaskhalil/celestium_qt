import polars as pl
import numpy as np
from datetime import datetime, timedelta
import os
import structlog

logger = structlog.get_logger()

def generate_market_data(
    symbol: str = "NQZ4",
    start_date: str = "2026-01-01",
    num_days: int = 5,
    base_price: float = 20000.0,
    volatility: float = 0.0002, # 1m vol
    drift: float = 0.00001,
    include_flash_crash: bool = True
) -> pl.DataFrame:
    """
    Generates synthetic 1m OHLCV data for NQ.
    Includes a 'Flash Crash' scenario to test Oracle DLL/Safety Net logic.
    """
    logger.info("Generating Synthetic Market Data", symbol=symbol, days=num_days)
    
    # 1. Setup Time Index (Trading hours only: 9:30 AM - 4:00 PM ET)
    # Simplified: 390 minutes per day
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    timestamps = []
    for d in range(num_days):
        day_start = start_dt + timedelta(days=d, hours=9, minutes=30)
        for m in range(390):
            timestamps.append(day_start + timedelta(minutes=m))
            
    num_rows = len(timestamps)
    
    # 2. Generate Random Walk (Geometric Brownian Motion)
    returns = np.random.normal(drift, volatility, num_rows)
    
    # 3. Inject "Flash Crash" on Day 2
    if include_flash_crash and num_days >= 2:
        crash_start = 390 + 100 # Mid-day 2
        crash_duration = 15
        # 400 point drop in 15 mins for NQ (~2% drop)
        returns[crash_start : crash_start + crash_duration] -= 0.002 
        logger.info("Injected Flash Crash into Day 2", start_index=crash_start)

    # Calculate price path
    price_path = base_price * np.exp(np.cumsum(returns))
    
    # 4. Create OHLC from Price Path
    highs = price_path * (1 + np.abs(np.random.normal(0, volatility/2, num_rows)))
    lows = price_path * (1 - np.abs(np.random.normal(0, volatility/2, num_rows)))
    opens = np.roll(price_path, 1)
    opens[0] = base_price
    
    # 5. Build Polars DataFrame
    df = pl.DataFrame({
        "timestamp": timestamps,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": price_path,
        "volume": np.random.randint(500, 5000, num_rows)
    })
    
    # Ensure High/Low bounds are valid
    df = df.with_columns([
        pl.max_horizontal("open", "close", "high").alias("high"),
        pl.min_horizontal("open", "close", "low").alias("low")
    ])
    
    return df

def main():
    raw_dir = "data/raw"
    os.makedirs(raw_dir, exist_ok=True)
    
    # Generate 10 days of synthetic NQ data
    df = generate_market_data(num_days=10)
    
    output_path = os.path.join(raw_dir, "synthetic_nq_1m.parquet")
    df.write_parquet(output_path)
    
    logger.info("Synthetic Data Saved", path=output_path, rows=len(df))

if __name__ == "__main__":
    main()
