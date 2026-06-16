"""Request / response models for the API.

The request body embeds the core ``BacktestConfig`` verbatim, so the API contract
is the same reproducible config the CLI and notebooks use. Walk-forward options
are carried alongside it.

To run against an uploaded point-in-time universe, set
``config.data.universe = {"kind": "point_in_time", "membership_file": "<universe-id>"}``.
In the API the ``membership_file`` is the id returned by POST /universes (not a
local path); the worker resolves it to the stored CSV before running.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from alphaforge.config import BacktestConfig


class WalkForwardOptions(BaseModel):
    enabled: bool = False
    train_months: int = 36
    test_months: int = 12
    step_months: int | None = None
    anchored: bool = False
    grid: dict | None = None


class BacktestCreate(BaseModel):
    config: BacktestConfig
    walk_forward: WalkForwardOptions = Field(default_factory=WalkForwardOptions)


class BacktestOut(BaseModel):
    id: str
    name: str
    kind: str
    status: str
    metrics: dict | None = None
    error: str | None = None
    artifact_path: str | None = None
    created_at: str | None = None
    finished_at: str | None = None

    @classmethod
    def from_row(cls, row: dict) -> "BacktestOut":
        return cls(
            id=str(row["id"]),
            name=row.get("name", "untitled"),
            kind=row.get("kind", "single"),
            status=row.get("status", "queued"),
            metrics=row.get("metrics"),
            error=row.get("error"),
            artifact_path=row.get("artifact_path"),
            created_at=row.get("created_at"),
            finished_at=row.get("finished_at"),
        )


class UniverseOut(BaseModel):
    id: str
    name: str
    n_symbols: int | None = None
    created_at: str | None = None

    @classmethod
    def from_row(cls, row: dict) -> "UniverseOut":
        return cls(
            id=str(row["id"]),
            name=row.get("name", ""),
            n_symbols=row.get("n_symbols"),
            created_at=row.get("created_at"),
        )
