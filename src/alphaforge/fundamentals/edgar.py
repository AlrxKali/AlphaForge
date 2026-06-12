"""SEC EDGAR fundamentals: free, authoritative, and truly point-in-time.

EDGAR's XBRL ``companyconcept`` API returns each reported fact with the date it
was ``filed``, and the moment it became public. We index facts by that filing date
and forward-fill onto the daily grid, so a value can never be seen before it was
actually disclosed. No API key is required; SEC asks only for a descriptive
User-Agent and reasonable request rates (we cache aggressively to disk).

Logical fields map to specific XBRL concepts; extend ``FIELD_CONCEPTS`` to add
more (net income, revenue, assets, ...).
"""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

import pandas as pd

from alphaforge.fundamentals.base import FundamentalProvider, register_fundamental_provider

# logical field -> (taxonomy, XBRL concept, unit)
FIELD_CONCEPTS: dict[str, tuple[str, str, str]] = {
    "book_equity": ("us-gaap", "StockholdersEquity", "USD"),
    "shares": ("dei", "EntityCommonStockSharesOutstanding", "shares"),
    "net_income": ("us-gaap", "NetIncomeLoss", "USD"),
    "revenue": ("us-gaap", "Revenues", "USD"),
}

_DEFAULT_UA = "AlphaForge research contact@alphaforge.example"
_CACHE_DIR = Path.home() / ".alphaforge" / "cache" / "edgar"


@register_fundamental_provider
class EdgarFundamentalProvider(FundamentalProvider):
    name = "edgar"

    def __init__(
        self, user_agent: str | None = None, cache_dir: Path | str = _CACHE_DIR, delay: float = 0.0
    ) -> None:
        self.user_agent = user_agent or _DEFAULT_UA
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.delay = delay  # optional politeness pause between live fetches
        self._cik: dict[str, int] | None = None

    # --- point-in-time assembly ------------------------------------------------

    def point_in_time(
        self, symbols: list[str], fields: list[str], dates: pd.DatetimeIndex
    ) -> dict[str, pd.DataFrame]:
        cikmap = self._ticker_to_cik()
        out = {f: pd.DataFrame(index=dates, columns=symbols, dtype="float64") for f in fields}
        for sym in symbols:
            cik = cikmap.get(sym.upper())
            if cik is None:
                continue  # ticker not in EDGAR -> all-NaN column
            for field in fields:
                series = self._concept_series(cik, field)
                if series is not None and not series.empty:
                    out[field][sym] = self._asof_ffill(series, dates).to_numpy()
        return out

    @staticmethod
    def _asof_ffill(series: pd.Series, dates: pd.DatetimeIndex) -> pd.Series:
        """Forward-fill a filing-date-indexed series onto ``dates``.

        A value at filed date D is visible on every date >= D and NaN before it,
        the core no-lookahead guarantee for fundamentals.
        """
        union = series.index.union(dates)
        return series.reindex(union).ffill().reindex(dates)

    # --- raw concept fetch -----------------------------------------------------

    def _concept_series(self, cik: int, field: str) -> pd.Series | None:
        taxonomy, concept, unit = FIELD_CONCEPTS[field]
        url = (
            f"https://data.sec.gov/api/xbrl/companyconcept/"
            f"CIK{cik:010d}/{taxonomy}/{concept}.json"
        )
        data = self._get_json(url, f"concept_{cik:010d}_{taxonomy}_{concept}.json")
        if data is None:
            return None
        rows = data.get("units", {}).get(unit)
        if not rows:
            return None
        return self._series_from_rows(rows)

    @staticmethod
    def _series_from_rows(rows: list[dict]) -> pd.Series:
        """Collapse raw XBRL fact rows into a value-by-filing-date series.

        When several facts share a filing date (a report restates multiple
        periods), keep the one with the latest period end. The as-of-filing
        figure. Later filings naturally override earlier ones via forward-fill.
        """
        df = pd.DataFrame(rows)
        df = df[["filed", "end", "val"]].copy()
        df["filed"] = pd.to_datetime(df["filed"])
        df["end"] = pd.to_datetime(df["end"])
        df = df.sort_values(["filed", "end"]).drop_duplicates("filed", keep="last")
        return pd.Series(df["val"].to_numpy(dtype="float64"), index=df["filed"])

    # --- ticker -> CIK ---------------------------------------------------------

    def _ticker_to_cik(self) -> dict[str, int]:
        if self._cik is None:
            data = self._get_json(
                "https://www.sec.gov/files/company_tickers.json", "company_tickers.json"
            )
            self._cik = (
                {v["ticker"].upper(): int(v["cik_str"]) for v in data.values()} if data else {}
            )
        return self._cik

    # --- cached HTTP GET -------------------------------------------------------

    def _get_json(self, url: str, cache_name: str) -> dict | None:
        path = self.cache_dir / cache_name
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
        except Exception:
            return None  # 404 (concept not reported) / network issue -> treat as no data
        if self.delay:
            time.sleep(self.delay)
        path.write_text(raw, encoding="utf-8")
        return json.loads(raw)
