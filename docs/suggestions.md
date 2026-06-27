# Suggestions & Observations

_Compiled 2026-06-27 after adding `src/analyze.py`, the engine `trace` hook, and switching the
report metric to `sum_return_pct`. These are review notes — nothing here is implemented. Each item
lists **what / why (evidence) / where / effort (S·M·L)**. Roughly priority-ordered._

---

## A. Execution realism (most likely to be inflating results)

### A1. Stop exits fill at the stop price, even on a gap-through — optimistic · M
- **✅ IMPLEMENTED (2026-06-27):** `Params.intrabar_stops` (default off; ON in `backtest.py` &
  `analyze.py`). Stop exits now fill at `min(stop, Open)`, so gap-downs fill at the open. On the
  default combo this cut the IPO-universe `sum_return_pct` from +4,294.8% to +1,701.1% (PF 4.06 → 1.73).
- **What:** On exit the trade is booked at `final_stop`, not at the bar's actual close/low.
- **Evidence:** `engine.py` `_record(t, final_stop, reason)` (≈line 121); `tests/test_engine.py:test_hard_stop_exit`
  asserts `exit_price == 95.0` when the bar's close is `94`. If a stock gaps down through the stop,
  the real fill is *below* the stop, but the backtest always assumes a perfect fill at the stop level.
- **Why it matters:** Across hundreds of trades this systematically overstates returns, especially for
  the hard-stop exits that make up the bulk of trades.
- **Suggested:** For longs, fill stop exits at `min(stop_level, close[t])` (or model the open/low of the
  exit bar). Add a `slippage_pct` and `commission_pct` parameter while you're in there.

### A2. Stops are only checked at the close, never intrabar — M
- **✅ IMPLEMENTED (2026-06-27):** Same `Params.intrabar_stops` flag. Exits now trigger on `Low[t] <=`
  `final_stop` (intrabar). The trail/lock roll forward only on the close *after* the intraday check, so
  there's no same-bar look-ahead. Entries kept close-confirmed per `docs/SPEC.md` (user's choice).
