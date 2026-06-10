"""Classic cross-sectional momentum.

Score = total return over a ``lookback`` window, optionally skipping the most
recent ``skip`` days (the standard 12-1 momentum convention skips the last
month to avoid short-term reversal). Uses only trailing data -> no lookahead.
"""

from __future__ import annotations

import pandas as pd

from alphaforge.factors.base import Factor, register_factor


@register_factor
class MomentumFactor(Factor):
    name = "momentum"

    def __init__(self, lookback: int = 252, skip: int = 21, **params) -> None:
        super().__init__(lookback=lookback, skip=skip, **params)
        self.lookback = lookback
        self.skip = skip

    def compute(self, prices: pd.DataFrame) -> pd.DataFrame:
        close = self.close(prices)
        # Return from (t - lookback) to (t - skip). pct_change over the window,
        # then shift by `skip` so the most recent `skip` days are excluded.
        window_return = close.pct_change(self.lookback - self.skip, fill_method=None)
        if self.skip:
            window_return = window_return.shift(self.skip)
        return window_return
