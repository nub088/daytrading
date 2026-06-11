"""Dash callbacks wiring the layout to data + charts.

State conventions:
  - The dropdown is the single source of truth for the current ticker.
  - Prev/Next buttons rotate through the current dropdown options.
  - The breakouts filter rebuilds the dropdown options list.
  - Earnings warnings and chart event markers are sourced from yfinance.
"""
from __future__ import annotations

import pandas as pd
from dash import ALL, Input, Output, State, ctx, html, no_update
from dash_bootstrap_templates import ThemeSwitchAIO

from tools import alerts as alerts_store

from . import data_loader
from .charts.daily import build_daily_figure
from .charts.intraday import build_intraday_figure
from .layout import (
    ID_ALERT_ADD_BTN,
    ID_ALERT_LIST,
    ID_ALERT_PRICE_INPUT,
    ID_ALERTS_VERSION,
    ID_BREAKOUTS_FILTER,
    ID_DAILY_CHART,
    ID_INTRADAY_CHART,
    ID_MAX_SMA200_AGE_INPUT,
    ID_MEASURE_DISPLAY,
    ID_METADATA_BAR,
    ID_MIN_RS_INPUT,
    ID_MIN_RVOL_INPUT,
    ID_NEWS_BANNER,
    ID_NEXT_BTN,
    ID_PREV_BTN,
    ID_REFRESH_INTRADAY,
    ID_SHOW_HISTORICAL_LEVELS,
    ID_TICKER_DROPDOWN,
    THEME_AIO_ID,
)

# News-banner thresholds (calendar days). Inside RED, treat the event as
# imminent — Pete: reduce risk and don't open new positions.
NEWS_WINDOW_DAYS = 7
NEWS_RED_DAYS = 3


def register_callbacks(app) -> None:
    _register_crosshair_sync(app)
    _register_measurement_tool(app)
    _register_alerts(app)

    @app.callback(
        Output(ID_TICKER_DROPDOWN, "options"),
        Output(ID_TICKER_DROPDOWN, "value"),
        Input(ID_BREAKOUTS_FILTER, "value"),
        Input(ID_MIN_RVOL_INPUT, "value"),
        Input(ID_MIN_RS_INPUT, "value"),
        Input(ID_MAX_SMA200_AGE_INPUT, "value"),
        State(ID_TICKER_DROPDOWN, "value"),
    )
    def _refilter_dropdown(filter_mode, min_rvol, min_rs, max_sma200_age, current_value):
        df = data_loader.load_scanner_df()

        def _to_float(v):
            try:
                return float(v) if v not in (None, "") else None
            except (TypeError, ValueError):
                return None

        def _to_int(v):
            try:
                return int(v) if v not in (None, "") else None
            except (TypeError, ValueError):
                return None

        opts = data_loader.ticker_choices(
            df,
            breakouts_only=(filter_mode == "breakouts"),
            min_rvol=_to_float(min_rvol),
            min_rs=_to_float(min_rs),
            max_sma200_age=_to_int(max_sma200_age),
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
        Output(ID_ALERT_LIST, "children"),
        Input(ID_TICKER_DROPDOWN, "value"),
        Input(ID_REFRESH_INTRADAY, "n_clicks"),
        Input(ID_SHOW_HISTORICAL_LEVELS, "value"),
        Input(ThemeSwitchAIO.ids.switch(THEME_AIO_ID), "value"),
        Input(ID_ALERTS_VERSION, "data"),
    )
    def _render_charts(ticker, refresh_clicks, historical_levels, theme_is_light, _alerts_version):
        # ThemeSwitchAIO emits True for the first theme (FLATLY/light),
        # False for the second (DARKLY/dark). Default to light if unset.
        template = "flatly" if theme_is_light in (True, None) else "darkly"

        if not ticker:
            return (
                build_daily_figure("", _empty_df(), template=template),
                build_intraday_figure("", _empty_df(), template=template),
                "",
                _build_news_banner(None),
                [],
            )

        if ctx.triggered_id == ID_REFRESH_INTRADAY:
            data_loader.clear_intraday_cache(ticker)
            data_loader.clear_intraday_cache("SPY")

        # ---- Daily ----
        daily_df = data_loader.load_daily(ticker)
        market_df = data_loader.load_daily("SPY")
        ed = data_loader.get_earnings_date(ticker)
        ticker_alerts = _refresh_ticker_alerts(ticker, daily_df)
        daily_fig = build_daily_figure(
            ticker,
            daily_df,
            market_ohlcv=market_df,
            earnings_date=ed,
            template=template,
            show_historical_levels="show" in (historical_levels or []),
            alerts=ticker_alerts,
        )

        # ---- 5-min ----
        intraday_df = data_loader.load_intraday(ticker)
        intraday_market_df = data_loader.load_intraday("SPY")
        intraday_fig = build_intraday_figure(
            ticker,
            intraday_df,
            market_ohlcv=intraday_market_df,
            template=template,
            alerts=ticker_alerts,
        )

        # ---- Metadata bar ----
        scanner_df = data_loader.load_scanner_df()
        row = data_loader.get_scanner_row(scanner_df, ticker)
        metadata = _format_metadata(ticker, row, ed)

        # ---- News-pending banner ----
        news = _build_news_banner(ticker, daily_ohlcv=daily_df)
        return daily_fig, intraday_fig, metadata, news, _render_alert_pills(ticker_alerts)


