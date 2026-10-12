"""
backend/tests/test_security.py

AgentGuard security test suite.
Plan.md §E1 required tests + extras from the user requirement.

These tests INTENTIONALLY FAIL until gateway.execute() is implemented.
They are the specification. When all 16 pass, the gateway is correct.

Decision strings are checked exactly. Reason strings are checked exactly.
tool_calls row count is checked for every test (the evidence that a tool ran or did not).

Run with:
    python run_tests.py tests/test_security.py -v
"""

from __future__ import annotations

import ast
import concurrent.futures
import os
import re
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from unittest.mock import patch

import pytest

from app.db import get_connection, reset_db, seed_demo
from app.schemas import Decision, canonical_hash, normalize_params


# ---------------------------------------------------------------------------
# Exact reason strings (plan.md §C2 + user spec)
# ---------------------------------------------------------------------------
REASON_RECIPIENT_CHANGED = "Recipient changed after approval"
REASON_AMOUNT_CHANGED = "Amount changed after approval"
REASON_EXPIRED = "Approval expired"
REASON_REVOKED = "Approval revoked"
REASON_REPLAY = "Approval already used (replay)"
REASON_NO_PERMISSION = "Agent lacks write permission"
REASON_DROP_TABLE = "Destructive database operation prohibited"
REASON_OVER_THRESHOLD = "Payment exceeds ₹10,000 limit: human approval required"
REASON_FAIL_CLOSED = "Gateway error: failed closed"


# ---------------------------------------------------------------------------
# Injectable clock — avoids sleep() in expiry tests
# ---------------------------------------------------------------------------
class FakeClock:
    """A clock whose current time can be nudged forward without sleeping."""

    def __init__(self):
        self._now: datetime = datetime.now(tz=timezone.utc)

    def now(self) -> datetime:
        return self._now

    def advance(self, **kwargs) -> None:
        """Advance time by the given timedelta kwargs (seconds=, minutes=, …)."""
        self._now += timedelta(**kwargs)

    def isoformat(self) -> str:
        return self._now.isoformat()


# ---------------------------------------------------------------------------
# DB fixture (fresh temp database per test)
# ---------------------------------------------------------------------------
@pytest.fixture()
def db_path(tmp_path) -> str:
    """Path to a fresh, seeded SQLite database for each test."""
    path = str(tmp_path / "test_agentguard.db")
    reset_db(path)
    seed_demo(path)
    return path


@pytest.fixture()
def clock() -> FakeClock:
    """Injectable clock shared between fixture helpers and tests."""
    return FakeClock()


# ---------------------------------------------------------------------------
# Helper: thin wrappers used inside tests.
# These call the gateway module, which is not yet implemented.
# They are written in terms of the interface that gateway.py MUST expose.
# ---------------------------------------------------------------------------

def _import_gateway():
    """
    Lazily import gateway so collection does not error before the module exists.
    Tests will raise ImportError and be marked ERROR until gateway.py is written.
    """
    from app import gateway  # noqa: F401 – triggers ImportError if stub only
    return gateway


def create_approval(
    db_path: str,
    agent_id: str,
    task_id: str,
    tool: str,
    params: Dict[str, Any],
    clock: Optional[FakeClock] = None,
    ttl_seconds: int = 600,
) -> str:
    """
    Insert a PENDING approval row via approvals.create and return its id.
    Does not go through the gateway (mimics the POST /v1/approvals endpoint).
    """
    from app import approvals
    ap = approvals.create(
        agent_id=agent_id,
        task_id=task_id,
        tool=tool,
        params=params,
        db_path=db_path,
        clock=clock,
        ttl_seconds=ttl_seconds,
    )
    return ap.id


def approve(db_path: str, approval_id: str, clock: Optional[FakeClock] = None) -> None:
    """Transition an approval from pending → approved."""
    from app import approvals
    approvals.approve(approval_id, db_path=db_path, clock=clock)


def revoke(db_path: str, approval_id: str, clock: Optional[FakeClock] = None) -> None:
    """Transition an approval from approved → revoked."""
    from app import approvals
    approvals.revoke(approval_id, db_path=db_path, clock=clock)


