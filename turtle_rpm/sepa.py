"""
SEPA (Specific Entry Point Analysis) data layer and base detection.

Provides daily/weekly OHLC loaders, 50/150/200 SMA and uptrend checks,
and detection of six base types (cup completion cheat, low cheat, cup w/ handle,
double bottom, Darvas box, Power Play) with start date, depth %, and duration.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import pandas as pd
import pandas_ta as ta
import yfinance as yf

logger = logging.getLogger(__name__)

# Minimum trading days of history for 200d SMA and base detection
MIN_DAILY_BARS = 252
# 200d SMA must be rising over this many trading days (≈1 month)
UPTREND_SLOPE_DAYS = 21
# SMA "pointing up" comparison: compare to this many days ago
SMA_RISING_LOOKBACK = 5
# Pivot window: weeks on each side for swing high/low on weekly bars
PIVOT_WEEKS = 2

# Base type duration ranges (weeks): (min_weeks, max_weeks)
POWER_PLAY_WEEKS = (2, 6)
DARVAS_WEEKS = (4, 6)
CUP_CHEAT_WEEKS = (6, 52)
CUP_HANDLE_WEEKS = (7, 65)
DOUBLE_BOTTOM_WEEKS = (7, 65)
# Prior run-up for Power Play: minimum gain in prior 8 weeks (decimal)
POWER_PLAY_MIN_RUNUP = 0.90
# Double bottom: two lows within this fraction of each other (e.g. 0.05 = 5%)
DOUBLE_BOTTOM_LOW_TOLERANCE = 0.05
# Darvas: max depth as fraction of high to count as "tight" (e.g. 0.25 = 25%)
DARVAS_MAX_DEPTH_PCT = 25.0


def get_daily_ohlcv(symbol: str, years: int = 5) -> pd.DataFrame:
    """
    Fetch daily OHLCV for a symbol; return DataFrame with datetime index.

    Columns: Open, High, Low, Close, Volume.
    Returns empty DataFrame on error or insufficient data.
    """
    try:
        df = yf.download(
            symbol,
            period=f"{years}y",
            interval="1d",
            progress=False,
            auto_adjust=True,
        )
    except Exception as exc:
        logger.exception("Failed to download daily data for %s", symbol)
        return pd.DataFrame()
    if df.empty or len(df) < 2:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna().reset_index()
    date_col = df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    if df.empty:
        return pd.DataFrame()
    if hasattr(df[date_col].dtype, "tz") and df[date_col].dtype.tz is not None:
        df[date_col] = df[date_col].dt.tz_localize(None)
    df = df.set_index(date_col)
    df.index.name = "Date"
    required = ["Open", "High", "Low", "Close"]
    if not all(c in df.columns for c in required):
        return pd.DataFrame()
    df = df[required + (["Volume"] if "Volume" in df.columns else [])].copy()
    if "Volume" not in df.columns:
        df["Volume"] = 0.0
    return df.sort_index()


def to_weekly(df_daily: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate daily OHLC to weekly (week ending Friday).

    Weekly: open = first open, high = max high, low = min low, close = last close.
    Volume = sum if present. Index = last date of each week.
    """
    if df_daily.empty:
        return pd.DataFrame()
    # Week ending Friday: use period 'W-FRI'
    g = df_daily.resample("W-FRI")
    weekly = pd.DataFrame(
        {
            "Open": g["Open"].first(),
            "High": g["High"].max(),
            "Low": g["Low"].min(),
            "Close": g["Close"].last(),
        }
    )
    if "Volume" in df_daily.columns:
        weekly["Volume"] = g["Volume"].sum()
    return weekly.dropna(how="all")


def compute_smas(
    df: pd.DataFrame,
    windows: tuple[int, ...] = (50, 150, 200),
    close_col: str = "Close",
) -> pd.DataFrame:
    """Return a copy of the DataFrame with SMA columns added (non-mutating)."""
    out = df.copy()
    for w in windows:
        out[f"SMA_{w}"] = out[close_col].rolling(window=w, min_periods=w).mean()
    return out


