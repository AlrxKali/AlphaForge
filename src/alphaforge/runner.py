"""End-to-end orchestration: config in, BacktestResult out.

This is the single seam the CLI, a notebook, or the API endpoint all call.
It wires the pipeline together but contains no algorithm of its own. Each step
lives in its own module.

Phase 2 made the data path point-in-time aware:
    universe -> download set -> quality check -> tradeability mask -> engine

The pipeline is split into ``load_inputs`` (the expensive, factor-independent
data work) and ``compute_result`` (cheap, varies with factor params). Walk-forward
relies on this split to load data once and re-run the engine across many windows
and parameter sets without re-downloading.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from alphaforge.config import BacktestConfig
from alphaforge.data import QualityReport, get_provider, tradeable_mask, validate_prices
from alphaforge.engine import BacktestResult, run_backtest
from alphaforge.factors import get_factor
from alphaforge.universe import from_config as universe_from_config


@dataclass
class Inputs:
    """Factor-independent backtest inputs: the price panel, the point-in-time
    tradeability mask, and the data-quality report. Computed once, reused across
    factor params / walk-forward windows."""

    prices: pd.DataFrame
    tradeable: pd.DataFrame
    quality: QualityReport


def load_inputs(cfg: BacktestConfig) -> Inputs:
    universe = universe_from_config(cfg.data.resolved_universe())
    symbols = universe.all_symbols(cfg.data.start, cfg.data.end)

    provider = get_provider(cfg.data.provider)
    prices = provider.get_prices(symbols, cfg.data.start, cfg.data.end)

    report = validate_prices(prices)
    members = universe.membership(prices.index)
    tradeable = tradeable_mask(prices) & members.reindex(
        index=prices.index, columns=prices["close"].columns, fill_value=False
    )
    return Inputs(prices=prices, tradeable=tradeable, quality=report)


def compute_result(inputs: Inputs, cfg: BacktestConfig) -> BacktestResult:
    factor = get_factor(cfg.factor.name, **cfg.factor.params)
    scores = factor.compute(inputs.prices)
    result = run_backtest(inputs.prices, scores, cfg, tradeable=inputs.tradeable)
    result.quality = inputs.quality
    return result


def run(cfg: BacktestConfig) -> BacktestResult:
    return compute_result(load_inputs(cfg), cfg)
