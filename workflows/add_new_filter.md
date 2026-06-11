# Add A New Filter

## Objective
Add a new exclusion filter (e.g., min ATR%, min dollar volume, exclude OTC, exclude sectors, distance from 52-week high) without touching existing filters or signal/ranking code.

## When to use
When you want to narrow the universe before signal computation — either for hygiene (excluding bad data) or for direction (bullish/bearish bias).

## Architecture refresher
A **Filter** is a Python class implementing `tools.filters.base.Filter`. It receives a single ticker's OHLCV history and returns a boolean. Filters are stateless; thresholds are constructor parameters. Filters compose via `AndFilter` (all must pass).

The contract:
```python
def passes(self, ohlcv: pd.DataFrame) -> bool:
    return True  # or False
```

## Steps

### 1. Decide: hygiene or directional?

- **Hygiene** (`min_price`, `min_volume`) → applied early in the pipeline, default ON, excludes bad/illiquid data. Should be cheap to compute (just looks at last bar or last N-day average).
- **Directional** (`above_sma`, `above_avwapq`) → applied after hygiene, default OFF, encodes a market view. Can be more expensive (uses indicators).

This matters because the orchestrator's pipeline order is `data → cheap filters → indicators → directional filters → signals`.

### 2. Create the filter file
`tools/filters/<your_filter>.py`. Follow the pattern of `min_price.py`:

```python
from .base import Filter
import pandas as pd

class MyFilter(Filter):
    name = "my_filter"  # used in explain() output

    def __init__(self, threshold: float = ...) -> None:
        self.threshold = float(threshold)

    def passes(self, ohlcv: pd.DataFrame) -> bool:
        if ohlcv.empty or len(ohlcv) < <min_history>:
            return False
        # ... compute, compare, return bool
```

Guards to always include:
- `if ohlcv.empty: return False`
- Check for sufficient history before any rolling/window computation.
- Check for NaN in the value you're comparing.

### 3. Smoke-test in isolation
```bash
.venv/bin/python -c "
from tools.data import cache
from tools.filters.<your_filter> import <YourFilter>
f = <YourFilter>(threshold=...)
for t in ['AAPL','MSFT','META','NVDA','PENNY_STOCK_TICKER']:
    df = cache.read(t)
    print(t, f.passes(df))
"
```

### 4. Wire into the orchestrator
Edit `run_daily_rs.py`:

a) Import:
```python
from tools.filters.<your_filter> import <YourFilter>
```

b) **For a hygiene filter** — add to the `cheap_filters` list before the early `AndFilter` chain:
```python
cheap_filters = [
    MinPriceFilter(args.min_price),
    MinVolumeFilter(args.min_volume, period=20),
    <YourFilter>(args.<your_threshold>),
]
```

c) **For a directional filter** — add to `dir_filters` inside the `if args.above_sma or args.above_avwapq` block (or add a new CLI flag for it):
```python
if args.<your_flag>:
    dir_filters.append(<YourFilter>(...))
```

d) Add a CLI arg via `parser.add_argument(...)` so it can be toggled/configured at runtime.

### 5. Smoke-test the full pipeline
```bash
.venv/bin/python run_daily_rs.py --smoke
# or with your flag:
.venv/bin/python run_daily_rs.py --smoke --<your-flag>
```
Confirm the survivor count changes in the expected direction when you toggle it.

## Edge cases

- **Filter needs market context** (e.g., "stock RS rank > 0.7" → requires whole-universe context): this is not a filter, it's a post-rank slicing step. Either compute it as a signal and add a post-rank filter step (new architecture), or filter on the resulting CSV in Excel/pandas.
- **Filter requires an indicator that isn't yet implemented**: add the indicator to `tools/indicators/` first, then use it inside your filter. Don't inline indicator math into the filter — keep them separate so other filters/signals can reuse the indicator.
- **Filter is slow** (e.g., computes a rolling regression): put it in the *directional* tier so it only runs on tickers that already passed cheap filters.
- **Filter would exclude reference tickers** (SPY, sector ETFs): the orchestrator already special-cases these (`if t in refs: survivors.append(...)`). Don't worry about it.

## Anti-patterns

- **Don't make a filter that's actually a signal.** Filters are boolean. If your idea is "stocks more than 5% above their 20-DMA" → that's a `pct_above_sma_20` signal, and you can filter on its rank in Excel.
- **Don't hardcode thresholds.** Always pass them in via `__init__` so the filter is reusable with different parameters.
- **Don't read from disk inside `passes()`.** All data comes from the `ohlcv` argument. If you need ancillary data (e.g., earnings dates), fetch it once in the orchestrator and pass it via constructor.

## Implemented filters (as of v1)

**Hygiene (default ON):**
- `min_price` (MinPriceFilter) — last close >= threshold. Default $5.
- `min_volume` (MinVolumeFilter) — N-day avg volume >= threshold. Default 1M shares / 20-day.
- `min_recent_volume` (MinRecentVolumeFilter) — recent median volume >= threshold. Default 500K shares / 5-day.
- `min_active_volume_sessions` (MinActiveVolumeSessionsFilter) — enough recent sessions clear a per-session volume floor. Default 8 of 10 sessions >= 100K shares.

**Directional (default OFF, opt-in via CLI):**
- `above_sma_<period>` (AboveSMAFilter) — last close > SMA(period). Periods 20, 50, 100, 200.
- `above_avwapq` (AboveAVWAPQFilter) — last close > AVWAPQ (anchored to most recent Triple Witching).
