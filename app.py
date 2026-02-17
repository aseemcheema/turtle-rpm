"""
Turtle RPM - Risk and Portfolio Management Tool for Turtle Trading System

Main entry point for the Streamlit application.
"""

import streamlit as st

# Configure the page
st.set_page_config(
    page_title="Turtle RPM",
    page_icon="🐢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Main page content
st.title("🐢 Turtle RPM")
st.subheader("Risk and Portfolio Management Tool for the Turtle Trading System")

st.write("""
Welcome to Turtle RPM, your comprehensive risk and portfolio management tool 
based on the legendary Turtle Trading System.

### Available Tools

Use the sidebar to navigate between:

- **Position Builder**: Create and configure new trading positions
- **Position Manager**: Monitor and manage all open positions and orders

### About the Turtle Trading System

The Turtle Trading System is one of the most famous trading experiments in history, 
demonstrating that successful trading can be taught through a systematic approach 
to risk management and position sizing.
""")

# Display some basic info in the sidebar
with st.sidebar:
    st.info("👈 Select a page from the navigation above to get started")
    
    st.markdown("---")
    st.caption("Turtle RPM v0.1.0")
