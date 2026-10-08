"""Print the CMES4 upper-limit tables used in the report and save them as Markdown.

  python upper_limit.py                       # uses the no-edge synthetic trades for v2's shape
  python upper_limit.py --v2-trades results/trades_yahoo_v2.csv   # after a real-data backtest
  python upper_limit.py --balance 1001395 --days 16

All money figures assume ES at $50 a point and $28,600 margin per contract.  Check the
margin CQG actually charges (Account > Purchasing power) and pass --margin.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from ceiling import ES, Contract, Scenario, best_shot, orb_trade_sample, perfect_foresight, per_trade_ceiling, simulate, simulate_trades
from cmes4_rules import backtest, v2_params
from marketdata import synthetic_rth

PCT = lambda x: f"{x:+.1%}"          # noqa: E731
P = lambda x: f"{x:.1%}"             # noqa: E731


def md(df: pd.DataFrame) -> str:
    """Markdown pipe table (no extra dependency)."""
    head = "| " + " | ".join(map(str, df.columns)) + " |"
    rule = "|" + "|".join(" --- " for _ in df.columns) + "|"
    body = ["| " + " | ".join(map(str, r)) + " |" for r in df.itertuples(index=False)]
    return "\n".join([head, rule, *body])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--balance", type=float, default=1_001_395.0)
    ap.add_argument("--days", type=int, default=16, help="sessions left (9-30 Oct = 16)")
    ap.add_argument("--stop", type=float, default=4.0, help="typical CMES4 stop, ES points")
    ap.add_argument("--margin", type=float, default=ES.margin)
    ap.add_argument("--v2-trades", help="trades CSV from backtest.py for CMES4 v2")
    ap.add_argument("--v2-per-day", type=float, default=1.25, help="v2 trades a day, with --v2-trades")
    ap.add_argument("--paths", type=int, default=20_000)
    ap.add_argument("--out", default="results/upper_limit.md")
    a = ap.parse_args()
    c = replace(ES, margin=a.margin)
    max_n = int(a.balance // c.margin)
    sections = []

    # A. what one trade can add at full margin
    rows = [("CMES4 v1 target: 2R x %.1f pts" % a.stop, 2 * a.stop),
            ("v2 runner on a trend leg (25 pts)", 25.0),
            ("Whole trend day, 1% of ES (78 pts)", 78.0)]
    tab_a = pd.DataFrame([{"Trade": n, "Points": f"{pts:g}",
                           "Most it can add (full margin)": P(per_trade_ceiling(pts, c))} for n, pts in rows])
    sections.append(("A. Most one perfect trade can add, at the margin limit "
                     f"({max_n} ES on ${a.balance:,.0f})", tab_a))

    # B. perfect foresight
    rows = []
    for name, kw in [("5 ES (as on 6 Oct)", {"fixed": 5}), ("0.5% risk per trade", {"risk_frac": 0.005}),
                     ("Full margin", {"risk_frac": 1.0})]:
        r = {"Size": name}
        for spd, label in [(1.0, "1 setup a day"), (2.3, "Every setup, full session (2.3 a day)")]:
            n = int(round(spd * a.days))
            fb = perfect_foresight(a.balance, n, a.stop, 2.0, c, **kw)
            r[f"{label}: {n} trades"] = PCT(fb / a.balance - 1)
        rows.append(r)
    sections.append(("B. Perfect foresight: every setup wins 2R, compounded to 30 Oct", pd.DataFrame(rows)))

    # C. realistic range for v1
    rows = []
    for hit_name, hit in [("33% (no edge)", 1 / 3), ("38% (breakeven after costs)", 0.38), ("45% (strong edge)", 0.45)]:
        for size, kw in [("5 ES", {"fixed": 5}), ("Full margin", {"risk_frac": 1.0})]:
            for spd in (1.0, 2.3):
                s = Scenario("", hit, spd, stop_pts_median=a.stop, daily_stop_frac=None, **kw)
                m = simulate(s, a.balance, a.days, a.paths, c)
                rows.append({"Hit rate": hit_name, "Size": size, "Setups/day": spd, "Median": PCT(m["median"]),
                             "1 in 10 best": PCT(m["p90"]), "1 in 100 best": PCT(m["p99"]),
                             "P(>= +30%)": P(m["p_up_30"]), "P(<= -10%)": P(m["p_down_10"])})
    sections.append(("C. CMES4 v1 by 30 Oct, Monte Carlo (20,000 runs)", pd.DataFrame(rows)))

    # D. v2 with its own trade shape
    if a.v2_trades:
        t = pd.read_csv(a.v2_trades)
        src, per_day = a.v2_trades, a.v2_per_day
    else:
        t, _ = backtest(synthetic_rth(days=1000, seed=2026), v2_params())
        src, per_day = "no-edge synthetic backtest, 1,000 sessions", round(len(t) / 1000, 2)
    rows = []
    for edge in (None, 0.10, 0.20):
        for size, kw in [("0.5% risk", {"risk_frac": 0.005}), ("1% risk (margin-capped)", {"risk_frac": 0.01}),
                         ("Full margin", {"risk_frac": 1.0, "daily_stop_frac": None})]:
            m = simulate_trades(t["r_net"].to_numpy(), t["risk_pts"].to_numpy(), per_day, mean_r=edge,
                                balance0=a.balance, days=a.days, paths=a.paths, c=c, **kw)
            rows.append({"Average R per trade": "as backtested (%+.2f)" % t["r_net"].mean() if edge is None else f"{edge:+.2f}",
                         "Size": size, "Median": PCT(m["median"]), "1 in 10 best": PCT(m["p90"]),
                         "1 in 100 best": PCT(m["p99"]), "P(>= +30%)": P(m["p_up_30"]),
                         "P(<= -10%)": P(m["p_down_10"])})
    sections.append((f"D. CMES4 v2 by 30 Oct, {per_day} trades a day, trade shape from {src}", pd.DataFrame(rows)))

    # E. the alternative already on the table: the WTI opening-range breakout playbook
    cl = Contract("CL", 1000.0, margin=1e12, commission_rt=5.0)
    rows = []
    for edge in (0.0, 0.15):
        r = orb_trade_sample(edge)
        stop = np.full(len(r), 1.22)              # the playbook's worked example: $1.22 range
        for risk in (0.015, 0.03, 0.05):
            m = simulate_trades(r - 25 / 1220, stop, 0.6, risk_frac=risk, balance0=a.balance, days=a.days,
                                paths=a.paths, c=cl, daily_stop_frac=None, max_per_day=1, margin_cap=False)
            rows.append({"Average R per trade": f"{edge:+.2f}", "Risk per trade": P(risk),
                         "Median": PCT(m["median"]), "1 in 10 best": PCT(m["p90"]), "1 in 100 best": PCT(m["p99"]),
                         "P(>= +30%)": P(m["p_up_30"]), "P(<= -10%)": P(m["p_down_10"])})
    sections.append(("E. WTI opening-range breakout (the playbook), its own trade model, about 10 trades left",
                     pd.DataFrame(rows)))

    # F. the top-5 question for any strategy
    rows = []
    for tgt, label in [(0.297, "+30% (2024's 5th place, if it started at $1M)"), (1.0, "+100%"),
                       (2.18, "+218% (2025's 5th place)")]:
        for sr in (0.0, 1.3):
            b = best_shot(tgt, a.days, sr)
            rows.append({"Finish": label, "Strategy Sharpe": sr, "Best daily volatility": P(b["daily_vol"]),
                         "Best chance": P(b["p_target"]), "Chance of losing half": P(b["p_lose_half"])})
    sections.append(("F. Best possible odds for ANY strategy (log-normal approximation)", pd.DataFrame(rows)))

    # the report's range chart: six plans, 40,000 runs each
    chart = []

    def add(label, assume, m):
        chart.append({"label": label, "assume": assume,
                      **{k: round(m[k] * 100, 1) for k in ("p10", "median", "p90", "p99", "p_up_30", "p_down_10")}})

    for label, kw in [("CMES4 as traded (5 ES)", {"fixed": 5}), ("CMES4 at full margin (35 ES)", {"risk_frac": 1.0})]:
        add(label, "45% hit 2R, every setup (2.3 a day)",
            simulate(Scenario("", 0.45, 2.3, stop_pts_median=a.stop, daily_stop_frac=None, **kw), a.balance, a.days, 40_000, c))
    add("CMES4 v2 at 1% risk", f"+0.20R a trade, {per_day} a day",
        simulate_trades(t["r_net"].to_numpy(), t["risk_pts"].to_numpy(), per_day, risk_frac=0.01, mean_r=0.20,
                        balance0=a.balance, days=a.days, paths=40_000, c=c))
    r = orb_trade_sample(0.15) - 25 / 1220
    for risk in (0.015, 0.03, 0.05):
        add(f"WTI breakout at {risk:.1%} risk".replace(".0%", "%"), "playbook model, +0.15R, 0.6 a day",
            simulate_trades(r, np.full(len(r), 1.22), 0.6, risk_frac=risk, balance0=a.balance, days=a.days,
                            paths=40_000, c=cl, daily_stop_frac=None, max_per_day=1, margin_cap=False))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    (Path(a.out).parent / "chart_outcomes.json").write_text(json.dumps(chart, indent=1) + "\n")

    text = "\n\n".join(f"### {title}\n\n{md(df)}" for title, df in sections)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
