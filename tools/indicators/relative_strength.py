"""Relative-strength time series versus a market reference.

The scanner's RS signals are point-in-time lookback scores. This module
builds the chart indicator version: cumulative excess performance over
time, aligned against a reference such as SPY.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def rs_over_time(
    close: pd.Series,
    reference_close: pd.Series,
    *,
    percent: bool = True,
) -> pd.Series:
    """Return cumulative relative strength versus `reference_close`.

    The first common bar is normalized to 0. Subsequent values are:

        stock cumulative return - reference cumulative return

    expressed as percentage points by default. Positive values mean the
    stock outperformed the reference since the first aligned bar.
    """
    if close.empty or reference_close.empty:
        return pd.Series(dtype="float64", name="rs_vs_ref")

    stock = pd.to_numeric(close, errors="coerce").rename("stock")
    ref = pd.to_numeric(reference_close, errors="coerce").rename("reference")
    aligned = pd.concat([stock, ref], axis=1, join="inner").dropna()
    aligned = aligned[(aligned["stock"] > 0) & (aligned["reference"] > 0)]
    if aligned.empty:
        return pd.Series(dtype="float64", index=aligned.index, name="rs_vs_ref")

    stock_rel = aligned["stock"] / float(aligned["stock"].iloc[0])
    ref_rel = aligned["reference"] / float(aligned["reference"].iloc[0])
    rs = stock_rel / ref_rel - 1.0
    if percent:
        rs = rs * 100.0
    rs.name = "rs_vs_ref"
    return rs.replace([np.inf, -np.inf], np.nan)
