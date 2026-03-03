"""Tests for turtle_rpm.big_picture: classify_days, get_days_in_window."""

import unittest
import pandas as pd

from turtle_rpm.big_picture import (
    TRADING_DAYS_PER_WEEK,
    classify_days,
    get_days_in_window,
)


def _daily_df(dates, close_values, volumes):
    """Build daily DataFrame with Date index, Close and Volume columns."""
    return pd.DataFrame(
        {"Close": close_values, "Volume": volumes},
        index=pd.DatetimeIndex(dates, name="Date"),
    )


class TestClassifyDays(unittest.TestCase):
    def test_empty_returns_copy(self):
        df = pd.DataFrame()
        out = classify_days(df)
        self.assertTrue(out.empty)
        self.assertIsNot(out, df)

    def test_no_close_column_returns_copy(self):
        df = pd.DataFrame({"Volume": [100.0]}, index=pd.DatetimeIndex(["2024-01-01"], name="Date"))
        out = classify_days(df)
        self.assertEqual(len(out), 1)
        self.assertIsNot(out, df)
        self.assertNotIn("day_type", out.columns)

    def test_first_row_has_no_day_type(self):
        # Two days: first has no prev
        df = _daily_df(
            ["2024-01-01", "2024-01-02"],
            [100.0, 101.0],
            [1000.0, 1100.0],
        )
        out = classify_days(df)
        self.assertEqual(out["day_type"].iloc[0], "")
        self.assertIn(out["day_type"].iloc[1], ("Follow-through", "Stalling", "Distribution", ""))

    def test_distribution_volume_up_price_down_more_than_02(self):
        # Day 2: close down 0.3%, volume higher -> Distribution
        df = _daily_df(
            ["2024-01-01", "2024-01-02"],
            [100.0, 99.7],
            [1000.0, 1500.0],
        )
        out = classify_days(df)
        self.assertEqual(out["day_type"].iloc[1], "Distribution")

    def test_stalling_volume_up_price_flat(self):
        # Day 2: close up 0.1%, volume higher -> Stalling (|chg| <= 0.2)
        df = _daily_df(
            ["2024-01-01", "2024-01-02"],
            [100.0, 100.1],
            [1000.0, 1500.0],
        )
        out = classify_days(df)
        self.assertEqual(out["day_type"].iloc[1], "Stalling")

    def test_follow_through_volume_up_price_up_more_than_02(self):
        # Day 2: close up 0.5%, volume higher -> Follow-through
        df = _daily_df(
            ["2024-01-01", "2024-01-02"],
            [100.0, 100.5],
            [1000.0, 1500.0],
        )
        out = classify_days(df)
        self.assertEqual(out["day_type"].iloc[1], "Follow-through")

    def test_volume_lower_than_prev_no_day_type(self):
        # Day 2: close up 0.5% but volume lower -> no classification
        df = _daily_df(
            ["2024-01-01", "2024-01-02"],
            [100.0, 100.5],
            [1000.0, 500.0],
        )
        out = classify_days(df)
        self.assertEqual(out["day_type"].iloc[1], "")

    def test_adds_pct_change_volume_vs_prev(self):
        df = _daily_df(
            ["2024-01-01", "2024-01-02"],
            [100.0, 101.0],
            [1000.0, 1100.0],
        )
        out = classify_days(df)
        self.assertIn("pct_change", out.columns)
        self.assertIn("volume_vs_prev", out.columns)
        self.assertIn("day_type", out.columns)
        self.assertEqual(out["volume_vs_prev"].iloc[1], "higher")


class TestGetDaysInWindow(unittest.TestCase):
    def test_returns_last_n_trading_days(self):
        n = 40
        idx = pd.date_range("2024-01-01", periods=n, freq="B")
        df = pd.DataFrame({"Close": [100.0] * n, "Volume": [1000.0] * n}, index=idx)
        for weeks, expected in ((2, 10), (4, 20), (6, 30)):
            out = get_days_in_window(df, weeks)
            self.assertEqual(len(out), min(weeks * TRADING_DAYS_PER_WEEK, n), f"weeks={weeks}")

    def test_empty_returns_copy(self):
        df = pd.DataFrame()
        out = get_days_in_window(df, 2)
        self.assertTrue(out.empty)

    def test_weeks_zero_returns_copy(self):
        df = pd.DataFrame({"Close": [100.0], "Volume": [1000.0]}, index=pd.DatetimeIndex(["2024-01-01"]))
        out = get_days_in_window(df, 0)
        self.assertEqual(len(out), 1)
