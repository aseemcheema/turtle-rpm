"""
E*TRADE order history: fetch orders API, immutable SQLite storage, incremental sync.

Order rows are insert-only; sync uses fromDate/toDate (MMDDYYYY) and pagination.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Rate limit: max retries and backoff (seconds)
RATE_LIMIT_MAX_RETRIES = 5
RATE_LIMIT_INITIAL_WAIT = 60
RATE_LIMIT_MAX_WAIT = 300

# Pagination: safety cap to avoid infinite loop if API never returns empty marker
ORDERS_MAX_PAGES = 5000

# E*TRADE allows two years of order history
ORDER_HISTORY_YEARS = 2


def get_db_path(project_root: Path | None = None) -> Path:
    """Return path to the SQLite file (data/etrade_orders.db). Creates data dir if needed."""
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent
    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "etrade_orders.db"


def init_db(path: Path | None = None) -> None:
    """Create orders table if not exists."""
    if path is None:
        path = get_db_path()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                account_id_key TEXT NOT NULL,
                order_id INTEGER NOT NULL,
                placed_time INTEGER,
                payload TEXT NOT NULL,
                ingested_at TEXT NOT NULL,
                PRIMARY KEY (account_id_key, order_id)
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def insert_orders(account_id_key: str, orders_list: list[dict[str, Any]], db_path: Path | None = None) -> int:
    """
    Insert orders; duplicates (same account_id_key, order_id) are ignored.
    Returns number of rows inserted.
    """
    if db_path is None:
        db_path = get_db_path()
    from datetime import datetime, timezone
    ingested_at = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_path)
    inserted = 0
    try:
        for order in orders_list:
            order_id = order.get("orderId")
            if order_id is None:
                continue
            # placedTime can be in orderDetail[0]; fallback to None
            placed_time = None
            details = order.get("orderDetail") or order.get("OrderDetail")
            if isinstance(details, list) and details:
                first = details[0]
                placed_time = first.get("placedTime") or first.get("PlacedTime")
            elif isinstance(details, dict):
                placed_time = details.get("placedTime") or details.get("PlacedTime")
            payload = json.dumps(order)
            try:
                cur = conn.execute(
                    """
                    INSERT OR IGNORE INTO orders (account_id_key, order_id, placed_time, payload, ingested_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (account_id_key, order_id, placed_time, payload, ingested_at),
                )
                inserted += cur.rowcount
            except sqlite3.IntegrityError:
                pass
        conn.commit()
    finally:
        conn.close()
    return inserted


def get_last_ingested_at(account_id_key: str, db_path: Path | None = None) -> str | None:
    """Return the most recent ingested_at for the account (for 'Last synced' display)."""
    if db_path is None:
        db_path = get_db_path()
    if not Path(db_path).is_file():
        return None
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT max(ingested_at) FROM orders WHERE account_id_key = ?",
            (account_id_key,),
        ).fetchone()
        return row[0] if row and row[0] else None
    finally:
        conn.close()


def get_max_placed_time(account_id_key: str, db_path: Path | None = None) -> int | None:
    """Return max(placed_time) for the account, or None if no rows."""
    if db_path is None:
        db_path = get_db_path()
    if not Path(db_path).is_file():
        return None
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT max(placed_time) FROM orders WHERE account_id_key = ? AND placed_time IS NOT NULL",
            (account_id_key,),
        ).fetchone()
        return row[0] if row and row[0] is not None else None
    finally:
        conn.close()


