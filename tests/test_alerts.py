from __future__ import annotations

import json

import pytest

from tools.alerts import (
    add_alert,
    alerts_for,
    check_alerts,
    load_alerts,
    remove_alert,
)


@pytest.fixture()
def alerts_path(tmp_path):
    return tmp_path / "alerts.json"


def test_add_alert_persists_and_reloads(alerts_path) -> None:
    created = add_alert("AAPL", 187.50, note="breakout retest", path=alerts_path)

    loaded = load_alerts(path=alerts_path)
    assert len(loaded) == 1
    assert loaded[0].id == created.id
    assert loaded[0].ticker == "AAPL"
    assert loaded[0].price == 187.50
    assert loaded[0].note == "breakout retest"
    assert loaded[0].active


def test_add_alert_rejects_bad_price(alerts_path) -> None:
    with pytest.raises(ValueError):
        add_alert("AAPL", 0, path=alerts_path)
    with pytest.raises(ValueError):
        add_alert("AAPL", float("nan"), path=alerts_path)
    assert load_alerts(path=alerts_path) == []


def test_alerts_for_filters_by_ticker(alerts_path) -> None:
    add_alert("AAPL", 187.50, path=alerts_path)
    add_alert("MSFT", 410.00, path=alerts_path)

    assert [a.ticker for a in alerts_for("AAPL", path=alerts_path)] == ["AAPL"]


def test_remove_alert(alerts_path) -> None:
    keep = add_alert("AAPL", 187.50, path=alerts_path)
    drop = add_alert("AAPL", 190.00, path=alerts_path)

    assert remove_alert(drop.id, path=alerts_path) is True
    assert remove_alert("missing", path=alerts_path) is False
    assert [a.id for a in load_alerts(path=alerts_path)] == [keep.id]


def test_check_alerts_triggers_when_bar_range_crosses_level(alerts_path) -> None:
    hit = add_alert("AAPL", 187.50, path=alerts_path)
    add_alert("AAPL", 200.00, path=alerts_path)
    add_alert("MSFT", 188.00, path=alerts_path)  # other ticker: untouched

    fired = check_alerts("AAPL", bar_high=188.0, bar_low=186.0, path=alerts_path)

    assert [a.id for a in fired] == [hit.id]
    reloaded = {a.id: a for a in load_alerts(path=alerts_path)}
    assert not reloaded[hit.id].active
    assert reloaded[hit.id].triggered_at is not None


def test_check_alerts_skips_already_triggered(alerts_path) -> None:
    add_alert("AAPL", 187.50, path=alerts_path)
    assert len(check_alerts("AAPL", bar_high=188.0, bar_low=186.0, path=alerts_path)) == 1
    # Same crossing again: alert already consumed, nothing new fires.
    assert check_alerts("AAPL", bar_high=188.0, bar_low=186.0, path=alerts_path) == []


def test_check_alerts_supports_single_tick_price(alerts_path) -> None:
    # Future IBKR live feed delivers ticks, not bars: high == low == tick.
    add_alert("AAPL", 187.50, path=alerts_path)
    assert check_alerts("AAPL", bar_high=187.50, bar_low=187.50, path=alerts_path) != []


def test_check_alerts_as_of_skips_alerts_created_after_the_bar(alerts_path) -> None:
    # An EOD bar dated before the alert was placed must not fire it:
    # that price action happened before the alert existed.
    alert = add_alert("AAPL", 187.50, path=alerts_path)
    stale_bar_time = "2020-01-01T00:00:00+00:00"
    assert check_alerts("AAPL", 188.0, 186.0, as_of=stale_bar_time, path=alerts_path) == []

    future_bar_time = "2999-01-01T00:00:00+00:00"
    fired = check_alerts("AAPL", 188.0, 186.0, as_of=future_bar_time, path=alerts_path)
    assert [a.id for a in fired] == [alert.id]


def test_load_alerts_tolerates_missing_or_corrupt_file(alerts_path) -> None:
    assert load_alerts(path=alerts_path) == []
    alerts_path.write_text("{not json")
    assert load_alerts(path=alerts_path) == []


def test_store_file_is_plain_json(alerts_path) -> None:
    add_alert("AAPL", 187.50, path=alerts_path)
    raw = json.loads(alerts_path.read_text())
    assert isinstance(raw, list)
    assert raw[0]["ticker"] == "AAPL"
