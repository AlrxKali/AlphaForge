"""Value factor: cheap stocks (high book-to-market) score high.

Book-to-market is the classic Fama-French value metric:

    book_to_market = book_equity / market_cap = book_equity / (price * shares)

Book equity and shares come from a point-in-time FundamentalProvider (EDGAR by
default), so on each date we use only figures already filed by then. Price is the
current adjusted close. Higher book-to-market = cheaper = more attractive.

Because the fundamentals are filing-date-stamped and forward-filled, this factor
is lookahead-free, unlike a naive "today's P/B applied to the whole history."
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from alphaforge.factors.base import Factor, register_factor


@register_factor
class ValueFactor(Factor):
    name = "value"

    def __init__(self, provider="edgar", metric: str = "book_to_market", **params) -> None:
        super().__init__(provider=provider, metric=metric, **params)
        if metric != "book_to_market":
            raise ValueError(f"unsupported value metric '{metric}'")
        self.metric = metric
        self._provider = provider  # resolved lazily (name or instance)

    def _resolve_provider(self):
        if isinstance(self._provider, str):
            from alphaforge.fundamentals import get_fundamental_provider

            return get_fundamental_provider(self._provider)
        return self._provider

    def compute(self, prices: pd.DataFrame) -> pd.DataFrame:
        close = self.close(prices)
        symbols = list(close.columns)
        provider = self._resolve_provider()

        facts = provider.point_in_time(symbols, ["book_equity", "shares"], close.index)
        book = facts["book_equity"].reindex(columns=symbols)
        shares = facts["shares"].reindex(columns=symbols)

        market_cap = close * shares
        btm = book / market_cap
        return btm.replace([np.inf, -np.inf], np.nan)  # higher btm == cheaper == attractive
