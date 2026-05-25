"""Anchor-date computations for AVWAP variants.

AVWAPQ anchors to the most recent Triple Witching (3rd Friday of
Mar/Jun/Sep/Dec). The author's reasoning: quarterly opex + ETF rebalances
concentrate institutional flow into that day, making it a meaningful
volume anchor.
"""
from __future__ import annotations

from datetime import date, timedelta


TRIPLE_WITCHING_MONTHS = (3, 6, 9, 12)


def third_friday(year: int, month: int) -> date:
    """3rd Friday of given month."""
    first = date(year, month, 1)
    # weekday(): Monday=0 ... Friday=4
    offset = (4 - first.weekday()) % 7
    first_friday = first + timedelta(days=offset)
    return first_friday + timedelta(weeks=2)


def triple_witching_dates(year: int) -> list[date]:
    return [third_friday(year, m) for m in TRIPLE_WITCHING_MONTHS]


def most_recent_triple_witching(asof: date | None = None) -> date:
    """Most recent (≤ asof) triple-witching Friday. asof defaults to today."""
    if asof is None:
        asof = date.today()
    candidates: list[date] = []
    for year in (asof.year - 1, asof.year):
        candidates.extend(triple_witching_dates(year))
    past = [d for d in candidates if d <= asof]
    if not past:
        raise RuntimeError(f"No triple-witching date on/before {asof}")
    return max(past)


if __name__ == "__main__":
    today = date.today()
    print(f"Today: {today}")
    print(f"Most recent triple witching: {most_recent_triple_witching(today)}")
    print(f"2026 triple witching dates: {triple_witching_dates(2026)}")
