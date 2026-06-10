"""Core performance metrics, implemented directly.

We compute the headline numbers ourselves (they're simple, and annualization
conventions are easy to get subtly wrong if left to a black box). The richer
visual tearsheet is delegated to quantstats in the reporting layer.

All functions take a daily returns Series. ``periods=252`` is the trading-day
annualization factor for US equities.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

TRADING_DAYS = 252


@dataclass
class PerformanceStats:
    cagr: float
    ann_volatility: float
    sharpe: float
    sortino: float
    max_drawdown: float
    calmar: float
    hit_rate: float
    total_return: float

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


def _ann_return(returns: pd.Series, periods: int) -> float:
    if returns.empty:
        return 0.0
    growth = (1 + returns).prod()
    years = len(returns) / periods
    if years <= 0 or growth <= 0:
        return 0.0
    return growth ** (1 / years) - 1


def max_drawdown(returns: pd.Series) -> float:
    equity = (1 + returns).cumprod()
    peak = equity.cummax()
    drawdown = equity / peak - 1
    return float(drawdown.min())


def sharpe(returns: pd.Series, rf: float = 0.0, periods: int = TRADING_DAYS) -> float:
    excess = returns - rf / periods
    sd = excess.std(ddof=1)
    if sd == 0 or np.isnan(sd):
        return 0.0
    return float(excess.mean() / sd * np.sqrt(periods))


def sortino(returns: pd.Series, rf: float = 0.0, periods: int = TRADING_DAYS) -> float:
    excess = returns - rf / periods
    downside = excess[excess < 0]
    dd = np.sqrt((downside**2).mean()) if len(downside) else 0.0
    if dd == 0 or np.isnan(dd):
        return 0.0
    return float(excess.mean() / dd * np.sqrt(periods))


def compute_metrics(
    returns: pd.Series, rf: float = 0.0, periods: int = TRADING_DAYS
) -> PerformanceStats:
    returns = returns.dropna()
    cagr = _ann_return(returns, periods)
    mdd = max_drawdown(returns)
    vol = float(returns.std(ddof=1) * np.sqrt(periods)) if len(returns) > 1 else 0.0
    return PerformanceStats(
        cagr=cagr,
        ann_volatility=vol,
        sharpe=sharpe(returns, rf, periods),
        sortino=sortino(returns, rf, periods),
        max_drawdown=mdd,
        calmar=float(cagr / abs(mdd)) if mdd != 0 else 0.0,
        hit_rate=float((returns > 0).mean()) if len(returns) else 0.0,
        total_return=float((1 + returns).prod() - 1),
    )
