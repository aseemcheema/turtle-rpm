# Pattern Recognition, Leadership Profile, and CAN SLIM Plan

## Current state

- **Bases**: [turtle_rpm/sepa.py](turtle_rpm/sepa.py) detects six base types (cup completion cheat, low cheat, cup w/ handle, double bottom, Darvas box, Power Play), computes resistance and backward-looking buy point date, and marks current vs past base.
- **Page**: [pages/1_specific_entry_point_analysis.py](pages/1_specific_entry_point_analysis.py) shows a table: Current?, Base type, Start date, Depth (%), Duration (weeks), Buy point date, Buy point price.
- **Data**: Daily/weekly OHLC(V) via yfinance; 50/150/200 SMA and uptrend check in-house. No relative strength, no fundamentals, no external pattern libraries.

---

## 1. Pattern recognition: buy-point proximity and quality

### 1.1 Closest to buy point (scoring)

- **Goal**: Rank or highlight stocks/bases that are nearest to a valid buy point (not yet broken out but close).
- **Metric**: For the **current base** (and optionally for any base at its end date), compute **distance to buy point** = (resistance - current_close) / resistance × 100 (percent below resistance). Smaller = closer to buy.
- **Implementation**: In `find_bases` (or a post-pass), for each base add `distance_pct` when we have latest close (e.g. segment["Close"].iloc[-1]) and resistance. For the table, add a column **Distance to buy (%)** (or **% below buy point**). Sort or display so "closest to buy" is obvious (e.g. current base first, then by distance_pct ascending).
- **"At buy point"**: If buy_point_date is not None, distance is 0 or "At/above"; if "Not yet", show the percent below resistance.

### 1.2 Libraries vs in-house

