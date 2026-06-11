"""Tests for the universe layer + point-in-time tradeability masking.

These pin down the survivorship-bias guarantees: a name is only a member while
its membership interval is active, the download set is the union over the range,
and a delisting forces an exit in the resulting weights.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from alphaforge.config import BacktestConfig, DataConfig, FactorConfig, UniverseConfig
from alphaforge.data.quality import tradeable_mask, validate_prices
from alphaforge.engine.backtest import build_target_weights
from alphaforge.universe import from_config
from alphaforge.universe.point_in_time import PointInTimeUniverse
from alphaforge.universe.static import StaticUniverse


def _dates(start="2020-01-01", periods=300):
    return pd.bdate_range(start, periods=periods)


def test_static_universe_all_members_always():
    u = StaticUniverse(["aapl", "MSFT", "aapl"])  # lower-case + dupe
    assert u.all_symbols(date(2020, 1, 1), date(2021, 1, 1)) == ["AAPL", "MSFT"]
    m = u.membership(_dates(periods=10))
    assert m.to_numpy().all()


def test_pit_download_set_is_union_over_range():
    u = PointInTimeUniverse(
        intervals={
            "AAPL": ("2015-01-01", None),
            "TWTR": ("2015-01-01", "2022-10-27"),
            "ABC": ("2030-01-01", None),  # not yet listed in our window
        }
    )
    syms = u.all_symbols(date(2020, 1, 1), date(2021, 1, 1))
    assert syms == ["AAPL", "TWTR"]  # ABC excluded: TWTR still active in 2020


def test_pit_membership_respects_delisting():
    u = PointInTimeUniverse(intervals={"TWTR": ("2015-01-01", "2022-10-27")})
    dates = pd.to_datetime(["2022-10-26", "2022-10-27", "2022-10-28"])
    m = u.membership(pd.DatetimeIndex(dates))
    assert list(m["TWTR"]) == [True, True, False]


def test_pit_supports_multiple_spells():
    # A name removed then re-added (like AAL) must be a member in BOTH spells
    # and a non-member in the gap between them.
    u = PointInTimeUniverse(
        intervals={"AAL": [("1996-01-02", "1997-01-15"), ("2015-03-23", None)]}
    )
    dates = pd.to_datetime(["1996-06-01", "2000-01-01", "2016-01-01"])
    m = u.membership(pd.DatetimeIndex(dates))
    assert list(m["AAL"]) == [True, False, True]
    # Overlapping either spell puts it in the download set.
    assert u.all_symbols(date(1996, 1, 1), date(1996, 12, 31)) == ["AAL"]
    assert u.all_symbols(date(2000, 1, 1), date(2001, 1, 1)) == []  # in the gap


def test_from_config_static_and_pit(tmp_path):
    csv = tmp_path / "m.csv"
    csv.write_text("symbol,start,end\nAAPL,2015-01-01,\nTWTR,2015-01-01,2022-10-27\n")
    u = from_config(UniverseConfig(kind="point_in_time", membership_file=str(csv)))
    assert isinstance(u, PointInTimeUniverse)
    s = from_config(UniverseConfig(kind="static", symbols=["AAPL"]))
    assert isinstance(s, StaticUniverse)


def test_quality_flags_partial_and_nodata():
    dates = _dates(periods=50)
    close = pd.DataFrame(100.0, index=dates, columns=["FULL", "LATE", "GONE"])
    close.loc[: dates[20], "LATE"] = np.nan   # IPOs partway in
    close["GONE"] = np.nan                     # never any data
    prices = pd.concat({"close": close}, axis=1)
    rep = validate_prices(prices)
    assert "GONE" in rep.no_data
    assert "LATE" in rep.partial
    assert "FULL" not in rep.partial and "FULL" not in rep.no_data


def test_delisting_forces_exit_in_weights():
    # Two names; "GONE" delists midway. With a constant high score it would be
    # The tradeable mask must zero it out after delisting.
    dates = _dates(periods=120)
    cols = ["KEEP", "GONE"]
    close = pd.DataFrame(
        np.linspace(100, 130, len(dates))[:, None].repeat(2, axis=1),
        index=dates,
        columns=cols,
    )
    cut = dates[80]
    close.loc[cut:, "GONE"] = np.nan
    prices = pd.concat({"close": close}, axis=1)

    members = pd.DataFrame(True, index=dates, columns=cols)
    members.loc[cut:, "GONE"] = False
    tradeable = tradeable_mask(prices) & members

    scores = pd.DataFrame(1.0, index=dates, columns=cols)  # both always "great"
    cfg = BacktestConfig(
        data=DataConfig(symbols=cols, start=date(2020, 1, 1), end=date(2021, 1, 1)),
        factor=FactorConfig(name="momentum"),
        top_n=2,
        rebalance="daily",
    )
    w = build_target_weights(scores, cfg, tradeable=tradeable)
    # After the delisting date, GONE must carry zero weight everywhere.
    assert (w.loc[cut:, "GONE"] == 0).all()
    # KEEP is still held.
    assert (w.loc[cut:, "KEEP"] > 0).any()
