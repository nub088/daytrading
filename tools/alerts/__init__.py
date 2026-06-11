"""Price alerts package.

Public API:
  - `PriceAlert` — the alert record (active until `triggered_at` is set).
  - `add_alert`, `remove_alert`, `load_alerts`, `save_alerts`, `alerts_for`
    — JSON-backed CRUD.
  - `check_alerts` — bar/tick crossing check that stamps and persists
    triggers; the same entry point a live IBKR feed will call per tick.
"""
from __future__ import annotations

from .store import (
    PriceAlert,
    add_alert,
    alerts_for,
    check_alerts,
    load_alerts,
    remove_alert,
    save_alerts,
)

__all__ = [
    "PriceAlert",
    "add_alert",
    "alerts_for",
    "check_alerts",
    "load_alerts",
    "remove_alert",
    "save_alerts",
]
