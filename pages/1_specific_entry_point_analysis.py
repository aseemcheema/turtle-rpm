"""
Specific Entry Point Analysis - Select a symbol (NYSE/NASDAQ).
"""

from pathlib import Path

import streamlit as st

from turtle_rpm.symbols import get_default_symbols_path, load_symbols_from_file

MAX_SELECTBOX_OPTIONS = 200


@st.cache_data(show_spinner=False)
def _cached_symbol_list(path: str) -> list[dict[str, str]]:
    """Load symbol list from CSV; cache by path so file changes can be picked up if path changes."""
    return load_symbols_from_file(Path(path))


st.set_page_config(page_title="Specific Entry Point Analysis", page_icon="📊", layout="wide")

st.title("📊 Specific Entry Point Analysis")
st.caption("Select a symbol from the NYSE and NASDAQ list.")

# Symbol selection: typeahead dropdown
symbols_path = str(get_default_symbols_path())
all_symbols = _cached_symbol_list(symbols_path)

if not all_symbols:
    st.warning(
        "Symbol list not found. Run `scripts/download_symbols.py` to populate "
        "`data/symbols.csv` (see README)."
    )
    symbol = ""
else:
    symbol_search = st.text_input(
        "Search symbol",
        placeholder="Type symbol (e.g. AAPL)",
        help="Filter by symbol only (prefix match). Select from the list below.",
    )
    query = (symbol_search or "").strip().lower()
    if query:
        filtered = [
            s
            for s in all_symbols
            if s["symbol"].lower().startswith(query)
        ][:MAX_SELECTBOX_OPTIONS]
    else:
        filtered = all_symbols[:MAX_SELECTBOX_OPTIONS]
    display_options = ["— Select a symbol —"] + [
        f"{s['symbol']} - {s['name']}" for s in filtered
    ]
    selected = st.selectbox(
        "Symbol",
        options=display_options,
        help="Choose a symbol from the list (NYSE and NASDAQ).",
    )
    if selected and selected != "— Select a symbol —":
        symbol = selected.split(" - ")[0].strip()
    else:
        symbol = ""
