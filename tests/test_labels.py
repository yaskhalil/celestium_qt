import pytest
import polars as pl
import numpy as np
from src.features.labels import apply_triple_barrier_labels

def test_triple_barrier_profit_hit():
    """Confirms label 1 is assigned when Profit Taking is hit first."""
    # Create a rising series: 100, 101, 102...
    prices = np.linspace(100, 110, 200)
    # Set a very small volatility to make sure PT is hit
    df = pl.DataFrame({"close": prices})
    
    # We'll mock the volatility manually for the test by using a subset
    # but the function calculates its own. Let's provide enough data.
    labeled_df = apply_triple_barrier_labels(df, pt_sl=[0.1, 0.1], target_std_window=5)
    
    # Since prices are strictly rising, PT should be hit first.
    # We check a row in the middle where volatility has settled.
    assert labeled_df["label"][50] == 1

def test_triple_barrier_stop_loss_hit():
    """Confirms label 0 is assigned when Stop Loss is hit first."""
    # Create a falling series
    prices = np.linspace(100, 90, 200)
    df = pl.DataFrame({"close": prices})
    
    labeled_df = apply_triple_barrier_labels(df, pt_sl=[0.1, 0.1], target_std_window=5)
    
    # Since prices are strictly falling, SL should be hit first.
    assert labeled_df["label"][50] == 0

def test_triple_barrier_vertical_barrier():
    """Confirms label 0 is assigned if no barrier hit before time-out."""
    # Flat series: No change
    prices = np.ones(200) * 100
    df = pl.DataFrame({"close": prices})
    
    labeled_df = apply_triple_barrier_labels(df, pt_sl=[2, 2], target_std_window=5, vertical_barrier=10)
    
    # Prices don't move, so vertical barrier (time-out) hits first.
    assert labeled_df["label"][50] == 0
