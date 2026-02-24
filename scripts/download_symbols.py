#!/usr/bin/env python3
"""
Download NYSE and NASDAQ symbol list from NASDAQ Trader and write data/symbols.csv.

Run from project root:
    python scripts/download_symbols.py
    uv run python scripts/download_symbols.py
"""

import csv
import sys
import urllib.request
from pathlib import Path

SOURCE_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt"
# Listing Exchange: N=NYSE, Q=Nasdaq Global Select, G=Nasdaq Global, S=Nasdaq Capital
NYSE_NASDAQ_EXCHANGES = {"N", "Q", "G", "S"}


def main() -> int:
    base = Path(__file__).resolve().parent.parent
    out_path = base / "data" / "symbols.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with urllib.request.urlopen(SOURCE_URL, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="replace")

    lines = raw.strip().splitlines()
    if not lines:
        print("Empty response from NASDAQ", file=sys.stderr)
        return 1

    # Header: Nasdaq Traded|Symbol|Security Name|Listing Exchange|...
    header = lines[0]
    parts = header.split("|")
    try:
        idx_symbol = parts.index("Symbol")
        idx_name = parts.index("Security Name")
        idx_exchange = parts.index("Listing Exchange")
        idx_test = parts.index("Test Issue")
    except ValueError as e:
        print(f"Unexpected header format: {e}", file=sys.stderr)
        return 1

    rows: list[tuple[str, str, str]] = []
    for line in lines[1:]:
        if line.startswith("File Creation Time"):
            continue
        cells = line.split("|")
        if len(cells) <= max(idx_symbol, idx_name, idx_exchange, idx_test):
            continue
        exchange = cells[idx_exchange].strip()
        test_issue = cells[idx_test].strip().upper()
        if exchange not in NYSE_NASDAQ_EXCHANGES or test_issue == "Y":
            continue
        symbol = cells[idx_symbol].strip()
        name = cells[idx_name].strip()
        if not symbol:
            continue
        rows.append((symbol, name, exchange))

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["symbol", "name", "exchange"])
        w.writerows(rows)

    print(f"Wrote {len(rows)} symbols to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
