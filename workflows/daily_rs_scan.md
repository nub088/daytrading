# Daily RS Scan

## Objective
Produce an end-of-day Relative-Strength ranking of US-listed equities, written to a CSV the user can open in Excel/pandas to find the day's strongest names by stock-vs-SPY, stock-vs-sector, and sector-vs-SPY.

## When to run
After US market close (after 4:00 PM ET). yfinance daily bars finalize ~30 min after close, so 4:30 PM ET onward is safe.

## Required inputs
- A working venv with deps installed (`pip install -r requirements.txt`).
- Internet access to NASDAQ + yfinance.
- ~1 GB free disk (price cache grows over time).

## Tool to use
`run_daily_rs.py` (the orchestrator). All sub-tools in `tools/` are called automatically.

## Standard run

```bash
.venv/bin/python run_daily_rs.py
```

This:
1. Loads the cached NASDAQ universe (refreshes from API if >7 days old).
2. Backfills any ticker missing from `.tmp/prices/` (first run: ~30-60 min for ~7K tickers; subsequent runs: usually 0 new tickers).
3. Appends today's bar to every cached ticker.
4. Applies cheap filters: `min_price >= $5`, `avg_vol_20d >= 1,000,000` shares.
5. Computes indicators (SMA 20/50/100/200, ATR%, AVWAPQ).
6. Computes signals (RS simple over 5/21/63d, RRS vol-adjusted over same windows, stock-vs-sector RS, sector-vs-SPY RS).
7. Percentile-ranks each signal across the surviving universe, combines into `combined_rank`.
8. Writes `output/rs_<DATE>.csv`, sorted by `combined_rank` descending.

Expected output: a CSV with ~2,000-3,000 rows (post-filter), 30 columns, sorted strongest-first.

## Variations

| Goal | Flag |
|---|---|
| Smoke test (~50 tickers, ~3s) | `--smoke` |
| Bullish-bias only (require above all SMAs + AVWAPQ) | `--above-sma --above-avwapq` |
| Custom liquidity threshold | `--min-price 10 --min-volume 5000000` |
| Re-rank without re-fetching prices | `--no-refresh` |
| Custom output path | `--output /path/to/file.csv` |

## How to read the output

- **`combined_rank` = 0.95** → stock is in the top 5% of the surviving universe across the blended RS signals.
- **`stock_vs_sector_rs > 0`** → the stock outperformed its sector ETF over the 21-day window.
- **`sector_vs_spy_rs`** = the same value for every stock in a given sector; tells you which sectors are leading (use this for sector rotation read).
- **`rs_simple_rank` vs `rrs_rank`** → when these disagree materially, the stock is either smoothly outperforming (RRS high, simple lower → consistent winner) or noisily outperforming (simple high, RRS lower → choppy mover).
- **SMA stack columns** are values, not booleans. If `last_price > sma_20 > sma_50 > sma_100 > sma_200`, you have a textbook bullish stack.

## Edge cases & failures

- **First run is slow.** Backfilling ~7,000 tickers at ~100/chunk with a 0.5s pause = 30-60 min. Subsequent daily runs append a single day per ticker and take a few minutes.
- **yfinance occasionally rate-limits.** The fetcher retries each failing chunk once with a 5s pause; persistently failing chunks are skipped (those tickers just won't update that day). Re-run later to pick them up.
- **Tickers with <200 days of history** (recent IPOs) get NaN for `sma_200`, `rs_simple_63d`, etc. They still appear in the output if they pass the cheap filters; their `combined_rank` is computed only from windows that have enough data.
- **Universe cache stale (>7 days)** triggers an automatic refresh from NASDAQ. If NASDAQ's API is down, delete `.tmp/universe.csv` and the run will use whatever is left in the per-ticker price cache (universe membership won't update).
- **Sector misclassifications** are known (NASDAQ taxonomy ≠ GICS). See `tools/universe/sectors.py` — sector RS is internally consistent regardless of the label.
- **No SPY data → abort.** SPY is the market reference; without it no RS can be computed. The fetcher should always pull SPY since it's in `reference_tickers()`, but if for any reason it's missing the orchestrator exits with an error.

## After the run

- Final CSV in `output/rs_<DATE>.csv`. Open in Excel: filter by `sector_etf == 'XLK'` and sort by `combined_rank` desc to find the strongest tech names of the day.
- The full per-ticker price history stays in `.tmp/prices/<TICKER>.parquet` — re-rank with different thresholds via `--no-refresh` to avoid re-fetching.
- If you want a multi-day comparison, keep old CSVs around (the orchestrator names them by date, so they don't overwrite).

## Self-improvement notes
- If a particular ticker fails repeatedly, log it and consider excluding it via an exclusion list (not yet implemented).
- If yfinance becomes too flaky for daily reliability, swap `tools/data/fetch_prices.py` to use Polygon/Alpaca — only that file changes.
