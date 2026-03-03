"""
Orders – E*TRADE order history sync and local table.

Reuses st.session_state.etrade_auth from the Portfolio page. Sync downloads
order history (incrementally) and stores it in SQLite; the table reads from local DB.
"""

import threading
import time
from pathlib import Path

import pandas as pd
import streamlit as st
from requests_oauthlib import OAuth1Session

from turtle_rpm.etrade_orders import (
    get_db_path,
    get_last_ingested_at,
    get_orders,
    init_db,
    sync_orders,
)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASE_URLS = {
    "Sandbox": "https://apisb.etrade.com",
    "Production": "https://api.etrade.com",
}


def _ensure_auth_state():
    """Ensure etrade_auth exists in session state (same keys as Portfolio page)."""
    defaults = {
        "consumer_key": "",
        "consumer_secret": "",
        "environment": "Sandbox",
        "request_token": None,
        "request_token_secret": None,
        "access_token": None,
        "access_token_secret": None,
        "account_id_key": "",
    }
    if "etrade_auth" not in st.session_state:
        st.session_state.etrade_auth = defaults.copy()
    else:
        for key, value in defaults.items():
            st.session_state.etrade_auth.setdefault(key, value)
    return st.session_state.etrade_auth


def _get_authenticated_session():
    """Build OAuth1Session for API calls if we have access token."""
    auth = st.session_state.get("etrade_auth") or _ensure_auth_state()
    if not auth.get("access_token") or not auth.get("access_token_secret"):
        return None
    return OAuth1Session(
        auth["consumer_key"],
        client_secret=auth["consumer_secret"],
        resource_owner_key=auth["access_token"],
        resource_owner_secret=auth["access_token_secret"],
    )


st.set_page_config(page_title="Orders", page_icon="📜", layout="wide")
st.title("Orders")
st.caption("Sync E*TRADE order history and view it from local storage.")

auth_state = _ensure_auth_state()
connected = bool(auth_state.get("access_token") and auth_state.get("access_token_secret"))

if not connected:
    st.info(
        "Not connected to E*TRADE. Complete OAuth on the **Portfolio** page (consumer key, request token, exchange for access token), then return here to sync and view orders."
    )
    st.stop()

db_path = get_db_path(_PROJECT_ROOT)
init_db(db_path)

account_id_key = st.text_input(
    "Account ID Key",
    value=auth_state.get("account_id_key", ""),
    placeholder="From Portfolio → Accounts list",
    key="orders_account_id",
).strip()

if not account_id_key:
    st.warning("Enter an Account ID Key to sync or view orders.")
    st.stop()

st.markdown("### Sync order history")
if st.button("Sync order history", type="primary", key="orders_sync_btn"):
    session = _get_authenticated_session()
    if session:
        base_url = BASE_URLS.get(auth_state.get("environment", "Sandbox"), BASE_URLS["Sandbox"])
        progress = {
            "message": "Starting…",
            "done": False,
            "result": None,
            "error": None,
            "orders_page": 0,
            "orders_max_pages": 1,
            "orders_total": 0,
        }

        def run_sync() -> None:
            try:
                def on_progress(msg: str) -> None:
                    progress["message"] = msg
                inserted, msg = sync_orders(
                    session,
                    base_url,
                    account_id_key,
                    db_path,
                    progress_callback=on_progress,
                    progress_dict=progress,
                )
                progress["result"] = (inserted, msg)
            except Exception as e:
                progress["error"] = str(e)
            finally:
                progress["done"] = True

        thread = threading.Thread(target=run_sync, daemon=True)
        thread.start()
        status_placeholder = st.empty()
        progress_bar_placeholder = st.empty()
        while thread.is_alive() or not progress["done"]:
            p = progress
            page, max_p = p.get("orders_page", 0), p.get("orders_max_pages", 1)
            total_orders = p.get("orders_total", 0)
            ratio = page / max_p if max_p else 0
            status_placeholder.markdown(
                f"**Sync progress**  \n{p['message']}  \n\n"
                f"Page **{page}** of **{max_p}** · **{total_orders:,}** orders so far"
            )
            if page > 0 and max_p > 0:
                progress_bar_placeholder.progress(min(ratio, 1.0))
            time.sleep(0.5)
        thread.join(timeout=0.1)
        status_placeholder.empty()
        progress_bar_placeholder.empty()
        if progress.get("error"):
            st.error(f"Sync failed: {progress['error']}")
            err = progress["error"]
            if "404" in err or "Resource not found" in err:
                st.info(
                    "**404 tip:** Use the Account ID Key from the **Portfolio** page for the same "
                    "environment (Sandbox or Production) you selected there. Some accounts may not "
                    "support the Orders API."
                )
        else:
            st.success(progress.get("result", (0, ""))[1])
    else:
        st.error("Not connected. Re-authorize on the Portfolio page.")

last_synced = get_last_ingested_at(account_id_key, db_path)
if last_synced:
    st.caption(f"Last synced: {last_synced}")

st.markdown("### Orders (local)")
orders = get_orders(account_id_key, db_path=db_path)
if not orders:
    st.write("No orders in local storage. Run **Sync order history** above.")
else:
    # Build display table from flattened fields
    rows = []
    for o in orders:
        placed = o.get("placed_time") or o.get("placedTime")
        if placed and isinstance(placed, (int, float)):
            from datetime import datetime, timezone
            try:
                dt = datetime.fromtimestamp(placed / 1000.0, tz=timezone.utc)
                placed_str = dt.strftime("%Y-%m-%d %H:%M")
            except (ValueError, OSError):
                placed_str = str(placed)
        else:
            placed_str = str(placed) if placed else ""
        rows.append({
            "order_id": o.get("order_id"),
            "placed": placed_str,
            "status": o.get("status", ""),
            "symbol": o.get("symbol", ""),
            "side": o.get("orderAction", ""),
            "quantity": o.get("quantity", ""),
            "order_type": o.get("orderType", ""),
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, width="stretch")
