"""5-minute bar fetcher (yfinance).

yfinance only serves 5-min history for the last 60 days — a hard limit
on its free endpoint. That's plenty for momentum chart reading on
today's breakouts. Deeper history would need Polygon/Alpaca/IBKR.

No on-disk cache for v1: 5-min data updates intraday, so caching adds
staleness risk. A single ticker fetch is ~1-2 seconds; we only ever
fetch one ticker at a time (on user click in the GUI), so refetching
each click is acceptable.

Returns a DataFrame with lowercase OHLCV columns and a tz-naive
DatetimeIndex in the exchange local time (Yahoo returns market time).
"""
from __future__ import annotations

import pandas as pd
import yfinance as yf


def fetch_5min(ticker: str, period_days: int = 60) -> pd.DataFrame:
    """Fetch 5-minute bars for the most recent `period_days`.

    `period_days` is clamped to [1, 60] — yfinance's hard limit.
    """
    period_days = max(1, min(60, int(period_days)))
    df = yf.download(
        tickers=ticker,
        period=f"{period_days}d",
        interval="5m",
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    if df is None or df.empty:
        return pd.DataFrame()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [str(c[0]).lower() for c in df.columns]
    else:
        df = df.rename(columns=str.lower)

    keep = [c for c in ("open", "high", "low", "close", "volume") if c in df.columns]
    df = df[keep].dropna(how="all")
    # Drop tz info so downstream date/time work is consistent.
    if df.index.tz is not None:
        df.index = df.index.tz_convert("America/New_York").tz_localize(None)
    df.index.name = "datetime"
    return df
