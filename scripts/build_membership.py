"""Generate a point-in-time S&P 500 membership CSV.

Source: the community-maintained dataset at https://github.com/fja05680/sp500,
specifically ``sp500_ticker_start_end.csv``, already has one row per membership
spell (ticker, start_date, end_date), with re-additions as separate rows. We
just rename columns to AlphaForge's ``symbol,start,end`` schema.

Optionally scope to a date window, and (by default) convert dotted tickers like BRK.B to
the BRK-B form yfinance expects.

Usage:
    python scripts/build_membership.py --out membership_sp500.csv
    python scripts/build_membership.py --start 2019-01-01 --end 2023-12-31 \
        --out membership_2019_2023.csv

Then backtest against it:
    alphaforge run --universe-file membership_2019_2023.csv \
        --start 2019-01-01 --end 2023-12-31 --factor momentum --top-n 20

This is necessary as a broad historical universe includes many delisted names yfinance can't
serve. Those surface as NO DATA in the quality report and are simply excluded.
Scope with --start/--end to keep the download set manageable.
"""

from __future__ import annotations

import argparse

import pandas as pd

SOURCE_URL = (
    "https://raw.githubusercontent.com/fja05680/sp500/master/sp500_ticker_start_end.csv"
)
FAR_FUTURE = pd.Timestamp("2261-12-31")


def build(url: str, start: str | None, end: str | None, yahoo: bool) -> pd.DataFrame:
    raw = pd.read_csv(url)
    df = raw.rename(columns={"ticker": "symbol", "start_date": "start", "end_date": "end"})
    df = df[["symbol", "start", "end"]].copy()
    df["start"] = pd.to_datetime(df["start"])
    df["end"] = pd.to_datetime(df["end"])  # blank -> NaT

    # Keep only spells that overlap the requested [start, end] window.
    if start or end:
        s = pd.Timestamp(start) if start else df["start"].min()
        e = pd.Timestamp(end) if end else pd.Timestamp.today().normalize()
        active_end = df["end"].fillna(FAR_FUTURE)
        df = df[(df["start"] <= e) & (active_end >= s)].copy()

    if yahoo:
        # yfinance uses '-' where the index uses '.' (BRK.B -> BRK-B).
        df["symbol"] = df["symbol"].str.replace(".", "-", regex=False)

    df = df.sort_values(["symbol", "start"]).reset_index(drop=True)
    df["start"] = df["start"].dt.strftime("%Y-%m-%d")
    # Re-blank the NaT end dates after formatting.
    df["end"] = df["end"].dt.strftime("%Y-%m-%d")
    df.loc[df["end"] == "NaT", "end"] = ""
    df["end"] = df["end"].fillna("")
    return df


def main() -> None:
    ap = argparse.ArgumentParser(description="Build a point-in-time S&P 500 membership CSV.")
    ap.add_argument("--out", default="membership_sp500.csv", help="Output CSV path.")
    ap.add_argument("--start", help="Keep members active on/after this date (YYYY-MM-DD).")
    ap.add_argument("--end", help="Keep members active on/before this date (YYYY-MM-DD).")
    ap.add_argument("--url", default=SOURCE_URL, help="Override the source dataset URL.")
    ap.add_argument(
        "--no-yahoo",
        action="store_true",
        help="Keep dotted tickers as-is (default converts BRK.B -> BRK-B for yfinance).",
    )
    args = ap.parse_args()

    df = build(args.url, args.start, args.end, yahoo=not args.no_yahoo)
    df.to_csv(args.out, index=False)

    n_rows = len(df)
    n_syms = df["symbol"].nunique()
    n_active = int((df["end"] == "").sum())
    print(f"Wrote {args.out}")
    print(f"  spells: {n_rows}   unique symbols: {n_syms}   currently-active: {n_active}")
    if args.start or args.end:
        print(f"  window: {args.start or 'min'} -> {args.end or 'today'}")


if __name__ == "__main__":
    main()
