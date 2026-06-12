"""Composite factor: blend several factors into one signal.

Each component is computed, z-scored cross-sectionally (so factors on different
scales become comparable), multiplied by its weight, and summed. Because every
factor already returns "higher = more attractive," no per-factor sign handling
is needed: a low-vol or reversal factor negates internally.

Configured via params, so it flows through the CLI/API/notebook like any factor:

    FactorConfig(name="composite", params={"components": [
        {"name": "momentum",      "weight": 1.0, "params": {"lookback": 252}},
        {"name": "mean_reversion","weight": 0.5, "params": {"lookback": 21}},
        {"name": "volatility",    "weight": 0.5},
    ]})
"""

from __future__ import annotations

import pandas as pd

from alphaforge.factors.base import Factor, get_factor, register_factor, zscore


@register_factor
class CompositeFactor(Factor):
    name = "composite"

    def __init__(self, components: list[dict] | None = None, **params) -> None:
        super().__init__(components=components, **params)
        if not components:
            raise ValueError("CompositeFactor requires a non-empty 'components' list")
        self._factors: list[Factor] = []
        self._weights: list[float] = []
        for c in components:
            self._factors.append(get_factor(c["name"], **c.get("params", {})))
            self._weights.append(float(c.get("weight", 1.0)))

    def compute(self, prices: pd.DataFrame) -> pd.DataFrame:
        blended: pd.DataFrame | None = None
        for factor, weight in zip(self._factors, self._weights):
            contribution = zscore(factor.compute(prices)) * weight
            blended = contribution if blended is None else blended.add(contribution, fill_value=0.0)
        return blended
