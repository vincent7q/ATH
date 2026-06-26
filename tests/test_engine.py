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


def make_df(closes, highs=None, lows=None, volumes=None, stock="TEST"):
    closes = [float(c) for c in closes]
    n = len(closes)
    highs = closes if highs is None else [float(h) for h in highs]
    lows = closes if lows is None else [float(x) for x in lows]
    volumes = [1_000_000.0] * n if volumes is None else [float(v) for v in volumes]
    dt = [BASE_TS + i * DAY for i in range(n)]
    date = [pd.to_datetime(ts, unit="s").strftime("%Y-%m-%d") for ts in dt]
    opens = closes[:]  # open == close; immaterial to the close-driven engine
    return pd.DataFrame(
        {"stock": stock, "DT": dt, "Date": date, "Open": opens,
         "Close": closes, "High": highs, "Low": lows, "Volume": volumes}
    )


def _p(**kw):
    """Params with test-friendly small windows so positions open on bar 0."""
    base = dict(min_dollar_vol=0.0, ipo_min_days=1, atr_period=2,
                roll_window=2, dollar_vol_window=1, entry_mode="literal")
    base.update(kw)
    return Params(**base)


def test_hard_stop_exit():
    df = make_df([100, 94])
    trades = engine.run_symbol(df, _p(initial_cutloss_pct=0.05, breakeven_trigger_pct=0.06))
    assert len(trades) == 1
    t = trades[0]
    assert t["entry_price"] == pytest.approx(100.0)
    assert t["exit_price"] == pytest.approx(95.0)        # stop boundary, not the 94 close
    assert t["pnl_pct"] == pytest.approx(-5.0)
    assert t["exit_reason"] == "hard_stop"


def test_breakeven_lock_exit():
    # price spikes to +7% (arms Rule 4 at +6%, locks stop at +1%), then falls back.
    df = make_df([100, 107, 100], highs=[100, 108, 101], lows=[100, 103, 99])
    trades = engine.run_symbol(
        df, _p(initial_cutloss_pct=0.05, breakeven_trigger_pct=0.06, breakeven_lock_pct=0.01,
               atr_multiplier=2.5))
    assert len(trades) == 1
    t = trades[0]
    assert t["exit_price"] == pytest.approx(101.0)       # entry * (1 + lock)
    assert t["pnl_pct"] == pytest.approx(1.0)
    assert t["exit_reason"] == "breakeven_lock"


def test_atr_trailing_exit():
    # gentle climb to 104 then pullback; ATR stays 1 (steps of 1), trail = 104 - 2.5*1 = 101.5
    closes = [100, 101, 102, 103, 104, 103, 102, 101]
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
    # lose on bar 1 -> freeze bars 2,3 -> re-entry allowed at bar 4 (frozen_until = 1 + 2 = 3)
    df = make_df([100, 90, 100, 100, 100, 100])
    trades = engine.run_symbol(
        df, _p(initial_cutloss_pct=0.05, breakeven_trigger_pct=0.50,
               freeze_days=2, force_close_at_end=True))
    assert len(trades) == 2
    assert trades[0]["entry_ts"] == BASE_TS + 0 * DAY
    assert trades[0]["pnl_pct"] < 0
    # second entry must be bar 4, NOT bar 2 or 3 (those were frozen)
    assert trades[1]["entry_ts"] == BASE_TS + 4 * DAY


def test_freeze_days_zero_allows_immediate_reentry():
    df = make_df([100, 90, 100, 100])
    trades = engine.run_symbol(
        df, _p(initial_cutloss_pct=0.05, breakeven_trigger_pct=0.50,
               freeze_days=0, force_close_at_end=True))
    assert len(trades) == 2
    assert trades[1]["entry_ts"] == BASE_TS + 2 * DAY    # re-enters immediately after the loss bar


def test_literal_vs_momentum_entry_timing_differs():
    # declining then a new high on bar 3. Literal: age clause enters early (bar 1).
    # Momentum: needs close >= prior all-time high -> only bar 3.
    closes = [100, 99, 98, 101]
    common = dict(initial_cutloss_pct=0.99, breakeven_trigger_pct=0.99,
                  ipo_min_days=2, force_close_at_end=True)
    lit = engine.run_symbol(make_df(closes), _p(entry_mode="literal", **common))
    mom = engine.run_symbol(make_df(closes), _p(entry_mode="momentum", **common))
    assert lit[0]["entry_ts"] == BASE_TS + 1 * DAY
    assert mom[0]["entry_ts"] == BASE_TS + 3 * DAY


def test_pl_instance_records_completed_trade():
    from profitandloss_v3 import PL
    pl = PL("TEST", days_of_trading_per_year=252)
    df = make_df([100, 94])
    engine.run_symbol(df, _p(initial_cutloss_pct=0.05, breakeven_trigger_pct=0.06), pl=pl)
    n, total_pl_pct = pl.statistics()
    assert n == 1
    assert total_pl_pct == pytest.approx(-5.0)
