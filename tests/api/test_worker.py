"""Unit tests for the worker payload builders (offline, no Supabase/Redis).

These pin the structured-results contract the frontend depends on: aligned
series arrays, correct drawdown, and JSON-serializable output."""

from __future__ import annotations

import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("fastapi")

from alphaforge.config import BacktestConfig, DataConfig, FactorConfig
from alphaforge.engine.backtest import BacktestResult 
from alphaforge_api.worker import _series, payload_single 


def _cfg():
    return BacktestConfig(
        data=DataConfig(symbols=["A"], start=date(2021, 1, 1), end=date(2021, 12, 31)),
        factor=FactorConfig(name="momentum"),
        name="t",
    )


def test_series_is_aligned_with_correct_drawdown():
    idx = pd.bdate_range("2021-01-01", periods=5)
    equity = pd.Series([100, 110, 105, 120, 90], index=idx, dtype=float)
    returns = equity.pct_change().fillna(0.0)
    s = _series(equity, returns)

    assert s["dates"][0] == "2021-01-01"
    assert len(s["dates"]) == len(s["equity"]) == len(s["returns"]) == len(s["drawdown"]) == 5
    # At the running peak (120) drawdown is 0. The final 90 is -25% off that peak.
    assert s["drawdown"][3] == 0.0
    assert abs(s["drawdown"][4] - (90 / 120 - 1)) < 1e-9


def test_payload_single_shape_and_json_serializable():
    idx = pd.bdate_range("2021-01-01", periods=50)
    rng = np.random.default_rng(0)
    returns = pd.Series(rng.normal(0.0005, 0.01, 50), index=idx)
    equity = 100_000 * (1 + returns).cumprod()
    result = BacktestResult(
        equity_curve=equity, returns=returns, weights=pd.DataFrame(index=idx), config=_cfg()
    )

    metrics, payload = payload_single(result)
    assert payload["kind"] == "single"
    assert "sharpe" in metrics and "sharpe" in payload["summary"]
    assert set(payload["series"]) == {"dates", "equity", "returns", "drawdown"}
    assert len(payload["series"]["equity"]) == 50
    json.dumps(payload)  # must be serializable for storage
