"""Universe layer: which symbols are investable, and when (survivorship fix)."""

from __future__ import annotations

from alphaforge.universe.base import Universe, get_universe, register_universe

# Import concrete universes so their @register_universe decorators run.
from alphaforge.universe import point_in_time, static


def from_config(cfg) -> Universe:
    """Build a Universe from a UniverseConfig (duck-typed to avoid an import
    cycle with the config module)."""
    if cfg.kind == "static":
        return get_universe("static", symbols=cfg.symbols)
    if cfg.kind == "point_in_time":
        return get_universe("point_in_time", membership_file=cfg.membership_file, **cfg.params)
    return get_universe(cfg.kind, **cfg.params)


__all__ = ["Universe", "get_universe", "register_universe", "from_config"]
