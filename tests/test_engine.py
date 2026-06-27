"""State-machine engine tests (TDD, written before src/engine.py).

Each test builds a tiny synthetic OHLCV frame and drives one specific rule from
docs/SPEC.md §2.B. Highs/lows default to the close (no intrabar range) so True Range
reduces to |close - prev_close|, making ATR hand-predictable.
"""
import numpy as np
import pandas as pd
import pytest

import engine
from config import Params

BASE_TS = 1_600_000_000  # arbitrary fixed unix epoch (Date strings derived from it)
DAY = 86_400


def make_df(closes, highs=None, lows=None, volumes=None, opens=None, stock="TEST"):
    closes = [float(c) for c in closes]
    n = len(closes)
    highs = closes if highs is None else [float(h) for h in highs]
    lows = closes if lows is None else [float(x) for x in lows]
    volumes = [1_000_000.0] * n if volumes is None else [float(v) for v in volumes]
    dt = [BASE_TS + i * DAY for i in range(n)]
    date = [pd.to_datetime(ts, unit="s").strftime("%Y-%m-%d") for ts in dt]
    opens = closes[:] if opens is None else [float(o) for o in opens]  # defaults to close
    return pd.DataFrame(
        {"stock": stock, "DT": dt, "Date": date, "Open": opens,
         "Close": closes, "High": highs, "Low": lows, "Volume": volumes}
    )


def _p(**kw):
    """Params with test-friendly small windows. Entry needs a breakout, so the earliest a
    position can open is bar 1 (bar 0 has no prior close to break out over)."""
    base = dict(min_dollar_vol=0.0, ipo_min_days=1, atr_period=2,
                roll_window=2, dollar_vol_window=1)
    base.update(kw)
    return Params(**base)


def test_hard_stop_exit():
    df = make_df([99, 100, 94])           # bar1 breaks out over 99 -> enter @100; bar2 stops out
    trades = engine.run_symbol(df, _p(initial_cutloss_pct=0.05, breakeven_trigger_pct=0.06))
    assert len(trades) == 1
    t = trades[0]
    assert t["entry_price"] == pytest.approx(100.0)
    assert t["exit_price"] == pytest.approx(95.0)        # stop boundary, not the 94 close
    assert t["pnl_pct"] == pytest.approx(-5.0)
    assert t["exit_reason"] == "hard_stop"


def test_breakeven_lock_exit():
    # bar1 breaks out @100; price spikes to +7% (arms Rule 4 at +6%, locks stop at +1%), then falls back.
    df = make_df([99, 100, 107, 100], highs=[99, 100, 108, 101], lows=[99, 100, 103, 99])
    trades = engine.run_symbol(
        df, _p(initial_cutloss_pct=0.05, breakeven_trigger_pct=0.06, breakeven_lock_pct=0.01,
               atr_multiplier=2.5))
    assert len(trades) == 1
    t = trades[0]
    assert t["exit_price"] == pytest.approx(101.0)       # entry * (1 + lock)
    assert t["pnl_pct"] == pytest.approx(1.0)
    assert t["exit_reason"] == "breakeven_lock"


def test_atr_trailing_exit():
    # bar1 breaks out @100; gentle climb to 104 then pullback; ATR stays 1, trail = 104 - 2.5*1 = 101.5
    closes = [99, 100, 101, 102, 103, 104, 103, 102, 101]
    df = make_df(closes)
    trades = engine.run_symbol(
        df, _p(initial_cutloss_pct=0.05, breakeven_trigger_pct=0.50, atr_multiplier=2.5))
    assert len(trades) == 1
    t = trades[0]
    assert t["exit_reason"] == "atr_trail"
    assert t["exit_price"] == pytest.approx(101.5)
    assert t["pnl_pct"] == pytest.approx(1.5)


def test_liquidity_filter_blocks_entry():
    df = make_df([100, 101, 102], volumes=[1, 1, 1])     # dollar vol ~100 << threshold
    trades = engine.run_symbol(df, _p(min_dollar_vol=1_000_000.0))
    assert trades == []


def test_loss_freeze_blocks_then_allows_reentry():
    # bar1 breaks out @100; lose on bar 2 -> freeze bars 3,4 -> re-entry at bar 5 (frozen_until = 2 + 2 = 4).
    # bar4 would itself break out (92 >= max(91,90)) but is still frozen, proving the lockout holds.
    df = make_df([99, 100, 90, 91, 92, 93])
    trades = engine.run_symbol(
        df, _p(initial_cutloss_pct=0.05, breakeven_trigger_pct=0.50,
               freeze_days=2, force_close_at_end=True))
    assert len(trades) == 2
    assert trades[0]["entry_ts"] == BASE_TS + 1 * DAY
    assert trades[0]["pnl_pct"] < 0
    # second entry must be bar 5, NOT bar 3 or 4 (those were frozen)
    assert trades[1]["entry_ts"] == BASE_TS + 5 * DAY


def test_freeze_days_zero_allows_immediate_reentry():
    df = make_df([99, 100, 90, 100])                     # bar1 enter @100; bar2 stops out
    trades = engine.run_symbol(
        df, _p(initial_cutloss_pct=0.05, breakeven_trigger_pct=0.50,
               freeze_days=0, force_close_at_end=True))
    assert len(trades) == 2
    assert trades[1]["entry_ts"] == BASE_TS + 3 * DAY    # re-enters on the bar right after the loss-exit bar


