"""Central configuration: paths and scanner defaults.

All paths are derived from the repository root so the project works from
any checkout location. Override via environment variables when needed:

  DAYTRADING_TMP_DIR     base dir for disposable caches (default: <repo>/.tmp)
  DAYTRADING_OUTPUT_DIR  scan result CSVs            (default: <repo>/output)
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

TMP_DIR = Path(os.environ.get("DAYTRADING_TMP_DIR", REPO_ROOT / ".tmp"))
OUTPUT_DIR = Path(os.environ.get("DAYTRADING_OUTPUT_DIR", REPO_ROOT / "output"))

PRICE_CACHE_DIR = TMP_DIR / "prices"
UNIVERSE_CSV = TMP_DIR / "universe.csv"

# Scanner defaults (CLI flags override these)
DEFAULT_MIN_PRICE = 5.0
DEFAULT_MIN_VOLUME = 1_000_000
DEFAULT_LOOKBACK_DAYS = 400
UNIVERSE_REFRESH_DAYS = 7