def _register_alerts(app) -> None:
    """Price-alert add/remove. Both bump the alerts-version store, which
    the chart-render callback listens to, so lines and pills refresh in
    one round trip."""

    @app.callback(
        Output(ID_ALERTS_VERSION, "data"),
        Output(ID_ALERT_PRICE_INPUT, "value"),
        Input(ID_ALERT_ADD_BTN, "n_clicks"),
        State(ID_ALERT_PRICE_INPUT, "value"),
        State(ID_TICKER_DROPDOWN, "value"),
        State(ID_ALERTS_VERSION, "data"),
        prevent_initial_call=True,
    )
    def _add_alert(_clicks, price, ticker, version):
        if not ticker or price in (None, ""):
            return no_update, no_update
        try:
            alerts_store.add_alert(ticker, price)
        except ValueError:
            return no_update, no_update
        return (version or 0) + 1, None  # clear the input on success

    @app.callback(
        Output(ID_ALERTS_VERSION, "data", allow_duplicate=True),
        Input({"type": "alert-remove", "id": ALL}, "n_clicks"),
        State(ID_ALERTS_VERSION, "data"),
        prevent_initial_call=True,
    )
    def _remove_alert(n_clicks_list, version):
        # Pattern-matching callbacks also fire when pills are (re)created
        # with n_clicks=0 — only a real click should delete.
        if not isinstance(ctx.triggered_id, dict) or not any(n_clicks_list or []):
            return no_update
        if not alerts_store.remove_alert(str(ctx.triggered_id.get("id"))):
            return no_update
        return (version or 0) + 1


def _refresh_ticker_alerts(ticker: str, daily_ohlcv: pd.DataFrame) -> list[alerts_store.PriceAlert]:
    """Run the EOD trigger check against the latest daily bar, then return
    the ticker's alerts with up-to-date triggered state.

    With end-of-day data this is the best we can do; once the live IBRK
    feed lands, `check_alerts` gets called per tick instead.
    """
    if not daily_ohlcv.empty:
        bar = daily_ohlcv.iloc[-1]
        try:
            alerts_store.check_alerts(
                ticker,
                bar_high=float(bar["high"]),
                bar_low=float(bar["low"]),
                as_of=pd.Timestamp(daily_ohlcv.index[-1]).isoformat(),
            )
        except (TypeError, ValueError, KeyError):
            pass
    return alerts_store.alerts_for(ticker)


def _render_alert_pills(ticker_alerts: list[alerts_store.PriceAlert]) -> list:
    """Inline pills for the alert row: amber while armed, slate once hit."""
    if not ticker_alerts:
        return [html.Span("no alerts for this ticker", style={"color": "#94a3b8", "fontSize": "0.8rem"})]
    pills = []
    for a in sorted(ticker_alerts, key=lambda a: a.price):
        if a.active:
            bg = "#f59e0b"
            label = f"⏰ {a.price:.2f}"
        else:
            bg = "#64748b"
            label = f"✓ hit {a.price:.2f}"
        pills.append(
            html.Span(
                [
                    html.Span(label, style={"marginRight": "6px"}),
                    html.Button(
                        "×",
                        id={"type": "alert-remove", "id": a.id},
                        n_clicks=0,
                        title="Remove alert",
                        style={
                            "border": "none",
                            "background": "transparent",
                            "color": "white",
                            "cursor": "pointer",
                            "fontWeight": 700,
                            "padding": "0",
                            "lineHeight": "1",
                        },
                    ),
                ],
                style={
                    "padding": "3px 8px",
                    "borderRadius": "4px",
                    "background": bg,
                    "color": "white",
                    "fontWeight": 600,
                    "fontSize": "0.8rem",
                    "display": "inline-flex",
                    "alignItems": "center",
                },
            )
        )
    return pills


