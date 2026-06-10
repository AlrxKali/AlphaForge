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


class DataConfig(BaseModel):
    provider: str = Field(default="yfinance", description="Registered DataProvider name.")
    symbols: list[str] = Field(..., min_length=1, description="Universe of tickers.")
    start: date
    end: date

    @model_validator(mode="after")
    def _check_dates(self) -> "DataConfig":
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self


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