- **What:** Exit is gated on `close[t] <= final_stop`; the bar's `Low` is never consulted for stop hits
  (it's used only for ATR). A stop pierced intraday but recovered by the close is ignored.
- **Evidence:** `engine.py` exit block (`close[t] <= final_stop`); `High`/`Low` only feed `atr_wilder`.
- **Why it matters:** Daily-close stop logic both misses intraday stop-outs and delays exits a full bar —
  a real modeling choice, but it should be explicit and tested.
- **Suggested:** Optionally evaluate stops against `Low[t]` (intrabar) and entries against intraday
  breakouts; keep it behind a flag so existing tests/semantics are preserved.

### A3. No transaction costs, slippage, or financing — S
- **What:** Returns are gross. A 5-day-DV liquidity gate helps, but small/young IPOs (the `ipo.db`
  universe) have real spread/impact.
- **Suggested:** A single round-trip cost parameter (e.g. `cost_pct` deducted per trade in `pnl_pct`)
  gives a quick sensitivity read.

---

## B. Metrics & portfolio construction

### B1. The real fix: a capital-constrained portfolio equity curve — L  *(biggest value)*
- **What:** `sum_return_pct` is the right *interim* aggregate, but it still assumes equal weight and
  unlimited concurrent capital. A tradeable result needs a real portfolio sim.
- **Why:** With one combo, 540 trades overlap in time across ~187 stocks. To know if the strategy is
  actually viable you need: starting capital, position sizing (e.g. risk-based so a hard stop loses a
  fixed % of equity), a cap on concurrent positions, cash drag, and a daily mark-to-market curve.
- **Payoff:** That curve makes **CAGR, annualized Sharpe (PRD asks for this), and max drawdown** all
  meaningful at once — and resolves B2 below for free.
- **Where:** New module alongside `sweep.py`; reuse the `trace`/trades output already produced.

### B2. `max_drawdown_pct` is still on the *compounded* curve — inconsistent now · S
- **✅ IMPLEMENTED (2026-06-27):** `metrics.max_drawdown_pct` now tracks the cumulative-**sum** curve and
  reports the peak-to-trough drop in additive percentage points. The old misleading −100% (compounded
  curve → zero) is gone; the default realistic combo reads −279.7 pts against its +1,701-pt total.
- **What:** After switching the headline to `sum_return_pct`, drawdown still compounds pooled trades
  (`metrics.max_drawdown_pct`). It doesn't explode (bounded, ≈ −64.6% for the default combo) but it's
  measuring a curve we just declared meaningless.
- **Suggested:** Either compute drawdown on the cumulative **sum** curve, or — better — defer to B1's
  real equity curve and drop the trade-sequence drawdown entirely.

### B3. Results hinge on a handful of outlier winners — fragility metric · S
- **Evidence:** For the default combo, per-stock tops were `6181.HK +490%`, `2617.HK +458%`,
  `6959.HK +423%`, `2477.HK +361%`; median per-stock compounded was only **+1.0%**. A few names carry
  the whole sum.
- **Suggested:** Report **median per-trade return** and a robustness column like "sum_return excluding
  top-5 trades" so the optimizer doesn't just chase outlier-luck combos.

---

## C. Data quality

### C1. Validate the giant single-trade winners for split/adjustment artifacts — S
- **What:** `2477.HK` shows a 0.562 → 2.59 move (+361%). It looks real (the stock keeps trading up to
  ~4.5 afterward), but +400–490% single trades are exactly where unadjusted splits / bad bars hide.
- **Suggested:** A quick data-quality pass flagging single-bar moves above, say, ±50%; eyeball the
  flagged names with `analyze.py` (the chart was built for this).

### C2. Universe / survivorship and date range should be documented — S
- **What:** `ipo.db` is recent IPOs; momentum-breakout results on a young, possibly survivorship-biased
  universe can look better than reality.
- **Suggested:** Record the universe construction, date span, and any de-listing handling in `docs/`.

---

## D. Project hygiene

### D1. `CLAUDE.md` is stale — M
- **What:** It states "the backtest engine described in the SPEC **does not exist yet**." It does now:
  `engine.py`, `sweep.py`, `backtest.py`, `metrics.py`, plus a 33-test suite.
- **Suggested:** Refresh it to describe the real layout and the new pieces: `analyze.py`, the default-off
  `trace` hook, `sum_return_pct`, the `plotly` dependency, and `ipo.db` vs `stocks.db`.

### D2. Reconcile the database files — S
- **What:** `stock_data_fetch.py` `__main__` points `DBFILE` at `stocks.db`; the engine defaults to
  `ipo.db` (`backtest.py`), and CLAUDE.md mentions `data.db`. Three names, unclear canon.
- **Suggested:** Pick the canonical DB per workflow and document it; consider a single config constant.

### D3. `profitandloss_v3.py` is dead weight on the live path — S
- **What:** The sweep never passes a `pl=`, so the `PL` class (and its `common.gfuncs` dependency,
  365-day Sharpe default) isn't exercised except in one test. It also *sums* PL% where the rest of the
  code is careful about compounding.
- **Suggested:** Either wire it in properly (with `days_of_trading_per_year=252`) or drop it from the
  engine surface to remove the phantom `common/` dependency noted in CLAUDE.md.

### D4. Generated artifacts in git — S
- **What:** `report_ipo.csv` (and the old `net_profit_pct` values) is committed. `analysis/` is now
  gitignored; `report*.csv` is not.
- **Suggested:** Decide whether the report is a tracked deliverable or a build artifact; if the latter,
  gitignore `report*.csv` too.

### D5. Add lint + CI — M
- **What:** No linter or CI, but there's now a real test suite worth protecting.
- **Suggested:** `ruff` (or flake8) + a minimal GitHub Actions workflow running `pytest`.

---

## E. Performance / nice-to-haves

- **E1. Parallelize the sweep (L):** 1,728 combos are independent and indicators are already precomputed
  once per symbol (`prepare_all`). `multiprocessing` over combos could cut wall-clock substantially.
  Profile first — confirm the state-machine pass, not I/O, is the bottleneck.
- **E2. Sharpe in the report (S, depends on B1):** PRD asks for annualized Sharpe; it only becomes
  well-defined once there's a real portfolio equity curve.
- **E3. `analyze.py` extras (S):** optional candlesticks instead of a close line, and an overlay of the
  per-bar `event`/`exit_reason` from the trace CSV for faster eyeballing.

---

## Suggested order of attack
1. **A1 + A3** (fill realism + costs) — cheapest way to find out if the edge survives contact with reality.
2. **B1** (portfolio equity curve) — unlocks correct Sharpe/CAGR/drawdown and supersedes B2.
3. **C1** (validate outlier trades) — make sure the few names carrying the sum are real.
4. **D1/D2** (docs + DB reconciliation) — low effort, removes confusion for future work.
