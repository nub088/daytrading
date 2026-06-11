"""Market-first long/short decision rules.

This module turns the scanner's transparent signal columns into a
directional game plan. It is intentionally a rules engine, not a price
prediction model: each decision includes the gates that passed or failed
so the user can review the chart and reject low-quality setups.
"""
# Created by Codex.
from __future__ import annotations

from dataclasses import dataclass
import math

import pandas as pd

from tools.indicators.sma import sma_latest


@dataclass(frozen=True)
class MarketBias:
    side: str
    score: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class TradeDecision:
    action: str
    setup_score: float
    direction_score: float
    timing_score: float
    risk_score: float
    reasons: tuple[str, ...]
    stop_reference: float
    initial_risk_pct: float
    target_reference: float
    reward_risk: float


def _finite(value: object) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return out


def _row_float(row: pd.Series, key: str) -> float | None:
    if key not in row:
        return None
    return _finite(row[key])


def _rank_score(value: float | None, bullish: bool) -> float:
    if value is None:
        return 0.0
    return value if bullish else 1.0 - value


def determine_market_bias(market: pd.DataFrame) -> MarketBias:
    """Classify SPY context as bullish, bearish, or neutral.

    The course material stresses "market first"; the implementation uses
    objective daily-chart evidence that already exists in this repo:
    price relative to key moving averages, moving-average slope, and
    recent return direction.
    """
    if market.empty or len(market) < 200:
        return MarketBias("neutral", 0.0, ("insufficient market history",))

    close = market["close"]
    last = _finite(close.iloc[-1])
    prev5 = _finite(close.iloc[-6]) if len(close) >= 6 else None
    sma20 = sma_latest(close, 20)
    sma50 = sma_latest(close, 50)
    sma200 = sma_latest(close, 200)
    sma20_prev = _finite(close.tail(25).head(20).mean()) if len(close) >= 25 else None
    sma50_prev = _finite(close.tail(60).head(50).mean()) if len(close) >= 60 else None

    if None in (last, prev5, sma20, sma50, sma200, sma20_prev, sma50_prev):
        return MarketBias("neutral", 0.0, ("incomplete market indicators",))

    bull_points = 0
    bear_points = 0
    reasons: list[str] = []

    if last > sma20 > sma50:
        bull_points += 2
        reasons.append("SPY close above rising short-term structure")
    elif last < sma20 < sma50:
        bear_points += 2
        reasons.append("SPY close below falling short-term structure")

    if last > sma200:
        bull_points += 1
        reasons.append("SPY above SMA200")
    elif last < sma200:
        bear_points += 1
        reasons.append("SPY below SMA200")

    if sma20 > sma20_prev and sma50 > sma50_prev:
        bull_points += 1
        reasons.append("SPY 20/50-day averages rising")
    elif sma20 < sma20_prev and sma50 < sma50_prev:
        bear_points += 1
        reasons.append("SPY 20/50-day averages falling")

    if last > prev5:
        bull_points += 1
        reasons.append("SPY positive 5-day momentum")
    elif last < prev5:
        bear_points += 1
        reasons.append("SPY negative 5-day momentum")

    score = (bull_points - bear_points) / 5.0
    if bull_points >= 4 and bull_points - bear_points >= 2:
        return MarketBias("bullish", round(score, 3), tuple(reasons))
    if bear_points >= 4 and bear_points - bull_points >= 2:
        return MarketBias("bearish", round(score, 3), tuple(reasons))
    return MarketBias("neutral", round(score, 3), tuple(reasons) or ("mixed SPY evidence",))


def evaluate_trade(
    row: pd.Series,
    market_bias: MarketBias,
    *,
    min_setup_score: float = 0.68,
    min_direction_score: float = 0.65,
    min_timing_score: float = 0.45,
    min_risk_score: float = 0.35,
    min_reward_risk: float = 1.5,
) -> TradeDecision:
    """Evaluate one ranked scanner row as long/short/stand_aside."""
    if market_bias.side == "bullish":
        bullish = True
        aligned_action = "long"
    elif market_bias.side == "bearish":
        bullish = False
        aligned_action = "short"
    else:
        return _stand_aside("market bias is neutral", market_bias)

    last_price = _row_float(row, "last_price")
    if last_price is None or last_price <= 0:
        return _stand_aside("missing last price", market_bias)

    rank_inputs = [
        _rank_score(_row_float(row, "combined_rank"), bullish),
        _rank_score(_row_float(row, "rrs_rank"), bullish),
        _rank_score(_row_float(row, "stock_vs_sector_rank"), bullish),
    ]
    direction_score = sum(rank_inputs) / len(rank_inputs)

    sma20 = _row_float(row, "sma_20")
    sma50 = _row_float(row, "sma_50")
    sma200 = _row_float(row, "sma_200")
    avwapq = _row_float(row, "avwapq")
    trend_votes = []
    if sma20 is not None and sma50 is not None:
        trend_votes.append(last_price > sma20 > sma50 if bullish else last_price < sma20 < sma50)
    if sma200 is not None:
        trend_votes.append(last_price > sma200 if bullish else last_price < sma200)
    if avwapq is not None:
        trend_votes.append(last_price > avwapq if bullish else last_price < avwapq)
    trend_score = sum(bool(v) for v in trend_votes) / len(trend_votes) if trend_votes else 0.0

    broke = _row_float(row, "broke_long" if bullish else "broke_short") == 1.0
    rvol = _row_float(row, "rvol_rank")
    rrv = _row_float(row, "rrv_rank")
    volume_score = (
        (0.5 if rvol is None else rvol) * 0.65
        + (0.5 if rrv is None else rrv) * 0.35
    )
    timing_score = min(1.0, (0.45 if broke else 0.0) + 0.35 * trend_score + 0.20 * volume_score)

    risk = _risk_context(row, bullish=bullish, last_price=last_price)
    risk_score = risk["risk_score"]

    setup_score = (
        0.40 * direction_score
        + 0.25 * trend_score
        + 0.20 * timing_score
        + 0.15 * risk_score
    )

    reasons = list(market_bias.reasons[:2])
    reasons.append("stock has relative strength" if bullish else "stock has relative weakness")
    if trend_score >= 0.67:
        reasons.append("daily trend filters align")
    else:
        reasons.append("daily trend filters are mixed")
    reasons.append("fresh level break" if broke else "no fresh level break")
    if risk["reward_risk"] is not None and risk["reward_risk"] >= 1.5:
        reasons.append("nearby level structure offers acceptable reward/risk")
    elif risk["reward_risk"] is not None:
        reasons.append("nearby level structure limits reward/risk")

    passes = (
        setup_score >= min_setup_score
        and direction_score >= min_direction_score
        and timing_score >= min_timing_score
        and risk_score >= min_risk_score
        and (
            risk["reward_risk"] is not None
            and math.isfinite(risk["reward_risk"])
            and risk["reward_risk"] >= min_reward_risk
        )
    )
    return TradeDecision(
        action=aligned_action if passes else "stand_aside",
        setup_score=round(setup_score, 3),
        direction_score=round(direction_score, 3),
        timing_score=round(timing_score, 3),
        risk_score=round(risk_score, 3),
        reasons=tuple(reasons),
        stop_reference=risk["stop_reference"],
        initial_risk_pct=risk["initial_risk_pct"],
        target_reference=risk["target_reference"],
        reward_risk=risk["reward_risk"],
    )


