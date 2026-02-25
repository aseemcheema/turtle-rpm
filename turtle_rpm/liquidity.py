"""
Liquidity risk metrics for position sizing.

Computes average daily volume (ADV), days-to-liquidate for a position,
and max purchase (shares and dollar) so that exit stays within an acceptable
number of days at a given % of ADV per day. Feeds into SEPA and position sizing.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

# ADV lookback windows (trading days)
ADV_WINDOW_20 = 20
ADV_WINDOW_50 = 50
# Defaults for max purchase: exit within N days, trading up to this % of ADV per day
DEFAULT_MAX_DAYS_TO_EXIT = 5
DEFAULT_PCT_ADV_PER_DAY = 0.25


def adv(df_daily: pd.DataFrame, window_days: int = ADV_WINDOW_20) -> float | None:
    """
    Average daily volume (shares) over the last window_days trading days.

    Returns None if insufficient data, no Volume column, or all-zero volume.
    """
    if df_daily.empty or "Volume" not in df_daily.columns or len(df_daily) < window_days:
        return None
    tail = df_daily["Volume"].tail(window_days)
    if tail.isna().all() or (tail <= 0).all():
        return None
    mean_vol = float(tail.mean())
    return mean_vol if mean_vol > 0 else None


def liquidity_metrics(
    df_daily: pd.DataFrame,
    adv_20: bool = True,
    adv_50: bool = True,
    include_dollar_adv: bool = True,
) -> dict[str, Any]:
    """
    Liquidity metrics from daily OHLCV: ADV (20d, 50d), latest price, optional dollar ADV.

    Returns dict: adv_20, adv_50, latest_close; and if include_dollar_adv:
    dollar_adv_20, dollar_adv_50 (ADV * latest_close). Missing values are None.
    """
    out: dict[str, Any] = {
        "adv_20": None,
        "adv_50": None,
        "latest_close": None,
    }
    if include_dollar_adv:
        out["dollar_adv_20"] = None
        out["dollar_adv_50"] = None

    if df_daily.empty or "Close" not in df_daily.columns:
        return out

    latest_close = float(df_daily["Close"].iloc[-1])
    out["latest_close"] = latest_close

    if adv_20:
        a20 = adv(df_daily, ADV_WINDOW_20)
        out["adv_20"] = a20
        if include_dollar_adv and a20 is not None:
            out["dollar_adv_20"] = a20 * latest_close
    if adv_50:
        a50 = adv(df_daily, ADV_WINDOW_50)
        out["adv_50"] = a50
        if include_dollar_adv and a50 is not None:
            out["dollar_adv_50"] = a50 * latest_close

    return out


def days_to_liquidate(position_shares: float, adv: float | None) -> float | None:
    """
    Number of days to liquidate position at one full ADV per day.

    position_shares / adv. Returns None if adv is None or <= 0.
    """
    if adv is None or adv <= 0 or position_shares < 0:
        return None
    return position_shares / adv


def max_purchase_by_liquidity(
    df_daily: pd.DataFrame,
    max_days_to_exit: int = DEFAULT_MAX_DAYS_TO_EXIT,
    pct_adv_per_day: float = DEFAULT_PCT_ADV_PER_DAY,
    adv_window: int = ADV_WINDOW_20,
) -> dict[str, Any]:
    """
    Max purchase (shares and dollar) so that exiting at pct_adv_per_day of ADV per day
    keeps days-to-exit <= max_days_to_exit. This is the liquidity-based limit for position sizing.

    Returns dict: max_shares, max_dollar, adv, days_to_exit_at_max, latest_close.
    Missing/invalid data yields None for numeric fields.
    """
    out: dict[str, Any] = {
        "max_shares": None,
        "max_dollar": None,
        "adv": None,
        "days_to_exit_at_max": None,
        "latest_close": None,
    }
    adv_val = adv(df_daily, adv_window)
    if adv_val is None or adv_val <= 0:
        return out
    if df_daily.empty or "Close" not in df_daily.columns:
        return out

    latest_close = float(df_daily["Close"].iloc[-1])
    max_shares = max_days_to_exit * pct_adv_per_day * adv_val
    max_dollar = max_shares * latest_close

    out["adv"] = adv_val
    out["latest_close"] = latest_close
    out["max_shares"] = max_shares
    out["max_dollar"] = max_dollar
    out["days_to_exit_at_max"] = max_days_to_exit
    return out
