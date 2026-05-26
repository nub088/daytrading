"""Sector classification + sector-ETF mapping.

NASDAQ uses 12 sector labels; we map them to the 11 GICS sector ETFs the
author favours, plus SPY as the overall market reference.

Sector ETFs:
  XLE Energy, XLU Utilities, XLK Technology, XLB Materials, XLP Staples,
  XLY Discretionary, XLI Industrials, XLC Communication Services,
  XLV Health Care, XLF Financials, XLRE Real Estate

NASDAQ's "Telecommunications" maps to XLC (Communication Services).
NASDAQ's "Miscellaneous" has no clean ETF analog → falls back to SPY.
"""
from __future__ import annotations

from .. import data  # noqa: F401  (ensures tools/data is a package)
from ..data.fetch_universe import load_universe
from .sector_overrides import SECTOR_OVERRIDES

MARKET_REF = "SPY"

# Eleven GICS sector ETFs
SECTOR_ETFS = (
    "XLE", "XLU", "XLK", "XLB", "XLP",
    "XLY", "XLI", "XLC", "XLV", "XLF", "XLRE",
)

# NASDAQ sector label → sector ETF
NASDAQ_TO_ETF: dict[str, str] = {
    "Energy": "XLE",
    "Utilities": "XLU",
    "Technology": "XLK",
    "Basic Materials": "XLB",
    "Consumer Staples": "XLP",
    "Consumer Discretionary": "XLY",
    "Industrials": "XLI",
    "Telecommunications": "XLC",
    "Health Care": "XLV",
    "Finance": "XLF",
    "Real Estate": "XLRE",
    # "Miscellaneous" intentionally absent → SPY fallback
}


def ticker_to_sector_etf() -> dict[str, str]:
    """Return a mapping of every cached universe ticker → its sector ETF
    (or MARKET_REF if no clean sector mapping).

    Hand-curated overrides in SECTOR_OVERRIDES take precedence over the
    NASDAQ sector tag, since NASDAQ's labels disagree with GICS for many
    large caps (notably XLC siblings, TSLA, NEE).
    """
    rows = load_universe()
    mapping: dict[str, str] = {}
    for r in rows:
        sym = (r.get("symbol") or "").strip().upper()
        if not sym:
            continue
        if sym in SECTOR_OVERRIDES:
            mapping[sym] = SECTOR_OVERRIDES[sym]
            continue
        sec = (r.get("sector") or "").strip()
        mapping[sym] = NASDAQ_TO_ETF.get(sec, MARKET_REF)
    return mapping


def reference_tickers() -> list[str]:
    """All tickers we always need price data for (SPY + 11 sector ETFs)."""
    return [MARKET_REF, *SECTOR_ETFS]


if __name__ == "__main__":
    m = ticker_to_sector_etf()
    print(f"Mapped {len(m)} tickers")
    from collections import Counter
    c = Counter(m.values())
    for etf, n in c.most_common():
        print(f"  {etf}: {n}")
    print(f"Reference tickers: {reference_tickers()}")
