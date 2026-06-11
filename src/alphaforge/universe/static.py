"""A fixed, time-invariant universe.

Every symbol is considered a member for the entire backtest. This reproduces
the Phase-1 behavior (a hand-picked list) and is the right tool when you
genuinely mean "these exact names, the whole time." It carries selection bias
by construction, so it's for research convenience, not survivorship-free studies.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from alphaforge.universe.base import Universe, register_universe


@register_universe
class StaticUniverse(Universe):
    name = "static"

    def __init__(self, symbols: list[str], **_) -> None:
        if not symbols:
            raise ValueError("StaticUniverse requires at least one symbol")
        # De-dupe while preserving order.
        seen: dict[str, None] = {}
        for s in symbols:
            seen.setdefault(s.strip().upper(), None)
        self.symbols = list(seen)

    def all_symbols(self, start: date, end: date) -> list[str]:
        return list(self.symbols)

    def membership(self, dates: pd.DatetimeIndex) -> pd.DataFrame:
        return pd.DataFrame(True, index=dates, columns=self.symbols)
