"""Configuration models.

A backtest is fully described by a serializable config object. The *same*
config flows through the CLI, a notebook, or the API request, which
makes runs reproducible and trivially shareable. No logic lives here. These
are validated data containers (Pydantic v2).
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class Rebalance(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class CostConfig(BaseModel):
    """Transaction costs. Required, with no silent zero."""

    commission_bps: float = Field(
        default=5.0, ge=0, description="Per-trade commission in basis points of notional."
    )
    slippage_bps: float = Field(
        default=5.0, ge=0, description="Assumed slippage in basis points per fill."
    )


class UniverseConfig(BaseModel):
    """How to resolve the investable set. ``kind`` names a registered Universe.

    static        -> a fixed list (``symbols``); reproduces hand-picked baskets.
    point_in_time -> a membership table (``membership_file``) with per-symbol
                     start/end dates; this is the survivorship-bias-free path.
    """

    kind: str = "static"
    symbols: list[str] | None = None
    membership_file: str | None = None
    params: dict = Field(default_factory=dict)


class DataConfig(BaseModel):
    provider: str = Field(default="yfinance", description="Registered DataProvider name.")
    # `symbols` is the convenient shorthand for a static universe
    # `universe` is the general form. Exactly one must be supplied.
    symbols: list[str] | None = Field(default=None, description="Shorthand static universe.")
    universe: UniverseConfig | None = None
    start: date
    end: date

    @model_validator(mode="after")
    def _check(self) -> "DataConfig":
        if self.end <= self.start:
            raise ValueError("end must be after start")
        if self.symbols is None and self.universe is None:
            raise ValueError("provide either `symbols` or `universe`")
        if self.symbols is not None and len(self.symbols) == 0:
            raise ValueError("`symbols` must be non-empty")
        return self

    def resolved_universe(self) -> UniverseConfig:
        """Normalize to a UniverseConfig (wrapping bare `symbols` as static)."""
        if self.universe is not None:
            return self.universe
        return UniverseConfig(kind="static", symbols=self.symbols)


class FactorConfig(BaseModel):
    name: str = Field(..., description="Registered factor name, e.g. 'momentum'.")
    params: dict = Field(default_factory=dict, description="Factor-specific parameters.")


class BacktestConfig(BaseModel):
    """Top-level, fully reproducible description of a backtest run."""

    data: DataConfig
    factor: FactorConfig
    costs: CostConfig = Field(default_factory=CostConfig)
    rebalance: Rebalance = Rebalance.MONTHLY
    top_n: int = Field(default=10, ge=1, description="Long the top-N ranked names.")
    initial_cash: float = Field(default=100_000.0, gt=0)
    name: str = Field(default="untitled", description="Human label for the run / report.")
