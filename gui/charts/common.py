"""Shared building blocks for the daily and 5-min chart factories.

Both charts use the same two-pane skeleton:

  Row 1  price candlesticks + chart-specific overlays.
  Row 2  combined indicator pane — volume bars and the 10-bar
         relative-volume oscillator on the left axis, RS% versus SPY on
         the right axis. The two axes are range-aligned so their zero
         lines coincide and one reference line serves both series.

Everything here is chart-agnostic: candle drawing, the indicator pane,
alert lines, base layout, and the empty-state figure. The factories keep
only their own overlays (SMAs/levels vs EMAs/VWAP/session lines).
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from tools.alerts import PriceAlert

# ---- Shared palette ----
CANDLE_UP_COLOR = "#10b981"
CANDLE_DOWN_COLOR = "#ef4444"
RS_LINE_COLOR = "#7c3aed"    # violet
RVOL_LINE_COLOR = "#3b63ff"  # blue
REFERENCE_LINE_COLOR = "rgba(148,163,184,0.6)"  # slate
ALERT_ACTIVE_COLOR = "#f59e0b"                  # amber
ALERT_TRIGGERED_COLOR = "rgba(148,163,184,0.7)"  # slate (consumed alert)

PRICE_ROW = 1
INDICATOR_ROW = 2


def two_pane_figure() -> go.Figure:
    """Price pane on top, combined indicator pane (with secondary y) below."""
    return make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.78, 0.22],
        specs=[
            [{"secondary_y": False}],
            [{"secondary_y": True}],
        ],
    )


def add_candles(fig: go.Figure, df: pd.DataFrame, row: int = PRICE_ROW) -> None:
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["open"], high=df["high"], low=df["low"], close=df["close"],
            name="price",
            increasing_line_color=CANDLE_UP_COLOR,
            decreasing_line_color=CANDLE_DOWN_COLOR,
            showlegend=False,
        ),
        row=row, col=1,
    )


def add_indicator_pane(
    fig: go.Figure,
    df: pd.DataFrame,
    rvol: pd.Series | None,
    rs: pd.Series | None,
    row: int = INDICATOR_ROW,
) -> None:
    """Volume bars + RVol oscillator (left axis) and RS% (right axis).

    The right axis range is solved so its zero sits at the same pane
    fraction as the left axis zero — one dotted reference line then
    reads correctly for both the oscillator and RS.
    """
    x = df.index
    vol = df["volume"]
    bar_colors = [
        CANDLE_UP_COLOR if c >= o else CANDLE_DOWN_COLOR
        for c, o in zip(df["close"], df["open"])
    ]
    fig.add_trace(
        go.Bar(
            x=x, y=vol, name="volume", marker_color=bar_colors,
            opacity=0.45, showlegend=False, hovertemplate="%{y:,}<extra></extra>",
        ),
        row=row, col=1, secondary_y=False,
    )

    if rvol is not None:
        fig.add_trace(
            go.Scatter(
                x=x, y=rvol, name="10VOL(10)", mode="lines",
                line=dict(color=RVOL_LINE_COLOR, width=1.4),
                hovertemplate="10VOL(10) %{y:+,.0f}<extra></extra>",
            ),
            row=row, col=1, secondary_y=False,
        )

    primary_range = _volume_axis_range(vol, rvol)
    fig.add_hline(
        y=0.0,
        line=dict(color=REFERENCE_LINE_COLOR, width=1, dash="dot"),
        row=row, col=1,
    )
    fig.update_yaxes(
        title_text="Vol",
        range=primary_range,
        row=row, col=1,
        secondary_y=False,
    )

    if rs is not None and not pd.to_numeric(rs, errors="coerce").dropna().empty:
        fig.add_trace(
            go.Scatter(
                x=x, y=rs, name="RS vs SPY", mode="lines",
                line=dict(color=RS_LINE_COLOR, width=1.6),
                hovertemplate="RS vs SPY %{y:+.2f}%<extra></extra>",
            ),
            row=row, col=1, secondary_y=True,
        )
        fig.update_yaxes(
            title_text="RS%",
            range=_aligned_secondary_range(primary_range, rs),
            showgrid=False,
            zeroline=False,  # the shared dotted hline is the zero reference
            row=row, col=1,
            secondary_y=True,
        )

    fig.update_yaxes(showgrid=False, row=row, col=1, secondary_y=False)


def _volume_axis_range(
    volume: pd.Series, oscillator: pd.Series | None
) -> list[float] | None:
    vol = pd.to_numeric(volume, errors="coerce").dropna()
    osc = (
        pd.to_numeric(oscillator, errors="coerce").dropna()
        if oscillator is not None
        else pd.Series(dtype="float64")
    )
    if vol.empty:
        return None
    top = float(max(vol.max(), osc.max() if not osc.empty else 0))
    bottom = float(min(0, osc.min() if not osc.empty else 0))
    padding = max(top - bottom, top, 1.0) * 0.05
    return [bottom - padding, top + padding]


def _aligned_secondary_range(
    primary_range: list[float] | None, values: pd.Series
) -> list[float]:
    """Range for the RS axis whose zero matches the primary axis zero."""
    series = pd.to_numeric(values, errors="coerce").dropna()
    hi_need = max(float(series.max()), 0.0) * 1.05 if not series.empty else 1.0
    lo_need = min(float(series.min()), 0.0) * 1.05 if not series.empty else -1.0
    hi_need = max(hi_need, 1e-6)

    if primary_range is None or primary_range[1] <= primary_range[0]:
        bound = max(hi_need, -lo_need, 1.0)
        return [-bound, bound]

    # Zero's fractional position on the primary axis; padding keeps it
    # strictly inside (0, 1).
    zero_frac = (0.0 - primary_range[0]) / (primary_range[1] - primary_range[0])
    zero_frac = min(max(zero_frac, 1e-3), 1.0 - 1e-3)
    span = max(hi_need / (1.0 - zero_frac), -lo_need / zero_frac, 1e-6)
    return [-zero_frac * span, (1.0 - zero_frac) * span]


def add_alert_lines(
    fig: go.Figure,
    alerts: list[PriceAlert] | None,
    x0,
    x1,
    row: int = PRICE_ROW,
) -> None:
    """Dashed alert lines across the price pane with a right-edge tag.

    Active alerts are amber; triggered ones fade to slate so the chart
    keeps a record of the hit without shouting about it.
    """
    for alert in alerts or []:
        color = ALERT_ACTIVE_COLOR if alert.active else ALERT_TRIGGERED_COLOR
        fig.add_shape(
            type="line",
            x0=x0, x1=x1, y0=alert.price, y1=alert.price,
            line=dict(color=color, width=1.6 if alert.active else 1.0, dash="dash"),
            row=row, col=1,
        )
        label = f"⏰ {alert.price:.2f}" if alert.active else f"✓ {alert.price:.2f}"
        fig.add_annotation(
            x=x1, y=alert.price,
            text=label, showarrow=False,
            xanchor="right", yshift=8,
            font=dict(size=10, color=color),
            row=row, col=1,
        )


def apply_base_layout(
    fig: go.Figure,
    title: str,
    template: str,
    height: int = 720,
    uirevision: str | None = None,
) -> None:
    """Layout boilerplate shared by both charts.

    `uirevision` preserves the user's pan/zoom across re-renders that
    don't change the subject (theme toggle, alert edits); pass the
    ticker so switching tickers still resets the view.
    """
    fig.update_layout(
        title=title,
        height=height,
        margin=dict(l=10, r=10, t=40, b=20),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template=template,
        dragmode="pan",
        hovermode="x unified",
        uirevision=uirevision,
        # Measurement tool (modebar drawline). User-drawn shapes are
        # marked editable by Plotly, which the measurement callback uses
        # to isolate them from algorithmic overlays.
        newshape=dict(line=dict(color="#0ea5e9", width=2), opacity=0.9),
    )
    fig.update_yaxes(title_text="Price", row=PRICE_ROW, col=1)


def empty_figure(message: str, template: str = "flatly") -> go.Figure:
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
