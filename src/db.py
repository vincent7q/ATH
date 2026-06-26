"""SQLite access for the price `data` table (see CLAUDE.md / docs for the schema).

Storage column order is ``stock, DT, Date, Open, Close, High, Low, Volume`` (note the
**Open, Close, High, Low** ordering — not conventional OHLC). ``DT`` is a Unix timestamp (s);
``Date`` is ``YYYY-MM-DD``. Primary key is ``(DT, stock)``.
"""
import sqlite3

import pandas as pd

COLUMNS = ["stock", "DT", "Date", "Open", "Close", "High", "Low", "Volume"]


def connect(path: str) -> sqlite3.Connection:
    return sqlite3.connect(path)


def list_symbols(conn: sqlite3.Connection) -> list[str]:
    """Distinct tickers present in `data`, sorted alphabetically."""
    cur = conn.execute("SELECT DISTINCT stock FROM data ORDER BY stock")
    return [r[0] for r in cur.fetchall()]


def load_symbol(conn: sqlite3.Connection, symbol: str) -> pd.DataFrame:
    """All bars for one symbol as a DataFrame sorted by DT ascending."""
    return pd.read_sql_query(
        "SELECT stock, DT, Date, Open, Close, High, Low, Volume "
        "FROM data WHERE stock = ? ORDER BY DT ASC",
        conn, params=(symbol,),
    )
