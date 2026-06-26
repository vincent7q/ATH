# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.



## Project Purpose

ATH is a backtesting engine for a **52-week all-time-high momentum breakout** trading
strategy (incl. young IPOs), with strict dollar-volume liquidity filters and a dual-exit
risk system. The full strategy and architecture are specified in:

- `docs/PRD.md` — strategy rules (entry trigger, liquidity filter, stop-loss, break-even
  lock "Rule 4", ATR trailing stop, `max()` exit clause) and the parameter-sweep goals.
- `docs/SPEC.md` — Python module design, indicator formulas (252-day rolling high, 14-day
  ATR/Wilder, 5-day avg dollar volume, days-since-IPO), and the per-day state-machine loop.

**Read both before implementing strategy logic** — they are the source of truth for the math.

## Current State (important)

The backtest engine described in the SPEC **does not exist yet**. Only two pieces are present:

- `src/stock_data_fetch.py` — data ingestion: pulls OHLCV from `yfinance` and bulk-inserts
  into SQLite. This is the data layer feeding the (future) engine.
- `src/profitandloss_v3.py` — the P&L accounting layer (`PL` and `Summary` classes),
  ported from a prior crypto trading project. The engine's loop is meant to call `PL.addnew(...)`
  on each entry/exit and read stats back out.

The engine loop that ties indicators + `PL` together (per `docs/SPEC.md` §B) still needs to be written.

## Commands

No build system, test suite, lint config, or `requirements.txt` exists. Python 3.12 (SPEC asks 3.10+).

```bash
# Install deps (none pinned — these are the imports actually used)
pip install yfinance pandas numpy

# Run the data fetcher (edit the date range / paths in its __main__ block first)
python src/stock_data_fetch.py
```

There are currently no tests. If adding them, there is no configured runner yet — introduce one
(e.g. `pytest`) as part of the change.

## Data Model (SQLite)

`src/data.db` holds the price + results tables. Key schema facts:

- **`data`** — daily price bars. Columns in storage order:
  `stock, DT, Date, Open, Close, High, Low, Volume`.
  **Note the column order: `Open, Close, High, Low` — NOT conventional OHLC.** `DT` is a Unix
  timestamp (seconds); `Date` is `YYYY-MM-DD`. Primary key is `(DT, stock)`. Currently empty.
- **`PL`** — trade results: `open_dt, open_date, close_dt, close_date, coin, entry_price,
  exit_price, unit, pnl, pnl_percent, holding_days, exit_reason, stage, entrycondition`.
- **`trans`** — raw transaction log (`DT, Date, coin, action, unit, price`).

`stock_data_fetch.py` assumes the `data` table already exists (it has no `CREATE TABLE`); inserts
go via `executemany` in 30k-row buffered batches.

## The `PL` accounting class (`profitandloss_v3.py`)

Drives trade bookkeeping. Core flow: call `addnew(action, price, now, unit, factor=1.0)` per
event — `action` is `+1` (long) / `-1` (short), `now` is a Unix timestamp. It supports
**turtle-style pyramiding**: same-direction calls add units; opposite-direction calls close
(handling full, partial, and over-close cases). `forcetoclosetrade(price, now)` liquidates an
open position at end-of-run.

Completed trades land in `self.df` as header rows indexed by trigger time. **Row layout (index → field):**
`0 coin, 1 action, 2 open_ts, 3 open_str, 4 avg_open_price, 5 close_ts, 6 close_str,
7 close_price, 8 PL, 9 PL%, 10 factor`. The `statistics*` methods read `row[8]`/`row[9]`, so
preserve this order if you touch it. Stats helpers: `statistics_details_advance()` (win/loss %,
annualized Sharpe, max loss) and `ratiosummary()` (via the `Summary` aggregator).

### Gotchas in `profitandloss_v3.py`

- **Missing dependency:** it imports `common.gfuncs as G` and calls `G.timestamp_to_str()` and
  `G.println()`. There is **no `common/` package in this repo** — it must be supplied before the
  module can run. Provide a `common/gfuncs.py` (or vendor it) when wiring the engine.
- **Sharpe day-count:** `PL(__init__)` defaults `days_of_trading_per_year=365` (crypto heritage).
  For equities pass **252** to match `docs/SPEC.md`, or the annualized Sharpe will be off.
- The header changelog references `docs/version_history.md`, `docs/backtest_improvements.md`,
  and `docs/core_bugs.md` — these files **do not exist** in the repo.

## Conventions

- Hardcoded Windows absolute paths live in `stock_data_fetch.py`'s `__main__` (the `nt` branch:
  `stockfile`, `DBFILE` → `src/stocks.db`). Note `DBFILE` there points at `stocks.db`, while the
  committed DB is `data.db` — reconcile the target before running.
- `src/stock_list.txt` is the universe: ~450 ticker symbols, one per line (first CSV column).
- Throughout the ported P&L code, "coin"/"currency" is generic for the traded symbol (a stock here).
