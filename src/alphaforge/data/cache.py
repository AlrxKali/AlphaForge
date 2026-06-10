"""On-disk parquet cache for price data.

Re-downloading the same history every run is the biggest avoidable slowdown in
a research loop. We cache per (provider, symbol) as parquet and slice in
memory. Keyed coarsely on purpose: we fetch a generous range once and serve
sub-ranges from disk.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

DEFAULT_CACHE_DIR = Path.home() / ".alphaforge" / "cache"


class PriceCache:
    def __init__(self, cache_dir: Path | str = DEFAULT_CACHE_DIR) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, provider: str, symbol: str) -> Path:
        # Hash the symbol so exotic tickers can't break the filesystem.
        key = hashlib.sha1(symbol.encode()).hexdigest()[:12]
        return self.cache_dir / f"{provider}__{symbol.replace('/', '_')}__{key}.parquet"

    def load(self, provider: str, symbol: str) -> pd.DataFrame | None:
        path = self._path(provider, symbol)
        if path.exists():
            return pd.read_parquet(path)
        return None

    def save(self, provider: str, symbol: str, df: pd.DataFrame) -> None:
        # Write to a temp sibling then atomically replace, so a crash mid-write
        # can never leave a half-written parquet in the cache.
        path = self._path(provider, symbol)
        tmp = path.with_suffix(".parquet.tmp")
        df.to_parquet(tmp)
        tmp.replace(path)
