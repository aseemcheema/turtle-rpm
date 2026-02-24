"""
Specific Entry Point Analysis - Select a symbol (NYSE/NASDAQ).
"""

from pathlib import Path

import streamlit as st

from turtle_rpm.symbols import get_default_symbols_path, load_symbols_from_file

MAX_SUGGESTIONS = 200
INPUT_KEY = "sepa_symbol_input"


@st.cache_data(show_spinner=False)
def _cached_symbol_list(path: str) -> list[dict[str, str]]:
    """Load symbol list from CSV; cache by path so file changes can be picked up if path changes."""
    return load_symbols_from_file(Path(path))


st.set_page_config(page_title="Specific Entry Point Analysis", page_icon="📊", layout="wide")

st.title("📊 Specific Entry Point Analysis")
st.caption("Type at least one character to search; pick a symbol from the list.")

# Symbol selection: single input, suggestions only after 1+ char
symbols_path = str(get_default_symbols_path())
all_symbols = _cached_symbol_list(symbols_path)

if not all_symbols:
    st.warning(
        "Symbol list not found. Run `scripts/download_symbols.py` to populate "
        "`data/symbols.csv` (see README)."
    )
    symbol = ""
else:
    if INPUT_KEY not in st.session_state:
        st.session_state[INPUT_KEY] = ""

    user_input = st.text_input(
        "Symbol",
        value=st.session_state[INPUT_KEY],
        key=INPUT_KEY,
        placeholder="Type at least 1 character (e.g. A or AAPL)",
        help="Symbol prefix match (NYSE/NASDAQ). Suggestions appear below after you type.",
    )
    query = (user_input or "").strip().lower()
    symbol = ""

    if len(query) >= 1:
        filtered = [
            s
            for s in all_symbols
            if s["symbol"].lower().startswith(query)
        ][:MAX_SUGGESTIONS]
        display_options = ["— Select a symbol —"] + [
            f"{s['symbol']} - {s['name']}" for s in filtered
        ]
        # Preselect if current input matches an option
        current_match = next(
            (
                opt
                for opt in display_options
                if opt != "— Select a symbol —"
                and opt.split(" - ")[0].strip().upper() == user_input.strip().upper()
            ),
            None,
        )
        default_index = display_options.index(current_match) if current_match else 0
        selected = st.selectbox(
            "Choose from list",
            options=display_options,
            index=default_index,
            key="sepa_symbol_select",
            label_visibility="collapsed",
        )
        if selected and selected != "— Select a symbol —":
            chosen_symbol = selected.split(" - ")[0].strip()
            symbol = chosen_symbol
            if st.session_state[INPUT_KEY] != chosen_symbol:
                st.session_state[INPUT_KEY] = chosen_symbol
                st.rerun()
    else:
        symbol = ""
