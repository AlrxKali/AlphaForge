"""Tests for the factor framework: the price-based factors, the z-score helper,
and composite blending. All factors must be trailing-only (no lookahead) and
return 'higher = more attractive' scores."""

from __future__ import annotations

import numpy as np
import pandas as pd

from alphaforge.factors import get_factor
from alphaforge.factors.base import zscore


def _prices_from_close(close: pd.DataFrame) -> pd.DataFrame:
    return pd.concat({"close": close}, axis=1)


def _trending(days=200):
    """Two names: STEADY (low vol, gentle up) and WILD (high vol)."""
    idx = pd.bdate_range("2021-01-01", periods=days)
    steady = 100 * (1 + 0.0005) ** np.arange(days)
    rng = np.random.default_rng(0)
    wild = 100 * np.cumprod(1 + rng.normal(0.0005, 0.04, days))
    return _prices_from_close(pd.DataFrame({"STEADY": steady, "WILD": wild}, index=idx))


def test_zscore_is_cross_sectional_and_centered():
    df = pd.DataFrame({"A": [1.0, 2.0], "B": [3.0, 4.0], "C": [5.0, 6.0]})
    z = zscore(df)
    # Each row standardized: mean ~0 across symbols.
    assert np.allclose(z.mean(axis=1).to_numpy(), 0.0, atol=1e-9)
    # Ordering preserved within a row.
    assert z.loc[0, "A"] < z.loc[0, "B"] < z.loc[0, "C"]


def test_volatility_prefers_low_vol_and_is_trailing():
    scores = get_factor("volatility", lookback=63).compute(_trending())
    assert scores.iloc[0].isna().all()             # warmup -> NaN (no lookahead)
    # Low-vol STEADY should score higher (less negative) than WILD at the end.
    assert scores["STEADY"].iloc[-1] > scores["WILD"].iloc[-1]


def test_mean_reversion_prefers_recent_losers():
    idx = pd.bdate_range("2021-01-01", periods=60)
    up = pd.Series(np.linspace(100, 130, 60), index=idx)    # recent winner
    down = pd.Series(np.linspace(130, 100, 60), index=idx)  # recent loser
    prices = _prices_from_close(pd.DataFrame({"UP": up, "DOWN": down}))
    scores = get_factor("mean_reversion", lookback=21).compute(prices)
    # The faller is the attractive (high) score under reversal.
    assert scores["DOWN"].iloc[-1] > scores["UP"].iloc[-1]


def test_composite_blends_components():
    prices = _trending()
    comp = get_factor(
        "composite",
        components=[
            {"name": "momentum", "weight": 1.0, "params": {"lookback": 60, "skip": 5}},
            {"name": "volatility", "weight": 1.0, "params": {"lookback": 60}},
        ],
    )
    blended = comp.compute(prices)
    assert blended.shape == prices["close"].shape
    # The blend equals the weighted sum of z-scored components.
    mom = zscore(get_factor("momentum", lookback=60, skip=5).compute(prices))
    vol = zscore(get_factor("volatility", lookback=60).compute(prices))
    expected = mom.add(vol, fill_value=0.0)
    pd.testing.assert_frame_equal(blended, expected)


def test_composite_requires_components():
    import pytest

    with pytest.raises(ValueError):
        get_factor("composite", components=[])
