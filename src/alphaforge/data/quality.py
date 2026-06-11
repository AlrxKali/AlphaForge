"""Data quality: turn a raw price panel into a point-in-time-honest view.

Two jobs:
  * ``tradeable_mask``: A boolean (date x symbol) panel marking where a name
    actually has a usable price. A symbol that IPOs mid-range is NaN before its
    first printb one that delists is NaN after its last. The engine uses this to
    avoid selecting or holding a name when it cannot actually be traded.
  * ``validate_prices``: A report surfacing the things that quietly corrupt
    backtests: symbols with no data, partial coverage, non-positive prices, and
    implausible single-day jumps (often bad ticks or unadjusted splits).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


def tradeable_mask(prices: pd.DataFrame) -> pd.DataFrame:
    """True where the adjusted close is present and strictly positive."""
    close = prices["close"]
    return close.notna() & (close > 0)


@dataclass
class QualityReport:
    n_symbols: int
    start: pd.Timestamp | None
    end: pd.Timestamp | None
    coverage: dict[str, float]           # symbol -> fraction of dates with a price
    no_data: list[str]                   # symbols with zero usable prices
    partial: list[str]                   # symbols present for only part of the range
    non_positive: int                    # count of <=0 prices
    extreme_moves: int                   # count of |daily return| > threshold
    extreme_threshold: float = field(default=0.5)

    def render(self) -> str:
        lines = ["----------- Data Quality -----------"]
        rng = f"{self.start.date()} -> {self.end.date()}" if self.start is not None else "n/a"
        lines.append(f"  symbols: {self.n_symbols}   range: {rng}")
        if self.no_data:
            lines.append(f"  NO DATA ({len(self.no_data)}): {', '.join(self.no_data)}")
        if self.partial:
            shown = ", ".join(f"{s} {self.coverage[s]:.0%}" for s in self.partial)
            lines.append(f"  partial coverage ({len(self.partial)}): {shown}")
        if self.non_positive:
            lines.append(f"  WARNING: {self.non_positive} non-positive price(s)")
        if self.extreme_moves:
            lines.append(
                f"  WARNING: {self.extreme_moves} daily move(s) > "
                f"{self.extreme_threshold:.0%} (possible bad ticks / unadjusted splits)"
            )
        if not (self.no_data or self.partial or self.non_positive or self.extreme_moves):
            lines.append("  clean: full coverage, no anomalies detected")
        lines.append("------------------------------------")
        return "\n".join(lines)


def validate_prices(prices: pd.DataFrame, extreme_threshold: float = 0.5) -> QualityReport:
    close = prices["close"]
    usable = close.notna() & (close > 0)

    coverage = usable.mean().to_dict()  # per symbol, fraction of rows usable
    no_data = sorted(s for s, c in coverage.items() if c == 0)
    partial = sorted(s for s, c in coverage.items() if 0 < c < 1)

    non_positive = int((close <= 0).to_numpy().sum())
    rets = close.pct_change(fill_method=None)
    extreme = int((rets.abs() > extreme_threshold).to_numpy().sum())

    return QualityReport(
        n_symbols=close.shape[1],
        start=close.index.min() if len(close.index) else None,
        end=close.index.max() if len(close.index) else None,
        coverage={k: float(v) for k, v in coverage.items()},
        no_data=no_data,
        partial=partial,
        non_positive=non_positive,
        extreme_moves=extreme,
        extreme_threshold=extreme_threshold,
    )
