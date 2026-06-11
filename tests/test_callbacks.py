from __future__ import annotations

import pandas as pd

from gui import callbacks


def _text(node) -> str:
    children = node.children
    if isinstance(children, list):
        return "".join(str(child) for child in children)
    return str(children)


def test_news_banner_warns_for_fetched_earnings_within_seven_days(monkeypatch) -> None:
    earnings_date = pd.Timestamp.now().normalize() + pd.Timedelta(days=2)
    monkeypatch.setattr(callbacks.data_loader, "get_next_earnings_date", lambda ticker: earnings_date)
    monkeypatch.setattr(callbacks.data_loader, "get_earnings_date", lambda ticker: None)
    monkeypatch.setattr(callbacks.data_loader, "get_upcoming_macro_events", lambda days: [])

    items = callbacks._build_news_banner("TEST")

    assert len(items) == 1
    assert "TEST earnings in 2d" in _text(items[0])
    assert items[0].style["background"] == "#dc2626"


def test_news_banner_warns_amber_for_fetched_earnings_one_week_out(monkeypatch) -> None:
    earnings_date = pd.Timestamp.now().normalize() + pd.Timedelta(days=7)
    monkeypatch.setattr(callbacks.data_loader, "get_next_earnings_date", lambda ticker: earnings_date)
    monkeypatch.setattr(callbacks.data_loader, "get_earnings_date", lambda ticker: None)
    monkeypatch.setattr(callbacks.data_loader, "get_upcoming_macro_events", lambda days: [])

    items = callbacks._build_news_banner("TEST")

    assert len(items) == 1
    assert "TEST earnings in 7d" in _text(items[0])
    assert items[0].style["background"] == "#d97706"


def test_news_banner_warns_for_recent_post_earnings_move(monkeypatch) -> None:
    today = pd.Timestamp.now().normalize()
    earnings_date = today - pd.Timedelta(days=1)
    daily = pd.DataFrame(
        {"close": [100.0, 109.0]},
        index=[earnings_date - pd.Timedelta(days=1), earnings_date],
    )
    monkeypatch.setattr(callbacks.data_loader, "get_next_earnings_date", lambda ticker: None)
    monkeypatch.setattr(callbacks.data_loader, "get_earnings_date", lambda ticker: earnings_date)
    monkeypatch.setattr(callbacks.data_loader, "get_upcoming_macro_events", lambda days: [])

    items = callbacks._build_news_banner(
        "TEST",
        daily_ohlcv=daily,
    )

    assert len(items) == 1
    assert "TEST post-earnings move +9.0%" in _text(items[0])
    assert items[0].style["background"] == "#dc2626"
