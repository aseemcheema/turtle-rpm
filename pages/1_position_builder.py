"""
Position Builder - Create and configure new trading positions

This page allows users to build new positions with proper risk management
parameters based on the Turtle Trading System principles.
"""

import streamlit as st

st.set_page_config(page_title="Position Builder", page_icon="📊", layout="wide")

st.title("📊 Position Builder")
st.subheader("Create New Trading Positions")

# Main content area
col1, col2 = st.columns(2)

with col1:
    st.header("Position Details")
    
    # Symbol selection
    symbol = st.text_input(
        "Symbol",
        placeholder="e.g., AAPL, GOOGL, ES",
        help="Enter the trading symbol"
    )
    
    # Direction
    direction = st.radio(
        "Direction",
        options=["Long", "Short"],
        horizontal=True
    )
    
    # Entry price
    entry_price = st.number_input(
        "Entry Price",
        min_value=0.0,
        step=0.01,
        format="%.2f",
        help="Planned entry price for the position"
    )
    
    # Position size
    position_size = st.number_input(
        "Position Size",
        min_value=0,
        step=1,
        help="Number of shares/contracts"
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
        help="Total account balance for risk calculations"
    )
    
    # Risk percentage
    risk_percentage = st.slider(
        "Risk Percentage",
        min_value=0.5,
        max_value=5.0,
        value=2.0,
        step=0.1,
        format="%.1f%%",
        help="Percentage of account to risk on this position (Turtle standard: 2%)"
    )
    
    # Stop loss
    stop_loss = st.number_input(
        "Stop Loss Price",
        min_value=0.0,
        step=0.01,
        format="%.2f",
        help="Stop loss price level"
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
            st.caption(f"Based on ${dollar_risk:.2f} risk (${account_balance:,.2f} × {risk_percentage}%)")

st.markdown("---")

# Position notes
st.header("Position Notes")
notes = st.text_area(
    "Notes",
    placeholder="Add any notes or observations about this position...",
    height=100,
    label_visibility="collapsed"
)

# Action buttons
st.markdown("---")
col1, col2, col3 = st.columns([1, 1, 4])

with col1:
    if st.button("📝 Create Position", type="primary", use_container_width=True):
        if symbol and entry_price > 0 and position_size > 0:
            st.success(f"Position created: {direction} {position_size} {symbol} @ ${entry_price:.2f}")
            st.info("💡 Navigate to Position Manager to view and manage this position")
        else:
            st.error("Please fill in all required fields (Symbol, Entry Price, Position Size)")

with col2:
    if st.button("🔄 Reset", use_container_width=True):
        st.rerun()

# Information section
with st.expander("ℹ️ Turtle Trading Position Sizing Principles"):
    st.write("""
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
    """)
