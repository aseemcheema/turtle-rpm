## Turtle RPM – Architecture and Behavior Overview

Turtle RPM is a **Streamlit-based web application** for **risk and portfolio management** built around the **Turtle Trading System**. It guides a trader through designing position sizes according to Turtle-style risk rules, monitoring and stress‑testing positions, and (optionally) inspecting real portfolio data from an E\*TRADE account.

The project is intentionally compact and script‑oriented: there is no separate backend service. All logic runs inside the Streamlit process, and each page is a self‑contained script that owns its own UI and business logic.

---

## 1. Repository Layout and Roles

At a high level, the repository is organized around a single Streamlit app (`app.py`) and three functional pages under `pages/`:

- **`app.py`**  
  - Main Streamlit entrypoint (`streamlit run app.py`).  
  - Configures global page settings and presents a landing page explaining the app and its tools.

- **`pages/1_position_builder.py` – Position Builder**  
  - Interactive tool for **designing new positions** according to Turtle-style risk rules.  
  - Pulls historical price data via `yfinance`.  
  - Computes risk per unit, dollar risk, and suggested position size based on account balance, risk percentage, and stop loss.

- **`pages/2_position_manager.py` – Position Manager**  
  - Dashboard for **monitoring positions and orders**.  
  - Currently uses **sample/demo data** generated in‑memory via `pandas`.  
  - Computes P&L, P&L%, position value, and “risk to stop” per position, and highlights rows based on risk and profit thresholds.

- **`pages/3_portfolio.py` – Portfolio (E\*TRADE Integration)**  
  - Handles **OAuth 1.0a** authentication with E\*TRADE (sandbox or production).  
  - Fetches account list (to discover `accountIdKey`) and portfolio holdings using E\*TRADE REST APIs.  
  - Uses Streamlit session state to manage tokens and credentials across reruns.

- **`tests/test_position_builder.py`**  
  - `unittest`-based test suite focusing on the `load_price_data` helper in the Position Builder.  
  - Stubs out `yfinance` and ensures date handling and error cases behave correctly.

- **`pyproject.toml`**  
  - Python packaging metadata, including dependencies (`streamlit`, `yfinance`, `requests-oauthlib`, `streamlit-lightweight-charts`, etc.).

- **`README.md`**  
  - Setup instructions, `streamlit run app.py` usage, and E\*TRADE portfolio integration walkthrough.

The notable point is that **navigation and page discovery are entirely delegated to Streamlit**: there is no custom router or app factory. Each file in `pages/` is effectively its own entrypoint executed when that page is selected in the sidebar, which is an idiomatic pattern for small-to-medium Streamlit apps and works well with lightweight cross-page communication via shared keys in `st.session_state` when needed.

---

## 2. Application Entry and Lifecycle

### 2.1 Main entrypoint (`app.py`)

The application is launched via:

```bash
streamlit run app.py
```

`app.py`:
- Calls `st.set_page_config` once at import time to define:
  - Title: “Turtle RPM”
  - Icon: turtle emoji
  - Layout: wide
  - Sidebar: expanded by default
- Renders:
  - A main title and subheader describing the app.  
  - Markdown with a short explanation of the Turtle Trading System and a list of available tools.  
  - A sidebar info block instructing the user to choose a page, plus a simple version caption.

Streamlit’s runtime model means that **every rerun** of the app re-executes the module top‑to‑bottom, relying on Streamlit widgets and `st.session_state` to maintain continuity.

### 2.2 Multi‑page navigation (`pages/` directory)

Streamlit treats each script under `pages/` as a separate page:

- Filenames are prefixed with an **ordering index** (`1_`, `2_`, `3_`) to control sidebar order.
- When the user clicks a page in the sidebar:
  - Streamlit executes that script from top to bottom.  
  - Page-local widgets manage state within that page; shared state is typically kept in `st.session_state`.

Each page also calls `st.set_page_config`. In practice, the first call to `st.set_page_config` in a run takes effect, so additional calls on other pages don’t change global config. This is mostly harmless but worth remembering if per‑page configuration is expected.

---

## 3. Core Domain Concepts

### 3.1 Positions and risk

The central concept is a **trading position** governed by Turtle-style risk rules:

