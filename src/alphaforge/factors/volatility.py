"""Low-volatility factor.

The low-volatility anomaly: historically, lower-risk stocks have delivered
better risk-adjusted (and sometimes outright) returns than high-risk ones. We
score by the *negative* of trailing realized volatility, so that low-vol names
get the high (attractive) score the engine ranks on. Trailing-only -> no
lookahead.
"""

from __future__ import annotations

import pandas as pd

from alphaforge.factors.base import Factor, register_factor


@register_factor
class VolatilityFactor(Factor):
    name = "volatility"

    def __init__(self, lookback: int = 63, **params) -> None:
        super().__init__(lookback=lookback, **params)
        self.lookback = lookback

    def compute(self, prices: pd.DataFrame) -> pd.DataFrame:
        rets = self.close(prices).pct_change(fill_method=None)
        vol = rets.rolling(self.lookback).std()
        return -vol  # low volatility == attractive == high score
