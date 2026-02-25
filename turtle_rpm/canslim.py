"""
CAN SLIM checklist: C/A/N/S/L/I/M using yfinance + price/volume + RS + SPY.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import yfinance as yf

from turtle_rpm.sepa import compute_smas

CANSLIM_MIN_EPS_GROWTH = 0.25  # 25%
CANSLIM_RS_MIN = 1.0  # Outperforming benchmark


def _ticker_quarterly_eps_growth(ticker: yf.Ticker) -> tuple[bool, str]:
    """C: Current quarter EPS growth >= 25% vs same quarter prior year. Returns (pass, detail)."""
    try:
        earnings = getattr(ticker, "quarterly_earnings", None) or (
            ticker.get_earnings(freq="quarterly") if hasattr(ticker, "get_earnings") else None
        )
        if earnings is None or earnings.empty or len(earnings) < 2:
            return False, "No quarterly earnings data"
        # DataFrame: index often date; column 'earnings' or first numeric column
        if "earnings" in earnings.columns:
            eps = earnings["earnings"]
        else:
            eps = earnings.select_dtypes(include=["number"]).iloc[:, 0] if not earnings.select_dtypes(include=["number"]).empty else earnings.iloc[:, 0]
        eps = eps.dropna()
        if len(eps) < 2:
            return False, "Insufficient quarters"
        latest = float(eps.iloc[0])
        prior_year = float(eps.iloc[4]) if len(eps) > 4 else float(eps.iloc[1])
        if prior_year == 0:
            return False, "Prior year EPS zero"
        growth = (latest - prior_year) / abs(prior_year)
        pass_ = growth >= CANSLIM_MIN_EPS_GROWTH
        return pass_, f"QoQ growth {growth * 100:.1f}%"
    except Exception:
        return False, "Data unavailable"


def _ticker_annual_eps_growth(ticker: yf.Ticker) -> tuple[bool, str]:
    """A: Annual EPS growth >= 25%. Returns (pass, detail)."""
    try:
        earnings = getattr(ticker, "earnings", None) or (
            ticker.get_earnings(freq="yearly") if hasattr(ticker, "get_earnings") else None
        )
        if earnings is None or earnings.empty or len(earnings) < 2:
            return False, "No annual earnings data"
        if "earnings" in earnings.columns:
            eps = earnings["earnings"]
        else:
            eps = earnings.select_dtypes(include=["number"]).iloc[:, 0] if not earnings.select_dtypes(include=["number"]).empty else earnings.iloc[:, 0]
        eps = eps.dropna()
        if len(eps) < 2:
            return False, "Insufficient years"
        latest = float(eps.iloc[0])
        prior = float(eps.iloc[1])
        if prior == 0:
            return False, "Prior year EPS zero"
        growth = (latest - prior) / abs(prior)
        pass_ = growth >= CANSLIM_MIN_EPS_GROWTH
        return pass_, f"YoY growth {growth * 100:.1f}%"
    except Exception:
        return False, "Data unavailable"


def _supply_demand(ticker: yf.Ticker, df_daily: pd.DataFrame) -> tuple[bool, str]:
    """S: Supply & demand - volume on up days vs down days; optional float. Returns (pass, detail)."""
    if df_daily.empty or "Volume" not in df_daily.columns or "Close" not in df_daily.columns:
        return False, "No volume data"
    close = df_daily["Close"]
    vol = df_daily["Volume"]
    up = close > close.shift(1)
    up_vol = vol.where(up).mean()
    down_vol = vol.where(~up).mean()
    if pd.isna(down_vol) or down_vol == 0:
        pass_ = True
        detail = "Up-day volume > down-day"
    else:
        pass_ = up_vol > down_vol
        detail = f"Up vol vs down vol: {float(up_vol):.0f} vs {float(down_vol):.0f}"
    try:
        info = ticker.info
        fl = info.get("floatShares") or info.get("sharesOutstanding")
        if fl is not None:
            detail += f"; float ~{fl / 1e6:.1f}M"
    except Exception:
        pass
    return pass_, detail


def _market_uptrend(benchmark: str = "SPY") -> tuple[bool, str]:
    """M: Market in uptrend - SPY above 50d and 200d, 200d rising."""
    try:
        df = yf.download(benchmark, period="1y", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < 200:
            return False, "Insufficient benchmark data"
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = compute_smas(df, windows=(50, 200))
        row = df.iloc[-1]
        close = float(row["Close"])
        sma50 = row.get("SMA_50")
        sma200 = row.get("SMA_200")
        above_50 = sma50 is not None and close > sma50
        above_200 = sma200 is not None and close > sma200
        rising_200 = False
        if len(df) >= 22 and sma200 is not None:
            rising_200 = float(sma200) > float(df["SMA_200"].iloc[-22])
        pass_ = above_50 and above_200 and rising_200
        return pass_, f"{benchmark} above 50d/200d, 200d rising: {pass_}"
    except Exception:
        return False, "Data unavailable"


def canslim_checklist(
    symbol: str,
    df_daily: pd.DataFrame,
    rs_ratio: float | None,
) -> list[dict[str, Any]]:
    """
    CAN SLIM checklist for symbol. Returns list of { letter, name, status, detail }.
    N and I are Manual/N/A.
    """
    ticker = yf.Ticker(symbol)
    out: list[dict[str, Any]] = []

    # C
    pass_c, detail_c = _ticker_quarterly_eps_growth(ticker)
    out.append({"letter": "C", "name": "Current quarter EPS growth ≥ 25%", "pass": pass_c, "detail": detail_c})

    # A
    pass_a, detail_a = _ticker_annual_eps_growth(ticker)
    out.append({"letter": "A", "name": "Annual earnings growth ≥ 25%", "pass": pass_a, "detail": detail_a})

    # N
    out.append({"letter": "N", "name": "New product/service/management", "pass": None, "detail": "Manual"})

    # S
    pass_s, detail_s = _supply_demand(ticker, df_daily)
    out.append({"letter": "S", "name": "Supply & demand (volume, float)", "pass": pass_s, "detail": detail_s})

    # L
    pass_l = rs_ratio is not None and rs_ratio >= CANSLIM_RS_MIN
    detail_l = f"RS ratio {rs_ratio:.2f}" if rs_ratio is not None else "N/A"
    out.append({"letter": "L", "name": "Leader (RS 80+ / outperforming)", "pass": pass_l, "detail": detail_l})

    # I
    out.append({"letter": "I", "name": "Institutional sponsorship", "pass": None, "detail": "Manual"})

    # M
    pass_m, detail_m = _market_uptrend()
    out.append({"letter": "M", "name": "Market in uptrend", "pass": pass_m, "detail": detail_m})

    return out


def canslim_status(p: bool | None) -> str:
    """Map pass (True/False/None) to Status string."""
    if p is None:
        return "Manual/N/A"
    return "Pass" if p else "Fail"
