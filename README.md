# turtle-rpm
Risk and portfolio management tool for the Turtle trading system. Built with Streamlit.

## Requirements
- Python 3.11+
- `uv` for installing Python packages (or `pip` as an alternative)
- Declared dependency: `streamlit>=1.36.0` (see `pyproject.toml`)

## Getting started
1. Clone the repository and move into it:
   ```bash
   git clone https://github.com/aseemcheema/turtle-rpm.git
   cd turtle-rpm
   ```
2. Create and activate a virtual environment (using `uv`):
   ```bash
   uv venv .venv
   source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
   ```
3. Install dependencies from `pyproject.toml`:
   ```bash
   uv pip install -e .
   # or with pip
   pip install -e .
   ```

## Running the app from the terminal
With the virtual environment activated and dependencies installed:
```bash
streamlit run app.py
```

The app will start at http://localhost:8501 by default. Use the Streamlit sidebar to switch between:

- **Home** (overview and quick links)
- **Specific Entry Point Analysis** (analyze a single symbol and size trades)
- **Pivot Breakouts Tomorrow** (view latest daily scan of potential pivot breakouts)
- **Portfolio** (connect to E*TRADE and view accounts/holdings)

## Symbol list (SEPA page)

The Specific Entry Point Analysis page uses a dropdown of NYSE and NASDAQ symbols. Populate the list by running:

```bash
python scripts/download_symbols.py
# or
uv run python scripts/download_symbols.py
```

This downloads the official NASDAQ Trader symbol file and writes `data/symbols.csv`. Without it, the SEPA symbol dropdown will be empty and the app will show instructions to run the script.

## Liquidity risk (SEPA page)

The Specific Entry Point Analysis page includes a **Liquidity risk** section that helps cap position size so you can exit without moving the market. It shows:

- **ADV (20d and 50d)** — average daily trading volume in shares (and dollar volume).
- **Days to liquidate** — for a reference position size (e.g. 100 shares), how many days of volume that represents (position ÷ ADV).
- **Liquidity-based limit** — max shares and max dollar you can buy such that exiting at a set percentage of ADV per day (default 25%) keeps exit within a set number of days (default 5). This limit is intended to feed into position sizing: final position = min(size from other rules, this liquidity max).

Defaults are 5 days to exit and 25% of ADV per day; the underlying logic lives in `turtle_rpm.liquidity` and can be tuned there or (in the future) via the UI.

## Jupyter notebooks

Research notebooks live in `notebooks/`. To launch Jupyter and open a notebook:

```bash
uv run jupyter notebook notebooks/sepa_entry_points.ipynb
```

Or with JupyterLab:

```bash
uv run jupyter lab notebooks/sepa_entry_points.ipynb
```

To execute a notebook headlessly and save the output in place:

```bash
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/sepa_entry_points.ipynb
```

Available notebooks:

- **sepa_entry_points.ipynb** — Identify and evaluate SEPA entry points: base detection (Cup & Handle, Double Bottom, Darvas Box, Power Play), VCP contractions, pivot points, Trend Template, Fab 5 fundamentals, and composite scoring.
- **sepa_entry_analysis.ipynb** — Historical SEPA edge research: forward return analysis by entry rule and base type.

## Pivot breakout daily scan

Run **after market close** to compute pivots for all symbols, rank by quality, and flag potential pivot breakouts for the next day:

```bash
uv run python scripts/pivot_breakout_scan.py
```

This reads `data/symbols.csv` (or `--symbols path/to.csv`), runs the scan, and writes to `data/pivot_scan/`:

- `pivot_scan_full_YYYYMMDD.csv` — all symbols with pivot/buyable/quality
- `pivot_breakouts_tomorrow_YYYYMMDD.csv` — buyable only (potential breakouts for tomorrow), sorted by quality

Open the **Pivot Breakouts Tomorrow** page in the app the next morning to view the latest report without re-running. Schedule the script daily (e.g. cron at 5pm ET weekdays) so you are ready before the open.

## E\*TRADE portfolio integration
- Open the **Portfolio** page and enter your E\*TRADE consumer key and secret (use Sandbox keys for testing).
- Click **Get Request Token**, follow the authorization URL, and paste the verification code.
- Exchange for an access token, then use **Fetch Accounts** to obtain your `accountIdKey` and **Fetch Portfolio** to view holdings. Sandboxed tokens work against `apisb.etrade.com` while production tokens use `api.etrade.com`.
