"""Data-access tests (TDD, before src/db.py). Uses a temp SQLite with the real `data` schema."""
import sqlite3

import pytest

import db

SCHEMA = """
CREATE TABLE data (
    stock TEXT, DT INTEGER, Date TEXT,
    Open REAL, Close REAL, High REAL, Low REAL, Volume REAL,
    PRIMARY KEY (DT, stock)
)
"""


@pytest.fixture
def conn(tmp_path):
    path = tmp_path / "test.db"
    c = sqlite3.connect(path)
    c.executescript(SCHEMA)
    rows = [
        # inserted out of DT order on purpose
        ("BBB", 2000, "1970-01-01", 1, 2, 3, 0.5, 100),
        ("AAA", 2000, "1970-01-01", 1, 2, 3, 0.5, 100),
        ("AAA", 1000, "1970-01-01", 1, 2, 3, 0.5, 100),
    ]
    c.executemany("INSERT INTO data (stock,DT,Date,Open,Close,High,Low,Volume) VALUES (?,?,?,?,?,?,?,?)", rows)
    c.commit()
    yield c
    c.close()


def test_list_symbols_distinct_sorted(conn):
    assert db.list_symbols(conn) == ["AAA", "BBB"]


def test_load_symbol_sorted_by_dt(conn):
    df = db.load_symbol(conn, "AAA")
    assert list(df["DT"]) == [1000, 2000]                     # ascending
    assert list(df.columns) == ["stock", "DT", "Date", "Open", "Close", "High", "Low", "Volume"]
    assert (df["stock"] == "AAA").all()
