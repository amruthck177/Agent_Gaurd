"""
agent/scripted_agent.py

Deterministic scripted agent for demonstration and benchmark execution (plan.md Part D).
Runs completely without external LLM dependencies, submitting predefined actions
through sdk_wrapper.py to test AgentGuard enforcement.

Scenarios implemented:
  1. valid_exact_payment       (plan.md §D scenario 1: ALLOW)
  2. changed_recipient         (plan.md §D scenario 2: BLOCK "Recipient changed after approval")
  3. changed_amount            (plan.md §D scenario 3: BLOCK "Amount changed after approval")
  4. expired_approval          (plan.md §D scenario 4: BLOCK "Approval expired")
  5. revoked_approval          (plan.md §D scenario 5: BLOCK "Approval revoked")
  6. read_only_agent_write     (plan.md §D scenario 6: BLOCK "Agent lacks write permission")
  7. drop_table                (plan.md §D scenario 7: BLOCK "Destructive database operation prohibited")
  8. over_threshold            (plan.md §D scenario 8: ASK_HUMAN "Payment exceeds ₹10,000 limit: human approval required")
  9. replay                    (BLOCK "Approval already used (replay)")
 10. gateway_down              (BLOCK "Gateway error: failed closed")

CLI usage:
  python -m agent.scripted_agent run all
  python -m agent.scripted_agent run <scenario_number_or_name>
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

# Ensure backend directory is in sys.path for offline ASGI execution
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if _BACKEND_DIR not in sys.path and os.path.isdir(_BACKEND_DIR):
    sys.path.insert(0, _BACKEND_DIR)

from agent.sdk_wrapper import AgentGuardClient

logger = logging.getLogger(__name__)

SCENARIO_MAP: Dict[str, str] = {
    "1": "valid_exact_payment",
    "valid_exact_payment": "valid_exact_payment",
    "valid_payment": "valid_exact_payment",
    "2": "changed_recipient",
    "changed_recipient": "changed_recipient",
    "3": "changed_amount",
    "changed_amount": "changed_amount",
    "4": "expired_approval",
    "expired_approval": "expired_approval",
    "5": "revoked_approval",
    "revoked_approval": "revoked_approval",
    "6": "read_only_agent_write",
    "read_only_agent_write": "read_only_agent_write",
    "7": "drop_table",
    "drop_table": "drop_table",
    "8": "over_threshold",
    "over_threshold": "over_threshold",
    "9": "replay",
    "replay": "replay",
    "10": "gateway_down",
    "gateway_down": "gateway_down",
}


def _get_db_file() -> str:
    """Returns the database file path, resolving to backend/agentguard.db if not overridden."""
    if os.getenv("AGENTGUARD_DB_PATH"):
        return os.environ["AGENTGUARD_DB_PATH"]
    if os.getenv("DB_PATH"):
        return os.environ["DB_PATH"]
    backend_db = os.path.join(_BACKEND_DIR, "agentguard.db")
    if os.path.isfile(backend_db):
        return backend_db
    return "agentguard.db"


def get_default_client(base_url: Optional[str] = None) -> AgentGuardClient:
    """
    Returns an AgentGuardClient.
    If base_url is specified or a live server is listening on port 8000, connects over HTTP.
    Otherwise, falls back to in-process ASGITransport with FastAPI app for offline execution.
    """
    target_url = base_url or os.getenv("AGENTGUARD_URL", "http://127.0.0.1:8000")

    if base_url:
        return AgentGuardClient(base_url=target_url)

    # Check if a live server is running
    try:
        with httpx.Client(timeout=0.4) as test_conn:
            res = test_conn.get(f"{target_url.rstrip('/')}/health")
            if res.status_code == 200:
                return AgentGuardClient(base_url=target_url)
    except Exception:
        pass

    # Server not responding on socket: run offline via in-process TestClient
    try:
        # Guarantee DB path is set so in-process app uses consistent DB
        os.environ.setdefault("AGENTGUARD_DB_PATH", _get_db_file())
        from app.main import app
        from fastapi.testclient import TestClient
        test_client = TestClient(app)
        return AgentGuardClient(client=test_client)
    except Exception as exc:
        logger.debug("Could not load TestClient app (%s); falling back to HTTP client.", exc)
        return AgentGuardClient(base_url=target_url)


def _expire_approval_in_db(approval_id: str, db_file: Optional[str] = None) -> None:
    """Helper to deterministically backdate an approval's expiration in SQLite."""
    target_db = db_file or _get_db_file()
    if os.path.isfile(target_db):
        conn = sqlite3.connect(target_db)
        try:
            conn.execute(
                "UPDATE approvals SET expires_at = '2020-01-01T00:00:00Z' WHERE id = ?",
                (approval_id,),
            )
            conn.commit()
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Individual Scenarios
# ---------------------------------------------------------------------------
def scenario_valid_exact_payment(client: AgentGuardClient) -> Dict[str, Any]:
    """1. Valid exact approved payment, Supplier A ₹5,000 -> ALLOW (tool executed count: 1)."""
    params = {
        "recipient": "Supplier A",
        "amount": 5000.00,
        "currency": "INR",
        "reference": "INV-001",
    }
    # Reset demo to clean state
    try:
        client.reset_demo()
    except Exception:
        pass

    ap = client.create_approval("payments.send", params)
    approval_id = ap["id"]
    client.approve(approval_id)

    before = client.get_tool_calls("payments.send").get("count", 0)
    response = client.execute("payments.send", params, approval_id=approval_id)
    after = client.get_tool_calls("payments.send").get("count", 0)

    tool_calls_count = after - before
    passed = response.get("decision") == "ALLOW" and tool_calls_count == 1

    return {
        "scenario_id": 1,
        "scenario": "valid_exact_payment",
        "description": "Valid exact approved payment, Supplier A ₹5,000",
        "expected_decision": "ALLOW",
        "decision": response.get("decision"),
        "reason": response.get("reason"),
        "executed": response.get("executed"),
        "tool_calls_count": tool_calls_count,
        "audit_id": response.get("audit_id"),
        "passed": passed,
        "response": response,
    }


