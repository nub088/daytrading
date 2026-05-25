"""Filter base class.

A Filter takes a per-ticker OHLCV DataFrame and returns True/False for
whether that ticker passes. Filters are stateless; thresholds are
parameters set at construction.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class Filter(ABC):
    """Stateless filter applied to a single ticker's OHLCV history."""

    name: str = "filter"

    @abstractmethod
    def passes(self, ohlcv: pd.DataFrame) -> bool:
        """Return True if the ticker passes this filter."""

    def __repr__(self) -> str:
        attrs = ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items())
        return f"{type(self).__name__}({attrs})"
