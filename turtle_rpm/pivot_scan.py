"""
Daily pivot breakout scan: batch pivot computation, quality score, buyable flag.

Run after market close to compute pivots for a list of stocks, rank by quality,
mark buyable (potential breakout tomorrow), and output reports.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from turtle_rpm.sepa import (
    MIN_DAILY_BARS,
    get_daily_ohlcv,
    to_weekly,
    compute_smas,
    find_bases,
    pivot_forming,
    pivot_in_base,
    pivot_volume_vs_average,
)
from turtle_rpm.leadership import add_52w_high_low, trend_template, rs_ratio_6m

logger = logging.getLogger(__name__)

# Default distance_pct threshold for "near resistance" (buyable for tomorrow)
DEFAULT_DISTANCE_PCT_MAX = 3.0


def compute_pivot_result(
    symbol: str,
    *,
    years: int = 5,
    include_leadership: bool = True,
    name: str | None = None,
) -> dict[str, Any]:
    """
    Compute pivot + base + volume (and optionally leadership) for one symbol.

    Returns a flat dict: symbol, name, pivot_forming, pivot_days, pivot_range_pct,
    tight_closes, pivot_high, in_base, base_type, resistance, distance_pct,
    buy_point_date, volume_at_pivot; optional trend_template_score, rs_ratio.
    """
    row: dict[str, Any] = {
        "symbol": symbol,
        "name": name or "",
        "pivot_forming": False,
        "pivot_days": None,
        "pivot_range_pct": None,
        "tight_closes": False,
        "pivot_high": None,
        "in_base": False,
        "base_type": None,
        "resistance": None,
        "distance_pct": None,
        "buy_point_date": None,
        "volume_at_pivot": None,
        "trend_template_score": None,
        "rs_ratio": None,
    }
    df_daily = get_daily_ohlcv(symbol, years=years)
    if df_daily.empty or len(df_daily) < MIN_DAILY_BARS:
        return row
    daily_smas = compute_smas(df_daily)
    weekly = to_weekly(df_daily)
    pivot = pivot_forming(df_daily)
    bases = find_bases(weekly, daily_smas, pivot=pivot)
    base_containing = pivot_in_base(pivot, bases) if pivot.get("forming") else None
    vol_label = pivot_volume_vs_average(df_daily, pivot) if pivot.get("forming") else None

    row["pivot_forming"] = bool(pivot.get("forming"))
    row["pivot_days"] = pivot.get("days")
    row["pivot_range_pct"] = pivot.get("range_pct")
    row["tight_closes"] = bool(pivot.get("tight_closes"))
    row["pivot_high"] = pivot.get("pivot_high")
    row["volume_at_pivot"] = vol_label

    if base_containing is not None:
        row["in_base"] = True
        row["base_type"] = base_containing.get("base_type")
        row["resistance"] = base_containing.get("resistance")
        row["distance_pct"] = base_containing.get("distance_pct")
        row["buy_point_date"] = base_containing.get("buy_point_date")

    if include_leadership:
        try:
            rs = rs_ratio_6m(symbol)
            row["rs_ratio"] = round(rs, 2) if rs is not None else None
            daily_with_52w = add_52w_high_low(daily_smas)
            tt = trend_template(daily_with_52w, rs_ratio=rs)
            row["trend_template_score"] = tt.get("score")
        except Exception as e:
            logger.debug("Leadership for %s: %s", symbol, e)

    return row


def pivot_quality_score(row: dict[str, Any]) -> float:
    """
    Single numeric quality score (higher = better) for ordering pivots.

    Factors: tighter range_pct, tight_closes, in_base, volume below average,
    smaller distance_pct (closer to breakout).
    """
    score = 0.0
    if not row.get("pivot_forming"):
        return score
    # Tighter pivot range: max 40 pts, 0% -> 40, 8% -> 0
    range_pct = row.get("pivot_range_pct")
    if range_pct is not None:
        score += max(0, 40 - 5 * range_pct)
    if row.get("tight_closes"):
        score += 15
    if row.get("in_base"):
        score += 20
    # Volume dry-up at pivot
    if row.get("volume_at_pivot") == "below":
        score += 10
    # Proximity to breakout: closer = better (max 15). distance_pct 0 -> 15, 5 -> 0
    dist = row.get("distance_pct")
    if dist is not None and row.get("buy_point_date") is None:
        if dist <= 0:
            score += 15
        else:
            score += max(0, 15 - 3 * dist)
    return round(score, 2)


def is_buyable(
    row: dict[str, Any],
    distance_pct_max: float = DEFAULT_DISTANCE_PCT_MAX,
    min_trend_score: int | None = None,
    require_rs_above_1: bool = False,
) -> bool:
    """
    True if symbol is a candidate for potential pivot breakout tomorrow.

    Requires: pivot forming, in base, not yet broken out, distance_pct within threshold.
    Optional: min trend_template score, rs_ratio > 1.
    """
    if not row.get("pivot_forming"):
        return False
    if not row.get("in_base") or row.get("resistance") is None:
        return False
    if row.get("buy_point_date") is not None:
        return False
    dist = row.get("distance_pct")
    if dist is None or dist > distance_pct_max:
        return False
    if min_trend_score is not None and (row.get("trend_template_score") or 0) < min_trend_score:
        return False
    if require_rs_above_1 and (row.get("rs_ratio") is None or row["rs_ratio"] < 1.0):
        return False
    return True


def run_scan(
    symbols: list[str] | list[dict[str, str]],
    *,
    years: int = 5,
    include_leadership: bool = True,
    distance_pct_max: float = DEFAULT_DISTANCE_PCT_MAX,
    min_trend_score: int | None = None,
    require_rs_above_1: bool = False,
) -> list[dict[str, Any]]:
    """
    Run pivot scan over a list of symbols. Each item can be a string (symbol)
    or a dict with 'symbol' and optional 'name'.

    Returns list of result dicts (with quality_score and buyable added), unsorted.
    Caller should sort by quality_score descending and filter buyable for "tomorrow" list.
    """
    name_by_symbol: dict[str, str] = {}
    sym_list: list[str] = []
    for s in symbols:
        if isinstance(s, dict):
            sym = (s.get("symbol") or "").strip()
            if sym:
                sym_list.append(sym)
                name_by_symbol[sym] = (s.get("name") or "").strip()
        else:
            sym = (s or "").strip()
            if sym:
                sym_list.append(sym)

    results: list[dict[str, Any]] = []
    for symbol in sym_list:
        try:
            row = compute_pivot_result(
                symbol,
                years=years,
                include_leadership=include_leadership,
                name=name_by_symbol.get(symbol),
            )
            row["quality_score"] = pivot_quality_score(row)
            row["buyable"] = is_buyable(
                row,
                distance_pct_max=distance_pct_max,
                min_trend_score=min_trend_score,
                require_rs_above_1=require_rs_above_1,
            )
            results.append(row)
        except Exception as e:
            logger.warning("Pivot scan %s: %s", symbol, e)
            results.append({
                "symbol": symbol,
                "name": name_by_symbol.get(symbol, ""),
                "pivot_forming": False,
                "pivot_days": None,
                "pivot_range_pct": None,
                "tight_closes": False,
                "pivot_high": None,
                "in_base": False,
                "base_type": None,
                "resistance": None,
                "distance_pct": None,
                "buy_point_date": None,
                "volume_at_pivot": None,
                "trend_template_score": None,
                "rs_ratio": None,
                "quality_score": 0.0,
                "buyable": False,
            })
    return results