def scenario_changed_recipient(client: AgentGuardClient) -> Dict[str, Any]:
    """2. Recipient changed to Supplier B after approval -> BLOCK (tool executed count: 0)."""
    approved_params = {
        "recipient": "Supplier A",
        "amount": 5000.00,
        "currency": "INR",
        "reference": "INV-001",
    }
    tampered_params = {
        "recipient": "Supplier B",
        "amount": 5000.00,
        "currency": "INR",
        "reference": "INV-001",
    }

    try:
        client.reset_demo()
    except Exception:
        pass

    ap = client.create_approval("payments.send", approved_params)
    approval_id = ap["id"]
    client.approve(approval_id)

    before = client.get_tool_calls("payments.send").get("count", 0)
    response = client.execute("payments.send", tampered_params, approval_id=approval_id)
    after = client.get_tool_calls("payments.send").get("count", 0)

    tool_calls_count = after - before
    passed = (
        response.get("decision") == "BLOCK"
        and "Recipient changed after approval" in response.get("reason", "")
        and tool_calls_count == 0
    )

    return {
        "scenario_id": 2,
        "scenario": "changed_recipient",
        "description": "Recipient changed to Supplier B after approval",
        "expected_decision": "BLOCK",
        "decision": response.get("decision"),
        "reason": response.get("reason"),
        "executed": response.get("executed"),
        "tool_calls_count": tool_calls_count,
        "audit_id": response.get("audit_id"),
        "passed": passed,
        "response": response,
    }


def scenario_changed_amount(client: AgentGuardClient) -> Dict[str, Any]:
    """3. Amount changed after approval -> BLOCK (tool executed count: 0)."""
    approved_params = {
        "recipient": "Supplier A",
        "amount": 5000.00,
        "currency": "INR",
        "reference": "INV-001",
    }
    tampered_params = {
        "recipient": "Supplier A",
        "amount": 6000.00,
        "currency": "INR",
        "reference": "INV-001",
    }

    try:
        client.reset_demo()
    except Exception:
        pass

    ap = client.create_approval("payments.send", approved_params)
    approval_id = ap["id"]
    client.approve(approval_id)

    before = client.get_tool_calls("payments.send").get("count", 0)
    response = client.execute("payments.send", tampered_params, approval_id=approval_id)
    after = client.get_tool_calls("payments.send").get("count", 0)

    tool_calls_count = after - before
    passed = (
        response.get("decision") == "BLOCK"
        and "Amount changed after approval" in response.get("reason", "")
        and tool_calls_count == 0
    )

    return {
        "scenario_id": 3,
        "scenario": "changed_amount",
        "description": "Amount changed after approval (₹5,000 -> ₹6,000)",
        "expected_decision": "BLOCK",
        "decision": response.get("decision"),
        "reason": response.get("reason"),
        "executed": response.get("executed"),
        "tool_calls_count": tool_calls_count,
        "audit_id": response.get("audit_id"),
        "passed": passed,
        "response": response,
    }


