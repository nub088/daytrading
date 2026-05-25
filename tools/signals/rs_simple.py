"""Simple Relative Strength vs a reference (default SPY).

For each lookback window N, RS_N = stock_return_N - market_return_N,
where returns are log returns over N trading days.

Positive RS = stock outperformed the market over the window.

Output columns: rs_simple_<N>d for each window.
"""
from __future__ import annotations

import math

import pandas as pd

from .base import Signal

DEFAULT_WINDOWS = (5, 21, 63)


def _log_return(close: pd.Series, window: int) -> float:
    if len(close) <= window:
        return float("nan")
    end = close.iloc[-1]
    start = close.iloc[-(window + 1)]
    if start <= 0 or end <= 0 or pd.isna(start) or pd.isna(end):
        return float("nan")
    return math.log(float(end) / float(start))


class RSSimple(Signal):
    name = "rs_simple"

    def __init__(self, windows: tuple[int, ...] = DEFAULT_WINDOWS) -> None:
        self.windows = tuple(int(w) for w in windows)

    def compute(
        self,
        ticker: str,
        ohlcv: pd.DataFrame,
        market: pd.DataFrame | None = None,
        sector: pd.DataFrame | None = None,
    ) -> dict[str, float]:
        if market is None or market.empty or ohlcv.empty:
            return {f"rs_simple_{w}d": float("nan") for w in self.windows}
        # Align on date intersection to keep windows honest.
        common = ohlcv.index.intersection(market.index)
        if len(common) <= max(self.windows):
            return {f"rs_simple_{w}d": float("nan") for w in self.windows}
        s_close = ohlcv.loc[common, "close"]
        m_close = market.loc[common, "close"]
        out: dict[str, float] = {}
        for w in self.windows:
            sr = _log_return(s_close, w)
            mr = _log_return(m_close, w)
            if math.isnan(sr) or math.isnan(mr):
                out[f"rs_simple_{w}d"] = float("nan")
            else:
                out[f"rs_simple_{w}d"] = sr - mr
        return out
