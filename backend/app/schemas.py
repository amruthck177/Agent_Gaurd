"""
backend/app/schemas.py

Pydantic models for AgentGuard request/response bodies, data entities,
and canonical parameter hashing helpers.

Decisions: ALLOW, ASK_HUMAN, BLOCK (the only three decisions everywhere).
Money: Stored and canonicalized as integer paise (1 INR = 100 paise).
"""

from __future__ import annotations

import hashlib
import json
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Decision enum — the ONLY three statuses allowed anywhere in AgentGuard
# ---------------------------------------------------------------------------
class Decision(str, Enum):
    ALLOW = "ALLOW"
    ASK_HUMAN = "ASK_HUMAN"
    BLOCK = "BLOCK"


# ---------------------------------------------------------------------------
# Canonicalization and Money Helpers
# ---------------------------------------------------------------------------
def parse_money_to_paise(val: Any) -> int:
    """
    Normalizes monetary values to integer paise.
    1 Rupee (INR) = 100 Paise.
    Examples:
      - 5000.00 (float rupees) -> 500000 paise
      - 500000 (int paise) -> 500000 paise
      - "5000.00" (str rupees) -> 500000 paise
      - "500000 paise" -> 500000 paise
      - "₹5,000.00" -> 500000 paise
    """
    if isinstance(val, float):
        return int(round(val * 100))
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        s = val.strip().lower()
        if s.endswith("paise"):
            s = s[:-5].strip()
            return int(round(float(s.replace(",", ""))))
        if s.endswith("p"):
            s = s[:-1].strip()
            return int(round(float(s.replace(",", ""))))
        if s.startswith("₹"):
            s = s[1:].strip()
            return int(round(float(s.replace(",", "")) * 100))
        if s.startswith("rs."):
            s = s[3:].strip()
            return int(round(float(s.replace(",", "")) * 100))
        if s.startswith("rs"):
            s = s[2:].strip()
            return int(round(float(s.replace(",", "")) * 100))
        if "." in s:
            return int(round(float(s.replace(",", "")) * 100))
        return int(s.replace(",", ""))
    raise ValueError(f"Cannot convert amount {val!r} to integer paise")


def normalize_recipient(val: str) -> str:
    """
    Trims whitespace and casefolds recipient/payee names to produce a stable ID.
    Prevents 'Supplier A ' vs 'supplier a' bypasses.
    """
    return val.strip().casefold()


