"""Minimum-last-close filter. Default $5 (author's recommendation, S4 L63)."""
from __future__ import annotations

import pandas as pd

from .base import Filter


class MinPriceFilter(Filter):
    name = "min_price"

    def __init__(self, threshold: float = 5.0) -> None:
        self.threshold = float(threshold)

    def passes(self, ohlcv: pd.DataFrame) -> bool:
        if ohlcv.empty:
            return False
        last_close = ohlcv["close"].iloc[-1]
        if pd.isna(last_close):
            return False
        return float(last_close) >= self.threshold
