"""Portfolio-metrics tests (TDD, before src/metrics.py and the two new PL methods).

Equity-curve metrics assume equal-weight, sequential compounding of per-trade returns
ordered by exit time (documented assumption — PRD doesn't specify portfolio construction).
"""
import math

import pytest

import metrics


def test_profit_factor_gains_over_losses():
    assert metrics.profit_factor([10, -5, 20, -15]) == pytest.approx(30 / 20)


def test_profit_factor_no_losses_is_inf():
    assert metrics.profit_factor([10, 5]) == math.inf


def test_win_rate_counts_strictly_positive():
    assert metrics.win_rate_pct([10, -5, 20, -15, 0]) == pytest.approx(40.0)


def test_net_profit_compounds_returns():
    assert metrics.net_profit_pct([10, -10]) == pytest.approx(-1.0)  # 1.1 * 0.9 - 1 = -0.01


def test_max_drawdown_is_peak_to_trough():
    # equity 1 -> 1.1 -> 0.88 -> 0.924 ; deepest dd = (0.88-1.1)/1.1 = -20%
    assert metrics.max_drawdown_pct([10, -20, 5]) == pytest.approx(-20.0)


def test_summarize_orders_by_exit_ts():
    trades = [
        {"pnl_pct": 10, "exit_ts": 200},
        {"pnl_pct": -20, "exit_ts": 300},
        {"pnl_pct": 5, "exit_ts": 100},
    ]
    s = metrics.summarize(trades)
    assert s["trade_count"] == 3
    assert s["win_rate_pct"] == pytest.approx(200 / 3)          # 2 of 3
    assert s["profit_factor"] == pytest.approx(15 / 20)         # gains 15, losses 20
    assert s["net_profit_pct"] == pytest.approx(-7.6)           # 1.05*1.10*0.80 - 1
    assert s["max_drawdown_pct"] == pytest.approx(-20.0)        # 0.924 vs peak 1.155


def test_summarize_empty():
    s = metrics.summarize([])
    assert s["trade_count"] == 0
    assert s["win_rate_pct"] == 0.0
    assert s["net_profit_pct"] == 0.0
    assert s["max_drawdown_pct"] == 0.0


def test_pl_profit_factor_and_max_drawdown():
    from profitandloss_v3 import PL
    pl = PL("X", days_of_trading_per_year=252)
    pl.addnew(1, 100, 1000, 1); pl.addnew(-1, 110, 2000, 1)   # +10
    pl.addnew(1, 100, 3000, 1); pl.addnew(-1, 90, 4000, 1)    # -10
    assert pl.profit_factor() == pytest.approx(1.0)            # gross 10 / 10
    assert pl.max_drawdown_pct() == pytest.approx(-10.0)       # 1.1 -> 0.99
