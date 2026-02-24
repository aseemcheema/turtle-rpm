"""
Specific Entry Point Analysis - Select a symbol (NYSE/NASDAQ).
"""

from pathlib import Path

import streamlit as st
from streamlit_searchbox import st_searchbox

from turtle_rpm.symbols import load_symbols_from_file

MAX_SUGGESTIONS = 200

# Resolve path from this file so it works regardless of cwd (e.g. under st.navigation)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
SYMBOLS_PATH = _PROJECT_ROOT / "data" / "symbols.csv"


@st.cache_data(show_spinner=False)
def _cached_symbol_list(path: str) -> list[dict[str, str]]:
    """Load symbol list from CSV; cache by path so file changes can be picked up if path changes."""
    return load_symbols_from_file(Path(path))


st.set_page_config(page_title="Specific Entry Point Analysis", page_icon="📊", layout="wide")

st.title("📊 Specific Entry Point Analysis")
st.caption("Type to search; pick a symbol from the list (NYSE and NASDAQ).")

all_symbols = _cached_symbol_list(str(SYMBOLS_PATH))

if not all_symbols:
    st.warning(
        "Symbol list not found. Run `scripts/download_symbols.py` to populate "
        "`data/symbols.csv` (see README)."
    )
    symbol = ""
else:

    def search_symbols(searchterm: str) -> list[tuple[str, str]]:
        """Return (display_label, symbol) for prefix match on symbol. Only match after 1+ char."""
        if not searchterm or not searchterm.strip():
            return []
        query = searchterm.strip().lower()
        filtered = [
            s
            for s in all_symbols
            if s["symbol"].lower().startswith(query)
        ][:MAX_SUGGESTIONS]
        return [(f"{s['symbol']} - {s['name']}", s["symbol"]) for s in filtered]

    symbol = st_searchbox(
        search_symbols,
        label="Symbol",
        placeholder="Type to search (e.g. A or AAPL)",
        key="sepa_symbol_searchbox",
        help="Symbol prefix match. Suggestions update as you type.",
    )
    symbol = symbol or ""
