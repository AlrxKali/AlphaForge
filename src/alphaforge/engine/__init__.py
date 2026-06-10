"""Execution engine: turn factor scores into a backtested portfolio.

vectorbt (numba-backed) is the execution core. It is imported lazily inside
the functions so the rest of the package works without the heavy stack.
"""

from alphaforge.engine.backtest import BacktestResult, run_backtest

__all__ = ["run_backtest", "BacktestResult"]
