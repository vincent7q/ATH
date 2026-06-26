"""CLI entry point: load `data.db`, run the parameter sweep, write a results matrix CSV.

Usage:
    python src/backtest.py                       # full default grid, literal entry mode
    python src/backtest.py --entry-mode momentum # recommended interpretation (see progress.md)
    python src/backtest.py --limit 20 --out small.csv
"""
import argparse
import csv
import os

import db
import engine
import sweep
from config import DEFAULT_SWEEP

DEFAULT_DB = os.path.join(os.path.dirname(__file__), "data.db")
METRIC_COLS = ["trade_count", "win_rate_pct", "net_profit_pct", "profit_factor", "max_drawdown_pct"]


def prepare_all(conn, symbols, atr_period=14, roll_window=252, dollar_vol_window=5):
    """Pre-compute indicators once per symbol (skips empty symbols)."""
    prepared = []
    for sym in symbols:
        d = db.load_symbol(conn, sym)
        if len(d) == 0:
            continue
        prepared.append(engine.prepare_symbol(d, atr_period, roll_window, dollar_vol_window))
    return prepared


def run(db_path, grid=DEFAULT_SWEEP, entry_mode="literal", force_close=False, limit=None,
        atr_period=14, roll_window=252, dollar_vol_window=5, fixed_overrides=None):
    """Load the DB, prepare every symbol once, and run the full sweep. Returns result rows."""
    conn = db.connect(db_path)
    try:
        symbols = db.list_symbols(conn)
        if limit:
            symbols = symbols[:limit]
        prepared = prepare_all(conn, symbols, atr_period, roll_window, dollar_vol_window)
    finally:
        conn.close()

    fixed = {"entry_mode": entry_mode, "force_close_at_end": force_close,
             "atr_period": atr_period, "roll_window": roll_window,
             "dollar_vol_window": dollar_vol_window}
    if fixed_overrides:
        fixed.update(fixed_overrides)
    return sweep.run_sweep(prepared, grid, fixed=fixed)


def write_csv(rows, path, grid=DEFAULT_SWEEP):
    cols = list(grid.keys()) + METRIC_COLS
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c) for c in cols})


def main(argv=None):
    ap = argparse.ArgumentParser(description="ATH momentum backtest parameter sweep")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--out", default="results.csv")
    ap.add_argument("--entry-mode", choices=["literal", "momentum"], default="literal")
    ap.add_argument("--force-close", action="store_true",
                    help="mark-to-market positions still open at the last bar")
    ap.add_argument("--limit", type=int, default=None, help="cap number of symbols (debugging)")
    args = ap.parse_args(argv)

    rows = run(args.db, entry_mode=args.entry_mode, force_close=args.force_close, limit=args.limit)
    write_csv(rows, args.out)
    print(f"Wrote {len(rows)} parameter rows -> {args.out}")


if __name__ == "__main__":
    main()
