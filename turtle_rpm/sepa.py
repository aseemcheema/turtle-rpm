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
# Trailing-high candidate: look back this many weeks for "highest high" when building current base
TRAILING_HIGH_LOOKBACK_WEEKS = 12
# Cup/Low cheat: minimum weeks when base is "current" (forming); completed bases still use 6
CUP_CHEAT_MIN_WEEKS_CURRENT = 5

# Pivot formation (tight consolidation near current price)
PIVOT_FORMING_MIN_DAYS = 3
PIVOT_FORMING_MAX_DAYS = 10
PIVOT_FORMING_MAX_RANGE_PCT = 8.0
PIVOT_TIGHT_CLOSES_DAYS = 3
PIVOT_TIGHT_CLOSES_MAX_PCT = 3.0


def pivot_forming(
    df_daily: pd.DataFrame,
    min_days: int = PIVOT_FORMING_MIN_DAYS,
    max_days: int = PIVOT_FORMING_MAX_DAYS,
    max_range_pct: float = PIVOT_FORMING_MAX_RANGE_PCT,
    tight_closes_days: int = PIVOT_TIGHT_CLOSES_DAYS,
    tight_closes_pct: float | None = PIVOT_TIGHT_CLOSES_MAX_PCT,
) -> dict[str, Any]:
    """
    Detect if a pivot (tight consolidation) is forming in the most recent bars.

    A pivot is 3–10 days of tight price action: high-to-low range < max_range_pct.
    Optional: last tight_closes_days have closes in a tight range (stronger signal).

    Returns dict: forming (bool), days (int | None), range_pct (float | None), tight_closes (bool),
    pivot_start_date (Timestamp | None), pivot_end_date (Timestamp | None), pivot_high (float | None) when forming.
    """
    empty_result: dict[str, Any] = {
        "forming": False,
        "days": None,
        "range_pct": None,
        "tight_closes": False,
        "pivot_start_date": None,
        "pivot_end_date": None,
        "pivot_high": None,
    }
    if df_daily.empty or len(df_daily) < min_days:
        return empty_result
    for col in ("High", "Low", "Close"):
        if col not in df_daily.columns:
            return empty_result
    tail = df_daily.tail(max_days)
    if len(tail) < min_days:
        return empty_result
    # Prefer longest qualifying window: try L from max_days down to min_days
    for L in range(min(len(tail), max_days), min_days - 1, -1):
        window = tail.tail(L)
        w_high = float(window["High"].max())
        w_low = float(window["Low"].min())
        if w_high <= 0:
            continue
        range_pct = (w_high - w_low) / w_high * 100.0
        if range_pct >= max_range_pct:
            continue
        tight_closes = False
        if tight_closes_pct is not None and L >= tight_closes_days:
            last_n = window.tail(tight_closes_days)
            closes = last_n["Close"]
            c_max = float(closes.max())
            c_min = float(closes.min())
            midpoint = (c_max + c_min) / 2.0
            if midpoint > 0:
                tight_pct = (c_max - c_min) / midpoint * 100.0
                tight_closes = tight_pct <= tight_closes_pct
        pivot_start = pd.Timestamp(window.index[0])
        pivot_end = pd.Timestamp(window.index[-1])
        return {
            "forming": True,
            "days": L,
            "range_pct": round(range_pct, 2),
            "tight_closes": tight_closes,
            "pivot_start_date": pivot_start,
            "pivot_end_date": pivot_end,
            "pivot_high": round(w_high, 2),
        }
    return empty_result


# Lookback for average volume comparison at pivot (days)
PIVOT_VOLUME_LOOKBACK_DAYS = 50


def pivot_in_base(pivot: dict[str, Any], bases: list[dict[str, Any]]) -> dict[str, Any] | None:
    """
    Return the base that contains the pivot window, or None.

    Pivot is "in" a base if the pivot window overlaps the base interval.
    If multiple bases overlap, prefer the one that contains pivot_end_date (typically the current base).
    """
    if not pivot.get("forming") or not bases:
        return None
    start_ts = pivot.get("pivot_start_date")
    end_ts = pivot.get("pivot_end_date")
    if start_ts is None or end_ts is None:
        return None
    start_ts = pd.Timestamp(start_ts)
    end_ts = pd.Timestamp(end_ts)
    containing = []
    for b in bases:
        b_start = pd.Timestamp(b["start_date"]) if b.get("start_date") is not None else None
        b_end = pd.Timestamp(b["end_date"]) if b.get("end_date") is not None else None
        if b_start is None or b_end is None:
            continue
        if start_ts <= b_end and end_ts >= b_start:
            containing.append(b)
    if not containing:
        return None
    # Prefer base that contains pivot end (current price)
    for b in containing:
        b_start = pd.Timestamp(b["start_date"])
        b_end = pd.Timestamp(b["end_date"])
        if b_start <= end_ts <= b_end:
            return b
    return containing[0]


