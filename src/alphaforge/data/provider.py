"""The DataProvider interface. The single most important abstraction here.

Everything downstream depends on price data *only* through this interface.
Swapping yfinance (which has survivorship bias) for a point-in-time-correct,
delisting-inclusive source (Polygon, Tiingo, Norgate, ...) is therefore a
one-class change that the rest of the system never sees.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

import pandas as pd


class DataProvider(ABC):
    """Returns OHLCV data for a universe of symbols over a date range.

    Contract for implementations:
      * Return a DataFrame with a tz-naive DatetimeIndex (daily bars).
      * Columns are a MultiIndex: (field, symbol) where field is one of
        {open, high, low, close, volume}. 'close' MUST be split/dividend
        adjusted for return calculations.
      * Rows are sorted ascending by date. No future leakage: a bar dated `t`
        contains only information known at the close of `t`.
    """

    name: str = "abstract"

    @abstractmethod
    def get_prices(
        self, symbols: list[str], start: date, end: date
    ) -> pd.DataFrame:  # pragma: no cover - interface
        ...


# --- tiny provider registry so configs can refer to providers by name ---------

_REGISTRY: dict[str, type[DataProvider]] = {}


def register_provider(cls: type[DataProvider]) -> type[DataProvider]:
    """Class decorator: register a provider under its ``name`` attribute."""
    _REGISTRY[cls.name] = cls
    return cls


def get_provider(name: str, **kwargs) -> DataProvider:
    if name not in _REGISTRY:
        raise KeyError(f"Unknown data provider '{name}'. Registered: {list(_REGISTRY)}")
    return _REGISTRY[name](**kwargs)
