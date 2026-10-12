"""
backend/tests/test_gateway_toctou.py

Security tests for R3: TOCTOU race resolution and concurrent execution prevention in gateway.py.
Verifies that:
- When atomic UPDATE fails due to concurrent revocation, gateway re-reads approval
  and records reason='Approval revoked' (not replay).
- When atomic UPDATE fails due to concurrent expiry, gateway re-reads approval
  and records reason='Approval expired' (not replay).
- When 10 concurrent threads attempt to execute the same approval, exactly 1 succeeds
  (ALLOW, executed=True) and 9 are blocked with reason='Approval already used (replay)'.
- Total tool execution count is strictly 1.
"""

import concurrent.futures
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app import approvals
from app.db import get_connection, reset_db, seed_demo
from app.gateway import execute
from app.schemas import Decision


@pytest.fixture
def clean_db(tmp_path):
    db_file = str(tmp_path / "test_gateway_toctou.db")
    reset_db(db_file)
    seed_demo(db_file)
    return db_file


def test_revocation_during_atomic_update_returns_revoked_reason(clean_db):
    """
    If an approval is revoked concurrently right before atomic UPDATE executes,
    gateway must re-read DB and report 'Approval revoked', NOT 'Approval already used (replay)'.
    """
    params = {"recipient": "Supplier A", "amount": 5000.0, "currency": "INR"}
    ap = approvals.create("accounts-agent", "task-accounts-1", "payments.send", params, db_path=clean_db)
    approvals.approve(ap.id, db_path=clean_db)

    # Revoke approval right as atomic update is attempted
    real_atomic = __import__("app.gateway", fromlist=["_atomic_use_approval"])._atomic_use_approval

    def revoke_and_run(db_path, approval_id, clock):
        approvals.revoke(approval_id, db_path=db_path)
        return real_atomic(db_path, approval_id, clock)

    with patch("app.gateway._atomic_use_approval", side_effect=revoke_and_run):
        resp = execute(
            db_path=clean_db,
            agent_id="accounts-agent",
            task_id="task-accounts-1",
            tool="payments.send",
            params=params,
            approval_id=ap.id,
        )

    decision = resp.decision if isinstance(resp.decision, str) else resp.decision.value
    assert decision == Decision.BLOCK.value
    assert resp.reason == "Approval revoked", f"Expected 'Approval revoked', got: {resp.reason!r}"
    assert resp.executed is False


def test_expiry_during_atomic_update_returns_expired_reason(clean_db):
    """
    If an approval expires concurrently right before atomic UPDATE executes,
    gateway must re-read DB and report 'Approval expired', NOT 'Approval already used (replay)'.
    """
    params = {"recipient": "Supplier A", "amount": 5000.0, "currency": "INR"}
    ap = approvals.create("accounts-agent", "task-accounts-1", "payments.send", params, db_path=clean_db)
    approvals.approve(ap.id, db_path=clean_db)

    # Force expiration in DB right as atomic update is attempted
    real_atomic = __import__("app.gateway", fromlist=["_atomic_use_approval"])._atomic_use_approval

    def expire_and_run(db_path, approval_id, clock):
        conn = get_connection(db_path)
        try:
            conn.execute("UPDATE approvals SET expires_at = '2020-01-01T00:00:00+00:00' WHERE id = ?", (approval_id,))
            conn.commit()
        finally:
            conn.close()
        return real_atomic(db_path, approval_id, clock)

    with patch("app.gateway._atomic_use_approval", side_effect=expire_and_run):
        resp = execute(
            db_path=clean_db,
            agent_id="accounts-agent",
            task_id="task-accounts-1",
            tool="payments.send",
            params=params,
            approval_id=ap.id,
        )

    decision = resp.decision if isinstance(resp.decision, str) else resp.decision.value
    assert decision == Decision.BLOCK.value
    assert resp.reason == "Approval expired", f"Expected 'Approval expired', got: {resp.reason!r}"
    assert resp.executed is False


def test_concurrent_execution_single_winner(clean_db):
    """
    10 threads concurrently executing the same approval:
    Exactly 1 ALLOW (executed=True)
    Exactly 9 BLOCK ('Approval already used (replay)')
    Total tool_calls in DB must be exactly 1.
    """
    params = {"recipient": "Supplier A", "amount": 5000.0, "currency": "INR"}
    ap = approvals.create("accounts-agent", "task-accounts-1", "payments.send", params, db_path=clean_db)
    approvals.approve(ap.id, db_path=clean_db)

    results = []

    def worker():
        return execute(
            db_path=clean_db,
            agent_id="accounts-agent",
            task_id="task-accounts-1",
            tool="payments.send",
            params=params,
            approval_id=ap.id,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(worker) for _ in range(10)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    allows = [r for r in results if (r.decision if isinstance(r.decision, str) else r.decision.value) == "ALLOW"]
    blocks = [r for r in results if (r.decision if isinstance(r.decision, str) else r.decision.value) == "BLOCK"]

    assert len(allows) == 1, f"Expected 1 ALLOW, got {len(allows)}"
    assert len(blocks) == 9, f"Expected 9 BLOCK, got {len(blocks)}"

    for b in blocks:
        assert b.reason == "Approval already used (replay)"
        assert b.executed is False

    # Check database tool_calls count
    conn = get_connection(clean_db)
    try:
        cur = conn.cursor()
        count = cur.execute("SELECT COUNT(*) FROM tool_calls").fetchone()[0]
        assert count == 1, f"Expected 1 tool_call in DB, got {count}"
    finally:
        conn.close()
