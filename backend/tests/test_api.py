"""
backend/tests/test_api.py

API integration tests using httpx / TestClient for AgentGuard 2.0.
Verifies plan.md §C5 endpoints:
  - Hero story: Create approval for Supplier A ₹5,000, approve it,
    attempt execution with Supplier B -> 200 BLOCK, tool_calls count 0, audit record exists,
    then execute with Supplier A -> 200 ALLOW, tool_calls count 1.
  - Validation: Bad input returns 422, never a stack trace.
  - Approvals: create, list, approve, reject, revoke.
  - Policies: GET and PUT.
  - Audit: GET, CSV export, and /v1/audit/verify.
  - Demo: /v1/demo/reset and /v1/demo/tamper (DEMO_MODE=1 vs 0).
  - Benchmarks: /v1/tests/results returns {"available": False} when missing.
  - CORS and WebSocket /ws/events.
"""

import os
import pytest
from fastapi.testclient import TestClient

from app.db import reset_db, seed_demo
from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Provides a TestClient connected to an isolated test SQLite database."""
    test_db = str(tmp_path / "test_api_guard.db")
    reset_db(test_db)
    seed_demo(test_db)
    monkeypatch.setenv("AGENTGUARD_DB_PATH", test_db)
    monkeypatch.setenv("DEMO_MODE", "1")

    with TestClient(app) as test_client:
        yield test_client


# ===========================================================================
# The Hero Demo Story: Supplier A -> Supplier B (plan.md §A2, §D scenario 2)
# ===========================================================================
def test_supplier_a_to_supplier_b_story(client):
    """
    1. Human approves: "pay Supplier A ₹5,000".
    2. Agent attempts: pay Supplier B ₹5,000 using that approval.
    3. AgentGuard returns: BLOCK "Recipient changed after approval".
    4. tool_calls count is 0.
    5. Audit log records the blocked attempt.
    6. Agent executes unchanged approved payment to Supplier A.
    7. AgentGuard returns: ALLOW.
    8. tool_calls count is 1.
    """
    payment_params_a = {
        "recipient": "Supplier A",
        "amount": 5000.00,
        "currency": "INR",
        "reference": "INV-101",
    }

    # Step 1: Create approval for Supplier A ₹5,000
    create_resp = client.post("/v1/approvals", json={
        "agent_id": "accounts-agent",
        "task_id": "task-accounts-1",
        "tool": "payments.send",
        "params": payment_params_a,
    })
    assert create_resp.status_code == 201
    approval = create_resp.json()
    approval_id = approval["id"]
    assert approval["status"] == "pending"

    # Step 2: Human approves it
    approve_resp = client.post(f"/v1/approvals/{approval_id}/approve")
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"

    # Step 3: Agent tries to pay Supplier B using Supplier A's approval
    payment_params_b = {
        "recipient": "Supplier B",
        "amount": 5000.00,
        "currency": "INR",
        "reference": "INV-101",
    }
    exec_b_resp = client.post("/v1/gateway/execute", json={
        "agent_id": "accounts-agent",
        "task_id": "task-accounts-1",
        "tool": "payments.send",
        "params": payment_params_b,
        "approval_id": approval_id,
    })
    assert exec_b_resp.status_code == 200
    b_data = exec_b_resp.json()
    assert b_data["decision"] == "BLOCK"
    assert b_data["reason"] == "Recipient changed after approval"
    assert b_data["executed"] is False

    # Step 4: Verify tool_calls count is 0 (tool never executed)
    tool_calls_resp = client.get("/v1/tool_calls")
    assert tool_calls_resp.status_code == 200
    assert tool_calls_resp.json()["count"] == 0

    # Step 5: Audit log contains the BLOCK record
    audit_resp = client.get("/v1/audit")
    assert audit_resp.status_code == 200
    audit_records = audit_resp.json()
    assert len(audit_records) >= 1
    block_rec = next(r for r in audit_records if r["id"] == b_data["audit_id"])
    assert block_rec["decision"] == "BLOCK"
    assert block_rec["reason"] == "Recipient changed after approval"
    assert block_rec["executed"] == 0

    # Step 6: Valid execution with Supplier A succeeds
    exec_a_resp = client.post("/v1/gateway/execute", json={
        "agent_id": "accounts-agent",
        "task_id": "task-accounts-1",
        "tool": "payments.send",
        "params": payment_params_a,
        "approval_id": approval_id,
    })
    assert exec_a_resp.status_code == 200
    a_data = exec_a_resp.json()
    assert a_data["decision"] == "ALLOW"
    assert a_data["executed"] is True

    # Step 7: Proof - tool_calls count is now exactly 1
    tool_calls_after = client.get("/v1/tool_calls")
    assert tool_calls_after.status_code == 200
    assert tool_calls_after.json()["count"] == 1


# ===========================================================================
# Validation Error (422) Tests: No Stack Traces
# ===========================================================================
def test_validation_bad_input_returns_422(client):
    # Missing required fields
    resp = client.post("/v1/gateway/execute", json={"invalid": "payload"})
    assert resp.status_code == 422
    body = resp.json()
    assert "detail" in body
    # Must never leak a Python traceback or internal path
    assert "Traceback" not in str(body)

    # Empty approval create
    resp_appr = client.post("/v1/approvals", json={})
    assert resp_appr.status_code == 422
    assert "detail" in resp_appr.json()


# ===========================================================================
# Approvals Lifecycle: Reject & Revoke
# ===========================================================================
def test_approvals_reject_and_revoke(client):
    # Create approval
    c_resp = client.post("/v1/approvals", json={
        "agent_id": "accounts-agent",
        "task_id": "task-accounts-1",
        "tool": "payments.send",
        "params": {"recipient": "Supplier A", "amount": 1000},
    })
    ap_id = c_resp.json()["id"]

    # Reject
    rej_resp = client.post(f"/v1/approvals/{ap_id}/reject")
    assert rej_resp.status_code == 200
    assert rej_resp.json()["status"] == "rejected"

    # Listing by status
    list_rej = client.get("/v1/approvals?status=rejected")
    assert list_rej.status_code == 200
    assert any(a["id"] == ap_id for a in list_rej.json())

    # Create another and revoke
    c_resp2 = client.post("/v1/approvals", json={
        "agent_id": "accounts-agent",
        "task_id": "task-accounts-1",
        "tool": "payments.send",
        "params": {"recipient": "Supplier A", "amount": 2000},
    })
    ap_id2 = c_resp2.json()["id"]
    client.post(f"/v1/approvals/{ap_id2}/approve")
    rev_resp = client.post(f"/v1/approvals/{ap_id2}/revoke")
    assert rev_resp.status_code == 200
    assert rev_resp.json()["status"] == "revoked"


# ===========================================================================
# Policies Management: GET & PUT
# ===========================================================================
def test_policies_endpoints(client):
    # GET policies
    get_resp = client.get("/v1/policies")
    assert get_resp.status_code == 200
    policies = get_resp.json()
    assert len(policies) >= 4

    # PUT a new policy
    new_pol = {
        "tool": "database.run_sql",
        "condition_json": '{"disallow": "ALTER TABLE"}',
        "decision": "BLOCK",
        "active": True,
    }
    put_resp = client.put("/v1/policies", json=new_pol)
    assert put_resp.status_code == 200
    created_pol = put_resp.json()
    assert created_pol["tool"] == "database.run_sql"
    assert created_pol["decision"] == "BLOCK"
    assert created_pol["id"] is not None


# ===========================================================================
# Audit Log, CSV Export & Verification
# ===========================================================================
def test_audit_endpoints(client):
    # Run a quick ALLOW call to create an audit record
    client.post("/v1/gateway/execute", json={
        "agent_id": "accounts-agent",
        "task_id": "task-accounts-1",
        "tool": "email.send",
        "params": {"to": "team@company.com", "subject": "Test"},
    })

    # GET audit records
    aud_resp = client.get("/v1/audit")
    assert aud_resp.status_code == 200
    records = aud_resp.json()
    assert len(records) >= 1

    # GET audit as CSV
    csv_resp = client.get("/v1/audit?format=csv")
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["content-type"]
    assert "prev_hash" in csv_resp.text

    # GET audit/verify
    v_resp = client.get("/v1/audit/verify")
    assert v_resp.status_code == 200
    assert v_resp.json()["ok"] is True
    assert v_resp.json()["checked"] >= 1


# ===========================================================================
# Demo Endpoints: Reset & Tamper
# ===========================================================================
def test_demo_reset_and_tamper(client, monkeypatch):
    # Create an audit record
    client.post("/v1/gateway/execute", json={
        "agent_id": "accounts-agent",
        "task_id": "task-accounts-1",
        "tool": "email.send",
        "params": {"to": "team@company.com", "subject": "Demo"},
    })

    # Tamper with latest record
    tamper_resp = client.post("/v1/demo/tamper")
    assert tamper_resp.status_code == 200
    assert tamper_resp.json()["status"] == "tampered"

    # Verify fails after tamper
    v_tampered = client.get("/v1/audit/verify")
    assert v_tampered.status_code == 200
    assert v_tampered.json()["ok"] is False

    # Reset demo
    reset_resp = client.post("/v1/demo/reset")
    assert reset_resp.status_code == 200
    assert reset_resp.json()["status"] == "ok"

    # Verify passes after reset
    v_clean = client.get("/v1/audit/verify")
    assert v_clean.json()["ok"] is True

    # When DEMO_MODE != 1, demo endpoints are 403 Forbidden
    monkeypatch.setenv("DEMO_MODE", "0")
    resp_forbidden = client.post("/v1/demo/reset")
    assert resp_forbidden.status_code == 403


# ===========================================================================
# Benchmarks / Tests Results Endpoint
# ===========================================================================
def test_benchmark_results_endpoint(client):
    from pathlib import Path
    bench_file = Path(__file__).resolve().parent.parent.parent / "benchmarks" / "results.json"
    resp = client.get("/v1/tests/results")
    assert resp.status_code == 200
    data = resp.json()
    if bench_file.is_file():
        assert data.get("available") is True
    else:
        assert data == {"available": False}


# ===========================================================================
# WebSocket /ws/events Feed
# ===========================================================================
def test_websocket_events(client):
    with client.websocket_connect("/ws/events") as ws:
        ws.send_text("ping")
        data = ws.receive_text()
        assert data == "pong"
