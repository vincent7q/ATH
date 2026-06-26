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

def import_prices_db(stockname, start_date='2025-02-19', end_date='2025-02-20', interval='1d'):
    """
    Parameters:
    start_date: Start date for data retrieval (e.g., '2025-02-19')
    end_date: End date for data retrieval (e.g., '2025-02-20')
    interval: Frequency (e.g., '1d')
    """
    # Fetch data for the specified date range
    df = yf.download(stockname, start=start_date, end=end_date, interval=interval)

    length = len(df.index)
    close = 0
    result = []

    for i in range(0, length):
        date = df.index.values[i]
        dt = int((date - np.datetime64('1970-01-01T00:00:00')) / np.timedelta64(1, 's'))
        date = pd.to_datetime(date)

        # Filter for only 2025-02-19
        # if date.strftime('%Y-%m-%d') == '2025-02-19':
        #     continue

        if df.values[i][0] is None:
            continue

        openprice = round(df.values[i][3], 3)
        if openprice == 0:
            openprice = close  # If open price is zero, assign previous day close value to it

        temp_high = round(df.values[i][1], 3)
        temp_low = round(df.values[i][2], 3)
        close = round(df.values[i][0], 3)

        temp = [openprice, temp_high, temp_low, close]
        high = max(temp)
        low = min(temp)

        try:
            volume = int(df.values[i][4])
        except Exception:
            volume = 0

        n = (stockname, dt, date.strftime('%Y-%m-%d'), openprice, close, high, low, volume)
        result.append(n)

    return result

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

if __name__ == '__main__':

    #production 
    import os
    import sys


    if os.name in 'nt':

        stockfile = r'C:\Users\vince\source\ATH\src\stock_list.txt'  # stocks
        DBFILE = r'C:\Users\vince\source\ATH\src\stocks.db'


    stocks = getstring(stockfile)

    # Stock prices import for 2025-02-19
    sqldata = []
    buffer_size = 30000
    conn = sqlite3.connect(DBFILE)
    c = conn.cursor()

    for stockname in stocks:
        data = import_prices_db(stockname, start_date='2025-05-22', end_date='2025-05-28', interval='1d')
        sqldata.extend(data)

        if len(sqldata) >= buffer_size:
            c.executemany("insert into data (stock,DT,Date,Open,Close,High,Low,Volume) values (?,?,?,?,?,?,?,?)", sqldata[::])
            conn.commit()
            sqldata = []

        print(f'{stockname} is completed')

    if len(sqldata) > 0:
        c.executemany("insert into data (stock,DT,Date,Open,Close,High,Low,Volume) values (?,?,?,?,?,?,?,?)", sqldata[::])
        conn.commit()

    conn.close()
    print("All completed!")