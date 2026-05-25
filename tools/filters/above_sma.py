"""Last close above SMA(period) filter.

Use period = 20, 50, 100, or 200. Default OFF in the pipeline; opt-in
when you want bullish-bias-only results.
"""
from __future__ import annotations

import pandas as pd

from ..indicators.sma import sma_latest
from .base import Filter


class AboveSMAFilter(Filter):
    def __init__(self, period: int) -> None:
        self.period = int(period)
        self.name = f"above_sma_{period}"

    def passes(self, ohlcv: pd.DataFrame) -> bool:
        if ohlcv.empty or len(ohlcv) < self.period:
            return False
        last_close = ohlcv["close"].iloc[-1]
        if pd.isna(last_close):
            return False
        s = sma_latest(ohlcv["close"], self.period)
        if s is None:
            return False
        return float(last_close) > s
