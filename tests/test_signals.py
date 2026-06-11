"""Tests for tools/signals: RSSimple, RSVolAdjusted, RSSector, RVol, RRV,
Breakouts."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from tools.signals.breakouts import Breakouts
from tools.signals.rrv import RRV
from tools.signals.rs_sector import RSSector
from tools.signals.rs_simple import RSSimple
from tools.signals.rs_vol_adjusted import RSVolAdjusted
from tools.signals.rvol import RVol

from conftest import N_BARS, make_ohlcv

RS_KEYS = ("rs_simple_5d", "rs_simple_21d", "rs_simple_63d")
RRS_KEYS = ("rrs_5d", "rrs_21d", "rrs_63d")
RVOL_KEYS = ("rvol_5d", "rvol_21d")
RRV_KEYS = ("rrv_5d", "rrv_21d")
BREAKOUT_KEYS = (
    "broke_long",
    "broke_short",
    "broke_horizontal_long",
    "broke_horizontal_short",
    "broke_trendline_long",
    "broke_trendline_short",
    "broke_sma200_long",
    "broke_sma200_short",
    "sma200_cross_up_age",
    "nearest_resistance",
    "nearest_support",
    "dist_to_resistance_atr",
    "dist_to_support_atr",
)


def assert_all_nan(out: dict[str, float], keys: tuple[str, ...]) -> None:
    assert set(out) == set(keys)
    assert all(math.isnan(out[k]) for k in keys)


class TestRSSimple:
    def test_outperformer_positive(
        self, uptrend_ohlcv: pd.DataFrame, flat_market: pd.DataFrame
    ) -> None:
        out = RSSimple().compute("UP", uptrend_ohlcv, market=flat_market)
        assert set(out) == set(RS_KEYS)
        assert all(out[k] > 0 for k in RS_KEYS)

    def test_underperformer_negative(
        self, downtrend_ohlcv: pd.DataFrame, flat_market: pd.DataFrame
    ) -> None:
        out = RSSimple().compute("DOWN", downtrend_ohlcv, market=flat_market)
        assert all(out[k] < 0 for k in RS_KEYS)

    def test_exact_value_vs_flat_market(
        self, uptrend_ohlcv: pd.DataFrame, flat_market: pd.DataFrame
    ) -> None:
        # flat market log-return = 0, so RS_5d = stock log-return over 5 bars
        close = uptrend_ohlcv["close"]
        expected = math.log(float(close.iloc[-1]) / float(close.iloc[-6]))
        out = RSSimple().compute("UP", uptrend_ohlcv, market=flat_market)
        assert out["rs_simple_5d"] == pytest.approx(expected)

    def test_no_market_all_nan(self, uptrend_ohlcv: pd.DataFrame) -> None:
        assert_all_nan(RSSimple().compute("UP", uptrend_ohlcv, market=None), RS_KEYS)

    def test_short_history_all_nan(
        self, short_ohlcv: pd.DataFrame, flat_market: pd.DataFrame
    ) -> None:
        # 10 common bars <= max window 63 -> ALL windows NaN (even 5d)
        out = RSSimple().compute("X", short_ohlcv, market=flat_market)
        assert_all_nan(out, RS_KEYS)


class TestRSVolAdjusted:
    def test_smooth_outperformer_positive(
        self, uptrend_ohlcv: pd.DataFrame, flat_market: pd.DataFrame
    ) -> None:
        out = RSVolAdjusted().compute("UP", uptrend_ohlcv, market=flat_market)
        assert set(out) == set(RRS_KEYS)
        assert all(out[k] > 0 for k in RRS_KEYS)

    def test_underperformer_negative(
        self, downtrend_ohlcv: pd.DataFrame, flat_market: pd.DataFrame
    ) -> None:
        out = RSVolAdjusted().compute("DOWN", downtrend_ohlcv, market=flat_market)
        assert all(out[k] < 0 for k in RRS_KEYS)

    def test_zero_excess_vol_is_nan(
        self, flat_ohlcv: pd.DataFrame, flat_market: pd.DataFrame
    ) -> None:
        # flat stock vs flat market: excess returns all zero -> std == 0 -> NaN
        out = RSVolAdjusted().compute("FLAT", flat_ohlcv, market=flat_market)
        assert_all_nan(out, RRS_KEYS)

    def test_no_market_all_nan(self, uptrend_ohlcv: pd.DataFrame) -> None:
        assert_all_nan(
            RSVolAdjusted().compute("UP", uptrend_ohlcv, market=None), RRS_KEYS
        )

    def test_short_history_all_nan(
        self, short_ohlcv: pd.DataFrame, flat_market: pd.DataFrame
    ) -> None:
        out = RSVolAdjusted().compute("X", short_ohlcv, market=flat_market)
        assert_all_nan(out, RRS_KEYS)


class TestRSSector:
    def test_stock_beats_flat_sector(
        self,
        uptrend_ohlcv: pd.DataFrame,
        flat_market: pd.DataFrame,
        flat_ohlcv: pd.DataFrame,
    ) -> None:
        out = RSSector().compute(
            "UP", uptrend_ohlcv, market=flat_market, sector=flat_ohlcv
        )
        assert set(out) == {"stock_vs_sector_rs", "sector_vs_spy_rs"}
        assert out["stock_vs_sector_rs"] > 0
        # flat sector vs flat SPY -> exactly 0
        assert out["sector_vs_spy_rs"] == pytest.approx(0.0)

    def test_sector_beats_spy(
        self,
        flat_ohlcv: pd.DataFrame,
        flat_market: pd.DataFrame,
        uptrend_ohlcv: pd.DataFrame,
    ) -> None:
        out = RSSector().compute(
            "X", flat_ohlcv, market=flat_market, sector=uptrend_ohlcv
        )
        assert out["sector_vs_spy_rs"] > 0
        assert out["stock_vs_sector_rs"] < 0

    def test_no_sector_all_nan(
        self, uptrend_ohlcv: pd.DataFrame, flat_market: pd.DataFrame
    ) -> None:
        out = RSSector().compute("UP", uptrend_ohlcv, market=flat_market, sector=None)
        assert math.isnan(out["stock_vs_sector_rs"])
        assert math.isnan(out["sector_vs_spy_rs"])

    def test_no_market_all_nan(
        self, uptrend_ohlcv: pd.DataFrame, flat_ohlcv: pd.DataFrame
    ) -> None:
        out = RSSector().compute("UP", uptrend_ohlcv, market=None, sector=flat_ohlcv)
        assert math.isnan(out["stock_vs_sector_rs"])
        assert math.isnan(out["sector_vs_spy_rs"])


class TestRVol:
    def test_constant_volume_is_one(self, flat_ohlcv: pd.DataFrame) -> None:
        out = RVol().compute("FLAT", flat_ohlcv)
        assert set(out) == set(RVOL_KEYS)
        assert all(out[k] == pytest.approx(1.0) for k in RVOL_KEYS)

    def test_volume_spike(self) -> None:
        vol = np.full(N_BARS, 1_000_000.0)
        vol[-1] = 3_000_000.0  # today trades 3x the prior baseline
        df = make_ohlcv(np.full(N_BARS, 100.0), volume=vol)
        out = RVol().compute("SPIKE", df)
        assert out["rvol_5d"] == pytest.approx(3.0)
        assert out["rvol_21d"] == pytest.approx(3.0)

    def test_short_history_nan(self) -> None:
        df = make_ohlcv(np.full(10, 100.0))  # 10 bars < 21-day baseline
        out = RVol().compute("X", df)
        assert out["rvol_5d"] == pytest.approx(1.0)  # 5d baseline still works
        assert math.isnan(out["rvol_21d"])

    def test_empty_frame_all_nan(self) -> None:
        assert_all_nan(RVol().compute("X", pd.DataFrame()), RVOL_KEYS)


class TestRRV:
    def test_stock_heavier_than_market(self, flat_market: pd.DataFrame) -> None:
        vol = np.full(N_BARS, 1_000_000.0)
        vol[-1] = 2_000_000.0
        df = make_ohlcv(np.full(N_BARS, 100.0), volume=vol)
        out = RRV().compute("HOT", df, market=flat_market)
        assert set(out) == set(RRV_KEYS)
        # stock rvol = 2.0, market rvol = 1.0 -> rrv = 2.0
        assert out["rrv_5d"] == pytest.approx(2.0)
        assert out["rrv_21d"] == pytest.approx(2.0)

    def test_equal_tape_is_one(
        self, flat_ohlcv: pd.DataFrame, flat_market: pd.DataFrame
    ) -> None:
        out = RRV().compute("X", flat_ohlcv, market=flat_market)
        assert all(out[k] == pytest.approx(1.0) for k in RRV_KEYS)

    def test_no_market_all_nan(self, flat_ohlcv: pd.DataFrame) -> None:
        assert_all_nan(RRV().compute("X", flat_ohlcv, market=None), RRV_KEYS)

    def test_short_history(self, flat_market: pd.DataFrame) -> None:
        df = make_ohlcv(np.full(10, 100.0))
        out = RRV().compute("X", df, market=flat_market)
        assert out["rrv_5d"] == pytest.approx(1.0)
        assert math.isnan(out["rrv_21d"])


class TestBreakouts:
    def test_output_keys(self, breakout_ohlcv: pd.DataFrame) -> None:
        out = Breakouts().compute("BRK", breakout_ohlcv)
        assert set(out) == set(BREAKOUT_KEYS)
        assert all(isinstance(v, float) for v in out.values())

    def test_horizontal_breakout_detected(self, breakout_ohlcv: pd.DataFrame) -> None:
        # yesterday 99.5 < resistance ~100.5 < today 104.0
        out = Breakouts().compute("BRK", breakout_ohlcv)
        assert out["broke_long"] == 1.0
        assert out["broke_horizontal_long"] == 1.0
        assert out["broke_short"] == 0.0
        assert out["broke_horizontal_short"] == 0.0

    def test_crossing_support_up_is_not_long_breakout(self) -> None:
        phase = np.arange(N_BARS) % 20
        close = np.where(phase <= 10, 100.0 - 0.5 * phase, 100.0 - 0.5 * (20 - phase))
        close = close.astype(float)
        close[-2] = 94.5   # below the repeated swing-low support cluster
        close[-1] = 95.4   # back above support, but not a resistance breakout
        out = Breakouts().compute("SUPPORT_RECLAIM", make_ohlcv(close, spread=1.0))
        assert out["broke_long"] == 0.0
        assert out["broke_horizontal_long"] == 0.0

    def test_no_breakout_in_flat_series(self, flat_ohlcv: pd.DataFrame) -> None:
        out = Breakouts().compute("FLAT", flat_ohlcv)
        assert out["broke_long"] == 0.0
        assert out["broke_short"] == 0.0

    def test_support_below_close_after_breakout(
        self, breakout_ohlcv: pd.DataFrame
    ) -> None:
        out = Breakouts().compute("BRK", breakout_ohlcv)
        close = float(breakout_ohlcv["close"].iloc[-1])
        if not math.isnan(out["nearest_support"]):
            assert out["nearest_support"] < close
            assert out["dist_to_support_atr"] > 0
        if not math.isnan(out["nearest_resistance"]):
            assert out["nearest_resistance"] > close
            assert out["dist_to_resistance_atr"] > 0

    def test_short_history_all_nan(self) -> None:
        df = make_ohlcv(np.full(1, 100.0))
        out = Breakouts().compute("X", df)
        assert_all_nan(out, BREAKOUT_KEYS)

    def test_empty_frame_all_nan(self) -> None:
        assert_all_nan(Breakouts().compute("X", pd.DataFrame()), BREAKOUT_KEYS)
