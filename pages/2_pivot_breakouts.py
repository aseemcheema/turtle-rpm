"""
Pivot breakouts for tomorrow: view the latest scan report.

Displays the most recent pivot scan (full + tomorrow) from data/pivot_scan
with filtering, sorting, and tables for breakouts and all pivots.
"""

from pathlib import Path

import pandas as pd
import streamlit as st

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
PIVOT_SCAN_DIR = _PROJECT_ROOT / "data" / "pivot_scan"

# Columns that are safe to sort/filter (numeric or short strings)
SORT_COLUMNS = [
    "symbol",
    "quality_score",
    "distance_pct",
    "pivot_range_pct",
    "pivot_high",
    "resistance",
    "trend_template_score",
    "rs_ratio",
    "pivot_days",
]
BOOL_FILTER_COLUMNS = ["buyable", "pivot_forming", "in_base"]


def _latest_full_scan_csv() -> Path | None:
    """Return path to the most recent pivot_scan_full_*.csv, or None."""
    if not PIVOT_SCAN_DIR.is_dir():
        return None
    files = list(PIVOT_SCAN_DIR.glob("pivot_scan_full_*.csv"))
    if not files:
        return None
    files.sort(key=lambda p: p.name, reverse=True)
    return files[0]


def _latest_tomorrow_csv() -> Path | None:
    """Return path to the most recent pivot_breakouts_tomorrow_*.csv, or None."""
    if not PIVOT_SCAN_DIR.is_dir():
        return None
    files = list(PIVOT_SCAN_DIR.glob("pivot_breakouts_tomorrow_*.csv"))
    if not files:
        return None
    files.sort(key=lambda p: p.name, reverse=True)
    return files[0]


def _normalize_bool_col(df: pd.DataFrame, col: str) -> None:
    """Convert column to bool if it looks like True/False strings."""
    if col not in df.columns:
        return
    s = df[col]
    if s.dtype == bool:
        return
    if s.dtype == object or s.dtype.kind == "U":
        df[col] = s.astype(str).str.lower().isin(("true", "1", "yes"))

def _load_latest_scan() -> pd.DataFrame | None:
    """Load the latest full scan CSV if present; otherwise load tomorrow CSV (narrower set)."""
    full_path = _latest_full_scan_csv()
    if full_path is not None:
        try:
            df = pd.read_csv(full_path)
            for c in BOOL_FILTER_COLUMNS:
                _normalize_bool_col(df, c)
            return df
        except Exception:
            pass
    tomorrow_path = _latest_tomorrow_csv()
    if tomorrow_path is not None:
        try:
            df = pd.read_csv(tomorrow_path)
            for c in BOOL_FILTER_COLUMNS:
                _normalize_bool_col(df, c)
            return df
        except Exception:
            pass
    return None


st.set_page_config(page_title="Pivot Breakouts Tomorrow", page_icon="📋", layout="wide")
st.title("Pivot Breakouts for Tomorrow")
st.caption(
    "Potential pivot breakouts from the latest daily scan (run after market close). "
    "Open this page in the morning to see your list without re-scanning."
)

df = _load_latest_scan()
if df is None or df.empty:
    st.info(
        "No scan report found. Run the pivot breakout scan after market close: "
        "`uv run python scripts/pivot_breakout_scan.py`"
    )
else:
    full_path = _latest_full_scan_csv() or _latest_tomorrow_csv()
    st.caption(f"Report: **{full_path.name}**" if full_path else "")

    # ---- Potential breakouts for tomorrow ----
    st.subheader("Potential breakouts for tomorrow")
    has_buyable = "buyable" in df.columns and df["buyable"].eq(True).any()
    tomorrow_df = df[df["buyable"] == True].copy() if has_buyable else pd.DataFrame()

    if tomorrow_df.empty:
        st.write("No buyable pivot breakouts in the latest scan.")
    else:
        st.write(f"**{len(tomorrow_df)}** symbols with potential pivot breakouts.")
        sort_col = st.selectbox(
            "Sort tomorrow list by",
            options=[c for c in SORT_COLUMNS if c in tomorrow_df.columns],
            index=1 if "quality_score" in tomorrow_df.columns else 0,
            key="tomorrow_sort",
        )
        sort_asc = st.checkbox("Ascending", value=False, key="tomorrow_asc")
        tomorrow_df = tomorrow_df.sort_values(
            by=sort_col, ascending=sort_asc, na_position="last"
        )
        st.dataframe(tomorrow_df, width="stretch")

    # ---- All pivots (filter and sort) ----
    st.subheader("All pivots")
    st.caption("Full scan results. Use filters and sort to narrow down.")

    # Filters
    filter_col1, filter_col2, filter_col3 = st.columns(3)
    with filter_col1:
        symbol_query = (
            st.text_input(
                "Symbol contains",
                value="",
                placeholder="e.g. AAPL or leave blank",
                key="symbol_filter",
            )
            .strip()
            .upper()
        )
    with filter_col2:
        if "buyable" in df.columns:
            filter_buyable = st.checkbox("Buyable only", value=False, key="fb_buyable")
        else:
            filter_buyable = False
        if "pivot_forming" in df.columns:
            filter_pivot = st.checkbox("Pivot forming only", value=False, key="fb_pivot")
        else:
            filter_pivot = False
        if "in_base" in df.columns:
            filter_in_base = st.checkbox("In base only", value=False, key="fb_inbase")
        else:
            filter_in_base = False
    with filter_col3:
        if "quality_score" in df.columns:
            min_quality = st.number_input(
                "Min quality score",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=0.5,
                key="min_quality",
            )
        else:
            min_quality = 0.0

    # Apply filters
    filtered = df.copy()
    if symbol_query:
        mask = filtered["symbol"].astype(str).str.upper().str.contains(symbol_query, na=False)
        filtered = filtered[mask]
    if filter_buyable and "buyable" in filtered.columns:
        filtered = filtered[filtered["buyable"] == True]
    if filter_pivot and "pivot_forming" in filtered.columns:
        filtered = filtered[filtered["pivot_forming"] == True]
    if filter_in_base and "in_base" in filtered.columns:
        filtered = filtered[filtered["in_base"] == True]
    if min_quality > 0 and "quality_score" in filtered.columns:
        filtered = filtered[filtered["quality_score"].fillna(0) >= min_quality]

    # Sort
    sort_col_all = st.selectbox(
        "Sort all pivots by",
        options=[c for c in SORT_COLUMNS if c in filtered.columns],
        index=1 if "quality_score" in filtered.columns else 0,
        key="all_sort",
    )
    sort_asc_all = st.checkbox("Ascending", value=False, key="all_asc")
    filtered = filtered.sort_values(
        by=sort_col_all, ascending=sort_asc_all, na_position="last"
    )

    st.write(f"Showing **{len(filtered)}** of **{len(df)}** rows.")
    st.dataframe(filtered, width="stretch")
