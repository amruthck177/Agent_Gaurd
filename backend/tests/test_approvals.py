"""
backend/tests/test_approvals.py

Unit tests for backend/app/approvals.py:
  1. create() creates pending approval with canonical sensitive params hash
  2. Sensitive parameters per tool:
     - payments.send (recipient, amount, currency)
     - email.send (to domain, has_attachment)
     - database.run_sql (statement type, table)
  3. State transitions: approve(), reject(), revoke()
  4. list() filtering by status
  5. Injectable clock integration
  6. diff() field-level diff helper
  7. Secret masking in approved_params_json
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from app.db import reset_db, seed_demo, get_connection
from app.approvals import (
    create,
    approve,
    reject,
    revoke,
    get,
    list_approvals,
    list as list_alias,
    diff,
    extract_sensitive_params,
    extract_email_domain,
    extract_sql_statement_type_and_table,
    now,
    set_clock,
    reset_clock,
    mask_secrets,
    APPROVAL_TTL_SECONDS,
)
from app.schemas import canonical_hash


class CustomTestClock:
    def __init__(self, start_dt: datetime):
        self._dt = start_dt

    def now(self) -> datetime:
        return self._dt

    def advance(self, **kwargs) -> None:
        self._dt += timedelta(**kwargs)


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    path = str(tmp_path / "test_approvals.db")
    reset_db(path)
    seed_demo(path)
    return path


@pytest.fixture
def test_clock() -> CustomTestClock:
    return CustomTestClock(datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc))


# ---------------------------------------------------------------------------
# Test 1: create() basic functionality
# ---------------------------------------------------------------------------
def test_create_pending_approval(db_path: str, test_clock: CustomTestClock):
    params = {
        "recipient": "Supplier A",
        "amount": 5000.00,
        "currency": "INR",
        "reference": "INV-100",
    }
    ap = create(
        "accounts-agent",
        "task-accounts-1",
        "payments.send",
        params,
        db_path=db_path,
        clock=test_clock,
        ttl_seconds=300,
    )

    assert ap.id.startswith("APR-")
    assert ap.agent_id == "accounts-agent"
    assert ap.task_id == "task-accounts-1"
    assert ap.tool == "payments.send"
    assert ap.status == "pending"
    assert ap.created_at == test_clock.now().isoformat()
    assert ap.expires_at == (test_clock.now() + timedelta(seconds=300)).isoformat()
    assert ap.approved_at is None
    assert ap.revoked_at is None
    assert ap.used_at is None

    # Check approved_hash matches sensitive params hash
    sens = extract_sensitive_params("payments.send", params)
    expected_hash = canonical_hash(sens)
    assert ap.approved_hash == expected_hash

    # Check persistence in DB
    stored = get(ap.id, db_path=db_path)
    assert stored is not None
    assert stored.id == ap.id
    assert stored.status == "pending"
    assert stored.approved_hash == expected_hash


# ---------------------------------------------------------------------------
# Test 2: Sensitive params extraction for payments.send
# ---------------------------------------------------------------------------
def test_sensitive_params_payments():
    p1 = {"recipient": "Supplier A ", "amount": 5000.00, "currency": "inr", "reference": "INV-1"}
    p2 = {"recipient": "supplier a", "amount_paise": 500000, "currency": "INR", "reference": "DIFFERENT-REF"}
    p3 = {"recipient": "Supplier B", "amount": 5000.00, "currency": "INR"}

    s1 = extract_sensitive_params("payments.send", p1)
    s2 = extract_sensitive_params("payments.send", p2)
    s3 = extract_sensitive_params("payments.send", p3)

    # s1 and s2 have identical normalized sensitive parameters (despite different ref and amount format)
    assert canonical_hash(s1) == canonical_hash(s2)
    # s3 has different recipient -> different hash
    assert canonical_hash(s1) != canonical_hash(s3)


# ---------------------------------------------------------------------------
# Test 3: Sensitive params extraction for email.send
# ---------------------------------------------------------------------------
def test_sensitive_params_email():
    p1 = {"to": "alice@company.com", "subject": "Hello", "has_attachment": False}
    p2 = {"to": "bob@company.com", "subject": "Good morning", "has_attachment": False}
    p3 = {"to": "bob@external.org", "subject": "Hello", "has_attachment": False}
    p4 = {"to": "alice@company.com", "subject": "Hello", "has_attachment": True}

    s1 = extract_sensitive_params("email.send", p1)
    s2 = extract_sensitive_params("email.send", p2)
    s3 = extract_sensitive_params("email.send", p3)
    s4 = extract_sensitive_params("email.send", p4)

    # Same domain + same attachment status -> same hash
    assert canonical_hash(s1) == canonical_hash(s2)
    # Different domain -> different hash
    assert canonical_hash(s1) != canonical_hash(s3)
    # Different attachment -> different hash
    assert canonical_hash(s1) != canonical_hash(s4)


# ---------------------------------------------------------------------------
# Test 4: Sensitive params extraction for database.run_sql
# ---------------------------------------------------------------------------
def test_sensitive_params_database():
    p1 = {"query": "SELECT * FROM orders WHERE id = 1"}
    p2 = {"query": "SELECT count(*) FROM `orders`"}
    p3 = {"query": "DROP TABLE orders"}
    p4 = {"query": "SELECT * FROM customers"}

    s1 = extract_sensitive_params("database.run_sql", p1)
    s2 = extract_sensitive_params("database.run_sql", p2)
    s3 = extract_sensitive_params("database.run_sql", p3)
    s4 = extract_sensitive_params("database.run_sql", p4)

    # s1 and s2 both have statement_type='SELECT' and table='orders'
    assert s1["statement_type"] == "SELECT"
    assert s1["table"] == "orders"
    assert canonical_hash(s1) == canonical_hash(s2)

    # s3 has statement_type='DROP'
    assert s3["statement_type"] == "DROP"
    assert canonical_hash(s1) != canonical_hash(s3)

    # s4 has table='customers'
    assert s4["table"] == "customers"
    assert canonical_hash(s1) != canonical_hash(s4)


# ---------------------------------------------------------------------------
# Test 5: State transitions (approve, reject, revoke)
# ---------------------------------------------------------------------------
def test_approval_lifecycle(db_path: str, test_clock: CustomTestClock):
    # Create
    ap = create("accounts-agent", "task-accounts-1", "payments.send", {"amount": 500}, db_path=db_path, clock=test_clock)
    assert ap.status == "pending"

    # Approve
    test_clock.advance(minutes=1)
    approved = approve(ap.id, db_path=db_path, clock=test_clock)
    assert approved.status == "approved"
    assert approved.approved_at == test_clock.now().isoformat()

    # Revoke
    test_clock.advance(minutes=2)
    revoked = revoke(ap.id, db_path=db_path, clock=test_clock)
    assert revoked.status == "revoked"
    assert revoked.revoked_at == test_clock.now().isoformat()


def test_reject_lifecycle(db_path: str, test_clock: CustomTestClock):
    ap = create("accounts-agent", "task-accounts-1", "payments.send", {"amount": 500}, db_path=db_path, clock=test_clock)
    assert ap.status == "pending"

    rejected = reject(ap.id, db_path=db_path, clock=test_clock)
    assert rejected.status == "rejected"


# ---------------------------------------------------------------------------
# Test 6: list() filtering
# ---------------------------------------------------------------------------
def test_list_approvals(db_path: str, test_clock: CustomTestClock):
    ap1 = create("accounts-agent", "task-accounts-1", "payments.send", {"amount": 100}, db_path=db_path, clock=test_clock)
    ap2 = create("accounts-agent", "task-accounts-1", "payments.send", {"amount": 200}, db_path=db_path, clock=test_clock)
    ap3 = create("accounts-agent", "task-accounts-1", "payments.send", {"amount": 300}, db_path=db_path, clock=test_clock)

    approve(ap2.id, db_path=db_path, clock=test_clock)
    reject(ap3.id, db_path=db_path, clock=test_clock)

    all_items = list_alias(db_path=db_path)
    assert len(all_items) >= 3

    pending_items = list_alias("pending", db_path=db_path)
    assert any(x.id == ap1.id for x in pending_items)
    assert not any(x.id == ap2.id for x in pending_items)

    approved_items = list_alias("approved", db_path=db_path)
    assert any(x.id == ap2.id for x in approved_items)

    rejected_items = list_alias("rejected", db_path=db_path)
    assert any(x.id == ap3.id for x in rejected_items)


# ---------------------------------------------------------------------------
# Test 7: Injectable clock via set_clock / reset_clock
# ---------------------------------------------------------------------------
def test_global_injectable_clock(test_clock: CustomTestClock):
    reset_clock()
    initial_now = now()
    assert isinstance(initial_now, datetime)

    set_clock(test_clock)
    assert now() == test_clock.now()

    test_clock.advance(hours=5)
    assert now() == test_clock.now()

    reset_clock()
    assert now() != test_clock.now()


# ---------------------------------------------------------------------------
# Test 8: diff() helper tests
# ---------------------------------------------------------------------------
def test_diff_recipient_and_amount():
    approved = {"recipient": "Supplier A", "amount": 5000.00, "currency": "INR"}
    attempted = {"recipient": "Supplier B", "amount": 6000.00, "currency": "INR"}

    diffs = diff(approved, attempted, tool="payments.send")
    fields = {d["field"]: d for d in diffs}

    assert "recipient" in fields
    assert fields["recipient"]["approved"] == "Supplier A"
    assert fields["recipient"]["attempted"] == "Supplier B"

    assert "amount" in fields
    assert fields["amount"]["approved"] == 5000.00
    assert fields["amount"]["attempted"] == 6000.00


def test_diff_identical_normalized_returns_empty():
    approved = {"recipient": "Supplier A ", "amount": 5000.00, "currency": "inr"}
    attempted = {"recipient": "supplier a", "amount_paise": 500000, "currency": "INR"}

    diffs = diff(approved, attempted, tool="payments.send")
    assert diffs == []


def test_diff_email_domain():
    approved = {"to": "support@partner.com", "has_attachment": False}
    attempted = {"to": "support@hacker.io", "has_attachment": False}

    diffs = diff(approved, attempted, tool="email.send")
    assert len(diffs) == 1
    assert diffs[0]["field"] == "to_domain"


def test_diff_database_sql():
    approved = {"query": "SELECT * FROM orders"}
    attempted = {"query": "DROP TABLE orders"}

    diffs = diff(approved, attempted, tool="database.run_sql")
    assert len(diffs) == 1
    assert diffs[0]["field"] == "statement_type"
    assert diffs[0]["approved"] == "SELECT"
    assert diffs[0]["attempted"] == "DROP"


# ---------------------------------------------------------------------------
# Test 9: Secret masking in approved_params_json
# ---------------------------------------------------------------------------
def test_secrets_masked_in_approval_storage(db_path: str):
    secret_val = "sk-test-SUPERSECRETTOKEN123"
    params = {
        "recipient": "Supplier A",
        "amount": 5000.00,
        "api_key": secret_val,
        "auth_token": f"Bearer {secret_val}",
    }
    ap = create("accounts-agent", "task-accounts-1", "payments.send", params, db_path=db_path)

    assert secret_val not in ap.approved_params_json
    assert "[MASKED]" in ap.approved_params_json

    # Check database raw row directly
    conn = get_connection(db_path)
    row = conn.execute("SELECT approved_params_json FROM approvals WHERE id = ?", (ap.id,)).fetchone()
    conn.close()

    assert secret_val not in row["approved_params_json"]
    assert "[MASKED]" in row["approved_params_json"]
