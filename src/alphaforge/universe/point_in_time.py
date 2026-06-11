"""A point-in-time universe backed by a membership table.

This is what makes survivorship-free backtests possible. The membership table
records, for each symbol, the date range(s) over which it was a member of the
universe (For example, an index). A symbol that left the index, acquired, delisted, or
simply dropped, stops being a member on its end date, and the engine will
neither select nor hold it afterward.

A symbol may have MULTIPLE membership spells (removed, later re-added), so the
table is stored as symbol -> list of (start, end) intervals.

CSV format (``end`` blank = still a member), one row per spell:

    symbol,start,end
    AAPL,2015-01-01,
    AAL,1996-01-02,1997-01-15
    AAL,2015-03-23,

The free yfinance source still can't give you *prices* for fully delisted names,
but this interface is exactly where a delisting-inclusive feed plugs in.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from alphaforge.universe.base import FAR_FUTURE, Universe, register_universe

# A spell is a (start, end) Timestamp pair; each symbol maps to a list of spells.
Intervals = dict[str, list[tuple]]


@register_universe
class PointInTimeUniverse(Universe):
    name = "point_in_time"

    def __init__(
        self,
        membership_file: str | Path | None = None,
        intervals: dict | None = None,
        **_,
    ) -> None:
        if membership_file is not None:
            self._intervals = self._load(membership_file)
        elif intervals is not None:
            self._intervals = self._normalize(intervals)
        else:
            raise ValueError("PointInTimeUniverse needs membership_file or intervals")
        if not self._intervals:
            raise ValueError("membership table is empty")

    @staticmethod
    def _normalize(intervals: dict) -> Intervals:
        """Accept either {sym: (start, end)} or {sym: [(start, end), ...]}."""
        out: Intervals = {}
        for sym, val in intervals.items():
            spells = val if isinstance(val, list) else [val]
            out[sym.upper()] = [
                (pd.Timestamp(lo), pd.Timestamp(hi) if hi else FAR_FUTURE) for lo, hi in spells
            ]
        return out

    @staticmethod
    def _load(path: str | Path) -> Intervals:
        df = pd.read_csv(path)
        cols = {c.lower(): c for c in df.columns}
        if "symbol" not in cols or "start" not in cols:
            raise ValueError("membership file needs at least 'symbol' and 'start' columns")
        out: Intervals = {}
        for _, row in df.iterrows():
            sym = str(row[cols["symbol"]]).strip().upper()
            lo = pd.Timestamp(row[cols["start"]])
            hi_raw = row[cols["end"]] if "end" in cols else None
            hi = FAR_FUTURE if pd.isna(hi_raw) or str(hi_raw).strip() == "" else pd.Timestamp(hi_raw)
            out.setdefault(sym, []).append((lo, hi))
        return out

    def all_symbols(self, start: date, end: date) -> list[str]:
        s, e = pd.Timestamp(start), pd.Timestamp(end)
        # A symbol is in the download set if ANY of its spells overlaps the window.
        return sorted(
            sym
            for sym, spells in self._intervals.items()
            if any(lo <= e and hi >= s for lo, hi in spells)
        )

    def membership(self, dates: pd.DatetimeIndex) -> pd.DataFrame:
        cols = sorted(self._intervals)
        mask = pd.DataFrame(False, index=dates, columns=cols)
        for sym, spells in self._intervals.items():
            member = pd.Series(False, index=dates)
            for lo, hi in spells:
                member |= (dates >= lo) & (dates <= hi)
            mask[sym] = member.to_numpy()
        return mask
