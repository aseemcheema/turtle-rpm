"""
Minervini leadership profile: 52-week high/low, Trend Template (8 criteria), RS vs SPY.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import yfinance as yf

from turtle_rpm.sepa import UPTREND_SLOPE_DAYS

TRADING_DAYS_52W = 252


def add_52w_high_low(df_daily: pd.DataFrame) -> pd.DataFrame:
    """Add High_52w and Low_52w (rolling 252-day max/min). Non-mutating."""
    out = df_daily.copy()
    out["High_52w"] = out["High"].rolling(window=TRADING_DAYS_52W, min_periods=1).max()
    out["Low_52w"] = out["Low"].rolling(window=TRADING_DAYS_52W, min_periods=1).min()
    return out


def _trend_template_at_row(
    df_daily: pd.DataFrame,
    pos: int,
    rs_ratio: float | None,
) -> tuple[int, list[dict[str, Any]]]:
    """Evaluate Trend Template 8 criteria at row pos. Returns (score, list of {name, pass, detail})."""
    details: list[dict[str, Any]] = []
    row = df_daily.iloc[pos]
    close = float(row["Close"])
    sma50 = row.get("SMA_50")
    sma150 = row.get("SMA_150")
    sma200 = row.get("SMA_200")
    high_52w = row.get("High_52w")
    low_52w = row.get("Low_52w")

    # 1: Price above 150d and 200d SMA
    c1 = sma150 is not None and sma200 is not None and close > sma150 and close > sma200
    details.append({"name": "Price above 150d & 200d SMA", "pass": c1, "detail": f"Close {close:.2f}"})

    # 2: 150d MA above 200d MA
    c2 = sma150 is not None and sma200 is not None and sma150 > sma200
    details.append({"name": "150d MA above 200d MA", "pass": c2, "detail": ""})

    # 3: 200d MA rising >= 1 month
    c3 = False
    if pos >= UPTREND_SLOPE_DAYS and sma200 is not None:
        sma200_ago = df_daily["SMA_200"].iloc[pos - UPTREND_SLOPE_DAYS]
        c3 = not pd.isna(sma200_ago) and float(sma200) > float(sma200_ago)
    details.append({"name": "200d MA rising (1 month)", "pass": c3, "detail": ""})

    # 4: 50d MA above 150d and 200d
    c4 = (
        sma50 is not None and sma150 is not None and sma200 is not None
        and sma50 > sma150 and sma50 > sma200
    )
    details.append({"name": "50d MA above 150d & 200d", "pass": c4, "detail": ""})

    # 5: Price above 50d MA
    c5 = sma50 is not None and close > sma50
    details.append({"name": "Price above 50d MA", "pass": c5, "detail": ""})

    # 6: Price >= 25% above 52-week low
    c6 = False
    if low_52w is not None and float(low_52w) > 0:
        c6 = close >= 1.25 * float(low_52w)
    details.append({"name": "Price ≥ 25% above 52w low", "pass": c6, "detail": ""})

    # 7: Price within 25% of 52-week high (close >= 0.75 * high_52w)
    c7 = False
    if high_52w is not None and float(high_52w) > 0:
        c7 = close >= 0.75 * float(high_52w)
    details.append({"name": "Price within 25% of 52w high", "pass": c7, "detail": ""})

    # 8: Relative Strength >= 70 (outperforming SPY -> rs_ratio > 1)
    c8 = rs_ratio is not None and rs_ratio >= 1.0
    details.append({
        "name": "Relative Strength ≥ 70",
        "pass": c8,
        "detail": f"RS ratio {rs_ratio:.2f}" if rs_ratio is not None else "N/A",
    })

    score = sum(1 for d in details if d["pass"])
    return score, details


def trend_template(
    df_daily: pd.DataFrame,
    rs_ratio: float | None = None,
    at_date: pd.Timestamp | datetime | None = None,
) -> dict[str, Any]:
    """
    Trend Template (8 criteria) at latest row or at_date.
    df_daily must have SMA_50, SMA_150, SMA_200 and optionally High_52w, Low_52w (use add_52w_high_low).
    Returns dict: score (0-8), details (list of {name, pass, detail}).
    """
    if df_daily.empty or len(df_daily) < 1:
        return {"score": 0, "details": []}
    if at_date is not None:
        at_date = pd.Timestamp(at_date)
        idx = df_daily.index[df_daily.index <= at_date]
        if len(idx) == 0:
            return {"score": 0, "details": []}
        pos = df_daily.index.get_loc(idx[-1])
    else:
        pos = len(df_daily) - 1
    score, details = _trend_template_at_row(df_daily, pos, rs_ratio)
    return {"score": score, "details": details}


def rs_ratio_6m(symbol: str, benchmark: str = "SPY") -> float | None:
    """
    Relative strength: (stock 6m return + 1) / (benchmark 6m return + 1).
    Returns None on error or insufficient data.
    """
    try:
        stock = yf.download(symbol, period="7mo", interval="1d", progress=False, auto_adjust=True)
        bench = yf.download(benchmark, period="7mo", interval="1d", progress=False, auto_adjust=True)
    except Exception:
        return None
    if stock.empty or bench.empty or len(stock) < 2 or len(bench) < 2:
        return None
    if isinstance(stock.columns, pd.MultiIndex):
        stock.columns = stock.columns.get_level_values(0)
    if isinstance(bench.columns, pd.MultiIndex):
        bench.columns = bench.columns.get_level_values(0)
    stock_close = stock["Close"].dropna()
    bench_close = bench["Close"].dropna()
    common = stock_close.index.intersection(bench_close.index)
    if len(common) < 2:
        return None
    # 6 months ~ 126 trading days
    if len(common) > 126:
        common = common[-126:]
    s_start = float(stock_close.loc[common[0]])
    s_end = float(stock_close.loc[common[-1]])
    b_start = float(bench_close.loc[common[0]])
    b_end = float(bench_close.loc[common[-1]])
    if b_start <= 0 or s_start <= 0:
        return None
    stock_ret = s_end / s_start
    bench_ret = b_end / b_start
    if bench_ret <= 0:
        return None
    return stock_ret / bench_ret


def get_rs_ratio_cached(symbol: str, benchmark: str = "SPY") -> float | None:
    """Thin wrapper for use with st.cache_data; pass (symbol, benchmark) as args."""
    return rs_ratio_6m(symbol, benchmark)
