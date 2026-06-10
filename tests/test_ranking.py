"""Tests for tools/ranking/combine.py add_percentile_ranks."""
from __future__ import annotations

import numpy as np
import pandas as pd

from tools.ranking.combine import add_percentile_ranks


def scanner_rows() -> pd.DataFrame:
    """Five tickers with strictly increasing signal values (A worst, E best)."""
    tickers = ["A", "B", "C", "D", "E"]
    base = np.array([-0.10, -0.05, 0.0, 0.05, 0.10])
    df = pd.DataFrame({"ticker": tickers})
    for col in ("rs_simple_5d", "rs_simple_21d", "rs_simple_63d"):
        df[col] = base
    for col in ("rrs_5d", "rrs_21d", "rrs_63d"):
        df[col] = base * 10
    for col in ("rvol_5d", "rvol_21d"):
        df[col] = 1.0 + base
    for col in ("rrv_5d", "rrv_21d"):
        df[col] = 1.0 + base
    df["stock_vs_sector_rs"] = base
    df["sector_vs_spy_rs"] = base / 2
    return df


class TestAddPercentileRanks:
    def test_rank_columns_added(self) -> None:
        out = add_percentile_ranks(scanner_rows())
        for col in (
            "rs_simple_5d_pct",
            "rrs_21d_pct",
            "rvol_5d_pct",
            "rrv_21d_pct",
            "rs_simple_rank",
            "rrs_rank",
            "rvol_rank",
            "rrv_rank",
            "stock_vs_sector_rank",
            "sector_rank",
            "combined_rank",
        ):
            assert col in out.columns, f"missing {col}"

    def test_ranks_in_unit_interval(self) -> None:
        out = add_percentile_ranks(scanner_rows())
        rank_cols = [c for c in out.columns if c.endswith(("_pct", "_rank"))]
        for col in rank_cols:
            vals = out[col].dropna()
            assert ((vals > 0) & (vals <= 1)).all(), col

    def test_monotonic_with_signal(self) -> None:
        df = scanner_rows()  # rows already sorted worst -> best
        out = add_percentile_ranks(df)
        for col in ("rs_simple_5d_pct", "rrs_rank", "combined_rank"):
            assert out[col].is_monotonic_increasing, col
            assert out[col].is_unique, col
        # best ticker gets rank 1.0, worst gets 1/n
        assert out["combined_rank"].iloc[-1] == 1.0
        assert out["combined_rank"].iloc[0] == 1.0 / len(df)

    def test_nan_values_get_nan_rank(self) -> None:
        df = scanner_rows()
        df.loc[2, "rs_simple_5d"] = np.nan
        out = add_percentile_ranks(df)
        assert pd.isna(out.loc[2, "rs_simple_5d_pct"])
        # other rows still ranked
        assert out["rs_simple_5d_pct"].drop(index=2).notna().all()

    def test_input_not_mutated(self) -> None:
        df = scanner_rows()
        before = df.copy()
        add_percentile_ranks(df)
        pd.testing.assert_frame_equal(df, before)

    def test_missing_columns_tolerated(self) -> None:
        # Only RS columns present: no rrs/rvol/rrv ranks, but combined_rank
        # still computed from what exists.
        df = scanner_rows()[["ticker", "rs_simple_5d", "rs_simple_21d", "rs_simple_63d"]]
        out = add_percentile_ranks(df)
        assert "rs_simple_rank" in out.columns
        assert "rrs_rank" not in out.columns
        assert "rvol_rank" not in out.columns
        assert "combined_rank" in out.columns
