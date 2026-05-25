"""Fetch the US-listed equities universe from NASDAQ's public screener API.

Returns one row per ticker with: symbol, name, last_sale, market_cap, sector,
industry, country, ipo_year, volume, exchange.

Cache to .tmp/universe.csv; refresh weekly by default.
"""
from __future__ import annotations

import csv
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

UNIVERSE_CSV = Path("/home/nublet/Projects/daytrading/.tmp/universe.csv")
REFRESH_DAYS = 7

NASDAQ_URL = "https://api.nasdaq.com/api/screener/stocks"
NASDAQ_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.nasdaq.com",
    "Referer": "https://www.nasdaq.com/",
}


def _fetch_exchange(exchange: str) -> list[dict]:
    """Fetch all common-stock listings for one exchange (NYSE | NASDAQ | AMEX)."""
    params = {
        "tableonly": "true",
        "limit": "25000",
        "exchange": exchange,
        "download": "true",
    }
    resp = requests.get(NASDAQ_URL, params=params, headers=NASDAQ_HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", {}).get("rows", []) or []


def fetch_universe_fresh() -> list[dict]:
    """Fetch the union of NYSE + NASDAQ + AMEX common stocks."""
    rows = []
    seen = set()
    for ex in ("nyse", "nasdaq", "amex"):
        for row in _fetch_exchange(ex):
            sym = (row.get("symbol") or "").strip().upper()
            if not sym or sym in seen:
                continue
            seen.add(sym)
            row["exchange"] = ex.upper()
            rows.append(row)
        time.sleep(0.5)
    return rows


def _cache_age_days() -> float | None:
    if not UNIVERSE_CSV.exists():
        return None
    mtime = datetime.fromtimestamp(UNIVERSE_CSV.stat().st_mtime)
    return (datetime.now() - mtime).total_seconds() / 86400


def load_universe(force_refresh: bool = False) -> list[dict]:
    """Return cached universe; refresh from NASDAQ if older than REFRESH_DAYS."""
    age = _cache_age_days()
    if not force_refresh and age is not None and age < REFRESH_DAYS:
        with UNIVERSE_CSV.open(newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    rows = fetch_universe_fresh()
    if not rows:
        raise RuntimeError("NASDAQ screener returned no rows")

    UNIVERSE_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({k for r in rows for k in r.keys()})
    with UNIVERSE_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    return rows


if __name__ == "__main__":
    rows = load_universe(force_refresh=True)
    print(f"Fetched {len(rows)} unique tickers")
    by_ex = {}
    for r in rows:
        by_ex[r["exchange"]] = by_ex.get(r["exchange"], 0) + 1
    for ex, n in sorted(by_ex.items()):
        print(f"  {ex}: {n}")
    print(f"Cached to {UNIVERSE_CSV}")
