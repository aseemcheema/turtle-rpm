"""Tests for turtle_rpm.sepa: SMA, uptrend, to_weekly."""

import unittest
import pandas as pd

from turtle_rpm.sepa import (
    compute_smas,
    to_weekly,
    uptrend_at_date,
    UPTREND_SLOPE_DAYS,
)


class TestComputeSmas(unittest.TestCase):
    def test_adds_sma_columns(self):
        n = 300
        idx = pd.date_range("2020-01-01", periods=n, freq="B")
        df = pd.DataFrame(
            {"Close": 100.0 + pd.Series(range(n), index=idx).astype(float)},
            index=idx,
        )
        out = compute_smas(df, windows=(50, 150, 200))
        self.assertIn("SMA_50", out.columns)
        self.assertIn("SMA_150", out.columns)
        self.assertIn("SMA_200", out.columns)
        self.assertEqual(len(out), len(df))
        # First 49 rows SMA_50 is NaN, row 49 (0-indexed) has first value
        self.assertTrue(pd.isna(out["SMA_50"].iloc[48]))
        self.assertFalse(pd.isna(out["SMA_50"].iloc[49]))
        self.assertAlmostEqual(out["SMA_50"].iloc[49], df["Close"].iloc[:50].mean())

    def test_does_not_mutate_input(self):
        df = pd.DataFrame({"Close": [100.0] * 250}, index=pd.date_range("2020-01-01", periods=250, freq="B"))
        compute_smas(df)
        self.assertNotIn("SMA_50", df.columns)


class TestUptrendAtDate(unittest.TestCase):
    def test_returns_false_without_sma_columns(self):
        df = pd.DataFrame(
            {"Close": [100.0] * 300},
            index=pd.date_range("2020-01-01", periods=300, freq="B"),
        )
        self.assertFalse(uptrend_at_date(df, df.index[250]))

    def test_returns_true_when_50_150_200_aligned_and_rising(self):
        n = 400
        idx = pd.date_range("2020-01-01", periods=n, freq="B")
        # Upward-sloping close so SMAs are in order and rising
        close = 100.0 + 0.5 * pd.Series(range(n), index=idx).astype(float)
        df = pd.DataFrame({"Close": close}, index=idx)
        df = compute_smas(df)
        # Pick a date well after 200 so all SMAs are valid
        at = df.index[300]
        self.assertTrue(uptrend_at_date(df, at))

    def test_returns_false_when_200d_not_rising(self):
        n = 400
        idx = pd.date_range("2020-01-01", periods=n, freq="B")
        # Flat then down: first 250 up, then flat/down so 200d SMA starts falling
        close = [100.0 + i * 0.2 for i in range(250)]
        close += [100.0 + 250 * 0.2 - (i - 250) * 0.1 for i in range(250, n)]
        df = pd.DataFrame({"Close": close}, index=idx)
        df = compute_smas(df)
        # At end, 200d SMA may be falling (we have 100 days of decline)
        at = df.index[-1]
        # If 200d slope over last UPTREND_SLOPE_DAYS is negative, uptrend_at_date should be False
        sma200_now = df["SMA_200"].iloc[-1]
        sma200_ago = df["SMA_200"].iloc[-1 - UPTREND_SLOPE_DAYS]
        if sma200_now <= sma200_ago:
            self.assertFalse(uptrend_at_date(df, at))


class TestToWeekly(unittest.TestCase):
    def test_aggregates_daily_to_weekly(self):
        # 3 weeks of daily data
        idx = pd.date_range("2020-01-06", periods=15, freq="B")  # Mon-Fri
        df = pd.DataFrame(
            {
                "Open": [10.0] * 15,
                "High": [12.0 + i for i in range(15)],
                "Low": [8.0] * 15,
                "Close": [11.0 + i for i in range(15)],
            },
            index=idx,
        )
        weekly = to_weekly(df)
        self.assertFalse(weekly.empty)
        self.assertLessEqual(len(weekly), 4)
        self.assertEqual(list(weekly.columns), ["Open", "High", "Low", "Close"])

    def test_returns_empty_for_empty_input(self):
        self.assertTrue(to_weekly(pd.DataFrame()).empty)


if __name__ == "__main__":
    unittest.main()
