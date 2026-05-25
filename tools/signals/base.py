"""Signal base class.

A Signal computes one or more named numeric scores for a single ticker,
optionally using a market reference (SPY) and sector reference (sector ETF).

Each signal returns a dict[str, float] of score_name -> value.
The Ranking layer percentile-ranks these across the universe.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class Signal(ABC):
    name: str = "signal"

    @abstractmethod
    def compute(
        self,
        ticker: str,
        ohlcv: pd.DataFrame,
        market: pd.DataFrame | None = None,
        sector: pd.DataFrame | None = None,
    ) -> dict[str, float]:
        """Return named scores. Missing/invalid values may be NaN."""

    def __repr__(self) -> str:
        attrs = ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items())
        return f"{type(self).__name__}({attrs})"
