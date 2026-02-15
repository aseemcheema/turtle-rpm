"""
Position Manager - Monitor and manage all open positions and orders

This page lists all open positions and orders with the ability to highlight
various risk elements for comprehensive portfolio management.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="Position Manager", page_icon="📈", layout="wide")

st.title("📈 Position Manager")
st.subheader("Monitor Open Positions and Orders")

# Create sample data for demonstration
# In a real application, this would be loaded from a database or trading API
@st.cache_data
def get_sample_positions():
    """Generate sample position data for demonstration"""
    return pd.DataFrame({
        "Symbol": ["AAPL", "GOOGL", "MSFT", "TSLA"],
        "Direction": ["Long", "Long", "Short", "Long"],
        "Entry Price": [150.25, 2800.50, 380.75, 245.00],
        "Current Price": [155.30, 2850.00, 375.20, 240.50],
        "Position Size": [100, 10, 50, 80],
        "Stop Loss": [145.00, 2750.00, 395.00, 235.00],
        "Entry Date": [
            datetime.now() - timedelta(days=5),
            datetime.now() - timedelta(days=3),
            datetime.now() - timedelta(days=7),
            datetime.now() - timedelta(days=2),
        ],
    })

@st.cache_data
def get_sample_orders():
    """Generate sample order data for demonstration"""
    return pd.DataFrame({
        "Symbol": ["AMZN", "NVDA"],
        "Direction": ["Long", "Long"],
        "Order Type": ["Limit", "Stop"],
        "Order Price": [3200.00, 480.00],
        "Quantity": [15, 100],
        "Status": ["Pending", "Pending"],
        "Created": [
            datetime.now() - timedelta(hours=2),
            datetime.now() - timedelta(hours=5),
        ],
    })

# Display controls
st.markdown("### Display Options")
col1, col2, col3 = st.columns(3)

with col1:
    show_positions = st.checkbox("Show Positions", value=True)

with col2:
    show_orders = st.checkbox("Show Open Orders", value=True)

with col3:
    highlight_risk = st.checkbox("Highlight Risk Elements", value=False)

st.markdown("---")

# Positions section
if show_positions:
    st.header("📊 Open Positions")
    
    positions_df = get_sample_positions()
    
    # Calculate P&L and risk metrics
    positions_df["P&L"] = positions_df.apply(
        lambda row: (row["Current Price"] - row["Entry Price"]) * row["Position Size"]
        if row["Direction"] == "Long"
        else (row["Entry Price"] - row["Current Price"]) * row["Position Size"],
        axis=1
    )
    
    positions_df["P&L %"] = positions_df.apply(
        lambda row: ((row["Current Price"] - row["Entry Price"]) / row["Entry Price"] * 100)
        if row["Direction"] == "Long"
        else ((row["Entry Price"] - row["Current Price"]) / row["Entry Price"] * 100),
        axis=1
    )
    
    positions_df["Position Value"] = positions_df["Current Price"] * positions_df["Position Size"]
    
    positions_df["Risk to Stop"] = positions_df.apply(
        lambda row: abs(row["Current Price"] - row["Stop Loss"]) * row["Position Size"],
        axis=1
    )
    
    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    
    total_positions = len(positions_df)
    total_value = positions_df["Position Value"].sum()
    total_pnl = positions_df["P&L"].sum()
    total_risk = positions_df["Risk to Stop"].sum()
    
    col1.metric("Total Positions", total_positions)
    col2.metric("Total Value", f"${total_value:,.2f}")
    pnl_pct = (total_pnl/total_value*100) if total_value > 0 else 0
    col3.metric("Total P&L", f"${total_pnl:,.2f}", delta=f"{pnl_pct:.2f}%")
    col4.metric("Total Risk Exposure", f"${total_risk:,.2f}")
    
    st.markdown("---")
    
    # Format dataframe for display
    display_df = positions_df.copy()
    display_df["Entry Date"] = display_df["Entry Date"].dt.strftime("%Y-%m-%d")
    display_df["Entry Price"] = display_df["Entry Price"].apply(lambda x: f"${x:.2f}")
    display_df["Current Price"] = display_df["Current Price"].apply(lambda x: f"${x:.2f}")
    display_df["Stop Loss"] = display_df["Stop Loss"].apply(lambda x: f"${x:.2f}")
    display_df["Position Value"] = display_df["Position Value"].apply(lambda x: f"${x:,.2f}")
    display_df["P&L"] = display_df["P&L"].apply(lambda x: f"${x:,.2f}")
    display_df["P&L %"] = display_df["P&L %"].apply(lambda x: f"{x:.2f}%")
    display_df["Risk to Stop"] = display_df["Risk to Stop"].apply(lambda x: f"${x:,.2f}")
    
    # Apply styling if risk highlighting is enabled
    def highlight_risk_rows(row):
        """Highlight rows based on risk conditions"""
        if not highlight_risk:
            return [""] * len(row)
        
        # Extract numeric P&L percentage
        pnl_pct = float(row["P&L %"].rstrip("%"))
        
        if pnl_pct < -5:  # More than 5% loss
            return ["background-color: #ffebee"] * len(row)  # Light red
        elif pnl_pct > 10:  # More than 10% gain
            return ["background-color: #e8f5e9"] * len(row)  # Light green
        return [""] * len(row)
    
    if highlight_risk:
        styled_df = display_df.style.apply(highlight_risk_rows, axis=1)
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
    else:
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    # Action buttons for positions
    st.markdown("#### Position Actions")
    col1, col2, col3 = st.columns([1, 1, 4])
    
    with col1:
        if st.button("🔄 Refresh Positions", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    with col2:
        if st.button("📤 Export Positions", use_container_width=True):
            st.info("Export functionality will be available in future updates")

# Orders section
if show_orders:
    st.markdown("---")
    st.header("📋 Open Orders")
    
    orders_df = get_sample_orders()
    
    if len(orders_df) > 0:
        # Format orders for display
        display_orders = orders_df.copy()
        display_orders["Created"] = display_orders["Created"].dt.strftime("%Y-%m-%d %H:%M")
        display_orders["Order Price"] = display_orders["Order Price"].apply(lambda x: f"${x:.2f}")
        
        st.dataframe(display_orders, use_container_width=True, hide_index=True)
        
        # Action buttons for orders
        col1, col2, col3 = st.columns([1, 1, 4])
        
        with col1:
            if st.button("🔄 Refresh Orders", use_container_width=True):
                st.cache_data.clear()
                st.rerun()
        
        with col2:
            if st.button("❌ Cancel All Orders", use_container_width=True):
                st.warning("Order cancellation functionality will be available in future updates")
    else:
        st.info("No open orders at this time")

# Risk Analysis Section
st.markdown("---")
with st.expander("📊 Risk Analysis & Insights"):
    st.write("""
    ### Risk Elements to Monitor
    
    **Highlighted Risk Conditions:**
    - 🔴 **Red Background**: Positions with > 5% loss (consider reviewing stop loss)
    - 🟢 **Green Background**: Positions with > 10% gain (consider profit taking or trailing stops)
    
    **Key Metrics:**
    - **Risk to Stop**: Total dollar amount at risk if all stops are hit
    - **Position Value**: Current market value of each position
    - **P&L**: Realized profit/loss for each position
    
    **Future Enhancements:**
    - Sector exposure analysis
    - Correlation risk between positions
    - Maximum drawdown tracking
    - Risk-adjusted returns (Sharpe ratio)
    - Turtle-specific metrics (N-based position sizing)
    """)
