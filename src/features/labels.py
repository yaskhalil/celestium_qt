import polars as pl
import numpy as np
from typing import Optional

def apply_triple_barrier_labels(
    df: pl.DataFrame,
    pt_sl: list = [1, 1],
    target_std_window: int = 100,
    vertical_barrier: int = 16  # 16 * 15m bars ~= 4 hours
) -> pl.DataFrame:
    """
    Implements the Triple Barrier Method for labeling.
    Barriers:
    1. Profit Taking (PT): Top barrier hit.
    2. Stop Loss (SL): Bottom barrier hit.
    3. Vertical: Time limit reached.
    
    Returns: 1 if PT hit first, 0 otherwise (SL or Vertical hit).
    """
    if df.is_empty():
        return df

    # 1. Calculate Daily Volatility (Standard Deviation of returns) as dynamic barrier width
    df = df.with_columns(
        pl.col("close").log().diff().rolling_std(window_size=target_std_window).alias("volatility")
    )
    
    # 2. Drop rows where volatility is null (start of series)
    df = df.drop_nulls(subset=["volatility"])
    
    # 3. Labeling Logic (Vectorized-ish using Polars)
    # Note: True Triple Barrier is path-dependent. For high performance, 
    # we simulate the forward look for each row.
    
    closes = df["close"].to_numpy()
    vols = df["volatility"].to_numpy()
    labels = []

    for i in range(len(closes)):
        # Define search window (Vertical Barrier)
        end_idx = min(i + vertical_barrier, len(closes) - 1)
        if i == end_idx:
            labels.append(0)
            continue
            
        subset = closes[i+1 : end_idx+1]
        start_price = closes[i]
        
        # Dynamic barrier widths
        pt_width = vols[i] * pt_sl[0]
        sl_width = vols[i] * pt_sl[1]
        
        # Upper and Lower price barriers
        # Use a small epsilon or check if volatility is 0 to avoid false positives
        if vols[i] > 0:
            upper_barrier = start_price * (1 + pt_width)
            lower_barrier = start_price * (1 - sl_width)
        else:
            # If no volatility, barriers are effectively unreachable except by time-out
            upper_barrier = float("inf")
            lower_barrier = float("-inf")
        
        # Find which barrier is hit first
        first_touch = 0 # Default: Vertical Barrier (Time-out)
        for price in subset:
            if price >= upper_barrier:
                first_touch = 1 # Profit Taking Hit
                break
            if price <= lower_barrier:
                first_touch = 0 # Stop Loss Hit
                break
                
        labels.append(first_touch)

    return df.with_columns(pl.Series("label", labels))
