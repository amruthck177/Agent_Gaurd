"""
backend/tests/test_schemas_and_db.py

Unit tests for schemas, canonical parameter normalization, hashing,
database initialization, reset, and demo seeding.
"""

import json
import sqlite3
import pytest
from app.db import get_connection, init_db, reset_db, seed_demo
from app.schemas import (
    Approval,
    AuditRecord,
    Decision,
    ExecuteRequest,
    ExecuteResponse,
    Policy,
    canonical,
    canonical_hash,
    normalize_recipient,
    parse_money_to_paise,
)


# ===========================================================================
# 1. Canonicalization and Equality Tests
# ===========================================================================
def test_recipient_normalization():
    """
    Proves:
    'Supplier A ' == 'supplier a' (trimmed and casefolded to a stable ID).
    Supplier A != Supplier B.
    """
    assert normalize_recipient("Supplier A ") == "supplier a"
    assert normalize_recipient("supplier a") == "supplier a"
    assert normalize_recipient("Supplier A ") == normalize_recipient("supplier a")
    assert normalize_recipient("Supplier A") != normalize_recipient("Supplier B")

    # Direct canonical string comparison
    assert canonical("Supplier A ") == canonical("supplier a")
    assert canonical("Supplier A") != canonical("Supplier B")

    # Dict comparison with recipient key
    assert canonical({"recipient": "Supplier A "}) == canonical({"recipient": "supplier a"})
    assert canonical({"recipient": "Supplier A "}) != canonical({"recipient": "Supplier B"})


def test_money_normalization_paise():
    """
    Proves:
    5000.00 (float rupees) == 500000 paise (integer paise).
    1 INR = 100 paise.
    """
    assert parse_money_to_paise(5000.00) == 500000
    assert parse_money_to_paise(500000) == 500000
    assert parse_money_to_paise("5000.00") == 500000
    assert parse_money_to_paise("500000 paise") == 500000
    assert parse_money_to_paise("500000p") == 500000
    assert parse_money_to_paise("₹5,000.00") == 500000

    # Direct canonical primitive comparison
    assert canonical(5000.00) == canonical(500000)
    assert canonical(5000.00) == canonical("500000 paise")

    # Dict comparison across amount representations
    assert canonical({"amount": 5000.00}) == canonical({"amount_paise": 500000})
    assert canonical({"amount": 5000.00}) == canonical({"amount": 500000})
    assert canonical({"amount": 5000.00}) == canonical({"amount": "500000 paise"})


def test_combined_exact_match_and_mismatch():
    """
    Tests the core hero scenario from plan.md §A2 & design.md §1:
    - Same approved payment with whitespace/case variation matches.
    - Altering payee from Supplier A to Supplier B produces mismatch.
    - Altering amount produces mismatch.
    """
    approved_params = {
        "recipient": "Supplier A ",
        "amount": 5000.00,
        "currency": "inr",
    }
    same_params_normalized = {
        "recipient": "supplier a",
        "amount_paise": 500000,
        "currency": "INR",
    }
    tampered_recipient = {
        "recipient": "Supplier B",
        "amount": 5000.00,
        "currency": "INR",
    }
    tampered_amount = {
        "recipient": "Supplier A",
        "amount": 6000.00,
        "currency": "INR",
    }

    # Hash and canonical matching
    assert canonical(approved_params) == canonical(same_params_normalized)
    assert canonical_hash(approved_params) == canonical_hash(same_params_normalized)

    # Recipient mismatch detection
    assert canonical(approved_params) != canonical(tampered_recipient)
    assert canonical_hash(approved_params) != canonical_hash(tampered_recipient)

    # Amount mismatch detection
    assert canonical(approved_params) != canonical(tampered_amount)
    assert canonical_hash(approved_params) != canonical_hash(tampered_amount)


def test_sorted_keys_compact_json():
    """
    Tests that keys are sorted deterministically and JSON is compact (no spacing around delimiters).
    """
    d1 = {"z": 1, "a": 2, "m": 3}
    d2 = {"a": 2, "m": 3, "z": 1}
    assert canonical(d1) == canonical(d2)
    assert canonical(d1) == '{"a":2,"m":3,"z":1}'


# ===========================================================================
# 2. Pydantic Models Tests
# ===========================================================================
def test_decision_enum():
    """Only ALLOW, ASK_HUMAN, and BLOCK exist."""
    assert Decision.ALLOW == "ALLOW"
    assert Decision.ASK_HUMAN == "ASK_HUMAN"
    assert Decision.BLOCK == "BLOCK"
    assert len(Decision) == 3

    with pytest.raises(ValueError):
        Decision("DENY")


