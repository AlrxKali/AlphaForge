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
| `fundamentals/` | `FundamentalProvider` interface, point-in-time financials (SEC EDGAR, filing-date stamped) |
| `factors/` | `Factor` base class + a registry of signals (momentum, low-vol, reversal, value, composite) |
| `engine/` | Top-N portfolio construction + vectorbt fill/PnL simulation |
| `metrics/` | Sharpe, Sortino, drawdown, Calmar, etc. (computed directly) |
| `validation/` | Walk-forward: window generation + per-window param optimization + stitched OOS evaluation |
| `reporting/` | Config/provenance header + data-quality + performance text report; quantstats HTML tearsheet |
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

## Factors

All factors return scores where **higher = more attractive**, and are
**trailing-only** (no lookahead). Combine them with `composite`, which
z-scores each component cross-sectionally before the weighted sum.

| name | signal | key params |
|------|--------|------------|
| `momentum` | 12-1 total return (trailing winners) | `lookback`, `skip` |
| `volatility` | low realized vol (negated) | `lookback` |
| `mean_reversion` | short-term reversal (recent losers) | `lookback` |
| `value` | book-to-market from point-in-time SEC EDGAR filings | `provider`, `metric` |
| `composite` | z-scored weighted blend of the above | `components` |

```bash
# Long-momentum + short-reversal + low-vol blend
alphaforge run --symbols AAPL,MSFT,NVDA,AMZN,META,JPM,XOM,UNH,JNJ,GOOG \
  --start 2019-01-01 --end 2024-12-31 --top-n 3 \
  --factor composite --factor-params '{"components":[
     {"name":"momentum","weight":1.0,"params":{"lookback":252,"skip":21}},
     {"name":"mean_reversion","weight":0.5,"params":{"lookback":21}},
     {"name":"volatility","weight":0.5,"params":{"lookback":63}}]}'
```

## Walk-forward validation

`--walk-forward` optimizes factor params on each rolling in-sample (train)
window, evaluates them on the next out-of-sample (test) window, and stitches the
test slices into one honest OOS curve. The report shows the per-window choices
plus the in-sample vs out-of-sample Sharpe gap (the overfitting tell).

```bash
alphaforge run --symbols AAPL,MSFT,NVDA,AMZN,GOOG,JPM,XOM,JNJ \
  --start 2014-01-01 --end 2024-12-31 --factor momentum --top-n 3 \
  --walk-forward --train-months 36 --test-months 12 \
  --grid '{"lookback":[126,252],"skip":[21,63]}'
```

With no `--grid` it becomes a rolling fixed-parameter OOS evaluation. Use
`--anchored` for an expanding (instead of rolling) train window. Each candidate
is backtested once over the full period and sliced per window, so cost is
O(grid), not O(grid x windows).

## API (service layer)

The `alphaforge_api` package (install with `pip install -e ".[api]"`) is a thin
FastAPI app plus an arq worker over the analytics core. The API persists jobs to
Supabase and enqueues them; the worker runs the core off the request path and
writes results back. The core never imports anything web. The arrow only points
api -> core, so analytics contributors never touch this layer.

```
UI ──HTTP──> FastAPI ──enqueue──> Redis (arq) ──> Worker ──imports──> alphaforge core
                 │                                    │
                 └──────────> Supabase <─────────────-┘   (Postgres + Auth + Storage)
```

Database schema and migrations live in a separate repo (`MarketDNA_DB`), so the
database can evolve without touching this project.

Local bring-up:

```bash
docker compose up -d redis
uvicorn alphaforge_api.main:app --reload
arq alphaforge_api.worker.WorkerSettings
```

The backend serves **data, not presentation**: the worker stores a compact
summary in the row (for listing/sorting) and the full time series (equity,
returns, drawdown, and per-window rows for walk-forward) as a JSON artifact. A
separate frontend repo renders the charts.

Endpoints: `POST /backtests` (enqueue, returns 202 + id), `GET /backtests`,
`GET /backtests/{id}` (poll status + summary metrics), `GET /backtests/{id}/series`
(structured results JSON for charting), `DELETE /backtests/{id}`,
`POST /universes` (upload a membership CSV), `GET /universes`,
`DELETE /universes/{id}`, `GET /healthz`. Auth is the Supabase JWT in the
Authorization header, row-level security scopes every user to their own rows.

To run a survivorship-correct backtest through the API, upload a membership CSV
with `POST /universes`, then set
`config.data.universe = {"kind": "point_in_time", "membership_file": "<universe-id>"}`
in the backtest body; the worker resolves that id to the stored CSV.

## Status & roadmap

- [x] **Phase 1: vertical slice**: yfinance → cache → momentum → vectorbt → metrics → report
- [x] **Phase 2: data depth**: `Universe` interface (static + point-in-time), tradeability masking, data-quality report
- [x] **Phase 3: factor framework**: momentum, low-volatility, mean-reversion, **value** (point-in-time SEC EDGAR book-to-market) + z-scored `composite` blending
- [x] **Phase 4: walk-forward orchestration**: per-window param optimization, stitched OOS curve, in-sample vs OOS Sharpe gap
- [x] **Phase 5: FastAPI layer**: FastAPI + arq worker + Supabase (auth via JWKS, row-level security, storage). Backtests, walk-forward, and universe upload all verified end-to-end live; results served as structured JSON.

## Tests

```bash
pytest        # correctness-critical logic. Runs without the engine extra
```
