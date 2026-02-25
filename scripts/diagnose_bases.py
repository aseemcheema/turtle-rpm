#!/usr/bin/env python3
"""
Diagnose why a symbol's base(s) are or aren't detected.

Prints weekly pivot highs/lows and per-candidate stats (uptrend, classification).
Run from project root:
    python scripts/diagnose_bases.py [SYMBOL]
    uv run python scripts/diagnose_bases.py ARGX
"""

import sys
from pathlib import Path

# Project root
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from turtle_rpm.sepa import (
    get_daily_ohlcv,
    to_weekly,
    compute_smas,
    find_bases,
    pivot_forming,
)


def main() -> int:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "ARGX"
    print(f"Loading {symbol} (5y daily)...")
    df_daily = get_daily_ohlcv(symbol, years=5)
    if df_daily.empty or len(df_daily) < 252:
        print("Insufficient daily data.")
        return 1
    daily_smas = compute_smas(df_daily)
    weekly = to_weekly(df_daily)
    pivot = pivot_forming(df_daily)
    print(f"Pivot forming: {pivot.get('forming')} (days={pivot.get('days')})")
    print()
    bases = find_bases(weekly, daily_smas, debug=True, pivot=pivot)
    print()
    print("=== Bases returned ===")
    for i, b in enumerate(bases):
        print(f"  {i+1}. {b['base_type']} start={b['start_date']} end={b['end_date']} "
              f"duration_weeks={b['duration_weeks']} depth_pct={b['depth_pct']} is_current={b.get('is_current')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