def add_trade_decisions(df: pd.DataFrame, market_bias: MarketBias) -> pd.DataFrame:
    """Append decision columns to a ranked scan DataFrame."""
    out = df.copy()
    decisions = [evaluate_trade(row, market_bias) for _, row in out.iterrows()]
    out["market_bias"] = market_bias.side
    out["market_bias_score"] = market_bias.score
    out["trade_action"] = [d.action for d in decisions]
    out["setup_score"] = [d.setup_score for d in decisions]
    out["direction_score"] = [d.direction_score for d in decisions]
    out["timing_score"] = [d.timing_score for d in decisions]
    out["risk_score"] = [d.risk_score for d in decisions]
    out["decision_reasons"] = ["; ".join(d.reasons) for d in decisions]
    out["stop_reference"] = [d.stop_reference for d in decisions]
    out["initial_risk_pct"] = [d.initial_risk_pct for d in decisions]
    out["target_reference"] = [d.target_reference for d in decisions]
    out["reward_risk"] = [d.reward_risk for d in decisions]
    return out


def _risk_context(row: pd.Series, *, bullish: bool, last_price: float) -> dict[str, float]:
    atr_pct = _row_float(row, "atr_pct_20d")
    atr = last_price * atr_pct / 100.0 if atr_pct is not None and atr_pct > 0 else None
    support = _row_float(row, "nearest_support")
    resistance = _row_float(row, "nearest_resistance")

    if bullish:
        stop = support if support is not None and support < last_price else (
            last_price - atr if atr is not None else float("nan")
        )
        target = resistance if resistance is not None and resistance > last_price else (
            last_price + 2.0 * atr if atr is not None else float("nan")
        )
        risk_dollars = last_price - stop
        reward_dollars = target - last_price
    else:
        stop = resistance if resistance is not None and resistance > last_price else (
            last_price + atr if atr is not None else float("nan")
        )
        target = support if support is not None and support < last_price else (
            last_price - 2.0 * atr if atr is not None else float("nan")
        )
        risk_dollars = stop - last_price
        reward_dollars = last_price - target

    if not all(math.isfinite(v) for v in (stop, target, risk_dollars, reward_dollars)):
        return {
            "stop_reference": float("nan"),
            "initial_risk_pct": float("nan"),
            "target_reference": float("nan"),
            "reward_risk": float("nan"),
            "risk_score": 0.0,
        }

    initial_risk_pct = max(0.0, risk_dollars / last_price * 100.0)
    reward_risk = reward_dollars / risk_dollars if risk_dollars > 0 else float("nan")

    if not math.isfinite(reward_risk) or reward_risk <= 0:
        risk_score = 0.0
    else:
        rr_score = min(1.0, reward_risk / 2.0)
        risk_size_score = 1.0 if initial_risk_pct <= 2.5 else max(0.0, 1.0 - (initial_risk_pct - 2.5) / 5.0)
        risk_score = min(rr_score, risk_size_score)

    return {
        "stop_reference": round(stop, 4),
        "initial_risk_pct": round(initial_risk_pct, 3),
        "target_reference": round(target, 4),
        "reward_risk": round(reward_risk, 3) if math.isfinite(reward_risk) else float("nan"),
        "risk_score": risk_score,
    }


def _stand_aside(reason: str, market_bias: MarketBias) -> TradeDecision:
    reasons = (reason, *market_bias.reasons[:2])
    return TradeDecision(
        action="stand_aside",
        setup_score=0.0,
        direction_score=0.0,
        timing_score=0.0,
        risk_score=0.0,
        reasons=reasons,
        stop_reference=float("nan"),
        initial_risk_pct=float("nan"),
        target_reference=float("nan"),
        reward_risk=float("nan"),
    )