- **Position attributes** (primarily in Position Builder/Manager):
  - Symbol (ticker).  
  - Direction (Long/Short).  
  - Entry Price, Current Price.  
  - Position Size (number of units).  
  - Stop Loss.  
  - Entry Date.  
  - Derived metrics: P&L, P&L%, Position Value, Risk to Stop.

- **Risk management parameters** (Position Builder):
  - **Account Balance** – basis for risk sizing.  
  - **Risk Percentage** – fraction of account to risk per trade (e.g. 2%).  
  - **Stop Loss Price** – exit level if the trade fails.  
  - From these, the page computes:
    - **Risk per Unit** = \(|\text{Entry Price} - \text{Stop Loss}|\) (sign depends on direction).  
    - **Dollar Risk** = \(\text{Account Balance} \times \text{Risk%}\).  
    - **Suggested Position Size** = \(\frac{\text{Dollar Risk}}{\text{Risk per Unit}}\).

These calculations are performed in page code and then surfaced to the user through Streamlit metrics and/or tables. There is no shared “Position” class or explicit domain model type; positions are represented as dictionaries or `pandas.DataFrame` rows.

### 3.2 Portfolio and accounts (E\*TRADE)

In the Portfolio page:

- E\*TRADE credentials & configuration:
  - Consumer Key and Consumer Secret.  
  - Environment: **Sandbox** vs **Production** (selects different base URLs).  
  - Request Token / Secret (pre‑access‑token stage).  
  - Access Token / Secret (final OAuth credentials).  
  - `accountIdKey` (E\*TRADE’s account ID key).

- These values live under a single `st.session_state.etrade_auth` dictionary, which is created and maintained by small helper functions on that page.

---

## 4. Page‑Level Behavior and Data Flow

### 4.1 Position Builder (`pages/1_position_builder.py`)

**Responsibilities**
- Fetch and visualize **historical price data** for a selected symbol and date range.  
- Compute **risk metrics** and **suggested position size** based on user inputs.  
- Present a combined UI that lets a user:
  - Pick a symbol and time resolution.  
  - Inspect a candlestick chart.  
  - Enter account/risk parameters and see suggested sizing.

**Data loading and caching**
- Uses `yfinance.download` to fetch OHLC data.  
- A helper `load_price_data` (decorated with `@st.cache_data`) encapsulates:
  - The `yfinance` call.  
  - Cleaning and standardization of columns.  
  - Conversion into a list of dicts suitable for `streamlit-lightweight-charts`.
- `load_price_data` has careful **date handling**:
  - It searches for a date source in this order:
    1. A `Date` column.  
    2. A `Datetime` column.  
    3. Any column whose dtype is datetime-like.  
  - Coerces these to naive datetimes (drops timezone) and to ISO date strings.  
  - Invalid dates (`NaT` etc.) are dropped, and a warning is logged if rows are removed.  
  - If data is missing or all rows are invalid, it returns an **empty list** instead of raising.

**Visualization**
- Uses `streamlit-lightweight-charts`:
  - The cleaned OHLC list is passed into `renderLightweightCharts`.  
  - Users can change symbol, time frame, and other parameters; data is cached for performance.

**Risk sizing UI**
- Provides input widgets for:
  - Account balance.  
  - Risk percentage per trade.  
  - Entry price & stop price.  
  - Direction (long/short).
- Based on these, it computes:
  - Risk per unit.  
  - Dollar risk.  
  - Suggested position size, rounded as appropriate.

Overall, Position Builder’s main “integration surface” is `yfinance` for price data and `streamlit-lightweight-charts` for visualization. Everything else is computed locally and rendered via Streamlit widgets.

### 4.2 Position Manager (`pages/2_position_manager.py`)

**Responsibilities**
- Provide a **dashboard-like view** over positions and orders.  
- Currently, all data is generated in‑memory and is meant as a **demo / prototype** of the final behavior.

**Data generation**
- Cached helper functions:
  - `get_sample_positions()`: returns a `pandas.DataFrame` describing mock positions.  
  - `get_sample_orders()`: returns a `pandas.DataFrame` describing mock orders.
- These are decorated with `@st.cache_data` so repeated loads are cheap.

**Derivations and metrics**
- For each position:
  - P&L = \((\text{Current} - \text{Entry}) \times \text{Size}\) (sign depends on direction).  
  - P&L% (as a percentage string with `%`).  
  - Position Value = \(\text{Current Price} \times \text{Size}\).  
  - Risk to Stop = remaining downside relative to stop.

