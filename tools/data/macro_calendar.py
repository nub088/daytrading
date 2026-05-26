"""Pending high-impact macro events.

Per Pete Stolcers' "Nail the Market" workflow, big scheduled releases
(FOMC, NFP, ISM, CPI, GDP) routinely whipsaw the tape. His prescription
is always the same: reduce risk into the print, wait for the reaction,
have your orders loaded (eBook pp. 5-7, p. 60).

This module surfaces those events to the GUI so a user picking a ticker
sees a warning when a big release falls inside their trading window.

Coverage is intentionally narrow — the events Pete names specifically
plus FOMC's known schedule. Extend EVENTS below to add anything else
(tariff deadlines, OPEC meetings, key Fed-speak, country-specific PMIs).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

# Hand-curated. Use date objects so comparisons stay simple.
# FOMC decision day (the second day of each 2-day meeting, 2pm ET press
# conference). Source: federalreserve.gov. Extend as the Fed publishes
# future-year schedules.
EVENTS: list[tuple[date, str]] = [
    (date(2026, 1, 28), "FOMC decision"),
    (date(2026, 3, 18), "FOMC decision + SEP"),
    (date(2026, 4, 29), "FOMC decision"),
    (date(2026, 6, 17), "FOMC decision + SEP"),
    (date(2026, 7, 29), "FOMC decision"),
    (date(2026, 9, 16), "FOMC decision + SEP"),
    (date(2026, 10, 28), "FOMC decision"),
    (date(2026, 12, 9), "FOMC decision + SEP"),
]


@dataclass(frozen=True)
class MacroEvent:
    when: date
    label: str

    @property
    def days_until(self) -> int:
        return (self.when - date.today()).days


def _first_friday(year: int, month: int) -> date:
    d = date(year, month, 1)
    # weekday(): Mon=0..Fri=4. Skip ahead to the next Friday.
    return d + timedelta(days=(4 - d.weekday()) % 7)


def _first_business_day(year: int, month: int) -> date:
    d = date(year, month, 1)
    while d.weekday() >= 5:  # Sat=5, Sun=6
        d += timedelta(days=1)
    return d


def _monthly_recurring(today: date, horizon: date) -> list[MacroEvent]:
    """Compute high-confidence monthly releases inside [today, horizon].

    NFP (first Friday) and ISM Manufacturing (first business day) are
    predictable enough to compute. Less-predictable releases (CPI, retail
    sales, etc.) belong in the static EVENTS list when dates are known.
    """
    out: list[MacroEvent] = []
    cursor = date(today.year, today.month, 1)
    while cursor <= horizon:
        nfp = _first_friday(cursor.year, cursor.month)
        if today <= nfp <= horizon:
            out.append(MacroEvent(nfp, "NFP / Employment report"))
        ism = _first_business_day(cursor.year, cursor.month)
        if today <= ism <= horizon:
            out.append(MacroEvent(ism, "ISM Manufacturing"))
        cursor = (
            date(cursor.year + 1, 1, 1)
            if cursor.month == 12
            else date(cursor.year, cursor.month + 1, 1)
        )
    return out


def upcoming_events(today: date | None = None, horizon_days: int = 7) -> list[MacroEvent]:
    """Return events in [today, today + horizon_days], soonest first."""
    today = today or date.today()
    horizon = today + timedelta(days=horizon_days)
    static = [MacroEvent(d, label) for d, label in EVENTS if today <= d <= horizon]
    return sorted(static + _monthly_recurring(today, horizon), key=lambda e: e.when)
