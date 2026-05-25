"""Bulk OHLCV fetcher using yfinance, with parquet caching.

- Initial backfill: ~1 year of daily history per ticker (configurable).
- Incremental refresh: fetch only the days since cache_last_date(ticker).
- Chunked downloads so we can resume cleanly if a chunk fails.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

from . import cache

DEFAULT_LOOKBACK_DAYS = 400
CHUNK_SIZE = 100


def _normalize_chunk(df: pd.DataFrame, tickers: list[str]) -> dict[str, pd.DataFrame]:
    """yfinance returns a MultiIndex when given >1 ticker; split into per-ticker DFs."""
    out: dict[str, pd.DataFrame] = {}
    if df.empty:
        return out
    # yfinance returns columns like (field, ticker) for batch downloads.
    if isinstance(df.columns, pd.MultiIndex):
        for t in tickers:
            if t not in df.columns.get_level_values(1):
                continue
            sub = df.xs(t, axis=1, level=1).dropna(how="all")
            if sub.empty:
                continue
            sub = sub.rename(columns=str.lower)
            sub.index.name = "date"
            out[t] = sub
    else:
        # single-ticker shape
        sub = df.dropna(how="all").rename(columns=str.lower)
        sub.index.name = "date"
        if not sub.empty:
            out[tickers[0]] = sub
    return out


def _fetch_chunk(
    tickers: list[str],
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict[str, pd.DataFrame]:
    """Single yfinance batch call for a chunk of tickers."""
    kwargs = dict(
        tickers=tickers,
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=True,
        group_by="column",
    )
    if start is not None:
        kwargs["start"] = start.strftime("%Y-%m-%d")
    if end is not None:
        kwargs["end"] = end.strftime("%Y-%m-%d")
    df = yf.download(**kwargs)
    return _normalize_chunk(df, tickers)


def backfill(
    tickers: list[str],
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    chunk_size: int = CHUNK_SIZE,
    skip_if_cached: bool = True,
    sleep_between_chunks: float = 0.5,
) -> dict[str, int]:
    """Backfill daily OHLCV for a list of tickers into the parquet cache.

    Returns a dict mapping ticker → number of rows written.
    Skips tickers that already have a cache file unless skip_if_cached=False.
    """
    end = datetime.now()
    start = end - timedelta(days=lookback_days)

    todo = [t for t in tickers if not (skip_if_cached and cache.has_cache(t))]
    written: dict[str, int] = {}
    total_chunks = (len(todo) + chunk_size - 1) // chunk_size

    for i in range(0, len(todo), chunk_size):
        chunk = todo[i : i + chunk_size]
        chunk_n = i // chunk_size + 1
        print(f"[backfill {chunk_n}/{total_chunks}] fetching {len(chunk)} tickers...")
        try:
            data = _fetch_chunk(chunk, start=start, end=end)
        except Exception as e:  # noqa: BLE001
            print(f"  CHUNK FAILED ({type(e).__name__}): {e}; retrying once after 5s")
            time.sleep(5)
            try:
                data = _fetch_chunk(chunk, start=start, end=end)
            except Exception as e2:  # noqa: BLE001
                print(f"  CHUNK FAILED AGAIN: {e2}; skipping")
                continue
        for t, df in data.items():
            cache.write(t, df)
            written[t] = len(df)
        if sleep_between_chunks:
            time.sleep(sleep_between_chunks)

    return written


def refresh(
    tickers: list[str],
    chunk_size: int = CHUNK_SIZE,
    sleep_between_chunks: float = 0.5,
) -> dict[str, int]:
    """Append the latest days to each cached ticker. Skips tickers with no cache."""
    end = datetime.now()
    grouped_by_start: dict[str, list[str]] = {}

    for t in tickers:
        last = cache.cache_last_date(t)
        if last is None:
            continue  # use backfill() for first-time tickers
        start = (last + timedelta(days=1)).strftime("%Y-%m-%d")
        grouped_by_start.setdefault(start, []).append(t)

    appended: dict[str, int] = {}
    for start_str, group in grouped_by_start.items():
        start_dt = datetime.strptime(start_str, "%Y-%m-%d")
        if start_dt.date() >= end.date():
            continue
        for i in range(0, len(group), chunk_size):
            chunk = group[i : i + chunk_size]
            try:
                data = _fetch_chunk(chunk, start=start_dt, end=end)
            except Exception as e:  # noqa: BLE001
                print(f"  refresh chunk failed: {e}; skipping")
                continue
            for t, df in data.items():
                cache.append(t, df)
                appended[t] = len(df)
            if sleep_between_chunks:
                time.sleep(sleep_between_chunks)
    return appended


if __name__ == "__main__":
    # Smoke test on a handful of liquid names
    test = ["SPY", "AAPL", "MSFT", "NVDA", "META"]
    print(f"Backfilling {test} ...")
    res = backfill(test, lookback_days=400, skip_if_cached=False)
    for t, n in res.items():
        df = cache.read(t)
        print(f"  {t}: {n} rows; date range {df.index.min().date()} → {df.index.max().date()}")
    print(f"Cache size: {cache.cache_size_mb():.1f} MB")
