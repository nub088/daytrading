"""Price-alert persistence and trigger logic.

Alerts are stored as a flat JSON list so they survive GUI restarts and
stay greppable. The trigger check is bar-range based: an active alert
fires when `bar_low <= alert.price <= bar_high`. A future live feed
(IBKR) can reuse `check_alerts` unchanged by passing the tick price as
both `bar_high` and `bar_low`.

All functions take an optional `path` so tests can point at a temp file;
production callers use the default `ALERTS_FILE` from config.
"""
from __future__ import annotations

import json
import math
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from tools.config import ALERTS_FILE


@dataclass
class PriceAlert:
    ticker: str
    price: float
    note: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    triggered_at: str | None = None

    @property
    def active(self) -> bool:
        return self.triggered_at is None


def _resolve(path: Path | None) -> Path:
    return Path(path) if path is not None else ALERTS_FILE


def load_alerts(path: Path | None = None) -> list[PriceAlert]:
    """Read all alerts. Missing or unparseable files yield an empty list."""
    p = _resolve(path)
    if not p.exists():
        return []
    try:
        raw = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(raw, list):
        return []
    alerts: list[PriceAlert] = []
    for item in raw:
        try:
            alerts.append(PriceAlert(**item))
        except TypeError:
            continue  # skip rows written by an older/newer schema
    return alerts


def save_alerts(alerts: list[PriceAlert], path: Path | None = None) -> None:
    """Write the full alert list atomically (write temp, then replace)."""
    p = _resolve(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps([asdict(a) for a in alerts], indent=2))
    os.replace(tmp, p)


def add_alert(
    ticker: str,
    price: float,
    note: str = "",
    path: Path | None = None,
) -> PriceAlert:
    """Create, persist, and return a new alert for `ticker` at `price`."""
    try:
        price = float(price)
    except (TypeError, ValueError):
        raise ValueError(f"alert price must be a number, got {price!r}")
    if math.isnan(price) or price <= 0:
        raise ValueError(f"alert price must be > 0, got {price!r}")
    ticker = str(ticker).strip().upper()
    if not ticker:
        raise ValueError("alert ticker must be non-empty")
    alert = PriceAlert(ticker=ticker, price=price, note=str(note))
    alerts = load_alerts(path)
    alerts.append(alert)
    save_alerts(alerts, path)
    return alert


def remove_alert(alert_id: str, path: Path | None = None) -> bool:
    """Delete an alert by id. Returns True if something was removed."""
    alerts = load_alerts(path)
    kept = [a for a in alerts if a.id != alert_id]
    if len(kept) == len(alerts):
        return False
    save_alerts(kept, path)
    return True


def alerts_for(ticker: str, path: Path | None = None) -> list[PriceAlert]:
    """All alerts (active and triggered) for one ticker."""
    ticker = str(ticker).strip().upper()
    return [a for a in load_alerts(path) if a.ticker == ticker]


def check_alerts(
    ticker: str,
    bar_high: float,
    bar_low: float,
    as_of: str | None = None,
    path: Path | None = None,
) -> list[PriceAlert]:
    """Fire active alerts whose price falls inside [bar_low, bar_high].

    Newly triggered alerts are stamped with `triggered_at`, persisted,
    and returned. Already-triggered alerts never fire twice.

    `as_of` is the ISO timestamp of the bar/tick being checked. Alerts
    created after it are skipped — with end-of-day bars this prevents an
    alert from firing off price action that happened before it was
    placed. Live feeds pass the tick time (or omit it).
    """
    ticker = str(ticker).strip().upper()
    alerts = load_alerts(path)
    fired: list[PriceAlert] = []
    for a in alerts:
        if a.ticker != ticker or not a.active:
            continue
        if as_of is not None and a.created_at > as_of:
            continue
        if bar_low <= a.price <= bar_high:
            a.triggered_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            fired.append(a)
    if fired:
        save_alerts(alerts, path)
    return fired
