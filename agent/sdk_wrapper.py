"""
agent/sdk_wrapper.py

Client SDK wrapper for interacting with AgentGuard gateway.
HARD RULE: Under NO circumstances does this module import backend/app/tools/*.
All tool execution requests must route through POST /v1/gateway/execute.
Fail closed: If the gateway is unreachable or errors, return BLOCK.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_GATEWAY_URL = os.getenv("AGENTGUARD_URL", "http://127.0.0.1:8000")
DEFAULT_TIMEOUT = float(os.getenv("AGENTGUARD_TIMEOUT", "3.0"))


class AgentGuardClient:
    """
    Client SDK wrapper for interacting with AgentGuard Gateway.
    Routes all actions to POST /v1/gateway/execute with a 3.0s timeout.
    Fails closed (returns BLOCK) on any timeout, connection error, or non-200 HTTP response.
    Contains NO tool code.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_GATEWAY_URL,
        agent_id: str = "accounts-agent",
        task_id: str = "task-accounts-1",
        timeout: float = DEFAULT_TIMEOUT,
        transport: Optional[httpx.BaseTransport] = None,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self.base_url = (base_url or DEFAULT_GATEWAY_URL).rstrip("/")
        self.agent_id = agent_id
        self.task_id = task_id
        self.timeout = timeout
        self.transport = transport
        if client is not None:
            self._client = client
        else:
            self._client = httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout,
                transport=self.transport,
            )

    def close(self) -> None:
        """Closes the underlying HTTP client session."""
        self._client.close()

    def __enter__(self) -> "AgentGuardClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _req_kwargs(self) -> Dict[str, Any]:
        """Returns request kwargs, omitting timeout if underlying client is a TestClient to avoid warnings."""
        if type(self._client).__name__ == "TestClient":
            return {}
        return {"timeout": self.timeout}

    def execute(
        self,
        tool: str,
        params: Dict[str, Any],
        approval_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes a sensitive tool action through the AgentGuard gateway.
        POSTs to /v1/gateway/execute with 3s timeout.
        Returns BLOCK on any network error, timeout, or non-200 HTTP response (fail closed).
        """
        target_agent = agent_id or self.agent_id
        target_task = task_id or self.task_id

        payload = {
            "agent_id": target_agent,
            "task_id": target_task,
            "tool": tool,
            "params": params,
            "approval_id": approval_id,
        }

        try:
            resp = self._client.post(
                "/v1/gateway/execute",
                json=payload,
                **self._req_kwargs(),
            )
            if resp.status_code == 200:
                return resp.json()
            else:
                logger.warning(
                    "Gateway returned non-200 status %d: %s. Failing closed.",
                    resp.status_code,
                    resp.text,
                )
                return {
                    "decision": "BLOCK",
                    "reason": "Gateway error: failed closed",
                    "executed": False,
                    "audit_id": None,
                    "approval_id": approval_id,
                    "status_code": resp.status_code,
                }
        except Exception as exc:
            logger.warning("Gateway request failed (%s). Failing closed to BLOCK.", exc)
            return {
                "decision": "BLOCK",
                "reason": "Gateway error: failed closed",
                "executed": False,
                "audit_id": None,
                "approval_id": approval_id,
                "error": str(exc),
            }

    # ── Convenience helper methods for demo/scripts ────────────────────────
    def create_approval(
        self,
        tool: str,
        params: Dict[str, Any],
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Creates a pending approval on the gateway."""
        payload = {
            "agent_id": agent_id or self.agent_id,
            "task_id": task_id or self.task_id,
            "tool": tool,
            "params": params,
        }
        resp = self._client.post("/v1/approvals", json=payload, **self._req_kwargs())
        resp.raise_for_status()
        return resp.json()

    def approve(self, approval_id: str) -> Dict[str, Any]:
        """Approves a pending approval."""
        resp = self._client.post(f"/v1/approvals/{approval_id}/approve", **self._req_kwargs())
        resp.raise_for_status()
        return resp.json()

    def reject(self, approval_id: str) -> Dict[str, Any]:
        """Rejects a pending approval."""
        resp = self._client.post(f"/v1/approvals/{approval_id}/reject", **self._req_kwargs())
        resp.raise_for_status()
        return resp.json()

    def revoke(self, approval_id: str) -> Dict[str, Any]:
        """Revokes an approved or pending approval."""
        resp = self._client.post(f"/v1/approvals/{approval_id}/revoke", **self._req_kwargs())
        resp.raise_for_status()
        return resp.json()

    def list_approvals(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists approvals optionally filtered by status."""
        params = {"status": status} if status else {}
        resp = self._client.get("/v1/approvals", params=params, **self._req_kwargs())
        resp.raise_for_status()
        return resp.json()

    def get_tool_calls(self, tool: Optional[str] = None) -> Dict[str, Any]:
        """Queries tool_calls records for verification."""
        params = {"tool": tool} if tool else {}
        resp = self._client.get("/v1/tool_calls", params=params, **self._req_kwargs())
        resp.raise_for_status()
        return resp.json()

    def get_audit(self) -> List[Dict[str, Any]]:
        """Queries audit log records."""
        resp = self._client.get("/v1/audit", **self._req_kwargs())
        resp.raise_for_status()
        return resp.json()

    def verify_audit(self) -> Dict[str, Any]:
        """Verifies hash-chain audit integrity."""
        resp = self._client.get("/v1/audit/verify", **self._req_kwargs())
        resp.raise_for_status()
        return resp.json()

    def reset_demo(self) -> Dict[str, Any]:
        """Resets and seeds demo database."""
        resp = self._client.post("/v1/demo/reset", **self._req_kwargs())
        resp.raise_for_status()
        return resp.json()

    def tamper_demo(self, record_id: Optional[int] = None) -> Dict[str, Any]:
        """Tampers with an audit record."""
        payload = {"record_id": record_id} if record_id else {}
        resp = self._client.post("/v1/demo/tamper", json=payload, **self._req_kwargs())
        resp.raise_for_status()
        return resp.json()
