"""Daily-chart Plotly figure factory.

Layout: two stacked panes, shared x-axis.
  Top pane     candlesticks + SMAs (20/50/100/200) + horizontal levels +
               active trendlines + AVWAPQ + AVWAPE (if earnings date set) +
               price alerts + breakout markers on today's bar.
  Bottom pane  combined indicator pane: volume bars + 10-bar
               relative-volume line (left axis) and RS% versus SPY
               (right axis), zero lines aligned.

Horizontal S/R rendering: each level is drawn as a single segment that
starts after the last candle that traded through it (with an ATR-based
clearance buffer) and extends past the most recent bar into right-edge
whitespace, tagged with its price. The line therefore never crosses or
skims a candle — if price is trading through the level today, only the
right-edge stub is drawn.

All overlays are tolerant of missing data — early bars without enough
history for SMA200 just have NaN, which plotly draws as gaps.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from tools.alerts import PriceAlert
from tools.indicators.atr import atr_latest
from tools.indicators.avwap import avwap, avwapq
from tools.indicators.relative_strength import rs_over_time
from tools.indicators.sma import sma
from tools.indicators.volume import avg_volume
from tools.levels import find_all_levels, HorizontalLevel, TrendlineLevel

from .common import (
    add_alert_lines,
    add_candles,
    add_indicator_pane,
    apply_base_layout,
    empty_figure,
    two_pane_figure,
)

# Colour palette — muted so overlays don't drown out price action.
SMA_COLORS = {
    20: "#f59e0b",   # amber
    50: "#3b82f6",   # blue
    100: "#14b8a6",  # teal
    200: "#ef4444",  # red
}
TRENDLINE_COLOR = "rgba(148, 163, 184, 0.85)"  # slate
AVWAPQ_COLOR = "#0ea5e9"   # sky
AVWAPE_COLOR = "#ec4899"   # pink

# Candles whose (buffered) range contains a level "block" its line; the
# buffer keeps the line from skimming along wicks at pixel distance.
LEVEL_CLEARANCE_ATRS = 0.10
# How far past the latest bar level lines extend (business days).
LEVEL_EXTEND_BDAYS = 6


def build_daily_figure(
    ticker: str,
    ohlcv: pd.DataFrame,
    market_ohlcv: pd.DataFrame | None = None,
    earnings_date: pd.Timestamp | None = None,
    last_n_bars: int = 250,
    template: str = "flatly",
    show_historical_levels: bool = False,
    alerts: list[PriceAlert] | None = None,
) -> go.Figure:
    """Build the daily-chart figure for `ticker`.

    `template` is a registered Plotly template name; "flatly" for light
    mode, "darkly" for dark. The chart factories don't need to know more
    than that — colors of overlays are RGBA-tuned to work on both.
    """
    if ohlcv.empty:
        return empty_figure(f"{ticker} — no daily data cached", template=template)

    df = ohlcv.tail(last_n_bars).copy()
    full = ohlcv  # full series for indicator math (use df.tail later for plotting)
    x = df.index
    x_end = df.index[-1] + pd.tseries.offsets.BDay(LEVEL_EXTEND_BDAYS)

    fig = two_pane_figure()
    add_candles(fig, df)

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
            earnings_bar = on_or_after[0]
            avwe = avwap(full, anchor=earnings_bar).reindex(df.index)
            if not avwe.isna().all():
                fig.add_trace(
                    go.Scatter(
                        x=x, y=avwe, mode="lines", name="AVWAPE",
                        line=dict(color=AVWAPE_COLOR, width=1.6, dash="dash"),
                    ),
                    row=1, col=1,
                )
            _draw_earnings_marker(fig, earnings_bar, df)

    # ---- Levels: detected once, shared by drawing + breakout markers ----
    levels = find_all_levels(full)
    _draw_levels(fig, full, df, levels, x_end, show_historical_levels)
    _draw_breakout_markers(fig, full, levels)

    # ---- Price alerts ----
    add_alert_lines(fig, alerts, x0=df.index[0], x1=x_end)

    # ---- Combined indicator pane: volume + RVol + RS vs SPY ----
    rvol = (full["volume"] - avg_volume(full["volume"], period=10)).reindex(df.index)
    rs = None
    if market_ohlcv is not None and not market_ohlcv.empty and "close" in market_ohlcv:
        rs = rs_over_time(full["close"], market_ohlcv["close"]).reindex(df.index)
    add_indicator_pane(fig, df, rvol, rs)

    apply_base_layout(
        fig, title=f"{ticker}  ·  Daily", template=template, uirevision=ticker
    )

    # Pin the x-range so the right-edge whitespace holding level/alert
    # tags is part of the initial view (shapes don't affect autorange).
    fig.update_xaxes(
        range=[df.index[0] - pd.Timedelta(days=1), x_end + pd.Timedelta(days=1)]
    )

    # ---- Crosshair: full H + V spike lines on the price pane ----
    spike_kwargs = dict(
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikedash="dot",
        spikethickness=1,
        spikecolor="rgba(148,163,184,0.7)",
    )
    fig.update_xaxes(**spike_kwargs, row=1, col=1)
    fig.update_yaxes(**spike_kwargs, row=1, col=1)
    return fig


def _level_color(is_resistance: bool, is_active: bool) -> str:
    rgb = "239, 68, 68" if is_resistance else "34, 197, 94"
    alpha = 0.8 if is_active else 0.3
    return f"rgba({rgb}, {alpha})"


def _level_clearance(full: pd.DataFrame) -> float:
    """Vertical clearance a candle adds around its high-low range."""
    a = atr_latest(full["high"], full["low"], full["close"], period=20)
    if a is not None and a > 0:
        return LEVEL_CLEARANCE_ATRS * a
    last_close = float(full["close"].iloc[-1])
    return 0.001 * abs(last_close)


def _draw_levels(
    fig: go.Figure,
    full: pd.DataFrame,
    plot_df: pd.DataFrame,
    levels: list,
    x_end: pd.Timestamp,
    show_historical_levels: bool = False,
) -> None:
    """Draw horizontal level lines + trendline shapes on row 1."""
    today_close = float(full["close"].iloc[-1])
    active_horizontal_levels = _active_horizontal_levels(levels, today_close)
    clearance = _level_clearance(full)

    for lv in levels:
        if isinstance(lv, HorizontalLevel):
            is_active = lv in active_horizontal_levels
            if not show_historical_levels and not is_active:
                continue
            color = _level_color(lv.price >= today_close, is_active)
            x0 = _level_line_start(full, plot_df, lv, clearance)
            if x0 is None:
                # Price is trading through the level right now — draw
                # only the right-edge stub so nothing crosses a candle.
                x0 = plot_df.index[-1] + pd.tseries.offsets.BDay(1)
            fig.add_shape(
                type="line",
                x0=x0, x1=x_end, y0=lv.price, y1=lv.price,
                line=dict(color=color, width=1.4),
                row=1, col=1,
            )
            fig.add_annotation(
                x=x_end, y=lv.price,
                text=f"{lv.price:.2f}", showarrow=False,
                xanchor="right", yshift=7,
                font=dict(size=10, color=color),
                row=1, col=1,
            )
        elif isinstance(lv, TrendlineLevel):
            x0_idx = lv.anchor1_idx
            x1_idx = len(full) - 1
            if x0_idx >= len(full) or x1_idx >= len(full):
                continue
            fig.add_shape(
                type="line",
                x0=full.index[x0_idx], x1=full.index[x1_idx],
                y0=lv.value_at(x0_idx), y1=lv.value_at(x1_idx),
                line=dict(color=TRENDLINE_COLOR, width=1.5, dash="solid"),
                row=1, col=1,
            )
        # MovingAverageLevel is already drawn as the SMA200 trace above.


def _active_horizontal_levels(
    levels: list,
    today_close: float,
) -> set[HorizontalLevel]:
    """Return the nearest horizontal resistance and support around price."""
    nearest_above: HorizontalLevel | None = None
    nearest_below: HorizontalLevel | None = None
    above_dist = float("inf")
    below_dist = float("inf")

    for lv in levels:
        if not isinstance(lv, HorizontalLevel):
            continue
        price = float(lv.price)
        if price >= today_close:
            dist = price - today_close
            if dist < above_dist:
                nearest_above = lv
                above_dist = dist
        else:
            dist = today_close - price
            if dist < below_dist:
                nearest_below = lv
                below_dist = dist

    return {lv for lv in (nearest_above, nearest_below) if lv is not None}


def _level_line_start(
    full: pd.DataFrame,
    plot_df: pd.DataFrame,
    lv: HorizontalLevel,
    clearance: float = 0.0,
) -> pd.Timestamp | None:
    """First bar of the level's clean run up to the most recent bar.

    A candle "blocks" the level when the level price falls inside the
    candle's high-low range widened by `clearance`. The line starts on
    the bar after the most recent blocking candle (or at the level's
    first touch if nothing blocks it in the plotted window). Returns
    None when the most recent bar itself blocks — the level has no clean
    run and should only be drawn in right-edge whitespace.
    """
    if plot_df.empty:
        return None

    start_idx = max(0, int(lv.first_touch_idx))
    if start_idx >= len(full):
        return None

    x_from = max(full.index[start_idx], plot_df.index[0])
    visible = plot_df.loc[x_from:]
    if visible.empty:
        return None

    price = float(lv.price)
    highs = pd.to_numeric(visible["high"], errors="coerce")
    lows = pd.to_numeric(visible["low"], errors="coerce")
    blocked = (lows - clearance <= price) & (price <= highs + clearance)

    if not blocked.any():
        return visible.index[0]
    last_blocked_pos = int(len(blocked) - 1 - blocked.values[::-1].argmax())
    if last_blocked_pos >= len(visible) - 1:
        return None
    return visible.index[last_blocked_pos + 1]


def _draw_breakout_markers(fig: go.Figure, full: pd.DataFrame, levels: list) -> None:
    """Add ↑/↓ markers above/below today's candle if any level broke today."""
    if len(full) < 2:
        return
    today = len(full) - 1
    close_today = float(full["close"].iloc[today])
    close_yest = float(full["close"].iloc[today - 1])

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
    if broke_long:
        fig.add_annotation(
            x=today_x, y=float(full["high"].iloc[today]), text="▲", showarrow=False,
            font=dict(size=22, color="#10b981"), yshift=12,
            row=1, col=1,
        )
    if broke_short:
        fig.add_annotation(
            x=today_x, y=float(full["low"].iloc[today]), text="▼", showarrow=False,
            font=dict(size=22, color="#ef4444"), yshift=-12,
            row=1, col=1,
        )


def _draw_earnings_marker(fig: go.Figure, earnings_bar: pd.Timestamp, plot_df: pd.DataFrame) -> None:
    """Add a TradingView-style earnings event marker on the price pane."""
    if plot_df.empty:
        return
    if not (plot_df.index[0] <= earnings_bar <= plot_df.index[-1]):
        return
    fig.add_annotation(
        x=earnings_bar,
        y=0.025,
        xref="x",
        yref="y domain",
        text="E",
        showarrow=False,
        font=dict(size=10, color="white"),
        bgcolor="#7c3aed",
        bordercolor="#7c3aed",
        borderpad=3,
        hovertext=f"Earnings {pd.Timestamp(earnings_bar).strftime('%Y-%m-%d')}",
        hoverlabel=dict(bgcolor="#7c3aed", font=dict(color="white")),
    )
