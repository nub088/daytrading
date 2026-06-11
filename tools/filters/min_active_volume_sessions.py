"""Minimum count of recently active volume sessions.

Average and median volume filters can still pass names whose liquidity is
concentrated in a few event spikes. This filter requires a minimum number
of recent sessions to clear a per-session volume floor.
"""
from __future__ import annotations

import pandas as pd

from .base import Filter


class MinActiveVolumeSessionsFilter(Filter):
    name = "min_active_volume_sessions"

    def __init__(
        self,
        volume_floor: int = 100_000,
        period: int = 10,
        min_sessions: int = 8,
    ) -> None:
        self.volume_floor = int(volume_floor)
        self.period = int(period)
        self.min_sessions = int(min_sessions)

    def passes(self, ohlcv: pd.DataFrame) -> bool:
        if ohlcv.empty or len(ohlcv) < self.period:
            return False
        recent = pd.to_numeric(ohlcv["volume"].tail(self.period), errors="coerce")
        if recent.isna().any():
            return False
        active_sessions = int((recent >= self.volume_floor).sum())
        return active_sessions >= self.min_sessions
