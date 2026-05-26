"""Breakouts signal: detect today's close crossing any technical level.

A **breakout** here means: yesterday's close was on one side of a level,
today's close is on the other side. The level can be horizontal S/R, a
trendline, or a moving average — the signal iterates over the unified
list[Level] from the levels package, so any future level type
(AVWAP, PDH/PDL, ...) is picked up automatically.

Bullish break ("broke_long") = a level that was resistance yesterday is
broken to the upside today. Bearish break ("broke_short") = a level that
was support yesterday is broken to the downside today.

Per-source flag columns are emitted alongside the composite so the user
can filter "horizontal breakouts only" or "trendline breakouts only".

Distance columns (`dist_to_resistance_atr`, `dist_to_support_atr`)
report how far the nearest unbroken level above/below current price is,
expressed in ATRs — gives the scanner context for follow-through room.
"""
from __future__ import annotations

import math

import pandas as pd

from ..indicators.atr import atr_latest
from ..levels import find_all_levels
from .base import Signal


_FLAG_COLS = (
    "broke_long",
    "broke_short",
    "broke_horizontal_long",
    "broke_horizontal_short",
    "broke_trendline_long",
    "broke_trendline_short",
    "broke_sma200_long",
    "broke_sma200_short",
)
_DISTANCE_COLS = (
    "nearest_resistance",
    "nearest_support",
    "dist_to_resistance_atr",
    "dist_to_support_atr",
)


class Breakouts(Signal):
    name = "breakouts"

    def __init__(
        self,
        sma_periods: tuple[int, ...] = (200,),
        atr_period: int = 20,
    ) -> None:
        self.sma_periods = tuple(int(p) for p in sma_periods)
        self.atr_period = int(atr_period)

    def compute(
        self,
        ticker: str,
        ohlcv: pd.DataFrame,
        market: pd.DataFrame | None = None,
        sector: pd.DataFrame | None = None,
    ) -> dict[str, float]:
        nan_out = self._nan_out()
        if ohlcv.empty or len(ohlcv) < 2:
            return nan_out

        today = len(ohlcv) - 1
        close_today = float(ohlcv["close"].iloc[today])
        close_yest = float(ohlcv["close"].iloc[today - 1])
        if pd.isna(close_today) or pd.isna(close_yest):
            return nan_out

        levels = find_all_levels(ohlcv, sma_periods=self.sma_periods)

        broke_long = 0
        broke_short = 0
        per_source_long: dict[str, int] = {}
        per_source_short: dict[str, int] = {}
        nearest_above = math.inf
        nearest_below = -math.inf

        for lv in levels:
            v_today = lv.value_at(today)
            v_yest = lv.value_at(today - 1)
            if math.isnan(v_today) or math.isnan(v_yest):
                continue

            if close_yest < v_yest and close_today > v_today:
                broke_long = 1
                per_source_long[lv.source] = 1
            elif close_yest > v_yest and close_today < v_today:
                broke_short = 1
                per_source_short[lv.source] = 1

            if v_today > close_today and v_today < nearest_above:
                nearest_above = v_today
            if v_today < close_today and v_today > nearest_below:
                nearest_below = v_today

        atr_val = atr_latest(
            ohlcv["high"], ohlcv["low"], ohlcv["close"], self.atr_period
        )

        nearest_resistance = nearest_above if nearest_above != math.inf else float("nan")
        nearest_support = nearest_below if nearest_below != -math.inf else float("nan")

        dist_to_res = float("nan")
        dist_to_sup = float("nan")
        if atr_val is not None and atr_val > 0:
            if not math.isnan(nearest_resistance):
                dist_to_res = (nearest_resistance - close_today) / atr_val
            if not math.isnan(nearest_support):
                dist_to_sup = (close_today - nearest_support) / atr_val

        # SMA-200 column uses the legacy short name; future SMAs would
        # need explicit columns added.
        return {
            "broke_long": float(broke_long),
            "broke_short": float(broke_short),
            "broke_horizontal_long": float(per_source_long.get("horizontal", 0)),
            "broke_horizontal_short": float(per_source_short.get("horizontal", 0)),
            "broke_trendline_long": float(per_source_long.get("trendline", 0)),
            "broke_trendline_short": float(per_source_short.get("trendline", 0)),
            "broke_sma200_long": float(per_source_long.get("sma_200", 0)),
            "broke_sma200_short": float(per_source_short.get("sma_200", 0)),
            "nearest_resistance": nearest_resistance,
            "nearest_support": nearest_support,
            "dist_to_resistance_atr": dist_to_res,
            "dist_to_support_atr": dist_to_sup,
        }

    @staticmethod
    def _nan_out() -> dict[str, float]:
        return {c: float("nan") for c in (*_FLAG_COLS, *_DISTANCE_COLS)}
