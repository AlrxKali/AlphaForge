"""Data layer: download, cache, and serve point-in-time-correct price data."""

from alphaforge.data.provider import DataProvider, get_provider, register_provider
from alphaforge.data.quality import QualityReport, tradeable_mask, validate_prices

# Import concrete providers so their @register_provider decorators run.
from alphaforge.data import yfinance_provider 

__all__ = [
    "DataProvider",
    "get_provider",
    "register_provider",
    "QualityReport",
    "tradeable_mask",
    "validate_prices",
]
