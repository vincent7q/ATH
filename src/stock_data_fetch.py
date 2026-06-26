import yfinance as yf
import datetime
import pandas as pd
import numpy as np
import sqlite3
import sys
import csv

def get_stock_info(stocknum):
    df = yf.Ticker(stocknum)
    data = df.info
    print(data)
    pass

def import_info_db(stocknum):
    df = yf.Ticker(stocknum)
    try:
        profitMargins = df.info["profitMargins"]
    except:
        profitMargins = 0
    try:
        earningsGrowth = float(df.info["earningsGrowth"])
    except:
        earningsGrowth = 0
    try:
        debtToEquity = float(df.info["debtToEquity"])
    except:
        debtToEquity = 0
    try:
        totalCash = float(df.info["totalCash"])
    except:
        totalCash = 0
    try:
        totalDebt = float(df.info["totalDebt"])
    except:
        totalDebt = 0
    try:
        totalRevenue = float(df.info["totalRevenue"])
    except:
        totalRevenue = 0
    try:
        forwardEps = float(df.info["forwardEps"])
    except:
        forwardEps = 0
    try:
        marketCap = float(df.info["marketCap"])
    except:
        marketCap = 0
    try:
        freeCashflow = float(df.info["freeCashflow"])
    except:
        freeCashflow = 0
    try:
        returnOnAssets = float(df.info["returnOnAssets"])
    except:
        returnOnAssets = 0
    try:
        averageVolume10days = float(df.info["averageVolume10days"])
    except:
        averageVolume10days = 0
    try:
        fiftyTwoWeekHigh = float(df.info["fiftyTwoWeekHigh"])
    except:
        fiftyTwoWeekHigh = 0
    try:
        fiftyTwoWeekLow = float(df.info["fiftyTwoWeekLow"])
    except:
        fiftyTwoWeekLow = 0
    try:
        currentPrice = float(df.info["currentPrice"])
    except:
        currentPrice = 0

    n = (stocknum, profitMargins, earningsGrowth, debtToEquity, totalCash, totalDebt, totalRevenue, forwardEps, marketCap, freeCashflow, returnOnAssets, averageVolume10days, fiftyTwoWeekHigh, fiftyTwoWeekLow, currentPrice)
    return n

DATA_SCHEMA = """
CREATE TABLE IF NOT EXISTS data (
    stock TEXT,
    DT INTEGER,
    Date TEXT,
    Open REAL,
    Close REAL,
    High REAL,
    Low REAL,
    Volume REAL,
    PRIMARY KEY (DT, stock)
)
"""


def ensure_schema(conn):
    """Create the `data` table if it does not already exist."""
    conn.execute(DATA_SCHEMA)
    conn.commit()


def _rows_from_frame(stockname, df):
    """Convert a yfinance OHLCV DataFrame into insert tuples.

    Selects columns by **name** (robust to yfinance returning MultiIndex columns for a single
    ticker). Emits tuples in `data` storage order: (stock, DT, Date, Open, Close, High, Low,
    Volume). Recomputes High/Low as the max/min across O/C/H/L (sanity), and carries the prior
    close forward when an open is zero. Rows with a missing close are skipped.
    """
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)

    result = []
    prev_close = 0.0
    for i in range(len(df.index)):
        ts = df.index.values[i]
        dt = int((ts - np.datetime64('1970-01-01T00:00:00')) / np.timedelta64(1, 's'))
        date_str = pd.to_datetime(ts).strftime('%Y-%m-%d')

        close_raw = df["Close"].values[i]
        if close_raw is None or (isinstance(close_raw, float) and np.isnan(close_raw)):
            continue

        close = round(float(close_raw), 3)
        openprice = round(float(df["Open"].values[i]), 3)
        if openprice == 0:
            openprice = prev_close

        temp_high = round(float(df["High"].values[i]), 3)
        temp_low = round(float(df["Low"].values[i]), 3)
        prices = [openprice, close, temp_high, temp_low]
        high = max(prices)
        low = min(prices)

        try:
            volume = int(df["Volume"].values[i])
        except Exception:
            volume = 0

        result.append((stockname, dt, date_str, openprice, close, high, low, volume))
        prev_close = close

    return result


def import_prices_db(stockname, start_date='2021-01-01', end_date='2026-01-01', interval='1d'):
    """
    Fetch OHLCV for one ticker from yfinance and return `data`-table insert tuples.

    Parameters:
    start_date / end_date: ISO dates (YYYY-MM-DD).
    interval: bar frequency (e.g., '1d').

    Prices are split/dividend-adjusted (auto_adjust=True) — appropriate for multi-year ATH /
    momentum logic so corporate actions don't create spurious breakouts.
    """
    df = yf.download(stockname, start=start_date, end=end_date, interval=interval,
                     auto_adjust=True, progress=False)
    if df is None or len(df.index) == 0:
        return []
    return _rows_from_frame(stockname, df)

def getstring(fn):
    """
    To get the first column values in a list
    """
    result = []
    with open(fn, 'r', encoding='utf-8') as data:
        for line in csv.reader(data):
            stockcode = line[0]
            result.append(stockcode)
    return result

def load_all(dbfile, stockfile, start_date, end_date, interval='1d', buffer_size=30000):
    """Fetch every ticker in `stockfile` and bulk-insert into the `data` table of `dbfile`.

    Idempotent: uses INSERT OR IGNORE against the (DT, stock) primary key, so re-running tops up
    missing rows without duplicating. Returns the total number of rows inserted-or-ignored.
    """
    stocks = getstring(stockfile)
    conn = sqlite3.connect(dbfile)
    ensure_schema(conn)
    c = conn.cursor()
    insert_sql = ("insert or ignore into data (stock,DT,Date,Open,Close,High,Low,Volume) "
                  "values (?,?,?,?,?,?,?,?)")

    sqldata = []
    total = 0
    for stockname in stocks:
        try:
            data = import_prices_db(stockname, start_date=start_date, end_date=end_date,
                                    interval=interval)
        except Exception as ex:
            print(f'{stockname} FAILED: {ex}')
            continue

        sqldata.extend(data)
        total += len(data)
        if len(sqldata) >= buffer_size:
            c.executemany(insert_sql, sqldata)
            conn.commit()
            sqldata = []
        print(f'{stockname} is completed ({len(data)} bars)')

    if sqldata:
        c.executemany(insert_sql, sqldata)
        conn.commit()

    conn.close()
    return total


if __name__ == '__main__':
    import os

    here = os.path.dirname(os.path.abspath(__file__))
    stockfile = os.path.join(here, 'stock_list.txt')
    DBFILE = os.path.join(here, 'data.db')

    # ~5-year horizon ending today (PRD §1).
    end_date = datetime.date.today().isoformat()
    start_date = (datetime.date.today() - datetime.timedelta(days=5 * 365 + 2)).isoformat()

    total = load_all(DBFILE, stockfile, start_date, end_date, interval='1d')
    print(f'All completed! ~{total} bars fetched into {DBFILE}')