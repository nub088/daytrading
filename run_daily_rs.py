#!/usr/bin/env python3
"""Daily Relative Strength scan orchestrator.

Pipeline:
  1. Load universe (cached NASDAQ screener).
  2. Refresh price cache (backfill new tickers + append latest day).
  3. Apply cheap filters (min_price, min_volume).
  4. Compute indicators (SMA stack, ATR%, AVWAPQ).
  5. Apply optional directional filters (above_sma_*, above_avwapq).
  6. Compute signals (RS simple, RRS, sector RS).
  7. Rank + combine.
  8. Write filtered CSV.

Run with:
  .venv/bin/python run_daily_rs.py             # full universe
  .venv/bin/python run_daily_rs.py --smoke     # tiny test (~50 tickers)
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from tools.data import cache, fetch_prices
from tools.data.fetch_universe import load_universe
from tools.universe.sectors import (
    MARKET_REF,
    SECTOR_ETFS,
    reference_tickers,
    ticker_to_sector_etf,
)
from tools.indicators.sma import sma_latest
from tools.indicators.atr import atr_pct_latest
from tools.indicators.avwap import avwapq_latest
from tools.filters.min_price import MinPriceFilter
from tools.filters.min_volume import MinVolumeFilter
from tools.filters.above_sma import AboveSMAFilter
from tools.filters.above_avwapq import AboveAVWAPQFilter
from tools.filters.compose import AndFilter
from tools.signals.rs_simple import RSSimple
from tools.signals.rs_vol_adjusted import RSVolAdjusted
from tools.signals.rs_sector import RSSector
from tools.signals.rvol import RVol
from tools.signals.rrv import RRV
from tools.signals.breakouts import Breakouts
from tools.ranking.combine import add_percentile_ranks
from tools.output.to_csv import write_csv
from tools.config import (
    OUTPUT_DIR,
    DEFAULT_MIN_PRICE,
    DEFAULT_MIN_VOLUME,
    DEFAULT_LOOKBACK_DAYS,
)


def _print_step(n: int, msg: str) -> None:
    print(f"\n[{n}] {msg}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="Run on ~50 tickers only")
    parser.add_argument("--min-price", type=float, default=DEFAULT_MIN_PRICE)
    parser.add_argument("--min-volume", type=int, default=DEFAULT_MIN_VOLUME)
    parser.add_argument("--above-sma", action="store_true",
                        help="Require last close above SMA(20/50/100/200)")
    parser.add_argument("--above-avwapq", action="store_true",
                        help="Require last close above AVWAPQ")
    parser.add_argument("--breakouts-long", action="store_true",
                        help="Only keep tickers that broke a level to the upside today")
    parser.add_argument("--breakouts-short", action="store_true",
                        help="Only keep tickers that broke a level to the downside today")
    parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument("--no-refresh", action="store_true",
                        help="Skip price refresh; use existing cache only")
    parser.add_argument("--output", type=str, default=None,
                        help="Output CSV path (default: output/rs_<DATE>.csv)")
    args = parser.parse_args(argv)

    t0 = time.time()

    # ---------- 1. Universe ----------
    _print_step(1, "Loading universe...")
    universe_rows = load_universe()
    sector_map = ticker_to_sector_etf()
    all_tickers = sorted(sector_map.keys())
    print(f"  Loaded {len(all_tickers)} tickers from NASDAQ screener cache")

    if args.smoke:
        # ~50 liquid names spanning multiple sectors
        smoke_set = [
            "SPY", "QQQ", "IWM",
            *SECTOR_ETFS,
            "AAPL", "MSFT", "NVDA", "META", "GOOGL", "AMZN", "TSLA", "AVGO",
            "JPM", "BAC", "WFC", "GS", "MS",
            "XOM", "CVX", "COP",
            "JNJ", "PFE", "UNH", "LLY",
            "WMT", "COST", "HD", "LOW",
            "PG", "KO", "PEP",
            "CAT", "DE", "HON", "BA",
            "NEE", "DUK",
            "PLD", "AMT",
            "DIS", "NFLX",
        ]
        tickers_to_process = [t for t in smoke_set if t in sector_map]
        # Make sure reference tickers are always included
        for ref in reference_tickers():
            if ref not in tickers_to_process:
                tickers_to_process.append(ref)
        print(f"  SMOKE TEST: using {len(tickers_to_process)} tickers")
    else:
        tickers_to_process = all_tickers
        # Ensure reference tickers in process list
        for ref in reference_tickers():
            if ref not in tickers_to_process:
                tickers_to_process.append(ref)

    # ---------- 2. Price refresh ----------
    if not args.no_refresh:
        _print_step(2, "Backfilling missing tickers...")
        missing = [t for t in tickers_to_process if not cache.has_cache(t)]
        if missing:
            print(f"  {len(missing)} tickers need backfill")
            fetch_prices.backfill(missing, lookback_days=args.lookback_days,
                                  skip_if_cached=True)
        else:
            print("  All tickers already cached")

        _print_step(3, "Appending latest day for existing tickers...")
        existing = [t for t in tickers_to_process if cache.has_cache(t)]
        if existing:
            appended = fetch_prices.refresh(existing)
            print(f"  Appended new rows for {len(appended)} tickers")
    else:
        _print_step(2, "Skipping price refresh (--no-refresh)")

    # ---------- 3. Cheap filters ----------
    _print_step(4, "Applying cheap filters (min_price, min_volume)...")
    cheap_filters = [
        MinPriceFilter(args.min_price),
        MinVolumeFilter(args.min_volume, period=20),
    ]
    cheap = AndFilter(cheap_filters)

    survivors: list[tuple[str, pd.DataFrame]] = []
    # Don't filter out the references — we need them for RS
    refs = set(reference_tickers())
    for t in tickers_to_process:
        df = cache.read(t)
        if df.empty:
            continue
        if t in refs:
            survivors.append((t, df))
            continue
        if cheap.passes(df):
            survivors.append((t, df))
    print(f"  {len(survivors)} of {len(tickers_to_process)} passed "
          f"(min_price=${args.min_price}, min_vol={args.min_volume:,})")

    # ---------- 4. Directional filters (optional) ----------
    if args.above_sma or args.above_avwapq:
        _print_step(5, "Applying directional filters...")
        dir_filters: list = []
        if args.above_sma:
            dir_filters.extend([
                AboveSMAFilter(20), AboveSMAFilter(50),
                AboveSMAFilter(100), AboveSMAFilter(200),
            ])
        if args.above_avwapq:
            dir_filters.append(AboveAVWAPQFilter())
        dir_chain = AndFilter(dir_filters)
        before = len(survivors)
        survivors = [
            (t, df) for (t, df) in survivors
            if t in refs or dir_chain.passes(df)
        ]
        print(f"  {len(survivors)} of {before} passed directional filters")

    # Need market + sector references to compute signals
    market_df = cache.read(MARKET_REF)
    if market_df.empty:
        print(f"ERROR: missing market reference {MARKET_REF}; aborting")
        return 1

    sector_dfs: dict[str, pd.DataFrame] = {}
    for etf in SECTOR_ETFS:
        sector_dfs[etf] = cache.read(etf)

    # ---------- 5. Compute indicators + signals per ticker ----------
    _print_step(6, "Computing indicators + signals...")
    rs_simple = RSSimple()
    rrs = RSVolAdjusted()
    rs_sector = RSSector(window=21)
    rvol = RVol()
    rrv = RRV()
    breakouts = Breakouts(sma_periods=(200,))

    today = datetime.now().date().isoformat()
    rows: list[dict] = []
    skipped = 0
    for t, df in survivors:
        if t in refs and t != MARKET_REF and t not in [MARKET_REF]:
            # Sector ETFs themselves still ranked but skip per-ticker sector RS
            pass
        sec_etf = sector_map.get(t, MARKET_REF)
        sec_df = sector_dfs.get(sec_etf)

        # Indicators
        last_close = float(df["close"].iloc[-1]) if not df.empty else float("nan")
        avg_vol_20 = float(df["volume"].tail(20).mean()) if len(df) >= 20 else float("nan")
        atr20 = atr_pct_latest(df["high"], df["low"], df["close"], 20)
        sma20 = sma_latest(df["close"], 20)
        sma50 = sma_latest(df["close"], 50)
        sma100 = sma_latest(df["close"], 100)
        sma200 = sma_latest(df["close"], 200)
        avwq = avwapq_latest(df)

        # Signals
        s1 = rs_simple.compute(t, df, market=market_df)
        s2 = rrs.compute(t, df, market=market_df)
        s3 = rs_sector.compute(t, df, market=market_df, sector=sec_df)
        s4 = rvol.compute(t, df, market=market_df)
        s5 = rrv.compute(t, df, market=market_df)
        s6 = breakouts.compute(t, df, market=market_df)

        rows.append({
            "date": today,
            "ticker": t,
            "sector_etf": sec_etf,
            "last_price": round(last_close, 4),
            "avg_vol_20d": int(avg_vol_20) if not math.isnan(avg_vol_20) else None,
            "atr_pct_20d": round(atr20, 3) if atr20 is not None else None,
            "sma_20": round(sma20, 4) if sma20 is not None else None,
            "sma_50": round(sma50, 4) if sma50 is not None else None,
            "sma_100": round(sma100, 4) if sma100 is not None else None,
            "sma_200": round(sma200, 4) if sma200 is not None else None,
            "avwapq": round(avwq, 4) if avwq is not None else None,
            **s1, **s2, **s3, **s4, **s5, **s6,
        })

    if skipped:
        print(f"  Skipped {skipped} due to missing data")
    df_all = pd.DataFrame(rows)

    # ---------- 6. Rank ----------
    _print_step(7, "Computing percentile ranks + combined rank...")
    df_ranked = add_percentile_ranks(df_all)

    # Drop references from the final output (they're tools, not trades)
    df_ranked = df_ranked[~df_ranked["ticker"].isin(refs - {MARKET_REF})]
    df_ranked = df_ranked[df_ranked["ticker"] != MARKET_REF]

    # Optional post-rank breakout filter (uses breakout flag columns).
    if args.breakouts_long:
        before = len(df_ranked)
        df_ranked = df_ranked[df_ranked["broke_long"] == 1.0]
        print(f"  --breakouts-long: {len(df_ranked)} of {before} kept")
    if args.breakouts_short:
        before = len(df_ranked)
        df_ranked = df_ranked[df_ranked["broke_short"] == 1.0]
        print(f"  --breakouts-short: {len(df_ranked)} of {before} kept")

    # ---------- 7. Write CSV ----------
    out_path = Path(args.output) if args.output else (
        OUTPUT_DIR / f"rs_{today}.csv"
    )
    _print_step(8, f"Writing {len(df_ranked)} rows to {out_path}...")
    write_csv(df_ranked, out_path)

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s. Wrote {len(df_ranked)} ranked tickers.")
    print(f"  Cache size: {cache.cache_size_mb():.1f} MB")
    print(f"  Output:     {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