def _register_measurement_tool(app) -> None:
    """Toolbar drawline (on either chart) → ΔPrice / Δ% / Δtime pill.

    User-drawn shapes are marked `editable=True` by Plotly's drawline
    tool; algorithmically-added levels are not. We pick the most recent
    editable shape from whichever chart fired the relayout and compute
    endpoint deltas. The time-delta format follows the chart's bar
    period (Δd for daily, Δh/Δm for 5-min).
    """
    @app.callback(
        Output(ID_MEASURE_DISPLAY, "children"),
        Input(ID_DAILY_CHART, "relayoutData"),
        Input(ID_INTRADAY_CHART, "relayoutData"),
        State(ID_DAILY_CHART, "figure"),
        State(ID_INTRADAY_CHART, "figure"),
        prevent_initial_call=True,
    )
    def _measure(_d_relayout, _i_relayout, d_fig, i_fig):
        is_intraday = ctx.triggered_id == ID_INTRADAY_CHART
        fig = i_fig if is_intraday else d_fig
        if not fig:
            return ""
        shapes = (fig.get("layout") or {}).get("shapes") or []
        user_shapes = [s for s in shapes if s.get("editable")]
        if not user_shapes:
            return ""
        s = user_shapes[-1]
        try:
            y0 = float(s["y0"])
            y1 = float(s["y1"])
        except (KeyError, TypeError, ValueError):
            return ""
        dy = y1 - y0
        pct = (dy / y0 * 100) if y0 else 0.0
        time_label = ""
        try:
            x0 = pd.to_datetime(s["x0"])
            x1 = pd.to_datetime(s["x1"])
            delta = abs(x1 - x0)
            if is_intraday:
                total_min = int(round(delta.total_seconds() / 60))
                if total_min >= 60:
                    h, m = divmod(total_min, 60)
                    time_label = f"  ·  Δ{h}h{m:02d}m"
                else:
                    time_label = f"  ·  Δ{total_min}m"
            else:
                # Daily bars ≈ calendar days minus weekends; show
                # calendar-day delta — close enough for swing context.
                time_label = f"  ·  Δ{int(delta.days)}d"
        except (KeyError, TypeError, ValueError):
            pass
        sign_color = "#16a34a" if dy >= 0 else "#dc2626"
        return html.Span(
            f"Δ${dy:+.2f}  ({pct:+.2f}%){time_label}",
            style={
                "padding": "4px 10px",
                "background": sign_color,
                "color": "white",
                "borderRadius": "4px",
                "fontWeight": 600,
                "fontSize": "0.85rem",
            },
        )


def _register_crosshair_sync(app) -> None:
    """Mirror the D1 cursor price as a horizontal line over the 5m chart.

    Architecture: the crosshair is a plain HTML <div> (`_crosshair_overlay`,
    a sibling of the 5m Graph inside a position:relative container) whose
    `top` is updated on every mousemove. We do NOT call Plotly.relayout
    on the 5m chart — that triggers the full Plotly relayout pipeline at
    60Hz, which caused the chart to visibly thrash (axis re-evaluation,
    rangebreak recompute, drag layer rebuild). The overlay decouples the
    crosshair from chart state entirely.

    Math:
      cursor pixel Y on D1 price pane
        → D1 price via dailyChart._fullLayout.yaxis.p2c(offsetY)
        → vertical fraction on 5m price pane via linear interpolation
          over fiveChart._fullLayout.yaxis.range
        → CSS top on the overlay, anchored to the 5m price drag layer's
          getBoundingClientRect (handles pan/zoom: range changes are
          reflected on the next mousemove).

    Trigger fires on D1 figure changes (ticker / theme) to (re-)attach
    the mousemove listener if Plotly replaced the drag layer DOM node.
    A flag on the element keeps the attach idempotent.
    """
    app.clientside_callback(
        """
        function(_figure) {
            requestAnimationFrame(function() {
                const dailyWrap = document.getElementById('daily-chart');
                const fiveWrap = document.getElementById('intraday-chart');
                const overlay = document.getElementById('_crosshair_overlay');
                if (!dailyWrap || !fiveWrap || !overlay) return;
                const dailyChart = dailyWrap.querySelector('.js-plotly-plot');
                const fiveChart = fiveWrap.querySelector('.js-plotly-plot');
                if (!dailyChart || !fiveChart) return;
                if (!dailyChart._fullLayout) return;

                // Row 1 (price pane) drag layer; ignore the volume pane.
                const priceDrag = dailyChart.querySelector('[data-subplot="xy"]');
                if (!priceDrag) return;
                if (priceDrag.__crosshairAttached) return;
                priceDrag.__crosshairAttached = true;

                const overlayParent = overlay.parentElement;
                let pendingPrice = null;
                let frameScheduled = false;

                function flush() {
                    frameScheduled = false;
                    if (pendingPrice == null || !isFinite(pendingPrice)) return;
                    const fiveYaxis = fiveChart._fullLayout && fiveChart._fullLayout.yaxis;
                    const fivePriceDrag = fiveChart.querySelector('[data-subplot="xy"]');
                    if (!fiveYaxis || !fivePriceDrag || !overlayParent) return;
                    const range = fiveYaxis.range;
                    if (!range || range.length !== 2) return;
                    const ymin = +range[0], ymax = +range[1];
                    if (!isFinite(ymin) || !isFinite(ymax) || ymax === ymin) return;

                    const dragRect = fivePriceDrag.getBoundingClientRect();
                    const parentRect = overlayParent.getBoundingClientRect();
                    // fraction: 0 at top of pane (ymax), 1 at bottom (ymin).
                    // Clamp to [0, 1] so the line pins to the chart edge when
                    // the cursor's D1 price is outside the 5m visible range —
                    // user still gets a "price is above/below" visual cue
                    // instead of the line silently disappearing.
                    const rawFrac = (ymax - pendingPrice) / (ymax - ymin);
                    const fraction = Math.max(0, Math.min(1, rawFrac));
                    const topPx = (dragRect.top - parentRect.top) + fraction * dragRect.height;
                    const leftPx = dragRect.left - parentRect.left;

                    overlay.style.top = topPx + 'px';
                    overlay.style.left = leftPx + 'px';
                    overlay.style.width = dragRect.width + 'px';
                    overlay.style.display = 'block';
                }

                priceDrag.addEventListener('mousemove', function(ev) {
                    const yaxis = dailyChart._fullLayout && dailyChart._fullLayout.yaxis;
                    if (!yaxis || typeof yaxis.p2c !== 'function') return;
                    // event.offsetY on SVG elements is canvas-relative
                    // (offsetParent quirk), not target-relative, so it includes
                    // the chart's top margin. Use clientY minus the drag
                    // rect's top to get a true plot-area-relative pixel.
                    const r = priceDrag.getBoundingClientRect();
                    pendingPrice = yaxis.p2c(ev.clientY - r.top);
                    if (frameScheduled) return;
                    frameScheduled = true;
                    requestAnimationFrame(flush);
                });
                priceDrag.addEventListener('mouseleave', function() {
                    pendingPrice = null;
                    overlay.style.display = 'none';
                });
            });
            return window.dash_clientside.no_update;
        }
        """,
        Output("_crosshair_init", "data"),
        Input(ID_DAILY_CHART, "figure"),
    )


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


