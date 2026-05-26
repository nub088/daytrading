"""Daily-chart Plotly figure factory.

Layout: two stacked panes, shared x-axis.
  Top pane     candlesticks + SMAs (20/50/100/200) + horizontal levels +
               active trendlines + AVWAPQ + AVWAPE (if earnings date set) +
               breakout markers on today's bar.
  Bottom pane  volume bars (primary y) + 20d RVol line (secondary y).

All overlays are tolerant of missing data — early bars without enough
history for SMA200 just have NaN, which plotly draws as gaps.

The chart is built to be a self-contained Plotly figure object; the
caller passes it to a `dcc.Graph(figure=...)` in the Dash layout.
"""
from __future__ import annotations

import pandas as pd
from plotly.subplots import make_subplots
import plotly.graph_objects as go

from tools.indicators.sma import sma
from tools.indicators.volume import relative_volume
from tools.indicators.avwap import avwap, avwapq
from tools.levels import find_all_levels, HorizontalLevel, TrendlineLevel, MovingAverageLevel


# Colour palette — muted so overlays don't drown out price action.
SMA_COLORS = {
    20: "#f59e0b",   # amber
    50: "#3b82f6",   # blue
    100: "#a855f7",  # purple
    200: "#ef4444",  # red
}
LEVEL_COLOR_RESISTANCE = "rgba(239, 68, 68, 0.35)"
LEVEL_COLOR_SUPPORT = "rgba(34, 197, 94, 0.35)"
TRENDLINE_COLOR = "rgba(148, 163, 184, 0.85)"  # slate
AVWAPQ_COLOR = "#0ea5e9"   # sky
AVWAPE_COLOR = "#ec4899"   # pink
RVOL_LINE_COLOR = "#f97316"  # orange


def build_daily_figure(
    ticker: str,
    ohlcv: pd.DataFrame,
    earnings_date: pd.Timestamp | None = None,
    last_n_bars: int = 250,
    template: str = "flatly",
) -> go.Figure:
    """Build the daily-chart figure for `ticker`.

    `template` is a registered Plotly template name; "flatly" for light
    mode, "darkly" for dark. The chart factories don't need to know more
    than that — colors of overlays are RGBA-tuned to work on both.
    """
    if ohlcv.empty:
        return _empty_figure(f"{ticker} — no daily data cached", template=template)

    df = ohlcv.tail(last_n_bars).copy()
    full = ohlcv  # full series for indicator math (use df.tail later for plotting)
    x = df.index

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.78, 0.22],
        specs=[[{"secondary_y": False}], [{"secondary_y": True}]],
    )

    # ---- Row 1: candles ----
    fig.add_trace(
        go.Candlestick(
            x=x, open=df["open"], high=df["high"], low=df["low"], close=df["close"],
            name="price", increasing_line_color="#10b981", decreasing_line_color="#ef4444",
            showlegend=False,
        ),
        row=1, col=1,
    )

    # ---- SMAs ----
    for period, color in SMA_COLORS.items():
        s = sma(full["close"], period).reindex(df.index)
        fig.add_trace(
            go.Scatter(
                x=x, y=s, mode="lines", name=f"SMA{period}",
                line=dict(color=color, width=1.2), hoverinfo="skip",
            ),
            row=1, col=1,
        )

    # ---- AVWAPQ (Triple Witching anchor) ----
    try:
        avwq = avwapq(full).reindex(df.index)
        if not avwq.isna().all():
            fig.add_trace(
                go.Scatter(
                    x=x, y=avwq, mode="lines", name="AVWAPQ",
                    line=dict(color=AVWAPQ_COLOR, width=1.6, dash="dot"),
                ),
                row=1, col=1,
            )
    except Exception:
        pass

    # ---- AVWAPE (earnings anchor, if available) ----
    if earnings_date is not None:
        ed = pd.Timestamp(earnings_date).normalize()
        # Anchor to the first OHLCV bar on or after the earnings date.
        on_or_after = full.index[full.index >= ed]
        if len(on_or_after) > 0:
            avwe = avwap(full, anchor=on_or_after[0]).reindex(df.index)
            if not avwe.isna().all():
                fig.add_trace(
                    go.Scatter(
                        x=x, y=avwe, mode="lines", name="AVWAPE",
                        line=dict(color=AVWAPE_COLOR, width=1.6, dash="dash"),
                    ),
                    row=1, col=1,
                )

    # ---- Horizontal levels and trendlines ----
    _draw_levels(fig, full, df)

    # ---- Breakout markers on today's bar ----
    _draw_breakout_markers(fig, full, df)

    # ---- Row 2: volume + RVol line ----
    vol = df["volume"]
    bar_colors = ["#10b981" if c >= o else "#ef4444"
                  for c, o in zip(df["close"], df["open"])]
    fig.add_trace(
        go.Bar(
            x=x, y=vol, name="volume", marker_color=bar_colors,
            opacity=0.55, showlegend=False, hovertemplate="%{y:,}<extra></extra>",
        ),
        row=2, col=1, secondary_y=False,
    )

    rvol_full = relative_volume(full["volume"], period=20).reindex(df.index)
    fig.add_trace(
        go.Scatter(
            x=x, y=rvol_full, name="RVol 20d", mode="lines",
            line=dict(color=RVOL_LINE_COLOR, width=1.4),
            hovertemplate="RVol %{y:.2f}<extra></extra>",
        ),
        row=2, col=1, secondary_y=True,
    )
    # Reference line at RVol = 1
    fig.add_hline(
        y=1.0, line=dict(color="rgba(148,163,184,0.6)", width=1, dash="dot"),
        row=2, col=1, secondary_y=True,
    )

    # ---- Layout ----
    fig.update_layout(
        title=f"{ticker}  ·  Daily",
        height=720,
        margin=dict(l=10, r=10, t=40, b=20),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template=template,
        dragmode="pan",
        hovermode="x unified",
    )
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1, secondary_y=False)
    fig.update_yaxes(title_text="RVol", row=2, col=1, secondary_y=True, showgrid=False)
    return fig


