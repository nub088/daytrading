"""Average True Range (Wilder) and ATR %."""
from __future__ import annotations

import pandas as pd


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """True Range = max(high-low, |high-prev_close|, |low-prev_close|)."""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    return pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)


def atr(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20
) -> pd.Series:
    """Wilder's smoothing of True Range."""
    tr = true_range(high, low, close)
    # Wilder smoothing == EMA with alpha = 1/period
    return tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def atr_pct(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20
) -> pd.Series:
    """ATR expressed as percentage of close."""
    a = atr(high, low, close, period=period)
    return 100.0 * a / close


def atr_pct_latest(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20
) -> float | None:
    s = atr_pct(high, low, close, period=period)
    if s.empty or pd.isna(s.iloc[-1]):
        return None
    return float(s.iloc[-1])