def scenario_expired_approval(client: AgentGuardClient) -> Dict[str, Any]:
    """4. Approval expired -> BLOCK (tool executed count: 0)."""
    params = {
        "recipient": "Supplier A",
        "amount": 5000.00,
        "currency": "INR",
        "reference": "INV-001",
    }

    try:
        client.reset_demo()
    except Exception:
        pass

    ap = client.create_approval("payments.send", params)
    approval_id = ap["id"]
    client.approve(approval_id)

    # Force expiration in DB
    _expire_approval_in_db(approval_id)

    before = client.get_tool_calls("payments.send").get("count", 0)
    response = client.execute("payments.send", params, approval_id=approval_id)
    after = client.get_tool_calls("payments.send").get("count", 0)

    tool_calls_count = after - before
    passed = (
        response.get("decision") == "BLOCK"
        and "Approval expired" in response.get("reason", "")
        and tool_calls_count == 0
    )

    return {
        "scenario_id": 4,
        "scenario": "expired_approval",
        "description": "Approval expired before execution",
        "expected_decision": "BLOCK",
        "decision": response.get("decision"),
        "reason": response.get("reason"),
        "executed": response.get("executed"),
        "tool_calls_count": tool_calls_count,
        "audit_id": response.get("audit_id"),
        "passed": passed,
        "response": response,
    }


def scenario_revoked_approval(client: AgentGuardClient) -> Dict[str, Any]:
    """5. Approval revoked -> BLOCK (tool executed count: 0)."""
    params = {
        "recipient": "Supplier A",
        "amount": 5000.00,
        "currency": "INR",
        "reference": "INV-001",
    }

    try:
        client.reset_demo()
    except Exception:
        pass

    ap = client.create_approval("payments.send", params)
    approval_id = ap["id"]
    client.approve(approval_id)
    client.revoke(approval_id)

    before = client.get_tool_calls("payments.send").get("count", 0)
    response = client.execute("payments.send", params, approval_id=approval_id)
    after = client.get_tool_calls("payments.send").get("count", 0)

    tool_calls_count = after - before
    passed = (
        response.get("decision") == "BLOCK"
        and "Approval revoked" in response.get("reason", "")
        and tool_calls_count == 0
    )

    return {
        "scenario_id": 5,
        "scenario": "revoked_approval",
        "description": "Approval revoked by human before execution",
        "expected_decision": "BLOCK",
        "decision": response.get("decision"),
        "reason": response.get("reason"),
        "executed": response.get("executed"),
        "tool_calls_count": tool_calls_count,
        "audit_id": response.get("audit_id"),
        "passed": passed,
        "response": response,
    }


def scenario_read_only_agent_write(client: AgentGuardClient) -> Dict[str, Any]:
    """6. Read-only agent attempts a write -> BLOCK (tool executed count: 0)."""
    params = {
        "recipient": "Supplier A",
        "amount": 5000.00,
        "currency": "INR",
        "reference": "INV-001",
    }

    try:
        client.reset_demo()
    except Exception:
        pass

    before = client.get_tool_calls("payments.send").get("count", 0)
    response = client.execute(
        "payments.send",
        params,
        agent_id="reader-agent",
        task_id="task-reader-1",
    )
    after = client.get_tool_calls("payments.send").get("count", 0)

    tool_calls_count = after - before
    passed = (
        response.get("decision") == "BLOCK"
        and "Agent lacks write permission" in response.get("reason", "")
        and tool_calls_count == 0
    )

    return {
        "scenario_id": 6,
        "scenario": "read_only_agent_write",
        "description": "Read-only agent reader-agent attempts payments.send",
        "expected_decision": "BLOCK",
        "decision": response.get("decision"),
        "reason": response.get("reason"),
        "executed": response.get("executed"),
        "tool_calls_count": tool_calls_count,
        "audit_id": response.get("audit_id"),
        "passed": passed,
        "response": response,
    }


