"""Single-stock troubleshooting tool — NOT part of the parameter sweep.

Drill into ONE symbol under ONE parameter combination: replay the exact engine state machine
(via its default-off ``trace`` hook), dump per-trade and per-bar detail to CSV, and render an
interactive Plotly chart (price, 52-week high, live stop levels, entry/exit markers, dollar-volume
liquidity gate, and this stock's own compounded-vs-summed equity curve).

Why this exists: the sweep originally compounded every trade from every stock into one sequence,
ballooning to absurd magnitudes (the report now sums per-trade returns instead — metrics.sum_return_pct).
This tool lets you confirm, one stock at a time, that the *per-trade* returns are sane — isolating
behaviour to the entry/exit logic. It deliberately runs for a single (symbol, combo); running it
across the whole universe would defeat the purpose (and take forever).

Edit the PARAMETERS block below, then run:  python src/analyze.py
"""
import os

import db
import engine
from config import Params

# ============================================================================
# PARAMETERS — edit these, then run:  python src/analyze.py
# ============================================================================

SYMBOL = "6990.HK"                                                    # ticker to analyse
DB_PATH = os.path.join(os.path.dirname(__file__), "ipo.db")       # price database
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "analysis")  # artifact folder
OPEN_BROWSER = True                                               # auto-open the chart when done

# One parameter combination (the same fields the sweep varies, plus fixed windows).
PARAMS = Params(
    initial_cutloss_pct=0.05,
    breakeven_trigger_pct=0.06,
    breakeven_lock_pct=0.01,
    atr_multiplier=2.5,
    min_dollar_vol=1_000_000.0,
    freeze_days=0,
    force_close_at_end=True,   # mark a still-open position to market so it shows on the chart
    intrabar_stops=True,       # realistic exits (bar Low trigger, fill at min(stop, Open)) — match the sweep
)

# ============================================================================

_REASON_COLORS = {
    "hard_stop": "#d62728",       # red    — stopped below entry
    "breakeven_lock": "#1f77b4",  # blue   — Rule 4 lock
    "atr_trail": "#ff7f0e",       # orange — trailing stop
    "force_close": "#7f7f7f",     # grey   — marked to market at last bar
}


def analyze(symbol: str, params: Params, db_path: str):
    """Replay one symbol+combo. Returns (trades, trace_df). Raises ValueError if no data."""
    import pandas as pd

    conn = db.connect(db_path)
    try:
        bars = db.load_symbol(conn, symbol)
    finally:
        conn.close()
    if len(bars) == 0:
        raise ValueError(f"No price bars for {symbol!r} in {db_path}")

    prepared = engine.prepare_symbol(
        bars, params.atr_period, params.roll_window, params.dollar_vol_window)
    trace: list = []
    trades = engine.run_state_machine(prepared, params, trace=trace)
    trace_df = pd.DataFrame(trace)
    trace_df["date"] = pd.to_datetime(trace_df["date"])
    return trades, trace_df


def _ordered_pnls(trades):
    """Per-trade returns (%) ordered by exit time — the same ordering metrics.summarize uses."""
    return [t["pnl_pct"] for t in sorted(trades, key=lambda t: t["exit_ts"])]


def summarize(trades) -> dict:
    """Single-stock summary contrasting compounded vs summed returns (the crux of the bug)."""
    pnls = _ordered_pnls(trades)
    n = len(pnls)
    equity = 1.0
    for r in pnls:
        equity *= 1.0 + r / 100.0
    return {
        "n_trades": n,
        "win_rate_pct": (sum(1 for r in pnls if r > 0) / n * 100.0) if n else 0.0,
        "compounded_pct": (equity - 1.0) * 100.0,
        "summed_pct": sum(pnls),
        "avg_pct": (sum(pnls) / n) if n else 0.0,
    }


def write_details(symbol: str, trades, trace_df, out_dir: str) -> dict:
    """Write per-trade and per-bar CSVs. Returns the paths written."""
    import pandas as pd

    os.makedirs(out_dir, exist_ok=True)
    trades_path = os.path.join(out_dir, f"analysis_{symbol}_trades.csv")
    trace_path = os.path.join(out_dir, f"analysis_{symbol}_trace.csv")

    if trades:
        td = pd.DataFrame(sorted(trades, key=lambda t: t["exit_ts"]))
        eq, cum = 1.0, []
        for r in td["pnl_pct"]:
            eq *= 1.0 + r / 100.0
            cum.append((eq - 1.0) * 100.0)
        td["cum_compounded_pct"] = cum
        td.to_csv(trades_path, index=False)
    else:
        pd.DataFrame().to_csv(trades_path, index=False)

    trace_df.to_csv(trace_path, index=False)
    return {"trades": trades_path, "trace": trace_path}


