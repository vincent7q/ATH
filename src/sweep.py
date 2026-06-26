"""Parameter-sweep driver (docs/PRD.md §4).

Indicators are pre-computed once per symbol (``engine.Prepared``); the sweep re-runs only the
cheap state-machine pass for each parameter combination, so the full grid stays tractable.
"""
import itertools

import engine
import metrics
from config import DEFAULT_SWEEP, Params


def iter_combos(grid: dict):
    """Yield one ``{param: value}`` dict per point in the Cartesian product of ``grid``."""
    keys = list(grid.keys())
    for values in itertools.product(*(grid[k] for k in keys)):
        yield dict(zip(keys, values))


def run_sweep(prepared_list, grid: dict = DEFAULT_SWEEP, fixed: dict | None = None) -> list[dict]:
    """Run every parameter combination over the pre-prepared symbols.

    ``fixed`` supplies non-swept Params overrides (e.g. ``entry_mode``, indicator windows) and is
    not echoed into the result rows. Each result row = the swept combo + the five PRD metrics.
    """
    fixed = fixed or {}
    results = []
    for combo in iter_combos(grid):
        params = Params(**{**fixed, **combo})
        trades = []
        for p in prepared_list:
            trades.extend(engine.run_state_machine(p, params))
        results.append({**combo, **metrics.summarize(trades)})
    return results
