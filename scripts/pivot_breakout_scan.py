#!/usr/bin/env python3
"""
Run daily pivot breakout scan after market close.

Loads symbol list, computes pivots and buyable flag, writes full results and
"potential pivot breakouts for tomorrow" CSV. Run from project root:
  uv run python scripts/pivot_breakout_scan.py
  uv run python scripts/pivot_breakout_scan.py --symbols data/watchlist.csv --out reports
"""

import argparse
import csv
import sys
from datetime import date
from pathlib import Path

# Project root
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from turtle_rpm.symbols import (
    get_default_symbols_path,
    load_symbols_from_file,
    load_symbols_from_mpa_csv,
)
from turtle_rpm.pivot_scan import run_scan, DEFAULT_DISTANCE_PCT_MAX


REPORT_COLUMNS = [
    "symbol",
    "name",
    "pivot_forming",
    "pivot_days",
    "pivot_range_pct",
    "tight_closes",
    "pivot_high",
    "in_base",
    "base_type",
    "resistance",
    "distance_pct",
    "buy_point_date",
    "volume_at_pivot",
    "trend_template_score",
    "rs_ratio",
    "quality_score",
    "buyable",
]


def _row_to_csv_row(row: dict) -> dict[str, str]:
    out = {}
    for k in REPORT_COLUMNS:
        v = row.get(k)
        if v is None or (isinstance(v, float) and (v != v)):  # NaN
            out[k] = ""
        elif hasattr(v, "strftime"):
            out[k] = v.strftime("%Y-%m-%d")
        else:
            out[k] = str(v)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily pivot breakout scan (run after market close)")
    parser.add_argument(
        "--symbols",
        type=Path,
        default=None,
        help="Path to symbol list CSV (default: data/symbols.csv)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output directory for reports (default: data/pivot_scan)",
    )
    parser.add_argument(
        "--distance-pct",
        type=float,
        default=DEFAULT_DISTANCE_PCT_MAX,
        help="Max distance_pct for buyable (default: 3.0)",
    )
    parser.add_argument(
        "--min-trend-score",
        type=int,
        default=None,
        help="Optional minimum trend template score for buyable",
    )
    parser.add_argument(
        "--require-rs",
        action="store_true",
        help="Require rs_ratio >= 1 for buyable",
    )
    parser.add_argument(
        "--no-leadership",
        action="store_true",
        help="Skip trend template and RS (faster)",
    )
    args = parser.parse_args()

    symbols_path = args.symbols or _root / get_default_symbols_path()
    symbols_path = symbols_path if symbols_path.is_absolute() else _root / symbols_path
    symbols_list = load_symbols_from_file(symbols_path)
    if not symbols_list:
        symbols_list = load_symbols_from_mpa_csv(symbols_path)
    if not symbols_list:
        print(f"No symbols found at {symbols_path}", file=sys.stderr)
        return 1

    out_dir = args.out or _root / "data" / "pivot_scan"
    out_dir = out_dir if out_dir.is_absolute() else _root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    today = date.today().strftime("%Y%m%d")
    full_path = out_dir / f"pivot_scan_full_{today}.csv"
    tomorrow_path = out_dir / f"pivot_breakouts_tomorrow_{today}.csv"

    print(f"Scanning {len(symbols_list)} symbols...")
    results = run_scan(
        symbols_list,
        include_leadership=not args.no_leadership,
        distance_pct_max=args.distance_pct,
        min_trend_score=args.min_trend_score,
        require_rs_above_1=args.require_rs,
    )
    results.sort(key=lambda r: (r.get("quality_score") or 0), reverse=True)

    # Full results
    with open(full_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=REPORT_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for row in results:
            w.writerow(_row_to_csv_row(row))
    print(f"Wrote {full_path} ({len(results)} rows)")

    # Tomorrow list (buyable only)
    tomorrow_rows = [r for r in results if r.get("buyable")]
    with open(tomorrow_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=REPORT_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for row in tomorrow_rows:
            w.writerow(_row_to_csv_row(row))
    print(f"Wrote {tomorrow_path} ({len(tomorrow_rows)} potential breakouts for tomorrow)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
