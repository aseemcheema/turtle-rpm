"""
Specific Entry Point Analysis - Select a symbol (NYSE/NASDAQ) and view a price chart.
"""

import logging
from pathlib import Path

import pandas as pd
import streamlit as st
import yfinance as yf
from streamlit_searchbox import st_searchbox
from streamlit_lightweight_charts import renderLightweightCharts

from turtle_rpm.symbols import load_symbols_from_file

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
def _load_daily_ohlcv(symbol: str):
    """Fetch daily OHLCV for a symbol; return (bar_data, volume_data) or ([], []) on error."""
    try:
        df = yf.download(symbol, period="2y", interval="1d", progress=False, auto_adjust=True)
    except Exception as exc:
        logger.exception("Failed to download daily data for %s", symbol)
        return [], []
    if df.empty or len(df) < 2:
        return [], []
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna().reset_index()
    # Index column name after reset_index() varies (Date, Datetime, "", etc.); use first column.
    date_col = df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    if df.empty:
        return [], []
    if isinstance(df[date_col].dtype, pd.DatetimeTZDtype):
        df[date_col] = df[date_col].dt.tz_localize(None)
    bars = []
    volumes = []
    for _, row in df.iterrows():
        t = row[date_col].strftime("%Y-%m-%d")
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

# Price chart: daily bars + volume (zoomable, pannable)
if symbol:
    with st.spinner(f"Loading daily chart for {symbol}..."):
        bar_data, volume_data = _load_daily_ohlcv(symbol)
    if bar_data and volume_data:
        st.markdown("---")
        st.subheader(f"Daily price & volume — {symbol}")
        renderLightweightCharts(
            [
                {
                    "chart": {
                        "height": CHART_HEIGHT,
                        "layout": {
                            "background": {"type": "solid", "color": "#0e1117"},
                            "textColor": "#d1d5db",
                        },
                        "rightPriceScale": {
                            "scaleMargins": {"top": 0.1, "bottom": 0.35},
                            "borderColor": "rgba(197, 203, 206, 0.4)",
                        },
                        "timeScale": {
                            "borderColor": "rgba(197, 203, 206, 0.4)",
                            "timeVisible": True,
                            "secondsVisible": False,
                        },
                    },
                    "series": [
                        {
                            "type": "Bar",
                            "data": bar_data,
                            "options": {
                                "upColor": "#26a69a",
                                "downColor": "#ef5350",
                                "borderUpColor": "#26a69a",
                                "borderDownColor": "#ef5350",
                                "wickUpColor": "#26a69a",
                                "wickDownColor": "#ef5350",
                            },
                        },
                        {
                            "type": "Histogram",
                            "data": volume_data,
                            "options": {
                                "priceFormat": {"type": "volume"},
                                "priceScaleId": "",
                            },
                            "priceScale": {
                                "scaleMargins": {"top": 0.7, "bottom": 0},
                            },
                        },
                    ],
                }
            ],
            key=f"sepa_chart_{symbol}",
        )
        st.caption("Drag to pan, scroll to zoom. Volume bars: green = up day, red = down day.")
    else:
        st.warning(f"No daily data available for {symbol}.")
else:
    st.info("Select a symbol above to load the daily price and volume chart.")
