"""yfinance-backed DataProvider. The free, prototype-grade source.

yfinance data has *survivorship bias* (delisted tickers are gone) and
occasional adjustment quirks. It is fine for development and for liquid names
that still trade, but is NOT trustworthy for broad universe backtests. The
``DataProvider`` interface exists precisely so this can be swapped later.

We will improve and find a different provider in the future.
"""

from __future__ import annotations

import warnings
from datetime import date

import pandas as pd

from alphaforge.data.cache import PriceCache
from alphaforge.data.provider import DataProvider, register_provider

_FIELDS = ["open", "high", "low", "close", "volume"]


@register_provider
class YFinanceProvider(DataProvider):
    name = "yfinance"

    def __init__(self, cache: PriceCache | None = None) -> None:
        self.cache = cache or PriceCache()

    def get_prices(self, symbols: list[str], start: date, end: date) -> pd.DataFrame:
        # Download each name: a symbol with no data (For example, delisted) yields an
        # empty frame and is simply omitted from the concat. It never allowed to
        # corrupt the panel's DatetimeIndex.
        frames = {sym: self._get_one(sym, start, end) for sym in symbols}
        frames = {sym: df for sym, df in frames.items() if not df.empty}

        all_cols = pd.MultiIndex.from_product([_FIELDS, symbols], names=["field", "symbol"])
        if not frames:
            idx = pd.DatetimeIndex([], name="date")
            return pd.DataFrame(index=idx, columns=all_cols, dtype="float64")

        out = pd.concat(frames, axis=1)            # columns: (symbol, field)
        out.columns = out.columns.swaplevel(0, 1)  # -> (field, symbol)
        out = out.sort_index(axis=0).sort_index(axis=1)

        # Reindex so EVERY requested symbol keeps columns (missing -> all-NaN).
        # Dropping them would hide no-data names, instead the quality layer flags
        # them and the tradeability mask excludes them.
        out = out.reindex(columns=all_cols)
        return out.loc[str(start) : str(end)]

    def _get_one(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        cached = self.cache.load(self.name, symbol)
        if cached is not None and self._covers(cached, start, end):
            return cached.loc[str(start) : str(end)]

        df = self._download(symbol, start, end)
        if df.empty:
            # No data (For example, fully delisted). Don't cache emptiness: A transient
            # fetch failure shouldn't permanently mark a name as dead.
            return df
        if cached is not None and not cached.empty:
            df = pd.concat([cached, df]).sort_index()
            df = df[~df.index.duplicated(keep="last")]
        self.cache.save(self.name, symbol, df)
        return df.loc[str(start) : str(end)]

    @staticmethod
    def _covers(df: pd.DataFrame, start: date, end: date) -> bool:
        if df.empty:
            return False
        return df.index.min() <= pd.Timestamp(start) and df.index.max() >= pd.Timestamp(end)

    @staticmethod
    def _download(symbol: str, start: date, end: date) -> pd.DataFrame:
        import yfinance as yf  # lazy: keep import cost out of package import

        raw = yf.download(
            symbol,
            start=str(start),
            end=str(end),
            auto_adjust=True,  # adjusted close for correct returns
            progress=False,
        )
        if raw is None or raw.empty:
            warnings.warn(f"No data returned for {symbol}", stacklevel=2)
            return pd.DataFrame(columns=_FIELDS, index=pd.DatetimeIndex([], name="date"))

        # yfinance returns a (Price, Ticker) column MultiIndex for single tickers
        # under recent versions. Normalize to lowercase single-level fields.
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        raw.columns = [str(c).lower() for c in raw.columns]
        raw = raw[[c for c in _FIELDS if c in raw.columns]]
        raw.index = pd.to_datetime(raw.index).tz_localize(None)
        raw.index.name = "date"
        return raw
