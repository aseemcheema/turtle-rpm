"""
Portfolio - Connect to E*TRADE and view account details

This page guides users through the OAuth 1.0a authentication flow required
by the E*TRADE API and provides a simple portfolio lookup.
"""

from typing import Dict

import streamlit as st
from requests_oauthlib import OAuth1Session


st.set_page_config(page_title="Portfolio", page_icon="💼", layout="wide")


BASE_URLS: Dict[str, str] = {
    "Sandbox": "https://apisb.etrade.com",
    "Production": "https://api.etrade.com",
}
AUTH_URL = "https://us.etrade.com/e/t/etws/authorize"


def _ensure_auth_state() -> Dict[str, str]:
    """Initialize session state storage for E*TRADE credentials."""
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
        # Add any new keys introduced after initial load
        for key, value in defaults.items():
            st.session_state.etrade_auth.setdefault(key, value)
    return st.session_state.etrade_auth


def _reset_tokens(auth_state: Dict[str, str]) -> None:
    """Clear any cached tokens when credentials change."""
    auth_state["request_token"] = None
    auth_state["request_token_secret"] = None
    auth_state["access_token"] = None
    auth_state["access_token_secret"] = None


def _build_oauth_session(auth_state: Dict[str, str], verifier: str | None = None) -> OAuth1Session:
    """Create an OAuth1 session configured for the selected environment."""
    return OAuth1Session(
        auth_state["consumer_key"],
        client_secret=auth_state["consumer_secret"],
        callback_uri="oob",
        resource_owner_key=auth_state.get("request_token"),
        resource_owner_secret=auth_state.get("request_token_secret"),
        verifier=verifier,
    )


auth_state = _ensure_auth_state()

st.title("💼 Portfolio")
st.subheader("Connect to your E*TRADE account and pull portfolio data")

# Credential capture
st.markdown("### E*TRADE API Credentials")
with st.form("etrade_keys"):
    col1, col2 = st.columns(2)
    with col1:
        consumer_key = st.text_input(
            "Consumer Key",
            value=auth_state["consumer_key"],
            placeholder="Provided by E*TRADE",
            help="Also known as API key",
        ).strip()
        environment = st.radio(
            "Environment",
            options=list(BASE_URLS.keys()),
            index=list(BASE_URLS.keys()).index(auth_state["environment"]),
            help="Use Sandbox for testing, Production for live accounts",
            horizontal=True,
        )
    with col2:
        consumer_secret = st.text_input(
            "Consumer Secret",
            value=auth_state["consumer_secret"],
            placeholder="Secret from E*TRADE",
            type="password",
            help="Do not share this secret",
        ).strip()
        account_id_key = st.text_input(
            "Account ID Key (optional)",
            value=auth_state.get("account_id_key", ""),
            help="Required for portfolio endpoint. Retrieve it from the accounts/list response.",
        ).strip()

    if st.form_submit_button("Save API Keys", type="primary"):
        auth_state["consumer_key"] = consumer_key
        auth_state["consumer_secret"] = consumer_secret
        auth_state["environment"] = environment
        auth_state["account_id_key"] = account_id_key
        _reset_tokens(auth_state)
        st.success("Credentials saved. Continue with the OAuth steps below.")

st.markdown("---")

col1, col2 = st.columns([1, 1])

with col1:
    st.markdown("### Step 1: Get request token")
    request_button = st.button(
        "Get Request Token",
        type="primary",
        disabled=not (auth_state["consumer_key"] and auth_state["consumer_secret"]),
    )
    if request_button:
        try:
            oauth = _build_oauth_session(auth_state)
            token_response = oauth.fetch_request_token(f"{BASE_URLS[auth_state['environment']]}/oauth/request_token")
            auth_state["request_token"] = token_response.get("oauth_token")
            auth_state["request_token_secret"] = token_response.get("oauth_token_secret")
            st.success("Request token received. Authorize the app in the next step.")
        except Exception as exc:  # noqa: BLE001
            _reset_tokens(auth_state)
            st.error(f"Failed to get request token: {exc}")

    if auth_state["request_token"]:
        auth_link = f"{AUTH_URL}?key={auth_state['consumer_key']}&token={auth_state['request_token']}"
        st.info("Open this URL, sign in to E*TRADE, and paste the verification code below.")
        st.code(auth_link, language="text")

