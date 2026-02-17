# turtle-rpm
Risk and portfolio management tool for the Turtle trading system. Built with Streamlit.

## Requirements
- Python 3.12+
- `pip` (or `uv`) for installing Python packages
- Declared dependency: `streamlit>=1.31.0` (see `pyproject.toml`)

## Getting started
1. Clone the repository and move into it:
   ```bash
   git clone https://github.com/aseemcheema/turtle-rpm.git
   cd turtle-rpm
   ```
2. Create and activate a virtual environment (example using `venv`):
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows use: .venv\\Scripts\\activate
   ```
3. Install dependencies from `pyproject.toml`:
   ```bash
   pip install -e .
   # or with uv
   uv pip install -e .
   ```

## Running the app from the terminal
With the virtual environment activated and dependencies installed:
```bash
streamlit run app.py
```

The app will start at http://localhost:8501 by default. Use the Streamlit sidebar to switch between the "Position Builder" and "Position Manager" tools located under the `pages/` directory.
