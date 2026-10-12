"""
backend/tests/test_audit.py

Comprehensive tests for backend/app/audit.py:
  - append(record) -> returns row ID
  - Genesis prev_hash is 64 zeros
  - Canonical JSON and SHA-256 hash chaining
  - Secret masking (sk-..., api keys, bearer tokens, account numbers keeping last 4)
  - verify() -> {ok, checked, broken_at}
  - tamper(record_id) demo function
  - list(filters) query filtering
  - export_csv() output formatting
  - Multi-threaded serialized appends maintaining an unbroken hash chain
"""

import concurrent.futures
import csv
import io
import pytest

from app import audit
from app.db import reset_db, seed_demo
from app.schemas import Decision


@pytest.fixture()
def db_path(tmp_path):
    path = str(tmp_path / "test_audit_chain.db")
    reset_db(path)
    seed_demo(path)
    return path


def test_genesis_hash_and_append(db_path):
    # Empty audit table
    v0 = audit.verify(db_path)
    assert v0.ok is True
    assert v0.checked == 0
    assert v0.broken_at is None

    # First append (genesis)
    row_id1 = audit.append({
        "ts": "2026-10-12T10:00:00Z",
        "agent_id": "accounts-agent",
        "task_id": "task-accounts-1",
        "tool": "payments.send",
        "params": {"recipient": "Supplier A", "amount": 5000},
        "decision": "ALLOW",
        "reason": "Valid request",
        "approval_id": None,
        "executed": True,
    }, db_path=db_path)

    assert row_id1 == 1

    records = audit.list(db_path=db_path)
    assert len(records) == 1
    rec1 = records[0]
    assert rec1["prev_hash"] == audit.GENESIS_HASH
    assert len(rec1["hash"]) == 64

    # Second append (links to first row's hash)
    row_id2 = audit.append({
        "ts": "2026-10-12T10:01:00Z",
        "agent_id": "accounts-agent",
        "task_id": "task-accounts-1",
        "tool": "email.send",
        "params": {"to": "vendor@company.com", "subject": "Hello"},
        "decision": "ALLOW",
        "reason": "Approved",
        "approval_id": None,
        "executed": True,
    }, db_path=db_path)

    assert row_id2 == 2

    records2 = audit.list(db_path=db_path, order="ASC")
    assert len(records2) == 2
    assert records2[1]["prev_hash"] == records2[0]["hash"]

    # Chain verifies clean
    v = audit.verify(db_path)
    assert v.ok is True
    assert v.checked == 2
    assert v.broken_at is None


def test_mask_secrets_before_hashing(db_path):
    secret_key = "sk-live-SECRET99999"
    bearer_tok = "Bearer secret_access_token_xyz"
    raw_acc = "12345678901234"  # 14 digits -> keep last 4: **********1234

    row_id = audit.append({
        "ts": "2026-10-12T10:02:00Z",
        "agent_id": "accounts-agent",
        "task_id": "task-accounts-1",
        "tool": "payments.send",
        "params": {
            "api_key": secret_key,
            "custom_header": bearer_tok,
            "account_number": raw_acc,
            "note": f"Transfer to account {raw_acc} with key {secret_key}",
        },
        "decision": "BLOCK",
        "reason": "Unauthorized secret detected",
        "approval_id": None,
        "executed": False,
    }, db_path=db_path)

    records = audit.list(db_path=db_path)
    rec = next(r for r in records if r["id"] == row_id)
    masked_json = rec["params_masked"]

    # Secrets MUST NOT appear
    assert secret_key not in masked_json
    assert bearer_tok not in masked_json
    assert raw_acc not in masked_json

    # Masked forms MUST appear
    assert "[MASKED]" in masked_json
    assert "Bearer [MASKED]" in masked_json
    assert "**********1234" in masked_json

    # Chain verification succeeds because mask was applied BEFORE hashing
    v = audit.verify(db_path)
    assert v.ok is True


