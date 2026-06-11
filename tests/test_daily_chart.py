from __future__ import annotations

import pandas as pd
from unittest.mock import patch

from gui.charts.daily import (
    _active_horizontal_levels,
    _level_line_start,
    build_daily_figure,
)
from tools.alerts import PriceAlert
from tools.levels import HorizontalLevel


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [8.0, 8.2, 9.6, 10.2, 11.1, 11.3],
            "high": [9.0, 9.2, 10.4, 10.8, 12.0, 12.2],
            "low": [7.5, 7.8, 9.4, 9.8, 10.8, 11.0],
            "close": [8.5, 8.7, 10.1, 10.4, 11.5, 11.7],
            "volume": [1000, 1000, 1000, 1000, 1000, 1000],
        },
        index=pd.bdate_range("2026-01-05", periods=6),
    )


def _level(price: float = 10.0, first_touch_idx: int = 0) -> HorizontalLevel:
    return HorizontalLevel(
        price=price,
        touches=2,
        last_touch_idx=3,
        first_touch_idx=first_touch_idx,
        strength=1.0,
        high_touches=2,
        low_touches=0,
    )


def test_level_line_starts_after_last_blocking_candle() -> None:
    df = _frame()
    # 10.0 sits inside bars 2 and 3 (9.4-10.4 and 9.8-10.8); bars 4-5 are clear.
    assert _level_line_start(df, df, _level(10.0)) == df.index[4]


def test_level_line_start_is_none_when_latest_bar_trades_through_level() -> None:
    df = _frame()
    # 11.5 is inside the last bar's 11.0-12.2 range: no clean run exists.
    assert _level_line_start(df, df, _level(11.5)) is None


def test_level_line_starts_at_first_touch_when_never_blocked() -> None:
    df = _frame()
    assert _level_line_start(df, df, _level(13.0)) == df.index[0]
    assert _level_line_start(df, df, _level(13.0, first_touch_idx=2)) == df.index[2]


def test_level_line_clearance_buffer_blocks_near_misses() -> None:
    df = _frame()
    # 10.75 misses bar 4's low (10.8) by 0.05: clear without a buffer,
    # blocked once the clearance covers the near-miss.
    assert _level_line_start(df, df, _level(10.75), clearance=0.0) == df.index[4]
    assert _level_line_start(df, df, _level(10.75), clearance=0.1) == df.index[5]


def test_level_shapes_never_overlap_blocking_candles() -> None:
    df = _frame()
    levels = [_level(10.0)]

    with patch("gui.charts.daily.find_all_levels", return_value=levels):
        fig = build_daily_figure("TEST", df, last_n_bars=6, template="plotly")

    level_shapes = [s for s in fig.layout.shapes if s.yref == "y" and s.y0 == 10.0]
    assert len(level_shapes) == 1
    # Starts after the last candle that traded through the level and
    # extends past the latest bar into right-edge whitespace.
    assert pd.Timestamp(level_shapes[0].x0) == df.index[4]
    assert pd.Timestamp(level_shapes[0].x1) > df.index[-1]


def test_daily_chart_adds_rs_vs_spy_trace_when_market_data_present() -> None:
    df = _frame()
    spy = df.copy()
    spy["close"] = [8.5, 8.6, 8.7, 8.8, 8.9, 9.0]

    fig = build_daily_figure("TEST", df, market_ohlcv=spy, last_n_bars=6, template="plotly")

    rs_traces = [trace for trace in fig.data if trace.name == "RS vs SPY"]
    assert len(rs_traces) == 1
    assert rs_traces[0].y[0] == 0
    # RS lives on the secondary axis of the combined indicator pane.
    assert fig.layout.yaxis3.title.text == "RS%"
    assert fig.layout.yaxis3.range[0] < 0
    assert fig.layout.yaxis3.range[1] > 0


def test_combined_pane_zero_lines_align() -> None:
    df = _frame()
    spy = df.copy()
    spy["close"] = [8.5, 8.6, 8.7, 8.8, 8.9, 9.0]

    fig = build_daily_figure("TEST", df, market_ohlcv=spy, last_n_bars=6, template="plotly")

    vol_lo, vol_hi = fig.layout.yaxis2.range
    rs_lo, rs_hi = fig.layout.yaxis3.range
    vol_zero_frac = (0 - vol_lo) / (vol_hi - vol_lo)
    rs_zero_frac = (0 - rs_lo) / (rs_hi - rs_lo)
    assert abs(vol_zero_frac - rs_zero_frac) < 1e-9


def test_active_horizontal_levels_keep_nearest_support_and_resistance() -> None:
    levels = [
        _level(price=8.0),
        _level(price=9.5),
        _level(price=12.0),
        _level(price=14.0),
    ]

    active = _active_horizontal_levels(levels, today_close=10.0)

    assert {lv.price for lv in active} == {9.5, 12.0}


def test_daily_chart_historical_levels_toggle_controls_level_count() -> None:
    df = _frame()
    levels = [
        _level(price=6.0),
        _level(price=7.0),
        _level(price=13.0),
        _level(price=14.0),
    ]

    with patch("gui.charts.daily.find_all_levels", return_value=levels):
        default_fig = build_daily_figure("TEST", df, last_n_bars=6, template="plotly")
        historical_fig = build_daily_figure(
            "TEST",
            df,
            last_n_bars=6,
            template="plotly",
            show_historical_levels=True,
        )

    default_level_shapes = [shape for shape in default_fig.layout.shapes if shape.yref == "y"]
    historical_level_shapes = [shape for shape in historical_fig.layout.shapes if shape.yref == "y"]
    assert len(default_level_shapes) == 2
    assert len(historical_level_shapes) == 4


def test_daily_chart_draws_alert_lines() -> None:
    df = _frame()
    alerts = [
        PriceAlert(ticker="TEST", price=10.5),
        PriceAlert(ticker="TEST", price=12.5, triggered_at="2026-01-08T00:00:00+00:00"),
    ]

    fig = build_daily_figure("TEST", df, last_n_bars=6, template="plotly", alerts=alerts)

    alert_shapes = [s for s in fig.layout.shapes if s.line.dash == "dash"]
    assert {s.y0 for s in alert_shapes} == {10.5, 12.5}
    labels = [a.text for a in fig.layout.annotations]
    assert "⏰ 10.50" in labels
    assert "✓ 12.50" in labels
