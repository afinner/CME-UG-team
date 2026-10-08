"""Backtest CMES4 v1 (as traded) and v2 (proposed) on 5-minute bars.

Examples
  python backtest.py --source yahoo                    # ES=F, last ~60 days (needs internet + yfinance)
  python backtest.py --source yahoo --symbol NQ=F --point-value 20
  python backtest.py --source csv --csv es_5m.csv --tz Europe/Dublin   # e.g. a CQG export
  python backtest.py --source synthetic --days 500     # no-edge random walk: the null baseline

Writes one trades CSV per variant to --out and prints a summary table.
Read the confidence interval: with 60 days the average R is uncertain by about +/-0.25R.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

import pandas as pd

from cmes4_rules import CMES4Params, backtest, summarise, v2_params
from marketdata import load_csv, load_yahoo, synthetic_rth


def variants(point_value: float) -> dict[str, CMES4Params]:
    v1 = CMES4Params(point_value=point_value)
    v2 = v2_params(point_value=point_value)
    return {
        "v1_3bar": v1,
        "v1_4bar": replace(v1, trend_bars=4),
        "v1_no_room_filter": replace(v1, room_min_r=0.0),
        "v1_worst_case_fills": replace(v1, intrabar="worst"),
        "v2": v2,
        "v2_4bar": replace(v2, trend_bars=4),
        "v2_all_day": replace(v2, windows=((v2.windows[0][0], v2.windows[-1][1]),)),
        "v2_worst_case_fills": replace(v2, intrabar="worst"),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=["yahoo", "csv", "synthetic"], default="synthetic")
    ap.add_argument("--symbol", default="ES=F")
    ap.add_argument("--csv")
    ap.add_argument("--tz", default="America/New_York", help="time zone of the CSV timestamps")
    ap.add_argument("--days", type=int, default=500, help="synthetic days")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--point-value", type=float, default=50.0, help="$ per point: ES 50, MES 5, NQ 20")
    ap.add_argument("--out", default="results")
    a = ap.parse_args()

    if a.source == "yahoo":
        bars = load_yahoo(a.symbol)
    elif a.source == "csv":
        bars = load_csv(a.csv, tz=a.tz)
    else:
        bars = synthetic_rth(days=a.days, seed=a.seed)
    n_days = len(set(bars.index.date))
    print(f"{a.source}: {len(bars)} RTH 5m bars, {n_days} sessions, "
          f"{bars.index[0]:%Y-%m-%d} to {bars.index[-1]:%Y-%m-%d}\n")

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = {}
    for name, p in variants(a.point_value).items():
        trades, skipped = backtest(bars, p)
        trades.to_csv(out / f"trades_{a.source}_{name}.csv", index=False)
        s = summarise(trades, n_days)
        if not skipped.empty:
            s["skips"] = skipped["reason"].value_counts().to_dict()
        rows[name] = s

    table = pd.DataFrame(rows).T
    cols = ["trades", "per_day", "win_rate", "avg_r_net", "avg_r_ci95", "avg_r_gross",
            "median_risk_pts", "avg_mfe_r", "share_mfe_over_3r", "best_r", "worst_r"]
    with pd.option_context("display.width", 200, "display.max_columns", 20, "display.precision", 3):
        print(table[[c for c in cols if c in table]].to_string())
    table.to_csv(out / f"summary_{a.source}.csv")
    print(f"\nTrades and summary written to {out}/")
    print("Go/no-go (decide before looking): scale v2 up only if its avg_r_net is above 0 "
          "AND its worst-case-fills version is above -0.10R.")


if __name__ == "__main__":
    main()
