"""Horizontal levels: flat S/R zones from clustered swing pivots.

Detection algorithm:
  1. Find all swing highs and lows in a lookback window (default ~1y).
  2. Cluster pivot prices that fall within `cluster_atr * ATR(20)` of
     each other. ATR-relative width self-scales across tickers.
  3. Keep clusters with >= `min_touches` pivots.
  4. The level's price is the cluster centroid; strength is touch count
     weighted by recency (exponential decay).

A horizontal level's `value_at(idx)` is constant — flat by definition.
Whether it acts as resistance or support at any given bar is judged
relative to the close at that bar (see `Level.kind_at`).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from ..indicators.atr import atr_latest
from ..indicators.swings import find_swings
from .base import Level


@dataclass(frozen=True, eq=False)
class HorizontalLevel(Level):
    price: float           # cluster centroid
    touches: int           # number of pivots merged
    last_touch_idx: int    # most recent pivot bar
    first_touch_idx: int   # earliest pivot bar
    strength: float        # recency-weighted touch count
    high_touches: int      # swing highs in the cluster
    low_touches: int       # swing lows in the cluster

    @property
    def source(self) -> str:
        return "horizontal"

    def value_at(self, idx: int) -> float:
        return self.price

    @property
    def role(self) -> str:
        """Dominant pivot type: resistance, support, or mixed."""
        if self.high_touches > self.low_touches:
            return "resistance"
        if self.low_touches > self.high_touches:
            return "support"
        return "mixed"


def _recency_weight(touch_idx: int, today_idx: int, half_life: int) -> float:
    age = max(0, today_idx - touch_idx)
    return 0.5 ** (age / half_life)


def find_horizontal_levels(
    ohlcv: pd.DataFrame,
    lookback_bars: int = 250,
    swing_window: int = 5,
    cluster_atr: float = 0.5,
    min_touches: int = 2,
    atr_period: int = 20,
    recency_half_life: int = 60,
) -> list[HorizontalLevel]:
    """Detect horizontal S/R levels in the recent window."""
    if ohlcv.empty:
        return []
    n = len(ohlcv)
    if n < swing_window * 2 + 1:
        return []

    today_close = float(ohlcv["close"].iloc[-1])
    if pd.isna(today_close):
        return []

    atr_value = atr_latest(
        ohlcv["high"], ohlcv["low"], ohlcv["close"], period=atr_period
    )
    if atr_value is None or atr_value <= 0:
        return []
    cluster_width = cluster_atr * atr_value

    cutoff = max(0, n - lookback_bars)
    swings = [s for s in find_swings(ohlcv, lookback=swing_window) if s.idx >= cutoff]
    if not swings:
        return []

    swings_sorted = sorted(swings, key=lambda s: s.price)
    clusters: list[list] = [[swings_sorted[0]]]
    for s in swings_sorted[1:]:
        running_mean = sum(p.price for p in clusters[-1]) / len(clusters[-1])
        if s.price - running_mean <= cluster_width:
            clusters[-1].append(s)
        else:
            clusters.append([s])

    today_idx = n - 1
    levels: list[HorizontalLevel] = []
    for c in clusters:
        if len(c) < min_touches:
            continue
        price = sum(p.price for p in c) / len(c)
        last_idx = max(p.idx for p in c)
        first_idx = min(p.idx for p in c)
        high_touches = sum(1 for p in c if p.kind == "high")
        low_touches = sum(1 for p in c if p.kind == "low")
        weight = sum(
            _recency_weight(p.idx, today_idx, recency_half_life) for p in c
        )
        levels.append(
            HorizontalLevel(
                price=float(price),
                touches=len(c),
                last_touch_idx=int(last_idx),
                first_touch_idx=int(first_idx),
                strength=float(weight),
                high_touches=int(high_touches),
                low_touches=int(low_touches),
            )
        )
    levels.sort(key=lambda lv: abs(lv.price - today_close))
    return levels
