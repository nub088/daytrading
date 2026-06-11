<!-- Created by Codex. -->

# Market-First Long/Short System

This repo is a research and screening tool, not financial advice. The
decision layer converts the scanner output into a reviewable game plan:
`long`, `short`, or `stand_aside`.

## Method

1. **Market first.** SPY is classified as bullish, bearish, or neutral
   from its daily trend structure: close vs SMA20/50/200, moving-average
   slope, and 5-day momentum.
2. **Stock second.** Longs require relative strength. Shorts require
   relative weakness. The rules use `combined_rank`, `rrs_rank`, and
   `stock_vs_sector_rank`.
3. **Trend alignment.** Long candidates should be above SMA20/50/200 and
   quarterly AVWAP. Short candidates should be below those references.
4. **Timing.** Fresh breaks of support/resistance, relative volume, and
   realized range improve the timing score.
5. **Risk context.** The system estimates an invalidation reference from
   nearby support/resistance, computes initial risk, and requires enough
   reward/risk room before a setup is actionable.

## Commands

Run the normal scan with decision columns:

```bash
python run_daily_rs.py
```

Only actionable setups:

```bash
python run_daily_rs.py --decision actionable
```

Long-only or short-only:

```bash
python run_daily_rs.py --decision long
python run_daily_rs.py --decision short
```

## Output Columns

- `market_bias`, `market_bias_score`
- `trade_action`: `long`, `short`, or `stand_aside`
- `setup_score`, `direction_score`, `timing_score`, `risk_score`
- `stop_reference`, `initial_risk_pct`, `target_reference`, `reward_risk`
- `decision_reasons`

Treat `long` and `short` as candidates for chart review, not orders.
Reject anything with upcoming binary event risk, poor liquidity, unclear
levels, or a setup you cannot manage with predefined risk.

## Liquidity False Positives

Some tickers pass a 20-day average-volume filter because of an old event
spike, but the current tape is too thin to trade. PIII on 2026-06-11 was
the calibration example: its 20-day average volume was high, while the
latest five sessions printed only tens of thousands of shares per day.

Default scanner rule:

- `min_recent_volume`: median daily volume over the last 5 sessions must
  be at least 500,000 shares. Use `--min-recent-volume 0` to disable.

Intraday quality rules to add for a later top-N or GUI quality pass:

- `active_5m_bar_ratio_4session >= 0.75`: most expected 5-minute candles
  should have actual volume.
- `median_5m_dollar_volume_4session >= 25,000`: the typical 5-minute bar
  should have enough dollar volume to avoid sparse-print charts.
