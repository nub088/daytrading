"""Dash app factory.

`build_app()` returns a Dash instance configured with the project's
layout and callbacks. The launcher (`run_gui.py`) calls this and starts
the dev server.

Theming: both FLATLY (light) and DARKLY (dark) bootstrap stylesheets
are loaded, and matching Plotly figure templates are registered. The
ThemeSwitchAIO component in the header toggles between them live.
"""
from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
from dash_bootstrap_templates import load_figure_template

from .callbacks import register_callbacks
from .layout import build_layout


# Pre-register matching Plotly templates so the chart factories can name
# them ("flatly" / "darkly") on a per-figure basis.
load_figure_template(["flatly", "darkly"])


def build_app() -> dash.Dash:
    app = dash.Dash(
        __name__,
        external_stylesheets=[dbc.themes.FLATLY, dbc.themes.DARKLY],
        suppress_callback_exceptions=False,
        title="Daytrading Chart Viewer",
    )
    app.layout = build_layout()
    register_callbacks(app)
    return app
