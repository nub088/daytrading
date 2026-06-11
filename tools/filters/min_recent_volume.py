"""Minimum recent median daily volume filter.

This catches stale-volume false positives where one old event keeps the
20-day average high, but the current tape has gone thin.
"""
from __future__ import annotations

import pandas as pd

from .base import Filter


class MinRecentVolumeFilter(Filter):
    name = "min_recent_volume"

    def __init__(self, threshold: int = 500_000, period: int = 5) -> None:
        self.threshold = int(threshold)
        self.period = int(period)

    def passes(self, ohlcv: pd.DataFrame) -> bool:
        if ohlcv.empty or len(ohlcv) < self.period:
            return False
        recent_median = ohlcv["volume"].tail(self.period).median()
        if pd.isna(recent_median):
            return False
        return float(recent_median) >= self.threshold
