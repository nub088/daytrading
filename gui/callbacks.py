"""Dash callbacks wiring the layout to data + charts.

State conventions:
  - The dropdown is the single source of truth for the current ticker.
  - Prev/Next buttons rotate through the current dropdown options.
  - The breakouts filter rebuilds the dropdown options list.
  - Earnings override is a free-text input; empty string = use yfinance
    default; an invalid date silently disables AVWAPE for that ticker.
"""
from __future__ import annotations

import pandas as pd
from dash import Input, Output, State, ctx, html, no_update
from dash_bootstrap_templates import ThemeSwitchAIO

from . import data_loader
from .charts.daily import build_daily_figure
from .charts.intraday import build_intraday_figure
from .layout import (
    ID_BREAKOUTS_FILTER,
    ID_DAILY_CHART,
    ID_EARNINGS_INPUT,
    ID_INTRADAY_CHART,
    ID_METADATA_BAR,
    ID_MIN_RS_INPUT,
    ID_MIN_RVOL_INPUT,
    ID_NEWS_BANNER,
    ID_NEXT_BTN,
    ID_PREV_BTN,
    ID_REFRESH_INTRADAY,
    ID_TICKER_DROPDOWN,
    THEME_AIO_ID,
)

# News-banner thresholds (calendar days). Inside RED, treat the event as
# imminent — Pete: reduce risk and don't open new positions.
NEWS_WINDOW_DAYS = 7
NEWS_RED_DAYS = 3


def register_callbacks(app) -> None:
    @app.callback(
        Output(ID_TICKER_DROPDOWN, "options"),
        Output(ID_TICKER_DROPDOWN, "value"),
        Input(ID_BREAKOUTS_FILTER, "value"),
        Input(ID_MIN_RVOL_INPUT, "value"),
        Input(ID_MIN_RS_INPUT, "value"),
        State(ID_TICKER_DROPDOWN, "value"),
    )
    def _refilter_dropdown(filter_mode, min_rvol, min_rs, current_value):
        df = data_loader.load_scanner_df()

        def _to_float(v):
            try:
                return float(v) if v not in (None, "") else None
            except (TypeError, ValueError):
                return None

        opts = data_loader.ticker_choices(
            df,
            breakouts_only=(filter_mode == "breakouts"),
            min_rvol=_to_float(min_rvol),
            min_rs=_to_float(min_rs),
        )
        if not opts:
            return [], None
        # Preserve current selection if still in options; otherwise pick top.
        values = {o["value"] for o in opts}
        if current_value in values:
            return opts, current_value
        return opts, opts[0]["value"]

    @app.callback(
        Output(ID_TICKER_DROPDOWN, "value", allow_duplicate=True),
        Input(ID_PREV_BTN, "n_clicks"),
        Input(ID_NEXT_BTN, "n_clicks"),
        State(ID_TICKER_DROPDOWN, "value"),
        State(ID_TICKER_DROPDOWN, "options"),
        prevent_initial_call=True,
    )
    def _rotate_selection(prev_clicks, next_clicks, current, options):
        if not options:
            return no_update
        values = [o["value"] for o in options]
        if current not in values:
            return values[0]
        idx = values.index(current)
        if ctx.triggered_id == ID_PREV_BTN:
            idx = (idx - 1) % len(values)
        elif ctx.triggered_id == ID_NEXT_BTN:
            idx = (idx + 1) % len(values)
        return values[idx]

    @app.callback(
        Output(ID_DAILY_CHART, "figure"),
        Output(ID_INTRADAY_CHART, "figure"),
        Output(ID_METADATA_BAR, "children"),
        Output(ID_NEWS_BANNER, "children"),
        Input(ID_TICKER_DROPDOWN, "value"),
        Input(ID_EARNINGS_INPUT, "value"),
        Input(ID_REFRESH_INTRADAY, "n_clicks"),
        Input(ThemeSwitchAIO.ids.switch(THEME_AIO_ID), "value"),
    )
    def _render_charts(ticker, earnings_override, refresh_clicks, theme_is_light):
        # ThemeSwitchAIO emits True for the first theme (FLATLY/light),
        # False for the second (DARKLY/dark). Default to light if unset.
        template = "flatly" if theme_is_light in (True, None) else "darkly"

        if not ticker:
            return (
                build_daily_figure("", _empty_df(), template=template),
                build_intraday_figure("", _empty_df(), template=template),
                "",
                _build_news_banner(None),
            )

        if ctx.triggered_id == ID_REFRESH_INTRADAY:
            data_loader.clear_intraday_cache(ticker)

        # ---- Daily ----
        daily_df = data_loader.load_daily(ticker)
        ed = data_loader.get_earnings_date(ticker, override=earnings_override or None)
        daily_fig = build_daily_figure(ticker, daily_df, earnings_date=ed, template=template)

        # ---- 5-min ----
        intraday_df = data_loader.load_intraday(ticker)
        intraday_fig = build_intraday_figure(ticker, intraday_df, template=template)

        # ---- Metadata bar ----
        scanner_df = data_loader.load_scanner_df()
        row = data_loader.get_scanner_row(scanner_df, ticker)
        metadata = _format_metadata(ticker, row, ed)

        # ---- News-pending banner ----
        news = _build_news_banner(ticker)
        return daily_fig, intraday_fig, metadata, news