def pivot_volume_vs_average(
    df_daily: pd.DataFrame,
    pivot: dict[str, Any],
    lookback_days: int = PIVOT_VOLUME_LOOKBACK_DAYS,
) -> str | None:
    """
    Compare mean volume over the pivot window to average volume over lookback.
    Returns "below", "above", or None if pivot not forming or no volume data.
    """
    if not pivot.get("forming") or df_daily.empty or "Volume" not in df_daily.columns:
        return None
    L = pivot.get("days")
    if L is None or L < 1:
        return None
    tail = df_daily.tail(max(lookback_days, L))
    if len(tail) < L:
        return None
    pivot_window = tail.tail(L)
    avg_lookback = tail["Volume"].mean()
    pivot_avg = pivot_window["Volume"].mean()
    if pd.isna(avg_lookback) or avg_lookback <= 0:
        return None
    if pd.isna(pivot_avg):
        return None
    return "below" if pivot_avg < avg_lookback else "above"


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
    is_current_base: bool = False,
) -> str | None:
    """
    Classify a candidate base into one of six types by duration and shape.
    Returns type name or None if no type matches. Priority: Power Play > Darvas > Cup completion > Low cheat > Cup w/ handle > Double bottom.
    When is_current_base is True, Cup/Low cheat are allowed for duration >= 5 weeks (forming base).
    """
    cup_range = prior_high - base_low
    lower_third_bound = base_low + cup_range / 3.0 if cup_range > 0 else base_low
    in_lower_third = latest_close <= lower_third_bound
    # Cup/Low cheat min weeks: 5 for current (forming) base, else 6
    cup_min_weeks = CUP_CHEAT_MIN_WEEKS_CURRENT if is_current_base else CUP_CHEAT_WEEKS[0]

    # Power Play: 2-6 weeks, prior 8-week gain >= 90%
    if POWER_PLAY_WEEKS[0] <= duration_weeks <= POWER_PLAY_WEEKS[1]:
        if prior_8wk_gain is not None and prior_8wk_gain >= POWER_PLAY_MIN_RUNUP:
            return "Power Play"

    # Darvas box: 4-6 weeks, tight (depth <= DARVAS_MAX_DEPTH_PCT)
    if DARVAS_WEEKS[0] <= duration_weeks <= DARVAS_WEEKS[1]:
        if depth_pct <= DARVAS_MAX_DEPTH_PCT:
            return "Darvas box"

    # Cup completion / Low cheat: cup_min_weeks to 52 weeks, single broad low, no handle
    if cup_min_weeks <= duration_weeks <= CUP_CHEAT_WEEKS[1] and not has_handle:
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

    # Fallback: if in cup range and we didn't classify, cup completion
    if cup_min_weeks <= duration_weeks <= CUP_CHEAT_WEEKS[1]:
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
    *,
    relax_uptrend_for_current_base: bool = True,
    debug: bool = False,
    pivot: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Detect SEPA bases from weekly and daily (with SMAs) DataFrames.

    Returns list of dicts: base_type, start_date, depth_pct, duration_weeks,
    end_date, prior_high, base_low, resistance, buy_point_date (or None),
    is_current (True for the base ending on the last week of data).
    Only includes bases that pass uptrend_at_date at base start (or at start-1 week for current base when relaxed).

    When relax_uptrend_for_current_base is True, for candidates ending on the last week we also accept
    uptrend at the week before base start if uptrend at base start fails.
    When debug is True, prints pivot highs/lows and per-candidate diagnostics to stdout.
    When pivot is provided and forming, adds a pivot-anchored candidate (last significant high before pivot window).
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

    if debug:
        print("=== Pivot highs (weekly) ===")
        for i in pivot_highs:
            print(f"  idx={i} date={df_weekly.index[i]}")
        print("=== Pivot lows (weekly) ===")
        for i in pivot_lows:
            print(f"  idx={i} date={df_weekly.index[i]}")

    # Collect (hi_idx, end_idx) for all candidates: from pivot highs, then trailing high, then pivot-anchored
    candidate_starts: list[tuple[int, int, str]] = []  # (hi_idx, end_idx, source)

    if pivot_highs:
        for hi_idx in pivot_highs:
            next_high_idx = next((i for i in pivot_highs if i > hi_idx), None)
            if next_high_idx is not None:
                end_idx = next_high_idx - 1
            else:
                end_idx = len(df_weekly) - 1
            if end_idx <= hi_idx:
                continue
            candidate_starts.append((hi_idx, end_idx, "pivot_high"))

    last_week_idx = len(df_weekly) - 1
    # Trailing-high candidate: week with highest high in last N weeks that is not already a pivot high
    lookback = min(TRAILING_HIGH_LOOKBACK_WEEKS, last_week_idx)
    if lookback >= 4:
        start_idx = max(0, last_week_idx - lookback)
        segment_trail = df_weekly.iloc[start_idx : last_week_idx + 1]
        max_high_val = segment_trail["High"].max()
        for j in range(len(segment_trail) - 1, -1, -1):
            if float(segment_trail["High"].iloc[j]) >= max_high_val - 1e-9:
                trailing_hi_idx = start_idx + j
                break
        else:
            trailing_hi_idx = start_idx
        if trailing_hi_idx not in pivot_highs and trailing_hi_idx <= last_week_idx - 4:
            if not any(c[0] == trailing_hi_idx and c[2] == "trailing_high" for c in candidate_starts):
                candidate_starts.append((trailing_hi_idx, last_week_idx, "trailing_high"))

    # Pivot-anchored candidate: when pivot is forming, base start = last significant high before pivot window
    if pivot and pivot.get("forming") and pivot.get("pivot_start_date") is not None:
        pivot_start = pd.Timestamp(pivot["pivot_start_date"])
        before_mask = df_weekly.index < pivot_start
        if before_mask.any():
            eligible = df_weekly.loc[before_mask]
            if len(eligible) >= 5:
                last_10 = eligible.tail(10)
                max_label = last_10["High"].idxmax()
                loc = df_weekly.index.get_loc(max_label)
                anchor_hi_idx = int(loc) if isinstance(loc, int) else int(loc.start)
                if not any(c[0] == anchor_hi_idx and c[2] == "pivot_anchored" for c in candidate_starts):
                    candidate_starts.append((anchor_hi_idx, last_week_idx, "pivot_anchored"))

    for hi_idx, end_idx, source in candidate_starts:
        prior_high = float(df_weekly["High"].iloc[hi_idx])
        start_ts = df_weekly.index[hi_idx]
        segment = df_weekly.iloc[hi_idx : end_idx + 1]
        base_low = float(segment["Low"].min())
        depth_pct = (prior_high - base_low) / prior_high * 100.0 if prior_high > 0 else 0.0
        duration_weeks = end_idx - hi_idx + 1
        latest_close = float(segment["Close"].iloc[-1])
        is_current_base = end_idx == last_week_idx
        cup_range = prior_high - base_low
        lower_third_bound = base_low + cup_range / 3.0 if cup_range > 0 else base_low
        in_lower_third = latest_close <= lower_third_bound
        lows_in_segment = [i for i in pivot_lows if hi_idx < i <= end_idx]
        two_lows = len(lows_in_segment) >= 2
        has_handle = False
        if len(lows_in_segment) >= 2:
            first_low = float(segment["Low"].min())
            mid_range = base_low + (prior_high - base_low) / 2
            second_low = float(df_weekly["Low"].iloc[lows_in_segment[1]])
            if second_low > mid_range and second_low > first_low:
                has_handle = True
        uptrend_ok = uptrend_at_date(df_daily, start_ts)
        if not uptrend_ok and is_current_base and relax_uptrend_for_current_base and hi_idx >= 1:
            prev_ts = df_weekly.index[hi_idx - 1]
            uptrend_ok = uptrend_at_date(df_daily, prev_ts)
        if debug:
            print(f"--- Candidate hi_idx={hi_idx} end_idx={end_idx} source={source} ---")
            print(f"  start_ts={start_ts} end_ts={df_weekly.index[end_idx]} duration_weeks={duration_weeks} depth_pct={depth_pct:.2f}")
            print(f"  base_low={base_low} latest_close={latest_close} in_lower_third={in_lower_third} has_handle={has_handle} two_lows={two_lows}")
            print(f"  uptrend_ok={uptrend_ok} -> ", end="")
        if not uptrend_ok:
            if debug:
                print("SKIP (uptrend)")
            continue
        low1 = float(df_weekly["Low"].iloc[lows_in_segment[0]]) if lows_in_segment else None
        low2 = float(df_weekly["Low"].iloc[lows_in_segment[1]]) if len(lows_in_segment) >= 2 else None
        prior_8wk_gain = None
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
            is_current_base=is_current_base,
        )
        if debug:
            print(f"base_type={base_type}")
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

    last_week = df_weekly.index[-1]
    # Deduplicate by start_date; when duplicate, prefer the one that extends to last week (current base)
    by_start: dict[pd.Timestamp, dict[str, Any]] = {}
    for b in results:
        st = b["start_date"]
        if isinstance(st, datetime):
            st = pd.Timestamp(st)
        end_ts = b["end_date"]
        if isinstance(end_ts, datetime):
            end_ts = pd.Timestamp(end_ts)
        b["is_current"] = end_ts == last_week
        if st not in by_start or b["is_current"]:
            by_start[st] = b
    return list(by_start.values())
