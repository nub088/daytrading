"""5-minute-chart Plotly figure factory.

Layout: two stacked panes, shared x-axis. Defaults to the most recent
two trading sessions (configurable) — that's the window momentum
traders actually care about.

  Top pane     candlesticks + EMA 9/21/50 + session VWAP +
               premarket high/low (dashed, per session) +
               prior day close (dashed, per session).
  Bottom pane  volume bars (primary y) + interval-matched intraday
               RVol line (secondary y, reference at 1.0).

5-min data is fetched on demand from yfinance (60-day limit). Session
boundaries are detected from the bar timestamps' dates.
"""
from __future__ import annotations

import pandas as pd
from plotly.subplots import make_subplots
import plotly.graph_objects as go

from tools.indicators.ema import ema
from tools.indicators.intraday_vwap import session_vwap
from tools.indicators.intraday_rvol import intraday_rvol


EMA_COLORS = {
    9: "#f59e0b",    # amber
    21: "#3b82f6",   # blue
    50: "#a855f7",   # purple
}
VWAP_COLOR = "#0ea5e9"             # sky
RVOL_LINE_COLOR = "#f97316"        # orange
PRIOR_CLOSE_COLOR = "rgba(148,163,184,0.85)"  # slate
PREMARKET_COLOR = "rgba(99, 102, 241, 0.55)"  # indigo

# Regular-hours window for premarket detection (NYSE/Nasdaq, local time).
RTH_OPEN = pd.Timestamp("09:30").time()
RTH_CLOSE = pd.Timestamp("16:00").time()


def build_intraday_figure(
    ticker: str,
    ohlcv: pd.DataFrame,
    sessions_to_show: int = 2,
    template: str = "flatly",
) -> go.Figure:
    """Build the 5-min chart figure for `ticker`.

    `sessions_to_show` clips the visible window to the most recent N
    trading days. Indicator math still uses the full intraday history
    so EMAs and the rolling RVol baseline are properly seeded.

    `template` is a registered Plotly template name ("flatly" / "darkly").
    """
    if ohlcv.empty:
        return _empty_figure(f"{ticker} — no intraday data available", template=template)

    full = ohlcv.copy()

    # Compute indicators on the full series so the visible window has
    # warmed-up values.
    ema_full = {p: ema(full["close"], p) for p in EMA_COLORS}
    vwap_full = session_vwap(full)
    rvol_full = intraday_rvol(full, lookback_sessions=20)

    # Clip to the most recent N sessions for plotting.
    unique_dates = sorted(set(full.index.date))
    keep_dates = set(unique_dates[-sessions_to_show:])
    plot_mask = pd.Series([d in keep_dates for d in full.index.date], index=full.index)
    df = full[plot_mask]
    if df.empty:
        return _empty_figure(f"{ticker} — no intraday data in window")

    x = df.index

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.78, 0.22],
        specs=[[{"secondary_y": False}], [{"secondary_y": True}]],
    )

    # ---- D1-hover crosshair placeholder (must stay at shapes[0]) ----
    # Hidden by default; the sync callback toggles `visible` and sets y0/y1
    # to the price the cursor is hovering on the daily chart. Spans the
    # entire intraday x-axis via "x domain" so it doesn't need real x values.
    fig.add_shape(
        type="line",
        xref="x domain", x0=0, x1=1,
        yref="y", y0=0, y1=0,
        line=dict(color="rgba(148,163,184,0.85)", width=1, dash="dot"),
        visible=False,
        row=1, col=1,
    )

    # ---- Candles ----
    fig.add_trace(
        go.Candlestick(
            x=x, open=df["open"], high=df["high"], low=df["low"], close=df["close"],
            name="price", increasing_line_color="#10b981", decreasing_line_color="#ef4444",
            showlegend=False,
        ),
        row=1, col=1,
    )

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
    vwap_window = vwap_full.reindex(df.index)
    fig.add_trace(
        go.Scatter(
            x=x, y=vwap_window, mode="lines", name="VWAP",
            line=dict(color=VWAP_COLOR, width=1.8),
        ),
        row=1, col=1,
    )

    # ---- Per-session overlays: premarket H/L and prior day close ----
    _draw_session_overlays(fig, full, df)

    # ---- Volume bars + RVol line ----
    bar_colors = ["#10b981" if c >= o else "#ef4444"
                  for c, o in zip(df["close"], df["open"])]
    fig.add_trace(
        go.Bar(
            x=x, y=df["volume"], name="volume", marker_color=bar_colors,
            opacity=0.55, showlegend=False, hovertemplate="%{y:,}<extra></extra>",
        ),
        row=2, col=1, secondary_y=False,
    )

    rvol_window = rvol_full.reindex(df.index)
    fig.add_trace(
        go.Scatter(
            x=x, y=rvol_window, name="RVol (ToD)", mode="lines",
            line=dict(color=RVOL_LINE_COLOR, width=1.4),
            hovertemplate="RVol %{y:.2f}<extra></extra>",
        ),
        row=2, col=1, secondary_y=True,
    )
    fig.add_hline(
        y=1.0, line=dict(color="rgba(148,163,184,0.6)", width=1, dash="dot"),
        row=2, col=1, secondary_y=True,
    )

    fig.update_layout(
        title=f"{ticker}  ·  5-min",
        height=720,
        margin=dict(l=10, r=10, t=40, b=20),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template=template,
        dragmode="pan",
        hovermode="x unified",
    )
    # Hide non-trading gaps (overnight, weekend) so candles pack together.
    fig.update_xaxes(rangebreaks=[
        dict(bounds=["sat", "mon"]),
        dict(bounds=[16.5, 8], pattern="hour"),  # after-hours/premarket gap
    ])
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1, secondary_y=False)
    fig.update_yaxes(title_text="RVol", row=2, col=1, secondary_y=True, showgrid=False)
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

        # Premarket H/L for this session
        pm_mask = day_mask & premarket_mask_full
        if pm_mask.any():
            pm_high = float(full.loc[pm_mask, "high"].max())
            pm_low = float(full.loc[pm_mask, "low"].min())
            session_start = full.index[day_mask][0]
            session_end = full.index[day_mask][-1]
            for y, label in ((pm_high, "PM high"), (pm_low, "PM low")):
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
        prior_day = prior_candidates[-1]
        prior_mask = (full.index.date == prior_day) & rth_mask_full
        if not prior_mask.any():
            continue
        prior_close = float(full.loc[prior_mask, "close"].iloc[-1])
        session_start = full.index[day_mask][0]
        session_end = full.index[day_mask][-1]
        fig.add_shape(
            type="line",
            x0=session_start, x1=session_end, y0=prior_close, y1=prior_close,
            line=dict(color=PRIOR_CLOSE_COLOR, width=1.2, dash="dot"),
            row=1, col=1,
        )


def _empty_figure(message: str, template: str = "flatly") -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message, xref="paper", yref="paper",
        x=0.5, y=0.5, showarrow=False, font=dict(size=16, color="#94a3b8"),
    )
    fig.update_layout(
        height=720, template=template,
        margin=dict(l=10, r=10, t=40, b=20),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
    )
    return fig
