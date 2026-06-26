# ATH Backtest Engine — Progress Tracker

Living checklist for building the 52-week-high momentum backtest engine described in
`docs/PRD.md` + `docs/SPEC.md`. Approved plan:
`~/.claude/plans/please-analysis-prd-md-and-fluffy-truffle.md`.

Legend: ☐ todo · ◐ in progress · ☑ done

---

## 🔖 RESUME HERE TOMORROW (handoff)

**Status: implementation complete & verified — `pytest` 29/29 green.** No half-finished or broken
code. All six phases below are ☑. What's left is **2 decisions** + an **optional backlog** (both
listed at the bottom of this file). This `progress.md` is the source of truth for resuming — the
approved plan file lives under `~/.claude/plans/` and is local to the *original* machine, so don't
rely on it being present elsewhere.

**On the other machine (fresh checkout):**
1. `pip install -r requirements.txt`
2. `python -m pytest`  → expect **29 passed**. (Confirms the engine works on the new box.)
3. Data: if `src/data.db` was committed, it's ready. If not, re-fetch — the importer is now
   path-portable (resolves from `__file__`, no hardcoded user path):
   `python src/stock_data_fetch.py`
4. Run a sweep: `python src/backtest.py --entry-mode momentum --out results.csv`

**Git note (you're committing after review):** new/untracked = the `src/` modules, `tests/`,
`conftest.py`, `requirements.txt`, `progress.md`. Modified = `README.md`, `src/data.db` (now
populated), `src/profitandloss_v3.py`, `src/stock_data_fetch.py`, `src/stock_list.txt` (the 6-HK
swap — see Open Questions #2). Generated/optional-to-ignore: `__pycache__/`, `results_*.csv`.
Consider committing `src/data.db` if you want data available tomorrow without re-fetching.

**The 2 decisions waiting on you:** (details below)
- Entry mode default — `literal` (current) vs `momentum` (recommended). One-line change in `src/config.py`.
- Universe — keep 6 HK tickers vs restore 451 US tickers in `src/stock_list.txt`.

---

## ⚠️ TOP DECISION (needs your call) — entry-gate semantics

`SPEC.md` §2.B writes the entry trigger as
`(close >= roll_max) OR (days_since_ipo >= ipo_min_days)`. Literally, the OR makes the
**52-week-high breakout irrelevant for any stock older than 30 trading days** (it would enter on
nearly every non-frozen bar). I've implemented this behind an `entry_mode` flag in `config.py`:

- `entry_mode="literal"` — exactly as SPEC reads (current default).
- `entry_mode="momentum"` *(recommended)* — `close >= roll_max(available history)` **AND**
  `days_since_ipo >= ipo_min_days` (IPO floor = young-stock allowance, not a blanket pass).

**Action:** tell me which to make the default. Everything else works the same either way.

**Concrete evidence** (full sweep on the real 6-ticker `data.db`, see `results_*.csv`):
`literal` enters ~**555 trades** in a representative combo (the age clause fires on nearly every
bar); `momentum` enters ~**21 trades** of genuine breakouts (best combo: win 71%, profit factor
9.4, net +567%, max drawdown −9.75%). This is the difference the flag controls. **My
recommendation: make `momentum` the default.**

---

## Phases

### Phase 0 — Scaffolding & TDD setup
- ☑ `requirements.txt` (yfinance, pandas, numpy, pytest)
- ☑ `conftest.py` puts `src/` on import path; `tests/` package created
- ☑ `src/` importable (conftest path injection)

### Phase 1 — Data pipeline (`src/stock_data_fetch.py`, modify) ☑ (full import running)
- ☑ `ensure_schema()` → `CREATE TABLE IF NOT EXISTS data (...)` PK `(DT, stock)`
- ☑ `__main__` paths resolved from `__file__` (no more `vince`; targets `data.db`)
- ☑ `load_all()` reads `src/stock_list.txt`; ~5-year window ending today; split-adjusted
- ☑ `_rows_from_frame()` parses yfinance **by name** (MultiIndex-safe); `INSERT OR IGNORE`; 30k batching
- ☑ Verified live on AAPL/MSFT/NVDA (354 bars each, correct dates/prices); full 451-ticker import in progress

### Phase 2 — Indicators (`src/indicators.py`) — TDD ☑
- ☑ 252-day rolling high (excludes today)
- ☑ ATR-14 (Wilder)
- ☑ 5-day avg dollar volume
- ☑ days_since_ipo counter
- ☑ Unit tests for each on hand-computed series (5/5 passing)

### Phase 3 — Engine (`src/engine.py`) — TDD
- ☐ `run_symbol(df, params)` — verbatim SPEC §2.B state machine on numpy arrays
- ☐ Wire to `PL` (one instance per symbol, `days_of_trading_per_year=252`, unit=1)
- ☐ `entry_mode` flag (literal vs momentum)
- ☐ Tests: breakout entry, Rule 4 lock, ATR-trail exit, `max()` clause, freeze off-by-one,
      no re-entry while frozen, `freeze_days=0` disables
- ☐ `run_backtest(params)` over all symbols → master trade list

### Phase 4 — Metrics (`src/metrics.py` + 2 `PL` methods) — TDD ☑
- ☑ Extended `PL`: `profit_factor()`, `max_drawdown_pct()` (row order preserved; reuse `metrics`)
- ☑ Portfolio aggregation `summarize()`: Net Profit %, Profit Factor, Max Drawdown %, Win Rate, Count
- ☑ Equal-weight sequential-compounding assumption documented in `metrics.py`
- ☑ Tests on known trade lists (incl. PL-instance integration)

### Phase 5 — Sweep + output (`src/sweep.py`, `src/backtest.py`, `src/config.py`) ☑
- ☑ `Params` dataclass + `DEFAULT_SWEEP` grid
- ☑ `itertools.product` over §4 ranges; indicators computed **once per symbol** (`prepare_symbol`), reused
- ☑ `results.csv` — one row per combo × 5 metrics (`backtest.py` CLI)
- ☑ Default grid = 540 combos (runs in seconds on current data); widen in `config.DEFAULT_SWEEP`

### Phase 6 — Verification & docs ☑
- ☑ `pytest` 29/29 green, output pristine
- ☑ End-to-end run on populated `data.db` → `results_literal.csv` + `results_momentum.csv` (sane metrics)
- ☑ README updated with run instructions

---

## Decisions log
- Reuse `PL` for bookkeeping/stats; add Profit Factor + Max Drawdown % (per your choice).
- Full system in one pass (engine + sweep + results matrix).
- Data pipeline in scope; finish `stock_data_fetch.py` to populate `data.db` from `stock_list.txt`.
- Open positions at end-of-data left open (faithful to SPEC); `forcetoclosetrade` available behind a flag.

## Open questions
1. Entry-gate semantics (see TOP DECISION). Default = `literal`; recommend `momentum`.
2. **Universe:** `src/stock_list.txt` currently holds **6 Hong Kong tickers** (0700.HK, 3690.HK,
   2513.HK, 1810.HK, 1024.HK, 9988.HK) — `data.db` was loaded from these. The committed version
   had 451 US tickers; it was swapped during the session (not by me). To use the US universe:
   `git checkout src/stock_list.txt` then re-run `python src/stock_data_fetch.py`.
3. Data horizon: ~5 years ending today (loaded 2021-06-25 → 2026-06-25). Adjust if you want a fixed window.
4. Full sweep ranges: shipping a 540-combo default grid; confirm if you want the full PRD-scale grid.
5. Liquidity tiers (500K/1M/5M) don't bind for these HK large-caps (dollar volume far exceeds 5M),
   so that sweep axis is currently inert for this universe — expected, not a bug.

## Optional backlog (none blocking — the engine is complete & tested)
- ☐ **Flip entry-mode default** to `momentum` in `src/config.py` (`Params.entry_mode`) once decided.
- ☐ **Widen the sweep grid** toward full PRD §4 ranges in `config.DEFAULT_SWEEP` (currently 540 combos).
      Note: runtime scales with combos × symbols × bars — re-check wall-clock if you 10× the grid.
- ☐ **`force_close_at_end`** — currently `False` (positions open at the last bar are excluded from
      results, faithful to SPEC). Flip to mark-to-market open positions if you want them counted.
- ☐ **ATR method** — Wilder by default; `SPEC.md` also permits a simple 14-bar average. Make it a
      param only if you want to A/B the two.
- ☐ **Housekeeping** — add a `.gitignore` for `__pycache__/` and `results_*.csv` (generated artifacts).
- ☐ **Exit-reason / richer trade log** — engine already tags each trade (`hard_stop`/`breakeven_lock`/
      `atr_trail`/`force_close`); not yet exported. Wire into the `PL`/`trans` DB tables if you want a
      persisted per-trade ledger (those tables exist in `data.db` but are unused).
- ☐ **Sharpe in output** — `PL` computes annualized Sharpe (252-day); not currently in `results.csv`.
      Add a column if useful for ranking robustness clusters.
