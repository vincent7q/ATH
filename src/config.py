"""Strategy parameters and parameter-sweep defaults (docs/PRD.md §2 & §4)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Params:
    """One backtest configuration. Percentages are fractions (0.05 == 5%)."""

    # --- swept by the optimizer (PRD §4) ---
    initial_cutloss_pct: float = 0.05     # hard stop = entry * (1 - cutloss)
    breakeven_trigger_pct: float = 0.06   # Rule 4 arms when price >= entry * (1 + trigger)
    breakeven_lock_pct: float = 0.01      # ...then stop locks at entry * (1 + lock)
    atr_multiplier: float = 2.5           # trailing stop = peak - mult * ATR
    min_dollar_vol: float = 1_000_000.0   # liquidity gate (strictly exceeds)
    freeze_days: int = 0                  # loss-cooldown lockout, in trading-day bars

    # --- fixed indicator windows (not swept) ---
    ipo_min_days: int = 30
    atr_period: int = 14
    roll_window: int = 252
    dollar_vol_window: int = 5

    # --- behaviour switches ---
    force_close_at_end: bool = False      # mark-to-market any position still open at last bar


# Default sweep grid — modest so the full run finishes quickly; widen toward PRD §4 as needed.
DEFAULT_SWEEP = {
    "initial_cutloss_pct": [0.03, 0.04, 0.05, 0.06, 0.07,0.08],
    "breakeven_trigger_pct": [0.06, 0.08, 0.10],
    "breakeven_lock_pct": [0.01, 0.02],
    "atr_multiplier": [1.5,2.0, 2.5, 3.0],
    "min_dollar_vol": [500_000.0, 1_000_000.0, 5_000_000.0],
    "freeze_days": [0, 10, 20, 30],
}
