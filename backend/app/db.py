"""
backend/app/db.py

SQLite connection management, schema initialization, reset, and seeding.
All other modules import get_connection() or get_db() from here;
nothing else opens the database directly.

Schema defined in plan.md §C4.
Default policies from plan.md §C6.
"""

from __future__ import annotations

import json
import os
import sqlite3
from typing import Generator, List, Optional

# Database path (configurable via DB_PATH env var)
DB_PATH: str = os.getenv("DB_PATH", "agentguard.db")

_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS agents (
    id               TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    role             TEXT NOT NULL,          -- e.g. "writer", "reader"
    permissions_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT PRIMARY KEY,
    agent_id    TEXT NOT NULL REFERENCES agents(id),
    description TEXT NOT NULL,
    scope_json  TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS suppliers (
    id          TEXT PRIMARY KEY,          -- canonical trimmed + casefolded id
    name        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS policies (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id       TEXT,                     -- NULL = applies to all agents
    task_id        TEXT,                     -- NULL = applies to all tasks
    tool           TEXT NOT NULL,
    condition_json TEXT NOT NULL DEFAULT '{}',
    decision       TEXT NOT NULL CHECK(decision IN ('ALLOW','ASK_HUMAN','BLOCK')),
    version        INTEGER NOT NULL DEFAULT 1,
    active         INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS approvals (
    id                   TEXT PRIMARY KEY,
    agent_id             TEXT NOT NULL REFERENCES agents(id),
    task_id              TEXT NOT NULL REFERENCES tasks(id),
    tool                 TEXT NOT NULL,
    approved_params_json TEXT NOT NULL,      -- human-readable JSON
    approved_hash        TEXT NOT NULL,      -- SHA-256 of canonical sensitive params
    status               TEXT NOT NULL DEFAULT 'pending'
                         CHECK(status IN ('pending','approved','rejected','used','revoked','expired')),
    created_at           TEXT NOT NULL,
    approved_at          TEXT,
    expires_at           TEXT NOT NULL,
    revoked_at           TEXT,
    used_at              TEXT
);

CREATE TABLE IF NOT EXISTS audit (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT NOT NULL,
    agent_id      TEXT NOT NULL,
    task_id       TEXT NOT NULL,
    tool          TEXT NOT NULL,
    params_masked TEXT NOT NULL,             -- secrets stripped before storage
    decision      TEXT NOT NULL CHECK(decision IN ('ALLOW','ASK_HUMAN','BLOCK')),
    reason        TEXT NOT NULL,
    approval_id   TEXT,
    executed      INTEGER NOT NULL DEFAULT 0, -- 1 if tool actually ran
    prev_hash     TEXT NOT NULL,
    hash          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tool_calls (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tool        TEXT NOT NULL,
    params_json TEXT NOT NULL,
    executed_at TEXT NOT NULL,
    audit_id    INTEGER NOT NULL REFERENCES audit(id)
);
"""


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """
    Returns a SQLite connection configured with WAL mode, foreign keys ON,
    and row_factory set to sqlite3.Row for dictionary-like column access.
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def get_db(db_path: str = DB_PATH) -> Generator[sqlite3.Connection, None, None]:
    """
    FastAPI dependency yielding a managed SQLite connection.
    Usage: `db: sqlite3.Connection = Depends(get_db)`
    """
    conn = get_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: str = DB_PATH) -> None:
    """Creates all tables if they do not exist. Safe on startup."""
    conn = get_connection(db_path)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def reset_db(db_path: str = DB_PATH) -> None:
    """
    Drops all AgentGuard tables and re-initializes an empty schema.
    Used for tests and demo environment reset.
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    try:
        conn.execute("PRAGMA foreign_keys=OFF;")
        tables = [
            "tool_calls",
            "audit",
            "approvals",
            "policies",
            "suppliers",
            "tasks",
            "agents",
        ]
        for table in tables:
            conn.execute(f"DROP TABLE IF EXISTS \"{table}\";")
        conn.commit()
    finally:
        conn.close()

    init_db(db_path)


def seed_demo(db_path: str = DB_PATH) -> None:
    """
    Seeds demo agents, tasks, suppliers, and default policies from plan.md §C6.
    Idempotent: safe to run repeatedly.
    """
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()

        # 1. Seed Agents (plan.md §C4, Part D)
        agents = [
            (
                "accounts-agent",
                "Accounts Agent",
                "writer",
                json.dumps(["payments.send", "email.send", "database.run_sql"]),
            ),
            (
                "reader-agent",
                "Reader Agent",
                "reader",
                json.dumps([]),
            ),
        ]
        cursor.executemany(
            """
            INSERT OR REPLACE INTO agents (id, name, role, permissions_json)
            VALUES (?, ?, ?, ?)
            """,
            agents,
        )

        # 2. Seed Tasks
        tasks = [
            (
                "task-accounts-1",
                "accounts-agent",
                "Process accounts payable, invoice payments, and supplier correspondence",
                json.dumps({
                    "allowed_recipients": ["supplier a", "supplier b"],
                    "allowed_tools": ["payments.send", "email.send", "database.run_sql"],
                }),
            ),
            (
                "task-reader-1",
                "reader-agent",
                "Read-only financial audits and system integrity checks",
                json.dumps({
                    "allowed_recipients": [],
                    "allowed_tools": [],
                }),
            ),
        ]
        cursor.executemany(
            """
            INSERT OR REPLACE INTO tasks (id, agent_id, description, scope_json)
            VALUES (?, ?, ?, ?)
            """,
            tasks,
        )

        # 3. Seed Suppliers
        suppliers = [
            ("supplier a", "Supplier A"),
            ("supplier b", "Supplier B"),
        ]
        cursor.executemany(
            """
            INSERT OR REPLACE INTO suppliers (id, name)
            VALUES (?, ?)
            """,
            suppliers,
        )

        # 4. Seed Default Policies from plan.md §C6
        # Clear existing default policies to ensure no duplicate stacking
        cursor.execute("DELETE FROM policies WHERE version = 1;")
        default_policies = [
            (
                None,
                None,
                "payments.send",
                json.dumps({
                    "field": "amount_paise",
                    "operator": ">",
                    "value": 1000000,
                    "threshold_inr": 10000,
                    "description": "Payment exceeds ₹10,000 limit (1,000,000 paise)",
                }),
                "ASK_HUMAN",
                1,
                1,
            ),
            (
                None,
                None,
                "payments.send",
                json.dumps({
                    "type": "parameter_mismatch",
                    "description": "Recipient or parameter changed after approval",
                }),
                "BLOCK",
                1,
                1,
            ),
            (
                None,
                None,
                "*",
                json.dumps({
                    "role": "reader",
                    "type": "disallow_write_tools",
                    "description": "Agent lacks write permission",
                }),
                "BLOCK",
                1,
                1,
            ),
            (
                None,
                None,
                "database.run_sql",
                json.dumps({
                    "forbidden_keywords": ["DROP", "TRUNCATE"],
                    "delete_requires_where": True,
                    "description": "Destructive database operation prohibited",
                }),
                "BLOCK",
                1,
                1,
            ),
            (
                None,
                None,
                "email.send",
                json.dumps({
                    "type": "unknown_domain",
                    "allowed_domains": ["internal.corp", "company.com", "example.com"],
                    "description": "Sending email to unknown external domain",
                }),
                "ASK_HUMAN",
                1,
                1,
            ),
        ]
        cursor.executemany(
            """
            INSERT INTO policies (agent_id, task_id, tool, condition_json, decision, version, active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            default_policies,
        )

        conn.commit()
    finally:
        conn.close()
