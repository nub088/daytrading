"""Filter composition. AND-chains a list of filters."""
from __future__ import annotations

import pandas as pd

from .base import Filter


class AndFilter(Filter):
    """All sub-filters must pass."""

    name = "and"

    def __init__(self, filters: list[Filter]) -> None:
        self.filters = list(filters)

    def passes(self, ohlcv: pd.DataFrame) -> bool:
        return all(f.passes(ohlcv) for f in self.filters)

    def explain(self, ohlcv: pd.DataFrame) -> dict[str, bool]:
        """Per-filter pass/fail for debugging or output-CSV columns."""
        return {f.name: f.passes(ohlcv) for f in self.filters}