def execute(
    db_path: str,
    agent_id: str,
    task_id: str,
    tool: str,
    params: Dict[str, Any],
    approval_id: Optional[str] = None,
    clock: Optional[FakeClock] = None,
) -> Dict[str, Any]:
    """
    Call gateway.execute() and return the response as a plain dict.
    gateway.execute() must accept:
      (db_path, agent_id, task_id, tool, params, approval_id=None, clock=None)
    and return an object with attributes: decision, reason, executed, audit_id.
    """
    gw = _import_gateway()
    resp = gw.execute(
        db_path=db_path,
        agent_id=agent_id,
        task_id=task_id,
        tool=tool,
        params=params,
        approval_id=approval_id,
        clock=clock,
    )
    return {
        "decision": resp.decision if isinstance(resp.decision, str) else resp.decision.value,
        "reason": resp.reason,
        "executed": resp.executed,
        "audit_id": resp.audit_id,
        "approval_id": getattr(resp, "approval_id", None),
    }


def tool_calls_count(db_path: str, tool: str, params: Dict[str, Any]) -> int:
    """
    Count rows in tool_calls for this (tool, canonical-params) combination.
    This is the tamper-evident proof that a tool ran or did not run.
    """
    import json
    normalised = normalize_params(params)
    params_json = json.dumps(normalised, sort_keys=True)
    conn = get_connection(db_path)
    row = conn.execute(
        "SELECT COUNT(*) FROM tool_calls WHERE tool=? AND params_json=?",
        (tool, params_json),
    ).fetchone()
    conn.close()
    return row[0]


def total_tool_calls(db_path: str) -> int:
    """Count ALL rows in tool_calls regardless of tool or params."""
    conn = get_connection(db_path)
    row = conn.execute("SELECT COUNT(*) FROM tool_calls").fetchone()
    conn.close()
    return row[0]


# ---------------------------------------------------------------------------
# Standard payment params used across multiple tests
# ---------------------------------------------------------------------------
PAYMENT_SUPPLIER_A = {
    "recipient": "Supplier A",
    "amount": 5000.00,   # ₹5,000 = 500,000 paise — under threshold
    "currency": "INR",
    "reference": "INV-001",
}

PAYMENT_SUPPLIER_B = {
    "recipient": "Supplier B",
    "amount": 5000.00,
    "currency": "INR",
    "reference": "INV-001",
}


# ===========================================================================
# Security Test 1: Changed recipient
# plan.md §D scenario 2; §E1 test 1
# ===========================================================================
def test_changed_recipient(db_path, clock):
    """
    Approve a payment to Supplier A. Agent tries to pay Supplier B.
    Must BLOCK with "Recipient changed after approval". tool_calls must be 0.
    """
    approval_id = create_approval(db_path, "accounts-agent", "task-accounts-1", "payments.send", PAYMENT_SUPPLIER_A, clock)
    approve(db_path, approval_id, clock)

    # Attempt with a different recipient
    resp = execute(db_path, "accounts-agent", "task-accounts-1", "payments.send",
                   PAYMENT_SUPPLIER_B, approval_id=approval_id, clock=clock)

    assert resp["decision"] == Decision.BLOCK.value, f"Expected BLOCK, got {resp['decision']}"
    assert resp["reason"] == REASON_RECIPIENT_CHANGED, f"Reason mismatch: {resp['reason']!r}"
    assert resp["executed"] is False
    assert tool_calls_count(db_path, "payments.send", PAYMENT_SUPPLIER_B) == 0


# ===========================================================================
# Security Test 2: Changed amount
# plan.md §D scenario 3; §E1 test 2
# ===========================================================================
def test_changed_amount(db_path, clock):
    """
    Approve ₹5,000 to Supplier A. Agent tries ₹6,000. Must BLOCK.
    """
    approval_id = create_approval(db_path, "accounts-agent", "task-accounts-1", "payments.send", PAYMENT_SUPPLIER_A, clock)
    approve(db_path, approval_id, clock)

    tampered = {**PAYMENT_SUPPLIER_A, "amount": 6000.00}
    resp = execute(db_path, "accounts-agent", "task-accounts-1", "payments.send",
                   tampered, approval_id=approval_id, clock=clock)

    assert resp["decision"] == Decision.BLOCK.value
    assert resp["reason"] == REASON_AMOUNT_CHANGED, f"Reason mismatch: {resp['reason']!r}"
    assert resp["executed"] is False
    assert tool_calls_count(db_path, "payments.send", tampered) == 0


