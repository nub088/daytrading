"""Fractal-style swing pivot detection on daily bars.

A bar at index i is a **swing high** if its high is the strict maximum of
the window [i-lookback, i+lookback]. Symmetric definition for swing lows.

This is the textbook Williams Fractal with a configurable wing size. It's
intentionally simple: 100% deterministic, no smoothing, no thresholds.
Filtering (proximity, age, prominence) happens in the consumer modules
(levels.py, trendlines.py).

The last `lookback` bars cannot be classified — they need future bars to
confirm. That's expected: today's bar is never a confirmed swing.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Swing:
    idx: int      # positional index into the OHLCV frame (0-based)
    price: float  # high (for kind='high') or low (for kind='low')
    kind: str     # 'high' or 'low'


def find_swings(ohlcv: pd.DataFrame, lookback: int = 5) -> list[Swing]:
    """Find all confirmed swing highs and lows.

    Returns a list of Swing objects ordered by idx ascending. A bar must
    have `lookback` bars on either side to qualify, so the most recent
    `lookback` bars are never returned.
    """
    if ohlcv.empty or len(ohlcv) < 2 * lookback + 1:
        return []
    highs = ohlcv["high"].to_numpy()
    lows = ohlcv["low"].to_numpy()
    n = len(highs)
    out: list[Swing] = []
    for i in range(lookback, n - lookback):
        window_h = highs[i - lookback : i + lookback + 1]
        if highs[i] == window_h.max() and (window_h == highs[i]).sum() == 1:
            out.append(Swing(idx=i, price=float(highs[i]), kind="high"))
            continue  # a bar can't be both high and low pivot
        window_l = lows[i - lookback : i + lookback + 1]
        if lows[i] == window_l.min() and (window_l == lows[i]).sum() == 1:
            out.append(Swing(idx=i, price=float(lows[i]), kind="low"))
    return out


def swing_highs(ohlcv: pd.DataFrame, lookback: int = 5) -> list[Swing]:
    return [s for s in find_swings(ohlcv, lookback) if s.kind == "high"]


def swing_lows(ohlcv: pd.DataFrame, lookback: int = 5) -> list[Swing]:
    return [s for s in find_swings(ohlcv, lookback) if s.kind == "low"]
