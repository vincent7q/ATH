"""Backtest execution engine — the per-symbol state machine of docs/SPEC.md §2.B.

Indicators are pre-computed once per symbol (``prepare_symbol``) and reused across every
parameter-sweep combination; only the cheap state-machine pass (``run_state_machine``) re-runs
per combo. Completed trades are returned as plain dicts and, optionally, recorded into a
per-symbol ``PL`` accounting instance.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

import indicators
from config import Params


@dataclass
class Prepared:
    """Param-independent per-symbol arrays (indicator windows are fixed, not swept)."""
    symbol: str
    dt: np.ndarray
    date: np.ndarray
    close: np.ndarray
    open: np.ndarray                 # exit-bar open, for realistic gap-through fills (intrabar_stops)
    low: np.ndarray                  # exit-bar low, for intrabar stop triggers (intrabar_stops)
    atr: np.ndarray
    advol: np.ndarray
    ipo: np.ndarray
    roll_max: np.ndarray             # 52-week high over available history (breakout reference)


def prepare_symbol(df: pd.DataFrame, atr_period: int = 14, roll_window: int = 252,
                   dollar_vol_window: int = 5) -> Prepared:
    """Compute the four indicator vectors for one symbol. Expects ``df`` sorted by DT ascending
    with columns ``stock, DT, Date, Open, Close, High, Low, Volume``."""
    close = df["Close"]
    n = len(df)
    return Prepared(
        symbol=str(df["stock"].iloc[0]) if n else "",
        dt=df["DT"].to_numpy(dtype=np.int64),
        date=df["Date"].to_numpy(),
        close=close.to_numpy(dtype=float),
        open=df["Open"].to_numpy(dtype=float),
        low=df["Low"].to_numpy(dtype=float),
        atr=indicators.atr_wilder(df["High"], df["Low"], close, atr_period).to_numpy(dtype=float),
        advol=indicators.avg_dollar_volume(close, df["Volume"], dollar_vol_window).to_numpy(dtype=float),
        ipo=indicators.days_since_ipo(n),
        roll_max=indicators.rolling_high(close, roll_window, 1).to_numpy(dtype=float),
    )


def _entry_signal(t: int, p: Prepared, params: Params) -> bool:
    """Entry gate (docs/SPEC.md §2.B / PRD §2): liquidity AND breakout AND IPO-age floor.

    All three conditions must hold. NaN comparisons evaluate False, so a young stock without a
    valid breakout reference cannot enter.
    """
    return bool(
        p.advol[t] > params.min_dollar_vol          # liquidity filter (strict >)
        and p.close[t] >= p.roll_max[t]             # breakout to the 52-week high
        and p.ipo[t] >= params.ipo_min_days         # past the young-IPO age floor
    )


def _exit_reason(dynamic_stop: float, atr_stop: float, entry_price: float) -> str:
    if atr_stop > dynamic_stop:
        return "atr_trail"
    if dynamic_stop >= entry_price:
        return "breakeven_lock"
    return "hard_stop"


def run_state_machine(p: Prepared, params: Params, pl=None, trace: list | None = None) -> list[dict]:
    """Run the daily loop over a prepared symbol. Returns a list of completed-trade dicts.

    If ``pl`` is given, each trade is also booked via ``pl.addnew(+1, entry)`` /
    ``pl.addnew(-1, exit)`` (unit = 1), so the existing accounting layer can produce its stats.

    If ``trace`` is a list, one per-bar state snapshot dict is appended to it for every bar
    (close, 52-week high, ATR, dollar volume, the live stop levels, and any entry/exit event).
    This is **off by default** (``trace=None``) so the parameter sweep pays no cost; it exists for
    single-symbol troubleshooting via ``src/analyze.py``.
    """
    close, atr, dt, date = p.close, p.atr, p.dt, p.date
    low, open_ = p.low, p.open
    n = len(close)
    record_trace = trace is not None

    trades: list[dict] = []
    in_position = False
    entry_price = peak_price = dynamic_stop = 0.0
    entry_i = -1
    frozen_until = -1

    def _record(exit_i: int, exit_price: float, reason: str) -> None:
        if pl is not None:
            pl.addnew(-1, float(exit_price), int(dt[exit_i]), 1.0)
        trades.append({
            "symbol": p.symbol,
            "entry_ts": int(dt[entry_i]), "entry_date": str(date[entry_i]),
            "exit_ts": int(dt[exit_i]), "exit_date": str(date[exit_i]),
            "entry_price": float(entry_price), "exit_price": float(exit_price),
            "pnl_pct": (exit_price - entry_price) / entry_price * 100.0,
            "holding_bars": exit_i - entry_i,
            "exit_reason": reason,
        })

    nan = float("nan")

    def _snap(t: int, event: str, dyn: float, atrs: float, finals: float, reason: str) -> None:
        held = in_position
        trace.append({
            "i": t, "ts": int(dt[t]), "date": str(date[t]),
            "close": float(close[t]),
            "roll_max": float(p.roll_max[t]),
            "atr": float(atr[t]),
            "advol": float(p.advol[t]),
            "in_position": held,
            "entry_price": float(entry_price) if held else nan,
            "peak_price": float(peak_price) if held else nan,
            "dynamic_stop": dyn, "atr_stop": atrs, "final_stop": finals,
            "event": event, "exit_reason": reason,
        })

    for t in range(n):
        if not in_position:
            if t > frozen_until and _entry_signal(t, p, params):
                in_position = True
                entry_price = close[t]
                peak_price = close[t]
                dynamic_stop = entry_price * (1.0 - params.initial_cutloss_pct)
                entry_i = t
                if pl is not None:
                    pl.addnew(1, float(entry_price), int(dt[t]), 1.0)
                if record_trace:
                    _snap(t, "entry", dynamic_stop, nan, nan, "")
            elif record_trace:
                _snap(t, "", nan, nan, nan, "")
            continue

        # in position
        if params.intrabar_stops:
            # Realistic exits (A1+A2). The stop carried into this bar uses the trail/lock as of the
            # PRIOR bars; the bar's Low triggers it and a gap-down fills at the Open. The trail/lock
            # only roll forward on today's close, AFTER the intraday check — no same-bar look-ahead.
            atr_t = atr[t]
            atr_stop = -np.inf if np.isnan(atr_t) else peak_price - params.atr_multiplier * atr_t
            final_stop = max(dynamic_stop, atr_stop)
            atr_disp = nan if np.isinf(atr_stop) else atr_stop
            if low[t] <= final_stop:                         # the bar's low pierced the stop (A2)
                reason = _exit_reason(dynamic_stop, atr_stop, entry_price)
                fill_price = min(final_stop, open_[t])       # gap-down opens fill at the open (A1)
                _record(t, fill_price, reason)
                if record_trace:
                    _snap(t, "exit", dynamic_stop, atr_disp, final_stop, reason)
                in_position = False
                if fill_price < entry_price:                 # losing exit -> cooldown
                    frozen_until = t + params.freeze_days
            else:
                if record_trace:
                    _snap(t, "", dynamic_stop, atr_disp, final_stop, "")
                if close[t] > peak_price:                    # roll the trail/lock forward for tomorrow
                    peak_price = close[t]
                if close[t] >= entry_price * (1.0 + params.breakeven_trigger_pct):
                    dynamic_stop = max(dynamic_stop, entry_price * (1.0 + params.breakeven_lock_pct))
            continue

        # close-confirmed exits (original semantics)
        if close[t] > peak_price:
            peak_price = close[t]
        if close[t] >= entry_price * (1.0 + params.breakeven_trigger_pct):
            dynamic_stop = max(dynamic_stop, entry_price * (1.0 + params.breakeven_lock_pct))

        atr_t = atr[t]
        atr_stop = -np.inf if np.isnan(atr_t) else peak_price - params.atr_multiplier * atr_t
        final_stop = max(dynamic_stop, atr_stop)
        atr_disp = nan if np.isinf(atr_stop) else atr_stop

        if close[t] <= final_stop:
            reason = _exit_reason(dynamic_stop, atr_stop, entry_price)
            _record(t, final_stop, reason)
            if record_trace:
                _snap(t, "exit", dynamic_stop, atr_disp, final_stop, reason)
            in_position = False
            if final_stop < entry_price:                    # losing exit -> cooldown
                frozen_until = t + params.freeze_days
        elif record_trace:
            _snap(t, "", dynamic_stop, atr_disp, final_stop, "")

    if in_position and params.force_close_at_end and n:
        last = n - 1
        exit_price = close[last]
        if pl is not None:
            pl.forcetoclosetrade(float(exit_price), int(dt[last]))
        # forcetoclosetrade already booked into pl; record the dict without double-booking
        trades.append({
            "symbol": p.symbol,
            "entry_ts": int(dt[entry_i]), "entry_date": str(date[entry_i]),
            "exit_ts": int(dt[last]), "exit_date": str(date[last]),
            "entry_price": float(entry_price), "exit_price": float(exit_price),
            "pnl_pct": (exit_price - entry_price) / entry_price * 100.0,
            "holding_bars": last - entry_i,
            "exit_reason": "force_close",
        })

    return trades


def run_symbol(df: pd.DataFrame, params: Params, pl=None) -> list[dict]:
    """Convenience: prepare indicators and run the state machine for one symbol DataFrame."""
    p = prepare_symbol(df, params.atr_period, params.roll_window, params.dollar_vol_window)
    return run_state_machine(p, params, pl=pl)
