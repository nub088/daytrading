"""Parquet cache for per-ticker OHLCV history.

Layout: one parquet file per ticker at .tmp/prices/<TICKER>.parquet
Columns: open, high, low, close, volume, adj_close
Index: date (datetime64[ns])
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from tools.config import PRICE_CACHE_DIR as CACHE_DIR


def cache_path(ticker: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{ticker.upper()}.parquet"


def has_cache(ticker: str) -> bool:
    return cache_path(ticker).exists()


def cache_last_date(ticker: str) -> datetime | None:
    """Most recent date in the cache; None if no cache or empty."""
    p = cache_path(ticker)
    if not p.exists():
        return None
    df = pd.read_parquet(p, columns=[])
    if df.empty:
        return None
    return df.index.max().to_pydatetime()


def read(ticker: str) -> pd.DataFrame:
    """Read full price history for a ticker. Returns empty DF if no cache."""
    p = cache_path(ticker)
    if not p.exists():
        return pd.DataFrame()
    return pd.read_parquet(p)


def write(ticker: str, df: pd.DataFrame) -> None:
    """Write/overwrite full history for a ticker."""
    if df.empty:
        return
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    df.to_parquet(cache_path(ticker), compression="snappy")


def append(ticker: str, df_new: pd.DataFrame) -> None:
    """Append new rows to existing cache, deduping on date."""
    if df_new.empty:
        return
    existing = read(ticker)
    if existing.empty:
        write(ticker, df_new)
        return
    combined = pd.concat([existing, df_new])
    combined = combined.sort_index()
    combined = combined[~combined.index.duplicated(keep="last")]
    combined.to_parquet(cache_path(ticker), compression="snappy")


def list_cached_tickers() -> list[str]:
    return sorted(p.stem for p in CACHE_DIR.glob("*.parquet"))


def cache_size_mb() -> float:
    total = sum(p.stat().st_size for p in CACHE_DIR.glob("*.parquet"))
    return total / (1024 * 1024)
