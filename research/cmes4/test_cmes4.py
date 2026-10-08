"""Tests for the CMES4 engine and the ceiling maths.  Run: python -m pytest -q"""

from datetime import time

import pandas as pd
import pytest

from ceiling import Scenario, contracts, kelly_binary, per_trade_ceiling, perfect_foresight, simulate
from cmes4_rules import CMES4Params, _trend, backtest, to_15m, v2_params
from marketdata import ET, synthetic_rth


def day(bars, date="2026-10-12"):
    """5m RTH bars from (open, high, low, close) tuples starting 09:30 ET, padded with flat bars."""
    bars = list(bars)
    last = bars[-1][3]
    bars += [(last, last, last, last)] * (78 - len(bars))
    idx = pd.date_range(f"{date} 09:30", periods=78, freq="5min", tz=ET)
    return pd.DataFrame(bars, columns=["open", "high", "low", "close"], index=idx)


def uptrend_bars(base=7800.0, spike=0.0):
    """Nine 5m bars = three rising 15m bars (09:30, 09:45, 10:00).  Optional spike on the last bar's high."""
    out = []
    for k in range(3):
        b = base + 10 * k
        out += [(b, b + 2, b - 1, b + 1), (b + 1, b + 3, b, b + 2), (b + 2, b + 4, b + 1, b + 3)]
    o, h, l, c = out[-1]
    out[-1] = (o, h + spike, l, c)
    return out


def downtrend_bars(base=7900.0):
    out = []
    for k in range(3):
        b = base - 10 * k
        out += [(b, b + 1, b - 2, b - 1), (b - 1, b, b - 3, b - 2), (b - 2, b - 1, b - 4, b - 3)]
    return out


# ------------------------------------------------------------------ trend rule (D001)

def test_three_bar_and_four_bar_wordings_can_disagree():
    df15 = pd.DataFrame({"open": [0] * 4, "close": [0] * 4,
                         "high": [10, 9, 11, 13], "low": [5, 6, 7, 8]})
    assert _trend(df15, 3, 3, "hh_hl") == 1      # last three bars rise
    assert _trend(df15, 3, 4, "hh_hl") == 0      # first comparison fails (9 < 10)


def test_resample_labels_by_bar_start():
    df15 = to_15m(day(uptrend_bars()))
    assert df15.index[0].time() == time(9, 30)
    assert df15.iloc[0]["high"] == 7804 and df15.iloc[0]["low"] == 7799


# ------------------------------------------------------------------ setup, entry, exits (T004 / D002 / D005)

def long_trade_day(spike, after):
    bars = uptrend_bars(spike=spike)
    bars += [(7823, 7823.5, 7818, 7819),          # 10:15 dip: low under 10:10's low (7821)
             (7819, 7825, 7818.5, 7824)]          # 10:20 confirm: closes above the dip's close
    return day(bars + after)


def test_long_setup_hits_target_at_2r():
    df = long_trade_day(spike=10, after=[(7824, 7830, 7822, 7829), (7829, 7837, 7828, 7836)])
    trades, _ = backtest(df, CMES4Params())
    t = trades.iloc[0]
    assert t["dir"] == 1 and t["entry"] == 7824 and t["stop"] == 7817.75
    assert t["risk_pts"] == pytest.approx(6.25)
    assert t["exit_reason"] == "target" and t["r_gross"] == pytest.approx(2.0)
    costs_r = (0.1 + 0.25) / 6.25                  # commission round trip + one tick entry slippage
    assert t["r_net"] == pytest.approx(2.0 - costs_r)


def test_room_to_peak_filter_skips_trade_like_d002():
    df = long_trade_day(spike=0, after=[(7824, 7830, 7822, 7829)])
    trades, skipped = backtest(df, CMES4Params())
    assert trades.empty
    assert "room-to-peak" in set(skipped["reason"])
    trades, _ = backtest(df, CMES4Params(room_min_r=0))
    assert len(trades) == 1


def test_setup_expires_without_a_bounce_like_d005():
    bars = downtrend_bars()
    o, h, l, c = bars[-1]
    bars += [(c, h - 1, c - 2, c - 1), (c - 1, h - 1, c - 3, c - 2), (c - 2, h - 1, c - 4, c - 3)]  # equal highs only
    trades, skipped = backtest(day(bars), CMES4Params(room_min_r=0))
    assert trades.empty
    assert skipped.iloc[0]["reason"] == "no pullback+confirm in window"


