"""Load symbol list from data/symbols.csv for SEPA and other pages."""

import csv
from pathlib import Path


def get_default_symbols_path() -> Path:
    """Return the default path to data/symbols.csv (relative to project root)."""
    # Assume we are run from project root (e.g. streamlit run app.py)
    return Path("data") / "symbols.csv"


def load_symbols_from_file(path: Path | None = None) -> list[dict[str, str]]:
    """
    Read symbol, name, and optional exchange from a CSV file.

    Returns a list of dicts with keys "symbol" and "name" (and "exchange" if present).
    Returns an empty list if the file is missing or unreadable.
    """
    if path is None:
        path = get_default_symbols_path()
    path = Path(path)
    if not path.is_file():
        return []
    result: list[dict[str, str]] = []
    try:
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                symbol = (row.get("symbol") or "").strip()
                if not symbol:
                    continue
                result.append({
                    "symbol": symbol,
                    "name": (row.get("name") or "").strip(),
                    "exchange": (row.get("exchange") or "").strip(),
                })
    except (OSError, csv.Error):
        return []
    return result