def get_orders(
    account_id_key: str,
    limit: int | None = None,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Return orders for the account, newest first. Each row includes payload and parsed fields."""
    if db_path is None:
        db_path = get_db_path()
    if not Path(db_path).is_file():
        return []
    conn = sqlite3.connect(db_path)
    try:
        sql = "SELECT order_id, placed_time, payload, ingested_at FROM orders WHERE account_id_key = ? ORDER BY placed_time DESC, order_id DESC"
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        rows = conn.execute(sql, (account_id_key,)).fetchall()
    finally:
        conn.close()
    out = []
    for order_id, placed_time, payload, ingested_at in rows:
        row = {"order_id": order_id, "placed_time": placed_time, "ingested_at": ingested_at}
        try:
            data = json.loads(payload)
            row["payload"] = data
            # Flatten common fields for display
            details = data.get("orderDetail") or data.get("OrderDetail")
            if isinstance(details, list) and details:
                d = details[0]
                row["status"] = d.get("status")
                row["orderType"] = d.get("orderType") or data.get("orderType")
                row["placedTime"] = d.get("placedTime")
                inst = (d.get("instrument") or d.get("Instrument") or [])
                if isinstance(inst, list) and inst:
                    prod = inst[0].get("Product") or inst[0].get("product") or {}
                    row["symbol"] = prod.get("symbol")
                    row["orderAction"] = inst[0].get("orderAction") or inst[0].get("OrderAction")
                    row["quantity"] = inst[0].get("quantity")
                elif isinstance(inst, dict):
                    prod = inst.get("Product") or inst.get("product") or {}
                    row["symbol"] = prod.get("symbol")
                    row["orderAction"] = inst.get("orderAction") or inst.get("OrderAction")
                    row["quantity"] = inst.get("quantity")
            else:
                row["status"] = data.get("status")
                row["orderType"] = data.get("orderType")
        except (json.JSONDecodeError, TypeError):
            row["payload"] = {}
        out.append(row)
    return out


def _date_to_mmddyyyy(d: date) -> str:
    """Format date as MMDDYYYY for E*TRADE API."""
    return d.strftime("%m%d%Y")


def _is_rate_limit_response(response: Any) -> bool:
    """True if response indicates rate limit (400/429 with rate limit message)."""
    if response.status_code not in (400, 429):
        return False
    text = (response.text or "").lower()
    return "rate limit" in text or "rate_limit" in text


def _retry_after_seconds(response: Any) -> int | None:
    """Parse Retry-After header; return seconds or None."""
    value = response.headers.get("Retry-After")
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return min(int(value), RATE_LIMIT_MAX_WAIT)
    return None


def fetch_orders(
    session: Any,
    base_url: str,
    account_id_key: str,
    from_date: date,
    to_date: date,
    count: int = 100,
    progress_callback: Callable[[str], None] | None = None,
    progress_dict: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch all orders for the account in the date range. Paginates with marker/next.
    On rate limit (400/429 with rate limit message), retries with backoff.
    Returns list of order dicts from the API.
    """
    from_d = _date_to_mmddyyyy(from_date)
    to_d = _date_to_mmddyyyy(to_date)
    base_path = f"{base_url.rstrip('/')}/v1/accounts/{account_id_key}"
    # Try /orders first (per doc); fallback to /orders.json once if 404 (some envs differ).
    url_base = f"{base_path}/orders"
    url_base_alt = f"{base_path}/orders.json"
    tried_orders_json = False
    all_orders: list[dict[str, Any]] = []
    marker = None
    page = 0

    def log_progress(msg: str) -> None:
        logger.info("%s", msg)
        if progress_callback:
            progress_callback(msg)

    while True:
        page += 1
        params: dict[str, str | int] = {
            "fromDate": from_d,
            "toDate": to_d,
            "count": count,
        }
        if marker is not None:
            params["marker"] = marker
        headers = {"Accept": "application/json"}

        retries = 0
        current_url = url_base
        while True:
            response = session.get(current_url, params=params, headers=headers)
            if response.ok:
                break
            if response.status_code == 404 and not tried_orders_json:
                logger.info("Orders API 404 on /orders; retrying with /orders.json")
                tried_orders_json = True
                url_base = url_base_alt
                current_url = url_base_alt
                continue
            if _is_rate_limit_response(response) and retries < RATE_LIMIT_MAX_RETRIES:
                wait = _retry_after_seconds(response) or min(
                    RATE_LIMIT_INITIAL_WAIT * (2**retries),
                    RATE_LIMIT_MAX_WAIT,
                )
                log_progress(f"Rate limited; waiting {wait}s before retry {retries + 1}/{RATE_LIMIT_MAX_RETRIES}...")
                time.sleep(wait)
                retries += 1
                continue
            err_msg = f"Orders API failed ({response.status_code}): {response.text}"
            if response.status_code == 404:
                err_msg += (
                    f" Request: {url_base} — "
                    "Check that the Account ID Key matches this environment (Sandbox vs Production) "
                    "and that the account supports order history."
                )
            raise RuntimeError(err_msg)

        raw = response.text.strip()
        if not raw:
            data = {"OrdersResponse": {"Order": []}}
        else:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as e:
                raise RuntimeError(
                    f"Orders API returned non-JSON (status={response.status_code}, "
                    f"Content-Type={response.headers.get('Content-Type', '')}): {raw[:500]!r}"
                ) from e

        orders = data.get("OrdersResponse", {}).get("Order") or data.get("Order") or []
        if isinstance(orders, dict):
            orders = [orders]
        all_orders.extend(orders)
        resp = data.get("OrdersResponse") or data
        next_marker = resp.get("next") or resp.get("marker")
        if isinstance(next_marker, str):
            next_marker = next_marker.strip() or None
        total_so_far = len(all_orders)
        if progress_dict is not None:
            progress_dict["orders_page"] = page
            progress_dict["orders_max_pages"] = ORDERS_MAX_PAGES
            progress_dict["orders_total"] = total_so_far
        log_progress(
            f"Orders page {page}/{ORDERS_MAX_PAGES}: got {len(orders)} orders ({total_so_far} total so far)"
        )

        if not next_marker or not orders:
            break
        if next_marker == marker:
            # API returned the same marker we sent: treat as end of list (per E*TRADE pagination).
            logger.info(
                "Orders API returned same marker (end of list); stopping with %s orders.",
                total_so_far,
            )
            break
        if page >= ORDERS_MAX_PAGES:
            logger.warning(
                "Reached max pages limit (%s); stopping. Synced %s orders.",
                ORDERS_MAX_PAGES,
                total_so_far,
            )
            break
        marker = next_marker
    return all_orders


def sync_orders(
    session: Any,
    base_url: str,
    account_id_key: str,
    db_path: Path | None = None,
    progress_callback: Callable[[str], None] | None = None,
    progress_dict: dict[str, Any] | None = None,
) -> tuple[int, str]:
    """
    Run incremental sync for one account: fetch new orders and insert.
    Returns (number of new orders inserted, status message).
    Raises on fetch failure so callers can show error in UI.
    """
    init_db(db_path)
    today = date.today()
    two_years_ago = today - timedelta(days=ORDER_HISTORY_YEARS * 365)
    max_placed = get_max_placed_time(account_id_key, db_path)
    if max_placed is None:
        from_date = two_years_ago
    else:
        from datetime import datetime, timezone
        from_dt = datetime.fromtimestamp(max_placed / 1000.0, tz=timezone.utc)
        from_date = from_dt.date()
        from_date = from_date + timedelta(days=1)
        if from_date > today:
            return 0, "Already up to date"
    to_date = today

    def report(msg: str) -> None:
        logger.info("[%s] %s", account_id_key[:8], msg)
        if progress_callback:
            progress_callback(msg)

    report(f"Syncing orders from {from_date} to {to_date}...")
    orders = fetch_orders(
        session,
        base_url,
        account_id_key,
        from_date,
        to_date,
        progress_callback=progress_callback,
        progress_dict=progress_dict,
    )
    report(f"Fetched {len(orders)} orders; inserting into DB...")
    inserted = insert_orders(account_id_key, orders, db_path)
    if inserted == 0 and not orders:
        return 0, "Already up to date"
    report(f"Inserted {inserted} new orders.")
    return inserted, f"Synced {inserted} new orders"
