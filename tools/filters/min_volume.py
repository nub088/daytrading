"""Minimum-N-day average volume filter.

Default: 20-day avg volume >= 1,000,000 shares (author S4 L63 / S6 L82).
"""
from __future__ import annotations

import pandas as pd

from .base import Filter


class MinVolumeFilter(Filter):
    name = "min_volume"

    def __init__(self, threshold: int = 1_000_000, period: int = 20) -> None:
        self.threshold = int(threshold)
        self.period = int(period)

    def passes(self, ohlcv: pd.DataFrame) -> bool:
        if ohlcv.empty or len(ohlcv) < self.period:
            return False
        avg_vol = ohlcv["volume"].tail(self.period).mean()
        if pd.isna(avg_vol):
            return False
        return float(avg_vol) >= self.threshold
