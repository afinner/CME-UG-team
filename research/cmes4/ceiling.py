"""How far can a strategy take the account by 30 October?  Ceilings and Monte Carlo.

Three ceilings, from hard to soft:

1. Per-trade ceiling at full margin.  If CQG charges ``margin`` per contract, the most
   contracts you can hold is balance / margin, so a perfect trade that captures
   ``points`` adds at most points x $/point / margin of the account, whatever the size.
2. Perfect-foresight ceiling: every setup wins its full target, compounded.
3. Realistic range: Monte Carlo over the remaining days, with the hit rate as the
   unknown.  The team's daily stop and CME's 20% one-day lockout are applied.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Contract:
    symbol: str
    point_value: float        # $ per 1.00 move
    margin: float             # $ per contract that CQG holds (check "Purchasing power" in CQG)
    commission_rt: float = 5.0  # $2.50 per side


ES = Contract("ES", 50.0, 28_600.0)      # TradeZero initial margin, 16 Sep 2026


def per_trade_ceiling(points: float, c: Contract = ES) -> float:
    """Largest account gain from one trade that captures ``points``, at full margin."""
    return (points * c.point_value - c.commission_rt) / c.margin


def contracts(balance: np.ndarray | float, risk_frac: float | None, stop_pts, c: Contract = ES,
              fixed: int | None = None, margin_cap: bool = True):
    """Contracts for a trade: fixed size, or risk_frac of balance at stop_pts; capped by margin."""
    balance = np.asarray(balance, dtype=float)
    stop_pts = np.asarray(stop_pts, dtype=float)
    if fixed is not None:
        n = np.full(np.broadcast(balance, stop_pts).shape, float(fixed))
    else:
        n = np.floor(balance * risk_frac / (stop_pts * c.point_value + c.commission_rt))
    if margin_cap:
        n = np.minimum(n, np.floor(balance / c.margin))
    return np.maximum(n, 0)


def perfect_foresight(balance: float, n_trades: int, stop_pts: float, target_r: float = 2.0,
                      c: Contract = ES, risk_frac: float | None = None, fixed: int | None = None,
                      margin_cap: bool = True) -> float:
    """Final balance if every one of n_trades wins target_r x the stop."""
    b = balance
    for _ in range(n_trades):
        n = float(contracts(b, risk_frac, stop_pts, c, fixed, margin_cap))
        b += n * (target_r * stop_pts * c.point_value - c.commission_rt)
    return b


def kelly_binary(hit: float, target_r: float = 2.0, cost_r: float = 0.0) -> tuple[float, float]:
    """Growth-optimal risk per trade and log growth per trade for a win/lose bracket."""
    win, loss = target_r - cost_r, 1.0 + cost_r
    f = max(0.0, (hit * win - (1 - hit) * loss) / (win * loss))
    g = hit * np.log1p(f * win) + (1 - hit) * np.log1p(-f * loss) if f > 0 else 0.0
    return f, g


@dataclass
class Scenario:
    name: str
    hit: float                   # share of trades that reach the target; the rest lose 1R
    setups_per_day: float
    risk_frac: float | None = None
    fixed: int | None = None
    target_r: float = 2.0
    stop_pts_median: float = 4.0
    stop_pts_spread: float = 0.35   # lognormal sigma of the stop distance
    slip_entry_pts: float = 0.25    # one tick on the entry
    slip_stop_pts: float = 0.25     # one tick more when the stop fills
    daily_stop_frac: float | None = 0.03
    margin_cap: bool = True


def simulate(s: Scenario, balance0: float = 1_000_000.0, days: int = 16, paths: int = 20_000,
             c: Contract = ES, lockout_frac: float = 0.20, seed: int = 0) -> dict:
    """Monte Carlo of the rest of the challenge.  Trades are independent; intraday only."""
    rng = np.random.default_rng(seed)
    b = np.full(paths, balance0)
    peak = b.copy()
    max_dd = np.zeros(paths)
    locked_days = np.zeros(paths)
    for _ in range(days):
        start = b.copy()
        k = rng.poisson(s.setups_per_day, paths)
        stopped = np.zeros(paths, bool)
        for t in range(int(k.max()) if k.size else 0):
            live = (k > t) & ~stopped
            if not live.any():
                break
            stop = s.stop_pts_median * np.exp(rng.normal(0, s.stop_pts_spread, paths))
            stop = np.maximum(0.25, np.round(stop * 4) / 4)
            n = contracts(b, s.risk_frac, stop, c, s.fixed, s.margin_cap)
            win = rng.random(paths) < s.hit
            r = np.where(win, s.target_r, -1.0)
            pts = r * stop - s.slip_entry_pts - np.where(win, 0.0, s.slip_stop_pts)
            pnl = n * (pts * c.point_value - c.commission_rt)
            b = np.where(live, b + pnl, b)
            day_ret = b / start - 1
            if s.daily_stop_frac is not None:
                stopped |= day_ret <= -s.daily_stop_frac
            lock = day_ret <= -lockout_frac
            stopped |= lock
            locked_days += lock & live
            peak = np.maximum(peak, b)
            max_dd = np.maximum(max_dd, 1 - b / peak)
    ret = b / balance0 - 1
    return {
        "scenario": s.name,
        "median": float(np.median(ret)),
        "p10": float(np.quantile(ret, 0.10)),
        "p90": float(np.quantile(ret, 0.90)),
        "p99": float(np.quantile(ret, 0.99)),
        "p_up_30": float(np.mean(ret >= 0.297)),
        "p_up_218": float(np.mean(ret >= 2.18)),
        "p_down_10": float(np.mean(ret <= -0.10)),
        "median_max_dd": float(np.median(max_dd)),
        "p_lockout_day": float(np.mean(locked_days > 0)),
    }


# --------------------------------------------------------------------------- empirical trades

def tilt(r: np.ndarray, target_mean: float) -> np.ndarray:
    """Probabilities that keep the empirical R values but move their mean to target_mean.

    Exponential tilting: weight each trade by exp(theta * R).  Used to ask "what if the
    real edge were +0.2R a trade?" while keeping the shape of the trade distribution.
    """
    r = np.asarray(r, float)
    if not r.min() < target_mean < r.max():
        raise ValueError("target mean outside the range of the trades")
    lo, hi = -50.0, 50.0
    for _ in range(200):
        th = (lo + hi) / 2
        w = np.exp(th * (r - r.max()))
        m = (w * r).sum() / w.sum()
        lo, hi = (th, hi) if m < target_mean else (lo, th)
    return w / w.sum()


def simulate_trades(r_net: np.ndarray, risk_pts: np.ndarray, per_day: float, *,
                    risk_frac: float | None = None, fixed: int | None = None, mean_r: float | None = None,
                    balance0: float = 1_000_000.0, days: int = 16, paths: int = 20_000, c: Contract = ES,
                    daily_stop_frac: float | None = 0.02, max_per_day: int = 3, lockout_frac: float = 0.20,
                    margin_cap: bool = True, seed: int = 0) -> dict:
    """Monte Carlo drawing whole trades (R net of costs, stop in points) from a backtest."""
    rng = np.random.default_rng(seed)
    r_net, risk_pts = np.asarray(r_net, float), np.asarray(risk_pts, float)
    prob = tilt(r_net, mean_r) if mean_r is not None else np.full(len(r_net), 1 / len(r_net))
    b = np.full(paths, balance0)
    peak, max_dd = b.copy(), np.zeros(paths)
    for _ in range(days):
        start = b.copy()
        k = np.minimum(rng.poisson(per_day, paths), max_per_day)
        stopped = np.zeros(paths, bool)
        for t in range(max_per_day):
            live = (k > t) & ~stopped
            if not live.any():
                break
            i = rng.choice(len(r_net), paths, p=prob)
            n = contracts(b, risk_frac, risk_pts[i], c, fixed, margin_cap)
            b = np.where(live, b + n * r_net[i] * risk_pts[i] * c.point_value, b)
            day_ret = b / start - 1
            if daily_stop_frac is not None:
                stopped |= day_ret <= -daily_stop_frac
            stopped |= day_ret <= -lockout_frac
            peak = np.maximum(peak, b)
            max_dd = np.maximum(max_dd, 1 - b / peak)
    ret = b / balance0 - 1
    return {
        "median": float(np.median(ret)), "p10": float(np.quantile(ret, 0.10)),
        "p90": float(np.quantile(ret, 0.90)), "p99": float(np.quantile(ret, 0.99)),
        "p_up_30": float(np.mean(ret >= 0.297)), "p_up_218": float(np.mean(ret >= 2.18)),
        "p_down_10": float(np.mean(ret <= -0.10)), "median_max_dd": float(np.median(max_dd)),
    }


# --------------------------------------------------------------------------- the top-5 question

def best_shot(target_ret: float, days: int = 16, sharpe: float = 1.0,
              daily_vols=np.linspace(0.005, 0.40, 400)) -> dict:
    """Best achievable chance of finishing above target_ret, for a strategy with this annual Sharpe.

    Log-normal approximation: pick the daily volatility (leverage) that maximises
    P(final >= 1 + target_ret).  Reports that volatility and the chance of losing half.
    """
    from math import erf, log, sqrt

    def tail(z):
        return 0.5 * (1 - erf(z / sqrt(2)))

    best = None
    for s in daily_vols:
        mu = sharpe / sqrt(252) * s * days - 0.5 * s * s * days
        sd = s * sqrt(days)
        p = tail((log(1 + target_ret) - mu) / sd)
        if best is None or p > best["p_target"]:
            best = {"daily_vol": float(s), "p_target": p,
                    "p_lose_half": 1 - tail((log(0.5) - mu) / sd)}
    return best


def orb_trade_sample(edge: float = 0.15, n: int = 200_000, seed: int = 1) -> np.ndarray:
    """R outcomes in the WTI playbook's own trade model (its 'modest edge' simulation).

    47% stopped at -1R, 15% scratched at breakeven, 3% gap through the stop to -2.5R;
    the remaining 35% exit at 14:25 ET with an exponential R whose mean sets the edge.
    """
    rng = np.random.default_rng(seed)
    mean_rest = (edge + 0.47 + 0.075) / 0.35
    u = rng.random(n)
    r = np.where(u < 0.47, -1.0, np.where(u < 0.62, 0.0, np.where(u < 0.65, -2.5, 0.0)))
    rest = u >= 0.65
    r[rest] = rng.exponential(mean_rest, rest.sum())
    return r
