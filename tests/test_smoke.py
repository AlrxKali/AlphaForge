"""Smoke tests for the parts that don't need the heavy engine stack.

These exercise config validation, the factor, the metric math, the no-lookahead
weight shift, and walk-forward splitting. For example, the correctness-critical logic.
The vectorbt simulation itself is covered separately once the 'engine' extra is
installed.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from alphaforge.config import BacktestConfig, DataConfig, FactorConfig
from alphaforge.engine.backtest import build_target_weights
from alphaforge.factors import get_factor
from alphaforge.metrics.performance import compute_metrics, max_drawdown, sharpe
from alphaforge.validation import generate_windows


def _fake_prices(symbols, days=400, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-01", periods=days)
    close = pd.DataFrame(
        100 * np.cumprod(1 + rng.normal(0.0005, 0.01, (days, len(symbols))), axis=0),
        index=idx,
        columns=symbols,
    )
    return pd.concat({"close": close}, axis=1)


def _cfg(symbols):
    return BacktestConfig(
        data=DataConfig(symbols=symbols, start=date(2020, 1, 1), end=date(2021, 6, 1)),
        factor=FactorConfig(name="momentum"),
        top_n=2,
    )


def test_config_rejects_bad_dates():
    with pytest.raises(ValueError):
        DataConfig(symbols=["AAPL"], start=date(2021, 1, 1), end=date(2020, 1, 1))


def test_momentum_is_trailing_only():
    prices = _fake_prices(["A", "B", "C", "D"])
    scores = get_factor("momentum", lookback=60, skip=5).compute(prices)
    # Warmup region must be NaN; no score before enough history exists.
    assert scores.iloc[0].isna().all()
    assert scores.shape == prices["close"].shape


def test_weights_are_shifted_no_lookahead():
    prices = _fake_prices(["A", "B", "C", "D"])
    scores = get_factor("momentum", lookback=60, skip=5).compute(prices)
    cfg = _cfg(["A", "B", "C", "D"])
    w = build_target_weights(scores, cfg)
    # First row must be flat: a signal at t is never traded at t.
    assert w.iloc[0].sum() == 0
    # Each active day holds exactly top_n names, equally weighted to ~100%.
    active = w[w.sum(axis=1) > 0]
    assert np.allclose(active.sum(axis=1), 1.0)
    assert (active > 0).sum(axis=1).max() == cfg.top_n


def test_metrics_basic_identities():
    r = pd.Series([0.01, -0.005, 0.02, 0.0, -0.01] * 60)
    stats = compute_metrics(r)
    assert stats.max_drawdown <= 0
    assert -1 <= stats.hit_rate <= 1
    # A flat series has zero Sharpe and zero drawdown.
    flat = pd.Series([0.0] * 100)
    assert sharpe(flat) == 0.0
    assert max_drawdown(flat) == 0.0


def test_walkforward_windows_no_leakage():
    windows = generate_windows(date(2010, 1, 1), date(2020, 1, 1), train_months=24, test_months=12)
    assert windows, "expected at least one window"
    for w in windows:
        assert w.test_start > w.train_end  # the core guarantee
