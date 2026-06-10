"""Reporting: a plain-text summary (always available) and a rich HTML tearsheet
(via quantstats, lazily imported)."""

from __future__ import annotations

from pathlib import Path

from alphaforge.engine.backtest import BacktestResult
from alphaforge.metrics.performance import compute_metrics

_LABELS = {
    "cagr": "CAGR",
    "ann_volatility": "Ann. Volatility",
    "sharpe": "Sharpe",
    "sortino": "Sortino",
    "max_drawdown": "Max Drawdown",
    "calmar": "Calmar",
    "hit_rate": "Hit Rate",
    "total_return": "Total Return",
}
_AS_PCT = {"cagr", "ann_volatility", "max_drawdown", "hit_rate", "total_return"}


def print_summary(result: BacktestResult) -> None:
    stats = compute_metrics(result.returns).as_dict()
    title = f" Backtest: {result.config.name} "
    print(title.center(44, "="))
    for key, label in _LABELS.items():
        val = stats[key]
        shown = f"{val:>8.2%}" if key in _AS_PCT else f"{val:>8.2f}"
        print(f"  {label:<18}{shown}")
    print("=" * 44)


def save_html_report(result: BacktestResult, path: str | Path) -> Path:
    """Full quantstats tearsheet. Requires the 'engine' extra (quantstats)."""
    import quantstats as qs  # lazy heavy import

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    qs.reports.html(
        result.returns,
        title=f"AlphaForge {result.config.name}",
        output=str(path),
    )
    return path
