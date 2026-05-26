#!/usr/bin/env python3
"""Launcher for the daytrading chart viewer.

  .venv/bin/python run_gui.py            # default: http://127.0.0.1:8050
  .venv/bin/python run_gui.py --port 9000

The app reads the most recent rs_*.csv in output/ as its ticker list,
so run `run_daily_rs.py` first to seed the scanner output.
"""
from __future__ import annotations

import argparse

from gui.app import build_app


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8050)
    parser.add_argument("--debug", action="store_true",
                        help="Dash hot-reload + tracebacks in browser")
    args = parser.parse_args()

    app = build_app()
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
