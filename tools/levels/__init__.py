"""Levels package.

Public API:
  - `Level` — the ABC; every level type subclasses it.
  - `HorizontalLevel`, `TrendlineLevel`, `MovingAverageLevel` — subclasses.
  - `find_horizontal_levels`, `find_trendlines`, `find_moving_average_level`
    — detectors for each kind.
  - `find_all_levels` — aggregator that returns a unified list[Level].

Downstream code (notably the Breakouts signal) should depend on this
package, not on the individual files, so future level types
(AVWAP, prior-day extremes, round numbers, Fibonacci, ...) plug in
without touching every consumer.
"""
from __future__ import annotations

import pandas as pd

from .base import Level
from .horizontal import HorizontalLevel, find_horizontal_levels
from .moving_average import MovingAverageLevel, find_moving_average_level
from .trendline import TrendlineLevel, find_trendlines

__all__ = [
    "Level",
    "HorizontalLevel",
    "TrendlineLevel",
    "MovingAverageLevel",
    "find_horizontal_levels",
    "find_trendlines",
    "find_moving_average_level",
    "find_all_levels",
]


def find_all_levels(
    ohlcv: pd.DataFrame,
    sma_periods: tuple[int, ...] = (200,),
) -> list[Level]:
    """Return every level we can detect for this ticker.

    Order: horizontal first, then trendlines, then moving averages. The
    Breakouts signal doesn't depend on order, but stability is useful
    when debugging.
    """
    levels: list[Level] = []
    levels.extend(find_horizontal_levels(ohlcv))
    levels.extend(find_trendlines(ohlcv))
    for p in sma_periods:
        ma = find_moving_average_level(ohlcv, period=p)
        if ma is not None:
            levels.append(ma)
    return levels
