"""Volume math: averages, ratios, dollar volume.

For daily bars only. Intraday RVol (interval-matched) would live in a
separate module if/when we add intraday data.
"""
from __future__ import annotations

import pandas as pd


def avg_volume(volume: pd.Series, period: int = 20) -> pd.Series:
    """Rolling mean of volume over `period` bars."""
    return volume.rolling(window=period, min_periods=period).mean()


def avg_volume_latest(volume: pd.Series, period: int = 20) -> float | None:
    if len(volume) < period:
        return None
    v = float(volume.tail(period).mean())
    return None if pd.isna(v) else v


def relative_volume(volume: pd.Series, period: int = 20) -> pd.Series:
    """Volume relative to its trailing average (today / avg_N). 1.0 = normal."""
    avg = avg_volume(volume, period)
    return volume / avg


def rvol_latest(volume: pd.Series, period: int = 20) -> float | None:
    """Most recent RVol value (today's volume / avg of prior `period` days).

    Uses prior `period` days as the baseline (excludes today) so RVol
    measures today's volume against a stable reference.
    """
    if len(volume) <= period:
        return None
    today = float(volume.iloc[-1])
    avg_prior = float(volume.iloc[-(period + 1):-1].mean())
    if pd.isna(today) or pd.isna(avg_prior) or avg_prior == 0:
        return None
    return today / avg_prior


def dollar_volume(close: pd.Series, volume: pd.Series, period: int = 20) -> pd.Series:
    """Rolling average of close * volume — dollar liquidity."""
    return (close * volume).rolling(window=period, min_periods=period).mean()


def dollar_volume_latest(
    close: pd.Series, volume: pd.Series, period: int = 20
) -> float | None:
    if len(close) < period or len(volume) < period:
        return None
    dv = (close.tail(period) * volume.tail(period)).mean()
    return None if pd.isna(dv) else float(dv)
