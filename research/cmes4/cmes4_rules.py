"""CMES4 strategy engine: the rules as reconstructed from the team's trading book.

CMES4 (as traded on 5-7 Oct 2026, trades T002-T004, decisions D001-D005):

1. Trend: N consecutive completed 15-minute bars, each with a higher high AND a
   higher low than the bar before (a downtrend mirrors this).  The team logged two
   wordings of this rule, "3-bar" and "4-bar" (D001), so ``trend_bars`` is a parameter.
2. Setup: at the close of the last trend bar.
3. Pullback: within the next ``pullback_window`` 5-minute bars, a bar that dips
   (low below the previous bar's low) in an uptrend, or bounces (high above the
   previous bar's high) in a downtrend.  An equal high is not a bounce (D005).
4. Confirmation: the very next 5-minute bar closes back in the trend direction.
5. Entry at the confirming close; stop one tick beyond the pullback bar; target 2R.
6. Room-to-peak filter: distance from entry to the trend's extreme must be at
   least ``room_min_r`` x risk (D002: 2.00 pts room vs 4.75 risk = no trade).
7. Time limit: exit at market if neither stop nor target is hit.

Times are US Eastern (ET).  Dublin is ET + 5h until 24 Oct and ET + 4h on 26-30 Oct.

``CMES4Params`` defaults reproduce the rules above (v1).  ``v2_params`` adds the
improvements proposed in the report: an entry stop above the confirming bar,
half off at 2R with the rest trailed, and trading only the open and close windows.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import time, timedelta

import numpy as np
import pandas as pd

LONG, SHORT = 1, -1


@dataclass(frozen=True)
class CMES4Params:
    trend_bars: int = 3                      # 15m bars in the trend; 3 bars = 2 comparisons
    trend_rule: str = "hh_hl"                # "hh_hl" or "close" (higher closes only)
    pullback_window: int = 3                 # 5m bars after the setup in which the pullback may start
    confirm_rule: str = "close_beyond_pullback_close"  # or "close_beyond_pullback_extreme", "trend_bar"
    entry_rule: str = "confirm_close"        # or "stop_beyond_confirm" (v2)
    entry_stop_valid_bars: int = 2           # stop-entry order life, in 5m bars (v2)
    stop_ticks: int = 1
    target_r: float | None = 2.0             # None = no fixed target
    room_min_r: float = 1.0                  # 0 disables the room-to-peak filter
    time_limit_bars: int | None = 12         # 12 x 5m = 60 minutes; None = hold to flat time
    windows: tuple[tuple[time, time], ...] = ((time(10, 0), time(15, 30)),)  # setup times allowed (ET)
    flat_time: time = time(15, 55)
    max_trades_per_day: int = 4
    max_losses_per_day: int | None = None    # stop for the day after this many losing trades
    # management (v2)
    partial_at_r: float | None = None        # take half off here, then breakeven + trail the rest
    trail_lookback: int = 3                  # trail under the lowest low of the last N 5m bars
    min_risk_pts: float = 0.0                # skip setups with a smaller stop (noise)
    max_risk_pts: float = float("inf")       # skip setups with a bigger stop
    # costs, in index points per contract
    tick: float = 0.25
    point_value: float = 50.0                # ES; MES = 5
    commission_per_side: float = 2.50        # challenge commission, $ per contract per side
    slippage_ticks: float = 1.0              # on market entries, stop exits and time exits
    intrabar: str = "ohlc"                   # order of moves inside a bar: "ohlc" or "worst"

    @property
    def commission_pts_round_trip(self) -> float:
        return 2 * self.commission_per_side / self.point_value


def v2_params(**overrides) -> CMES4Params:
    """CMES4 v2: same setup, objective entry, uncapped runner, open and close windows."""
    base = CMES4Params(
        trend_bars=3,
        entry_rule="stop_beyond_confirm",
        target_r=None,
        partial_at_r=2.0,
        room_min_r=0.0,                      # the runner makes the prior peak irrelevant
        time_limit_bars=12,                  # applies until the partial fills
        windows=((time(9, 45), time(11, 30)), (time(14, 0), time(15, 30))),
        min_risk_pts=2.0,
        max_risk_pts=12.0,
        max_trades_per_day=3,
        max_losses_per_day=2,
    )
    return replace(base, **overrides)


# --------------------------------------------------------------------------- helpers

def to_15m(bars5: pd.DataFrame) -> pd.DataFrame:
    """Resample 5m bars (index = bar start, ET) into 15m bars labelled by start time."""
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    out = bars5.resample("15min", label="left", closed="left").agg(agg)
    return out.dropna()


def _trend(df15: pd.DataFrame, k: int, n: int, rule: str) -> int:
    """+1 / -1 if bars k-n+1..k form an up / down trend, else 0."""
    if k - n + 1 < 0:
        return 0
    seg = df15.iloc[k - n + 1:k + 1]
    hi, lo, cl = seg["high"].to_numpy(), seg["low"].to_numpy(), seg["close"].to_numpy()
    if rule == "close":
        up = np.all(np.diff(cl) > 0)
        down = np.all(np.diff(cl) < 0)
    else:
        up = np.all(np.diff(hi) > 0) and np.all(np.diff(lo) > 0)
        down = np.all(np.diff(hi) < 0) and np.all(np.diff(lo) < 0)
    return LONG if up else SHORT if down else 0


def _is_pullback(bar, prev, d: int) -> bool:
    return bar.low < prev.low if d == LONG else bar.high > prev.high


def _is_confirm(conf, pb, d: int, rule: str) -> bool:
    if rule == "close_beyond_pullback_extreme":
        return conf.close > pb.high if d == LONG else conf.close < pb.low
    if rule == "trend_bar":
        return conf.close > conf.open if d == LONG else conf.close < conf.open
    return conf.close > pb.close if d == LONG else conf.close < pb.close


def _in_windows(t: time, windows) -> bool:
    return any(a <= t <= b for a, b in windows)


def _ypath(b, d: int, worst: bool = False, pending_entry: bool = False) -> tuple:
    """The bar's path in direction-normalised prices (y = d x price, so up is good for us).

    Standard OHLC rule: a bar that closes up went open-low-high-close, one that closes
    down went open-high-low-close.  ``worst`` puts the adverse extreme first for an
    open position, and fills a pending stop entry before the adverse extreme.
    """
    o, c = d * b.open, d * b.close
    hi, lo = (b.high, b.low) if d == LONG else (-b.low, -b.high)
    if worst:
        return (o, hi, lo, c) if pending_entry else (o, lo, hi, c)
    return (o, lo, hi, c) if c >= o else (o, hi, lo, c)


def _fill_stop_entry(b, d: int, trigger_y: float, worst: bool):
    """Fill price (y units) of a stop entry on this bar and the rest of the bar's path, or (None, None)."""
    pts = _ypath(b, d, worst, pending_entry=True)
    if pts[0] >= trigger_y:
        return pts[0], pts[1:]
    for k in range(1, len(pts)):
        if pts[k - 1] < trigger_y <= pts[k]:
            return trigger_y, pts[k:]
    return None, None


