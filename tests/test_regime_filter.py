import polars as pl
from src.core.regime_filter import RegimeFilter
from src.config import settings


def _ctx(close: float = 105.0, sma_20: float = 100.0,
         hurst: float = 0.6, adx: float = 30.0) -> pl.DataFrame:
    return pl.DataFrame({
        "close": [close],
        "sma_20": [sma_20],
        "hurst": [hurst],
        "adx": [adx],
    })


def test_trending_all_conditions_met():
    assert RegimeFilter().is_trending(_ctx()) is True


def test_price_below_sma20_blocks():
    assert RegimeFilter().is_trending(_ctx(close=95.0, sma_20=100.0)) is False


def test_low_hurst_blocks():
    assert RegimeFilter().is_trending(_ctx(hurst=0.3)) is False


def test_low_adx_blocks():
    assert RegimeFilter().is_trending(_ctx(adx=15.0)) is False


def test_missing_columns_fail_closed():
    """Missing feature columns must NOT silently pass the gate."""
    df = pl.DataFrame({"close": [105.0]})  # no sma_20/hurst/adx
    assert RegimeFilter().is_trending(df) is False


def test_nan_features_fail_closed():
    """NaN features (e.g. degenerate ADX) must NOT fail open — NaN < threshold is False."""
    df = pl.DataFrame({
        "close": [105.0], "sma_20": [100.0],
        "hurst": [0.6], "adx": [float("nan")],
    })
    assert RegimeFilter().is_trending(df) is False


def test_empty_frame_fails_closed():
    assert RegimeFilter().is_trending(pl.DataFrame()) is False
    assert RegimeFilter().is_trending(None) is False


def test_thresholds_match_settings():
    """The gate must use the configured Hurst threshold, not a magic 0.5."""
    hurst_at_threshold = settings.HURST_THRESHOLD
    assert RegimeFilter().is_trending(_ctx(hurst=hurst_at_threshold)) is True
    assert RegimeFilter().is_trending(_ctx(hurst=hurst_at_threshold - 0.01)) is False