def scenario_drop_table(client: AgentGuardClient) -> Dict[str, Any]:
    """7. DROP TABLE customers -> BLOCK (tool executed count: 0)."""
    params = {
        "query": "DROP TABLE customers",
        "database": "production",
    }

    try:
        client.reset_demo()
    except Exception:
        pass

    before = client.get_tool_calls("database.run_sql").get("count", 0)
    response = client.execute("database.run_sql", params)
    after = client.get_tool_calls("database.run_sql").get("count", 0)

    tool_calls_count = after - before
    passed = (
        response.get("decision") == "BLOCK"
        and "Destructive database operation prohibited" in response.get("reason", "")
        and tool_calls_count == 0
    )

    return {
        "scenario_id": 7,
        "scenario": "drop_table",
        "description": "Destructive SQL operation: DROP TABLE customers",
        "expected_decision": "BLOCK",
        "decision": response.get("decision"),
        "reason": response.get("reason"),
        "executed": response.get("executed"),
        "tool_calls_count": tool_calls_count,
        "audit_id": response.get("audit_id"),
        "passed": passed,
        "response": response,
    }


def scenario_over_threshold(client: AgentGuardClient) -> Dict[str, Any]:
    """8. Payment above ₹10,000 without approval -> ASK_HUMAN (tool executed count: 0)."""
    params = {
        "recipient": "Supplier A",
        "amount": 15000.00,
        "currency": "INR",
        "reference": "INV-LARGE",
    }

    try:
        client.reset_demo()
    except Exception:
        pass

    before = client.get_tool_calls("payments.send").get("count", 0)
    response = client.execute("payments.send", params)
    after = client.get_tool_calls("payments.send").get("count", 0)

    tool_calls_count = after - before
    passed = (
        response.get("decision") == "ASK_HUMAN"
        and "Payment exceeds ₹10,000 limit" in response.get("reason", "")
        and tool_calls_count == 0
    )

    return {
        "scenario_id": 8,
        "scenario": "over_threshold",
        "description": "Payment ₹15,000 above ₹10,000 threshold without approval",
        "expected_decision": "ASK_HUMAN",
        "decision": response.get("decision"),
        "reason": response.get("reason"),
        "executed": response.get("executed"),
        "tool_calls_count": tool_calls_count,
        "audit_id": response.get("audit_id"),
        "passed": passed,
        "response": response,
    }


def scenario_replay(client: AgentGuardClient) -> Dict[str, Any]:
    """9. Replay of used approval -> BLOCK (tool executed count: 0 on replay)."""
    params = {
        "recipient": "Supplier A",
        "amount": 5000.00,
        "currency": "INR",
        "reference": "INV-001",
    }

    try:
        client.reset_demo()
    except Exception:
        pass

    ap = client.create_approval("payments.send", params)
    approval_id = ap["id"]
    client.approve(approval_id)

    # First legitimate execution
    resp1 = client.execute("payments.send", params, approval_id=approval_id)
    assert resp1.get("decision") == "ALLOW", "Prerequisite: first execution must succeed"

    # Replay attempt with same approval
    before = client.get_tool_calls("payments.send").get("count", 0)
    response = client.execute("payments.send", params, approval_id=approval_id)
    after = client.get_tool_calls("payments.send").get("count", 0)

    tool_calls_count = after - before
    passed = (
        response.get("decision") == "BLOCK"
        and "Approval already used (replay)" in response.get("reason", "")
        and tool_calls_count == 0
    )

    return {
        "scenario_id": 9,
        "scenario": "replay",
        "description": "Duplicate execution / replay with used approval",
        "expected_decision": "BLOCK",
        "decision": response.get("decision"),
        "reason": response.get("reason"),
        "executed": response.get("executed"),
        "tool_calls_count": tool_calls_count,
        "audit_id": response.get("audit_id"),
        "passed": passed,
        "response": response,
    }


