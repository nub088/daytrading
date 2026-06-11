"""5-minute-chart Plotly figure factory.

Layout: two stacked panes, shared x-axis. Defaults to the most recent
four trading sessions (latest session plus three prior sessions), which
keeps recent context visible without crowding the intraday view.

  Top pane     candlesticks + EMA 9/21/50 + session VWAP +
               premarket high/low (dashed, per session) +
               prior day close (dashed, per session) + price alerts.
  Bottom pane  combined indicator pane: volume bars + 10-bar
               relative-volume line (left axis) and RS% versus SPY
               (right axis), zero lines aligned.

5-min data is fetched on demand from yfinance (60-day limit). Session
boundaries are detected from the bar timestamps' dates.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from tools.alerts import PriceAlert
from tools.indicators.ema import ema
from tools.indicators.intraday_vwap import session_vwap
from tools.indicators.relative_strength import rs_over_time
from tools.indicators.volume import avg_volume

from .common import (
    add_alert_lines,
    add_candles,
    add_indicator_pane,
    apply_base_layout,
    empty_figure,
    two_pane_figure,
)

EMA_COLORS = {
    9: "#f59e0b",    # amber
    21: "#3b82f6",   # blue
    50: "#a855f7",   # purple
}
VWAP_COLOR = "#7c3aed"             # purple
PRIOR_CLOSE_COLOR = "rgba(148,163,184,0.85)"  # slate
PREMARKET_COLOR = "rgba(99, 102, 241, 0.55)"  # indigo

# Regular-hours window for premarket detection (NYSE/Nasdaq, local time).
RTH_OPEN = pd.Timestamp("09:30").time()
RTH_CLOSE = pd.Timestamp("16:00").time()


def build_intraday_figure(
    ticker: str,
    ohlcv: pd.DataFrame,
    market_ohlcv: pd.DataFrame | None = None,
    sessions_to_show: int = 4,
    template: str = "flatly",
    alerts: list[PriceAlert] | None = None,
) -> go.Figure:
    """Build the 5-min chart figure for `ticker`.

    `sessions_to_show` clips the visible window to the most recent N
    trading days. Indicator math still uses the full intraday history
    so EMAs and the rolling RVol baseline are properly seeded.

    `template` is a registered Plotly template name ("flatly" / "darkly").
    """
    if ohlcv.empty:
        return empty_figure(f"{ticker} — no intraday data available", template=template)

    full = ohlcv.copy()

    # Compute indicators on the full series so the visible window has
    # warmed-up values.
    ema_full = {p: ema(full["close"], p) for p in EMA_COLORS}
    vwap_full = session_vwap(full)
    rvol_full = full["volume"] - avg_volume(full["volume"], period=10)

    # Clip to the most recent N sessions for plotting.
    unique_dates = sorted(set(full.index.date))
    keep_dates = set(unique_dates[-sessions_to_show:])
    plot_mask = pd.Series([d in keep_dates for d in full.index.date], index=full.index)
    df = full[plot_mask]
    if df.empty:
        return empty_figure(f"{ticker} — no intraday data in window", template=template)

    x = df.index

    fig = two_pane_figure()
    add_candles(fig, df)

    # ---- EMAs ----
    for period, color in EMA_COLORS.items():
        s = ema_full[period].reindex(df.index)
        fig.add_trace(
            go.Scatter(
                x=x, y=s, mode="lines", name=f"EMA{period}",
                line=dict(color=color, width=1.2), hoverinfo="skip",
            ),
            row=1, col=1,
        )

    # ---- Session VWAP ----
    fig.add_trace(
        go.Scatter(
            x=x, y=vwap_full.reindex(df.index), mode="lines", name="VWAP",
            line=dict(color=VWAP_COLOR, width=2.8),
        ),
        row=1, col=1,
    )

    # ---- Per-session overlays: premarket H/L and prior day close ----
    _draw_session_overlays(fig, full, df)

    # ---- Price alerts ----
    add_alert_lines(fig, alerts, x0=df.index[0], x1=df.index[-1])

    # ---- Combined indicator pane: volume + RVol + RS vs SPY ----
    rs = None
    if market_ohlcv is not None and not market_ohlcv.empty and "close" in market_ohlcv:
        market_window = market_ohlcv.reindex(df.index)
        rs = rs_over_time(df["close"], market_window["close"]).reindex(df.index)
    add_indicator_pane(fig, df, rvol_full.reindex(df.index), rs)

    apply_base_layout(
        fig, title=f"{ticker}  ·  5-min", template=template, uirevision=ticker
    )
    # Hide non-trading gaps (overnight, weekend) so candles pack together.
    fig.update_xaxes(rangebreaks=[
        dict(bounds=["sat", "mon"]),
        dict(bounds=[16, 9.5], pattern="hour"),  # regular-hours feed: 4pm -> 9:30am
    ])
    return fig


def _draw_session_overlays(fig: go.Figure, full: pd.DataFrame, plot_df: pd.DataFrame) -> None:
    """For each session in `plot_df`, draw:
       - premarket high (dashed indigo, from session open to RTH close)
       - premarket low  (dashed indigo)
       - prior day's regular-hours close (dashed slate)
    """
    times = pd.Index(full.index.time)
    rth_mask_full = (times >= RTH_OPEN) & (times < RTH_CLOSE)
    premarket_mask_full = times < RTH_OPEN

    unique_dates = sorted(set(plot_df.index.date))
    prior_dates = sorted(set(full.index.date))

    for d in unique_dates:
        day_mask = full.index.date == d
        session_start = full.index[day_mask][0]
        session_end = full.index[day_mask][-1]

        # Premarket H/L for this session
        pm_mask = day_mask & premarket_mask_full
        if pm_mask.any():
            pm_high = float(full.loc[pm_mask, "high"].max())
            pm_low = float(full.loc[pm_mask, "low"].min())
            for y in (pm_high, pm_low):
                fig.add_shape(
                    type="line",
                    x0=session_start, x1=session_end, y0=y, y1=y,
                    line=dict(color=PREMARKET_COLOR, width=1.2, dash="dash"),
                    row=1, col=1,
                )

        # Prior day's RTH close (last close before 4pm of the previous trading day)
        prior_candidates = [pd_ for pd_ in prior_dates if pd_ < d]
        if not prior_candidates:
            continue
        prior_mask = (full.index.date == prior_candidates[-1]) & rth_mask_full
        if not prior_mask.any():
            continue
        prior_close = float(full.loc[prior_mask, "close"].iloc[-1])
        fig.add_shape(
            type="line",
            x0=session_start, x1=session_end, y0=prior_close, y1=prior_close,
            line=dict(color=PRIOR_CLOSE_COLOR, width=1.2, dash="dot"),
            row=1, col=1,
        )