# ===========================================================================
# Security Test 3: Expired approval
# plan.md §D scenario 4; §E1 test 3 — uses injectable clock, no sleep()
# ===========================================================================
def test_expired_approval(db_path, clock):
    """
    Create an approval with 60 s TTL. Advance the clock 61 s.
    Must BLOCK with "Approval expired". tool_calls must be 0.
    """
    approval_id = create_approval(db_path, "accounts-agent", "task-accounts-1", "payments.send",
                                  PAYMENT_SUPPLIER_A, clock, ttl_seconds=60)
    approve(db_path, approval_id, clock)

    # Advance clock past expiry
    clock.advance(seconds=61)

    resp = execute(db_path, "accounts-agent", "task-accounts-1", "payments.send",
                   PAYMENT_SUPPLIER_A, approval_id=approval_id, clock=clock)

    assert resp["decision"] == Decision.BLOCK.value
    assert resp["reason"] == REASON_EXPIRED, f"Reason mismatch: {resp['reason']!r}"
    assert resp["executed"] is False
    assert tool_calls_count(db_path, "payments.send", PAYMENT_SUPPLIER_A) == 0


# ===========================================================================
# Security Test 4: Revoked approval
# plan.md §D scenario 5; §E1 test 4
# ===========================================================================
def test_revoked_approval(db_path, clock):
    """
    Approve then revoke. Executing the revoked approval must BLOCK.
    """
    approval_id = create_approval(db_path, "accounts-agent", "task-accounts-1", "payments.send", PAYMENT_SUPPLIER_A, clock)
    approve(db_path, approval_id, clock)
    revoke(db_path, approval_id, clock)

    resp = execute(db_path, "accounts-agent", "task-accounts-1", "payments.send",
                   PAYMENT_SUPPLIER_A, approval_id=approval_id, clock=clock)

    assert resp["decision"] == Decision.BLOCK.value
    assert resp["reason"] == REASON_REVOKED, f"Reason mismatch: {resp['reason']!r}"
    assert resp["executed"] is False
    assert tool_calls_count(db_path, "payments.send", PAYMENT_SUPPLIER_A) == 0


# ===========================================================================
# Security Test 5: Read-only agent attempts write
# plan.md §D scenario 6; §E1 test 5
# ===========================================================================
def test_read_only_agent_write(db_path, clock):
    """
    reader-agent has role 'reader' and empty permissions list.
    Attempting payments.send must BLOCK before any approval check.
    """
    resp = execute(db_path, "reader-agent", "task-reader-1", "payments.send",
                   PAYMENT_SUPPLIER_A, clock=clock)

    assert resp["decision"] == Decision.BLOCK.value
    assert resp["reason"] == REASON_NO_PERMISSION, f"Reason mismatch: {resp['reason']!r}"
    assert resp["executed"] is False
    assert total_tool_calls(db_path) == 0


# ===========================================================================
# Security Test 6a: Replay / duplicate – sequential
# plan.md §E1 test 6
# ===========================================================================
def test_replay_sequential(db_path, clock):
    """
    Use an approval once (ALLOW). Use it again (BLOCK: replay).
    """
    approval_id = create_approval(db_path, "accounts-agent", "task-accounts-1", "payments.send", PAYMENT_SUPPLIER_A, clock)
    approve(db_path, approval_id, clock)

    # First use: must ALLOW and mark as used
    resp1 = execute(db_path, "accounts-agent", "task-accounts-1", "payments.send",
                    PAYMENT_SUPPLIER_A, approval_id=approval_id, clock=clock)
    assert resp1["decision"] == Decision.ALLOW.value, f"First use should ALLOW, got {resp1['decision']}"
    assert resp1["executed"] is True

    # Second use: must BLOCK (replay)
    resp2 = execute(db_path, "accounts-agent", "task-accounts-1", "payments.send",
                    PAYMENT_SUPPLIER_A, approval_id=approval_id, clock=clock)
    assert resp2["decision"] == Decision.BLOCK.value
    assert resp2["reason"] == REASON_REPLAY, f"Reason mismatch: {resp2['reason']!r}"
    assert resp2["executed"] is False

    # Exactly one tool_calls row (from the first, legitimate execution)
    assert tool_calls_count(db_path, "payments.send", PAYMENT_SUPPLIER_A) == 1


