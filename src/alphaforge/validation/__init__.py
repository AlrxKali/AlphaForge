"""Validation layer: walk-forward / out-of-sample evaluation."""

from alphaforge.validation.orchestrator import (
    WalkForwardResult,
    WindowResult,
    param_grid,
    walk_forward,
    walk_forward_from_returns,
)
from alphaforge.validation.walkforward import WalkForwardWindow, generate_windows

__all__ = [
    "WalkForwardWindow",
    "generate_windows",
    "WalkForwardResult",
    "WindowResult",
    "walk_forward",
    "walk_forward_from_returns",
    "param_grid",
]
