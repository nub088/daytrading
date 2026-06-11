"""Dash page layout.

A single-page app with:
  - Header: ticker dropdown, prev/next, scanner filters,
    scanner-metadata strip.
  - Body: two side-by-side panels for the daily and 5-min charts.

All component IDs are defined as module constants so callbacks can
import them without string drift.
"""
from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dcc, html
from dash_bootstrap_templates import ThemeSwitchAIO

from . import data_loader

THEME_AIO_ID = "main-theme"

# ---- Component IDs ----
ID_TICKER_DROPDOWN = "ticker-dropdown"
ID_PREV_BTN = "prev-btn"
ID_NEXT_BTN = "next-btn"
ID_BREAKOUTS_FILTER = "breakouts-filter"
ID_MIN_RVOL_INPUT = "min-rvol-input"
ID_MIN_RS_INPUT = "min-rs-input"
ID_MAX_SMA200_AGE_INPUT = "max-sma200-age-input"
ID_DAILY_CHART = "daily-chart"
ID_INTRADAY_CHART = "intraday-chart"
ID_METADATA_BAR = "metadata-bar"
ID_MEASURE_DISPLAY = "measure-display"
ID_NEWS_BANNER = "news-banner"
ID_REFRESH_INTRADAY = "refresh-intraday"
ID_SHOW_HISTORICAL_LEVELS = "show-historical-levels"
ID_ALERT_PRICE_INPUT = "alert-price-input"
ID_ALERT_ADD_BTN = "alert-add-btn"
ID_ALERT_LIST = "alert-list"
# Monotonic counter bumped by alert add/remove; the chart-render
# callback listens to it so new alert lines appear immediately.
ID_ALERTS_VERSION = "alerts-version"


