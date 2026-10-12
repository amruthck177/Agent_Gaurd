"""
backend/tests/test_secrets_leak.py

Security tests for R2 + R4: Secrets prevention in responses, logs, and audit records.
Verifies that:
- When an unhandled exception occurs with planted secrets ("x_api_key": "sk-real-TEST123"),
  a clean 500 JSON is returned with decision=BLOCK, reason='Gateway error: failed closed',
  and a unique error_id UUID.
- No exception text or traceback appears in the response body.
- No secret appears in logs (enforced via handler structure and logging filter).
- No secret appears in audit records (masked before storage and hashing).
"""

import logging
import uuid
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.db import get_connection, reset_db, seed_demo
from app.main import app, get_db_path


@pytest.fixture
def clean_db(tmp_path):
    db_file = str(tmp_path / "test_secrets_leak.db")
    reset_db(db_file)
    seed_demo(db_file)
    return db_file


@pytest.mark.asyncio
async def test_unhandled_exception_does_not_leak_secret(clean_db, caplog, monkeypatch):
    """
    Planted secret in exception and request params must not leak into 500 response body
    or log output when an unhandled server error occurs.
    """
    monkeypatch.setenv("AGENTGUARD_DB_PATH", clean_db)
    secret_key = "sk-real-TEST123"

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Patch gateway.execute to simulate an unhandled exception containing the secret
        with caplog.at_level(logging.DEBUG):
            with patch("app.main.gateway.execute", side_effect=RuntimeError(f"Database crash with secret {secret_key}")):
                resp = await client.post(
                    "/v1/gateway/execute",
                    json={
                        "agent_id": "accounts-agent",
                        "task_id": "task-accounts-1",
                        "tool": "payments.send",
                        "params": {
                            "recipient": "Supplier A",
                            "amount": 5000,
                            "currency": "INR",
                            "x_api_key": secret_key,
                        },
                    },
                )

    # 1. HTTP 500 returned
    assert resp.status_code == 500

    body = resp.json()
    resp_text = resp.text

    # 2. Response body must have clean structure with error_id
    assert body.get("decision") == "BLOCK"
    assert body.get("reason") == "Gateway error: failed closed"
    assert "error_id" in body
    # error_id must be a valid UUID
    uuid_obj = uuid.UUID(body["error_id"])
    assert str(uuid_obj) == body["error_id"]

    # 3. Secret MUST NOT appear in response body
    assert secret_key not in resp_text
    assert "Database crash" not in resp_text

    # 4. Secret MUST NOT appear in log output
    assert secret_key not in caplog.text


@pytest.mark.asyncio
async def test_gateway_error_and_audit_do_not_leak_secret(clean_db, caplog, monkeypatch):
    """
    Normal execution with planted secret must not leak secret into audit database,
    logs, or gateway response.
    """
    monkeypatch.setenv("AGENTGUARD_DB_PATH", clean_db)
    secret_key = "sk-real-TEST123"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with caplog.at_level(logging.DEBUG):
            resp = await client.post(
                "/v1/gateway/execute",
                json={
                    "agent_id": "accounts-agent",
                    "task_id": "task-accounts-1",
                    "tool": "payments.send",
                    "params": {
                        "recipient": "Supplier A",
                        "amount": 5000,
                        "currency": "INR",
                        "x_api_key": secret_key,
                    },
                },
            )

    resp_text = resp.text

    # 1. Secret MUST NOT appear in response
    assert secret_key not in resp_text

    # 2. Secret MUST NOT appear in log output
    assert secret_key not in caplog.text

    # 3. Secret MUST NOT appear in audit table
    conn = get_connection(clean_db)
    try:
        cur = conn.cursor()
        rows = cur.execute("SELECT * FROM audit").fetchall()
        for r in rows:
            row_dict = dict(r)
            for k, v in row_dict.items():
                val_str = str(v)
                assert secret_key not in val_str, f"Secret leaked in audit column {k}: {val_str}"
    finally:
        conn.close()
