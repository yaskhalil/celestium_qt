import polars as pl
from datetime import datetime
import structlog

logger = structlog.get_logger()

class PolarsPipeline:
    """Real-time Polars resampling/buffering (2026 Edition)"""
    
    def __init__(self, window_size: str = "15m", stride: str = "1m"):
        self.window_size = window_size
        self.stride = stride
        self.buffer = pl.DataFrame(
            schema={
                "timestamp": pl.Datetime,
                "price": pl.Float64,
                "volume": pl.Int64
            }
        )

    def add_tick(self, timestamp: datetime, price: float, volume: int):
        """Adds a tick to the buffer."""
        new_tick = pl.DataFrame({
            "timestamp": [timestamp],
            "price": [price],
            "volume": [volume]
        })
        self.buffer = pl.concat([self.buffer, new_tick])
        
        # Prune buffer to keep only last 24 hours of 1m data for Hurst/Regime context
        limit = datetime.now().timestamp() - (24 * 3600)
        # self.buffer = self.buffer.filter(pl.col("timestamp").dt.timestamp() > limit)

    def resample_to_15m(self) -> pl.DataFrame:
        """
        Resamples 1m Rithmic ticks into 15m OHLCV bars using a sliding window.
        Optimized for Hurst Exponent and Regime Detection.
        """
        if self.buffer.is_empty():
            return pl.DataFrame()
            
        # 1. Group by 15m Dynamic Window
        bars = (
            self.buffer.sort("timestamp")
            .group_by_dynamic(
                "timestamp", 
                every=self.stride, # 1m stride for sliding window
                period=self.window_size, # 15m lookback
                include_boundaries=True
            )
            .agg([
                pl.col("price").first().alias("open"),
                pl.col("price").max().alias("high"),
                pl.col("price").min().alias("low"),
                pl.col("price").last().alias("close"),
                pl.col("volume").sum().alias("volume"),
                # Add log returns for Hurst calculation later
                (pl.col("price").last().log() - pl.col("price").first().log()).alias("log_return")
            ])
        )
        
        return bars

    def get_hurst_context(self, min_periods: int = 30) -> pl.Series:
        """Extracts the price series needed for Hurst calculation."""
        bars = self.resample_to_15m()
        if len(bars) < min_periods:
            return pl.Series()
        return bars["close"]
