import polars as pl
import numpy as np
from scipy import stats

def calculate_hurst(series: np.ndarray) -> float:
    """
    Calculates the Hurst Exponent (H) to classify the regime.
    H < 0.5: Mean Reverting
    H = 0.5: Random Walk
    H > 0.5: Trending
    """
    lags = range(2, 20)
    tau = [np.sqrt(np.std(np.subtract(series[lag:], series[:-lag]))) for lag in lags]
    poly = np.polyfit(np.log(lags), np.log(tau), 1)
    return poly[0] * 2.0

def add_regime_features(df: pl.DataFrame) -> pl.DataFrame:
    """Adds regime features using Polars."""
    
    # Example ATR calculation
    df = df.with_columns([
        (pl.col("high") - pl.col("low")).alias("tr_1"),
        (pl.col("high") - pl.col("close").shift(1)).abs().alias("tr_2"),
        (pl.col("low") - pl.col("close").shift(1)).abs().alias("tr_3"),
    ])
    
    df = df.with_columns(
        pl.max_horizontal("tr_1", "tr_2", "tr_3").alias("true_range")
    )
    
    df = df.with_columns(
        pl.col("true_range").rolling_mean(window_size=14).alias("atr")
    )
    
    return df
