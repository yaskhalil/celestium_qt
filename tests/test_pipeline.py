import pytest
import polars as pl
from datetime import datetime, timedelta
from src.data.pipeline import LiveBuffer

def test_live_buffer_sliding_window():
    """Confirms the LiveBuffer correctly resamples 1m bars into 15m windows."""
    buffer = LiveBuffer(max_rows=100)
    
    # Add 20 minutes of 1m bars
    start_time = datetime(2026, 1, 1, 9, 0)
    for i in range(20):
        buffer.add_bar(
            timestamp=start_time + timedelta(minutes=i),
            o=100.0 + i,
            h=105.0 + i,
            l=95.0 + i,
            c=102.0 + i,
            v=1000
        )
        
    context = buffer.get_15m_context()
    assert context is not None
    assert len(context) == 1
    
    # The most recent 15m window should end at 9:19 (inclusive of the last bar)
    # Depending on how group_by_dynamic is configured, we check the latest Close.
    latest_bar_close = buffer.latest_bar["close"]
    context_close = context["close"].item()
    assert context_close == latest_bar_close

def test_live_buffer_pruning():
    """Confirms the buffer prunes old data after 1000 rows."""
    buffer = LiveBuffer(max_rows=10)
    
    for i in range(15):
        buffer.add_bar(
            timestamp=datetime.now() + timedelta(minutes=i),
            o=100.0, h=100.0, l=100.0, c=100.0, v=10
        )
        
    assert len(buffer.df) == 10
