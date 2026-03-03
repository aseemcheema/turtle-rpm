"""
Big Picture: classify market days as distribution, stalling, or follow-through.

Uses daily OHLCV (Close, Volume) and day-over-day comparison. No UI; pure pandas.
"""

from __future__ import annotations

import pandas as pd

# Thresholds (percent): distribution = down > 0.2%; stalling = |chg| <= 0.2%; follow-through = up > 0.2%
DISTRIBUTION_THRESHOLD = 0.2
STALLING_BAND = 0.2

# Trading days per week (approximate)
TRADING_DAYS_PER_WEEK = 5


def classify_days(df_daily: pd.DataFrame) -> pd.DataFrame:
    """
    Classify each day as Distribution, Stalling, Follow-through, or none.

    Input: DataFrame with DatetimeIndex and columns Close, Volume (e.g. from get_daily_ohlcv).
    Adds columns: pct_change, volume_vs_prev, day_type.
    First row has no previous day -> day_type "".
    """
    if df_daily.empty or "Close" not in df_daily.columns:
        return df_daily.copy()
    df = df_daily[["Close"]].copy()
    if "Volume" in df_daily.columns:
        df["Volume"] = df_daily["Volume"].fillna(0.0)
    else:
        df["Volume"] = 0.0

    prev_close = df["Close"].shift(1)
    prev_volume = df["Volume"].shift(1)
    df["pct_change"] = (df["Close"] - prev_close) / prev_close * 100.0
    df["volume_vs_prev"] = pd.Series("", index=df.index, dtype=object)
    df.loc[df["Volume"] > prev_volume, "volume_vs_prev"] = "higher"
    df.loc[df["Volume"] <= prev_volume, "volume_vs_prev"] = "lower"

    df["day_type"] = ""
    vol_higher = df["Volume"] > prev_volume
    pct = df["pct_change"]
    df.loc[vol_higher & (pct < -DISTRIBUTION_THRESHOLD), "day_type"] = "Distribution"
    df.loc[vol_higher & (pct >= -STALLING_BAND) & (pct <= STALLING_BAND), "day_type"] = "Stalling"
    df.loc[vol_higher & (pct > DISTRIBUTION_THRESHOLD), "day_type"] = "Follow-through"

    return df


def get_days_in_window(classified: pd.DataFrame, weeks: int) -> pd.DataFrame:
    """
    Return the last `weeks` weeks of trading days from the classified DataFrame.

    classified must have DatetimeIndex. Returns sliced DataFrame (most recent at end).
    """
    if classified.empty or weeks <= 0:
        return classified.copy()
    n = min(weeks * TRADING_DAYS_PER_WEEK, len(classified))
    return classified.iloc[-n:].copy()
