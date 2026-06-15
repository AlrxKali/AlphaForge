"""Backtest job endpoints.

POST enqueues a job (validate -> persist `queued` row -> enqueue arq job ->
return immediately). The worker does the heavy lifting and updates the row. The
client polls GET until a terminal status.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from alphaforge_api.auth import AuthUser, get_current_user
from alphaforge_api.db import service_client
from alphaforge_api.deps import get_queue, get_user_db
from alphaforge_api.schemas import BacktestCreate, BacktestOut
from alphaforge_api.settings import get_settings

router = APIRouter(prefix="/backtests", tags=["backtests"])


@router.post("", response_model=BacktestOut, status_code=status.HTTP_202_ACCEPTED)
async def create_backtest(
    body: BacktestCreate,
    user: AuthUser = Depends(get_current_user),
    db=Depends(get_user_db),
    queue=Depends(get_queue),
) -> BacktestOut:
    row = {
        "user_id": user.id,
        "name": body.config.name,
        "kind": "walk_forward" if body.walk_forward.enabled else "single",
        "config": body.config.model_dump(mode="json"),
        "options": body.walk_forward.model_dump(),
        "status": "queued",
    }
    inserted = db.table("backtests").insert(row).execute().data
    if not inserted:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to create backtest")
    created = inserted[0]
    await queue.enqueue_job("run_backtest_job", str(created["id"]))
    return BacktestOut.from_row(created)


@router.get("", response_model=list[BacktestOut])
def list_backtests(
    limit: int = 50,
    user: AuthUser = Depends(get_current_user),
    db=Depends(get_user_db),
) -> list[BacktestOut]:
    rows = (
        db.table("backtests")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data
    )
    return [BacktestOut.from_row(r) for r in rows]


@router.get("/{backtest_id}", response_model=BacktestOut)
def get_backtest(
    backtest_id: str,
    user: AuthUser = Depends(get_current_user),
    db=Depends(get_user_db),
) -> BacktestOut:
    rows = db.table("backtests").select("*").eq("id", backtest_id).execute().data
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Backtest not found")
    return BacktestOut.from_row(rows[0])


@router.get("/{backtest_id}/series")
def get_series(
    backtest_id: str,
    user: AuthUser = Depends(get_current_user),
    db=Depends(get_user_db),
) -> JSONResponse:
    """Return the structured results document (summary + equity/returns/drawdown
    series, plus per-window rows for walk-forward) for the frontend to render."""
    rows = (
        db.table("backtests")
        .select("artifact_path,status")
        .eq("id", backtest_id)
        .execute()
        .data
    )
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Backtest not found")
    path = rows[0].get("artifact_path")
    if rows[0].get("status") != "succeeded" or not path:
        raise HTTPException(status.HTTP_409_CONFLICT, "Results not ready")

    # Ownership is already enforced by RLS on the row read above; the service
    # client just fetches the artifact bytes from storage.
    data = service_client().storage.from_(get_settings().reports_bucket).download(path)
    return JSONResponse(content=json.loads(data))


@router.delete("/{backtest_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_backtest(
    backtest_id: str,
    user: AuthUser = Depends(get_current_user),
    db=Depends(get_user_db),
) -> None:
    # Read the artifact path (RLS confirms ownership), delete the row, then
    # remove the stored artifact so it is not left orphaned.
    rows = db.table("backtests").select("artifact_path").eq("id", backtest_id).execute().data
    db.table("backtests").delete().eq("id", backtest_id).execute()
    if rows and rows[0].get("artifact_path"):
        try:
            service_client().storage.from_(get_settings().reports_bucket).remove(
                [rows[0]["artifact_path"]]
            )
        except Exception:
            pass  # best-effort cleanup; the row is already gone