# --------------------------------------------------------------------------- engine

def find_setups(day5: pd.DataFrame, p: CMES4Params) -> list[dict]:
    """All qualifying CMES4 setups in one RTH session (no position bookkeeping)."""
    df15 = to_15m(day5)
    setups = []
    for k in range(len(df15)):
        d = _trend(df15, k, p.trend_bars, p.trend_rule)
        if not d:
            continue
        t_setup = df15.index[k] + timedelta(minutes=15)
        if not _in_windows(t_setup.time(), p.windows):
            continue
        trend_start = df15.index[k - p.trend_bars + 1]
        setups.append({"time": t_setup, "dir": d, "trend_start": trend_start})
    return setups


def _scan_entry(day5: pd.DataFrame, s: dict, p: CMES4Params):
    """Find pullback + confirmation after a setup; return an entry dict or a skip reason."""
    d, t0 = s["dir"], s["time"]
    pos0 = day5.index.searchsorted(t0)
    if pos0 == 0 or pos0 >= len(day5):
        return None, "no bars"
    for i in range(pos0, min(pos0 + p.pullback_window, len(day5))):
        pb, prev = day5.iloc[i], day5.iloc[i - 1]
        if not _is_pullback(pb, prev, d):
            continue
        if i + 1 >= len(day5):
            return None, "no confirm bar"
        conf = day5.iloc[i + 1]
        if not _is_confirm(conf, pb, d, p.confirm_rule):
            continue
        stop = pb.low - p.stop_ticks * p.tick if d == LONG else pb.high + p.stop_ticks * p.tick
        span = day5.loc[s["trend_start"]:day5.index[i]]
        extreme = span["high"].max() if d == LONG else span["low"].min()
        fill_rest = ()
        if p.entry_rule == "stop_beyond_confirm":
            trigger_y = d * (conf.high + p.tick if d == LONG else conf.low - p.tick)
            fill_y = None
            for j in range(i + 2, min(i + 2 + p.entry_stop_valid_bars, len(day5))):
                fill_y, fill_rest = _fill_stop_entry(day5.iloc[j], d, trigger_y, p.intrabar == "worst")
                if fill_y is not None:
                    break
            if fill_y is None:
                return None, "entry stop not filled"
            entry_planned, entry_pos, entry_in_bar = d * fill_y, j, True
        else:
            entry_planned, entry_pos, entry_in_bar = conf.close, i + 1, False
        risk = abs(entry_planned - stop)
        room = (extreme - entry_planned) * d
        if risk <= 0:
            return None, "bad risk"
        if risk < p.min_risk_pts or risk > p.max_risk_pts:
            return None, "risk outside band"
        if p.room_min_r and room < p.room_min_r * risk:
            return None, "room-to-peak"
        return {
            "dir": d, "pullback_time": day5.index[i], "confirm_time": day5.index[i + 1],
            "entry_pos": entry_pos, "entry_in_bar": entry_in_bar, "fill_rest": fill_rest,
            "entry_planned": entry_planned, "stop": stop, "risk": risk, "room": room,
        }, None
    return None, "no pullback+confirm in window"


