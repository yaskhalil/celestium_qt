"""
Regime Filter — The trend-regime gate (Layer 1) that only allows entries during confirmed trends.

This gate validates three conditions:
1. Price above 20-bar SMA (uptrend)
2. Hurst exponent at or above threshold (persistent, non-random movement)
3. ADX above threshold (directional strength, not choppy)

When any feature is missing (e.g., insufficient bars) or is NaN (edge case), fails CLOSED
to prevent false signals from incomplete data.

Replaces the former Boolean State Space / STP framing (from cancer-cell modeling).
"""
import polars as pl
import math
from typing import Optional
import structlog
from src.config import settings

logger = structlog.get_logger()

def _valid(x: Optional[float]) -> bool:
    """True only for real finite numbers — None and NaN fail closed."""
    return x is not None and not (isinstance(x, float) and math.isnan(x))

class RegimeFilter:
    """
    Plain trend-regime gate. Reads real feature columns computed by
    add_regime_features() (sma_20, hurst, adx) from the latest bar and
    only allows entries when the market is in a confirmed trend.

    Replaces the former BooleanStateSpace/"attractor" gate: same intent
    (trend-aligned entries only), honest names, no discrete-state framing.
    """

    def is_trending(self, context: Optional[pl.DataFrame],
                    context_market: Optional[pl.DataFrame] = None) -> bool:
        """
        Returns True when the latest bar satisfies all trend conditions:
        - close above its 20-bar SMA (price in an uptrend)
        - Hurst exponent at or above the configured threshold (persistent trend)
        - ADX above the configured threshold (directional strength)

        When a feature column is missing (e.g. short context window), the
        gate fails CLOSED (returns False) — never silently passes.
        """
        if context is None or context.is_empty():
            return False

        row = context.tail(1).to_dicts()[0]

        close = row.get("close")
        sma_20 = row.get("sma_20")
        hurst = row.get("hurst")
        adx = row.get("adx")

        if not (_valid(close) and _valid(sma_20) and _valid(hurst) and _valid(adx)):
            logger.debug("RegimeFilter: feature columns missing or NaN, gate closed")
            return False
        # Narrow for the type checker (values already validated non-None above)
        assert close is not None and sma_20 is not None
        assert hurst is not None and adx is not None

        if close <= sma_20:
            logger.debug("RegimeFilter: price below SMA20", close=close, sma_20=sma_20)
            return False

        if hurst < settings.HURST_THRESHOLD:
            logger.debug("RegimeFilter: hurst below threshold",
                         hurst=hurst, threshold=settings.HURST_THRESHOLD)
            return False

        if adx < settings.ADX_THRESHOLD:
            logger.debug("RegimeFilter: adx below threshold",
                         adx=adx, threshold=settings.ADX_THRESHOLD)
            return False

        return True
