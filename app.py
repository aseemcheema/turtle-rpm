"""
Turtle RPM – entrypoint.

Uses st.navigation so the sidebar shows "Home" (and other pages) with icons.
"""

import streamlit as st

st.set_page_config(
    page_title="Home",
    page_icon="🐢",
    layout="wide",
    initial_sidebar_state="expanded",
)

pg = st.navigation([
    st.Page("pages/home.py", title="Home", icon="🏠", default=True),
    st.Page(
        "pages/1_specific_entry_point_analysis.py",
        title="Specific Entry Point Analysis",
        icon="📊",
    ),
    st.Page(
        "pages/2_pivot_breakouts.py",
        title="Pivot Breakouts Tomorrow",
        icon="📋",
    ),
    st.Page("pages/3_portfolio.py", title="Portfolio", icon="💼"),
    st.Page("pages/4_orders.py", title="Orders", icon="📜"),
])

with st.sidebar:
    st.caption("Turtle RPM v0.1.0")

pg.run()
