"""Relative Relative-Volume (RRV) — market-adjusted RVol.

On heavy-tape days the whole market trades 1.5x average; a stock at
1.5x RVol is then unremarkable. RRV normalises this by dividing the
stock's RVol by the market's RVol on the same day:

    RRV_N = stock_rvol_N / market_rvol_N

>1 means the stock traded heavier than SPY for the day on a relative basis.

Output columns: rrv_<N>d for each window.
"""
from __future__ import annotations

import math

import pandas as pd

from ..indicators.volume import rvol_latest
from .base import Signal

DEFAULT_WINDOWS = (5, 21)


class RRV(Signal):
    name = "rrv"

    def __init__(self, windows: tuple[int, ...] = DEFAULT_WINDOWS) -> None:
        self.windows = tuple(int(w) for w in windows)

    def compute(
        self,
        ticker: str,
        ohlcv: pd.DataFrame,
        market: pd.DataFrame | None = None,
        sector: pd.DataFrame | None = None,
    ) -> dict[str, float]:
        nan_out = {f"rrv_{w}d": float("nan") for w in self.windows}
        if ohlcv.empty or market is None or market.empty:
            return nan_out
        if "volume" not in ohlcv.columns or "volume" not in market.columns:
            return nan_out

        # Align stock and market on shared dates so "today" is the same day.
        common = ohlcv.index.intersection(market.index)
        if len(common) == 0:
            return nan_out
        s_vol = ohlcv.loc[common, "volume"]
        m_vol = market.loc[common, "volume"]

        out: dict[str, float] = {}
        for w in self.windows:
            sv = rvol_latest(s_vol, period=w)
            mv = rvol_latest(m_vol, period=w)
            if sv is None or mv is None or mv == 0 or math.isnan(sv) or math.isnan(mv):
                out[f"rrv_{w}d"] = float("nan")
            else:
                out[f"rrv_{w}d"] = float(sv / mv)
        return out
