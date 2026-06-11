"""End-to-end orchestration: config in, BacktestResult out.

This is the single seam the CLI, a notebook, or the API endpoint all call.
It wires the pipeline together but contains no algorithm of its own. Each step
lives in its own module.

Phase 2 made the data path point-in-time aware:
    universe -> download set -> quality check -> tradeability mask -> engine
"""

from __future__ import annotations

from alphaforge.config import BacktestConfig
from alphaforge.data import get_provider, tradeable_mask, validate_prices
from alphaforge.engine import BacktestResult, run_backtest
from alphaforge.factors import get_factor
from alphaforge.universe import from_config as universe_from_config


def run(cfg: BacktestConfig) -> BacktestResult:
    # 1. Resolve the investable set (static list or point-in-time membership).
    universe = universe_from_config(cfg.data.resolved_universe())
    symbols = universe.all_symbols(cfg.data.start, cfg.data.end)

    # 2. Fetch prices for the full historical membership (the download set).
    provider = get_provider(cfg.data.provider)
    prices = provider.get_prices(symbols, cfg.data.start, cfg.data.end)

    # 3. Inspect data quality before trusting it.
    report = validate_prices(prices)

    # 4. Tradeability = universe member on that date AND a usable price exists.
    members = universe.membership(prices.index)
    tradeable = tradeable_mask(prices) & members.reindex(
        index=prices.index, columns=prices["close"].columns, fill_value=False
    )

    # 5. Signal -> backtest, with the mask enforcing point-in-time correctness.
    factor = get_factor(cfg.factor.name, **cfg.factor.params)
    scores = factor.compute(prices)

    result = run_backtest(prices, scores, cfg, tradeable=tradeable)
    result.quality = report
    return result