def test_bar_touching_stop_and_target_counts_as_stop():
    df = long_trade_day(spike=10, after=[(7824, 7840, 7815, 7830)])
    t = backtest(df, CMES4Params())[0].iloc[0]
    assert t["exit_reason"] == "stop"
    assert t["exit"] == pytest.approx(7817.75 - 0.25)


def test_time_limit_exits_at_market():
    df = long_trade_day(spike=10, after=[(7824, 7826, 7822, 7825)] * 14)
    t = backtest(df, CMES4Params(time_limit_bars=12))[0].iloc[0]
    assert t["exit_reason"] == "time"
    assert t["exit"] == pytest.approx(7825 - 0.25)


# ------------------------------------------------------------------ v2: stop entry, half at 2R, trailed runner

def test_v2_takes_half_at_2r_and_trails_the_rest():
    p = v2_params(windows=((time(10, 0), time(15, 30)),))
    bars = uptrend_bars(spike=10)
    bars += [(7823, 7823.5, 7818, 7819),          # 10:15 dip
             (7819, 7825, 7818.5, 7824),          # 10:20 confirm, high 7825 -> buy stop 7825.25
             (7824, 7826, 7823, 7826),            # 10:25 fills at 7825.25; risk = 7825.25 - 7817.75 = 7.5
             (7826, 7841, 7825, 7840),            # 10:30 high 7841 >= 2R (7840.25): half off, rest to breakeven
             (7840, 7850, 7839, 7849),
             (7849, 7860, 7848, 7859),
             (7859, 7866, 7857, 7865),
             (7865, 7870, 7862, 7868),
             (7868, 7869, 7860, 7861),            # trail now 1 tick under 7857 = 7856.75
             (7861, 7862, 7845, 7846)]            # falls through the trail: exit 7856.50
    t = backtest(day(bars), p)[0].iloc[0]
    assert t["entry"] == pytest.approx(7825.25) and t["risk_pts"] == pytest.approx(7.5)
    assert bool(t["partial"]) and t["exit_reason"] == "trail"
    runner_r = (t["exit"] - 7825.25) / 7.5
    assert runner_r > 2
    assert t["r_gross"] == pytest.approx(0.5 * 2.0 + 0.5 * runner_r)


def test_engine_has_no_edge_on_a_random_walk():
    df = synthetic_rth(days=150, seed=11)
    trades, _ = backtest(df, CMES4Params(time_limit_bars=None, room_min_r=0))
    hit = (trades["exit_reason"] == "target").mean()
    assert abs(hit - 1 / 3) < 0.05                # a 2R target before a 1R stop: 1/3 on a martingale
    assert abs(trades["r_gross"].mean()) < 0.15


# ------------------------------------------------------------------ ceiling maths

def test_per_trade_ceiling_matches_hand_calculation():
    assert per_trade_ceiling(7.0) == pytest.approx((7 * 50 - 5) / 28_600)


def test_contracts_are_capped_by_margin():
    assert contracts(1_000_000, 0.01, 4.0) == 34          # 1% would be 48 ES; margin allows 34
    assert contracts(1_000_000, 0.005, 4.0) == 24
    assert contracts(1_000_000, None, 4.0, fixed=5) == 5


def test_perfect_foresight_at_fixed_size_is_linear():
    b = perfect_foresight(1_000_000, 10, 4.0, fixed=5)
    assert b == pytest.approx(1_000_000 + 10 * 5 * (2 * 4 * 50 - 5))


def test_kelly_is_zero_without_edge():
    assert kelly_binary(1 / 3)[0] == pytest.approx(0.0, abs=1e-12)
    f, g = kelly_binary(0.5)
    assert f == pytest.approx(0.25) and g > 0


def test_simulation_respects_fixed_size_scale():
    out = simulate(Scenario("t", hit=1.0, setups_per_day=1.0, fixed=5, stop_pts_spread=0.0,
                            stop_pts_median=4.0), days=5, paths=500)
    one_trade = 5 * ((2 * 4 - 0.25) * 50 - 5) / 1_000_000
    assert out["p99"] < 15 * one_trade                 # Poisson(1) trades a day over 5 days
    assert out["median"] > 0


def test_v2_stops_for_the_day_after_two_losers():
    p = v2_params()
    assert p.max_trades_per_day == 3 and p.max_losses_per_day == 2
    df = synthetic_rth(days=200, seed=3)
    trades, _ = backtest(df, p)
    per_day = trades.groupby("date").agg(n=("r_net", "size"), losses=("r_net", lambda r: (r < 0).sum()))
    assert per_day["n"].max() <= 3
    assert per_day["losses"].max() <= 2
