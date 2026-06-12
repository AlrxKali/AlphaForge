"""Fundamentals layer: point-in-time company financials behind a provider interface."""

from alphaforge.fundamentals.base import (
    FundamentalProvider,
    get_fundamental_provider,
    register_fundamental_provider,
)

# Import concrete providers so their registration decorators run.
from alphaforge.fundamentals import edgar

__all__ = [
    "FundamentalProvider",
    "get_fundamental_provider",
    "register_fundamental_provider",
]
