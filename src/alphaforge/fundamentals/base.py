"""The FundamentalProvider interface: point-in-time company fundamentals.

Mirrors ``DataProvider``: everything downstream sees fundamentals only through
this interface, so the source can be swapped. The defining requirement is
*point-in-time correctness*: a fundamental value may only appear on dates on or
after it was actually public (its filing date), never its period-end date. That
reporting lag is exactly what stops a value factor from peeking at a Q4 balance
sheet in January before it was filed.

``point_in_time`` returns, per requested field, a (date x symbol) panel already
forward-filled from filing dates onto the given daily grid, directly consumable
by a factor.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
import pandas as pd


class FundamentalProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    def point_in_time(
        self, symbols: list[str], fields: list[str], dates: pd.DatetimeIndex
    ) -> dict[str, pd.DataFrame]:
        """For each field, a (date x symbol) panel of the latest value known
        as-of each date (forward-filled from filing dates; NaN before the first
        filing). Unknown symbols/fields yield all-NaN columns."""
        ...


# --- provider registry --------------------------------------------------------

_REGISTRY: dict[str, type[FundamentalProvider]] = {}


def register_fundamental_provider(cls: type[FundamentalProvider]) -> type[FundamentalProvider]:
    _REGISTRY[cls.name] = cls
    return cls


def get_fundamental_provider(name: str, **kwargs) -> FundamentalProvider:
    if name not in _REGISTRY:
        raise KeyError(f"Unknown fundamental provider '{name}'. Registered: {list(_REGISTRY)}")
    return _REGISTRY[name](**kwargs)
