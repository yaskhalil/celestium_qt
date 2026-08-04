import polars as pl
import numpy as np
from scipy import stats

def calculate_hurst_variance_ratio(prices: pl.Series) -> float:
    """
    Calculates the Hurst Exponent using the R/S method.
    Optimized for 1m bars in CelestiumQT.
    """
    if len(prices) < 100:
        return 0.5
        
    prices_np = prices.to_numpy()
    # 1. Calculate returns
    returns = np.diff(np.log(prices_np))
    
    def get_rs(data):
        # Mean centered
        z = data - np.mean(data)
        # Cumulative sum of deviations
        y = np.cumsum(z)
        # Range
        r = np.max(y) - np.min(y)
        # Standard deviation
        s = np.std(data)
        if s == 0: return 0
        return r / s

    # 2. Calculate R/S for different sub-window sizes
    # We'll use 10, 20, 50, 100
    lags = [10, 25, 50, 99]
    rs_values = []
    for lag in lags:
        # Average RS over non-overlapping windows
        num_windows = len(returns) // lag
        if num_windows == 0: continue
        
        rss = []
        for i in range(num_windows):
            chunk = returns[i*lag : (i+1)*lag]
            res = get_rs(chunk)
            if res > 0: rss.append(res)
            
        if rss:
            rs_values.append(np.mean(rss))
        else:
            rs_values.append(1.0) # Fallback

    if len(rs_values) < 2:
        return 0.5

    # 3. Regression: log(R/S) = H * log(n)
    slope, _, _, _, _ = stats.linregress(np.log(lags), np.log(rs_values))
    
    return float(np.clip(slope, 0.0, 1.0))

def add_adx(df: pl.DataFrame, window: int = 14) -> pl.DataFrame:
    """
    Calculates the Average Directional Index (ADX) using Polars.
    """
    df = df.with_columns([
        (pl.col("high") - pl.col("high").shift(1)).alias("up_move"),
        (pl.col("low").shift(1) - pl.col("low")).alias("down_move")
    ])

    df = df.with_columns([
        pl.when((pl.col("up_move") > pl.col("down_move")) & (pl.col("up_move") > 0))
        .then(pl.col("up_move"))
        .otherwise(0.0)
        .alias("plus_dm"),
        
        pl.when((pl.col("down_move") > pl.col("up_move")) & (pl.col("down_move") > 0))
        .then(pl.col("down_move"))
        .otherwise(0.0)
        .alias("minus_dm")
    ])

    # True Range calculation (if not already present)
    df = df.with_columns([
        pl.max_horizontal(
            (pl.col("high") - pl.col("low")),
            (pl.col("high") - pl.col("close").shift(1)).abs(),
            (pl.col("low") - pl.col("close").shift(1)).abs()
        ).alias("tr")
    ])

    # Wilder's Smoothing approx using EWMA
    alpha = 1 / window
    df = df.with_columns([
        pl.col("tr").ewm_mean(alpha=alpha, adjust=False).alias("smoothed_tr"),
        pl.col("plus_dm").ewm_mean(alpha=alpha, adjust=False).alias("smoothed_plus_dm"),
        pl.col("minus_dm").ewm_mean(alpha=alpha, adjust=False).alias("smoothed_minus_dm")
    ])

    df = df.with_columns([
        (100 * pl.col("smoothed_plus_dm") / pl.col("smoothed_tr")).alias("plus_di"),
        (100 * pl.col("smoothed_minus_dm") / pl.col("smoothed_tr")).alias("minus_di")
    ])

    df = df.with_columns(
        (100 * (pl.col("plus_di") - pl.col("minus_di")).abs() / (pl.col("plus_di") + pl.col("minus_di"))).alias("dx")
    )

    return df.with_columns(
        pl.col("dx").ewm_mean(alpha=alpha, adjust=False).alias("adx")
    )

def add_regime_features(df: pl.DataFrame) -> pl.DataFrame:
    """
    Adds statistical context features (Layer 1).
    Calculates Hurst, Hurst Gradient, ADX, ATR, Efficiency Ratio, and Vol-Adj Momentum.
    """
    if df.is_empty():
        return df

    # 1. ATR and Basic TR
    df = df.with_columns([
        (pl.col("high") - pl.col("low")).alias("tr1"),
        (pl.col("high") - pl.col("close").shift(1)).abs().alias("tr2"),
        (pl.col("low") - pl.col("close").shift(1)).abs().alias("tr3"),
    ])
    
    df = df.with_columns(
        pl.max_horizontal("tr1", "tr2", "tr3").alias("true_range")
    )
    
    df = df.with_columns(
        pl.col("true_range").rolling_mean(window_size=14).alias("atr")
    )
    
    # 2. ADX
    df = add_adx(df)
    
    # 3. Efficiency Ratio (Kaufman)
    df = df.with_columns(
        (pl.col("close") - pl.col("close").shift(10)).abs().alias("net_change"),
        pl.col("close").diff().abs().rolling_sum(window_size=10).alias("volatility")
    )
    
    df = df.with_columns(
        (pl.col("net_change") / pl.col("volatility")).alias("efficiency_ratio")
    )

    # 4. Hurst and Hurst Gradient (Rolling 100)
    df = df.with_columns(
        pl.col("close").rolling_map(
            lambda s: calculate_hurst_variance_ratio(pl.Series(s)), 
            window_size=100
        ).alias("hurst")
    )
    
    df = df.with_columns(
        (pl.col("hurst") - pl.col("hurst").shift(5)).alias("hurst_gradient")
    )

    # 4b. 20-bar Simple Moving Average (trend baseline for regime gates)
    df = df.with_columns(
        pl.col("close").rolling_mean(window_size=20).alias("sma_20")
    )

    # 5. Volatility-Adjusted Momentum (10-period)
    df = df.with_columns(
        ((pl.col("close") - pl.col("close").shift(10)) / pl.col("atr")).alias("vol_adj_momentum")
    )
    
    return df