def test_tamper_detection(db_path):
    row_id1 = audit.append({
        "agent_id": "accounts-agent",
        "task_id": "task-accounts-1",
        "tool": "payments.send",
        "params": {"amount": 5000},
        "decision": "ALLOW",
        "reason": "OK",
    }, db_path=db_path)

    row_id2 = audit.append({
        "agent_id": "accounts-agent",
        "task_id": "task-accounts-1",
        "tool": "payments.send",
        "params": {"amount": 10000},
        "decision": "ALLOW",
        "reason": "OK 2",
    }, db_path=db_path)

    # Initial verification passes
    v_init = audit.verify(db_path)
    assert v_init.ok is True

    # Tamper with row 1
    tampered = audit.tamper(row_id1, db_path=db_path)
    assert tampered is True

    # Verify must immediately catch the tamper and point to row 1
    v_tampered = audit.verify(db_path)
    assert v_tampered.ok is False
    assert v_tampered.broken_at == row_id1


def test_concurrent_appends_serialized(db_path):
    """
    Spawns 10 concurrent threads appending records.
    The internal lock + BEGIN IMMEDIATE must guarantee an unbroken chain.
    """
    total_records = 20

    def append_worker(idx):
        return audit.append({
            "agent_id": "accounts-agent",
            "task_id": "task-accounts-1",
            "tool": "payments.send",
            "params": {"worker": idx, "amount": 1000 * idx},
            "decision": "ALLOW",
            "reason": f"Worker {idx} run",
            "executed": True,
        }, db_path=db_path)

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(append_worker, i) for i in range(total_records)]
        ids = [f.result() for f in futures]

    assert len(ids) == total_records
    assert len(set(ids)) == total_records  # Unique row IDs

    # Entire chain must verify 100% valid with all records checked
    v = audit.verify(db_path)
    assert v.ok is True
    assert v.checked == total_records
    assert v.broken_at is None


def test_audit_list_filters(db_path):
    audit.append({
        "agent_id": "accounts-agent",
        "task_id": "task-accounts-1",
        "tool": "payments.send",
        "params": {},
        "decision": "ALLOW",
        "reason": "All good",
        "executed": True,
    }, db_path=db_path)

    audit.append({
        "agent_id": "reader-agent",
        "task_id": "task-reader-1",
        "tool": "database.run_sql",
        "params": {},
        "decision": "BLOCK",
        "reason": "Unauthorized read attempt",
        "executed": False,
    }, db_path=db_path)

    # Filter by agent
    by_agent = audit.list({"agent_id": "reader-agent"}, db_path=db_path)
    assert len(by_agent) == 1
    assert by_agent[0]["agent_id"] == "reader-agent"

    # Filter by decision
    by_decision = audit.list({"decision": "BLOCK"}, db_path=db_path)
    assert len(by_decision) == 1
    assert by_decision[0]["decision"] == "BLOCK"

    # Filter by execution
    by_exec = audit.list({"executed": True}, db_path=db_path)
    assert len(by_exec) == 1
    assert by_exec[0]["executed"] == 1


def test_export_csv(db_path):
    audit.append({
        "ts": "2026-10-12T12:00:00Z",
        "agent_id": "accounts-agent",
        "task_id": "task-accounts-1",
        "tool": "payments.send",
        "params": {"recipient": "Supplier A", "amount": 5000},
        "decision": "ALLOW",
        "reason": "Approved payment",
        "approval_id": "appr-123",
        "executed": True,
    }, db_path=db_path)

    csv_text = audit.export_csv(db_path=db_path)
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)

    assert len(rows) >= 2  # Header + at least 1 record
    header = rows[0]
    assert "id" in header
    assert "prev_hash" in header
    assert "hash" in header
    assert "params_masked" in header

    data_row = rows[1]
    assert "accounts-agent" in data_row
    assert "payments.send" in data_row
    assert "ALLOW" in data_row
