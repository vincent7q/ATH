"""Performance metrics for backtest output (docs/PRD.md §4).

The reported aggregate return is ``sum_return_pct`` — the equal-weight **sum** of per-trade returns.
That is the meaningful figure when trades overlap in time across many symbols; serially compounding
pooled trades (``net_profit_pct``) implies one position at a time funded by a single growing bankroll,
which has no economic interpretation here and balloons to absurd magnitudes. ``net_profit_pct`` is
kept as a utility but is no longer in the report. ``max_drawdown_pct`` is measured on the cumulative-
**sum** curve (consistent with ``sum_return_pct``); ``profit_factor`` and ``win_rate`` are order-independent.
"""
import math


def profit_factor(values) -> float:
    """Gross profit / gross loss over a list of signed P&L figures (any unit).

    Returns ``inf`` when there are gains but no losses, ``0.0`` when there are no gains.
    """
    gains = sum(v for v in values if v > 0)
    losses = -sum(v for v in values if v < 0)
    if losses == 0:
        return math.inf if gains > 0 else 0.0
    return gains / losses


def win_rate_pct(pnls) -> float:
    """Percentage of trades with strictly positive P&L."""
    if not pnls:
        return 0.0
    wins = sum(1 for v in pnls if v > 0)
    return wins / len(pnls) * 100.0


def net_profit_pct(pnl_pcts) -> float:
    """Net return (%) from sequentially compounding per-trade percentage returns.

    Kept as a utility; NOT used in the report — see module docstring and ``sum_return_pct``.
    """
    equity = 1.0
    for r in pnl_pcts:
        equity *= 1.0 + r / 100.0
    return (equity - 1.0) * 100.0


def sum_return_pct(pnl_pcts) -> float:
    """Sum of per-trade percentage returns — the equal-weight, non-reinvested aggregate.

    The economically meaningful total when trades overlap in time across many symbols (no serial
    reinvestment assumed). Order-independent.
    """
    return float(sum(pnl_pcts))


def max_drawdown_pct(pnl_pcts) -> float:
    """Deepest peak-to-trough drop on the cumulative-**sum** return curve, in percentage points (≤ 0.0).

    Consistent with ``sum_return_pct``: tracks the running sum of per-trade returns and reports the
    largest peak-to-trough decline in cumulative points (an additive curve, not a compounded ratio).
    """
    cum = 0.0
    peak = 0.0
    max_dd = 0.0
    for r in pnl_pcts:
        cum += r
        peak = max(peak, cum)
        max_dd = min(max_dd, cum - peak)
    return max_dd


def summarize(trades) -> dict:
    """Aggregate a list of trade dicts (each with ``pnl_pct`` and ``exit_ts``) into the
    output metrics. Trades are ordered by ``exit_ts`` for the order-dependent drawdown."""
    ordered = sorted(trades, key=lambda t: t["exit_ts"])
    pnls = [t["pnl_pct"] for t in ordered]
    return {
        "trade_count": len(pnls),
        "win_rate_pct": win_rate_pct(pnls),
        "sum_return_pct": sum_return_pct(pnls),
        "profit_factor": profit_factor(pnls),
        "max_drawdown_pct": max_drawdown_pct(pnls),
    }
