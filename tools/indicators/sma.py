"""Simple Moving Average."""
from __future__ import annotations

import pandas as pd


def sma(close: pd.Series, period: int) -> pd.Series:
    """Rolling mean of the close series. Requires at least `period` values
    before the first non-NaN result.
    """
    return close.rolling(window=period, min_periods=period).mean()


def sma_latest(close: pd.Series, period: int) -> float | None:
    """Return the most recent SMA value, or None if not enough history."""
    s = sma(close, period)
    if s.empty or pd.isna(s.iloc[-1]):
        return None
    return float(s.iloc[-1])
