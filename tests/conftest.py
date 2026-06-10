"""Shared synthetic OHLCV fixtures for the scanner test suite.

All frames match the cache schema (tools/data/cache.py): lowercase
columns open/high/low/close/volume, DatetimeIndex of business days.
Everything is deterministic — no network, no unseeded randomness.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Make `tools` importable regardless of pytest rootdir/sys.path behavior.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# All fixtures share the same calendar so date intersections are full.
N_BARS = 260
START = "2025-06-02"


def bday_index(n: int = N_BARS, start: str = START) -> pd.DatetimeIndex:
    return pd.bdate_range(start=start, periods=n)


def make_ohlcv(
    close: np.ndarray,
    volume: np.ndarray | float = 2_000_000,
    spread: float = 1.0,
    start: str = START,
) -> pd.DataFrame:
    """Build a schema-conformant OHLCV frame from a close series."""
    close = np.asarray(close, dtype=float)
    n = len(close)
    if np.isscalar(volume) or np.ndim(volume) == 0:
        volume = np.full(n, float(volume))
    return pd.DataFrame(
        {
            "open": close,
            "high": close + spread / 2.0,
            "low": close - spread / 2.0,
            "close": close,
            "volume": np.asarray(volume, dtype=float),
        },
        index=bday_index(n, start),
    )


@pytest.fixture
def flat_ohlcv() -> pd.DataFrame:
    """Constant close 100, high 101, low 99, volume 1.5M."""
    return make_ohlcv(np.full(N_BARS, 100.0), volume=1_500_000, spread=2.0)


@pytest.fixture
def uptrend_ohlcv() -> pd.DataFrame:
    """Linear uptrend: close 50.0, 50.2, ... (+0.2/day)."""
    return make_ohlcv(50.0 + 0.2 * np.arange(N_BARS))


@pytest.fixture
def downtrend_ohlcv() -> pd.DataFrame:
    """Linear downtrend: close 150.0, 149.8, ... (-0.2/day)."""
    return make_ohlcv(150.0 - 0.2 * np.arange(N_BARS))


@pytest.fixture
def breakout_ohlcv() -> pd.DataFrame:
    """Triangular wave oscillating 95..100 (peaks at exactly 100 every
    20 bars -> horizontal resistance with high pivots at 100.5), then a
    final bar that closes well above the level.

    Yesterday's close (99.5) is below the level, today's close (104.0)
    is above it -> a bullish horizontal breakout on the last bar.
    """
    phase = np.arange(N_BARS) % 20
    close = np.where(phase <= 10, 95.0 + 0.5 * phase, 95.0 + 0.5 * (20 - phase))
    close = close.astype(float)
    close[-2] = 99.5   # below the ~100.5 resistance
    close[-1] = 104.0  # breaks above it
    return make_ohlcv(close, spread=1.0)


@pytest.fixture
def short_ohlcv() -> pd.DataFrame:
    """Only 10 bars — too short for most indicators/signals."""
    return make_ohlcv(np.full(10, 100.0), spread=2.0)


@pytest.fixture
def flat_market(flat_ohlcv: pd.DataFrame) -> pd.DataFrame:
    """A flat 'SPY' reference on the same calendar."""
    return flat_ohlcv.copy()
