# Technical Specification Document (SPEC)

## 1. Architecture Overview & Data Schema
The program will be written in Python 3.10+ using a modular, single-process, matrix-driven execution architecture. Data is extracted directly from a local `sqlite3` database file.

### Database Interaction Schema
The engine assumes the database file contains daily historical bars with at least the following column structures:
* `Symbol` (TEXT / VARCHAR) - Indexed
* `Date` (TEXT/DATE) - ISO-8601 Format (`YYYY-MM-DD`), Indexed
* `Open` (REAL), `High` (REAL), `Low` (REAL), `Close` (REAL), `Volume` (REAL)

The Python script must pull data sequentially by symbol or chunked into an optimal structure using `pandas` to maintain speed during iterations.

## 2. Core Functional Modules & Algorithmic Logic

### A. Data Pre-processing Module
For each stock dataframe, calculate the required indicator vectors *before* loop execution to minimize runtime calculations:
1.  **52-Week High (252-day Rolling Maximum):**
    $$\text{Roll\_Max}_{t} = \max(C_{t-1}, C_{t-2}, \dots, C_{t-252})$$
    Computed over *available* history (a partial window is used until 252 prior closes exist), so a young IPO past the age floor still has a valid breakout reference.
2.  **Average True Range (ATR - 14 Days):**
    $$\text{TR}_t = \max([H_t - L_t], |H_t - C_{t-1}|, |L_t - C_{t-1}|)$$
    $$\text{ATR}_t = \frac{1}{14}\sum_{i=0}^{13}\text{TR}_{t-i} \quad \text{(or Wilders Smoothing)}$$
3.  **5-Day Average Dollar Volume:**
    $$\text{Dollar\_Vol}_t = C_t \times V_t$$
    $$\text{Avg\_Dollar\_Vol}_t = \frac{1}{5}\sum_{i=0}^{4}\text{Dollar\_Vol}_{t-i}$$
4.  **Days Since IPO Tracking:** A running counter mapping cumulative active trading rows per symbol to confirm $\ge N$ days constraint.

### B. Backtest Execution Engine (Loop Logic)
The engine maintains a virtual portfolio and step-tracks state arrays per trade:
* `in_position` (Boolean)
* `entry_price` (Float)
* `peak_price` (Float)
* `dynamic_stop` (Float)
* `frozen_until` (Int) — last bar index still frozen for this symbol after a losing exit; initialized to `-1` (nothing frozen at start). Driven by the `freeze_days` parameter (trading-day bars; `0` = disabled).

```python
# State Variable Transitions Per Day 't'  (t = integer bar index)
if not in_position:
    # Entry Condition Check — gated by the loss-cooldown freeze (t > frozen_until).
    # A losing exit on bar k freezes bars k+1 .. k+freeze_days; re-entry resumes at k+freeze_days+1.
    # With freeze_days == 0, frozen_until == k and the next entry check (t = k+1 > k) is unaffected -> disabled.
    if t > frozen_until and (close[t] >= roll_max[t]) and (days_since_ipo[t] >= ipo_min_days) and (avg_dollar_vol[t] > min_dollar_vol):
        in_position = True
        entry_price = close[t]
        peak_price = close[t]
        dynamic_stop = entry_price * (1 - initial_cutloss_pct)
        entry_date = date[t]
else:
    # Track trailing metrics
    if close[t] > peak_price:
        peak_price = close[t]
        
    # Rule 4: Break-Even Trigger Modification
    if close[t] >= (entry_price * (1 + breakeven_trigger_pct)):
        dynamic_stop = max(dynamic_stop, entry_price * (1 + breakeven_lock_pct))
        
    # ATR Trailing Stop Calculation
    atr_stop = peak_price - (atr_multiplier * atr[t])
    
    # Combined OR execution boundary via MAX()
    final_execution_stop = max(dynamic_stop, atr_stop)
    
    # Exit Execution Check
    if close[t] <= final_execution_stop:
        exit_price = final_execution_stop # Simulating instant execution boundary
        log_trade_metrics(symbol, entry_price, exit_price, entry_date, date[t])
        in_position = False
        
        # Loss-Cooldown Freeze: lock out re-entry for freeze_days bars after a losing trade
        if exit_price < entry_price:
            frozen_until = t + freeze_days