def test_entry_requires_new_high():
    # declining then a new high on bar 3 -> entry only fires on the breakout bar, never on the
    # earlier (non-breakout) bars. Confirms the age floor alone does NOT open a position.
    closes = [100, 99, 98, 101]
    trades = engine.run_symbol(
        make_df(closes),
        _p(initial_cutloss_pct=0.99, breakeven_trigger_pct=0.99,
           ipo_min_days=2, force_close_at_end=True))
    assert len(trades) == 1
    assert trades[0]["entry_ts"] == BASE_TS + 3 * DAY


def test_entry_blocked_until_ipo_age_floor():
    # bar1 already breaks out (101 >= 100) but is too young; entry waits until the age floor is met.
    closes = [100, 101, 102, 103]
    trades = engine.run_symbol(
        make_df(closes),
        _p(initial_cutloss_pct=0.99, breakeven_trigger_pct=0.99,
           ipo_min_days=3, force_close_at_end=True))
    assert len(trades) == 1
    assert trades[0]["entry_ts"] == BASE_TS + 2 * DAY    # bar2 is the first bar with days_since_ipo >= 3


def test_pl_instance_records_completed_trade():
    from profitandloss_v3 import PL
    pl = PL("TEST", days_of_trading_per_year=252)
    df = make_df([99, 100, 94])           # bar1 breaks out @100; bar2 stops out at 95
    engine.run_symbol(df, _p(initial_cutloss_pct=0.05, breakeven_trigger_pct=0.06), pl=pl)
    n, total_pl_pct = pl.statistics()
    assert n == 1
    assert total_pl_pct == pytest.approx(-5.0)


def test_trace_records_per_bar_snapshots():
    # Same scenario as test_hard_stop_exit: enter @100 on bar 1, hard-stop @95 on bar 2.
    df = make_df([99, 100, 94])
    p = engine.prepare_symbol(df, atr_period=2, roll_window=2, dollar_vol_window=1)
    trace: list = []
    trades = engine.run_state_machine(
        p, _p(initial_cutloss_pct=0.05, breakeven_trigger_pct=0.06), trace=trace)

    assert len(trades) == 1 and trades[0]["exit_reason"] == "hard_stop"
    assert len(trace) == len(df) == 3           # exactly one snapshot per bar

    assert trace[0]["event"] == "" and trace[0]["in_position"] is False   # flat, no breakout yet
    assert trace[1]["event"] == "entry" and trace[1]["in_position"] is True
    assert trace[1]["entry_price"] == pytest.approx(100.0)
    assert trace[1]["dynamic_stop"] == pytest.approx(95.0)                # initial hard stop
    assert trace[2]["event"] == "exit" and trace[2]["exit_reason"] == "hard_stop"
    assert trace[2]["final_stop"] == pytest.approx(95.0)
    assert trace[2]["close"] == pytest.approx(94.0)


def test_trace_does_not_change_trades():
    # Tracing is observation-only: identical trades with and without a trace sink.
    df = make_df([99, 100, 90, 91, 92, 93])
    params = _p(initial_cutloss_pct=0.05, breakeven_trigger_pct=0.50,
                freeze_days=2, force_close_at_end=True)
    untraced = engine.run_symbol(df, params)
    p = engine.prepare_symbol(df, atr_period=2, roll_window=2, dollar_vol_window=1)
    sink: list = []
    traced = engine.run_state_machine(p, params, trace=sink)
    assert traced == untraced
    assert len(sink) == len(df)


def test_intrabar_stop_triggers_on_low_not_close():
    # bar1 enter @100, hard stop 95. bar2 CLOSES at 98 (above 95) but its LOW pierces to 94.
    df = make_df([99, 100, 98], highs=[99, 100, 101], lows=[99, 100, 94], opens=[99, 100, 98])
    # close-based (default): close 98 > 95 -> never stops out, position runs to the end, no trade.
    assert engine.run_symbol(df, _p(initial_cutloss_pct=0.05, breakeven_trigger_pct=0.50)) == []
    # intrabar: the low taps the stop -> exit; bar opened above the stop so it fills AT the stop.
    trades = engine.run_symbol(
        df, _p(initial_cutloss_pct=0.05, breakeven_trigger_pct=0.50, intrabar_stops=True))
    assert len(trades) == 1
    assert trades[0]["exit_reason"] == "hard_stop"
    assert trades[0]["exit_price"] == pytest.approx(95.0)
    assert trades[0]["pnl_pct"] == pytest.approx(-5.0)


def test_gap_through_fills_at_open_not_stop():
    # bar1 enter @100, hard stop 95. bar2 GAPS down: opens 92 (below the 95 stop), low 88.
    df = make_df([99, 100, 90], highs=[99, 100, 92], lows=[99, 100, 88], opens=[99, 100, 92])
    # close-based: optimistic fill exactly at the 95 stop.
    t_close = engine.run_symbol(df, _p(initial_cutloss_pct=0.05, breakeven_trigger_pct=0.50))
    assert t_close[0]["exit_price"] == pytest.approx(95.0)
    assert t_close[0]["pnl_pct"] == pytest.approx(-5.0)
    # intrabar: bar opened below the stop, so the realistic fill is the open (92) -> a bigger loss.
    t_real = engine.run_symbol(
        df, _p(initial_cutloss_pct=0.05, breakeven_trigger_pct=0.50, intrabar_stops=True))
    assert t_real[0]["exit_price"] == pytest.approx(92.0)
    assert t_real[0]["pnl_pct"] == pytest.approx(-8.0)
