"""Moving-average levels: dynamic S/R from an SMA series.

A moving average is a level that moves with each bar — `value_at(idx)`
returns the SMA value at that bar. Bars before the SMA has enough
history return NaN.

The 200-day SMA on the daily chart is the headline use case (the
"institutional line"). Other periods (50, 100) can be wrapped the same
way; each becomes its own level with `source = "sma_<period>"`.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..indicators.sma import sma
from .base import Level


@dataclass(frozen=True, eq=False)
class MovingAverageLevel(Level):
    series: pd.Series  # precomputed SMA, aligned to the OHLCV index
    period: int

    @property
    def source(self) -> str:
        return f"sma_{self.period}"

    def value_at(self, idx: int) -> float:
        if idx < 0 or idx >= len(self.series):
            return float("nan")
        v = self.series.iloc[idx]
        return float("nan") if pd.isna(v) else float(v)


def find_moving_average_level(
    ohlcv: pd.DataFrame,
    period: int,
) -> MovingAverageLevel | None:
    """Wrap an SMA(period) as a MovingAverageLevel.

    Returns None if there isn't enough history for a single SMA value.
    """
    if ohlcv.empty or len(ohlcv) < period:
        return None
    series = sma(ohlcv["close"], period)
    if series.isna().all():
        return None
    return MovingAverageLevel(series=series, period=int(period))