def _build_news_banner(
    ticker: str | None,
    daily_ohlcv: pd.DataFrame | None = None,
) -> list:
    """Surface earnings context (per-ticker) and macro events (global).

    Red = imminent upcoming earnings, or a large post-earnings move.
    Amber = earnings/news inside the broader watch window.
    Green = nothing flagged inside the window.
    """
    items: list = []
    today = pd.Timestamp.now().normalize()

    # Per-ticker earnings. Upcoming earnings warns against holding through
    # binary risk; recent past earnings flags that price may be moving because
    # of the report.
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

        ed = data_loader.get_earnings_date(ticker)
        if ed is not None:
            days_ago = (today - ed.normalize()).days
            if 0 <= days_ago <= NEWS_WINDOW_DAYS:
                move = _post_earnings_move(daily_ohlcv, ed)
                if move is None:
                    label = f"⚠ {ticker} reported earnings {days_ago}d ago ({ed.strftime('%a %b %d')})"
                    color = "#d97706"
                else:
                    move_label = f"{move:+.1f}%"
                    label = (
                        f"⚠ {ticker} post-earnings move {move_label} "
                        f"since {ed.strftime('%a %b %d')}"
                    )
                    color = "#dc2626" if abs(move) >= 5 else "#d97706"
                items.append(_warn_pill(label, color))

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


def _post_earnings_move(daily_ohlcv: pd.DataFrame | None, earnings_date: pd.Timestamp) -> float | None:
    """Return close-to-close % move from the prior bar to the earnings bar.

    Uses the first trading bar on or after the earnings date because reports
    can land before the open, after the close, or on non-trading days.
    """
    if daily_ohlcv is None or daily_ohlcv.empty or "close" not in daily_ohlcv.columns:
        return None
    work = daily_ohlcv.sort_index()
    if not isinstance(work.index, pd.DatetimeIndex):
        work = work.copy()
        work.index = pd.to_datetime(work.index)
    closes = work["close"].dropna()
    if closes.empty:
        return None
    normalized_index = closes.index.normalize()
    candidates = normalized_index >= pd.Timestamp(earnings_date).normalize()
    if not candidates.any():
        return None
    event_pos = int(candidates.argmax())
    if event_pos == 0:
        return None
    prev_close = float(closes.iloc[event_pos - 1])
    event_close = float(closes.iloc[event_pos])
    if prev_close == 0:
        return None
    return (event_close / prev_close - 1.0) * 100.0


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
