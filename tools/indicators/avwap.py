"""Anchored Volume-Weighted Average Price (AVWAP).

AVWAP from an arbitrary anchor date = cumulative (typical_price × volume) /
cumulative volume, summed only over bars on/after the anchor.

typical_price = (high + low + close) / 3
"""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from .anchors import most_recent_triple_witching


def avwap(
    ohlcv: pd.DataFrame,
    anchor: date | datetime | pd.Timestamp,
) -> pd.Series:
    """AVWAP series from anchor onward; NaN before the anchor."""
    if isinstance(anchor, date) and not isinstance(anchor, datetime):
        anchor = datetime.combine(anchor, datetime.min.time())
    anchor_ts = pd.Timestamp(anchor)

    high = ohlcv["high"]
    low = ohlcv["low"]
    close = ohlcv["close"]
    volume = ohlcv["volume"]

    typical = (high + low + close) / 3.0
    pv = typical * volume

    mask = ohlcv.index >= anchor_ts
    cum_pv = pv.where(mask, 0).cumsum()
    cum_v = volume.where(mask, 0).cumsum()

    out = cum_pv / cum_v
    out = out.where(mask)
    return out


def avwap_latest(
    ohlcv: pd.DataFrame,
    anchor: date | datetime | pd.Timestamp,
) -> float | None:
    s = avwap(ohlcv, anchor)
    if s.empty or pd.isna(s.iloc[-1]):
        return None
    return float(s.iloc[-1])


def avwapq(ohlcv: pd.DataFrame, asof: date | None = None) -> pd.Series:
    """AVWAP anchored to the most recent Triple Witching on/before `asof`."""
    anchor = most_recent_triple_witching(asof)
    return avwap(ohlcv, anchor)


def avwapq_latest(ohlcv: pd.DataFrame, asof: date | None = None) -> float | None:
    s = avwapq(ohlcv, asof)
    if s.empty or pd.isna(s.iloc[-1]):
        return None
    return float(s.iloc[-1])
