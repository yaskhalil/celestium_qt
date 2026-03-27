import polars as pl
from datetime import datetime
import structlog
from typing import Optional

logger = structlog.get_logger()

class LiveBuffer:
    """
    The 'Heartbeat': Maintains a rolling 1,000-row Polars DataFrame of 1m bars.
    Provides the 15-minute context windows for Layer 1 (Hurst) and Layer 2 (XGBoost).
    """
    
    def __init__(self, max_rows: int = 1000):
        self.max_rows = max_rows
        self.schema = {
            "timestamp": pl.Datetime,
            "open": pl.Float64,
            "high": pl.Float64,
            "low": pl.Float64,
            "close": pl.Float64,
            "volume": pl.Int64
        }
        self.df = pl.DataFrame(schema=self.schema)

    def add_bar(self, timestamp: datetime, o: float, h: float, l: float, c: float, v: int):
        """Adds a new 1m bar and prunes the buffer to max_rows."""
        new_bar = pl.DataFrame({
            "timestamp": [timestamp],
            "open": [o],
            "high": [h],
            "low": [l],
            "close": [c],
            "volume": [v]
        }, schema=self.schema)
        
        self.df = pl.concat([self.df, new_bar])
        
        if len(self.df) > self.max_rows:
            self.df = self.df.tail(self.max_rows)

    def get_15m_context(self) -> Optional[pl.DataFrame]:
        """
        Resamples the 1m buffer into 15m OHLCV bars.
        Returns the latest context for inference.
        """
        if self.df.is_empty():
            return None
            
        return (
            self.df.sort("timestamp")
            .group_by_dynamic(
                "timestamp", 
                every="1m",    # 1m stride for sliding window
                period="15m",  # 15m lookback
            )
            .agg([
                pl.col("open").first(),
                pl.col("high").max(),
                pl.col("low").min(),
                pl.col("close").last(),
                pl.col("volume").sum()
            ])
            .tail(1) # Get only the most recent 15m window
        )

    def get_hurst_series(self, window: int = 100) -> Optional[pl.Series]:
        """Returns the closing price series for Hurst calculation."""
        if len(self.df) < window:
            return None
        return self.df.tail(window)["close"]

    @property
    def latest_bar(self) -> Optional[dict]:
        """Quick access to the last processed 1m bar."""
        if self.df.is_empty():
            return None
        return self.df.tail(1).to_dicts()[0]
