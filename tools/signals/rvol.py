"""Relative Volume (RVol) signal.

For each window N, RVol_N = today's volume / mean(prior N days' volume).
Values > 1 mean today traded heavier than the recent N-day average.

The baseline uses the prior N bars (excluding today) so RVol measures
today's tape against a stable reference window.

Output columns: rvol_<N>d for each window.
"""
from __future__ import annotations

import pandas as pd

from ..indicators.volume import rvol_latest
from .base import Signal

DEFAULT_WINDOWS = (5, 21)


class RVol(Signal):
    name = "rvol"

    def __init__(self, windows: tuple[int, ...] = DEFAULT_WINDOWS) -> None:
        self.windows = tuple(int(w) for w in windows)

    def compute(
        self,
        ticker: str,
        ohlcv: pd.DataFrame,
        market: pd.DataFrame | None = None,
        sector: pd.DataFrame | None = None,
    ) -> dict[str, float]:
        out: dict[str, float] = {}
        if ohlcv.empty or "volume" not in ohlcv.columns:
            return {f"rvol_{w}d": float("nan") for w in self.windows}
        vol = ohlcv["volume"]
        for w in self.windows:
            v = rvol_latest(vol, period=w)
            out[f"rvol_{w}d"] = float("nan") if v is None else float(v)
        return out
