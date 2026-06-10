"""End-to-end orchestration: config in, BacktestResult out.

This is the single seam the CLI, a notebook, or the API endpoint all call.
It wires the pipeline together but contains no algorithm of its own. Each step
lives in its own module.
"""

from __future__ import annotations

from alphaforge.config import BacktestConfig
from alphaforge.data import get_provider
from alphaforge.engine import BacktestResult, run_backtest
from alphaforge.factors import get_factor


def run(cfg: BacktestConfig) -> BacktestResult:
    provider = get_provider(cfg.data.provider)
    prices = provider.get_prices(cfg.data.symbols, cfg.data.start, cfg.data.end)

    factor = get_factor(cfg.factor.name, **cfg.factor.params)
    scores = factor.compute(prices)

    return run_backtest(prices, scores, cfg)
