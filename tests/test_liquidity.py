"""Tests for turtle_rpm.liquidity: ADV, days_to_liquidate, max_purchase_by_liquidity."""

import unittest

import pandas as pd

from turtle_rpm.liquidity import (
    adv,
    liquidity_metrics,
    days_to_liquidate,
    max_purchase_by_liquidity,
    ADV_WINDOW_20,
    ADV_WINDOW_50,
    DEFAULT_MAX_DAYS_TO_EXIT,
    DEFAULT_PCT_ADV_PER_DAY,
)


def _daily_ohlcv(n_days: int, volume: float = 100_000.0, close: float = 50.0) -> pd.DataFrame:
    """Daily OHLCV with datetime index; Volume and Close as given."""
    idx = pd.date_range("2020-01-01", periods=n_days, freq="B")
    return pd.DataFrame(
        {
            "Open": [close] * n_days,
            "High": [close] * n_days,
            "Low": [close] * n_days,
            "Close": [close] * n_days,
            "Volume": [volume] * n_days,
        },
        index=idx,
    )


class TestAdv(unittest.TestCase):
    def test_adv_returns_mean_volume_over_window(self):
        vol = 100_000.0
        df = _daily_ohlcv(30, volume=vol)
        self.assertEqual(adv(df, 20), vol)
        self.assertEqual(adv(df, 50), None)  # only 30 rows

    def test_adv_returns_none_insufficient_data(self):
        df = _daily_ohlcv(10, volume=50_000.0)
        self.assertIsNone(adv(df, 20))

    def test_adv_returns_none_no_volume_column(self):
        idx = pd.date_range("2020-01-01", periods=25, freq="B")
        df = pd.DataFrame({"Close": [100.0] * 25}, index=idx)
        self.assertIsNone(adv(df, 20))

    def test_adv_returns_none_empty_df(self):
        df = pd.DataFrame()
        self.assertIsNone(adv(df, 20))

    def test_adv_returns_none_zero_volume(self):
        df = _daily_ohlcv(25, volume=0.0)
        self.assertIsNone(adv(df, 20))


class TestLiquidityMetrics(unittest.TestCase):
    def test_returns_adv_20_adv_50_and_latest_close(self):
        df = _daily_ohlcv(60, volume=80_000.0, close=25.0)
        m = liquidity_metrics(df)
        self.assertEqual(m["adv_20"], 80_000.0)
        self.assertEqual(m["adv_50"], 80_000.0)
        self.assertEqual(m["latest_close"], 25.0)
        self.assertEqual(m["dollar_adv_20"], 80_000.0 * 25.0)
        self.assertEqual(m["dollar_adv_50"], 80_000.0 * 25.0)

    def test_returns_none_for_insufficient_data(self):
        df = _daily_ohlcv(15, volume=50_000.0)
        m = liquidity_metrics(df)
        self.assertIsNone(m["adv_50"])
        self.assertIsNone(m["adv_20"])  # need 20 rows for adv_20
        self.assertEqual(m["latest_close"], 50.0)


class TestDaysToLiquidate(unittest.TestCase):
    def test_position_over_adv(self):
        self.assertAlmostEqual(days_to_liquidate(100_000, 50_000), 2.0)

    def test_position_under_adv(self):
        self.assertAlmostEqual(days_to_liquidate(10_000, 100_000), 0.1)

    def test_returns_none_when_adv_none(self):
        self.assertIsNone(days_to_liquidate(1000, None))

    def test_returns_none_when_adv_zero(self):
        self.assertIsNone(days_to_liquidate(1000, 0))


class TestMaxPurchaseByLiquidity(unittest.TestCase):
    def test_max_shares_and_dollar(self):
        # ADV 100k, 5 days, 25% per day => max_shares = 5 * 0.25 * 100k = 125_000
        df = _daily_ohlcv(30, volume=100_000.0, close=40.0)
        out = max_purchase_by_liquidity(
            df,
            max_days_to_exit=DEFAULT_MAX_DAYS_TO_EXIT,
            pct_adv_per_day=DEFAULT_PCT_ADV_PER_DAY,
            adv_window=20,
        )
        self.assertEqual(out["adv"], 100_000.0)
        self.assertEqual(out["latest_close"], 40.0)
        self.assertEqual(out["max_shares"], 125_000.0)
        self.assertEqual(out["max_dollar"], 125_000.0 * 40.0)
        self.assertEqual(out["days_to_exit_at_max"], DEFAULT_MAX_DAYS_TO_EXIT)

    def test_returns_none_fields_when_insufficient_data(self):
        df = _daily_ohlcv(5, volume=50_000.0)
        out = max_purchase_by_liquidity(df, adv_window=20)
        self.assertIsNone(out["max_shares"])
        self.assertIsNone(out["max_dollar"])
        self.assertIsNone(out["adv"])
