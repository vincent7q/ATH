"""Tests for the yfinance->rows parsing in stock_data_fetch (no network).

Verifies name-based column parsing (robust to yfinance MultiIndex columns) and that the emitted
tuple order matches the `data` table insert: (stock, DT, Date, Open, Close, High, Low, Volume).
"""
import numpy as np
import pandas as pd

import stock_data_fetch as sdf


def _flat_frame():
    idx = pd.DatetimeIndex(["2021-01-04", "2021-01-05"])
    return pd.DataFrame(
        {"Open": [10.0, 11.0], "High": [12.0, 13.0], "Low": [9.0, 10.0],
         "Close": [11.0, 12.0], "Volume": [1000, 2000]}, index=idx,
    )


def test_rows_from_flat_frame_order_and_values():
    rows = sdf._rows_from_frame("AAA", _flat_frame())
    assert len(rows) == 2
    stock, dt, date, openp, close, high, low, volume = rows[0]
    assert stock == "AAA"
    assert date == "2021-01-04"
    assert (openp, close) == (10.0, 11.0)
    assert high == 12.0 and low == 9.0          # max/min across O,C,H,L
    assert volume == 1000


def test_rows_from_multiindex_frame():
    idx = pd.DatetimeIndex(["2021-01-04"])
    cols = pd.MultiIndex.from_tuples(
        [("Open", "AAA"), ("High", "AAA"), ("Low", "AAA"), ("Close", "AAA"), ("Volume", "AAA")])
    df = pd.DataFrame([[10.0, 12.0, 9.0, 11.0, 1000]], index=idx, columns=cols)
    rows = sdf._rows_from_frame("AAA", df)
    assert rows[0][4] == 11.0                    # Close
    assert rows[0][7] == 1000                    # Volume


def test_rows_skip_nan_close():
    idx = pd.DatetimeIndex(["2021-01-04", "2021-01-05"])
    df = pd.DataFrame(
        {"Open": [10.0, 11.0], "High": [12.0, 13.0], "Low": [9.0, 10.0],
         "Close": [np.nan, 12.0], "Volume": [1000, 2000]}, index=idx,
    )
    rows = sdf._rows_from_frame("AAA", df)
    assert len(rows) == 1
    assert rows[0][2] == "2021-01-05"
