"""The backtest core. A thin, correctness-focused wrapper over vectorbt.

Responsibilities:
  1. Turn factor scores into a top-N long-only target weight matrix.
  2. Enforce the no-lookahead rule by trading signals on the *next* bar.
  3. Apply rebalancing cadence and transaction costs.
  4. Hand the weights + prices to vectorbt to simulate fills and equity.

We deliberately keep portfolio construction here (ours, testable) and delegate
only the fill/PnL simulation to vectorbt.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from alphaforge.config import BacktestConfig, Rebalance

_REBALANCE_RULE = {Rebalance.DAILY: None, Rebalance.WEEKLY: "W-FRI", Rebalance.MONTHLY: "ME"}


@dataclass
class BacktestResult:
    """Holds everything downstream (metrics, reporting) needs."""

    equity_curve: pd.Series
    returns: pd.Series
    weights: pd.DataFrame
    config: BacktestConfig
    portfolio: object | None = None  # the raw vbt.Portfolio, if available


def build_target_weights(scores: pd.DataFrame, cfg: BacktestConfig) -> pd.DataFrame:
    """Top-N equal-weight long-only target weights from factor scores.

    Critically: the returned weights are shifted forward one bar so that a
    signal computed from data through day t is only acted on at t+1. This is
    the primary lookahead-bias guard at the portfolio level.
    """
    rule = _REBALANCE_RULE[cfg.rebalance]

    # Rank cross-sectionally each day; keep the top-N.
    ranks = scores.rank(axis=1, ascending=False, method="first")
    selected = ranks <= cfg.top_n
    weights = selected.div(selected.sum(axis=1), axis=0).fillna(0.0)

    # Only let weights change on rebalance dates; hold in between.
    if rule is not None:
        rebal_days = weights.resample(rule).last().index
        on_rebal = pd.Series(weights.index.isin(rebal_days), index=weights.index)
        weights = weights.where(on_rebal, axis=0).ffill().fillna(0.0)

    # Shift: act tomorrow on today's signal. THE no-lookahead guard.
    return weights.shift(1).fillna(0.0)


def run_backtest(prices: pd.DataFrame, scores: pd.DataFrame, cfg: BacktestConfig) -> BacktestResult:
    import vectorbt as vbt  # lazy heavy import

    close = prices["close"]
    weights = build_target_weights(scores, cfg).reindex(close.index).fillna(0.0)

    # Drop the warmup region where the factor is all-NaN (no position yet).
    valid = weights.abs().sum(axis=1) > 0
    if valid.any():
        first = valid.idxmax()
        close = close.loc[first:]
        weights = weights.loc[first:]

    total_cost = (cfg.costs.commission_bps + cfg.costs.slippage_bps) / 1e4

    pf = vbt.Portfolio.from_orders(
        close=close,
        size=weights,
        size_type="targetpercent",
        group_by=True,            # one portfolio across the universe
        cash_sharing=True,
        fees=total_cost,
        init_cash=cfg.initial_cash,
        freq="1D",
        call_seq="auto",          # sell-before-buy so cash is available
    )

    equity = pf.value()
    if isinstance(equity, pd.DataFrame):  # collapse grouped output to a Series
        equity = equity.iloc[:, 0]
    returns = equity.pct_change().fillna(0.0)

    return BacktestResult(
        equity_curve=equity,
        returns=returns,
        weights=weights,
        config=cfg,
        portfolio=pf,
    )
