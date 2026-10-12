"""
backend/tests/test_agent.py

Unit and integration tests for:
  - agent/sdk_wrapper.py (AgentGuardClient fail-closed enforcement, timeouts, error handling)
  - agent/scripted_agent.py (Deterministic scenarios 1-10 + CLI runner)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

_ROOT_DIR = str(Path(__file__).resolve().parent.parent.parent)
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from app.db import reset_db, seed_demo
from app.main import app
from agent.sdk_wrapper import AgentGuardClient
from agent.scripted_agent import (
    run_all,
    run_scenario,
    scenario_valid_exact_payment,
    scenario_changed_recipient,
    scenario_changed_amount,
    scenario_expired_approval,
    scenario_revoked_approval,
    scenario_read_only_agent_write,
    scenario_drop_table,
    scenario_over_threshold,
    scenario_replay,
    scenario_gateway_down,
)


@pytest.fixture()
def client_fixture(tmp_path, monkeypatch):
    """Provides an isolated database and TestClient for AgentGuardClient."""
    test_db = str(tmp_path / "test_agent_suite.db")
    reset_db(test_db)
    seed_demo(test_db)
    monkeypatch.setenv("AGENTGUARD_DB_PATH", test_db)
    monkeypatch.setenv("DEMO_MODE", "1")

    with TestClient(app) as tc:
        yield AgentGuardClient(client=tc)


# ===========================================================================
# 1. AgentGuardClient SDK Wrapper Fail-Closed Tests
# ===========================================================================
def test_sdk_wrapper_success(client_fixture):
    """When gateway permits an action, returns parsed response with ALLOW."""
    # Create and approve payment
    ap = client_fixture.create_approval("payments.send", {"recipient": "Supplier A", "amount": 5000})
    client_fixture.approve(ap["id"])

    res = client_fixture.execute("payments.send", {"recipient": "Supplier A", "amount": 5000}, approval_id=ap["id"])
    assert res["decision"] == "ALLOW"
    assert res["executed"] is True
    assert res["audit_id"] is not None


def test_sdk_wrapper_fails_closed_on_network_error():
    """Any network/connection error must return BLOCK (fail closed)."""
    # Connect to unreachable port
    dead_client = AgentGuardClient(base_url="http://127.0.0.1:59998", timeout=0.5)
    try:
        res = dead_client.execute("payments.send", {"recipient": "Supplier A", "amount": 5000})
        assert res["decision"] == "BLOCK"
        assert res["executed"] is False
        assert "Gateway error: failed closed" in res["reason"]
    finally:
        dead_client.close()


def test_sdk_wrapper_fails_closed_on_500_status():
    """Any non-200 HTTP response must return BLOCK (fail closed)."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 502
    mock_resp.text = "Bad Gateway"
    mock_client.post.return_value = mock_resp

    client = AgentGuardClient(client=mock_client)
    res = client.execute("payments.send", {"recipient": "Supplier A", "amount": 5000})

    assert res["decision"] == "BLOCK"
    assert res["executed"] is False
    assert "Gateway error: failed closed" in res["reason"]
    assert res["status_code"] == 502


def test_sdk_wrapper_fails_closed_on_timeout():
    """A request timeout must return BLOCK (fail closed)."""
    import httpx
    mock_client = MagicMock()
    mock_client.post.side_effect = httpx.TimeoutException("Read timed out")

    client = AgentGuardClient(client=mock_client)
    res = client.execute("payments.send", {"recipient": "Supplier A", "amount": 5000})

    assert res["decision"] == "BLOCK"
    assert res["executed"] is False
    assert "Gateway error: failed closed" in res["reason"]


def test_sdk_wrapper_has_no_tool_code():
    """Verify sdk_wrapper contains zero tool implementations or sensitive logic."""
    import inspect
    import agent.sdk_wrapper as sdk_mod

    source = inspect.getsource(sdk_mod)
    assert "payments.send(" not in source
    assert "sqlite3.connect" not in source
    assert "def run_sql" not in source
    assert "def send_email" not in source


# ===========================================================================
# 2. Scripted Agent Deterministic Scenarios Tests
# ===========================================================================
def test_scenario_1_valid_exact_payment(client_fixture):
    res = scenario_valid_exact_payment(client_fixture)
    assert res["passed"] is True
    assert res["decision"] == "ALLOW"
    assert res["tool_calls_count"] == 1


def test_scenario_2_changed_recipient(client_fixture):
    res = scenario_changed_recipient(client_fixture)
    assert res["passed"] is True
    assert res["decision"] == "BLOCK"
    assert res["tool_calls_count"] == 0
    assert "Recipient changed after approval" in res["reason"]


def test_scenario_3_changed_amount(client_fixture):
    res = scenario_changed_amount(client_fixture)
    assert res["passed"] is True
    assert res["decision"] == "BLOCK"
    assert res["tool_calls_count"] == 0
    assert "Amount changed after approval" in res["reason"]


def test_scenario_4_expired_approval(client_fixture):
    res = scenario_expired_approval(client_fixture)
    assert res["passed"] is True
    assert res["decision"] == "BLOCK"
    assert res["tool_calls_count"] == 0
    assert "Approval expired" in res["reason"]


def test_scenario_5_revoked_approval(client_fixture):
    res = scenario_revoked_approval(client_fixture)
    assert res["passed"] is True
    assert res["decision"] == "BLOCK"
    assert res["tool_calls_count"] == 0
    assert "Approval revoked" in res["reason"]


def test_scenario_6_read_only_agent_write(client_fixture):
    res = scenario_read_only_agent_write(client_fixture)
    assert res["passed"] is True
    assert res["decision"] == "BLOCK"
    assert res["tool_calls_count"] == 0
    assert "Agent lacks write permission" in res["reason"]


def test_scenario_7_drop_table(client_fixture):
    res = scenario_drop_table(client_fixture)
    assert res["passed"] is True
    assert res["decision"] == "BLOCK"
    assert res["tool_calls_count"] == 0
    assert "Destructive database operation prohibited" in res["reason"]


def test_scenario_8_over_threshold(client_fixture):
    res = scenario_over_threshold(client_fixture)
    assert res["passed"] is True
    assert res["decision"] == "ASK_HUMAN"
    assert res["tool_calls_count"] == 0
    assert "Payment exceeds ₹10,000 limit" in res["reason"]


def test_scenario_9_replay(client_fixture):
    res = scenario_replay(client_fixture)
    assert res["passed"] is True
    assert res["decision"] == "BLOCK"
    assert res["tool_calls_count"] == 0
    assert "Approval already used (replay)" in res["reason"]


def test_scenario_10_gateway_down():
    res = scenario_gateway_down()
    assert res["passed"] is True
    assert res["decision"] == "BLOCK"
    assert res["tool_calls_count"] == 0
    assert "Gateway error: failed closed" in res["reason"]


def test_run_all_and_run_scenario(client_fixture):
    """Test the batch runner and single runner."""
    single = run_scenario("changed_recipient", client_fixture)
    assert single["passed"] is True
    assert single["scenario"] == "changed_recipient"

    all_res = run_all(client_fixture)
    assert len(all_res) == 10
    assert all(r["passed"] for r in all_res)