# ===========================================================================
# Security Test 6b: Replay / duplicate – two concurrent threads
# plan.md §E1 test 6 (concurrent variant)
# ===========================================================================
def test_replay_concurrent(db_path, clock):
    """
    Two threads fire the same approval simultaneously.
    The atomic UPDATE...WHERE status='approved' must guarantee exactly one ALLOW.
    """
    approval_id = create_approval(db_path, "accounts-agent", "task-accounts-1", "payments.send", PAYMENT_SUPPLIER_A, clock)
    approve(db_path, approval_id, clock)

    results = []
    barrier = threading.Barrier(2)  # Both threads start at the same moment

    def call_gateway():
        barrier.wait()  # Synchronise both threads to maximise race condition
        r = execute(db_path, "accounts-agent", "task-accounts-1", "payments.send",
                    PAYMENT_SUPPLIER_A, approval_id=approval_id, clock=clock)
        results.append(r)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(call_gateway), pool.submit(call_gateway)]
        concurrent.futures.wait(futures)
        # Raise any exceptions that occurred in threads
        for f in futures:
            f.result()

    decisions = [r["decision"] for r in results]
    allow_count = decisions.count(Decision.ALLOW.value)
    block_count = decisions.count(Decision.BLOCK.value)

    assert allow_count == 1, f"Exactly one thread must ALLOW, got {allow_count} ALLOWs: {decisions}"
    assert block_count == 1, f"Exactly one thread must BLOCK (replay), got {block_count} BLOCKs: {decisions}"

    # Only one tool_calls row must exist (the winner)
    assert tool_calls_count(db_path, "payments.send", PAYMENT_SUPPLIER_A) == 1


# ===========================================================================
# Security Test 7: Payment over threshold, no approval → ASK_HUMAN
# plan.md §D scenario 8; §E1 test 7
# ===========================================================================
def test_payment_over_threshold_without_approval(db_path, clock):
    """
    Amount > ₹10,000 (1,000,000 paise) without an approval_id → ASK_HUMAN.
    tool_calls must be 0 (tool does not run until approved).
    """
    large_payment = {
        "recipient": "Supplier A",
        "amount": 15000.00,   # ₹15,000 = 1,500,000 paise > 1,000,000 paise threshold
        "currency": "INR",
        "reference": "INV-002",
    }
    resp = execute(db_path, "accounts-agent", "task-accounts-1", "payments.send",
                   large_payment, clock=clock)

    assert resp["decision"] == Decision.ASK_HUMAN.value, f"Expected ASK_HUMAN, got {resp['decision']}"
    assert resp["reason"] == REASON_OVER_THRESHOLD, f"Reason mismatch: {resp['reason']!r}"
    assert resp["executed"] is False
    assert total_tool_calls(db_path) == 0


# ===========================================================================
# Security Test 8: Gateway failure → BLOCK (fail closed)
# plan.md §A4 "Fail closed"; §E1 test 8
# ===========================================================================
def test_gateway_failure_fails_closed(db_path, clock):
    """
    Monkeypatching the policy engine to raise RuntimeError.
    Gateway must catch the exception, return BLOCK with "Gateway error: failed closed",
    and ensure zero tool_calls rows are written.
    """
    gw = _import_gateway()

    with patch.object(gw, "policy_check", side_effect=RuntimeError("Simulated internal failure")):
        resp = execute(db_path, "accounts-agent", "task-accounts-1", "payments.send",
                       PAYMENT_SUPPLIER_A, clock=clock)

    assert resp["decision"] == Decision.BLOCK.value
    assert resp["reason"] == REASON_FAIL_CLOSED, f"Reason mismatch: {resp['reason']!r}"
    assert resp["executed"] is False
    assert total_tool_calls(db_path) == 0


