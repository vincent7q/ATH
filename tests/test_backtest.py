"""End-to-end pipeline test (TDD, before src/backtest.py): temp DB -> sweep -> CSV."""
import csv
import sqlite3

import pytest

import backtest

SCHEMA = """
CREATE TABLE data (
    stock TEXT, DT INTEGER, Date TEXT,
    Open REAL, Close REAL, High REAL, Low REAL, Volume REAL,
    PRIMARY KEY (DT, stock)
)
"""
BASE_TS = 1_600_000_000
DAY = 86_400


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "data.db"
    c = sqlite3.connect(path)
    c.executescript(SCHEMA)
    closes = [100, 94, 100, 94, 100, 94]                       # repeated -6% drops -> losing trades
    rows = []
    for i, px in enumerate(closes):
        ts = BASE_TS + i * DAY
        rows.append(("T", ts, "1970-01-01", px, px, px, px, 1_000_000))
    c.executemany("INSERT INTO data (stock,DT,Date,Open,Close,High,Low,Volume) VALUES (?,?,?,?,?,?,?,?)", rows)
    c.commit()
    c.close()
    return str(path)


def test_run_pipeline_produces_results(db_path):
    rows = backtest.run(
        db_path, grid={"initial_cutloss_pct": [0.05]},
        atr_period=2, roll_window=2, dollar_vol_window=1,
        fixed_overrides={"min_dollar_vol": 0.0, "ipo_min_days": 1}, force_close=True,
    )
    assert len(rows) == 1
    assert rows[0]["trade_count"] >= 1


def test_write_csv_has_header_and_rows(tmp_path):
    rows = [{"initial_cutloss_pct": 0.05, "trade_count": 2, "win_rate_pct": 0.0,
             "sum_return_pct": -9.8, "profit_factor": 0.0, "max_drawdown_pct": -9.8}]
    out = tmp_path / "results.csv"
    backtest.write_csv(rows, str(out), grid={"initial_cutloss_pct": [0.05]})
    with open(out, newline="") as f:
        read = list(csv.DictReader(f))
    assert len(read) == 1
    assert "initial_cutloss_pct" in read[0] and "sum_return_pct" in read[0]
