"""
Home page content for Turtle RPM.
"""

import streamlit as st

st.title("🐢 Turtle RPM")
st.subheader("Risk and Portfolio Management Tool for the Turtle Trading System")

st.write(
    """
Welcome to Turtle RPM, your comprehensive risk and portfolio management tool
based on the legendary Turtle Trading System.
"""
)

st.markdown("### Tools in this app")

st.write(
    """
Use the navigation to access:

- **Home**: This overview page and entry point to the rest of the app.
- **Specific Entry Point Analysis**: Analyze a single symbol's entry setup, visualize historical
  price action, and size a position using Turtle-style risk rules.
- **Portfolio**: Connect to your E*TRADE account (Sandbox or Production) and inspect accounts
  and portfolio holdings.
"""
)

st.markdown("### Quick links")

# Title-style quick links: one icon per link, labels as titles
c1, c2, c3 = st.columns(3)
with c1:
    st.page_link("pages/home.py", label="Home", icon="🏠")
with c2:
    st.page_link(
        "pages/1_specific_entry_point_analysis.py",
        label="Specific Entry Point Analysis",
        icon="📊",
    )
with c3:
    st.page_link("pages/3_portfolio.py", label="Portfolio", icon="💼")

st.markdown("### About the Turtle Trading System")

st.write(
    """
The Turtle Trading System is one of the most famous trading experiments in history,
demonstrating that successful trading can be taught through a systematic approach
to risk management and position sizing.
"""
)

with st.sidebar:
    st.info("👈 Select a page from the navigation above or use the quick links to get started")
