"""Factor layer: turn price data into a cross-sectional signal to rank on."""

from alphaforge.factors.base import Factor, get_factor, register_factor

# Import concrete factors so their @register_factor decorators run.
from alphaforge.factors import momentum 

__all__ = ["Factor", "get_factor", "register_factor"]