def _manage(day5: pd.DataFrame, e: dict, p: CMES4Params) -> dict:
    """Walk each bar's path after entry and return the exit (prices in y = d x price)."""
    d, risk = e["dir"], e["risk"]
    worst = p.intrabar == "worst"
    slip = p.slippage_ticks * p.tick
    entry, stop = d * e["entry_planned"], d * e["stop"]
    target = entry + p.target_r * risk if p.target_r else None
    partial = entry + p.partial_at_r * risk if p.partial_at_r else None
    half = False
    mfe = mae = 0.0
    lows = []
    first = e["entry_pos"] if e["entry_in_bar"] else e["entry_pos"] + 1
    exit_y = reason = exit_pos = None

    for j in range(first, len(day5)):
        b = day5.iloc[j]
        if e["entry_in_bar"] and j == e["entry_pos"]:
            pts = (entry,) + tuple(e["fill_rest"])
        else:
            pts = _ypath(b, d, worst)
            if pts[0] <= stop:                       # opened through the stop
                exit_y, reason, exit_pos = pts[0] - slip, ("trail" if half else "stop"), j
                break
        mfe = max(mfe, (max(pts) - entry) / risk)
        mae = max(mae, (entry - min(pts)) / risk)
        for x, y in zip(pts[:-1], pts[1:]):
            if y < x and y <= stop:
                exit_y, reason = stop - slip, ("trail" if half else "stop")
                break
            if y > x:
                if partial is not None and not half and y >= partial:
                    half, stop = True, max(stop, entry)     # half off; runner to breakeven
                if target is not None and y >= target:
                    exit_y, reason = target, "target"
                    break
        if exit_y is not None:
            exit_pos = j
            break
        lows.append(min(pts))
        if half:
            stop = max(stop, min(lows[-p.trail_lookback:]) - p.tick)
        bar_end = day5.index[j] + timedelta(minutes=5)
        if p.time_limit_bars is not None and not half and j - e["entry_pos"] >= p.time_limit_bars:
            exit_y, reason, exit_pos = pts[-1] - slip, "time", j
            break
        if j == len(day5) - 1 or bar_end.time() >= p.flat_time:
            exit_y, reason, exit_pos = pts[-1] - slip, "flat", j
            break

    runner_r = (exit_y - entry) / risk
    gross_r = 0.5 * p.partial_at_r + 0.5 * runner_r if half else runner_r
    costs_r = (p.commission_pts_round_trip + slip) / risk   # commission + entry slippage
    return {
        "exit_time": day5.index[exit_pos] + timedelta(minutes=5), "exit": d * exit_y,
        "exit_reason": reason, "entry_fill": e["entry_planned"] + d * slip,
        "r_gross": gross_r, "r_net": gross_r - costs_r,
        "mfe_r": mfe, "mae_r": mae, "partial": half,
    }


