"""Walk-forward window generation (the splitting half of validation).

This is the scaffold for rolling out-of-sample evaluation: carve the timeline
into (train, test) windows that never overlap and always move forward in time,
so a strategy is only ever scored on data it could not have fit to.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd


@dataclass(frozen=True)
class WalkForwardWindow:
    train_start: date
    train_end: date
    test_start: date
    test_end: date

    def __post_init__(self) -> None:
        # Hard guarantee: test begins strictly after train ends. No leakage.
        if self.test_start <= self.train_end:
            raise ValueError("test_start must be after train_end (no leakage)")


def generate_windows(
    start: date,
    end: date,
    train_months: int = 36,
    test_months: int = 12,
    step_months: int | None = None,
    anchored: bool = False,
) -> list[WalkForwardWindow]:
    """Produce rolling (or anchored) walk-forward windows.

    anchored=False -> rolling: train window slides forward (constant length).
    anchored=True  -> expanding: train_start is pinned, train window grows.
    step_months defaults to test_months (non-overlapping test periods).
    """
    step = step_months or test_months
    windows: list[WalkForwardWindow] = []

    origin = pd.Timestamp(start)
    train_from = origin
    while True:
        train_to = train_from + pd.DateOffset(months=train_months)
        test_from = train_to  # test starts the day after train ends in practice
        test_to = test_from + pd.DateOffset(months=test_months)
        if test_to > pd.Timestamp(end):
            break

        windows.append(
            WalkForwardWindow(
                train_start=(origin if anchored else train_from).date(),
                train_end=(train_to - pd.Timedelta(days=1)).date(),
                test_start=test_from.date(),
                test_end=(test_to - pd.Timedelta(days=1)).date(),
            )
        )
        train_from = train_from + pd.DateOffset(months=step)

    return windows