def uptrend_at_date(df_daily: pd.DataFrame, date: pd.Timestamp | datetime) -> bool:
    """
    Return True if at the given date (or nearest prior trading day):
    - 200d SMA is rising over the last UPTREND_SLOPE_DAYS
    - 50d > 150d > 200d
    - All three SMAs are rising (vs SMA_RISING_LOOKBACK days ago).
    """
    if df_daily.empty or "SMA_200" not in df_daily.columns:
        return False
    if isinstance(date, datetime) and hasattr(date, "tzinfo") and date.tzinfo:
        date = pd.Timestamp(date).tz_localize(None)
    else:
        date = pd.Timestamp(date)
    # Nearest date at or before
    idx = df_daily.index[df_daily.index <= date]
    if len(idx) == 0:
        return False
    at_date = idx[-1]
    row = df_daily.loc[at_date]
    sma50, sma150, sma200 = row.get("SMA_50"), row.get("SMA_150"), row.get("SMA_200")
    if pd.isna(sma50) or pd.isna(sma150) or pd.isna(sma200):
        return False
    if not (sma50 > sma150 > sma200):
        return False
    # 200d rising over last UPTREND_SLOPE_DAYS
    pos = df_daily.index.get_loc(at_date)
    if pos < UPTREND_SLOPE_DAYS:
        return False
    sma200_now = df_daily["SMA_200"].iloc[pos]
    sma200_ago = df_daily["SMA_200"].iloc[pos - UPTREND_SLOPE_DAYS]
    if pd.isna(sma200_ago) or sma200_now <= sma200_ago:
        return False
    # All three rising vs SMA_RISING_LOOKBACK
    if pos < SMA_RISING_LOOKBACK:
        return True
    for name in ("SMA_50", "SMA_150", "SMA_200"):
        now_val = df_daily[name].iloc[pos]
        ago_val = df_daily[name].iloc[pos - SMA_RISING_LOOKBACK]
        if pd.isna(ago_val) or now_val <= ago_val:
            return False
    return True


def _pivot_highs_lows(df_weekly: pd.DataFrame) -> tuple[list[int], list[int]]:
    """Return (indices of pivot highs, indices of pivot lows)."""
    pivot_highs: list[int] = []
    pivot_lows: list[int] = []
    n = len(df_weekly)
    for i in range(n):
        left = max(0, i - PIVOT_WEEKS)
        right = min(n, i + PIVOT_WEEKS + 1)
        if df_weekly["High"].iloc[i] >= df_weekly["High"].iloc[left:right].max():
            pivot_highs.append(i)
        if df_weekly["Low"].iloc[i] <= df_weekly["Low"].iloc[left:right].min():
            pivot_lows.append(i)
    return pivot_highs, pivot_lows


