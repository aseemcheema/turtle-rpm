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
    pivot_forming,
    pivot_in_base,
    pivot_volume_vs_average,
)
from turtle_rpm.leadership import (
    add_52w_high_low,
    trend_template,
    rs_ratio_6m,
)
from turtle_rpm.liquidity import (
    liquidity_metrics,
    days_to_liquidate,
    max_purchase_by_liquidity,
    DEFAULT_MAX_DAYS_TO_EXIT,
    DEFAULT_PCT_ADV_PER_DAY,
)
# from turtle_rpm.canslim import canslim_checklist, canslim_status

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


@st.cache_data(show_spinner=False)
def _get_rs_ratio(symbol: str, benchmark: str = "SPY") -> float | None:
    """RS ratio vs benchmark (6m). Cached."""
    return rs_ratio_6m(symbol, benchmark)


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
        # Data and base detection (full 5y history)
        daily_smas = compute_smas(df_daily)
        weekly = to_weekly(df_daily)
        pivot = pivot_forming(df_daily)
        bases = find_bases(weekly, daily_smas, pivot=pivot)
        current_base = next((b for b in bases if b.get("is_current")), None)

        def _fmt_date(d):
            if d is None:
                return "Not yet"
            return d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)

        def _fmt_distance(b):
            if b.get("buy_point_date") is not None:
                return "At/above"
            d = b.get("distance_pct")
            return f"{d}%" if d is not None else "—"

        st.markdown("---")
        # Row 1: Base details (left) | Pivot details (right)
        row1_col1, row1_col2 = st.columns(2)
        with row1_col1:
            st.subheader("Current base")
            if current_base is None:
                st.caption("No current base meeting SEPA criteria.")
            else:
                b = current_base
                st.caption(f"**Base type:** {b['base_type']}")
                st.caption(f"Start: {_fmt_date(b['start_date'])} — End: {_fmt_date(b['end_date'])}")
                st.caption(f"Depth: {b['depth_pct']}% — Duration: {b['duration_weeks']} weeks")
                st.caption(f"Resistance (buy point): {b.get('resistance', '—')}")
                st.caption(f"Distance to buy: {_fmt_distance(b)}")
                st.caption(f"Buy point date: {_fmt_date(b.get('buy_point_date'))}")
        with row1_col2:
            st.subheader("Pivot")
            if pivot["forming"]:
                detail = f"{pivot['days']} days, {pivot['range_pct']}% range"
                if pivot.get("tight_closes"):
                    detail += ", tight closes"
                st.caption(f"Pivot forming: Yes ({detail})")
                if pivot.get("pivot_high") is not None:
                    st.caption(f"Pivot high: {pivot['pivot_high']}")
                base_containing = pivot_in_base(pivot, bases)
                if base_containing is not None:
                    label = f"In base: Yes — {base_containing['base_type']}"
                    if base_containing.get("is_current"):
                        label += " (current base)"
                    st.caption(label)
                else:
                    st.caption("In base: No")
            else:
                st.caption("Pivot forming: No")

        st.markdown("---")
        # Row 2: Leadership profile (left) | VCP characteristics (right)
        daily_with_52w = add_52w_high_low(daily_smas)
        rs_ratio = _get_rs_ratio(symbol)
        tt = trend_template(daily_with_52w, rs_ratio=rs_ratio)
        row2_col1, row2_col2 = st.columns(2)
        with row2_col1:
            st.subheader("Leadership profile (Minervini)")
            st.metric("Trend Template", f"{tt['score']}/8", help="8 criteria: price vs SMAs, 52w range, RS")
            for d in tt["details"]:
                status = "Pass" if d["pass"] else "Fail"
                st.caption(f"{status}: {d['name']}" + (f" — {d['detail']}" if d.get("detail") else ""))
            if rs_ratio is not None:
                st.caption(f"RS vs SPY (6m): {rs_ratio:.2f} — {'Outperforming' if rs_ratio >= 1 else 'Underperforming'}")
        with row2_col2:
            st.subheader("VCP characteristics")
            if current_base is not None:
                st.caption(f"Current base VCP-like: {'Yes' if current_base.get('vcp_like') else 'No'}")
            vol_label = pivot_volume_vs_average(df_daily, pivot)
            if vol_label == "below":
                st.caption("Volume at pivot: Below average")
            elif vol_label == "above":
                st.caption("Volume at pivot: Above average")
            else:
                st.caption("Volume at pivot: —")

        st.markdown("---")
        # Row 3: Liquidity risk (metrics and purchase limit)
        st.subheader("Liquidity risk")
        st.caption(
            "Metrics from average daily volume (ADV). Liquidity-based limit feeds into position sizing."
        )
        liq = liquidity_metrics(df_daily)
        max_buy = max_purchase_by_liquidity(
            df_daily,
            max_days_to_exit=DEFAULT_MAX_DAYS_TO_EXIT,
            pct_adv_per_day=DEFAULT_PCT_ADV_PER_DAY,
        )
        ref_shares = st.number_input(
            "Reference position (shares) for days-to-liquidate",
            min_value=1,
            value=100,
            step=50,
            key="sepa_liquidity_ref_shares",
        )
        row3_col1, row3_col2 = st.columns(2)
        with row3_col1:
            if liq["adv_20"] is not None:
                st.caption(f"ADV (20d): {liq['adv_20']:,.0f} shares")
            else:
                st.caption("ADV (20d): —")
            if liq["adv_50"] is not None:
                st.caption(f"ADV (50d): {liq['adv_50']:,.0f} shares")
            else:
                st.caption("ADV (50d): —")
            if liq.get("dollar_adv_20") is not None:
                st.caption(f"Dollar ADV (20d): ${liq['dollar_adv_20']:,.0f}")
            if liq.get("dollar_adv_50") is not None:
                st.caption(f"Dollar ADV (50d): ${liq['dollar_adv_50']:,.0f}")
            adv_for_dtl = liq["adv_20"]
            dtl = days_to_liquidate(float(ref_shares), adv_for_dtl)
            if dtl is not None:
                st.caption(f"Days to liquidate ({ref_shares} shares): {dtl:.2f} days")
            else:
                st.caption(f"Days to liquidate ({ref_shares} shares): —")
        with row3_col2:
            st.caption(
                f"**Liquidity-based limit** (exit in {DEFAULT_MAX_DAYS_TO_EXIT} days at {DEFAULT_PCT_ADV_PER_DAY * 100:.0f}% ADV/day):"
            )
            if max_buy["max_shares"] is not None:
                st.caption(f"Max shares: {max_buy['max_shares']:,.0f}")
            else:
                st.caption("Max shares: —")
            if max_buy["max_dollar"] is not None:
                st.caption(f"Max $: ${max_buy['max_dollar']:,.0f}")
            else:
                st.caption("Max $: —")

        # CAN SLIM checklist (temporarily commented out)
        # st.markdown("---")
        # st.subheader("CAN SLIM checklist")
        # can_items = canslim_checklist(symbol, daily_smas, rs_ratio)
        # can_df = pd.DataFrame([
        #     {"Letter": it["letter"], "Criterion": it["name"], "Status": canslim_status(it["pass"]), "Detail": it["detail"]}
        #     for it in can_items
        # ])
        # st.dataframe(can_df, width="stretch")
else:
    st.info("Select a symbol above to load the daily price and volume chart.")