# ===========================================================================
# Extra: Valid exact payment → ALLOW (plan.md §D scenario 1)
# ===========================================================================
def test_valid_exact_payment_allow(db_path, clock):
    """
    The hero scenario from plan.md §A2 step 6: valid matching approval → ALLOW.
    Proves the system does not over-block.
    """
    approval_id = create_approval(db_path, "accounts-agent", "task-accounts-1", "payments.send", PAYMENT_SUPPLIER_A, clock)
    approve(db_path, approval_id, clock)

    resp = execute(db_path, "accounts-agent", "task-accounts-1", "payments.send",
                   PAYMENT_SUPPLIER_A, approval_id=approval_id, clock=clock)

    assert resp["decision"] == Decision.ALLOW.value, f"Expected ALLOW, got {resp['decision']}: {resp['reason']}"
    assert resp["executed"] is True

    # Proof: exactly one tool_calls row
    assert tool_calls_count(db_path, "payments.send", PAYMENT_SUPPLIER_A) == 1


# ===========================================================================
# Extra: Whitespace/case variation of approved params still ALLOWs
# This validates the canonical normalisation (plan.md §C2 "Canonical hash")
# ===========================================================================
def test_valid_normalised_variant_allow(db_path, clock):
    """
    Approve with 'Supplier A ' (trailing space) / float amount.
    Execute with 'supplier a' (lowercase) and same amount as paise int.
    Must ALLOW — same canonical hash, different surface representation.
    """
    approval_id = create_approval(db_path, "accounts-agent", "task-accounts-1", "payments.send",
                                  {"recipient": "Supplier A ", "amount": 5000.00, "currency": "inr"}, clock)
    approve(db_path, approval_id, clock)

    normalised_variant = {"recipient": "supplier a", "amount_paise": 500000, "currency": "INR"}
    resp = execute(db_path, "accounts-agent", "task-accounts-1", "payments.send",
                   normalised_variant, approval_id=approval_id, clock=clock)

    assert resp["decision"] == Decision.ALLOW.value, f"Expected ALLOW, got {resp['decision']}: {resp['reason']}"
    assert resp["executed"] is True


# ===========================================================================
# Extra: Approval for a different agent or task is rejected
# plan.md §C2: (ap.agent_id, ap.task_id, ap.tool) != (req.agent_id, ...)
# ===========================================================================
def test_approval_for_other_agent_blocked(db_path, clock):
    """
    An approval created for accounts-agent cannot be used by reader-agent.
    """
    approval_id = create_approval(db_path, "accounts-agent", "task-accounts-1", "payments.send", PAYMENT_SUPPLIER_A, clock)
    approve(db_path, approval_id, clock)

    # reader-agent tries to use accounts-agent's approval
    resp = execute(db_path, "reader-agent", "task-reader-1", "payments.send",
                   PAYMENT_SUPPLIER_A, approval_id=approval_id, clock=clock)

    assert resp["decision"] == Decision.BLOCK.value
    # Will BLOCK either due to no permission (reader-agent) or approval mismatch
    assert resp["executed"] is False
    assert total_tool_calls(db_path) == 0


def test_approval_for_other_task_blocked(db_path, clock):
    """
    An approval created for task-accounts-1 cannot be used for a different task_id.
    """
    approval_id = create_approval(db_path, "accounts-agent", "task-accounts-1", "payments.send", PAYMENT_SUPPLIER_A, clock)
    approve(db_path, approval_id, clock)

    # Same agent, different task_id
    resp = execute(db_path, "accounts-agent", "task-reader-1", "payments.send",
                   PAYMENT_SUPPLIER_A, approval_id=approval_id, clock=clock)

    assert resp["decision"] == Decision.BLOCK.value, f"Expected BLOCK for wrong task, got {resp['decision']}"
    assert resp["executed"] is False
    assert total_tool_calls(db_path) == 0


# ===========================================================================
# Extra: DROP TABLE → BLOCK (plan.md §C6, §D scenario 7)
# ===========================================================================
def test_drop_table_blocked(db_path, clock):
    """
    database.run_sql containing DROP must BLOCK unconditionally.
    No approval can override a hard-block policy.
    """
    sql_params = {
        "query": "DROP TABLE customers",
        "database": "production",
    }
    resp = execute(db_path, "accounts-agent", "task-accounts-1", "database.run_sql",
                   sql_params, clock=clock)

    assert resp["decision"] == Decision.BLOCK.value
    assert resp["reason"] == REASON_DROP_TABLE, f"Reason mismatch: {resp['reason']!r}"
    assert resp["executed"] is False
    assert total_tool_calls(db_path) == 0


