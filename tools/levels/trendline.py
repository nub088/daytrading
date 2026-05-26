"""Trendline levels: slanted S/R from two connected swing pivots.

A **resistance trendline** is a down-sloping line through two swing highs
where the later high sits below the earlier one. A **support trendline**
is an up-sloping line through two swing lows where the later low sits
above the earlier one. The line extends forward indefinitely.

Validity rules (kept conservative to avoid spurious lines):

  1. The pair forms the correct slope direction for its kind.
  2. Between the two anchors, no bar's high (resistance) or low (support)
     pierces the line by more than `tol_atr * ATR(20)`.
  3. After the second anchor and up to yesterday, no bar's close crossed
     the line. Lines broken before today are not returned — the
     breakouts signal only cares about lines that were valid yesterday.
  4. Minimum bar span between anchors; cap on the number of recent
     pivots considered (keeps the O(K²) enumeration cheap).
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..indicators.atr import atr_latest
from ..indicators.swings import find_swings
from .base import Level


@dataclass(frozen=True, eq=False)
class TrendlineLevel(Level):
    slope: float          # price per bar
    intercept: float      # price at positional index 0
    anchor1_idx: int      # earlier anchor
    anchor2_idx: int      # later anchor (> anchor1_idx)
    direction: str        # 'falling' (resistance) or 'rising' (support)
    touch_count: int = 2  # bars between anchor1 and today within tol of line

    @property
    def source(self) -> str:
        return "trendline"

    def value_at(self, idx: int) -> float:
        if idx < self.anchor1_idx:
            return float("nan")
        return self.intercept + self.slope * idx

    @property
    def bars_span(self) -> int:
        return self.anchor2_idx - self.anchor1_idx


def _line_through(idx1: int, p1: float, idx2: int, p2: float) -> tuple[float, float]:
    slope = (p2 - p1) / (idx2 - idx1)
    intercept = p1 - slope * idx1
    return slope, intercept


def find_trendlines(
    ohlcv: pd.DataFrame,
    lookback_bars: int = 250,
    swing_window: int = 5,
    max_pivots: int = 12,
    min_bars_span: int = 10,
    tol_atr: float = 0.25,
    atr_period: int = 20,
    max_per_direction: int = 2,
) -> list[TrendlineLevel]:
    """Return resistance + support trendlines that were valid up to yesterday.

    Returned lines are ranked by `touch_count` (descending) — the number
    of bars between anchor1 and today whose high/low comes within `tol`
    of the line. Pete: "the more data points they connect the more
    relevant they are" (eBook p. 28). `max_per_direction` caps how many
    lines per direction reach the chart to avoid clutter.
    """
    if ohlcv.empty:
        return []
    n = len(ohlcv)
    if n < swing_window * 2 + 1 or n < 2:
        return []

    atr_value = atr_latest(
        ohlcv["high"], ohlcv["low"], ohlcv["close"], period=atr_period
    )
    if atr_value is None or atr_value <= 0:
        return []
    tol = tol_atr * atr_value

    cutoff = max(0, n - lookback_bars)
    swings = [s for s in find_swings(ohlcv, lookback=swing_window) if s.idx >= cutoff]
    if not swings:
        return []

    highs_np = ohlcv["high"].to_numpy()
    lows_np = ohlcv["low"].to_numpy()
    close_np = ohlcv["close"].to_numpy()
    today = n - 1

    swing_highs = [s for s in swings if s.kind == "high"][-max_pivots:]
    swing_lows = [s for s in swings if s.kind == "low"][-max_pivots:]

    falling = _scan_pairs(
        pivots=swing_highs,
        extremes=highs_np,
        close_np=close_np,
        today=today,
        direction="falling",
        min_bars_span=min_bars_span,
        tol=tol,
    )
    rising = _scan_pairs(
        pivots=swing_lows,
        extremes=lows_np,
        close_np=close_np,
        today=today,
        direction="rising",
        min_bars_span=min_bars_span,
        tol=tol,
    )
    # Within each direction, prefer more touches; break ties with longer span.
    falling.sort(key=lambda t: (t.touch_count, t.bars_span), reverse=True)
    rising.sort(key=lambda t: (t.touch_count, t.bars_span), reverse=True)
    return falling[:max_per_direction] + rising[:max_per_direction]


def _scan_pairs(
    pivots,
    extremes,
    close_np,
    today: int,
    direction: str,
    min_bars_span: int,
    tol: float,
) -> list[TrendlineLevel]:
    out: list[TrendlineLevel] = []
    for a in range(len(pivots)):
        for b in range(a + 1, len(pivots)):
            p1, p2 = pivots[a], pivots[b]
            if p2.idx - p1.idx < min_bars_span:
                continue
            if direction == "falling" and p2.price >= p1.price:
                continue
            if direction == "rising" and p2.price <= p1.price:
                continue

            slope, intercept = _line_through(p1.idx, p1.price, p2.idx, p2.price)

            if not _holds_between(
                extremes, p1.idx, p2.idx, slope, intercept, direction, tol
            ):
                continue
            if not _holds_after(
                close_np, p2.idx, today - 1, slope, intercept, direction, tol
            ):
                continue

            touches = _count_touches(extremes, p1.idx, today, slope, intercept, tol)

            out.append(
                TrendlineLevel(
                    slope=float(slope),
                    intercept=float(intercept),
                    anchor1_idx=int(p1.idx),
                    anchor2_idx=int(p2.idx),
                    direction=direction,
                    touch_count=int(touches),
                )
            )
    return out


def _count_touches(
    extremes, a: int, until: int, slope: float, intercept: float, tol: float
) -> int:
    """Bars in [a, until] whose extreme is within `tol` of the line.

    Both anchors always touch by construction. Additional touches between
    or after the anchors are what make a line meaningful — they're the
    "data points connected" that Pete weighs trendlines by.
    """
    count = 0
    for k in range(a, until + 1):
        v = extremes[k]
        if pd.isna(v):
            continue
        line = intercept + slope * k
        if abs(v - line) <= tol:
            count += 1
    return count


def _holds_between(
    extremes, a: int, b: int, slope: float, intercept: float, direction: str, tol: float
) -> bool:
    if b <= a + 1:
        return True
    for k in range(a + 1, b):
        line = intercept + slope * k
        if direction == "falling":
            if extremes[k] > line + tol:
                return False
        else:
            if extremes[k] < line - tol:
                return False
    return True


def _holds_after(
    close_np, after: int, until: int, slope: float, intercept: float, direction: str, tol: float
) -> bool:
    if until <= after:
        return True
    for k in range(after + 1, until + 1):
        line = intercept + slope * k
        c = close_np[k]
        if pd.isna(c):
            continue
        if direction == "falling":
            if c > line + tol:
                return False
        else:
            if c < line - tol:
                return False
    return True