def backtest(bars5: pd.DataFrame, p: CMES4Params) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run CMES4 on RTH 5m bars (ET index).  Returns (trades, skipped setups)."""
    trades, skipped = [], []
    for day, day5 in bars5.groupby(bars5.index.date):
        if len(day5) < 30:
            continue
        busy_until = None
        n_today = losses_today = 0
        for s in find_setups(day5, p):
            if busy_until is not None and s["time"] < busy_until:
                continue
            if n_today >= p.max_trades_per_day:
                break
            if p.max_losses_per_day is not None and losses_today >= p.max_losses_per_day:
                break
            e, why = _scan_entry(day5, s, p)
            if e is None:
                skipped.append({"date": day, "setup_time": s["time"], "dir": s["dir"], "reason": why})
                continue
            x = _manage(day5, e, p)
            busy_until = x["exit_time"]
            n_today += 1
            losses_today += x["r_net"] < 0
            trades.append({
                "date": day, "setup_time": s["time"], "dir": e["dir"],
                "entry_time": day5.index[e["entry_pos"]] + (timedelta(0) if e["entry_in_bar"] else timedelta(minutes=5)),
                "entry": e["entry_planned"], "stop": e["stop"], "risk_pts": e["risk"], "room_pts": e["room"],
                **x,
            })
    return pd.DataFrame(trades), pd.DataFrame(skipped)


def summarise(trades: pd.DataFrame, n_days: int) -> dict:
    """Headline stats in R."""
    if trades.empty:
        return {"trades": 0, "per_day": 0.0}
    r = trades["r_net"]
    se = r.std(ddof=1) / np.sqrt(len(r)) if len(r) > 1 else np.nan
    return {
        "trades": len(r),
        "per_day": len(r) / max(n_days, 1),
        "win_rate": float((r > 0).mean()),
        "target_or_runner_hits": float(trades["exit_reason"].isin(["target", "trail"]).mean()),
        "avg_r_net": float(r.mean()),
        "avg_r_ci95": (round(float(r.mean() - 1.96 * se), 3), round(float(r.mean() + 1.96 * se), 3)) if len(r) > 1 else None,
        "avg_r_gross": float(trades["r_gross"].mean()),
        "median_risk_pts": float(trades["risk_pts"].median()),
        "avg_mfe_r": float(trades["mfe_r"].mean()),
        "share_mfe_over_3r": float((trades["mfe_r"] >= 3).mean()),
        "best_r": float(r.max()),
        "worst_r": float(r.min()),
    }
