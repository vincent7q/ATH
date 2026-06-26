"""Pre-computed indicator vectors for the ATH momentum backtest (docs/SPEC.md §2.A).

Each function is pure and operates on a single symbol's price series. They are computed
once per symbol and reused across every parameter-sweep combination.
"""
import numpy as np
import pandas as pd


def rolling_high(close: pd.Series, window: int = 252, min_periods: int | None = None) -> pd.Series:
    """52-week rolling high: ``Roll_Max_t = max(C_{t-1} … C_{t-window})``.

    Excludes today's close (``shift(1)``). With the default ``min_periods == window`` the
    result is NaN until a full ``window`` of prior closes exists (literal SPEC). Pass a smaller
    ``min_periods`` (e.g. 1) to take the max over *available* history — used by the
    "momentum" entry mode so young IPOs have a valid breakout reference.
    """
    if min_periods is None:
        min_periods = window
    return close.shift(1).rolling(window, min_periods=min_periods).max()


def atr_wilder(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range via Wilder's smoothing (docs/SPEC.md §2.A.2).

    ``TR_t = max(H_t - L_t, |H_t - C_{t-1}|, |L_t - C_{t-1}|)``; the first ATR is seeded with
    the simple mean of the first ``period`` true ranges, then ratcheted by Wilder's recurrence
    ``ATR_t = (ATR_{t-1}*(period-1) + TR_t) / period``. (SPEC also permits a simple ``period``-bar
    average; Wilder is the convention for volatility trailing stops.)
    """
    h = np.asarray(high, dtype=float)
    low_ = np.asarray(low, dtype=float)
    c = np.asarray(close, dtype=float)
    n = len(c)
    tr = np.full(n, np.nan)
    for t in range(1, n):
        tr[t] = max(h[t] - low_[t], abs(h[t] - c[t - 1]), abs(low_[t] - c[t - 1]))

    atr = np.full(n, np.nan)
    if n > period:
        atr[period] = np.nanmean(tr[1:period + 1])  # TR is valid from index 1
        for t in range(period + 1, n):
            atr[t] = (atr[t - 1] * (period - 1) + tr[t]) / period
    return pd.Series(atr, index=close.index)


def avg_dollar_volume(close: pd.Series, volume: pd.Series, window: int = 5) -> pd.Series:
    """5-day average dollar volume: trailing ``window``-bar mean of ``Close * Volume`` (incl. today)."""
    return (close * volume).rolling(window, min_periods=window).mean()


def days_since_ipo(n: int) -> np.ndarray:
    """1-based cumulative bar count per symbol: ``[1, 2, …, n]`` (lifetime trading-day age)."""
    return np.arange(1, n + 1)
