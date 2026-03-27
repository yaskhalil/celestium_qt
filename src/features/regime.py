import polars as pl
import numpy as np
from scipy import stats

def calculate_hurst_variance_ratio(prices: pl.Series, lags: list = [2, 5, 10, 20]) -> float:
    """
    Calculates the Hurst Exponent using the Variance Ratio (VR) method.
    Optimized for live speed in CelestiumQT.
    H = 1/2 * (1 + VR_test_slope)
    """
    if len(prices) < max(lags) * 2:
        return 0.5 # Random walk default
        
    prices_np = prices.to_numpy()
    log_prices = np.log(prices_np)
    variances = []
    
    # 1. Calculate variance of k-period returns
    base_var = np.var(np.diff(log_prices))
    
    for k in lags:
        # k-period returns: log(P_t) - log(P_{t-k})
        k_returns = log_prices[k:] - log_prices[:-k]
        k_var = np.var(k_returns)
        # Variance Ratio: Var(k-ret) / (k * Var(1-ret))
        vr = k_var / (k * base_var)
        variances.append(vr)
        
    # 2. Linear regression: log(VR) vs log(k)
    log_k = np.log(lags)
    log_vark = np.log([np.var(log_prices[k:] - log_prices[:-k]) for k in lags])
    
    slope, _, _, _, _ = stats.linregress(log_k, log_vark)
    hurst = slope / 2.0
    
    return float(np.clip(hurst, 0.0, 1.0))

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
    Calculates Hurst, ADX, ATR, and Efficiency Ratio.
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
    
    return df
