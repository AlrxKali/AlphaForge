"""AlphaForge is a modular alpha research & backtesting platform.

The package is organized as a library-first monolith. All logic lives in the
core modules below; the CLI / future API are thin adapters over them.

Pipeline:  data -> factors -> engine -> metrics -> validation -> reporting
"""

__version__ = "0.1.0"
