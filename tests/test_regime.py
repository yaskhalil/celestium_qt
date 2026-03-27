import pytest
import polars as pl
import numpy as np
from src.features.regime import calculate_hurst_variance_ratio

def test_hurst_trending_data():
    """Confirms Hurst > 0.5 for a strong trend."""
    # Create a perfectly trending series
    prices = np.linspace(100, 200, 500)
    # Add very minimal noise
    prices += np.random.normal(0, 0.1, 500)
    
    hurst = calculate_hurst_variance_ratio(pl.Series(prices))
    print(f"Trending Hurst: {hurst}")
    assert hurst > 0.5

def test_hurst_mean_reverting_data():
    """Confirms Hurst < 0.5 for mean-reverting data."""
    # Create an Ornstein-Uhlenbeck process or simple oscillating data
    n = 500
    prices = np.zeros(n)
    prices[0] = 100
    mu = 100
    theta = 0.5
    sigma = 2
    
    for t in range(1, n):
        prices[t] = prices[t-1] + theta * (mu - prices[t-1]) + sigma * np.random.randn()
        
    hurst = calculate_hurst_variance_ratio(pl.Series(prices))
    print(f"Mean Reverting Hurst: {hurst}")
    assert hurst < 0.5

def test_hurst_random_walk():
    """Confirms Hurst ~ 0.5 for a random walk."""
    # Standard geometric brownian motion or simple random walk
    n = 1000
    returns = np.random.normal(0, 1, n)
    prices = 100 + np.cumsum(returns)
    
    hurst = calculate_hurst_variance_ratio(pl.Series(prices))
    print(f"Random Walk Hurst: {hurst}")
    # Random walk Hurst should be around 0.5, we'll use a broad range for noise
    assert 0.35 < hurst < 0.65
