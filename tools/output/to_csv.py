"""CSV writer for the daily RS dashboard.

Writes a filtered-only CSV sorted by combined_rank descending.
Column order is fixed for stability across runs.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

COLUMN_ORDER = [
    "date", "ticker", "sector_etf", "last_price", "avg_vol_20d", "atr_pct_20d",
    "sma_20", "sma_50", "sma_100", "sma_200",
    "avwapq",
    "rs_simple_5d", "rs_simple_21d", "rs_simple_63d", "rs_simple_rank",
    "rrs_5d", "rrs_21d", "rrs_63d", "rrs_rank",
    "stock_vs_sector_rs", "stock_vs_sector_rank",
    "sector_vs_spy_rs", "sector_rank",
    "rvol_5d", "rvol_21d", "rvol_rank",
    "rrv_5d", "rrv_21d", "rrv_rank",
    "broke_long", "broke_short",
    "broke_horizontal_long", "broke_horizontal_short",
    "broke_trendline_long", "broke_trendline_short",
    "broke_sma200_long", "broke_sma200_short",
    "sma200_cross_up_age",
    "nearest_resistance", "nearest_support",
    "dist_to_resistance_atr", "dist_to_support_atr",
    "combined_rank",
]


def write_csv(
    df: pd.DataFrame,
    path: str | Path,
    sort_by: str = "combined_rank",
    ascending: bool = False,
) -> Path:
    """Write the dashboard DataFrame to CSV with stable column ordering."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    out = df.copy()
    if sort_by in out.columns:
        out = out.sort_values(by=sort_by, ascending=ascending, na_position="last")

    # Reorder columns: known ones first, rest at the end
    known = [c for c in COLUMN_ORDER if c in out.columns]
    extras = [c for c in out.columns if c not in COLUMN_ORDER]
    out = out[known + extras]

    out.to_csv(p, index=False, float_format="%.6g")
    return p
