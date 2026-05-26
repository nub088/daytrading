"""The Level abstraction.

A **Level** is any reference price that price action might react to:
a horizontal S/R zone, a slanted trendline, a moving average, an
anchored VWAP, a prior-day high — anything you'd draw on a chart and
expect to matter.

All subclasses expose the same minimal interface so downstream code
(notably the Breakouts signal) can iterate over a heterogeneous list
without caring what kind of level each entry is:

    for lv in levels:
        v_today = lv.value_at(today_idx)
        v_yest  = lv.value_at(today_idx - 1)
        if close_yest < v_yest and close_today > v_today:
            # bullish break of a level — its source tells us which kind

Subclasses store their own parameters (price, slope+intercept, SMA series,
...) and implement `value_at` to project the level onto any bar index.

`source` is the short tag used for CSV column suffixes and filtering.
Each subclass declares its own (e.g. "horizontal", "trendline", "sma_200").
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import math


class Level(ABC):
    """Reference price that price action might react to."""

    @property
    @abstractmethod
    def source(self) -> str:
        """Short tag identifying the kind of level (used in column names)."""

    @abstractmethod
    def value_at(self, idx: int) -> float:
        """Level's price at positional bar index `idx`.

        Returns NaN if the level isn't defined at that bar (e.g. SMA(200)
        before bar 200, or a trendline before its first anchor).
        """

    def kind_at(self, idx: int, ref_price: float) -> str:
        """'resistance' if the level is above ref_price at this bar,
        'support' if below, 'unknown' if undefined.
        """
        v = self.value_at(idx)
        if math.isnan(v):
            return "unknown"
        return "resistance" if v >= ref_price else "support"

    def __repr__(self) -> str:
        return f"{type(self).__name__}(source={self.source!r})"
