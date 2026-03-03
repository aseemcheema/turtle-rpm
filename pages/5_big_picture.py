"""
Big Picture – distribution days, stalling days, and follow-through days.

Identifies market days that signal tops (distribution), potential reversals (stalling),
and rally confirmation (follow-through) for major indices and ETFs over 2, 4, and 6 weeks.
"""

import streamlit as st

from turtle_rpm.big_picture import classify_days, get_days_in_window
from turtle_rpm.sepa import get_daily_ohlcv

INSTRUMENTS = [
    ("S&P 500", "^GSPC"),
    ("SPY", "SPY"),
    ("QQQ", "QQQ"),
    ("NASDAQ Composite", "^IXIC"),
    ("NYSE Composite", "^NYA"),
    ("Dow Jones (DJIA)", "^DJI"),
]

st.set_page_config(page_title="Big Picture", page_icon="🖼️", layout="wide")
st.title("Big Picture")
st.caption(
    "Distribution days (volume up, price down >0.2%) can signal market tops. "
    "Stalling days (volume up, |price change| ≤0.2%) can signal a change in direction. "
    "Follow-through days (volume up, price up >0.2%) confirm rallies."
)

option = st.selectbox(
    "Instrument",
    options=[label for label, _ in INSTRUMENTS],
    index=0,
    key="big_picture_instrument",
)
ticker = next(t for label, t in INSTRUMENTS if label == option)

with st.spinner(f"Loading {option}..."):
    df_daily = get_daily_ohlcv(ticker, years=1)

if df_daily.empty or len(df_daily) < 2:
    st.warning("No data for this symbol. Try another instrument.")
    st.stop()

classified = classify_days(df_daily)

for weeks in (2, 4, 6):
    st.subheader(f"Last {weeks} weeks")
    window = get_days_in_window(classified, weeks)
    if window.empty:
        st.caption("No days in this window.")
        continue
    display = window.copy()
    display = display.reset_index()
    display["Date"] = display["Date"].dt.strftime("%Y-%m-%d")
    display = display.rename(columns={"pct_change": "Chg %", "volume_vs_prev": "Vol vs prev", "day_type": "Day type"})
    display["Chg %"] = display["Chg %"].round(2)
    if "Volume" in display.columns:
        display["Volume"] = display["Volume"].astype(int)
    st.dataframe(
        display[["Date", "Close", "Chg %", "Volume", "Vol vs prev", "Day type"]],
        column_config={
            "Date": st.column_config.TextColumn(),
            "Close": st.column_config.NumberColumn(format="%.2f"),
            "Chg %": st.column_config.NumberColumn(format="%.2f%%"),
            "Day type": st.column_config.TextColumn(),
        },
        hide_index=True,
    )