with col2:
    st.markdown("### Step 2: Exchange for access token")
    verifier_code = st.text_input(
        "Verification Code (oauth_verifier)",
        value="",
        placeholder="Paste code from E*TRADE authorization page",
        disabled=not auth_state["request_token"],
    ).strip()
    exchange_button = st.button(
        "Exchange Access Token",
        type="primary",
        disabled=not (auth_state["request_token"] and verifier_code),
    )
    if exchange_button:
        try:
            oauth = _build_oauth_session(auth_state, verifier=verifier_code)
            access_response = oauth.fetch_access_token(f"{BASE_URLS[auth_state['environment']]}/oauth/access_token")
            auth_state["access_token"] = access_response.get("oauth_token")
            auth_state["access_token_secret"] = access_response.get("oauth_token_secret")
            st.success("Access token created. You can now query accounts and portfolios.")
        except Exception as exc:  # noqa: BLE001
            _reset_tokens(auth_state)
            st.error(f"Failed to exchange access token: {exc}")

st.markdown("---")

# Connected state and API helpers
st.markdown("### Portfolio lookup")
connected = bool(auth_state["access_token"] and auth_state["access_token_secret"])
status_col1, status_col2 = st.columns(2)

with status_col1:
    st.metric("Connection status", "Connected" if connected else "Not connected")
with status_col2:
    st.caption("Use Sandbox until ready for live trading. Tokens reset when keys change.")

def _get_authenticated_session() -> OAuth1Session | None:
    if not connected:
        return None
    return OAuth1Session(
        auth_state["consumer_key"],
        client_secret=auth_state["consumer_secret"],
        resource_owner_key=auth_state["access_token"],
        resource_owner_secret=auth_state["access_token_secret"],
    )


api_col1, api_col2 = st.columns(2)

with api_col1:
    st.markdown("#### 1) Accounts list")
    st.caption("Use this to retrieve accountIdKey values for portfolio calls.")
    if st.button("Fetch Accounts", disabled=not connected):
        session = _get_authenticated_session()
        if session:
            try:
                response = session.get(f"{BASE_URLS[auth_state['environment']]}/v1/accounts/list.json")
                if response.ok:
                    st.json(response.json())
                else:
                    st.error(f"Accounts request failed ({response.status_code}): {response.text}")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Unable to call accounts endpoint: {exc}")

with api_col2:
    st.markdown("#### 2) Portfolio snapshot")
    st.caption("Provide the accountIdKey from the accounts list to pull holdings.")
    account_id_for_lookup = st.text_input(
        "Account ID Key",
        value=auth_state.get("account_id_key", ""),
        key="portfolio_account_input",
        disabled=not connected,
    ).strip()
    if st.button("Fetch Portfolio", disabled=not (connected and account_id_for_lookup)):
        session = _get_authenticated_session()
        if session:
            auth_state["account_id_key"] = account_id_for_lookup
            try:
                url = f"{BASE_URLS[auth_state['environment']]}/v1/accounts/{account_id_for_lookup}/portfolio.json"
                response = session.get(url)
                if response.ok:
                    st.json(response.json())
                else:
                    st.error(f"Portfolio request failed ({response.status_code}): {response.text}")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Unable to call portfolio endpoint: {exc}")

with st.expander("ℹ️ E*TRADE OAuth flow (summary)"):
    st.write(
        """
        1. Request a **request token** with your consumer key/secret (`/oauth/request_token`).
        2. Direct the user to the **authorization URL** displayed above and collect the `oauth_verifier`.
        3. Exchange the verifier for an **access token** using `/oauth/access_token`.
        4. Call account or portfolio endpoints with the access token. The `accounts/list` call returns
           the `accountIdKey` needed for portfolio lookups.
        """
    )