def build_layout() -> dbc.Container:
    df = data_loader.load_scanner_df()
    options = data_loader.ticker_choices(df, breakouts_only=False)
    default_value = options[0]["value"] if options else None

    header = dbc.Row(
        [
            dbc.Col(
                dcc.Dropdown(
                    id=ID_TICKER_DROPDOWN,
                    options=options,
                    value=default_value,
                    clearable=False,
                    placeholder="Pick a ticker…",
                    style={"minWidth": "260px"},
                ),
                width=3,
            ),
            dbc.Col(
                dbc.ButtonGroup(
                    [
                        dbc.Button("◀ Prev", id=ID_PREV_BTN, color="secondary", outline=True, size="sm"),
                        dbc.Button("Next ▶", id=ID_NEXT_BTN, color="secondary", outline=True, size="sm"),
                    ]
                ),
                width="auto",
            ),
            dbc.Col(
                dbc.RadioItems(
                    id=ID_BREAKOUTS_FILTER,
                    options=[
                        {"label": "All", "value": "all"},
                        {"label": "Breakouts only", "value": "breakouts"},
                    ],
                    value="all",
                    inline=True,
                    inputStyle={"marginRight": "4px", "marginLeft": "10px"},
                ),
                width="auto",
            ),
            dbc.Col(
                html.Div(
                    [
                        html.Label("Min RVol:", style={"marginRight": "6px", "fontSize": "0.85rem"}),
                        dcc.Input(
                            id=ID_MIN_RVOL_INPUT,
                            type="number",
                            placeholder="1.0",
                            min=0, step=0.1,
                            debounce=True,
                            style={"width": "80px", "fontSize": "0.85rem"},
                        ),
                    ],
                    style={"display": "flex", "alignItems": "center"},
                ),
                width="auto",
            ),
            dbc.Col(
                html.Div(
                    [
                        html.Label(
                            "Min RS:",
                            title="21-day volatility-adjusted relative strength (RRS). 2.0 ~ meaningful outperformance.",
                            style={"marginRight": "6px", "fontSize": "0.85rem"},
                        ),
                        dcc.Input(
                            id=ID_MIN_RS_INPUT,
                            type="number",
                            placeholder="2.0",
                            step=0.1,
                            debounce=True,
                            style={"width": "80px", "fontSize": "0.85rem"},
                        ),
                    ],
                    style={"display": "flex", "alignItems": "center"},
                ),
                width="auto",
            ),
            dbc.Col(
                html.Div(
                    [
                        html.Label(
                            "200 ↑ ≤",
                            title="Show only stocks where price reclaimed the 200-day SMA within the last N sessions (and is still above it). Blank = no filter.",
                            style={"marginRight": "6px", "fontSize": "0.85rem"},
                        ),
                        dcc.Input(
                            id=ID_MAX_SMA200_AGE_INPUT,
                            type="number",
                            placeholder="3d",
                            min=0, max=10, step=1,
                            debounce=True,
                            style={"width": "70px", "fontSize": "0.85rem"},
                        ),
                    ],
                    style={"display": "flex", "alignItems": "center"},
                ),
                width="auto",
            ),
            dbc.Col(
                dbc.Checklist(
                    id=ID_SHOW_HISTORICAL_LEVELS,
                    options=[{"label": "Historical S/R", "value": "show"}],
                    value=[],
                    switch=True,
                    inline=True,
                    persistence=True,
                    persistence_type="local",
                    inputStyle={"marginRight": "4px"},
                    labelStyle={"fontSize": "0.85rem"},
                ),
                width="auto",
            ),
            dbc.Col(
                dbc.Button(
                    "↻ Refresh 5m",
                    id=ID_REFRESH_INTRADAY,
                    color="secondary",
                    outline=True,
                    size="sm",
                ),
                width="auto",
            ),
            dbc.Col(
                ThemeSwitchAIO(
                    aio_id=THEME_AIO_ID,
                    themes=[dbc.themes.FLATLY, dbc.themes.DARKLY],
                    switch_props={"persistence": True, "persistence_type": "local"},
                ),
                width="auto",
            ),
        ],
        align="center",
        className="g-2 mb-2",
    )

    news_banner = dbc.Row(
        [
            dbc.Col(
                html.Div(id=ID_NEWS_BANNER, style={"fontSize": "0.85rem"}),
                width=12,
            ),
        ],
        className="mb-2",
    )

    alerts_row = dbc.Row(
        [
            dbc.Col(
                html.Div(
                    [
                        html.Label(
                            "⏰ Alert @",
                            title="Price alert for the selected ticker. Checked against "
                                  "daily bars for now; will move to live IBKR data later.",
                            style={"marginRight": "6px", "fontSize": "0.85rem", "whiteSpace": "nowrap"},
                        ),
                        dcc.Input(
                            id=ID_ALERT_PRICE_INPUT,
                            type="number",
                            placeholder="price",
                            min=0, step=0.01,
                            style={"width": "100px", "fontSize": "0.85rem"},
                        ),
                        dbc.Button(
                            "Add",
                            id=ID_ALERT_ADD_BTN,
                            color="warning",
                            outline=True,
                            size="sm",
                            style={"marginLeft": "6px"},
                        ),
                    ],
                    style={"display": "flex", "alignItems": "center"},
                ),
                width="auto",
            ),
            dbc.Col(
                html.Div(
                    id=ID_ALERT_LIST,
                    style={"display": "flex", "flexWrap": "wrap", "alignItems": "center", "gap": "6px"},
                ),
                width=True,
            ),
        ],
        align="center",
        className="g-2 mb-2",
    )

    metadata = dbc.Row(
        [
            dbc.Col(
                html.Div(id=ID_METADATA_BAR, style={"fontSize": "0.85rem"}),
                width=10,
            ),
            dbc.Col(
                html.Div(id=ID_MEASURE_DISPLAY, style={"fontSize": "0.85rem", "textAlign": "right"}),
                width=2,
            ),
        ],
        className="mb-2",
    )

    charts = dbc.Row(
        [
            dbc.Col(
                dcc.Loading(
                    dcc.Graph(
                        id=ID_DAILY_CHART,
                        config={
                            "displaylogo": False,
                            "scrollZoom": True,
                            # Measurement tool: click drawline, drag two points;
                            # eraseshape removes the line; toggle dragmode buttons
                            # let users switch between pan/draw.
                            "modeBarButtonsToAdd": ["drawline", "eraseshape"],
                        },
                        style={"height": "720px"},
                    ),
                    type="circle",
                ),
                width=6, style={"paddingRight": "4px"},
            ),
            dbc.Col(
                # position:relative so the absolutely-positioned crosshair
                # overlay stays glued to the 5m chart inside this column.
                html.Div(
                    [
                        dcc.Loading(
                            dcc.Graph(
                                id=ID_INTRADAY_CHART,
                                config={
                                    "displaylogo": False,
                                    "scrollZoom": True,
                                    "modeBarButtonsToAdd": ["drawline", "eraseshape"],
                                },
                                style={"height": "720px"},
                            ),
                            type="circle",
                        ),
                        # Crosshair line — a plain HTML overlay moved by the
                        # clientside callback. We deliberately do NOT mutate
                        # the 5m Plotly figure for this; touching shapes via
                        # Plotly.relayout at 60Hz caused the chart to jiggle.
                        html.Div(
                            id="_crosshair_overlay",
                            style={
                                "position": "absolute",
                                "left": "0",
                                "width": "0",
                                "height": "0",
                                # Solid 2px with a contrast halo so it's
                                # visible against light or dark themes
                                # and against the busy chart background.
                                "borderTop": "2px dashed #ef4444",
                                "boxShadow": "0 0 0 1px rgba(255,255,255,0.55)",
                                "pointerEvents": "none",
                                "display": "none",
                                "zIndex": 5,
                                "top": "0",
                            },
                        ),
                    ],
                    style={"position": "relative"},
                ),
                width=6, style={"paddingLeft": "4px"},
            ),
        ],
        className="g-0",
    )

    return dbc.Container(
        [
            header,
            news_banner,
            alerts_row,
            metadata,
            charts,
            # Sink for the crosshair-sync clientside callback. The callback
            # attaches DOM listeners on the daily chart and pushes price
            # updates to the 5m chart via Plotly.relayout — it never needs
            # to return real data, but Dash requires an Output.
            dcc.Store(id="_crosshair_init"),
            dcc.Store(id=ID_ALERTS_VERSION, data=0),
        ],
        fluid=True,
        style={"padding": "10px"},
    )