def _empty_df():
    return pd.DataFrame()


def _warn_pill(text: str, color: str):
    return html.Span(
        text,
        style={
            "marginRight": "8px",
            "padding": "4px 10px",
            "borderRadius": "4px",
            "background": color,
            "color": "white",
            "fontWeight": 600,
            "fontSize": "0.85rem",
        },
    )


def _build_news_banner(ticker: str | None) -> list:
    """Surface pending earnings (per-ticker) and macro events (global).

    Red = inside NEWS_RED_DAYS — Pete's "don't open new positions" zone.
    Amber = inside NEWS_WINDOW_DAYS but not yet imminent — be aware.
    Green = nothing flagged inside the window.
    """
    items: list = []
    today = pd.Timestamp.now().normalize()

    # Per-ticker earnings.
    if ticker:
        ne = data_loader.get_next_earnings_date(ticker)
        if ne is not None:
            days = (ne.normalize() - today).days
            if 0 <= days <= NEWS_WINDOW_DAYS:
                color = "#dc2626" if days <= NEWS_RED_DAYS else "#d97706"
                items.append(
                    _warn_pill(
                        f"⚠ {ticker} earnings in {days}d ({ne.strftime('%a %b %d')})",
                        color,
                    )
                )

    # Global macro releases.
    for ev in data_loader.get_upcoming_macro_events(NEWS_WINDOW_DAYS):
        days = ev.days_until
        color = "#dc2626" if days <= NEWS_RED_DAYS else "#d97706"
        items.append(
            _warn_pill(
                f"⚠ {ev.label} in {days}d ({ev.when.strftime('%a %b %d')})",
                color,
            )
        )

    if not items:
        return [
            html.Span(
                f"✓ No major news inside {NEWS_WINDOW_DAYS}-day window",
                style={"color": "#16a34a", "fontSize": "0.85rem", "fontWeight": 600},
            )
        ]
    return items


def _format_metadata(ticker, row, earnings_date) -> list:
    """Render the scanner-row metadata as a row of inline pills."""
    if row is None:
        return [html.Span(f"{ticker} — not in latest scan", style={"color": "#94a3b8"})]

    def pill(label, value, color="#1e293b"):
        return html.Span(
            [html.Strong(f"{label}: ", style={"color": "#475569"}), html.Span(value)],
            style={
                "marginRight": "14px",
                "padding": "2px 8px",
                "borderRadius": "4px",
                "background": "#f1f5f9",
                "color": color,
            },
        )

    def fmt(v, n=2):
        try:
            return f"{float(v):.{n}f}"
        except (TypeError, ValueError):
            return "—"

    def pct(v):
        try:
            return f"{float(v)*100:.0f}%"
        except (TypeError, ValueError):
            return "—"

    breakout_tags = []
    if row.broke_long == 1:
        breakout_tags.append("↑ broke long")
    if row.broke_short == 1:
        breakout_tags.append("↓ broke short")
    breakout_label = " · ".join(breakout_tags) if breakout_tags else "no breakout today"
    breakout_color = "#16a34a" if row.broke_long == 1 else ("#dc2626" if row.broke_short == 1 else "#475569")

    ed_label = earnings_date.strftime("%Y-%m-%d") if earnings_date is not None else "—"

    return [
        pill("Sector", row.sector_etf),
        pill("Last", f"${fmt(row.last_price)}"),
        pill("Combined rank", pct(row.combined_rank)),
        pill("RS", pct(row.rs_simple_rank)),
        pill("RRS", pct(row.rrs_rank)),
        pill("RVol 5d", fmt(row.rvol_5d)),
        pill("Next R", f"${fmt(row.nearest_resistance)} ({fmt(row.dist_to_resistance_atr, 2)} ATR)"),
        pill("Next S", f"${fmt(row.nearest_support)} ({fmt(row.dist_to_support_atr, 2)} ATR)"),
        pill("Earnings", ed_label),
        html.Span(breakout_label, style={"marginLeft": "8px", "color": breakout_color, "fontWeight": 600}),
    ]
