"""
backend/tests/test_policy_and_tools.py

Comprehensive unit tests for:
  - backend/app/policy.py (DB policy loading, SQL tokenization & classification,
    permitted(), hard_block(), requires_approval(), email allowlisting)
  - backend/app/tools/payments.py (simulated ledger, fake txn id, docstrings, simulated=True)
  - backend/app/tools/email.py (simulated outbox, fake message id, docstrings, simulated=True)
  - backend/app/tools/database.py (separate demo SQLite with customers & orders tables, docstrings, simulated=True)
"""

import os
import tempfile
import pytest

from app.db import get_connection, reset_db, seed_demo
from app.schemas import Decision, ExecuteRequest
from app.policy import (
    DEFAULT_ALLOWED_EMAIL_DOMAINS,
    REASON_DESTRUCTIVE_SQL,
    REASON_NO_PERMISSION,
    REASON_OVER_THRESHOLD,
    REASON_UNKNOWN_EMAIL_DOMAIN,
    classify_sql,
    extract_email_domains,
    hard_block,
    load_active_policies,
    permitted,
    policy_check,
    requires_approval,
    tokenize_sql,
)
from app.tools import database as db_tool
from app.tools import email as email_tool
from app.tools import payments as payments_tool


@pytest.fixture()
def seeded_db(tmp_path):
    """Provides a fresh seeded SQLite database for policy testing."""
    path = str(tmp_path / "test_policy.db")
    reset_db(path)
    seed_demo(path)
    return path


# ===========================================================================
# 1. SQL Tokenizer and Classifier Tests
# ===========================================================================
def test_tokenize_sql_strips_comments():
    # Single-line comment
    sql1 = "SELECT * FROM customers -- ignore this comment"
    tokens1 = tokenize_sql(sql1)
    assert tokens1 == ["SELECT", "*", "FROM", "CUSTOMERS"]

    # Multi-line comment
    sql2 = "SELECT /* benign comment */ id FROM orders"
    tokens2 = tokenize_sql(sql2)
    assert tokens2 == ["SELECT", "ID", "FROM", "ORDERS"]

    # Tricky comment attempt to hide DROP
    sql3 = "/* comment */ DROP TABLE customers"
    tokens3 = tokenize_sql(sql3)
    assert "DROP" in tokens3


def test_classify_sql_statements():
    # SELECT
    c_sel = classify_sql("SELECT id, name FROM customers WHERE id = 1")
    assert c_sel["statement_type"] == "SELECT"
    assert c_sel["is_destructive"] is False
    assert c_sel["has_where"] is True

    # INSERT
    c_ins = classify_sql("INSERT INTO customers (name, email) VALUES ('Acme', 'a@b.com')")
    assert c_ins["statement_type"] == "INSERT"
    assert c_ins["is_destructive"] is False

    # UPDATE with WHERE
    c_upd = classify_sql("UPDATE customers SET city = 'Mangaluru' WHERE id = 2")
    assert c_upd["statement_type"] == "UPDATE"
    assert c_upd["is_destructive"] is False
    assert c_upd["has_where"] is True

    # DELETE with WHERE (allowed)
    c_del_where = classify_sql("DELETE FROM customers WHERE id = 10")
    assert c_del_where["statement_type"] == "DELETE"
    assert c_del_where["has_where"] is True
    assert c_del_where["is_destructive"] is False

    # DELETE without WHERE (hard block)
    c_del_nowhere = classify_sql("DELETE FROM customers")
    assert c_del_nowhere["statement_type"] == "DELETE"
    assert c_del_nowhere["has_where"] is False
    assert c_del_nowhere["is_destructive"] is True

    # DROP TABLE (hard block)
    c_drop = classify_sql("DROP TABLE customers")
    assert c_drop["statement_type"] == "DROP"
    assert c_drop["is_destructive"] is True

    # TRUNCATE (hard block)
    c_trunc = classify_sql("TRUNCATE orders")
    assert c_trunc["statement_type"] == "TRUNCATE"
    assert c_trunc["is_destructive"] is True

    # Injection with hidden DROP inside multi-statement or comment
    c_inject = classify_sql("DELETE FROM customers /* WHERE 1=1 */")
    assert c_inject["is_destructive"] is True  # Comment was stripped, so has_where is False


