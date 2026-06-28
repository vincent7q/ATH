"""Entry point: load `stocks.db`, run the parameter sweep, write a results matrix CSV.

No command-line arguments — edit the PARAMETERS block below, then run directly:

    python src/backtest.py
"""
import csv
import os

import db
import engine
import sweep

# ============================================================================
# PARAMETERS — edit these, then run:  python src/backtest.py
# ============================================================================

# --- Run options ---
GROUP=2;   #1: IPOs, 2: All stocks
if GROUP==1:
    DB_PATH = os.path.join(os.path.dirname(__file__), "ipo.db")  # price database
    OUT_PATH = "report_ipo.csv"       # output CSV (parameter matrix)
else:
    DB_PATH = os.path.join(os.path.dirname(__file__), "stocks.db")  # price database
    OUT_PATH = "report_stocks.csv"       # output CSV (parameter matrix)

FORCE_CLOSE = True                # mark-to-market positions still open at the last bar
INTRABAR_STOPS = True             # realistic exits: stop triggers on the bar Low, fills at min(stop, Open)
LIMIT = None                      # cap number of symbols (e.g. 20 for a quick test); None = all

# --- Indicator windows (fixed across the whole sweep) ---
ATR_PERIOD = 14
ROLL_WINDOW = 252
DOLLAR_VOL_WINDOW = 5

# --- Parameter sweep grid (one CSV row per combination) ---
SWEEP_GRID = {
    "initial_cutloss_pct": [0.03, 0.04, 0.05, 0.06, 0.07,0.08],
    "breakeven_trigger_pct": [0.06, 0.08, 0.10],
    "breakeven_lock_pct": [0.01, 0.02],
    "atr_multiplier": [1.5,2.0, 2.5, 3.0],
    "min_dollar_vol": [500_000.0, 1_000_000.0, 5_000_000.0],
    "freeze_days": [0, 10, 20, 30],
}

# ============================================================================

METRIC_COLS = ["trade_count", "win_rate_pct", "sum_return_pct", "profit_factor", "max_drawdown_pct"]


def prepare_all(conn, symbols, atr_period=14, roll_window=252, dollar_vol_window=5):
    """Pre-compute indicators once per symbol (skips empty symbols)."""
    prepared = []
    for sym in symbols:
        d = db.load_symbol(conn, sym)
        if len(d) == 0:
            continue
        prepared.append(engine.prepare_symbol(d, atr_period, roll_window, dollar_vol_window))
    return prepared


def run(db_path, grid=SWEEP_GRID, force_close=False, limit=None,
        atr_period=14, roll_window=252, dollar_vol_window=5, fixed_overrides=None,
        intrabar_stops=False):
    """Load the DB, prepare every symbol once, and run the full sweep. Returns result rows."""
    conn = db.connect(db_path)
    try:
        symbols = db.list_symbols(conn)
        if limit:
            symbols = symbols[:limit]
        prepared = prepare_all(conn, symbols, atr_period, roll_window, dollar_vol_window)
    finally:
        conn.close()

    fixed = {"force_close_at_end": force_close, "intrabar_stops": intrabar_stops,
             "atr_period": atr_period, "roll_window": roll_window,
             "dollar_vol_window": dollar_vol_window}
    if fixed_overrides:
        fixed.update(fixed_overrides)
    return sweep.run_sweep(prepared, grid, fixed=fixed)


def write_csv(rows, path, grid=SWEEP_GRID):
    cols = list(grid.keys()) + METRIC_COLS
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c) for c in cols})


def main():
    rows = run(DB_PATH, grid=SWEEP_GRID, force_close=FORCE_CLOSE,
               limit=LIMIT, atr_period=ATR_PERIOD, roll_window=ROLL_WINDOW,
               dollar_vol_window=DOLLAR_VOL_WINDOW, intrabar_stops=INTRABAR_STOPS)
    write_csv(rows, OUT_PATH, grid=SWEEP_GRID)
    print(f"Wrote {len(rows)} parameter rows -> {OUT_PATH}")


if __name__ == "__main__":
    main()
