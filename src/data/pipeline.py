import polars as pl
from datetime import datetime
import structlog

logger = structlog.get_logger()

class PolarsPipeline:
    """Real-time Polars resampling/buffering"""
    
    def __init__(self, window_size: str = "15m"):
        self.window_size = window_size
        self.buffer = pl.DataFrame()

    def add_tick(self, tick: dict):
        """Adds a tick to the buffer and resamples."""
        tick_df = pl.DataFrame(tick)
        self.buffer = pl.concat([self.buffer, tick_df])
        
        # Keep only last N ticks or rows needed
        if len(self.buffer) > 10000:
            self.buffer = self.buffer.tail(5000)

    def resample_to_bars(self) -> pl.DataFrame:
        """Resamples ticks/1m bars to target timeframe."""
        if self.buffer.is_empty():
            return pl.DataFrame()
        
        # Assumes 'timestamp' column is in datetime format
        return (
            self.buffer.sort("timestamp")
            .group_by_dynamic("timestamp", every=self.window_size)
            .agg([
                pl.col("price").first().alias("open"),
                pl.col("price").max().alias("high"),
                pl.col("price").min().alias("low"),
                pl.col("price").last().alias("close"),
                pl.col("volume").sum().alias("volume"),
            ])
        )
