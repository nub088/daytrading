"""Last close above AVWAPQ filter.

AVWAPQ = Anchored VWAP from the most recent Triple Witching. Author treats
this as the first line of support in uptrends (S2 L22). Default OFF.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from ..indicators.avwap import avwapq_latest
from .base import Filter


class AboveAVWAPQFilter(Filter):
    name = "above_avwapq"

    def __init__(self, asof: date | None = None) -> None:
        self.asof = asof  # None → current date at apply time

    def passes(self, ohlcv: pd.DataFrame) -> bool:
        if ohlcv.empty:
            return False
        last_close = ohlcv["close"].iloc[-1]
        if pd.isna(last_close):
            return False
        v = avwapq_latest(ohlcv, asof=self.asof)
        if v is None:
            return False
        return float(last_close) > v
