"""
backend/tests/test_story_http.py

B7 – Full-story integration test over REAL HTTP (plan.md §B7).

Verifies the complete Supplier A → Supplier B scenario through a live
uvicorn server using httpx Client:

  1. Create approval for Supplier A ₹5,000
  2. Human approves the approval
  3. Agent attempts to execute for Supplier B  → HTTP 200 BLOCK
  4. tool_calls count == 0 (tool NEVER ran)
  5. Audit log contains the BLOCK record
  6. Agent executes the original Supplier A payment → HTTP 200 ALLOW
  7. tool_calls count == 1 (tool ran exactly once)

All requests go over the network stack (TCP → uvicorn → FastAPI → gateway).
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time

import httpx
import pytest


# ---------------------------------------------------------------------------
# Live server fixture – spawns uvicorn as a subprocess on a free port
# ---------------------------------------------------------------------------

def _free_port() -> int:
    """Ask the OS for a free TCP port, then immediately release it."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def live_server(tmp_path_factory):
    """
    Starts a real uvicorn server as a subprocess for the module, seeded with
    the demo DB.  Yields the base URL string, e.g. 'http://127.0.0.1:54321'.
    """
    from app.db import reset_db, seed_demo

    db_path = str(tmp_path_factory.mktemp("http_story") / "story.db")
    reset_db(db_path)
    seed_demo(db_path)

    port = _free_port()
    env = {
        **os.environ,
        "AGENTGUARD_DB_PATH": db_path,
        "DEMO_MODE": "1",
        # Silence uvicorn startup banner in test output
        "UVICORN_LOG_LEVEL": "error",
    }

    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "app.main:app",
            "--host", "127.0.0.1",
            "--port", str(port),
            "--log-level", "error",
        ],
        env=env,
        cwd=os.path.dirname(os.path.dirname(__file__)),  # backend/
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    base_url = f"http://127.0.0.1:{port}"

    # Wait up to 10 s for the server to respond to /health
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{base_url}/health", timeout=1.0)
            if r.status_code == 200:
                break
        except Exception:
            time.sleep(0.15)
    else:
        proc.kill()
        raise RuntimeError(f"uvicorn did not start within 10 seconds on port {port}")

    yield base_url

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


# ---------------------------------------------------------------------------
# Helper: synchronous httpx client
# ---------------------------------------------------------------------------
@pytest.fixture()
def http(live_server):
    with httpx.Client(base_url=live_server, timeout=10.0) as client:
        yield client


# ---------------------------------------------------------------------------
# B7 – Supplier A → Supplier B full-story over real HTTP
# ---------------------------------------------------------------------------
class TestSupplierStoryHTTP:
    """
    Full-story integration test:
      Approve A → attempt B (BLOCK) → execute A (ALLOW).
    All requests traverse a live TCP stack.
    """

    def test_full_story_supplier_a_to_b(self, http: httpx.Client) -> None:
        payment_a = {
            "recipient": "Supplier A",
            "amount": 5000.00,
            "currency": "INR",
            "reference": "INV-HTTP-101",
        }

        # ── Step 1: Create approval for Supplier A ₹5,000 ───────────────────
        r = http.post("/v1/approvals", json={
            "agent_id": "accounts-agent",
            "task_id": "task-accounts-1",
            "tool": "payments.send",
            "params": payment_a,
        })
        assert r.status_code == 201, f"Create approval failed: {r.text}"
        approval_id = r.json()["id"]
        assert r.json()["status"] == "pending"

        # ── Step 2: Human approves ───────────────────────────────────────────
        r = http.post(f"/v1/approvals/{approval_id}/approve")
        assert r.status_code == 200, f"Approve failed: {r.text}"
        assert r.json()["status"] == "approved"

        # ── Step 3: Agent attempts Supplier B with Supplier A's approval ─────
        payment_b = {**payment_a, "recipient": "Supplier B"}
        r = http.post("/v1/gateway/execute", json={
            "agent_id": "accounts-agent",
            "task_id": "task-accounts-1",
            "tool": "payments.send",
            "params": payment_b,
            "approval_id": approval_id,
        })
        assert r.status_code == 200, f"Execute (B) failed: {r.text}"
        body_b = r.json()
        assert body_b["decision"] == "BLOCK", f"Expected BLOCK, got: {body_b}"
        assert body_b["reason"] == "Recipient changed after approval"
        assert body_b["executed"] is False

        # ── Step 4: tool_calls count must be 0 ──────────────────────────────
        r = http.get("/v1/tool_calls")
        assert r.status_code == 200
        assert r.json()["count"] == 0, "Tool executed despite BLOCK — critical failure"

        # ── Step 5: Audit log records the BLOCK ─────────────────────────────
        r = http.get("/v1/audit")
        assert r.status_code == 200
        records = r.json()
        block_rec = next(
            (rec for rec in records if rec["id"] == body_b["audit_id"]), None
        )
        assert block_rec is not None, "Audit record for BLOCK attempt not found"
        assert block_rec["decision"] == "BLOCK"
        assert block_rec["executed"] == 0

        # ── Step 6: Execute the original approved payment to Supplier A ──────
        r = http.post("/v1/gateway/execute", json={
            "agent_id": "accounts-agent",
            "task_id": "task-accounts-1",
            "tool": "payments.send",
            "params": payment_a,
            "approval_id": approval_id,
        })
        assert r.status_code == 200, f"Execute (A) failed: {r.text}"
        body_a = r.json()
        assert body_a["decision"] == "ALLOW", f"Expected ALLOW, got: {body_a}"
        assert body_a["executed"] is True

        # ── Step 7: Exactly one tool_call recorded ───────────────────────────
        r = http.get("/v1/tool_calls")
        assert r.status_code == 200
        assert r.json()["count"] == 1, "Expected exactly 1 tool_call after ALLOW"

    def test_health_endpoint(self, http: httpx.Client) -> None:
        """Sanity check: /health returns 200 ok over real HTTP."""
        r = http.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_cors_allowed_origin(self, http: httpx.Client) -> None:
        """
        B6 – Preflight from http://localhost:5173 must receive ACAO header.
        """
        r = http.options(
            "/v1/gateway/execute",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        acao = r.headers.get("access-control-allow-origin", "")
        assert acao == "http://localhost:5173", (
            f"Expected CORS allow-origin=http://localhost:5173, got {acao!r}"
        )

    def test_cors_wrong_origin_not_reflected(self, http: httpx.Client) -> None:
        """
        B6 – Preflight from an unapproved origin must NOT receive the ACAO header
        with that origin's value.
        """
        r = http.options(
            "/v1/gateway/execute",
            headers={
                "Origin": "http://evil.example.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        acao = r.headers.get("access-control-allow-origin", "")
        assert acao != "http://evil.example.com", (
            f"Evil origin was reflected in CORS — got ACAO={acao!r}"
        )

    def test_demo_reset_succeeds_with_demo_mode(self, http: httpx.Client) -> None:
        """
        B6 – /v1/demo/reset must succeed when DEMO_MODE=1 (set by fixture).
        """
        r = http.post("/v1/demo/reset")
        assert r.status_code == 200, f"Demo reset failed with DEMO_MODE=1: {r.text}"
        assert r.json()["status"] == "ok"
