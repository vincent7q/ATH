"""Pytest bootstrap: put ``src/`` on the import path so tests can import the
engine modules (``indicators``, ``engine``, ``metrics``, ``profitandloss_v3`` …)
directly, matching how ``python src/backtest.py`` resolves its own imports."""
import os
import sys

SRC = os.path.join(os.path.dirname(__file__), "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)
