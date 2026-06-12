"""Short-term mean-reversion (reversal) factor.

Over short horizons (days to a few weeks), recent losers tend to bounce and
recent winners to give back. The opposite of long-horizon momentum. We score
by the *negative* of the recent short-window return, so recent underperformers
get the high (attractive) score. Trailing-only -> no lookahead.

Note this is deliberately the mirror image of MomentumFactor. Blending the two
(short-reversal + long-momentum) is a classic combination, easy via the
composite factor.
"""

from __future__ import annotations

import pandas as pd

from alphaforge.factors.base import Factor, register_factor


@register_factor
class MeanReversionFactor(Factor):
    name = "mean_reversion"

    def __init__(self, lookback: int = 21, **params) -> None:
        super().__init__(lookback=lookback, **params)
        self.lookback = lookback

    def compute(self, prices: pd.DataFrame) -> pd.DataFrame:
        recent = self.close(prices).pct_change(self.lookback, fill_method=None)
        return -recent  # recent losers == attractive == high score
