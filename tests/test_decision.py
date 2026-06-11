"""Tests for the market-first trade decision layer."""
# Created by Codex.
from __future__ import annotations

import numpy as np
import pandas as pd

from tools.decision import MarketBias, add_trade_decisions, determine_market_bias, evaluate_trade


def _row(**overrides: float | str) -> pd.Series:
    base: dict[str, float | str] = {
        "ticker": "TEST",
        "last_price": 100.0,
        "atr_pct_20d": 2.0,
        "sma_20": 96.0,
        "sma_50": 92.0,
        "sma_200": 80.0,
        "avwapq": 90.0,
        "combined_rank": 0.95,
        "rrs_rank": 0.90,
        "stock_vs_sector_rank": 0.88,
        "rvol_rank": 0.80,
        "rrv_rank": 0.70,
        "broke_long": 1.0,
        "broke_short": 0.0,
        "nearest_support": 98.0,
        "nearest_resistance": 105.0,
    }
    base.update(overrides)
    return pd.Series(base)


def test_bullish_market_bias_from_uptrend(uptrend_ohlcv: pd.DataFrame) -> None:
    bias = determine_market_bias(uptrend_ohlcv)
    assert bias.side == "bullish"
    assert bias.score > 0


def test_bearish_market_bias_from_downtrend(downtrend_ohlcv: pd.DataFrame) -> None:
    bias = determine_market_bias(downtrend_ohlcv)
    assert bias.side == "bearish"
    assert bias.score < 0


def test_long_decision_requires_bullish_market_and_aligned_stock() -> None:
    decision = evaluate_trade(_row(), MarketBias("bullish", 0.8, ("SPY bullish",)))
    assert decision.action == "long"
    assert decision.setup_score >= 0.68
    assert decision.reward_risk == 2.5


def test_short_decision_uses_relative_weakness_and_downtrend() -> None:
    row = _row(
        last_price=100.0,
        sma_20=104.0,
        sma_50=108.0,
        sma_200=120.0,
        avwapq=110.0,
        combined_rank=0.05,
        rrs_rank=0.10,
        stock_vs_sector_rank=0.12,
        broke_long=0.0,
        broke_short=1.0,
        nearest_support=95.0,
        nearest_resistance=102.0,
    )
    decision = evaluate_trade(row, MarketBias("bearish", -0.8, ("SPY bearish",)))
    assert decision.action == "short"
    assert decision.direction_score > 0.85
    assert decision.reward_risk == 2.5


def test_neutral_market_stands_aside() -> None:
    decision = evaluate_trade(_row(), MarketBias("neutral", 0.0, ("mixed SPY evidence",)))
    assert decision.action == "stand_aside"
    assert "market bias is neutral" in decision.reasons


def test_weak_reward_risk_stands_aside() -> None:
    decision = evaluate_trade(
        _row(nearest_support=99.0, nearest_resistance=100.5),
        MarketBias("bullish", 0.8, ("SPY bullish",)),
    )
    assert decision.action == "stand_aside"
    assert decision.risk_score < 0.35


def test_add_trade_decisions_appends_columns() -> None:
    df = pd.DataFrame([_row(), _row(ticker="WEAK", combined_rank=0.2, rrs_rank=0.3)])
    out = add_trade_decisions(df, MarketBias("bullish", 0.8, ("SPY bullish",)))
    assert "trade_action" in out.columns
    assert "decision_reasons" in out.columns
    assert out.loc[0, "trade_action"] == "long"
    assert out.loc[1, "trade_action"] == "stand_aside"


def test_short_or_incomplete_market_history_is_neutral(short_ohlcv: pd.DataFrame) -> None:
    bias = determine_market_bias(short_ohlcv)
    assert bias.side == "neutral"


def test_missing_values_do_not_raise() -> None:
    row = _row(combined_rank=np.nan, nearest_support=np.nan, nearest_resistance=np.nan)
    decision = evaluate_trade(row, MarketBias("bullish", 0.8, ("SPY bullish",)))
    assert decision.action == "stand_aside"
