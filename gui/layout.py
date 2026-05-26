"""Dash page layout.

A single-page app with:
  - Header: ticker dropdown, prev/next, breakouts-only filter,
    earnings-date override, scanner-metadata strip.
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
ID_EARNINGS_INPUT = "earnings-override"
ID_DAILY_CHART = "daily-chart"
ID_INTRADAY_CHART = "intraday-chart"
ID_METADATA_BAR = "metadata-bar"
ID_NEWS_BANNER = "news-banner"
ID_REFRESH_INTRADAY = "refresh-intraday"


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
                html.Div(
                    [
                        html.Label("Earnings:", style={"marginRight": "6px", "fontSize": "0.85rem"}),
                        dcc.Input(
                            id=ID_EARNINGS_INPUT,
                            type="text",
                            placeholder="YYYY-MM-DD",
                            debounce=True,
                            style={"width": "120px", "fontSize": "0.85rem"},
                        ),
                    ],
                    style={"display": "flex", "alignItems": "center"},
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

    metadata = dbc.Row(
        [
            dbc.Col(
                html.Div(id=ID_METADATA_BAR, style={"fontSize": "0.85rem"}),
                width=12,
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
                        config={"displaylogo": False, "scrollZoom": True},
                        style={"height": "720px"},
                    ),
                    type="circle",
                ),
                width=6, style={"paddingRight": "4px"},
            ),
            dbc.Col(
                dcc.Loading(
                    dcc.Graph(
                        id=ID_INTRADAY_CHART,
                        config={"displaylogo": False, "scrollZoom": True},
                        style={"height": "720px"},
                    ),
                    type="circle",
                ),
                width=6, style={"paddingLeft": "4px"},
            ),
        ],
        className="g-0",
    )

    return dbc.Container(
        [header, news_banner, metadata, charts],
        fluid=True,
        style={"padding": "10px"},
    )
