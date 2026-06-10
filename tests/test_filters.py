"""Tests for tools/filters: MinPrice, MinVolume, AboveSMA, AboveAVWAPQ, And."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from tools.filters.above_avwapq import AboveAVWAPQFilter
from tools.filters.above_sma import AboveSMAFilter
from tools.filters.compose import AndFilter
from tools.filters.min_price import MinPriceFilter
from tools.filters.min_volume import MinVolumeFilter

from conftest import N_BARS, make_ohlcv

AVWAPQ_ASOF = date(2026, 4, 1)


class TestMinPriceFilter:
    def test_passes_above_threshold(self, flat_ohlcv: pd.DataFrame) -> None:
        assert MinPriceFilter(threshold=5.0).passes(flat_ohlcv)

    def test_fails_below_threshold(self, flat_ohlcv: pd.DataFrame) -> None:
        assert not MinPriceFilter(threshold=500.0).passes(flat_ohlcv)

    def test_threshold_is_inclusive(self, flat_ohlcv: pd.DataFrame) -> None:
        assert MinPriceFilter(threshold=100.0).passes(flat_ohlcv)

    def test_empty_frame_fails(self) -> None:
        assert not MinPriceFilter().passes(pd.DataFrame())

    def test_nan_last_close_fails(self, flat_ohlcv: pd.DataFrame) -> None:
        df = flat_ohlcv.copy()
        df.iloc[-1, df.columns.get_loc("close")] = float("nan")
        assert not MinPriceFilter().passes(df)


class TestMinVolumeFilter:
    def test_passes_high_volume(self, flat_ohlcv: pd.DataFrame) -> None:
        # fixture volume = 1.5M constant
        assert MinVolumeFilter(threshold=1_000_000, period=20).passes(flat_ohlcv)

    def test_fails_low_volume(self, flat_ohlcv: pd.DataFrame) -> None:
        assert not MinVolumeFilter(threshold=2_000_000, period=20).passes(flat_ohlcv)

    def test_short_history_fails(self, short_ohlcv: pd.DataFrame) -> None:
        assert not MinVolumeFilter(threshold=1, period=20).passes(short_ohlcv)

    def test_empty_frame_fails(self) -> None:
        assert not MinVolumeFilter().passes(pd.DataFrame())


class TestAboveSMAFilter:
    def test_uptrend_above_sma(self, uptrend_ohlcv: pd.DataFrame) -> None:
        assert AboveSMAFilter(50).passes(uptrend_ohlcv)

    def test_downtrend_below_sma(self, downtrend_ohlcv: pd.DataFrame) -> None:
        assert not AboveSMAFilter(50).passes(downtrend_ohlcv)

    def test_flat_equal_to_sma_fails(self, flat_ohlcv: pd.DataFrame) -> None:
        # strict > comparison: close == SMA does not pass
        assert not AboveSMAFilter(20).passes(flat_ohlcv)

    def test_short_history_fails(self, short_ohlcv: pd.DataFrame) -> None:
        assert not AboveSMAFilter(20).passes(short_ohlcv)

    def test_name_includes_period(self) -> None:
        assert AboveSMAFilter(200).name == "above_sma_200"


class TestAboveAVWAPQFilter:
    def test_uptrend_passes(self, uptrend_ohlcv: pd.DataFrame) -> None:
        assert AboveAVWAPQFilter(asof=AVWAPQ_ASOF).passes(uptrend_ohlcv)

    def test_downtrend_fails(self, downtrend_ohlcv: pd.DataFrame) -> None:
        assert not AboveAVWAPQFilter(asof=AVWAPQ_ASOF).passes(downtrend_ohlcv)

    def test_flat_equal_to_avwap_fails(self, flat_ohlcv: pd.DataFrame) -> None:
        # strict > comparison: close == AVWAPQ does not pass
        assert not AboveAVWAPQFilter(asof=AVWAPQ_ASOF).passes(flat_ohlcv)

    def test_anchor_outside_history_fails(self, flat_ohlcv: pd.DataFrame) -> None:
        # most recent triple witching before 2010-01-04 is 2009-12-18,
        # which predates the fixture data -> avwapq_latest is None -> fail
        assert not AboveAVWAPQFilter(asof=date(2010, 1, 4)).passes(flat_ohlcv)

    def test_empty_frame_fails(self) -> None:
        assert not AboveAVWAPQFilter(asof=AVWAPQ_ASOF).passes(pd.DataFrame())


class TestAndFilter:
    def test_all_pass(self, uptrend_ohlcv: pd.DataFrame) -> None:
        f = AndFilter([MinPriceFilter(5.0), MinVolumeFilter(1_000_000), AboveSMAFilter(50)])
        assert f.passes(uptrend_ohlcv)

    def test_one_fails(self, uptrend_ohlcv: pd.DataFrame) -> None:
        f = AndFilter([MinPriceFilter(5.0), MinPriceFilter(1_000_000.0)])
        assert not f.passes(uptrend_ohlcv)

    def test_empty_filter_list_passes(self, flat_ohlcv: pd.DataFrame) -> None:
        assert AndFilter([]).passes(flat_ohlcv)

    def test_explain_reports_each_filter(self, uptrend_ohlcv: pd.DataFrame) -> None:
        f = AndFilter([MinPriceFilter(5.0), AboveSMAFilter(50), MinVolumeFilter(10**9)])
        result = f.explain(uptrend_ohlcv)
        assert result == {
            "min_price": True,
            "above_sma_50": True,
            "min_volume": False,
        }

    def test_low_priced_thin_stock_rejected(self) -> None:
        df = make_ohlcv(np.full(N_BARS, 2.0), volume=50_000, spread=0.1)
        f = AndFilter([MinPriceFilter(5.0), MinVolumeFilter(1_000_000)])
        assert not f.passes(df)
        assert f.explain(df) == {"min_price": False, "min_volume": False}