def build_figure(symbol: str, params: Params, trades, trace_df):
    """Build the interactive Plotly figure (price + stops + markers / liquidity / equity)."""
    import pandas as pd
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    s = summarize(trades)
    title = (
        f"{symbol} — cutloss {params.initial_cutloss_pct:.0%}, "
        f"BE {params.breakeven_trigger_pct:.0%}/{params.breakeven_lock_pct:.0%}, "
        f"ATR×{params.atr_multiplier:g}, minDV {params.min_dollar_vol:,.0f}, "
        f"freeze {params.freeze_days}d  |  {s['n_trades']} trades, "
        f"win {s['win_rate_pct']:.0f}%, compounded {s['compounded_pct']:,.1f}% "
        f"vs summed {s['summed_pct']:,.1f}%"
    )

    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.04,
        row_heights=[0.58, 0.20, 0.22],
        subplot_titles=("Price · 52-wk high · stops · entries/exits",
                        "Dollar volume vs liquidity gate",
                        "This stock's equity: compounded vs summed"),
    )

    x = trace_df["date"]
    # --- Row 1: price, 52-week high, the live final stop, and the stop components ---
    fig.add_trace(go.Scatter(x=x, y=trace_df["close"], name="close",
                             line=dict(color="#111", width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=trace_df["roll_max"], name="52-wk high",
                             line=dict(color="#9467bd", width=1, dash="dot")), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=trace_df["final_stop"], name="stop (final)",
                             line=dict(color="#d62728", width=1.2), connectgaps=False),
                  row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=trace_df["atr_stop"], name="ATR stop",
                             line=dict(color="#ff7f0e", width=0.8, dash="dash"),
                             connectgaps=False, visible="legendonly"), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=trace_df["dynamic_stop"], name="hard/BE stop",
                             line=dict(color="#2ca02c", width=0.8, dash="dash"),
                             connectgaps=False, visible="legendonly"), row=1, col=1)

    # entry/exit markers come from the authoritative trade list (includes force_close fills)
    if trades:
        ents = sorted(trades, key=lambda t: t["entry_ts"])
        fig.add_trace(go.Scatter(
            x=pd.to_datetime([t["entry_date"] for t in ents]),
            y=[t["entry_price"] for t in ents], name="entry", mode="markers",
            marker=dict(symbol="triangle-up", size=10, color="#2ca02c",
                        line=dict(width=1, color="#111")),
            hovertext=[f"entry {t['entry_date']} @ {t['entry_price']:.2f}" for t in ents],
            hoverinfo="text"), row=1, col=1)
        for reason, color in _REASON_COLORS.items():
            grp = [t for t in trades if t["exit_reason"] == reason]
            if not grp:
                continue
            fig.add_trace(go.Scatter(
                x=pd.to_datetime([t["exit_date"] for t in grp]),
                y=[t["exit_price"] for t in grp], name=f"exit · {reason}", mode="markers",
                marker=dict(symbol="triangle-down", size=10, color=color,
                            line=dict(width=1, color="#111")),
                hovertext=[f"exit {t['exit_date']} @ {t['exit_price']:.2f} "
                           f"({t['pnl_pct']:+.2f}%)" for t in grp],
                hoverinfo="text"), row=1, col=1)

    # --- Row 2: dollar volume vs the liquidity gate ---
    fig.add_trace(go.Scatter(x=x, y=trace_df["advol"], name="avg $ volume",
                             line=dict(color="#1f77b4", width=1)), row=2, col=1)
    fig.add_hline(y=params.min_dollar_vol, line=dict(color="#d62728", width=1, dash="dash"),
                  annotation_text="min $ vol", row=2, col=1)

    # --- Row 3: this stock's own equity curve (compounded vs summed) ---
    if trades:
        ordered = sorted(trades, key=lambda t: t["exit_ts"])
        ex = pd.to_datetime([t["exit_date"] for t in ordered])
        eq, comp, summ, run = 1.0, [], [], 0.0
        for t in ordered:
            r = t["pnl_pct"]
            eq *= 1.0 + r / 100.0
            run += r
            comp.append((eq - 1.0) * 100.0)
            summ.append(run)
        fig.add_trace(go.Scatter(x=ex, y=comp, name="compounded %",
                                 line=dict(color="#111", width=1.5)), row=3, col=1)
        fig.add_trace(go.Scatter(x=ex, y=summ, name="summed %",
                                 line=dict(color="#999", width=1, dash="dot")), row=3, col=1)

    fig.update_layout(title=title, hovermode="x unified", template="plotly_white",
                      height=920, legend=dict(orientation="h", y=-0.07))
    fig.update_yaxes(title_text="price", row=1, col=1)
    fig.update_yaxes(title_text="$ vol", row=2, col=1)
    fig.update_yaxes(title_text="return %", row=3, col=1)
    return fig


def run(symbol: str, params: Params, db_path: str, out_dir: str, open_browser: bool) -> dict:
    """End-to-end: replay, write CSVs, render the chart. Returns artifact paths + summary."""
    trades, trace_df = analyze(symbol, params, db_path)
    paths = write_details(symbol, trades, trace_df, out_dir)
    fig = build_figure(symbol, params, trades, trace_df)
    html_path = os.path.join(out_dir, f"analysis_{symbol}.html")
    fig.write_html(html_path, include_plotlyjs=True, auto_open=open_browser)
    return {"summary": summarize(trades), "html": html_path, **paths}


def main() -> None:
    try:
        out = run(SYMBOL, PARAMS, DB_PATH, OUT_DIR, open_browser=OPEN_BROWSER)
    except ValueError as e:
        conn = db.connect(DB_PATH)
        try:
            syms = db.list_symbols(conn)
        finally:
            conn.close()
        print(f"ERROR: {e}")
        print(f"{len(syms)} symbols in DB. e.g. {', '.join(syms[:15])}")
        raise SystemExit(1)

    s = out["summary"]
    print(f"{SYMBOL}: {s['n_trades']} trades, win {s['win_rate_pct']:.0f}%, "
          f"avg {s['avg_pct']:+.2f}%/trade")
    print(f"  compounded {s['compounded_pct']:,.1f}%   (summed {s['summed_pct']:,.1f}%)")
    print(f"  chart  -> {out['html']}")
    print(f"  trades -> {out['trades']}")
    print(f"  trace  -> {out['trace']}")


if __name__ == "__main__":
    main()
