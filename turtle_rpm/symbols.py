"""Load symbol list from data/symbols.csv for SEPA and other pages."""

import csv
import re
from pathlib import Path


# MPA CSV: first column is "Symbol" (quoted in file). Skip rows where first cell is not a ticker-like symbol.
_TICKER_RE = re.compile(r"^[A-Z0-9.]{1,6}$", re.IGNORECASE)


def _looks_like_ticker(s: str) -> bool:
    """True if s is non-empty, no spaces, and looks like a ticker (e.g. AAPL, BRK.B)."""
    s = (s or "").strip().strip('"').strip()
    if not s or " " in s or s in ("->", "Symbol", "symbol"):
        return False
    return bool(_TICKER_RE.match(s))


def load_symbols_from_mpa_csv(path: Path | None = None) -> list[dict[str, str]]:
    """
    Read symbols from an MPA-style CSV where the first column is Symbol (often quoted).

    Uses only rows where the first column looks like a ticker (e.g. "ABVX", "MU").
    Skips rows where the first column is not a quoted symbol (e.g. " -> ", headers, labels).
    Returns list of dicts with "symbol" and "name" (name empty).
    """
    if path is None:
        path = get_default_symbols_path()
    path = Path(path)
    if not path.is_file():
        return []
    result: list[dict[str, str]] = []
    try:
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            next(reader, None)  # skip header
            for row in reader:
                if not row:
                    continue
                raw = (row[0] or "").strip().strip('"').strip()
                if not _looks_like_ticker(raw):
                    continue
                result.append({"symbol": raw, "name": "", "exchange": ""})
    except (OSError, csv.Error):
        return []
    return result


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