def _draw_levels(fig: go.Figure, full: pd.DataFrame, plot_df: pd.DataFrame) -> None:
    """Draw horizontal level lines + trendline shapes on row 1."""
    levels = find_all_levels(full)
    today_close = float(full["close"].iloc[-1])
    plot_start = plot_df.index[0]
    plot_end = plot_df.index[-1]

    for lv in levels:
        if isinstance(lv, HorizontalLevel):
            # Only draw if the level intersects the visible window.
            color = LEVEL_COLOR_RESISTANCE if lv.price >= today_close else LEVEL_COLOR_SUPPORT
            # Draw from first_touch onwards (clipped to plot range).
            x_from = full.index[max(0, lv.first_touch_idx)]
            x_from = max(x_from, plot_start)
            fig.add_shape(
                type="line",
                x0=x_from, x1=plot_end,
                y0=lv.price, y1=lv.price,
                line=dict(color=color, width=1.4),
                row=1, col=1,
            )
        elif isinstance(lv, TrendlineLevel):
            x0_idx = lv.anchor1_idx
            x1_idx = len(full) - 1
            if x0_idx >= len(full) or x1_idx >= len(full):
                continue
            x0 = full.index[x0_idx]
            x1 = full.index[x1_idx]
            y0 = lv.value_at(x0_idx)
            y1 = lv.value_at(x1_idx)
            fig.add_shape(
                type="line",
                x0=x0, x1=x1, y0=y0, y1=y1,
                line=dict(color=TRENDLINE_COLOR, width=1.5, dash="solid"),
                row=1, col=1,
            )
        # MovingAverageLevel is already drawn as the SMA200 trace above.


def _draw_breakout_markers(fig: go.Figure, full: pd.DataFrame, plot_df: pd.DataFrame) -> None:
    """Add ↑/↓ markers above/below today's candle if any level broke today.

    We re-run the breakouts logic inline (cheaper than threading the
    scanner row through) but only inspect today vs yesterday on the
    full level list.
    """
    if len(full) < 2:
        return
    today = len(full) - 1
    close_today = float(full["close"].iloc[today])
    close_yest = float(full["close"].iloc[today - 1])

    levels = find_all_levels(full)
    broke_long = False
    broke_short = False
    for lv in levels:
        v_today = lv.value_at(today)
        v_yest = lv.value_at(today - 1)
        if pd.isna(v_today) or pd.isna(v_yest):
            continue
        if close_yest < v_yest and close_today > v_today:
            broke_long = True
        elif close_yest > v_yest and close_today < v_today:
            broke_short = True

    today_x = full.index[today]
    today_high = float(full["high"].iloc[today])
    today_low = float(full["low"].iloc[today])

    if broke_long:
        fig.add_annotation(
            x=today_x, y=today_high, text="▲", showarrow=False,
            font=dict(size=22, color="#10b981"), yshift=12,
            row=1, col=1,
        )
    if broke_short:
        fig.add_annotation(
            x=today_x, y=today_low, text="▼", showarrow=False,
            font=dict(size=22, color="#ef4444"), yshift=-12,
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
