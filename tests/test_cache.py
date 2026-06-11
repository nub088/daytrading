"""Tests for tools/data/cache.py parquet helpers."""
# Created by Codex.
from __future__ import annotations

from datetime import datetime

import numpy as np

from tests.conftest import make_ohlcv
from tools.data import cache


def test_cache_last_date_reads_parquet_rows(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    df = make_ohlcv(np.array([10.0, 11.0, 12.0]), start="2026-06-08")

    cache.write("FROG", df)

    assert cache.cache_last_date("FROG") == datetime(2026, 6, 10)
