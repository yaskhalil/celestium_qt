import polars as pl
import structlog
from src.data.duck_storage import DuckDBStorage
from src.features.regime import add_regime_features
from typing import Optional

logger = structlog.get_logger()

class DuckDBBuffer:
    """
    DuckDB Buffer: Queries DuckDB for historical OHLCV data and enriches it
    with statistical context features (Hurst, ADX, ATR, SMA20) before it is
    consumed by the strategy and Oracle layers.

    Feature enrichment here is the single source of truth for the live path —
    without it, gates that read 'hurst'/'adx'/'atr' silently fall back to
    defaults and become no-ops.
    """

    def __init__(self):
        self.storage = DuckDBStorage()

    def get_context(self, symbol: str, window: int = 150,
                    with_features: bool = True) -> pl.DataFrame:
        """
        Query DuckDB for the last N bars for the given symbol.

        When with_features=True (default), the frame is enriched with
        add_regime_features() so downstream consumers see real feature columns.
        Short windows (e.g. 5-bar monitor ticks) skip enrichment: the rolling
        windows need history and the monitor path only reads 'close'.
        """
        df = self.storage.fetch_ohlcv(symbol, limit=window)

        if with_features and window >= 110 and not df.is_empty():
            try:
                df = add_regime_features(df)
            except Exception as e:
                logger.warning("DuckDBBuffer: feature enrichment failed, returning raw",
                               symbol=symbol, error=str(e))

        return df
