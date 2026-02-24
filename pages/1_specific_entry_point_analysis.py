"""
Specific Entry Point Analysis - Analyze and size new trades

This page allows users to analyze specific trade entry points, visualize
historical price action, and size positions with Turtle-style risk
management parameters.
"""

import logging

import pandas as pd
import streamlit as st
import yfinance as yf
from streamlit_lightweight_charts import renderLightweightCharts

st.set_page_config(page_title="Specific Entry Point Analysis", page_icon="📊", layout="wide")

st.title("📊 Specific Entry Point Analysis")
st.subheader("Analyze Entries and Position Sizing for a Single Symbol")
logger = logging.getLogger(__name__)

TIMEFRAMES = {
    "Daily": "1d",
    "Weekly": "1wk",
    "Monthly": "1mo",
}


@st.cache_data(show_spinner=False)
def load_price_data(symbol: str, interval: str):
    try:
        history = yf.download(symbol, period="10y", interval=interval, progress=False)
    except Exception as exc:
        logger.exception("Failed to download %s data for %s", interval, symbol)
        return []

    if history.empty:
        return []

    history = history.dropna().reset_index()
    if "Date" in history.columns:
        date_col = "Date"
    elif "Datetime" in history.columns:
        date_col = "Datetime"
    else:
        datetime_cols = [
            col for col in history.columns
            if pd.api.types.is_datetime64_any_dtype(history[col])
        ]
        if not datetime_cols:
            return []
        date_col = datetime_cols[0]

    history[date_col] = pd.to_datetime(history[date_col], errors="coerce")
    if isinstance(history[date_col].dtype, pd.DatetimeTZDtype):
        history[date_col] = history[date_col].dt.tz_convert(None)
    invalid_date_count = history[date_col].isna().sum()
    if invalid_date_count:
        logger.warning(
            "Dropped %s rows with invalid %s values for %s %s",
            invalid_date_count,
            date_col,
            interval,
            symbol,
        )
    history = history.dropna(subset=[date_col])
    if history.empty:
        return []

    return [
        {
            "time": row[date_col].strftime("%Y-%m-%d"),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
        }
        for _, row in history.iterrows()
    ]


st.caption(
    "Analyze a specific symbol: load its price history, choose a timeframe, "
    "and size a position using Turtle-style risk rules."
)

# Main content area
col1, col2 = st.columns(2)

with col1:
    st.header("Entry Details")

    # Symbol selection
    symbol = st.text_input(
        "Symbol",
        placeholder="e.g., AAPL, GOOGL, ES",
        help="Enter the trading symbol you want to analyze",
    )

    # Direction
    direction = st.radio(
        "Direction",
        options=["Long", "Short"],
        horizontal=True,
    )

    # Entry price
    entry_price = st.number_input(
        "Planned Entry Price",
        min_value=0.0,
        step=0.01,
        format="%.2f",
        help="Planned entry price for this trade",
    )

    # Position size (optional, if you already know it)
    position_size = st.number_input(
        "Position Size (optional)",
        min_value=0,
        step=1,
        help="Number of shares/contracts you plan to trade (optional)",
    )

with col2:
    st.header("Risk Management")

    # Account balance
    account_balance = st.number_input(
        "Account Balance",
        min_value=0.0,
        value=100000.0,
        step=1000.0,
        format="%.2f",
        help="Total account balance for risk calculations",
    )

    # Risk percentage
    risk_percentage = st.slider(
        "Risk Percentage per Trade",
        min_value=0.5,
        max_value=5.0,
        value=2.0,
        step=0.1,
        format="%.1f%%",
        help="Percentage of account to risk on this trade (Turtle standard: 2%)",
    )

    # Stop loss
    stop_loss = st.number_input(
        "Stop Loss Price",
        min_value=0.0,
        step=0.01,
        format="%.2f",
        help="Stop loss price level for this entry",
    )

    # Calculate risk metrics
    if entry_price > 0 and stop_loss > 0:
        if direction == "Long":
            risk_per_unit = entry_price - stop_loss
        else:
            risk_per_unit = stop_loss - entry_price

        if risk_per_unit > 0:
            st.metric("Risk per Unit", f"${risk_per_unit:.2f}")

            # Calculate position size based on risk
            dollar_risk = account_balance * (risk_percentage / 100)
            suggested_size = int(dollar_risk / risk_per_unit)
            st.metric("Suggested Position Size", f"{suggested_size} units")
            st.caption(
                f"Based on ${dollar_risk:.2f} risk "
                f"(${account_balance:,.2f} × {risk_percentage}%)"
            )


st.markdown("---")

st.header("Price Chart")
timeframe_choice = st.radio("Timeframe", list(TIMEFRAMES.keys()), horizontal=True)
symbol_clean = symbol.strip().upper()

if symbol_clean:
    with st.spinner(f"Loading {symbol_clean} {timeframe_choice.lower()} data..."):
        price_data = load_price_data(symbol_clean, TIMEFRAMES[timeframe_choice])

    if price_data:
        renderLightweightCharts(
            [
                {
                    "chart": {
                        "layout": {
                            "background": {"type": "solid", "color": "#0e1117"},
                            "textColor": "#d1d5db",
                        },
                        "height": 380,
                        "rightPriceScale": {"borderColor": "rgba(197,203,206,0.4)"},
                        "timeScale": {"borderColor": "rgba(197,203,206,0.4)"},
                    },
                    "series": [
                        {
                            "type": "candlestick",
                            "data": price_data,
                            "options": {
                                "upColor": "#26a69a",
                                "downColor": "#ef5350",
                                "borderUpColor": "#26a69a",
                                "borderDownColor": "#ef5350",
                                "wickUpColor": "#26a69a",
                                "wickDownColor": "#ef5350",
                            },
                        }
                    ],
                }
            ],
            key=f"chart-{symbol_clean}-{TIMEFRAMES[timeframe_choice]}",
        )
    else:
        st.warning("No price data available for this symbol/timeframe.")
else:
    st.info("Enter a symbol to load the TradingView-style chart.")

st.markdown("---")

# Notes for this specific entry
st.header("Entry Notes")
notes = st.text_area(
    "Notes",
    placeholder="Add any notes or observations about this specific entry (setup, context, news, etc.)...",
    height=100,
    label_visibility="collapsed",
)

# Action buttons
st.markdown("---")
col1, col2, col3 = st.columns([1, 1, 4])

with col1:
    if st.button("📝 Save Entry Analysis", type="primary", width="stretch"):
        if symbol and entry_price > 0:
            st.success(
                f"Entry analysis saved for {direction} {symbol_clean} @ ${entry_price:.2f}"
            )
        else:
            st.error("Please fill in at least Symbol and Planned Entry Price.")

with col2:
    if st.button("🔄 Reset", width="stretch"):
        st.rerun()

# Information section
with st.expander("ℹ️ Turtle Trading Position Sizing Principles"):
    st.write(
        """
        **Key Principles:**

        - **2% Rule**: Risk no more than 2% of account equity on any single position
        - **Unit-Based Sizing**: Calculate position size based on account volatility (N)
        - **Pyramiding**: Add to winning positions in unit increments
        - **Maximum Position Size**: Limit total exposure per market sector

        **Position Sizing Formula:**

        ```
        Dollar Risk = Account Balance × Risk %
        Risk per Unit = |Entry Price - Stop Loss|
        Position Size = Dollar Risk ÷ Risk per Unit
        ```

        For Long positions: Risk per Unit = Entry Price - Stop Loss
        For Short positions: Risk per Unit = Stop Loss - Entry Price
        """
    )

