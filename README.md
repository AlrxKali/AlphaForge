# AlphaForge

A modular alpha research & backtesting platform for US equities. Library-first:
all logic lives in an importable core; the CLI (and a future API / web UI) are
thin adapters over it.

```
data → factors → engine → metrics → validation → reporting
```

## Architecture

A backtest is a tight computational loop over time-series data, so a network boundary 
between stages would buynothing and cost latency. The clean module seams below mean 
any single piece can be peeled out later if it ever genuinely needs independent scaling.

| Module | Responsibility |
|--------|----------------|
| `data/` | Download, cache (parquet), serve prices behind a `DataProvider` interface; data-quality checks |
| `universe/` | `Universe` interface, *which* symbols are investable *when* (static or point-in-time membership) |
| `factors/` | `Factor` base class + a registry of signals (momentum to start) |
| `engine/` | Top-N portfolio construction + vectorbt fill/PnL simulation |
| `metrics/` | Sharpe, Sortino, drawdown, Calmar, etc. (computed directly) |
| `validation/` | Walk-forward / out-of-sample window generation |
| `reporting/` | Plain-text summary + quantstats HTML tearsheet |
| `runner.py` | The single seam wiring the pipeline; CLI/API/notebook all call it |

### Correctness guardrails (baked in, not bolted on)

- **Lookahead bias**: factors are trailing-only; the engine shifts signals one
  bar before trading (`build_target_weights`).
- **Survivorship bias**: yfinance has it; the `DataProvider` interface exists so
  a delisting-inclusive source (Polygon / Tiingo / Norgate) is a one-class swap.
- **No cost-free fantasy**: commission + slippage are first-class config, never
  silently zero.
- **No train/test leakage**: walk-forward windows guarantee `test_start > train_end`.

## Install

```bash
pip install -e .            # core: data, factors, metrics, validation
pip install -e ".[engine]"  # adds vectorbt + quantstats (the execution core)
pip install -e ".[dev]"     # pytest + ruff
```

> ⚠️ **Python version note.** `vectorbt` depends on `numba`/`llvmlite`, which
> often lag new CPython releases by months. If `pip install ".[engine]"` fails on
> Python 3.14, use a **3.11 or 3.12** virtual environment for now. The core
> package (and the full test suite) runs fine without the engine extra.

## Usage

```bash
alphaforge run \
  --symbols AAPL,MSFT,GOOG,AMZN,META,NVDA,TSLA,JPM,XOM,UNH \
  --start 2018-01-01 --end 2024-12-31 \
  --factor momentum --top-n 3 --rebalance monthly \
  --html report.html
```

**Survivorship-free runs** use a point-in-time membership table instead of a
fixed list, each symbol carries the dates it was actually a member (blank `end`
= still active), and the engine never selects or holds a name outside its window:

```bash
alphaforge run \
  --universe-file examples/membership_sample.csv \
  --start 2021-01-01 --end 2023-06-01 \
  --factor momentum --top-n 3
```

Each run prints a **data-quality report** first (no-data names, partial coverage,
non-positive prices, implausible jumps) so you see what you're trusting.

You don't hand-write the membership table, generate a real, survivorship-correct
S&P 500 one (sourced from [`fja05680/sp500`](https://github.com/fja05680/sp500)):

```bash
python scripts/build_membership.py --start 2019-01-01 --end 2023-12-31 \
    --out examples/membership_sp500_2019_2023.csv
```

It emits one row per membership spell (`symbol,start,end`, blank `end` = still a
member), handles re-additions, and converts dotted tickers (BRK.B → BRK-B) for
yfinance.

Or from Python / a notebook:

```python
from datetime import date
from alphaforge.config import BacktestConfig, DataConfig, FactorConfig
from alphaforge.runner import run
from alphaforge.reporting import print_summary

cfg = BacktestConfig(
    data=DataConfig(symbols=["AAPL", "MSFT", "NVDA"], start=date(2019,1,1), end=date(2024,1,1)),
    factor=FactorConfig(name="momentum", params={"lookback": 252, "skip": 21}),
    top_n=2,
)
print_summary(run(cfg))
```

## Status & roadmap

- [x] **Phase 1: vertical slice**: yfinance → cache → momentum → vectorbt → metrics → report
- [x] **Phase 2: data depth**: `Universe` interface (static + point-in-time), tradeability masking, data-quality report
- [ ] **Phase 3: factor framework**: value, volatility, mean-reversion, factor combination
- [ ] **Phase 4: walk-forward orchestration**: re-run engine per window, OOS reporting
- [ ] **Phase 5: FastAPI layer**: expose the core for a web frontend

## Tests

```bash
pytest        # correctness-critical logic; runs without the engine extra
```