- **Preferred libraries** (e.g. [pandas-ta](https://github.com/twopirllc/pandas-ta), [ta-lib](https://ta-lib.org/)): Use for **indicators** (e.g. ATR for volatility, volume profile) to support **VCP-style** "progressive contraction" (pullback depths 15% → 10% → 5%) and volume dry-up.

### 1.3 Base quality (leadership profile – technical)

- Quality is addressed by the **Minervini Trend Template** and optional **VCP** criteria (Section 2). Bases that also satisfy the Trend Template (and RS) are "high quality"; we can show a **Leadership score** (e.g. Trend Template X/8) next to each base or for the symbol.

---

## 2. Minervini leadership profile

### 2.1 Trend Template (8 criteria)

All evaluated at **current** price (or at base end date for historical view). Data from existing daily + 52-week high/low from same series.


| #   | Criterion                        | Implementation                                                   |
| --- | -------------------------------- | ---------------------------------------------------------------- |
| 1   | Price above 150d and 200d SMA    | Close vs SMA_150, SMA_200                                        |
| 2   | 150d MA above 200d MA            | Compare SMAs                                                     |
| 3   | 200d MA rising ≥ 1 month         | Already have slope logic in `uptrend_at_date`                    |
| 4   | 50d MA above 150d and 200d       | Compare SMAs                                                     |
| 5   | Price above 50d MA               | Close vs SMA_50                                                  |
| 6   | Price ≥ 25% above 52-week low    | 52w low from rolling min(Low); require close ≥ 1.25 × 52w_low    |
| 7   | Price within 25% of 52-week high | 52w high from rolling max(High); require close ≥ 0.75 × 52w_high |
| 8   | Relative Strength ≥ 70           | RS rank vs benchmark (e.g. SPY): see 2.3                         |


- **Output**: **Trend Template score** = count of criteria met (0–8). Display on SEPA page as "Trend Template: X/8" for the symbol (and optionally per base end date).

### 2.2 VCP (Volatility Contraction Pattern)

- **Idea**: Each pullback in the base has smaller depth (e.g. 15% → 10% → 5%) and volume dries up on pullbacks.
- **v1**: Can add a **simple VCP-style check** on the current base: e.g. "last two pullbacks in the base have decreasing depth?" using pivot lows and prior_high. Volume dry-up = compare avg volume on down weeks vs up weeks in the base. Label "VCP-like: Yes/No" or a score.
- **Volatility contraction**: Use pandas-ta ATR on daily data; require ATR at end of base < ATR at start of base to support VCP-style progressive contraction.

### 2.3 Relative Strength (RS)

- **Definition**: Stock performance vs benchmark (e.g. S&P 500 / SPY) over a lookback (e.g. 6 or 12 months). Expressed as **percentile rank** (1–99) among a universe, or as a ratio.
- **Data**: yfinance for stock and SPY (or ^GSPC). Compute (stock_close / stock_close_6m_ago) vs (SPY_close / SPY_close_6m_ago); rank across symbols or use a fixed threshold.
- **For single-symbol SEPA page**: Compute RS ratio vs SPY over last 6 months; convert to a "pseudo-rank" (e.g. if stock up 20% and SPY up 10%, RS ratio = 1.2). For a **rank 70+** style check: either (a) require RS ratio > 1 (outperforming) and map to a score, or (b) maintain a small universe (e.g. watchlist) and compute percentile rank. v1: **RS ratio vs SPY (6m)** and a pass/fail "RS ≥ 1" or "Outperforming SPY"; full rank 70+ can come with a screener/watchlist later.
- **Placement**: Use in Trend Template (criterion 8) and in CAN SLIM (L).

---

## 3. CAN SLIM checklist

- **Goal**: A checklist (C/A/N/S/L/I/M) on the SEPA page so the user can see pass/fail or "Data" vs "Manual" per letter.
- **Data source**: Primarily **yfinance** (Ticker: earnings, income statement, info) plus our price/volume data. Some items (N, I) are qualitative or need external data; mark as "Manual" or "N/A" for v1.


| Letter | Criterion                                      | Data / Implementation                                                                                                                                                                             |
| ------ | ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **C**  | Current quarter EPS growth ≥ 25%               | yfinance quarterly earnings; compare current quarter EPS to same quarter prior year; pass if growth ≥ 25%.                                                                                        |
| **A**  | Annual earnings growth ≥ 25% (e.g. 3–5 yr)     | yfinance annual earnings; YoY growth; pass if ≥ 25%.                                                                                                                                              |
| **N**  | New product/service/management                 | Qualitative. v1: Checklist checkbox "Manual" or "N/A"; optional link to news.                                                                                                                    |
| **S**  | Supply & demand (low float, volume on up days) | Float from yfinance `ticker.info`; volume: we have it; "volume on up days" vs "down days" from our series. Pass: e.g. "up-day volume > down-day volume" and float below a threshold if available. |
| **L**  | Leader (RS 80+)                                | Same RS as Trend Template; pass if RS ratio outperforms or rank ≥ 80 when available.                                                                                                              |
| **I**  | Institutional sponsorship increasing           | yfinance may expose institutional holdings; if not, "Manual" or "N/A" for v1.                                                                                                                     |
| **M**  | Market in uptrend                              | Fetch SPY (or ^GSPC); 50d/200d SMA; pass if SPY above 50d and 200d and 200d rising.                                                                                                                |


- **UI**: On SEPA page, a **CAN SLIM** section: seven rows (C, A, N, S, L, I, M) with columns e.g. **Criterion**, **Status** (Pass / Fail / Manual / N/A), **Detail** (e.g. "EPS growth 32%"). Keep it simple so the user can mentally or manually complete N and I.

---

## 4. Data and module layout

- **New/updated modules** (suggested):
  - **turtle_rpm/sepa.py**: Add `distance_pct` to base dict; optionally add 52w high/low and Trend Template helper (or move to a `leadership.py`).
  - **turtle_rpm/leadership.py** (new): Trend Template (8) and RS vs SPY. Input: daily DataFrame with SMAs and 52w high/low; optional SPY series for RS. Returns: dict with trend_template_score, trend_template_details, rs_ratio, rs_pass.
  - **turtle_rpm/canslim.py** (new): CAN SLIM checklist. Input: symbol, yfinance Ticker (or cached fundamentals), our price/volume DataFrame, RS result, market (SPY) series. Returns: list of dicts { letter, name, status, detail }.
- **Data**: yfinance for stock + SPY; 52w high/low from rolling window on existing daily data. Cache Ticker info and SPY history (e.g. `@st.cache_data`) to avoid repeated requests.

---

## 5. SEPA page changes

- **Table**: Add column **Distance to buy (%)** (or **% below buy point**); for "Not yet" bases show percent below resistance; for past/triggered show "At/above" or 0. Order so current base first, then by distance ascending (closest to buy first).
- **Leadership block**: New section "Leadership profile (Minervini)" with **Trend Template: X/8** and list of which criteria pass/fail; optionally **RS vs SPY (6m)** and **VCP-like: Yes/No** for current base.
- **CAN SLIM block**: New section "CAN SLIM checklist" with table or list of C/A/N/S/L/I/M, status, and short detail.
- **Order**: Symbol → (optional chart) → SEPA bases table → Leadership profile → CAN SLIM.

---

## 6. Implementation order

1. **Buy-point distance**: Add `distance_pct` (and column) in sepa.py + page; no new deps.
2. **52w high/low**: Add to sepa or leadership; use in Trend Template criteria 6–7.
3. **Trend Template**: Implement 8 criteria in `leadership.py`; call from page; show X/8 and optional details.
4. **RS vs SPY**: Fetch SPY, compute 6m performance ratio in leadership.py; use for Template #8 and CAN SLIM L.
5. **CAN SLIM**: New `canslim.py`; wire C, A, S, L, M from data; N and I as Manual/N/A; show checklist on page.
6. **VCP-style**: Simple "decreasing pullback depth" and volume dry-up for current base; label "VCP-like".

---

## 7. Out of scope for initial implementation

- Full stock screener with RS rank across many symbols (single-symbol SEPA page first).
- External paid APIs for institutional ownership or IBD-style RS rank.
- Backtesting or automated trade signals.

---

## Summary

- **Pattern recognition**: use library; add **distance to buy point** (%) and optional volatility/VCP checks; no requirement to add a new pattern library for v1.
- **Leadership profile**: Add **Trend Template (8)** and **RS vs SPY** in a small `leadership` module; display on SEPA page; optionally add simple **VCP-like** flag for current base.
- **CAN SLIM**: New **checklist** (C/A/N/S/L/I/M) using yfinance + our price/volume + RS + SPY for market; N and I manual/N/A initially.
- **Page**: Table gains "Distance to buy (%)"; new sections "Leadership profile" and "CAN SLIM checklist".