def _classify_base(
    duration_weeks: int,
    depth_pct: float,
    prior_high: float,
    base_low: float,
    latest_close: float,
    two_lows: bool,
    low1: float | None,
    low2: float | None,
    has_handle: bool,
    prior_8wk_gain: float | None,
) -> str | None:
    """
    Classify a candidate base into one of six types by duration and shape.
    Returns type name or None if no type matches. Priority: Power Play > Darvas > Cup completion > Low cheat > Cup w/ handle > Double bottom.
    """
    cup_range = prior_high - base_low
    lower_third_bound = base_low + cup_range / 3.0 if cup_range > 0 else base_low
    in_lower_third = latest_close <= lower_third_bound

    # Power Play: 2-6 weeks, prior 8-week gain >= 90%
    if POWER_PLAY_WEEKS[0] <= duration_weeks <= POWER_PLAY_WEEKS[1]:
        if prior_8wk_gain is not None and prior_8wk_gain >= POWER_PLAY_MIN_RUNUP:
            return "Power Play"

    # Darvas box: 4-6 weeks, tight (depth <= DARVAS_MAX_DEPTH_PCT)
    if DARVAS_WEEKS[0] <= duration_weeks <= DARVAS_WEEKS[1]:
        if depth_pct <= DARVAS_MAX_DEPTH_PCT:
            return "Darvas box"

    # Cup completion / Low cheat: 6-52 weeks, single broad low, no handle
    if CUP_CHEAT_WEEKS[0] <= duration_weeks <= CUP_CHEAT_WEEKS[1] and not has_handle:
        if in_lower_third:
            return "Low cheat"
        return "Cup completion cheat"

    # Cup w/ handle: 7-65 weeks, two pullbacks
    if CUP_HANDLE_WEEKS[0] <= duration_weeks <= CUP_HANDLE_WEEKS[1] and has_handle:
        return "Cup w/ handle"

    # Double bottom: 7-65 weeks, two distinct lows at similar levels
    if DOUBLE_BOTTOM_WEEKS[0] <= duration_weeks <= DOUBLE_BOTTOM_WEEKS[1] and two_lows:
        if low1 is not None and low2 is not None and prior_high > 0:
            pct_diff = abs(low1 - low2) / prior_high
            if pct_diff <= DOUBLE_BOTTOM_LOW_TOLERANCE:
                return "Double bottom"

    # Fallback: if 6-52 and we didn't classify, cup completion
    if CUP_CHEAT_WEEKS[0] <= duration_weeks <= CUP_CHEAT_WEEKS[1]:
        return "Cup completion cheat"
    if CUP_HANDLE_WEEKS[0] <= duration_weeks <= CUP_HANDLE_WEEKS[1]:
        return "Cup w/ handle"
    return None


def _resistance_for_base(
    base_type: str,
    segment: pd.DataFrame,
    prior_high: float,
    df_weekly: pd.DataFrame,
    hi_idx: int,
    end_idx: int,
    lows_in_segment: list[int],
    has_handle: bool,
) -> float:
    """
    Resistance level used for buy point (breakout above this = buy signal).
    - Cup w/ handle: handle high (max High from second low to end).
    - Double bottom: neckline = max High between the two lows.
    - Darvas: consolidation high = max High in segment.
    - Cup completion / Low cheat / Power Play: prior_high (left rim).
    """
    if base_type == "Cup w/ handle" and has_handle and len(lows_in_segment) >= 2:
        second_low_idx = lows_in_segment[1]
        handle_segment = df_weekly.iloc[second_low_idx : end_idx + 1]
        return float(handle_segment["High"].max())
    if base_type == "Double bottom" and len(lows_in_segment) >= 2:
        i0, i1 = lows_in_segment[0], lows_in_segment[1]
        between = df_weekly.iloc[i0 : i1 + 1]
        return float(between["High"].max())
    if base_type == "Darvas box":
        return float(segment["High"].max())
    # Cup completion cheat, Low cheat, Power Play: prior_high
    return prior_high