# ===========================================================================
# 2. Email Domain Extraction & Allowlist Tests
# ===========================================================================
def test_extract_email_domains():
    assert extract_email_domains("alice@company.com") == ["company.com"]
    assert extract_email_domains("Bob <bob@internal.corp>") == ["internal.corp"]
    assert extract_email_domains("a@example.com, b@company.com") == ["example.com", "company.com"]
    assert extract_email_domains(["x@one.com", "y@two.com"]) == ["one.com", "two.com"]
    assert extract_email_domains("") == []


# ===========================================================================
# 3. Policy Loading & permitted() Tests
# ===========================================================================
def test_load_active_policies(seeded_db):
    policies = load_active_policies(seeded_db)
    assert len(policies) >= 4
    tools = [p["tool"] for p in policies]
    assert "payments.send" in tools
    assert "database.run_sql" in tools
    assert "email.send" in tools


def test_permitted_agents(seeded_db):
    # Accounts agent (writer) can execute permitted tools
    assert permitted("accounts-agent", "task-accounts-1", "payments.send", db_path=seeded_db) is True
    assert permitted("accounts-agent", "task-accounts-1", "email.send", db_path=seeded_db) is True
    assert permitted("accounts-agent", "task-accounts-1", "database.run_sql", db_path=seeded_db) is True

    # Reader agent (role reader) cannot execute write tools
    assert permitted("reader-agent", "task-reader-1", "payments.send", db_path=seeded_db) is False
    assert permitted("reader-agent", "task-reader-1", "database.run_sql", db_path=seeded_db) is False

    # Accounts agent cannot execute unapproved / unknown tool
    assert permitted("accounts-agent", "task-accounts-1", "admin.destroy_system", db_path=seeded_db) is False

    # Unknown agent
    assert permitted("nonexistent-agent", "task-accounts-1", "payments.send", db_path=seeded_db) is False


# ===========================================================================
# 4. hard_block(req) Tests
# ===========================================================================
def test_hard_block_reader_agent(seeded_db):
    req = ExecuteRequest(
        agent_id="reader-agent",
        task_id="task-reader-1",
        tool="payments.send",
        params={"recipient": "Supplier A", "amount": 5000, "currency": "INR"},
    )
    assert hard_block(req, db_path=seeded_db) == REASON_NO_PERMISSION


def test_hard_block_drop_table(seeded_db):
    req = ExecuteRequest(
        agent_id="accounts-agent",
        task_id="task-accounts-1",
        tool="database.run_sql",
        params={"query": "DROP TABLE customers"},
    )
    assert hard_block(req, db_path=seeded_db) == REASON_DESTRUCTIVE_SQL


def test_hard_block_truncate(seeded_db):
    req = ExecuteRequest(
        agent_id="accounts-agent",
        task_id="task-accounts-1",
        tool="database.run_sql",
        params={"query": "TRUNCATE orders"},
    )
    assert hard_block(req, db_path=seeded_db) == REASON_DESTRUCTIVE_SQL


def test_hard_block_delete_without_where(seeded_db):
    req = ExecuteRequest(
        agent_id="accounts-agent",
        task_id="task-accounts-1",
        tool="database.run_sql",
        params={"query": "DELETE FROM customers"},
    )
    assert hard_block(req, db_path=seeded_db) == REASON_DESTRUCTIVE_SQL


def test_hard_block_delete_with_where_is_allowed(seeded_db):
    req = ExecuteRequest(
        agent_id="accounts-agent",
        task_id="task-accounts-1",
        tool="database.run_sql",
        params={"query": "DELETE FROM customers WHERE id = 5"},
    )
    assert hard_block(req, db_path=seeded_db) is None


def test_hard_block_valid_payment_is_allowed(seeded_db):
    req = ExecuteRequest(
        agent_id="accounts-agent",
        task_id="task-accounts-1",
        tool="payments.send",
        params={"recipient": "Supplier A", "amount": 5000, "currency": "INR"},
    )
    assert hard_block(req, db_path=seeded_db) is None


