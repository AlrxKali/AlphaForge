"""Liveness endpoint (no auth)."""

from __future__ import annotations

from fastapi import APIRouter

from alphaforge import __version__

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "core_version": __version__}
