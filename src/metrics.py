"""Performance metrics for backtest output (docs/PRD.md §4).

Equity-curve metrics (net profit, max drawdown) assume **equal-weight, sequentially compounded**
per-trade returns ordered by exit time. The PRD does not specify portfolio construction; this is
the documented simplifying assumption. Profit factor and win rate are order-independent.
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
    """Net return (%) from sequentially compounding per-trade percentage returns."""
    equity = 1.0
    for r in pnl_pcts:
        equity *= 1.0 + r / 100.0
    return (equity - 1.0) * 100.0


def max_drawdown_pct(pnl_pcts) -> float:
    """Deepest peak-to-trough decline (%) on the compounded equity curve. Returns ≤ 0.0."""
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for r in pnl_pcts:
        equity *= 1.0 + r / 100.0
        peak = max(peak, equity)
        max_dd = min(max_dd, (equity - peak) / peak * 100.0)
    return max_dd


def summarize(trades) -> dict:
    """Aggregate a list of trade dicts (each with ``pnl_pct`` and ``exit_ts``) into the
    five PRD output metrics. Trades are ordered by ``exit_ts`` before compounding."""
    ordered = sorted(trades, key=lambda t: t["exit_ts"])
    pnls = [t["pnl_pct"] for t in ordered]
    return {
        "trade_count": len(pnls),
        "win_rate_pct": win_rate_pct(pnls),
        "net_profit_pct": net_profit_pct(pnls),
        "profit_factor": profit_factor(pnls),
        "max_drawdown_pct": max_drawdown_pct(pnls),
    }
