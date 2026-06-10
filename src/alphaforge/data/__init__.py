"""Data layer: download, cache, and serve point-in-time-correct price data."""

from alphaforge.data.provider import DataProvider, get_provider, register_provider

# Import concrete providers so their @register_provider decorators run.
from alphaforge.data import yfinance_provider  # noqa: F401  (registration side-effect)

__all__ = ["DataProvider", "get_provider", "register_provider"]
