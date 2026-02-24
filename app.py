"""
Home - Turtle RPM

Main entry point and overview for the Turtle RPM Streamlit application.
"""

import streamlit as st

# Configure the page
st.set_page_config(
    page_title="Home",
    page_icon="🐢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Main page content
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

st.page_link("app.py", label="🏠 Home", icon="🏠")
st.page_link(
    "pages/1_specific_entry_point_analysis.py",
    label="📊 Specific Entry Point Analysis",
    icon="📊",
)
st.page_link("pages/3_portfolio.py", label="💼 Portfolio", icon="💼")

st.markdown("### About the Turtle Trading System")

st.write(
    """
The Turtle Trading System is one of the most famous trading experiments in history,
demonstrating that successful trading can be taught through a systematic approach
to risk management and position sizing.
"""
)

# Display some basic info in the sidebar
with st.sidebar:
    st.info("👈 Select a page from the navigation above or use the quick links on Home to get started")

    st.markdown("---")
    st.caption("Turtle RPM v0.1.0")