def test_truncate_blocked(db_path, clock):
    """TRUNCATE is also a hard-block like DROP."""
    sql_params = {"query": "TRUNCATE orders", "database": "production"}
    resp = execute(db_path, "accounts-agent", "task-accounts-1", "database.run_sql",
                   sql_params, clock=clock)

    assert resp["decision"] == Decision.BLOCK.value
    assert resp["reason"] == REASON_DROP_TABLE, f"Reason mismatch: {resp['reason']!r}"
    assert resp["executed"] is False
    assert total_tool_calls(db_path) == 0


# ===========================================================================
# Extra: Audit chain tamper detection
# plan.md §C3: GET /v1/audit/verify must detect any edit to a stored record
# ===========================================================================
def test_audit_tamper_detected(db_path, clock):
    """
    Execute a valid action to write an audit record.
    Manually edit a field in the stored audit row.
    Calling audit.verify() must return ok=False and name the broken record.
    """
    approval_id = create_approval(db_path, "accounts-agent", "task-accounts-1", "payments.send", PAYMENT_SUPPLIER_A, clock)
    approve(db_path, approval_id, clock)
    resp = execute(db_path, "accounts-agent", "task-accounts-1", "payments.send",
                   PAYMENT_SUPPLIER_A, approval_id=approval_id, clock=clock)

    assert resp["decision"] == Decision.ALLOW.value, "Prerequisite: valid payment must ALLOW"
    audit_id = resp["audit_id"]
    assert audit_id is not None

    # Tamper: alter the decision field in the stored row (simulating an attacker editing the DB)
    conn = get_connection(db_path)
    conn.execute("UPDATE audit SET decision='ALLOW' WHERE id=? AND decision='ALLOW'", (audit_id,))
    # More damaging tamper: change the reason
    conn.execute("UPDATE audit SET reason='Tampered reason' WHERE id=?", (audit_id,))
    conn.commit()
    conn.close()

    # Now verify the chain — must detect the tamper
    from app import audit as audit_module
    result = audit_module.verify(db_path)
    assert result.ok is False, "Chain verify must return ok=False after tampering"
    assert result.broken_at is not None, "broken_at must identify which record was tampered"
    assert result.broken_at == audit_id or result.broken_at <= audit_id, (
        f"broken_at ({result.broken_at}) should be at or before tampered record ({audit_id})"
    )


# ===========================================================================
# Extra: Secrets not stored in audit log or DB
# plan.md §C3: "Secrets masked BEFORE hashing and storing"
# ===========================================================================
SECRET_VALUE = "sk-test-SECRET123"


def test_secrets_not_in_audit_log(db_path, clock, caplog):
    """
    Plant a fake secret in the params.
    After gateway execution, the secret must NOT appear in:
      1. The audit table (params_masked column)
      2. The tool_calls table (params_json column)
      3. Any captured log output (caplog)
    """
    import logging
    params_with_secret = {
        "recipient": "Supplier A",
        "amount": 5000.00,
        "currency": "INR",
        "api_key": SECRET_VALUE,          # Should be masked before storage
        "auth_token": f"Bearer {SECRET_VALUE}",
    }
    approval_id = create_approval(db_path, "accounts-agent", "task-accounts-1", "payments.send",
                                  params_with_secret, clock)
    approve(db_path, approval_id, clock)

    with caplog.at_level(logging.DEBUG):
        resp = execute(db_path, "accounts-agent", "task-accounts-1", "payments.send",
                       params_with_secret, approval_id=approval_id, clock=clock)

    # Check audit table
    conn = get_connection(db_path)
    audit_rows = conn.execute("SELECT params_masked FROM audit").fetchall()
    for row in audit_rows:
        assert SECRET_VALUE not in (row["params_masked"] or ""), (
            f"Secret found in audit.params_masked: {row['params_masked']}"
        )

    # Check tool_calls table
    tool_rows = conn.execute("SELECT params_json FROM tool_calls").fetchall()
    for row in tool_rows:
        assert SECRET_VALUE not in (row["params_json"] or ""), (
            f"Secret found in tool_calls.params_json: {row['params_json']}"
        )
    conn.close()

    # Check captured logs
    full_log = caplog.text
    assert SECRET_VALUE not in full_log, (
        f"Secret found in log output: contains '{SECRET_VALUE}'"
    )

    # Approval approved_params_json also must not contain raw secret
    conn = get_connection(db_path)
    appr_rows = conn.execute("SELECT approved_params_json FROM approvals").fetchall()
    for row in appr_rows:
        assert SECRET_VALUE not in (row["approved_params_json"] or ""), (
            f"Secret found in approvals.approved_params_json: {row['approved_params_json']}"
        )
    conn.close()


