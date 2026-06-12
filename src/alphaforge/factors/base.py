"""The Factor interface.

A factor maps price history -> a per-day, per-symbol score. The engine ranks
symbols cross-sectionally on that score and holds the top-N.

Lookahead-bias contract: ``compute`` must produce a score for day ``t`` using
ONLY data up to and including ``t``. The engine further enforces this by
shifting signals one bar before trading on them, but factors must not peek
forward internally (e.g. no centered rolling windows, no full-sample scaling).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


def zscore(scores: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional (per-date) z-score: standardize each row across symbols.

    This is what makes heterogeneous factors comparable before blending: a
    momentum return (~0.2) and a volatility (~0.01) live on different scales, so
    we re-express both as "standard deviations above/below the cross-section."
    Rows with fewer than two valid values yield 0 (no cross-section to rank).
    """
    mean = scores.mean(axis=1)
    std = scores.std(axis=1, ddof=0)
    z = scores.sub(mean, axis=0).div(std.replace(0.0, pd.NA), axis=0)
    return z.where(scores.notna())


class Factor(ABC):
    name: str = "abstract"

    def __init__(self, **params) -> None:
        self.params = params

    @abstractmethod
    def compute(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Given a (field, symbol) price frame, return a DataFrame of scores
        indexed by date with one column per symbol. Higher = more attractive."""
        ...

    @staticmethod
    def close(prices: pd.DataFrame) -> pd.DataFrame:
        """Convenience: pull the adjusted-close (date x symbol) sub-frame."""
        return prices["close"]


# --- factor registry ----------------------------------------------------------

_REGISTRY: dict[str, type[Factor]] = {}


def register_factor(cls: type[Factor]) -> type[Factor]:
    _REGISTRY[cls.name] = cls
    return cls


def get_factor(name: str, **params) -> Factor:
    if name not in _REGISTRY:
        raise KeyError(f"Unknown factor '{name}'. Registered: {list(_REGISTRY)}")
    return _REGISTRY[name](**params)