**Styling / highlighting**
- A helper like `highlight_risk_rows` operates on a **string P&L% column**:
  - Strips `%` and casts to `float`.  
  - Applies colors:
    - Loss worse than a threshold (e.g. < −5%) → red.  
    - Gain above a threshold (e.g. > 10%) → green.  
  - Everything else is neutral.
- Important **gotcha**: this depends on the `%` formatting being stable.  
  - Any change in representation (localization, added characters) will break the parsing logic.

**Refresh semantics**
- There are “Refresh Positions” and “Refresh Orders” actions:
  - These explicitly call `st.cache_data.clear()` to flush cached data.  
  - Then call `st.rerun()` to re‑execute the page, causing the cached functions to be recomputed.
- This is a coarse-grained cache clear: it affects all `st.cache_data` in the app, not just this page.

### 4.3 Portfolio / E\*TRADE Integration (`pages/3_portfolio.py`)

**Responsibilities**
- Walk the user through the **OAuth 1.0a flow** for E\*TRADE.  
- Let the user:
  - Save consumer key and secret.  
  - Retrieve a **request token**.  
  - Visit the E\*TRADE authorization URL and paste the verifier code.  
  - Exchange the verifier for an **access token**.  
  - Fetch accounts (to obtain `accountIdKey`) and portfolio holdings.

**Session state management**
- A central helper (e.g. `_ensure_auth_state()`) ensures `st.session_state.etrade_auth` exists and contains:
  - Credentials (key/secret).  
  - Tokens (request/access).  
  - Environment selection.  
  - Account ID key.
- `_reset_tokens(auth_state)` is called when credentials are changed:
  - Clears request/access tokens so stale tokens are not reused after key changes.

**OAuth session helpers**
- `_build_oauth_session(...)`:
  - Constructs a `requests_oauthlib.OAuth1Session` given the current keys, secrets, and environment.  
  - Uses base URLs that depend on Sandbox vs Production:
    - Sandbox: `https://apisb.etrade.com`  
    - Production: `https://api.etrade.com`
- `_get_authenticated_session()`:
  - Returns an OAuth session with **access token** attached, or `None` if user has not completed the flow.

**API calls**
- Uses the OAuth session to call:
  - `/oauth/request_token` – obtain the request token.  
  - `/oauth/access_token` – exchange verifier for access token.  
  - `/v1/accounts/list.json` – list accounts to obtain `accountIdKey`.  
  - `/v1/accounts/{accountIdKey}/portfolio.json` – fetch portfolio holdings.
- Responses are shown with `st.json` for transparency.

**Error handling**
- Surrounds HTTP calls in `try`/`except`:
  - On failure, resets tokens (when appropriate) and displays `st.error` messages.  
  - Uses type hints (e.g. `OAuth1Session | None`) for clarity and to guide refactors.

---

## 5. External Dependencies and Their Roles

From `pyproject.toml` and the page implementations, the main dependencies are:

- **`streamlit`**  
  - Core web framework; provides widget primitives, layout, session state, caching, and reruns.

- **`yfinance`**  
  - Fetches historical market data for a given symbol and range (Position Builder).  
  - Returns `pandas.DataFrame`s which are normalized and converted to OHLC lists.

- **`streamlit-lightweight-charts`**  
  - Renders TradingView-style candlestick charts from the cleaned price data.

- **`requests-oauthlib`**  
  - Implements OAuth 1.0a for E\*TRADE integration in the Portfolio page.

- **`pandas`** (indirectly, via `yfinance` and explicit imports in pages)  
  - Used for tabular manipulation and computation in Position Manager and tests.

These dependencies are all used at the page level; there is no separate library layer wrapping them. Any future refactor might extract these interactions into reusable modules, particularly for E\*TRADE and price history.

---

## 6. Testing Strategy and Coverage

### 6.1 Test framework

- Uses Python’s built-in **`unittest`** framework.  
- All current tests live under `tests/test_position_builder.py`.

### 6.2 What is tested

The tests focus exclusively on `load_price_data` in the Position Builder page:

- `test_load_price_data_formats_dates_from_index`  
  - Ensures date index values are converted to ISO date strings in the returned data.

- `test_load_price_data_handles_nonstandard_datetime_column`  
  - Verifies that the function can find and use a non-standard datetime column (e.g. `timestamp`) when standard names are absent.

