"""Sector-level RS pieces.

Two scores per ticker:
  - stock_vs_sector_rs: stock log-return minus its sector ETF log-return.
  - sector_vs_spy_rs:   sector ETF log-return minus SPY log-return.

Default window: 21 trading days (~1 month). Configurable.
"""
from __future__ import annotations

import math

import pandas as pd

from .base import Signal
from .rs_simple import _log_return


class RSSector(Signal):
    name = "rs_sector"

    def __init__(self, window: int = 21) -> None:
        self.window = int(window)

    def compute(
        self,
        ticker: str,
        ohlcv: pd.DataFrame,
        market: pd.DataFrame | None = None,
        sector: pd.DataFrame | None = None,
    ) -> dict[str, float]:
        out = {
            "stock_vs_sector_rs": float("nan"),
            "sector_vs_spy_rs": float("nan"),
        }
        if ohlcv.empty or market is None or market.empty:
            return out

        # stock vs sector
        if sector is not None and not sector.empty:
            common_ss = ohlcv.index.intersection(sector.index)
            if len(common_ss) > self.window:
                sr = _log_return(ohlcv.loc[common_ss, "close"], self.window)
                secr = _log_return(sector.loc[common_ss, "close"], self.window)
                if not (math.isnan(sr) or math.isnan(secr)):
                    out["stock_vs_sector_rs"] = sr - secr

        # sector vs SPY
        ref_for_sec = sector if (sector is not None and not sector.empty) else None
        if ref_for_sec is not None:
            common_sm = ref_for_sec.index.intersection(market.index)
            if len(common_sm) > self.window:
                secr = _log_return(ref_for_sec.loc[common_sm, "close"], self.window)
                mr = _log_return(market.loc[common_sm, "close"], self.window)
                if not (math.isnan(secr) or math.isnan(mr)):
                    out["sector_vs_spy_rs"] = secr - mr
        return out
