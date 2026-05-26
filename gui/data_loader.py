"""Data plumbing for the GUI.

Loads the most recent scanner CSV from output/, reads daily OHLCV from
the parquet cache, fetches 5-min bars on demand, and looks up earnings
dates with an in-memory cache so navigation doesn't re-hit yfinance.

This module is the single source of truth for the GUI's data needs;
chart factories and callbacks consume from here only.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from tools.data import cache
from tools.data.fetch_earnings import latest_earnings_date, next_earnings_date
from tools.data.fetch_intraday import fetch_5min
from tools.data.macro_calendar import MacroEvent, upcoming_events

OUTPUT_DIR = Path("/home/nublet/Projects/daytrading/output")


@dataclass(frozen=True)
class ScannerRow:
    """One row from the scanner CSV — the metadata bar uses these fields."""
    ticker: str
    sector_etf: str
    last_price: float
    combined_rank: float
    broke_long: float
    broke_short: float
    rs_simple_rank: float
    rrs_rank: float
    rvol_5d: float
    nearest_resistance: float
    nearest_support: float
    dist_to_resistance_atr: float
    dist_to_support_atr: float


def latest_scanner_csv() -> Path | None:
    """Return the most recently modified rs_*.csv in output/, or None."""
    if not OUTPUT_DIR.exists():
        return None
    candidates = sorted(OUTPUT_DIR.glob("rs_*.csv"), key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


def load_scanner_df(path: Path | None = None) -> pd.DataFrame:
    """Load the scanner CSV into a DataFrame.

    Falls back to an empty frame with the expected columns if no CSV
    exists yet — lets the GUI launch cleanly before the first scan.
    """
    p = path or latest_scanner_csv()
    if p is None or not p.exists():
        return pd.DataFrame(columns=["ticker", "combined_rank", "broke_long"])
    return pd.read_csv(p)


def get_scanner_row(df: pd.DataFrame, ticker: str) -> ScannerRow | None:
    sub = df[df["ticker"] == ticker]
    if sub.empty:
        return None
    r = sub.iloc[0]

    def _f(col: str) -> float:
        v = r.get(col)
        try:
            return float(v) if pd.notna(v) else float("nan")
        except (TypeError, ValueError):
            return float("nan")

    return ScannerRow(
        ticker=ticker,
        sector_etf=str(r.get("sector_etf", "")),
        last_price=_f("last_price"),
        combined_rank=_f("combined_rank"),
        broke_long=_f("broke_long"),
        broke_short=_f("broke_short"),
        rs_simple_rank=_f("rs_simple_rank"),
        rrs_rank=_f("rrs_rank"),
        rvol_5d=_f("rvol_5d"),
        nearest_resistance=_f("nearest_resistance"),
        nearest_support=_f("nearest_support"),
        dist_to_resistance_atr=_f("dist_to_resistance_atr"),
        dist_to_support_atr=_f("dist_to_support_atr"),
    )


def load_daily(ticker: str) -> pd.DataFrame:
    """Read daily OHLCV from the parquet cache. Empty frame if missing."""
    df = cache.read(ticker)
    if df.empty:
        return df
    # Ensure index is DatetimeIndex (cache.read should already do this).
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    return df


# ---- earnings + intraday caches (in-memory; cleared on app restart) ----

_earnings_cache: dict[str, pd.Timestamp | None] = {}
_next_earnings_cache: dict[str, pd.Timestamp | None] = {}
_intraday_cache: dict[str, pd.DataFrame] = {}


def get_earnings_date(ticker: str, override: str | None = None) -> pd.Timestamp | None:
    """Latest earnings date — manual override wins, else yfinance, else None."""
    if override:
        try:
            return pd.Timestamp(override).normalize()
        except (ValueError, TypeError):
            return None
    if ticker in _earnings_cache:
        return _earnings_cache[ticker]
    ed = latest_earnings_date(ticker)
    _earnings_cache[ticker] = ed
    return ed


def get_next_earnings_date(ticker: str) -> pd.Timestamp | None:
    """Next *upcoming* earnings date, cached. Powers the news-pending banner."""
    if ticker in _next_earnings_cache:
        return _next_earnings_cache[ticker]
    ne = next_earnings_date(ticker)
    _next_earnings_cache[ticker] = ne
    return ne


def get_upcoming_macro_events(window_days: int = 7) -> list[MacroEvent]:
    """Macro releases falling inside the next `window_days` calendar days."""
    return upcoming_events(horizon_days=window_days)


def load_intraday(ticker: str, period_days: int = 60, force_refresh: bool = False) -> pd.DataFrame:
    """Fetch 5-min bars; cached for the lifetime of the process."""
    if not force_refresh and ticker in _intraday_cache:
        return _intraday_cache[ticker]
    df = fetch_5min(ticker, period_days=period_days)
    _intraday_cache[ticker] = df
    return df


def clear_intraday_cache(ticker: str | None = None) -> None:
    if ticker is None:
        _intraday_cache.clear()
    else:
        _intraday_cache.pop(ticker, None)


def ticker_choices(
    df: pd.DataFrame,
    breakouts_only: bool = False,
    min_rvol: float | None = None,
    min_rs: float | None = None,
    rvol_col: str = "rvol_21d",
    rs_col: str = "rrs_21d",
) -> list[dict]:
    """Build dropdown options sorted by combined_rank descending.

    Filters compose with AND:
      - `breakouts_only`: drop tickers with no upside/downside break today.
      - `min_rvol`: drop tickers where `rvol_col` < min_rvol (NaN excluded).
        Default rvol_col is the 21-day window (closest match to Pete's
        "20-day" RVol on the daily).
      - `min_rs`: drop tickers where `rs_col` < min_rs (NaN excluded).
        Default rs_col is the 21-day vol-adjusted RRS — its t-stat-like
        scale (~2-12 for top names) makes thresholds like 2.0 meaningful.

    Each option label includes the ticker, rank percentile, breakout
    flag, RVol, and RS (so the user sees which names are above thresholds).
    """
    if df.empty:
        return []
    work = df.copy()
    if breakouts_only:
        mask = (work.get("broke_long", 0) == 1) | (work.get("broke_short", 0) == 1)
        work = work[mask]
    if min_rvol is not None and rvol_col in work.columns:
        rv = pd.to_numeric(work[rvol_col], errors="coerce")
        work = work[rv > min_rvol]
    if min_rs is not None and rs_col in work.columns:
        rs = pd.to_numeric(work[rs_col], errors="coerce")
        work = work[rs >= min_rs]
    work = work.sort_values("combined_rank", ascending=False, na_position="last")

    options = []
    for _, row in work.iterrows():
        tkr = row["ticker"]
        rank = row.get("combined_rank", float("nan"))
        rv = row.get(rvol_col, float("nan"))
        rs = row.get(rs_col, float("nan"))
        flags = ""
        if row.get("broke_long", 0) == 1:
            flags += " ↑"
        if row.get("broke_short", 0) == 1:
            flags += " ↓"
        rank_str = f"{rank*100:.0f}%" if pd.notna(rank) else "—"
        rv_str = f" · RV {rv:.1f}" if pd.notna(rv) else ""
        rs_str = f" · RS {rs:.1f}" if pd.notna(rs) else ""
        options.append({"label": f"{tkr}  ({rank_str}){flags}{rv_str}{rs_str}", "value": tkr})
    return options
