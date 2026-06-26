# ATH

Backtesting engine for a **52-week all-time-high momentum breakout** strategy (incl. young IPOs),
with a dollar-volume liquidity filter and a dual-exit risk system
(`max(hard_stop, ATR_trailing_stop)`). Strategy rules: `docs/PRD.md`; module/indicator design:
`docs/SPEC.md`. Build status & open decisions: `progress.md`.

## Install

```bash
pip install -r requirements.txt   # yfinance, pandas, numpy, pytest
```

## 1. Load price data

Fetches ~5 years of daily OHLCV for every ticker in `src/stock_list.txt` into `src/data.db`
(split/dividend-adjusted; idempotent `INSERT OR IGNORE`, so re-running just tops up).

```bash
python src/stock_data_fetch.py
```

## 2. Run the parameter sweep

Runs the strategy across the `DEFAULT_SWEEP` grid (cutloss %, breakeven trigger/lock %,
ATR multiplier, min dollar-volume tiers, freeze-days) and writes one row per combination with
Net Profit %, Profit Factor, Max Drawdown %, Win Rate, and Trade Count.

```bash
python src/backtest.py --entry-mode momentum --out results.csv
# options: --entry-mode {literal|momentum}  --force-close  --limit N  --db PATH
```

**Entry mode** — `momentum` (recommended) enters only on a genuine break to the all-time high;
`literal` follows the SPEC verbatim, where the IPO age-clause makes the breakout filter moot for
mature names (see the decision note in `progress.md`). Widen the search space by editing
`config.DEFAULT_SWEEP`.

## Architecture (`src/`)

| Module | Role |
|--------|------|
| `stock_data_fetch.py` | yfinance → SQLite `data` table |
| `db.py` | load price bars per symbol |
| `indicators.py` | 252-day high, ATR-14 (Wilder), 5-day $-volume, days-since-IPO |
| `engine.py` | per-symbol state machine (`docs/SPEC.md` §2.B) |
| `metrics.py` | portfolio metrics (net profit, profit factor, max drawdown, win rate) |
| `sweep.py` / `backtest.py` | parameter sweep + CSV output |
| `profitandloss_v3.py` | trade bookkeeping (`PL`), extended with profit-factor / max-drawdown |

## Tests

```bash
python -m pytest        # 29 tests: indicators, engine rules, metrics, db, sweep, pipeline
```