- `test_load_price_data_returns_empty_when_dates_invalid`  
  - Confirms that invalid datetime data (e.g. all `NaT`) leads to an empty result rather than an exception.

### 6.3 Test mechanics and patterns

- The test module dynamically imports the page script:
  - Uses `importlib.util.spec_from_file_location` to load `pages/1_position_builder.py` as a module.  
  - Registers it as `position_builder` in `sys.modules` for easier access.
- External dependency isolation:
  - Replaces `self.module.yf` with a `types.SimpleNamespace` whose `download` function returns controlled `pandas.DataFrame`s.  
  - This allows testing logic without touching live network or Yahoo’s APIs.
- Caching considerations:
  - `setUp` clears `st.cache_data` on the imported module (if present) to avoid test pollution between cases.

There are currently **no tests** for Position Manager or Portfolio behaviors. As the app matures, those would be natural areas to extend coverage, likely with more explicit separation between UI and logic.

---

## 7. Project-Specific Conventions and Gotchas

### 7.1 Streamlit multi-page nuances

- All pages call `st.set_page_config`, but only the **first call** in a run actually takes effect.  
- Navigating between pages is entirely controlled by Streamlit; there is no custom routing code.
- Import-time side effects:
  - Because the pages are plain scripts, importing them (e.g., in tests) executes top-level Streamlit calls.  
  - In non‑Streamlit contexts, this can be surprising and may require monkeypatching or test config.

### 7.2 Caching and refresh behavior

- Data‑loading helpers are commonly decorated with `@st.cache_data`.  
- In Position Manager, “Refresh” buttons:
  - Call `st.cache_data.clear()` (global cache wipe).  
  - Then `st.rerun()` to reload data.
- This **clears all cached data across pages**, not just sample positions/orders. If more cached functions are added in the future, this broad clear could have unintended performance or UX implications.

### 7.3 Date handling robustness in `load_price_data`

- The function is intentionally defensive:
  - It identifies datetime information via standard names first, then falls back to type heuristics.  
  - It coerces values to datetime with `errors="coerce"` and drops invalid rows.  
  - It logs warnings when it discards data, and returns `[]` when no valid dates remain.
- This makes it robust against a variety of input shapes, but:
  - It can silently drop rows; callers should be prepared for fewer rows than expected.  
  - Adding new date columns with unexpected types should be tested to ensure the heuristic still behaves as desired.

### 7.4 E\*TRADE auth state and deployment

- All E\*TRADE credentials and tokens live in `st.session_state.etrade_auth`:
  - Convenient for a single-user local app.  
  - Insufficient for a multi-user or shared deployment where secrets must be isolated and persisted.
- `_reset_tokens` is used to avoid reusing stale tokens after credential changes.  
- Sandbox vs Production choice is entirely UI-driven; there is no environment guardrail to prevent accidental use of production with test keys.

### 7.5 Styling-driven logic in Position Manager

- Risk highlighting logic operates on **stringified percentages**:
  - It assumes values end with `%` and can be converted back to `float`.  
  - Any change in formatting (e.g., localization) will break this.
- Thresholds are currently **hard-coded** in the page:
  - Loss beyond a certain percentage is red; large gains are green.  
  - There is no shared config or user control over these thresholds yet.

---

## 8. Opportunities for Extension and Refactoring

While not strictly part of the existing behavior, the current design suggests several natural extension paths:

- **Extract reusable services**  
  - E\*TRADE API logic and price history loading could be pulled into modules under a `turtle_rpm/` package.  
  - This would simplify testing and reduce duplication if more pages need these capabilities.

- **Introduce formal domain models**  
  - Positions, orders, and portfolios are currently dictionaries/DataFrame rows.  
  - Lightweight dataclasses or pydantic models could make invariants and field meanings explicit.

- **Configuration centralization**  
  - URLs, risk thresholds, and UI defaults are currently scattered across files.  
  - A simple config module or environment-variable-based configuration would help with deployment flexibility.

- **Expand test coverage**  
  - Portfolio: tests around OAuth helpers and URL construction (with HTTP mocked).  
  - Position Manager: tests for P&L computations and highlight logic independent of Streamlit.

Despite these potential improvements, the current codebase is intentionally straightforward: its primary goal is to provide a clear, interactive environment for experimenting with Turtle-style risk and managing a trading portfolio through a familiar Streamlit workflow.