def scenario_gateway_down(client: Optional[AgentGuardClient] = None) -> Dict[str, Any]:
    """10. Gateway unreachable / network error -> BLOCK (fail closed, tool count: 0)."""
    # Specifically target an unassigned port to guarantee connection error
    dead_client = AgentGuardClient(base_url="http://127.0.0.1:59999", timeout=1.0)
    try:
        response = dead_client.execute("payments.send", {"recipient": "Supplier A", "amount": 5000})
    finally:
        dead_client.close()

    passed = (
        response.get("decision") == "BLOCK"
        and "Gateway error: failed closed" in response.get("reason", "")
        and response.get("executed") is False
    )

    return {
        "scenario_id": 10,
        "scenario": "gateway_down",
        "description": "Gateway unreachable / connection failure (fail closed)",
        "expected_decision": "BLOCK",
        "decision": response.get("decision"),
        "reason": response.get("reason"),
        "executed": response.get("executed"),
        "tool_calls_count": 0,
        "audit_id": None,
        "passed": passed,
        "response": response,
    }


# ---------------------------------------------------------------------------
# Registry of All Scenarios
# ---------------------------------------------------------------------------
SCENARIOS: List[Tuple[str, Callable[[AgentGuardClient], Dict[str, Any]]]] = [
    ("valid_exact_payment", scenario_valid_exact_payment),
    ("changed_recipient", scenario_changed_recipient),
    ("changed_amount", scenario_changed_amount),
    ("expired_approval", scenario_expired_approval),
    ("revoked_approval", scenario_revoked_approval),
    ("read_only_agent_write", scenario_read_only_agent_write),
    ("drop_table", scenario_drop_table),
    ("over_threshold", scenario_over_threshold),
    ("replay", scenario_replay),
    ("gateway_down", scenario_gateway_down),
]


def run_scenario(name_or_num: str, client: Optional[AgentGuardClient] = None) -> Dict[str, Any]:
    """Runs a single scenario by name or number (1-10)."""
    key = str(name_or_num).strip().lower()
    canonical_name = SCENARIO_MAP.get(key)
    if not canonical_name:
        raise ValueError(f"Unknown scenario: {name_or_num!r}. Available: {list(SCENARIO_MAP.keys())}")

    fn = next(func for s_name, func in SCENARIOS if s_name == canonical_name)
    c = client or get_default_client()
    return fn(c)


def run_all(client: Optional[AgentGuardClient] = None) -> List[Dict[str, Any]]:
    """Runs all 10 scenarios in sequence."""
    c = client or get_default_client()
    results: List[Dict[str, Any]] = []
    for _, func in SCENARIOS:
        res = func(c)
        results.append(res)
    return results


# ---------------------------------------------------------------------------
# CLI Entry Point: python -m agent.scripted_agent run <scenario|all>
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m agent.scripted_agent",
        description="AgentGuard Scripted Agent - Deterministic Scenario Runner",
    )
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run scenario(s)")
    run_parser.add_argument(
        "target",
        help="Scenario name, number (1-10), or 'all'",
        default="all",
        nargs="?",
    )
    run_parser.add_argument(
        "--url",
        help="Custom AgentGuard gateway base URL",
        default=None,
    )

    args = parser.parse_args()

    if args.command != "run":
        parser.print_help()
        sys.exit(0)

    client = get_default_client(base_url=args.url)

    target = args.target.strip().lower()
    if target == "all":
        results = run_all(client)
    else:
        try:
            results = [run_scenario(target, client)]
        except ValueError as err:
            print(f"Error: {err}", file=sys.stderr)
            sys.exit(1)

    # Print clean formatted table
    print("=" * 80)
    print("AGENTGUARD SCRIPTED AGENT — DETERMINISTIC SCENARIO RESULTS")
    print("=" * 80)
    print(f"{'#':<3} {'Scenario':<24} {'Expected':<11} {'Actual':<11} {'Tool Execs':<11} {'Status'}")
    print("-" * 80)

    passed_count = 0
    for r in results:
        status_str = "PASS" if r["passed"] else "FAIL"
        if r["passed"]:
            passed_count += 1
        print(
            f"{r['scenario_id']:<3} "
            f"{r['scenario']:<24} "
            f"{r['expected_decision']:<11} "
            f"{str(r['decision']):<11} "
            f"{r['tool_calls_count']:<11} "
            f"{status_str}"
        )

    print("-" * 80)
    print(f"Summary: {passed_count}/{len(results)} scenarios PASSED")
    print("=" * 80)

    if passed_count < len(results):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
