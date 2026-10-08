"""Load 5-minute bars for the backtests.

Three sources, all returning RTH bars (09:30-16:00 ET) indexed by bar start time in
America/New_York, with columns open, high, low, close:

* ``load_yahoo``: ES=F / NQ=F from Yahoo Finance (about the last 60 days of 5m bars).
* ``load_csv``: any CSV export (CQG, TradingView, Barchart); pass the file's time zone.
* ``synthetic_rth``: a random walk with an intraday volatility smile.  It has no
  edge by construction, so it shows what CMES4 looks like when nothing is there.
"""

from __future__ import annotations

from datetime import time

import numpy as np
import pandas as pd

ET = "America/New_York"
RTH_OPEN, RTH_CLOSE = time(9, 30), time(16, 0)


def rth(df: pd.DataFrame) -> pd.DataFrame:
    t = df.index.time
    return df[(t >= RTH_OPEN) & (t < RTH_CLOSE)]


def load_yahoo(symbol: str = "ES=F", period: str = "60d", interval: str = "5m") -> pd.DataFrame:
    import yfinance as yf  # imported here so the rest works without it

    raw = yf.download(symbol, period=period, interval=interval, auto_adjust=False,
                      progress=False, prepost=True)
    if raw.empty:
        raise RuntimeError(f"Yahoo returned no data for {symbol}")
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    df = raw.rename(columns=str.lower)[["open", "high", "low", "close"]].dropna()
    df.index = df.index.tz_convert(ET) if df.index.tz is not None else df.index.tz_localize("UTC").tz_convert(ET)
    return rth(df)


def load_csv(path: str, tz: str = ET, time_col: str | None = None) -> pd.DataFrame:
    """Read a bar export.  Looks for a datetime column, or separate Date and Time columns."""
    df = pd.read_csv(path)
    cols = {c.lower().strip(): c for c in df.columns}
    if time_col:
        stamp = pd.to_datetime(df[time_col])
    elif "datetime" in cols:
        stamp = pd.to_datetime(df[cols["datetime"]])
    elif "date" in cols and "time" in cols:
        stamp = pd.to_datetime(df[cols["date"]].astype(str) + " " + df[cols["time"]].astype(str))
    else:
        stamp = pd.to_datetime(df[df.columns[0]])
    out = pd.DataFrame({k: pd.to_numeric(df[cols[k]]) for k in ("open", "high", "low", "close")})
    idx = pd.DatetimeIndex(stamp)
    out.index = (idx.tz_localize(tz) if idx.tz is None else idx).tz_convert(ET)
    return rth(out.sort_index())


def synthetic_rth(days: int = 60, end: str = "2026-10-02", price: float = 7850.0,
                  annual_vol: float = 0.13, seed: int = 0, trend_day_prob: float = 0.0,
                  trend_day_size: float = 1.0, tick: float = 0.25) -> pd.DataFrame:
    """Random-walk RTH 5m bars for ES-like prices.

    ``annual_vol`` sets close-to-close volatility; 85% of daily variance falls in RTH.
    Volatility follows a U-shape through the day and varies from day to day.
    Each bar's high and low are drawn from the exact distribution of a continuous
    random walk's extremes between its open and close (Brownian bridge), so stop
    orders are not filled at prices the path jumped over.
    ``trend_day_prob`` > 0 adds days with a steady drift of ``trend_day_size`` x the
    day's RTH standard deviation, to show what a trailing exit does on trend days.
    """
    rng = np.random.default_rng(seed)
    n_bars = 78
    i = np.arange(n_bars)
    m = 0.6 + 1.8 * np.exp(-i / 4) + 0.7 * np.exp(-(n_bars - 1 - i) / 5)
    m = m / np.sqrt(np.mean(m ** 2))
    dates = pd.bdate_range(end=end, periods=days)
    frames = []
    log_p = np.log(price)
    for day in dates:
        sd_day = annual_vol / np.sqrt(252) * np.exp(rng.normal(0, 0.35) - 0.35 ** 2 / 2)
        log_p += rng.normal(0, sd_day * np.sqrt(0.15))          # overnight gap
        sd_bar = sd_day * np.sqrt(0.85) * m / np.sqrt(n_bars)
        drift = np.zeros(n_bars)
        if trend_day_prob and rng.random() < trend_day_prob:
            drift[:] = rng.choice([-1, 1]) * trend_day_size * sd_day * np.sqrt(0.85) / n_bars
        steps = drift + sd_bar * rng.standard_normal(n_bars)
        c = log_p + np.cumsum(steps)
        o = np.concatenate([[log_p], c[:-1]])
        spread_hi = np.sqrt((c - o) ** 2 - 2 * sd_bar ** 2 * np.log(rng.random(n_bars)))
        spread_lo = np.sqrt((c - o) ** 2 - 2 * sd_bar ** 2 * np.log(rng.random(n_bars)))
        h, lo = (o + c + spread_hi) / 2, (o + c - spread_lo) / 2
        log_p = c[-1]
        idx = pd.date_range(pd.Timestamp.combine(day.date(), RTH_OPEN), periods=n_bars, freq="5min", tz=ET)
        frames.append(pd.DataFrame(np.exp(np.column_stack([o, h, lo, c])),
                                   columns=["open", "high", "low", "close"], index=idx))
    df = pd.concat(frames)
    df[["open", "close"]] = (df[["open", "close"]] / tick).round() * tick
    df["high"] = np.floor(df["high"] / tick) * tick     # highest tick the path actually reached
    df["low"] = np.ceil(df["low"] / tick) * tick
    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)
    return df
