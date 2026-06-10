"""Validation layer: walk-forward / out-of-sample evaluation."""

from alphaforge.validation.walkforward import WalkForwardWindow, generate_windows

__all__ = ["WalkForwardWindow", "generate_windows"]