def test_execute_request_response_models():
    req = ExecuteRequest(
        agent_id="accounts-agent",
        task_id="task-accounts-1",
        tool="payments.send",
        params={"recipient": "Supplier A", "amount": 5000.00},
    )
    assert req.agent_id == "accounts-agent"
    assert req.approval_id is None

    res = ExecuteResponse(
        decision=Decision.ALLOW,
        reason="Approved by policy",
        executed=True,
        audit_id=42,
        approval_id="APR-001",
    )
    assert res.decision == Decision.ALLOW
    assert res.executed is True
    assert res.audit_id == 42


def test_policy_and_approval_models():
    pol = Policy(
        tool="payments.send",
        condition_json=json.dumps({"field": "amount_paise", "operator": ">", "value": 1000000}),
        decision=Decision.ASK_HUMAN,
    )
    assert pol.decision == Decision.ASK_HUMAN
    assert pol.active is True
    assert pol.version == 1

    appr = Approval(
        id="APR-001",
        agent_id="accounts-agent",
        task_id="task-accounts-1",
        tool="payments.send",
        approved_params_json='{"recipient":"supplier a","amount_paise":500000}',
        approved_hash="abc123hash",
        status="approved",
        created_at="2026-10-12T10:00:00Z",
        expires_at="2026-10-12T10:10:00Z",
    )
    assert appr.status == "approved"
    assert appr.tool == "payments.send"


# ===========================================================================
# 3. Database Tests (init, reset, WAL, FK, seed_demo)
# ===========================================================================
def test_db_init_and_pragmas(tmp_path):
    test_db = str(tmp_path / "test_agentguard.db")
    init_db(test_db)

    conn = get_connection(test_db)
    try:
        # Verify WAL mode
        mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        assert mode.lower() == "wal"

        # Verify Foreign Keys
        fk = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
        assert fk == 1

        # Verify all tables exist
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        expected_tables = {"agents", "tasks", "suppliers", "policies", "approvals", "audit", "tool_calls"}
        assert expected_tables.issubset(tables)
    finally:
        conn.close()


def test_db_reset(tmp_path):
    test_db = str(tmp_path / "test_reset.db")
    seed_demo(test_db)

    conn = get_connection(test_db)
    count_before = conn.execute("SELECT COUNT(*) FROM agents;").fetchone()[0]
    conn.close()
    assert count_before > 0

    reset_db(test_db)

    conn = get_connection(test_db)
    count_after = conn.execute("SELECT COUNT(*) FROM agents;").fetchone()[0]
    conn.close()
    assert count_after == 0


def test_seed_demo_data(tmp_path):
    test_db = str(tmp_path / "test_seed.db")
    seed_demo(test_db)

    conn = get_connection(test_db)
    try:
        # Check agents
        agents = {row["id"]: dict(row) for row in conn.execute("SELECT * FROM agents;").fetchall()}
        assert "accounts-agent" in agents
        assert "reader-agent" in agents

        assert agents["accounts-agent"]["role"] == "writer"
        assert "payments.send" in agents["accounts-agent"]["permissions_json"]
        assert "email.send" in agents["accounts-agent"]["permissions_json"]
        assert "database.run_sql" in agents["accounts-agent"]["permissions_json"]

        assert agents["reader-agent"]["role"] == "reader"
        assert agents["reader-agent"]["permissions_json"] == "[]"

        # Check tasks
        tasks = {row["id"]: dict(row) for row in conn.execute("SELECT * FROM tasks;").fetchall()}
        assert "task-accounts-1" in tasks
        assert "task-reader-1" in tasks
        assert tasks["task-accounts-1"]["agent_id"] == "accounts-agent"
        assert tasks["task-reader-1"]["agent_id"] == "reader-agent"

        # Check suppliers
        suppliers = {row["id"]: dict(row) for row in conn.execute("SELECT * FROM suppliers;").fetchall()}
        assert "supplier a" in suppliers
        assert suppliers["supplier a"]["name"] == "Supplier A"
        assert "supplier b" in suppliers
        assert suppliers["supplier b"]["name"] == "Supplier B"

        # Check default policies (plan.md §C6)
        policies = [dict(row) for row in conn.execute("SELECT * FROM policies WHERE active=1;").fetchall()]
        assert len(policies) >= 5

        tools = {p["tool"] for p in policies}
        assert "payments.send" in tools
        assert "*" in tools
        assert "database.run_sql" in tools
        assert "email.send" in tools

        # Find payment limit policy
        limit_policy = next(p for p in policies if p["tool"] == "payments.send" and p["decision"] == "ASK_HUMAN")
        cond = json.loads(limit_policy["condition_json"])
        assert cond["value"] == 1000000  # 10,000 INR in paise

        # Find reader block policy
        reader_policy = next(p for p in policies if p["tool"] == "*" and p["decision"] == "BLOCK")
        cond_reader = json.loads(reader_policy["condition_json"])
        assert cond_reader["role"] == "reader"

        # Find database destructive block policy
        db_policy = next(p for p in policies if p["tool"] == "database.run_sql" and p["decision"] == "BLOCK")
        assert db_policy["decision"] == "BLOCK"
    finally:
        conn.close()