# ===========================================================================
# 5. requires_approval(req) Tests
# ===========================================================================
def test_requires_approval_payment_threshold(seeded_db):
    # Over threshold (> 10,000 INR = 1,000,000 paise)
    req_high = ExecuteRequest(
        agent_id="accounts-agent",
        task_id="task-accounts-1",
        tool="payments.send",
        params={"recipient": "Supplier A", "amount": 15000.00, "currency": "INR"},
    )
    assert requires_approval(req_high, db_path=seeded_db) == REASON_OVER_THRESHOLD

    # Under threshold (<= 10,000 INR)
    req_low = ExecuteRequest(
        agent_id="accounts-agent",
        task_id="task-accounts-1",
        tool="payments.send",
        params={"recipient": "Supplier A", "amount": 5000.00, "currency": "INR"},
    )
    assert requires_approval(req_low, db_path=seeded_db) is None


def test_requires_approval_email_allowlist(seeded_db):
    # Allowed domain
    req_allowed = ExecuteRequest(
        agent_id="accounts-agent",
        task_id="task-accounts-1",
        tool="email.send",
        params={"to": "billing@company.com", "subject": "Invoice", "body": "Attached"},
    )
    assert requires_approval(req_allowed, db_path=seeded_db) is None

    # External unknown domain -> ASK_HUMAN
    req_external = ExecuteRequest(
        agent_id="accounts-agent",
        task_id="task-accounts-1",
        tool="email.send",
        params={"to": "contact@unknown-vendor.xyz", "subject": "Notice", "body": "Hi"},
    )
    assert requires_approval(req_external, db_path=seeded_db) == REASON_UNKNOWN_EMAIL_DOMAIN


# ===========================================================================
# 6. Simulated Tools Tests
# ===========================================================================
def test_payments_tool_simulation():
    payments_tool.clear_ledger()

    # Call with positional/keyword arguments
    res = payments_tool.send("Supplier A", 5000, "INR")
    assert res["simulated"] is True
    assert res["status"] == "simulated_success"
    assert res["recipient"] == "Supplier A"
    assert res["amount"] == 5000
    assert res["txn_id"].startswith("sim_txn_")
    assert "[SIMULATED]" in payments_tool.send.__doc__

    # Ledger recorded the payment
    ledger = payments_tool.get_ledger()
    assert len(ledger) == 1
    assert ledger[0]["recipient"] == "Supplier A"

    # Call with params dict
    res2 = payments_tool.send({"recipient": "Supplier B", "amount": 2500, "currency": "INR"})
    assert res2["simulated"] is True
    assert res2["recipient"] == "Supplier B"
    assert len(payments_tool.get_ledger()) == 2


def test_email_tool_simulation():
    email_tool.clear_outbox()

    res = email_tool.send("vendor@example.com", "Payment Advise", "Amount credited")
    assert res["simulated"] is True
    assert res["status"] == "simulated_success"
    assert res["to"] == "vendor@example.com"
    assert res["subject"] == "Payment Advise"
    assert res["message_id"].startswith("sim_email_")
    assert "[SIMULATED]" in email_tool.send.__doc__

    outbox = email_tool.get_outbox()
    assert len(outbox) == 1
    assert outbox[0]["to"] == "vendor@example.com"


def test_database_tool_simulation(tmp_path):
    demo_db = str(tmp_path / "sandbox_demo.db")

    # SELECT customers
    res = db_tool.run_sql("SELECT * FROM customers", database_path=demo_db)
    assert res["simulated"] is True
    assert res["status"] == "simulated_success"
    assert len(res["rows"]) >= 3
    customer_names = [r["name"] for r in res["rows"]]
    assert "Supplier A Ltd" in customer_names

    # SELECT orders
    res_orders = db_tool.run_sql("SELECT * FROM orders", database_path=demo_db)
    assert res_orders["simulated"] is True
    assert len(res_orders["rows"]) >= 3

    # INSERT into customers
    res_ins = db_tool.run_sql(
        "INSERT INTO customers (name, email, city) VALUES ('New Client', 'client@test.com', 'Surathkal')",
        database_path=demo_db,
    )
    assert res_ins["simulated"] is True
    assert res_ins["rows_affected"] == 1

    # Verify new row is queryable
    res_verify = db_tool.run_sql("SELECT * FROM customers WHERE city = 'Surathkal'", database_path=demo_db)
    assert len(res_verify["rows"]) == 1
    assert res_verify["rows"][0]["name"] == "New Client"
    assert "[SIMULATED]" in db_tool.run_sql.__doc__
