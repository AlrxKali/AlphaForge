"""Universe endpoints: upload and manage point-in-time membership CSVs.

An uploaded CSV is validated (it must load as a PointInTimeUniverse), stored in
the `universes` bucket, and recorded in the `universes` table. Reference it from
a backtest by setting ``config.data.universe.membership_file`` to the returned
universe id. The worker resolves that id to the stored CSV before running.
"""

from __future__ import annotations

import os
import tempfile
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from alphaforge.universe.point_in_time import PointInTimeUniverse
from alphaforge_api.auth import AuthUser, get_current_user
from alphaforge_api.db import service_client
from alphaforge_api.deps import get_user_db
from alphaforge_api.schemas import UniverseOut
from alphaforge_api.settings import get_settings

router = APIRouter(prefix="/universes", tags=["universes"])


def _validate_membership(content: bytes) -> int:
    """Load the CSV as a PointInTimeUniverse to validate it; return symbol count."""
    tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
    try:
        tmp.write(content)
        tmp.close()
        universe = PointInTimeUniverse(membership_file=tmp.name)
        return len(universe._intervals)
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid membership CSV: {exc}") from exc
    finally:
        os.unlink(tmp.name)


@router.post("", response_model=UniverseOut, status_code=status.HTTP_201_CREATED)
def upload_universe(
    name: str = Form(...),
    file: UploadFile = File(...),
    user: AuthUser = Depends(get_current_user),
    db=Depends(get_user_db),
) -> UniverseOut:
    content = file.file.read()
    n_symbols = _validate_membership(content)

    s = get_settings()
    storage_path = f"{user.id}/{uuid.uuid4()}.csv"
    service_client().storage.from_(s.universes_bucket).upload(
        storage_path, content, {"content-type": "text/csv", "upsert": "true"}
    )

    row = {"user_id": user.id, "name": name, "storage_path": storage_path, "n_symbols": n_symbols}
    inserted = db.table("universes").insert(row).execute().data
    if not inserted:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to create universe")
    return UniverseOut.from_row(inserted[0])


@router.get("", response_model=list[UniverseOut])
def list_universes(
    user: AuthUser = Depends(get_current_user),
    db=Depends(get_user_db),
) -> list[UniverseOut]:
    rows = db.table("universes").select("*").order("created_at", desc=True).execute().data
    return [UniverseOut.from_row(r) for r in rows]


@router.delete("/{universe_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_universe(
    universe_id: str,
    user: AuthUser = Depends(get_current_user),
    db=Depends(get_user_db),
) -> None:
    rows = db.table("universes").select("storage_path").eq("id", universe_id).execute().data
    db.table("universes").delete().eq("id", universe_id).execute()
    if rows and rows[0].get("storage_path"):
        try:
            service_client().storage.from_(get_settings().universes_bucket).remove(
                [rows[0]["storage_path"]]
            )
        except Exception:
            pass
