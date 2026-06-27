# Product Requirement Document (PRD)

## 1. Executive Summary & Objective
The objective is to build a high-performance, lightweight algorithmic backtesting engine in Python to evaluate a classic momentum breakout trading strategy over a historical 5-year horizon. The strategy targets stocks achieving 52-week all-time highs (including young IPO stocks) while applying strict dollar-volume liquidity filters. Risk management is governed by a dynamic dual-exit system executing an `OR` condition logic via a mathematical `max()` function across a hard stop-loss ceiling and a volatility-adjusted Average True Range (ATR) trailing profit-take. 

The system must facilitate automated parameter sweeps and multi-variable optimizations to eliminate curve-fitting and identify robust operational parameter clusters.

## 2. Core Trading Strategy Specifications
The engine must strictly enforce the following algorithmic logic per asset-session:

* **Entry Trigger (Momentum Breakout):** An entry signal is generated on day $t$ only when **both** conditions hold: (1) the closing price $C_t$ matches or exceeds the 52-week (252 trading days) high computed over the asset's available history, **AND** (2) the asset has a lifetime trading history matching or exceeding a configurable floor parameter ($\ge N$ days, default 30). The age floor screens out the first volatile days of a young IPO while still letting it break out over its available history; it is a gate on the breakout, not an alternative entry path.
* **Liquidity Filter:** The rolling 5-day moving average of daily dollar volume ($\text{Close}_t \times \text{Volume}_t$) must strictly exceed a configurable dollar threshold parameter ($V_{\text{target}}$).
* **Initial Stop-Loss Ceiling:** Upon entry, a hard stop-loss is placed at a fixed percentage below the entry price ($1 - \text{Cutloss}\%$, e.g., $-5\%$).
* **Break-Even Profit Protection (Rule 4 Trigger):** If the market price at any point touches or exceeds a target percentage above the execution entry price ($1 + \text{Trigger}\%$, e.g., $+6\%$), the hard stop-loss value must instantly lock at a guaranteed profitable floor ($1 + \text{Lock}\%$, e.g., $+1\%$).
* **Volatility-Adjusted Trailing Profit-Take:** The program tracks the highest peak price ($P_{\text{max}}$) achieved since entry. A trailing stop is plotted dynamically below this peak based on a volatility multiplier multiplied by the current ATR ($P_{\text{max}} - [K \times \text{ATR}_t]$).
* **Dynamic Exit Execution (`OR` Clause):** Positions are closed on day $t$ if the current price falls to or below the maximum value of either safety net:
    $$\text{Trigger Stop Price} = \max(\text{Dynamic Stop Price}, \text{ATR Trailing Price})$$
* **Loss-Cooldown Freeze (Re-entry Lockout):** Immediately after any position closes at a realized loss (exit price strictly below entry price, $\text{exit\_price} < \text{entry\_price}$), the symbol enters a *frozen* state and is barred from generating new entry signals for a configurable number of **trading days** ($\text{Freeze\_Days}$, default $0$ = disabled). This suppresses immediate re-entry whipsaw following a stop-out. The lockout is measured in trading-day bars (weekends/holidays are skipped automatically) and is tracked **per symbol** independently.

## 3. Scope, Parameters & Structural Limitations
To streamline early-stage development and optimize processing throughput, the following conditions apply:
* **Slippage & Gaps:** Assumed execution at exact close or historical boundary values; real-world execution slippage and overnight price gaps are excluded from tracking for this stage.
* **Survivorship Bias:** The engine will evaluate historical data using the available database schema (acknowledged restriction for initial testing phases).
* **Data Persistence:** The engine must interface natively with a local SQLite database containing pre-imported historical price and volume matrices.

## 4. Parameter Sweep & Optimization Goals
The application must execute automated multi-variable loops over user-defined ranges. It must record, aggregate, and map performance output vectors to expose clusters of robustness across:
* Initial Cutloss % (Step sizes of 1%)
* Break-Even Trigger % & Lock %
* ATR Multiplier steps (e.g., intervals of 0.5R)
* Minimum Average Dollar Volume Tiers (e.g., $500,000, $1,000,000, $5,000,000)
* Loss-Cooldown Freeze Duration ($\text{Freeze\_Days}$, trading days; e.g., {0, 5, 10, 20, 30})

The system must log and output data matrices containing Net Profit %, Profit Factor, Max Drawdown %, Win Rate, and Total Trade Count.