def normalize_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively normalizes a parameter dictionary:
      - Recipient / payee / supplier keys are trimmed and casefolded.
      - Currency keys are uppercased (e.g. 'inr' -> 'INR').
      - Amount / amount_paise keys are converted to integer paise under 'amount_paise'.
      - Nested dictionaries and lists are normalized recursively.
    """
    normalized: Dict[str, Any] = {}
    recipient_keys = {"recipient", "recipient_id", "payee", "supplier", "vendor", "to"}

    for key, value in params.items():
        if key in ("amount", "amount_paise"):
            normalized["amount_paise"] = parse_money_to_paise(value)
        elif key in recipient_keys and isinstance(value, str):
            normalized[key] = normalize_recipient(value)
        elif key == "currency" and isinstance(value, str):
            normalized[key] = value.strip().upper()
        elif isinstance(value, dict):
            normalized[key] = normalize_params(value)
        elif isinstance(value, list):
            normalized[key] = [
                normalize_params(item) if isinstance(item, dict)
                else (normalize_recipient(item) if isinstance(item, str) and key in recipient_keys else item)
                for item in value
            ]
        else:
            normalized[key] = value

    return normalized


def canonical(data: Any) -> str:
    """
    Produces a canonical sorted-key compact JSON string for deterministic matching and hashing.
      - Dictionaries: normalized via normalize_params, keys sorted, no extra whitespace.
      - Primitive strings: trimmed and casefolded if recipient-like or parsed if money.
      - Floats: converted to integer paise.
      - Pydantic models: dumped to dict and normalized.
    """
    if isinstance(data, BaseModel):
        data = data.model_dump()

    if isinstance(data, dict):
        normalized = normalize_params(data)
        return json.dumps(normalized, sort_keys=True, separators=(",", ":"))

    if isinstance(data, (float, int)):
        paise = parse_money_to_paise(data)
        return json.dumps(paise, separators=(",", ":"))

    if isinstance(data, str):
        s = data.strip()
        # Monetary string check
        s_lower = s.lower()
        if s_lower.endswith("paise") or s_lower.endswith("p") or s_lower.startswith("₹") or s_lower.startswith("rs"):
            paise = parse_money_to_paise(s)
            return json.dumps(paise, separators=(",", ":"))
        try:
            if "." in s:
                val = float(s.replace(",", ""))
                return json.dumps(parse_money_to_paise(val), separators=(",", ":"))
        except ValueError:
            pass
        return json.dumps(normalize_recipient(s), separators=(",", ":"))

    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def canonical_hash(data: Any) -> str:
    """Computes SHA-256 hash of the canonical JSON string."""
    return hashlib.sha256(canonical(data).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Gateway Execution Models (plan.md §C5: POST /v1/gateway/execute)
# ---------------------------------------------------------------------------
class ExecuteRequest(BaseModel):
    agent_id: str = Field(..., description="Registered agent identifier, e.g. 'accounts-agent'")
    task_id: str = Field(..., description="Active task identifier, e.g. 'task-accounts-1'")
    tool: str = Field(..., description="Tool name, e.g. 'payments.send'")
    params: Dict[str, Any] = Field(default_factory=dict, description="Tool parameters")
    approval_id: Optional[str] = Field(None, description="Pre-obtained approval ID, if any")


class ExecuteResponse(BaseModel):
    decision: Decision = Field(..., description="Decision: ALLOW, ASK_HUMAN, or BLOCK")
    reason: str = Field(..., description="Deterministic human-readable explanation")
    executed: bool = Field(False, description="True only if tool actually executed")
    audit_id: Optional[int] = Field(None, description="Audit log record ID")
    approval_id: Optional[str] = Field(None, description="Approval ID if created or validated")


# Backward compatibility aliases
GatewayRequest = ExecuteRequest
GatewayResponse = ExecuteResponse


# ---------------------------------------------------------------------------
# Approvals Models (plan.md §C4, §C5)
# ---------------------------------------------------------------------------
class Approval(BaseModel):
    id: str
    agent_id: str
    task_id: str
    tool: str
    approved_params_json: str
    approved_hash: str
    status: str = Field(
        ...,
        description="One of: 'pending', 'approved', 'rejected', 'used', 'revoked', 'expired'"
    )
    created_at: str
    approved_at: Optional[str] = None
    expires_at: str
    revoked_at: Optional[str] = None
    used_at: Optional[str] = None


class ApprovalCreate(BaseModel):
    agent_id: str
    task_id: str
    tool: str
    params: Dict[str, Any]


class ApprovalOut(Approval):
    pass


# ---------------------------------------------------------------------------
# Policy Models (plan.md §C4, §C5, §C6)
# ---------------------------------------------------------------------------
class Policy(BaseModel):
    id: Optional[int] = None
    agent_id: Optional[str] = None
    task_id: Optional[str] = None
    tool: str
    condition_json: str
    decision: Decision
    version: int = 1
    active: bool = True


class PolicyOut(Policy):
    id: int


class PolicyUpdate(BaseModel):
    tool: str
    condition_json: str
    decision: Decision
    agent_id: Optional[str] = None
    task_id: Optional[str] = None
    active: bool = True


# ---------------------------------------------------------------------------
# Audit Models (plan.md §C3, §C4, §C5)
# ---------------------------------------------------------------------------
class AuditRecord(BaseModel):
    id: Optional[int] = None
    ts: str
    agent_id: str
    task_id: str
    tool: str
    params_masked: str
    decision: Decision
    reason: str
    approval_id: Optional[str] = None
    executed: bool = False
    prev_hash: str
    hash: str


class AuditRecordOut(AuditRecord):
    id: int


class AuditVerifyResponse(BaseModel):
    ok: bool
    checked: int
    broken_at: Optional[int] = None

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)


# ---------------------------------------------------------------------------
# Agent and Task Models (plan.md §C4)
# ---------------------------------------------------------------------------
class Agent(BaseModel):
    id: str
    name: str
    role: str
    permissions_json: str = "[]"


class Task(BaseModel):
    id: str
    agent_id: str
    description: str
    scope_json: str = "{}"


class Supplier(BaseModel):
    id: str
    name: str
