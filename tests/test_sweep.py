"""Parameter-sweep tests (TDD, before src/sweep.py)."""
import pandas as pd

import engine
import sweep

BASE_TS = 1_600_000_000
DAY = 86_400


def _prepared(closes):
    n = len(closes)
    dt = [BASE_TS + i * DAY for i in range(n)]
    date = [pd.to_datetime(ts, unit="s").strftime("%Y-%m-%d") for ts in dt]
    df = pd.DataFrame({
        "stock": "T", "DT": dt, "Date": date, "Open": closes,
        "Close": closes, "High": closes, "Low": closes, "Volume": [1e6] * n,
    })
    return engine.prepare_symbol(df, atr_period=2, roll_window=2, dollar_vol_window=1)


def test_run_sweep_one_row_per_combo():
    grid = {"initial_cutloss_pct": [0.03, 0.05], "atr_multiplier": [2.0, 3.0]}
    fixed = {"min_dollar_vol": 0.0, "ipo_min_days": 1, "atr_period": 2,
             "roll_window": 2, "dollar_vol_window": 1}
    results = sweep.run_sweep([_prepared([100, 99, 98, 97, 96])], grid, fixed=fixed)
    assert len(results) == 4                                   # 2 x 2
    row = results[0]
    for key in ("initial_cutloss_pct", "atr_multiplier", "trade_count",
                "win_rate_pct", "net_profit_pct", "profit_factor", "max_drawdown_pct"):
        assert key in row
