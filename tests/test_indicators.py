"""Tests for tools/indicators: sma, ema, atr, avwap, swings."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from tools.indicators.atr import atr_pct_latest, true_range
from tools.indicators.avwap import avwap_latest, avwapq_latest
from tools.indicators.ema import ema, ema_latest
from tools.indicators.sma import sma, sma_latest
from tools.indicators.swings import find_swings, swing_highs, swing_lows

# An as-of date whose most recent triple witching (2026-03-20) falls
# inside the fixture calendar (2025-06-02 .. ~2026-05-29).
AVWAPQ_ASOF = date(2026, 4, 1)


class TestSMA:
    def test_constant_series(self, flat_ohlcv: pd.DataFrame) -> None:
        assert sma_latest(flat_ohlcv["close"], 20) == pytest.approx(100.0)

    def test_linear_series_hand_computed(self, uptrend_ohlcv: pd.DataFrame) -> None:
        # SMA of an arithmetic sequence = last - step * (period - 1) / 2
        close = uptrend_ohlcv["close"]
        expected = float(close.iloc[-1]) - 0.2 * (20 - 1) / 2
        assert sma_latest(close, 20) == pytest.approx(expected)

    def test_short_history_returns_none(self, short_ohlcv: pd.DataFrame) -> None:
        assert sma_latest(short_ohlcv["close"], 20) is None

    def test_series_nan_before_period(self, flat_ohlcv: pd.DataFrame) -> None:
        s = sma(flat_ohlcv["close"], 20)
        assert s.iloc[:19].isna().all()
        assert s.iloc[19:].notna().all()


class TestEMA:
    def test_constant_series(self, flat_ohlcv: pd.DataFrame) -> None:
        assert ema_latest(flat_ohlcv["close"], 21) == pytest.approx(100.0)

    def test_short_history_returns_none(self, short_ohlcv: pd.DataFrame) -> None:
        assert ema_latest(short_ohlcv["close"], 21) is None

    def test_ema_lags_uptrend_below_close(self, uptrend_ohlcv: pd.DataFrame) -> None:
        close = uptrend_ohlcv["close"]
        v = ema_latest(close, 21)
        assert v is not None
        assert v < float(close.iloc[-1])

    def test_min_periods_respected(self, flat_ohlcv: pd.DataFrame) -> None:
        s = ema(flat_ohlcv["close"], 21)
        assert s.iloc[:20].isna().all()
        assert not pd.isna(s.iloc[20])


class TestATR:
    def test_true_range_known_ranges(self, flat_ohlcv: pd.DataFrame) -> None:
        # flat: high 101, low 99, close 100 -> TR = 2 every bar
        tr = true_range(
            flat_ohlcv["high"], flat_ohlcv["low"], flat_ohlcv["close"]
        )
        assert (tr == 2.0).all()

    def test_atr_pct_of_constant_ranges(self, flat_ohlcv: pd.DataFrame) -> None:
        # ATR = 2 (Wilder smoothing of a constant), close = 100 -> 2.0%
        v = atr_pct_latest(
            flat_ohlcv["high"], flat_ohlcv["low"], flat_ohlcv["close"], period=20
        )
        assert v == pytest.approx(2.0)

    def test_short_history_returns_none(self, short_ohlcv: pd.DataFrame) -> None:
        v = atr_pct_latest(
            short_ohlcv["high"], short_ohlcv["low"], short_ohlcv["close"], period=20
        )
        assert v is None


class TestAVWAP:
    def test_flat_series_equals_price(self, flat_ohlcv: pd.DataFrame) -> None:
        # typical price = (101 + 99 + 100) / 3 = 100 on every bar
        anchor = flat_ohlcv.index[50]
        assert avwap_latest(flat_ohlcv, anchor) == pytest.approx(100.0)

    def test_avwapq_flat_series(self, flat_ohlcv: pd.DataFrame) -> None:
        assert avwapq_latest(flat_ohlcv, asof=AVWAPQ_ASOF) == pytest.approx(100.0)

    def test_avwapq_below_close_in_uptrend(self, uptrend_ohlcv: pd.DataFrame) -> None:
        v = avwapq_latest(uptrend_ohlcv, asof=AVWAPQ_ASOF)
        assert v is not None
        assert v < float(uptrend_ohlcv["close"].iloc[-1])

    def test_anchor_after_data_returns_none(self, flat_ohlcv: pd.DataFrame) -> None:
        anchor = flat_ohlcv.index[-1] + pd.Timedelta(days=30)
        assert avwap_latest(flat_ohlcv, anchor) is None


class TestSwings:
    def test_triangular_wave_pivots(self, breakout_ohlcv: pd.DataFrame) -> None:
        swings = find_swings(breakout_ohlcv, lookback=5)
        assert swings, "expected pivots in a triangular wave"
        highs = [s for s in swings if s.kind == "high"]
        lows = [s for s in swings if s.kind == "low"]
        assert highs and lows
        # every peak high is exactly 100.5, every trough low exactly 94.5
        assert all(s.price == pytest.approx(100.5) for s in highs)
        assert all(s.price == pytest.approx(94.5) for s in lows)
        # ordered by idx ascending
        idxs = [s.idx for s in swings]
        assert idxs == sorted(idxs)

    def test_last_lookback_bars_never_classified(
        self, breakout_ohlcv: pd.DataFrame
    ) -> None:
        n = len(breakout_ohlcv)
        swings = find_swings(breakout_ohlcv, lookback=5)
        assert all(s.idx < n - 5 for s in swings)

    def test_flat_series_has_no_pivots(self, flat_ohlcv: pd.DataFrame) -> None:
        # strict-max definition: ties never qualify
        assert find_swings(flat_ohlcv, lookback=5) == []

    def test_short_history_returns_empty(self, short_ohlcv: pd.DataFrame) -> None:
        assert find_swings(short_ohlcv.head(5), lookback=5) == []

    def test_helpers_filter_by_kind(self, breakout_ohlcv: pd.DataFrame) -> None:
        assert all(s.kind == "high" for s in swing_highs(breakout_ohlcv))
        assert all(s.kind == "low" for s in swing_lows(breakout_ohlcv))
