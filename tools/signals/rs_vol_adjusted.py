"""Volatility-adjusted Relative Strength (Bruzzese-style RRS).

For each lookback window N:
    excess_return_N = stock_log_return_N - market_log_return_N
    excess_vol_N    = std(stock_log_returns - market_log_returns) over N days
    rrs_N           = excess_return_N / excess_vol_N

This penalises noisy outperformers. A stock that beats SPY by 10% with
high day-to-day chop scores lower than a stock that beats by 8% smoothly.

Output columns: rrs_<N>d for each window.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .base import Signal

DEFAULT_WINDOWS = (5, 21, 63)


def _log_returns(close: pd.Series) -> pd.Series:
    return np.log(close / close.shift(1))


class RSVolAdjusted(Signal):
    name = "rrs"

    def __init__(self, windows: tuple[int, ...] = DEFAULT_WINDOWS) -> None:
        self.windows = tuple(int(w) for w in windows)

    def compute(
        self,
        ticker: str,
        ohlcv: pd.DataFrame,
        market: pd.DataFrame | None = None,
        sector: pd.DataFrame | None = None,
    ) -> dict[str, float]:
        nan_out = {f"rrs_{w}d": float("nan") for w in self.windows}
        if market is None or market.empty or ohlcv.empty:
            return nan_out
        common = ohlcv.index.intersection(market.index)
        if len(common) <= max(self.windows):
            return nan_out
        s_close = ohlcv.loc[common, "close"]
        m_close = market.loc[common, "close"]
        s_ret = _log_returns(s_close)
        m_ret = _log_returns(m_close)
        excess_daily = (s_ret - m_ret).dropna()
        if excess_daily.empty:
            return nan_out
        out: dict[str, float] = {}
        for w in self.windows:
            if len(excess_daily) < w:
                out[f"rrs_{w}d"] = float("nan")
                continue
            window_excess = excess_daily.tail(w)
            excess_return = window_excess.sum()
            excess_vol = window_excess.std(ddof=1)
            if excess_vol is None or excess_vol == 0 or math.isnan(excess_vol):
                out[f"rrs_{w}d"] = float("nan")
            else:
                out[f"rrs_{w}d"] = float(excess_return / excess_vol)
        return out
