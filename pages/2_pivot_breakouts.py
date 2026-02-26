"""
Pivot breakouts for tomorrow: view the latest scan report.

Displays the most recent pivot_breakouts_tomorrow_YYYYMMDD.csv from data/pivot_scan
so you can open the app in the morning and see the list without re-running the scan.
"""

from pathlib import Path

import pandas as pd
import streamlit as st

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
PIVOT_SCAN_DIR = _PROJECT_ROOT / "data" / "pivot_scan"


def _latest_tomorrow_csv() -> Path | None:
    """Return path to the most recent pivot_breakouts_tomorrow_*.csv, or None."""
    if not PIVOT_SCAN_DIR.is_dir():
        return None
    pattern = "pivot_breakouts_tomorrow_*.csv"
    files = list(PIVOT_SCAN_DIR.glob(pattern))
    if not files:
        return None
    # Sort by name (date in filename) descending
    files.sort(key=lambda p: p.name, reverse=True)
    return files[0]


st.set_page_config(page_title="Pivot Breakouts Tomorrow", page_icon="📋", layout="wide")
st.title("Pivot Breakouts for Tomorrow")
st.caption(
    "Potential pivot breakouts from the latest daily scan (run after market close). "
    "Open this page in the morning to see your list without re-scanning."
)

csv_path = _latest_tomorrow_csv()
if csv_path is None:
    st.info(
        "No scan report found. Run the pivot breakout scan after market close: "
        "`uv run python scripts/pivot_breakout_scan.py`"
    )
else:
    try:
        df = pd.read_csv(csv_path)
        st.caption(f"Report: **{csv_path.name}**")
        if df.empty:
            st.write("No buyable pivot breakouts in the latest scan.")
        else:
            st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"Could not load report: {e}")
