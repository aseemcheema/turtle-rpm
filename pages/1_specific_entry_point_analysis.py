"""
Specific Entry Point Analysis - Select a symbol (NYSE/NASDAQ), view a price chart, and list SEPA bases.
"""

import logging
from pathlib import Path

import pandas as pd
import streamlit as st
import yfinance as yf
from streamlit_searchbox import st_searchbox
from streamlit_lightweight_charts import renderLightweightCharts

from turtle_rpm.symbols import load_symbols_from_file
from turtle_rpm.sepa import (
    get_daily_ohlcv,
    to_weekly,
    compute_smas,
    find_bases,
)

MAX_SUGGESTIONS = 200
CHART_HEIGHT = 450

# Resolve path from this file so it works regardless of cwd (e.g. under st.navigation)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
SYMBOLS_PATH = _PROJECT_ROOT / "data" / "symbols.csv"
logger = logging.getLogger(__name__)


@st.cache_data(show_spinner=False)
def _cached_symbol_list(path: str) -> list[dict[str, str]]:
    """Load symbol list from CSV; cache by path so file changes can be picked up if path changes."""
    return load_symbols_from_file(Path(path))


@st.cache_data(show_spinner=False)
def _get_daily_ohlcv_df(symbol: str, years: int = 5) -> pd.DataFrame:
    """Fetch daily OHLCV as DataFrame for SEPA (chart + base detection). Cached by symbol and years."""
    return get_daily_ohlcv(symbol, years=years)


def _df_to_chart_data(df: pd.DataFrame):
    """Convert daily OHLC DataFrame to (bar_data, volume_data) for lightweight-charts."""
    if df.empty:
        return [], []
    bars = []
    volumes = []
    for ts, row in df.iterrows():
        t = pd.Timestamp(ts).strftime("%Y-%m-%d")
        o, h, l, c = float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"])
        bars.append({"time": t, "open": o, "high": h, "low": l, "close": c})
        vol = float(row.get("Volume", 0))
        color = "#26a69a" if c >= o else "#ef5350"
        volumes.append({"time": t, "value": vol, "color": color})
    return bars, volumes


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

# Price chart + SEPA base analysis
if symbol:
    with st.spinner(f"Loading data for {symbol}..."):
        df_daily = _get_daily_ohlcv_df(symbol, years=5)
    if df_daily.empty or len(df_daily) < 2:
        st.warning(f"No daily data available for {symbol}.")
    else:
        # Chart: last ~2 years for responsiveness (temporarily commented out)
        # chart_df = df_daily.tail(252 * 2)
        # bar_data, volume_data = _df_to_chart_data(chart_df)
        # if bar_data and volume_data:
        #     st.markdown("---")
        #     st.subheader(f"Daily price & volume — {symbol}")
        #     renderLightweightCharts(
        #         [
        #         {
        #             "chart": {
        #                 "height": CHART_HEIGHT,
        #                 "layout": {
        #                     "background": {"type": "solid", "color": "#0e1117"},
        #                     "textColor": "#d1d5db",
        #                 },
        #                 "rightPriceScale": {
        #                     "scaleMargins": {"top": 0.1, "bottom": 0.35},
        #                     "borderColor": "rgba(197, 203, 206, 0.4)",
        #                 },
        #                 "timeScale": {
        #                     "borderColor": "rgba(197, 203, 206, 0.4)",
        #                     "timeVisible": True,
        #                     "secondsVisible": False,
        #                 },
        #             },
        #             "series": [
        #                 {
        #                     "type": "Bar",
        #                     "data": bar_data,
        #                     "options": {
        #                         "upColor": "#26a69a",
        #                         "downColor": "#ef5350",
        #                         "borderUpColor": "#26a69a",
        #                         "borderDownColor": "#ef5350",
        #                         "wickUpColor": "#26a69a",
        #                         "wickDownColor": "#ef5350",
        #                     },
        #                 },
        #                 {
        #                     "type": "Histogram",
        #                     "data": volume_data,
        #                     "options": {
        #                         "priceFormat": {"type": "volume"},
        #                         "priceScaleId": "",
        #                     },
        #                     "priceScale": {
        #                         "scaleMargins": {"top": 0.7, "bottom": 0},
        #                     },
        #                 },
        #             ],
        #         }
        #         ],
        #         key=f"sepa_chart_{symbol}",
        #     )
        #     st.caption("Drag to pan, scroll to zoom. Volume bars: green = up day, red = down day.")
        # else:
        #     st.warning("Chart data unavailable.")
        # SEPA base detection (full 5y history)
        daily_smas = compute_smas(df_daily)
        weekly = to_weekly(df_daily)
        bases = find_bases(weekly, daily_smas)
        st.markdown("---")
        st.subheader("SEPA bases")
        if not bases:
            st.info("No bases meeting SEPA criteria (uptrend + base type and duration).")
        else:
            def _fmt_date(d):
                if d is None:
                    return "Not yet"
                return d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)
            # Current base first, then past bases by start date descending
            sorted_bases = sorted(
                bases,
                key=lambda b: (not b["is_current"], -pd.Timestamp(b["start_date"]).value()),
            )
            table_df = pd.DataFrame([
                {
                    "Current?": "Yes" if b["is_current"] else "No",
                    "Base type": b["base_type"],
                    "Start date": _fmt_date(b["start_date"]),
                    "Depth (%)": b["depth_pct"],
                    "Duration (weeks)": b["duration_weeks"],
                    "Buy point date": _fmt_date(b.get("buy_point_date")),
                    "Buy point price": b.get("resistance", ""),
                }
                for b in sorted_bases
            ])
            st.dataframe(table_df, width="stretch")
else:
    st.info("Select a symbol above to load the daily price and volume chart.")
