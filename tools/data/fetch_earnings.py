"""Earnings date lookup via yfinance.

`Ticker.earnings_dates` returns a DataFrame indexed by datetime, ordered
most-recent first, mixing future estimates and past actuals. We want the
most recent **past** earnings date — that's the anchor for AVWAPE on
the daily chart.

yfinance's earnings_dates is reliable for liquid large caps and spotty
on micro caps. When missing, the GUI should show a "no earnings date"
badge and skip the AVWAPE overlay rather than fail. A manual override
input lets the user supply a date directly.

The data layer is intentionally minimal so swapping in a paid source
(Polygon, Alpaca) is a one-function change.
"""
from __future__ import annotations

import pandas as pd
import yfinance as yf


def latest_earnings_date(ticker: str) -> pd.Timestamp | None:
    """Most recent past earnings date for `ticker`, or None if unavailable.

    Returned as a tz-naive Timestamp (date-only granularity is enough for
    the AVWAPE anchor — we anchor to the next trading session's open).
    """
    try:
        t = yf.Ticker(ticker)
        ed = t.earnings_dates
    except Exception:
        return None
    if ed is None or len(ed) == 0:
        return None

    idx = ed.index
    if idx.tz is not None:
        now = pd.Timestamp.now(tz=idx.tz)
    else:
        now = pd.Timestamp.now()
    past = ed[idx < now]
    if past.empty:
        return None
    most_recent = past.index[0]
    if most_recent.tz is not None:
        most_recent = most_recent.tz_convert(None) if False else most_recent.tz_localize(None)
    return most_recent.normalize()


def next_earnings_date(ticker: str) -> pd.Timestamp | None:
    """Soonest *upcoming* earnings date for `ticker`, or None if unavailable.

    The news-pending watcher uses this — distinct from
    `latest_earnings_date`, which returns the most recent past print to
    anchor AVWAPE. Pete's rule: do not hold over earnings (eBook p. 25).
    """
    try:
        t = yf.Ticker(ticker)
        ed = t.earnings_dates
    except Exception:
        return None
    if ed is None or len(ed) == 0:
        return None

    idx = ed.index
    if idx.tz is not None:
        now = pd.Timestamp.now(tz=idx.tz)
    else:
        now = pd.Timestamp.now()
    future = ed[idx >= now]
    if future.empty:
        return None
    # ed is most-recent-first, so the soonest future date is the last future row.
    soonest = future.index[-1]
    if soonest.tz is not None:
        soonest = soonest.tz_localize(None)
    return soonest.normalize()