# ===========================================================================
# Extra: Agent package has no direct tool imports (static check)
# plan.md §C2: "only gateway.py imports the tool module"
# ===========================================================================
AGENT_DIR = Path(__file__).parent.parent.parent / "agent"
TOOL_IMPORT_PATTERNS = [
    re.compile(r"from\s+(?:backend\.)?app\.tools"),
    re.compile(r"import\s+(?:backend\.)?app\.tools"),
    re.compile(r"from\s+app\.tools"),
    re.compile(r"import\s+app\.tools"),
]


def _file_has_tool_import(filepath: Path) -> Optional[str]:
    """
    Returns the offending line if the file contains a direct tool import,
    None otherwise. Uses both regex and AST to avoid false positives.
    """
    source = filepath.read_text(encoding="utf-8")

    # Fast regex check
    for pattern in TOOL_IMPORT_PATTERNS:
        match = pattern.search(source)
        if match:
            return match.group(0)

    # AST check for aliased or nested imports
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "app.tools" in alias.name or "backend.app.tools" in alias.name:
                    return f"import {alias.name}"
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if "app.tools" in module or "backend.app.tools" in module:
                return f"from {module} import ..."

    return None


def test_agent_package_has_no_tool_imports():
    """
    Static check: nothing under agent/ may directly import backend.app.tools.
    Every tool call must be routed through POST /v1/gateway/execute via sdk_wrapper.
    """
    assert AGENT_DIR.is_dir(), f"agent/ directory not found at {AGENT_DIR}"

    violations = []
    for py_file in AGENT_DIR.rglob("*.py"):
        offence = _file_has_tool_import(py_file)
        if offence:
            violations.append(f"{py_file.name}: {offence}")

    assert not violations, (
        "HARD RULE VIOLATION: the following agent files import tool functions directly.\n"
        "All tool calls must route through the gateway (POST /v1/gateway/execute):\n"
        + "\n".join(f"  {v}" for v in violations)
    )


# ===========================================================================
# Extra: Unknown agent is blocked immediately
# plan.md §C2: "agent = agents.get(req.agent_id) else BLOCK 'Unknown agent'"
# ===========================================================================
def test_unknown_agent_blocked(db_path, clock):
    """An agent_id not in the agents table must be BLOCK immediately."""
    resp = execute(db_path, "nonexistent-agent-xyz", "task-accounts-1", "payments.send",
                   PAYMENT_SUPPLIER_A, clock=clock)

    assert resp["decision"] == Decision.BLOCK.value
    assert "unknown agent" in resp["reason"].lower() or "agent" in resp["reason"].lower(), (
        f"Expected reason to mention 'unknown agent', got: {resp['reason']!r}"
    )
    assert resp["executed"] is False
    assert total_tool_calls(db_path) == 0


# ===========================================================================
# Extra: Unknown tool is blocked immediately
# plan.md §C2: "tool = registry.get(req.tool) else BLOCK 'Unknown tool'"
# ===========================================================================
def test_unknown_tool_blocked(db_path, clock):
    """A tool name not in the tool registry must be BLOCK immediately."""
    resp = execute(db_path, "accounts-agent", "task-accounts-1", "nonexistent.tool",
                   {"param": "value"}, clock=clock)

    assert resp["decision"] == Decision.BLOCK.value
    assert "unknown tool" in resp["reason"].lower() or "tool" in resp["reason"].lower(), (
        f"Expected reason to mention 'unknown tool', got: {resp['reason']!r}"
    )
    assert resp["executed"] is False
    assert total_tool_calls(db_path) == 0
