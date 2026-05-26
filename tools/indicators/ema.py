"""Exponential Moving Average."""
from __future__ import annotations

import pandas as pd


def ema(close: pd.Series, period: int) -> pd.Series:
    """EMA with the standard span = period convention (Welles Wilder uses
    a different alpha; this uses the more common chart-package default).
    `min_periods=period` so we don't return values until we have enough
    data to make the EMA meaningful.
    """
    return close.ewm(span=period, adjust=False, min_periods=period).mean()


def ema_latest(close: pd.Series, period: int) -> float | None:
    s = ema(close, period)
    if s.empty or pd.isna(s.iloc[-1]):
        return None
    return float(s.iloc[-1])
