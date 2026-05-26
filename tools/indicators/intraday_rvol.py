"""Interval-matched intraday relative volume.

A bar's RVol is its volume divided by the average volume at the same
time-of-day over the prior `lookback_sessions` sessions.

This is the "apples-to-apples" RVol the user's source emphasises: the
9:35 5-min bar gets compared to the average 9:35 5-min bar over the
last 20 sessions, NOT to a global average that would always make the
open look like an outlier.

Output is a float Series aligned to the input's index. Bars with fewer
than `min_history` prior sessions at that exact time get NaN.
"""
from __future__ import annotations

import pandas as pd


def intraday_rvol(
    ohlcv: pd.DataFrame,
    lookback_sessions: int = 20,
    min_history: int = 5,
) -> pd.Series:
    if ohlcv.empty or "volume" not in ohlcv.columns:
        return pd.Series(dtype=float)

    idx = ohlcv.index
    dates = pd.Index(idx.date)
    times = pd.Index(idx.time)

    df = pd.DataFrame(
        {"volume": ohlcv["volume"].to_numpy()},
        index=pd.MultiIndex.from_arrays([dates, times], names=["date", "time"]),
    )
    # date × time table of volumes. Missing combinations stay NaN.
    pivot = df["volume"].unstack(level="time").sort_index()

    # For each (date, time-of-day), baseline = rolling mean of prior
    # `lookback_sessions` rows in that column, excluding today (shift by 1).
    baseline = (
        pivot.shift(1)
        .rolling(window=lookback_sessions, min_periods=min_history)
        .mean()
    )

    # Map back from (date, time) → original DatetimeIndex.
    bl_lookup = baseline.stack(future_stack=True)  # MultiIndex (date, time) → baseline
    keys = list(zip(dates, times))
    bl_aligned = bl_lookup.reindex(keys).to_numpy()
    out_vals = ohlcv["volume"].to_numpy() / bl_aligned
    out = pd.Series(out_vals, index=idx, name="intraday_rvol")
    # Replace inf (baseline = 0) with NaN
    return out.where(~out.isin([float("inf"), float("-inf")]))
