"""Indicator unit tests — hand-computed expected values (TDD: written before src/indicators.py)."""
import numpy as np
import pandas as pd
import pytest

import indicators


def test_rolling_high_excludes_today():
    # Roll_Max_t = max of the PRIOR `window` closes, NOT including today.
    close = pd.Series([10.0, 11.0, 12.0, 13.0])
    result = indicators.rolling_high(close, window=2)
    # t0,t1 -> NaN (not enough prior bars); t2 -> max(10,11)=11; t3 -> max(11,12)=12
    np.testing.assert_allclose(result.to_numpy(), [np.nan, np.nan, 11.0, 12.0], equal_nan=True)


def test_rolling_high_strict_window_nan_until_full():
    close = pd.Series(np.arange(1.0, 11.0))  # 10 bars
    result = indicators.rolling_high(close, window=5)
    # first 5 entries NaN (need 5 prior closes), then values appear
    assert result.iloc[:5].isna().all()
    assert not result.iloc[5:].isna().any()


def test_atr_wilder_small_series():
    high = pd.Series([10.0, 12.0, 11.0, 13.0])
    low = pd.Series([9.0, 10.0, 9.0, 11.0])
    close = pd.Series([9.0, 11.0, 10.0, 12.0])
    # TR: t0=nan; t1=max(2,3,1)=3; t2=max(2,0,2)=2; t3=max(2,3,1)=3
    # period=2: seed atr[2]=mean(3,2)=2.5; atr[3]=(2.5*1+3)/2=2.75
    result = indicators.atr_wilder(high, low, close, period=2)
    np.testing.assert_allclose(result.to_numpy(), [np.nan, np.nan, 2.5, 2.75], equal_nan=True)


def test_avg_dollar_volume_trailing_window_includes_today():
    close = pd.Series([10.0, 20.0, 30.0])
    volume = pd.Series([1.0, 2.0, 3.0])
    # dollar vol = [10, 40, 90]; trailing 2-bar mean = [nan, 25, 65]
    result = indicators.avg_dollar_volume(close, volume, window=2)
    np.testing.assert_allclose(result.to_numpy(), [np.nan, 25.0, 65.0], equal_nan=True)


def test_days_since_ipo_is_one_based_bar_count():
    result = indicators.days_since_ipo(4)
    np.testing.assert_array_equal(result, [1, 2, 3, 4])