def _vcp_like(
    segment: pd.DataFrame,
    lows_in_segment: list[int],
    prior_high: float,
    df_weekly: pd.DataFrame,
    df_daily: pd.DataFrame | None = None,
    start_ts: pd.Timestamp | None = None,
    end_ts: pd.Timestamp | None = None,
) -> bool:
    """
    VCP-style: (1) Last two pullbacks have decreasing depth; (2) volume dries up on pullbacks;
    (3) if daily data with ATR is provided, volatility contracts (ATR at end of base < ATR at start).
    Returns True when all applicable conditions hold.
    """
    if prior_high <= 0:
        return False
    # Decreasing pullback depths: depth from prior_high to each pivot low, in order; each should be <= previous
    depths: list[float] = []
    for i in lows_in_segment:
        low = float(df_weekly["Low"].iloc[i])
        d = (prior_high - low) / prior_high * 100.0
        depths.append(d)
    decreasing = True
    for k in range(1, len(depths)):
        if depths[k] >= depths[k - 1]:
            decreasing = False
            break
    if not decreasing or len(depths) < 2:
        return False
    # Volume dry-up: avg volume on down weeks < avg volume on up weeks
    if "Volume" not in segment.columns:
        volume_ok = True
    else:
        up_weeks = segment["Close"] >= segment["Open"]
        down_vol = segment.loc[~up_weeks, "Volume"].mean()
        up_vol = segment.loc[up_weeks, "Volume"].mean()
        if pd.isna(down_vol) or pd.isna(up_vol) or up_vol <= 0:
            volume_ok = True
        else:
            volume_ok = float(down_vol) < float(up_vol)
    if not volume_ok:
        return False
    # ATR contraction (pandas-ta): require ATR at end of base < ATR at start when daily ATR is available
    if df_daily is not None and "ATR" in df_daily.columns and start_ts is not None and end_ts is not None:
        in_range = df_daily.loc[(df_daily.index >= start_ts) & (df_daily.index <= end_ts)]
        if not in_range.empty and in_range["ATR"].notna().any():
            atr_start = in_range["ATR"].iloc[0]
            atr_end = in_range["ATR"].iloc[-1]
            if pd.notna(atr_start) and pd.notna(atr_end) and atr_start > 0:
                if float(atr_end) >= float(atr_start):
                    return False
    return True


def _buy_point_date(
    df_weekly: pd.DataFrame,
    start_idx: int,
    end_idx: int,
    resistance: float,
) -> pd.Timestamp | None:
    """
    First week (in range start_idx..end_idx inclusive) where Close >= resistance.
    Backward-looking: no future data. Returns None if never triggered.
    """
    for i in range(start_idx, end_idx + 1):
        if i >= len(df_weekly):
            break
        close = float(df_weekly["Close"].iloc[i])
        if close >= resistance:
            return df_weekly.index[i]
    return None


