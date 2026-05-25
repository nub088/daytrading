"""Combine per-ticker signal scores into percentile ranks + a composite.

Input: DataFrame with one row per ticker, columns include raw signal scores
(rs_simple_5d, rs_simple_21d, ..., rrs_5d, ..., stock_vs_sector_rs, etc.).

Output: same DataFrame with added percentile-rank columns and a
combined_rank column.

Percentile rank: 0.0 = worst, 1.0 = best. NaN values get NaN rank
(they don't pollute the percentiles of the surviving universe).
"""
from __future__ import annotations

import pandas as pd

DEFAULT_RS_COLS = ("rs_simple_5d", "rs_simple_21d", "rs_simple_63d")
DEFAULT_RRS_COLS = ("rrs_5d", "rrs_21d", "rrs_63d")
DEFAULT_RVOL_COLS = ("rvol_5d", "rvol_21d")
DEFAULT_RRV_COLS = ("rrv_5d", "rrv_21d")


def _pct_rank(s: pd.Series) -> pd.Series:
    """Percentile rank, 0..1, NaNs preserved."""
    return s.rank(pct=True, na_option="keep")


def add_percentile_ranks(
    df: pd.DataFrame,
    rs_simple_cols: tuple[str, ...] = DEFAULT_RS_COLS,
    rrs_cols: tuple[str, ...] = DEFAULT_RRS_COLS,
    rvol_cols: tuple[str, ...] = DEFAULT_RVOL_COLS,
    rrv_cols: tuple[str, ...] = DEFAULT_RRV_COLS,
) -> pd.DataFrame:
    """Add per-signal percentile ranks + family summary ranks."""
    out = df.copy()

    # Per-column ranks (kept for transparency)
    for c in rs_simple_cols + rrs_cols + rvol_cols + rrv_cols:
        if c in out.columns:
            out[f"{c}_pct"] = _pct_rank(out[c])

    # Composite per-family rank = mean of available windows (then re-rank).
    rs_pct_cols = [f"{c}_pct" for c in rs_simple_cols if f"{c}_pct" in out.columns]
    if rs_pct_cols:
        out["rs_simple_rank"] = _pct_rank(out[rs_pct_cols].mean(axis=1))

    rrs_pct_cols = [f"{c}_pct" for c in rrs_cols if f"{c}_pct" in out.columns]
    if rrs_pct_cols:
        out["rrs_rank"] = _pct_rank(out[rrs_pct_cols].mean(axis=1))

    rvol_pct_cols = [f"{c}_pct" for c in rvol_cols if f"{c}_pct" in out.columns]
    if rvol_pct_cols:
        out["rvol_rank"] = _pct_rank(out[rvol_pct_cols].mean(axis=1))

    rrv_pct_cols = [f"{c}_pct" for c in rrv_cols if f"{c}_pct" in out.columns]
    if rrv_pct_cols:
        out["rrv_rank"] = _pct_rank(out[rrv_pct_cols].mean(axis=1))

    # Sector ranks
    if "stock_vs_sector_rs" in out.columns:
        out["stock_vs_sector_rank"] = _pct_rank(out["stock_vs_sector_rs"])
    if "sector_vs_spy_rs" in out.columns:
        out["sector_rank"] = _pct_rank(out["sector_vs_spy_rs"])

    # Combined rank = mean of price-RS family ranks (volume ranks are
    # contextual indicators, not direction signals, so they stay separate).
    parts = [c for c in ("rs_simple_rank", "rrs_rank", "stock_vs_sector_rank") if c in out.columns]
    if parts:
        out["combined_rank"] = _pct_rank(out[parts].mean(axis=1))

    return out
