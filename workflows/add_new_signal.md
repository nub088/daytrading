# Add A New Signal

## Objective
Add a new ranking signal (e.g., momentum, breakout strength, volume surge) to the daily RS pipeline without touching existing signals or downstream code.

## When to use
When you want the daily scan to factor in something beyond the current RS signals — for example: 21-day price momentum, distance from 52-week high, post-earnings drift, etc.

## Architecture refresher
A **Signal** is a Python class implementing `tools.signals.base.Signal`. It receives one ticker's OHLCV history plus optional market and sector references, and returns a dict of named float scores. The orchestrator collects scores across the universe; `tools/ranking/combine.py` percentile-ranks them.

The contract:
```python
def compute(
    self,
    ticker: str,
    ohlcv: pd.DataFrame,         # this ticker's price history
    market: pd.DataFrame | None,  # SPY (or None if not applicable)
    sector: pd.DataFrame | None,  # this ticker's sector ETF
) -> dict[str, float]:
    return {"my_score_name": 0.42, ...}
```

## Steps

### 1. Create the signal file
`tools/signals/<your_signal>.py`. Follow the pattern of `rs_simple.py`:
- Inherit from `Signal`.
- Set `self.name` (used in logs).
- Implement `compute()` returning a dict of `{score_name: float}`.
- Handle empty/short price histories by returning NaN values.
- Use the `_log_return` helper from `rs_simple.py` if you need windowed returns.

Reuse indicators from `tools/indicators/` (sma, atr, avwap) rather than recomputing.

### 2. Smoke-test the signal in isolation
```bash
.venv/bin/python -c "
from tools.data import cache
from tools.signals.<your_signal> import <YourSignal>
sig = <YourSignal>(...)
df = cache.read('AAPL')
spy = cache.read('SPY')
print(sig.compute('AAPL', df, market=spy))
"
```
Verify the returned values are sensible (sign, magnitude). If they're NaN, your guards triggered — check why before continuing.

### 3. Wire the signal into the orchestrator
Edit `run_daily_rs.py`:

a) Import it near the other signal imports:
```python
from tools.signals.<your_signal> import <YourSignal>
```

b) Instantiate it in the "Compute signals" block:
```python
my_signal = <YourSignal>()
```

c) Call it inside the per-ticker loop and merge into the row dict:
```python
sN = my_signal.compute(t, df, market=market_df, sector=sec_df)
rows.append({..., **s1, **s2, **s3, **sN})
```

### 4. Tell `combine.py` how to rank it
Edit `tools/ranking/combine.py`:

If your signal returns a single score, add it to the parts that go into `combined_rank`:
```python
parts = [c for c in ("rs_simple_rank", "rrs_rank", "stock_vs_sector_rank", "my_signal_rank") if c in out.columns]
```

If it returns multi-window scores like RS, follow the `rs_simple` / `rrs` pattern: percentile-rank each window, then mean-and-rerank into a family rank.

### 5. Add to `COLUMN_ORDER` in `tools/output/to_csv.py`
So the new columns appear in a stable position in the CSV.

### 6. Smoke-test the full pipeline
```bash
.venv/bin/python run_daily_rs.py --smoke
```
Open `output/rs_<DATE>.csv` and confirm the new column is present and sensibly populated.

## Edge cases

- **Signal needs more history than the lookback we backfill** (e.g., 250-day momentum vs default 400-day backfill): your signal will silently return NaN for tickers without enough data. They still rank by other signals. To require more history, raise `DEFAULT_LOOKBACK_DAYS` in `tools/data/fetch_prices.py`.
- **Signal needs a non-SPY reference** (e.g., VIX): add a separate cache fetch in the orchestrator, pass it via an optional kwarg, and update the `Signal` base class signature.
- **Signal is expensive to compute** (e.g., needs API calls): cache the result per ticker per date in `.tmp/<signal_name>/`. Don't recompute on every run.
- **Signal interacts with another signal's score** (e.g., "RS divergence" = RS rising but price falling): compute both inside one Signal class rather than trying to wire two signals together at rank time.

## Anti-patterns

- **Don't put filtering logic in a signal.** Signals score; filters exclude. If you want "only stocks above 50-DMA," that's an `above_sma` filter, not a signal.
- **Don't normalize inside the signal** (e.g., dividing by max across universe). The Signal sees one ticker at a time. Percentile-ranking happens in `combine.py` after all tickers are scored.
- **Don't return integer ranks.** Return raw floats. The ranking layer turns them into percentiles.

## After adding the signal
- Update this workflow's "implemented signals" list (below) so the next person can see what's available.

## Implemented signals (as of v1)
- `rs_simple` (RSSimple) — log-return excess vs SPY over 5/21/63 days.
- `rrs` (RSVolAdjusted) — vol-adjusted excess return vs SPY over 5/21/63 days.
- `rs_sector` (RSSector) — stock vs its sector ETF + sector ETF vs SPY, 21-day window.
