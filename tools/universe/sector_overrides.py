"""Hand-curated sector ETF assignments that override NASDAQ's labels.

NASDAQ's screener uses coarse, sometimes-wrong sector tags. We map each
ticker to one of the eleven SPDR GICS sector ETFs because that's what
the scanner uses for sector relative-strength comparison. When NASDAQ
disagrees with GICS for a liquid, important ticker, we override here.

The most common failure modes (verified from the cached universe):

  - Communication Services (XLC) — GICS created XLC in 2018 by pulling
    media/internet names out of Tech and Discretionary. NASDAQ never
    fully caught up: META/GOOGL/GOOG land in "Technology", NFLX/DIS/WBD
    land in "Consumer Discretionary", FOX/FOXA land in "Industrials"(!).

  - TSLA — NASDAQ tags as "Industrials"; GICS sub-industry is
    Automobile Manufacturers → Consumer Discretionary (XLY).

  - NEE — NASDAQ tags NextEra Energy as "Technology"(!). It's a regulated
    utility holding company → XLU.

Add new overrides only when:
  1. The ticker is liquid enough to matter for the scanner.
  2. The GICS classification is unambiguous.
  3. NASDAQ's tag is provably wrong (not a minor disagreement).
"""
from __future__ import annotations

SECTOR_OVERRIDES: dict[str, str] = {
    # ---- Communication Services (XLC) ----
    # NASDAQ tags as Technology
    "META": "XLC",
    "GOOGL": "XLC", "GOOG": "XLC",
    "MTCH": "XLC",
    "PINS": "XLC",
    "SNAP": "XLC",
    # NASDAQ tags as Consumer Discretionary
    "NFLX": "XLC",
    "DIS": "XLC",
    "WBD": "XLC",
    "EA": "XLC", "TTWO": "XLC",
    "SPOT": "XLC",
    "LYV": "XLC",
    # NASDAQ tags as Industrials
    "FOX": "XLC", "FOXA": "XLC",
    # Not in current NASDAQ universe but worth recording for stability
    "PARA": "XLC",
    "NWS": "XLC", "NWSA": "XLC",

    # ---- Consumer Discretionary (XLY) ----
    # NASDAQ tags TSLA as Industrials
    "TSLA": "XLY",
    # NASDAQ tags as Technology
    "PDD": "XLY",

    # ---- Utilities (XLU) ----
    # NASDAQ tags NEE as Technology
    "NEE": "XLU",
}