def find_bases(
    df_weekly: pd.DataFrame,
    df_daily: pd.DataFrame,
) -> list[dict[str, Any]]:
    """
    Detect SEPA bases from weekly and daily (with SMAs) DataFrames.

    Returns list of dicts: base_type, start_date, depth_pct, duration_weeks,
    end_date, prior_high, base_low, resistance, buy_point_date (or None),
    is_current (True for the base ending on the last week of data).
    Only includes bases that pass uptrend_at_date at base start.
    """
    results: list[dict[str, Any]] = []
    if df_weekly.empty or len(df_weekly) < 4:
        return results
    if len(df_daily) < MIN_DAILY_BARS:
        return results
    # Add ATR (pandas-ta) for VCP volatility-contraction check
    df_daily_atr = df_daily.copy()
    atr_series = ta.atr(
        high=df_daily_atr["High"],
        low=df_daily_atr["Low"],
        close=df_daily_atr["Close"],
        length=14,
    )
    df_daily_atr["ATR"] = atr_series
    pivot_highs, pivot_lows = _pivot_highs_lows(df_weekly)
    if not pivot_highs:
        return results

    # Build candidate bases: from each pivot high, find subsequent low(s) and measure depth/duration
    for hi_idx in pivot_highs:
        prior_high = float(df_weekly["High"].iloc[hi_idx])
        start_ts = df_weekly.index[hi_idx]
        # End of base: next pivot high after hi_idx, or last week
        next_high_idx = next((i for i in pivot_highs if i > hi_idx), None)
        if next_high_idx is not None:
            end_idx = next_high_idx - 1
        else:
            end_idx = len(df_weekly) - 1
        if end_idx <= hi_idx:
            continue
        segment = df_weekly.iloc[hi_idx : end_idx + 1]
        base_low = float(segment["Low"].min())
        depth_pct = (prior_high - base_low) / prior_high * 100.0 if prior_high > 0 else 0.0
        duration_weeks = end_idx - hi_idx + 1
        latest_close = float(segment["Close"].iloc[-1])

        # Uptrend at base start (use first day of that week for daily lookup)
        if not uptrend_at_date(df_daily, start_ts):
            continue

        # Shape heuristics: two lows? handle? prior 8-week run-up?
        lows_in_segment = [i for i in pivot_lows if hi_idx < i <= end_idx]
        two_lows = len(lows_in_segment) >= 2
        low1 = float(df_weekly["Low"].iloc[lows_in_segment[0]]) if lows_in_segment else None
        low2 = float(df_weekly["Low"].iloc[lows_in_segment[1]]) if len(lows_in_segment) >= 2 else None
        # Handle: second, smaller pullback in upper portion (simplified: two pivot lows with second in upper half of range)
        has_handle = False
        if len(lows_in_segment) >= 2:
            first_low = float(segment["Low"].min())
            mid_range = base_low + (prior_high - base_low) / 2
            second_low_idx = lows_in_segment[1]
            second_low = float(df_weekly["Low"].iloc[second_low_idx])
            if second_low > mid_range and second_low > first_low:
                has_handle = True
        # Prior 8-week gain: close 8 weeks before start vs prior_high
        prior_8wk_gain: float | None = None
        if hi_idx >= 8:
            close_8_ago = float(df_weekly["Close"].iloc[hi_idx - 8])
            if close_8_ago > 0:
                prior_8wk_gain = (prior_high - close_8_ago) / close_8_ago

        base_type = _classify_base(
            duration_weeks=duration_weeks,
            depth_pct=depth_pct,
            prior_high=prior_high,
            base_low=base_low,
            latest_close=latest_close,
            two_lows=two_lows,
            low1=low1,
            low2=low2,
            has_handle=has_handle,
            prior_8wk_gain=prior_8wk_gain,
        )
        if base_type is None:
            continue
        end_ts = df_weekly.index[end_idx]
        resistance = _resistance_for_base(
            base_type=base_type,
            segment=segment,
            prior_high=prior_high,
            df_weekly=df_weekly,
            hi_idx=hi_idx,
            end_idx=end_idx,
            lows_in_segment=lows_in_segment,
            has_handle=has_handle,
        )
        buy_point_date = _buy_point_date(df_weekly, hi_idx, end_idx, resistance)
        # Distance to buy point: % below resistance; 0 if already at/above
        if buy_point_date is not None or resistance <= 0:
            distance_pct = 0.0
        else:
            distance_pct = (resistance - latest_close) / resistance * 100.0
        vcp_like = _vcp_like(
            segment, lows_in_segment, prior_high, df_weekly,
            df_daily=df_daily_atr, start_ts=start_ts, end_ts=end_ts,
        )
        results.append({
            "base_type": base_type,
            "start_date": start_ts,
            "depth_pct": round(depth_pct, 2),
            "duration_weeks": duration_weeks,
            "end_date": end_ts,
            "prior_high": prior_high,
            "base_low": base_low,
            "resistance": round(resistance, 2),
            "buy_point_date": buy_point_date,
            "distance_pct": round(distance_pct, 2),
            "vcp_like": vcp_like,
        })

    # Deduplicate by start_date (keep first/base type by priority already in _classify_base)
    seen_starts: set[pd.Timestamp] = set()
    unique: list[dict[str, Any]] = []
    for b in results:
        st = b["start_date"]
        if isinstance(st, datetime):
            st = pd.Timestamp(st)
        if st not in seen_starts:
            seen_starts.add(st)
            unique.append(b)
    last_week = df_weekly.index[-1]
    for b in unique:
        end_ts = b["end_date"]
        if isinstance(end_ts, datetime):
            end_ts = pd.Timestamp(end_ts)
        b["is_current"] = end_ts == last_week
    return unique
