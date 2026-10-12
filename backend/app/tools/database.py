"""
backend/app/tools/database.py

[SIMULATED] Simulated database query tool — executes against demo SQLite sandbox.
LABEL: [SIMULATED] — shown in UI.
Runs against a separate demo SQLite database containing tables: customers and orders.
Only imported and invoked by gateway.py after all security checks pass.
Gateway hard-blocks DROP, TRUNCATE, and DELETE without WHERE before calling this.
All tools print nothing sensitive and are clearly labelled SIMULATED in docstrings
and return payloads ({"simulated": true}).
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

# Path to the separate isolated demo SQLite database
_DEFAULT_DEMO_DB = Path(__file__).resolve().parent.parent.parent / "demo_sandbox.db"
DEMO_DB_PATH = os.getenv("AGENTGUARD_DEMO_DB_PATH", str(_DEFAULT_DEMO_DB))

_DEMO_SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    city TEXT
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER,
    amount_paise INTEGER NOT NULL,
    status TEXT NOT NULL,
    FOREIGN KEY(customer_id) REFERENCES customers(id)
);
"""


def init_demo_db(db_path: Optional[str] = None) -> None:
    """
    [SIMULATED] Initializes the separate demo SQLite database schema and seeds initial rows
    if the tables are currently empty.
    """
    target = db_path or DEMO_DB_PATH
    conn = sqlite3.connect(target, check_same_thread=False)
    try:
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.executescript(_DEMO_SCHEMA)

        # Seed initial demo rows if empty
        cur = conn.cursor()
        count = cur.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        if count == 0:
            cur.executemany(
                "INSERT INTO customers (name, email, city) VALUES (?, ?, ?)",
                [
                    ("Supplier A Ltd", "supplier_a@example.com", "Mangaluru"),
                    ("Supplier B Ltd", "supplier_b@example.com", "Udupi"),
                    ("Coastal Fish Exports", "accounts@coastal.internal.corp", "Mangaluru"),
                ],
            )
            cur.executemany(
                "INSERT INTO orders (customer_id, amount_paise, status) VALUES (?, ?, ?)",
                [
                    (1, 500000, "completed"),
                    (2, 750000, "pending"),
                    (3, 1200000, "processing"),
                ],
            )
            conn.commit()
    finally:
        conn.close()


def run_sql(sql: Any = None, **kwargs: Any) -> Dict[str, Any]:
    """
    [SIMULATED] Executes a SQL query against the separate demo SQLite sandbox.
    Prints nothing sensitive.

    Accepts either a SQL string or a params dict as the first argument.
    """
    if isinstance(sql, dict):
        params = sql
        sql_text = str(params.get("sql") or params.get("query") or "").strip()
        db_file = params.get("database_path") or kwargs.get("database_path") or DEMO_DB_PATH
    else:
        sql_text = str(sql if sql is not None else kwargs.get("sql", kwargs.get("query", ""))).strip()
        db_file = kwargs.get("database_path") or DEMO_DB_PATH

    init_demo_db(db_file)

    conn = sqlite3.connect(db_file, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(sql_text)

        rows: List[Dict[str, Any]] = []
        if cursor.description:
            rows = [dict(row) for row in cursor.fetchall()]

        rows_affected = cursor.rowcount
        conn.commit()

        return {
            "simulated": True,
            "status": "simulated_success",
            "sql": sql_text,
            "rows_affected": rows_affected if rows_affected >= 0 else len(rows),
            "rows": rows,
            "label": "[SIMULATED] Executed against isolated demo SQLite sandbox",
        }
    except Exception as exc:
        return {
            "simulated": True,
            "status": "error",
            "error": str(exc),
            "sql": sql_text,
            "label": "[SIMULATED] Error executing against isolated demo SQLite sandbox",
        }
    finally:
        conn.close()
