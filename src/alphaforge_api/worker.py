"""arq worker: claim a job, run the analytics core, persist structured results.

Run with:  arq alphaforge_api.worker.WorkerSettings

The worker imports the same ``alphaforge`` core the CLI uses and is the single
place heavy backtests execute, off the request path. It produces DATA, not
presentation: a compact summary lands in the row's ``metrics`` (for listing and
sorting) and the full time series (equity / returns / drawdown, plus per-window
rows for walk-forward) is stored as a JSON artifact for the frontend to render.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd
from arq.connections import RedisSettings

from alphaforge.config import BacktestConfig
from alphaforge.metrics.performance import compute_metrics
from alphaforge.runner import run as run_single_backtest
from alphaforge.validation import walk_forward
from alphaforge_api.db import service_client
from alphaforge_api.settings import get_settings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _series(equity: pd.Series, returns: pd.Series) -> dict:
    """Aligned time series for charting: dates + equity + returns + drawdown."""
    drawdown = equity / equity.cummax() - 1.0
    returns = returns.reindex(equity.index).fillna(0.0)
    return {
        "dates": [d.strftime("%Y-%m-%d") for d in equity.index],
        "equity": [round(float(x), 4) for x in equity.to_numpy()],
        "returns": [float(x) for x in returns.to_numpy()],
        "drawdown": [float(x) for x in drawdown.to_numpy()],
    }


def payload_single(result) -> tuple[dict, dict]:
    metrics = compute_metrics(result.returns).as_dict()
    payload = {
        "kind": "single",
        "summary": metrics,
        "series": _series(result.equity_curve, result.returns),
    }
    return metrics, payload


def payload_walk_forward(wf) -> tuple[dict, dict]:
    metrics = wf.metrics().as_dict()
    metrics["benchmark_sharpe"] = wf.benchmark_sharpe
    metrics["n_windows"] = len(wf.windows)
    windows = [
        {
            "test_start": str(w.window.test_start),
            "test_end": str(w.window.test_end),
            "params": w.params,
            "train_sharpe": w.train_sharpe,
            "test_sharpe": w.test_sharpe,
            "test_return": w.test_return,
        }
        for w in wf.windows
    ]
    payload = {
        "kind": "walk_forward",
        "summary": metrics,
        "series": _series(wf.oos_equity, wf.oos_returns),
        "windows": windows,
    }
    return metrics, payload


def _upload_json(sb, user_id: str, backtest_id: str, payload: dict) -> str:
    s = get_settings()
    path = f"{user_id}/{backtest_id}.json"
    data = json.dumps(payload).encode("utf-8")
    sb.storage.from_(s.reports_bucket).upload(
        path, data, {"content-type": "application/json", "upsert": "true"}
    )
    return path


async def run_backtest_job(ctx, backtest_id: str) -> None:
    sb = service_client()
    rows = sb.table("backtests").select("*").eq("id", backtest_id).execute().data
    if not rows:
        return
    row = rows[0]

    sb.table("backtests").update({"status": "running", "started_at": _now()}).eq(
        "id", backtest_id
    ).execute()
    try:
        cfg = BacktestConfig.model_validate(row["config"])
        opts = row.get("options") or {}
        if row.get("kind") == "walk_forward":
            wf = walk_forward(
                cfg,
                train_months=opts.get("train_months", 36),
                test_months=opts.get("test_months", 12),
                step_months=opts.get("step_months"),
                anchored=opts.get("anchored", False),
                grid=opts.get("grid"),
            )
            metrics, payload = payload_walk_forward(wf)
        else:
            metrics, payload = payload_single(run_single_backtest(cfg))

        artifact_path = _upload_json(sb, row["user_id"], backtest_id, payload)
        sb.table("backtests").update(
            {
                "status": "succeeded",
                "metrics": metrics,
                "artifact_path": artifact_path,
                "finished_at": _now(),
            }
        ).eq("id", backtest_id).execute()
    except Exception as exc:
        sb.table("backtests").update(
            {"status": "failed", "error": str(exc), "finished_at": _now()}
        ).eq("id", backtest_id).execute()
        raise


class WorkerSettings:
    functions = [run_backtest_job]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
