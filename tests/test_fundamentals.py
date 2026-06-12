"""Tests for the fundamentals layer + value factor.

The headline guarantee: a fundamental is invisible before its filing date
(no lookahead), and book-to-market ranks cheap names above expensive ones.
These run fully offline. EDGAR's live path is verified manually."""

from __future__ import annotations

import numpy as np
import pandas as pd

from alphaforge.factors import get_factor
from alphaforge.fundamentals.base import FundamentalProvider
from alphaforge.fundamentals.edgar import EdgarFundamentalProvider


def test_series_from_rows_keeps_latest_period_per_filing():
    rows = [
        {"filed": "2021-02-15", "end": "2020-09-30", "val": 90.0},   # comparative
        {"filed": "2021-02-15", "end": "2020-12-31", "val": 100.0},  # as-of figure
        {"filed": "2021-05-10", "end": "2021-03-31", "val": 110.0},
    ]
    s = EdgarFundamentalProvider._series_from_rows(rows)
    # One value per filing date, the latest period end wins.
    assert s.loc[pd.Timestamp("2021-02-15")] == 100.0
    assert s.loc[pd.Timestamp("2021-05-10")] == 110.0


def test_asof_ffill_is_lookahead_free():
    series = pd.Series(
        [100.0, 110.0],
        index=pd.to_datetime(["2021-02-15", "2021-05-10"]),
    )
    dates = pd.bdate_range("2021-02-12", "2021-05-12")
    pit = EdgarFundamentalProvider._asof_ffill(series, dates)
    # Before the first filing -> NaN (we must NOT know the value early).
    assert np.isnan(pit.loc["2021-02-12"])
    # On/after the filing -> visible and forward-filled.
    assert pit.loc["2021-02-15"] == 100.0
    assert pit.loc["2021-03-01"] == 100.0
    # The next filing supersedes it.
    assert pit.loc["2021-05-10"] == 110.0


class _StubFundamentals(FundamentalProvider):
    """Two names: CHEAP (high book, low price) and RICH (low book, high price)."""

    name = "stub"

    def point_in_time(self, symbols, fields, dates):
        book = pd.DataFrame({"CHEAP": 200.0, "RICH": 50.0}, index=dates)[symbols]
        shares = pd.DataFrame({"CHEAP": 1.0, "RICH": 1.0}, index=dates)[symbols]
        return {"book_equity": book, "shares": shares}


def test_value_factor_prefers_cheap():
    dates = pd.bdate_range("2021-01-01", periods=10)
    close = pd.DataFrame({"CHEAP": 10.0, "RICH": 100.0}, index=dates)
    prices = pd.concat({"close": close}, axis=1)

    factor = get_factor("value", provider=_StubFundamentals())
    btm = factor.compute(prices)
    # CHEAP: 200/(10*1)=20 ; RICH: 50/(100*1)=0.5 -> CHEAP much higher (attractive).
    assert btm["CHEAP"].iloc[-1] > btm["RICH"].iloc[-1]
    assert np.isclose(btm["CHEAP"].iloc[-1], 20.0)
    assert np.isclose(btm["RICH"].iloc[-1], 0.5)
