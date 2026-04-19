import pytest
import polars as pl
from src.core.boolean_network import BooleanStateSpace

def test_map_to_bits_basic():
    # Context with indicators
    # Bit 0: price > sma_20
    # Bit 1: hurst > 0.5
    # Bit 2: adx > 25
    df = pl.DataFrame({
        "close": [105.0],
        "sma_20": [100.0],
        "hurst": [0.6],
        "adx": [30.0]
    })
    
    bss = BooleanStateSpace()
    state = bss.map_to_bits(df)
    
    # Expected: 
    # price > sma_20 (105 > 100) -> Bit 0 = 1
    # hurst > 0.5 (0.6 > 0.5) -> Bit 1 = 1
    # adx > 25 (30 > 25) -> Bit 2 = 1
    # Integer = 1*2^0 + 1*2^1 + 1*2^2 = 1 + 2 + 4 = 7
    assert state == 7

def test_map_to_bits_partial():
    df = pl.DataFrame({
        "close": [95.0],
        "sma_20": [100.0],
        "hurst": [0.6],
        "adx": [20.0]
    })
    
    bss = BooleanStateSpace()
    state = bss.map_to_bits(df)
    
    # Expected: 
    # price > sma_20 (95 > 100) -> Bit 0 = 0
    # hurst > 0.5 (0.6 > 0.5) -> Bit 1 = 1
    # adx > 25 (20 > 25) -> Bit 2 = 0
    # Integer = 0 + 2 + 0 = 2
    assert state == 2

def test_is_in_attractor():
    bss = BooleanStateSpace()
    # target_attractors = {1, 3, 7}
    assert bss.is_in_attractor(1) is True
    assert bss.is_in_attractor(3) is True
    assert bss.is_in_attractor(7) is True
    assert bss.is_in_attractor(0) is False
    assert bss.is_in_attractor(2) is False
    assert bss.is_in_attractor(4) is False
