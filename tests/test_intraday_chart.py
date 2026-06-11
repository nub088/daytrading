from __future__ import annotations

import pandas as pd

from gui.charts.intraday import build_intraday_figure
from tools.alerts import PriceAlert


def _frame() -> pd.DataFrame:
    idx = pd.date_range("2026-01-05 09:30", periods=12, freq="5min")
    return pd.DataFrame(
        {
            "open": [10.0, 10.1, 10.2, 10.4, 10.5, 10.6, 10.7, 10.8, 10.9, 11.0, 11.1, 11.2],
            "high": [10.2, 10.3, 10.5, 10.6, 10.7, 10.9, 10.9, 11.0, 11.2, 11.3, 11.4, 11.5],
            "low": [9.9, 10.0, 10.1, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 10.9, 11.0, 11.1],
            "close": [10.1, 10.2, 10.4, 10.5, 10.6, 10.8, 10.8, 10.9, 11.1, 11.2, 11.3, 11.4],
            "volume": [1000, 1100, 1050, 1200, 1150, 1300, 1250, 1400, 1350, 1500, 1450, 1600],
        },
        index=idx,
    )


def test_intraday_chart_adds_rs_vs_spy_trace_when_market_data_present() -> None:
    df = _frame()
    spy = df.copy()
    spy["close"] = [10.1, 10.12, 10.14, 10.16, 10.18, 10.2, 10.22, 10.24, 10.26, 10.28, 10.3, 10.32]

    fig = build_intraday_figure("TEST", df, market_ohlcv=spy, template="plotly")

    rs_traces = [trace for trace in fig.data if trace.name == "RS vs SPY"]
    assert len(rs_traces) == 1
    assert rs_traces[0].y[0] == 0
    # Combined indicator pane: volume on the primary axis, RS% secondary.
    assert fig.layout.yaxis2.title.text == "Vol"
    assert fig.layout.yaxis3.title.text == "RS%"
    assert fig.layout.yaxis3.range[0] < 0
    assert fig.layout.yaxis3.range[1] > 0


def test_intraday_rs_normalizes_to_first_visible_5min_bar() -> None:
    first_session = _frame()
    second_session = _frame()
    second_session.index = pd.date_range("2026-01-06 09:30", periods=12, freq="5min")
    df = pd.concat([first_session, second_session])

    spy = df.copy()
    spy["close"] = range(100, 124)

    fig = build_intraday_figure("TEST", df, market_ohlcv=spy, sessions_to_show=1, template="plotly")

    rs_traces = [trace for trace in fig.data if trace.name == "RS vs SPY"]
    assert len(rs_traces) == 1
    assert rs_traces[0].x[0] == second_session.index[0]
    assert rs_traces[0].y[0] == 0


def test_intraday_chart_defaults_to_latest_session_plus_three_prior_sessions() -> None:
    sessions = []
    for day in range(5):
        session = _frame()
        session.index = pd.date_range(f"2026-01-{5 + day:02d} 09:30", periods=12, freq="5min")
        sessions.append(session)
    df = pd.concat(sessions)

    fig = build_intraday_figure("TEST", df, market_ohlcv=df, template="plotly")

    price_trace = next(trace for trace in fig.data if trace.name == "price")
    assert price_trace.x[0] == sessions[1].index[0]


def test_intraday_chart_draws_alert_lines() -> None:
    df = _frame()
    alerts = [PriceAlert(ticker="TEST", price=10.75)]

    fig = build_intraday_figure("TEST", df, template="plotly", alerts=alerts)

    alert_shapes = [s for s in fig.layout.shapes if s.y0 == 10.75]
    assert len(alert_shapes) == 1
    assert alert_shapes[0].line.dash == "dash"
    assert any(a.text == "⏰ 10.75" for a in fig.layout.annotations)
