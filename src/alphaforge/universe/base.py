"""The Universe interface, *which* symbols are investable, and *when*.

This is the structural fix for survivorship bias. A backtest must only ever
consider names that were actually in the investable set on each date, not the
set that happens to still exist today. By routing membership through this
interface (mirroring ``DataProvider``), the rest of the system is point-in-time
correct regardless of how membership is sourced.

A ``membership`` panel is a boolean (date x symbol) frame: True where the symbol
was a member of the universe on that date.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

import pandas as pd

# pandas Timestamps top out near 2262. Use a sentinel for "still active".
FAR_FUTURE = pd.Timestamp("2261-12-31")


class Universe(ABC):
    name: str = "abstract"

    @abstractmethod
    def all_symbols(self, start: date, end: date) -> list[str]:
        """Every symbol that was a member at any point in [start, end].

        This is the download set. We fetch prices for all of them, then mask
        per-date with ``membership``."""
        ...

    @abstractmethod
    def membership(self, dates: pd.DatetimeIndex) -> pd.DataFrame:
        """Boolean (date x symbol) membership panel over the given dates."""
        ...


# --- universe registry --------------------------------------------------------

_REGISTRY: dict[str, type[Universe]] = {}


def register_universe(cls: type[Universe]) -> type[Universe]:
    _REGISTRY[cls.name] = cls
    return cls


def get_universe(kind: str, **kwargs) -> Universe:
    if kind not in _REGISTRY:
        raise KeyError(f"Unknown universe '{kind}'. Registered: {list(_REGISTRY)}")
    return _REGISTRY[kind](**kwargs)
