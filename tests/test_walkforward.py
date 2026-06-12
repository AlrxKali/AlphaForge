"""Tests for walk-forward orchestration.

The core guarantee: for each window the params with the best IN-SAMPLE (train)
Sharpe are chosen, and the stitched OOS curve is built from those params'
OUT-OF-SAMPLE (test) slices only. Pure, offline (no data download)."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from alphaforge.config import BacktestConfig, DataConfig, FactorConfig
from alphaforge.validation import generate_windows, param_grid, walk_forward_from_returns


def _cfg():
    return BacktestConfig(
        data=DataConfig(symbols=["A", "B"], start=date(2015, 1, 1), end=date(2019, 12, 31)),
        factor=FactorConfig(name="momentum"),
        name="wf-test",
    )


def test_param_grid_cartesian():
    assert param_grid(None) == [{}]
    assert param_grid({}) == [{}]
    g = param_grid({"lookback": [126, 252], "skip": [21, 42]})
    assert len(g) == 4
    assert {"lookback": 126, "skip": 21} in g
    assert {"lookback": 252, "skip": 42} in g


def test_walk_forward_selects_best_train_params_and_stitches_oos():
    idx = pd.bdate_range("2015-01-01", "2019-12-31")
    rng = np.random.default_rng(0)
    base = pd.Series(rng.normal(0, 0.01, len(idx)), index=idx)

    # Candidate A shines in 2015-2016; candidate B in 2016-2017.
    a = base.copy()
    a.loc["2015":"2016"] += 0.003
    b = base.copy()
    b.loc["2016":"2017"] += 0.003
    candidates = [({"k": "A"}, a), ({"k": "B"}, b)]

    windows = generate_windows(date(2015, 1, 1), date(2019, 12, 31), 24, 12)
    assert len(windows) == 2  # test 2017, test 2018

    wf = walk_forward_from_returns(candidates, windows, _cfg(), base)

    # Window 1 train = 2015-2016 -> A; window 2 train = 2016-2017 -> B.
    assert wf.windows[0].params == {"k": "A"}
    assert wf.windows[1].params == {"k": "B"}

    # The stitched OOS uses the CHOSEN candidate's test slice in each window.
    assert np.allclose(wf.oos_returns.loc["2017"], a.loc["2017"])
    assert np.allclose(wf.oos_returns.loc["2018"], b.loc["2018"])

    # OOS index is sorted and free of duplicate dates.
    assert wf.oos_returns.index.is_monotonic_increasing
    assert not wf.oos_returns.index.has_duplicates


def test_walk_forward_no_grid_is_single_candidate():
    idx = pd.bdate_range("2015-01-01", "2019-12-31")
    returns = pd.Series(0.0005, index=idx)
    windows = generate_windows(date(2015, 1, 1), date(2019, 12, 31), 24, 12)
    wf = walk_forward_from_returns([({}, returns)], windows, _cfg(), returns)
    # With one candidate, every window selects the base params.
    assert all(wr.params == {} for wr in wf.windows)
    assert len(wf.oos_returns) > 0
