"""Thin CLI adapter. No logic, parse args, build a config, call the runner,
hand the result to reporting.

    alphaforge run --symbols AAPL,MSFT,GOOG,AMZN,META,NVDA --start 2018-01-01 \
        --end 2024-12-31 --factor momentum --top-n 3 --html report.html
"""
from __future__ import annotations
from datetime import date


from alphaforge.config import (
    BacktestConfig,
    CostConfig,
    DataConfig,
    FactorConfig,
    Rebalance,
    UniverseConfig,
)

import typer
import json
from alphaforge.reporting import print_summary, save_html_report
from alphaforge.runner import run as run_backtest

app = typer.Typer(add_completion=False, help="AlphaForge alpha research platform.")


@app.command()
def run(
    symbols: str = typer.Option("", help="Comma-separated tickers (static universe)."),
    universe_file: str = typer.Option(
        "", help="Point-in-time membership CSV (symbol,start,end). Overrides --symbols."
    ),
    start: str = typer.Option(..., help="Start date YYYY-MM-DD."),
    end: str = typer.Option(..., help="End date YYYY-MM-DD."),
    factor: str = typer.Option("momentum", help="Factor name."),
    factor_params: str = typer.Option(
        "", help='JSON factor params, e.g. \'{"lookback": 126}\' or a composite spec.'
    ),
    top_n: int = typer.Option(10, help="Hold the top-N ranked names."),
    rebalance: Rebalance = typer.Option(Rebalance.MONTHLY, help="Rebalance cadence."),
    commission_bps: float = typer.Option(5.0, help="Commission, bps of notional."),
    slippage_bps: float = typer.Option(5.0, help="Slippage, bps per fill."),
    cash: float = typer.Option(100_000.0, help="Initial cash."),
    name: str = typer.Option("untitled", help="Run / report label."),
    html: str = typer.Option("", help="If set, write a quantstats HTML tearsheet here."),
) -> None:
    """Run a single backtest end-to-end and print a performance summary."""
    # Imports deferred so `--help` and arg parsing never pay the heavy import cost.

    params = json.loads(factor_params) if factor_params else {}

    # Resolve the universe: a point-in-time membership file takes precedence.
    if universe_file:
        data = DataConfig(
            universe=UniverseConfig(kind="point_in_time", membership_file=universe_file),
            start=date.fromisoformat(start),
            end=date.fromisoformat(end),
        )
    elif symbols:
        data = DataConfig(
            symbols=[s.strip().upper() for s in symbols.split(",") if s.strip()],
            start=date.fromisoformat(start),
            end=date.fromisoformat(end),
        )
    else:
        raise typer.BadParameter("provide either --symbols or --universe-file")

    cfg = BacktestConfig(
        data=data,
        factor=FactorConfig(name=factor, params=params),
        costs=CostConfig(commission_bps=commission_bps, slippage_bps=slippage_bps),
        rebalance=rebalance,
        top_n=top_n,
        initial_cash=cash,
        name=name,
    )

    result = run_backtest(cfg)
    print_summary(result)  # full report: header + data quality + performance

    if html:
        try:
            out = save_html_report(result, html)
            typer.echo(f"\nTearsheet written to {out}")
        except ModuleNotFoundError:
            typer.secho(
                "\nSkipped HTML tearsheet: quantstats is not installed. "
                'Install the reporting stack with:  pip install -e ".[engine]"',
                fg=typer.colors.YELLOW,
            )


if __name__ == "__main__":
    app()
