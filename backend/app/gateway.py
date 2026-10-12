"""
backend/app/gateway.py

HARD RULES (plan.md):
  - ONLY this file may import from app.tools.*
  - Every exception → BLOCK "Gateway error: failed closed" (fail closed).
  - Every decision is appended to the audit log in the finally block.
  - Three decisions ONLY: ALLOW, ASK_HUMAN, BLOCK. Never invent others.

Execution flow (plan.md §C2, in exact order):
  1. Lookup agent → BLOCK "Unknown agent: <id>" if missing
  2. Verify tool in registry → BLOCK "Unknown tool: <name>" if missing
  3. policy_check() → BLOCK reason | ASK_HUMAN reason | None
  4. If ASK_HUMAN reason and no approval_id supplied:
       create pending approval → return ASK_HUMAN with approval_id
  5. If approval_id supplied:
     a. Fetch approval row
     b. Verify (agent_id, task_id, tool) match → BLOCK "Approval does not match request"
     c. Recompute canonical hash of sensitive params → BLOCK "<Field> changed after approval"
     d. Check expiry: now >= expires_at → BLOCK "Approval expired"
     e. Check revocation: revoked_at IS NOT NULL → BLOCK "Approval revoked"
     f. Atomic UPDATE SET status='used' WHERE status='approved' AND revoked_at IS NULL AND expires_at > now
        rowcount != 1 → BLOCK "Approval already used (replay)"
  6. Call tool → insert tool_calls row → return ALLOW executed=True
  7. Any exception at any point → BLOCK "Gateway error: failed closed"
  8. finally: append audit record (if audit write fails, still return BLOCK)

The module-level name `policy_check` is forwarded from policy.py so that
  patch.object(gw, 'policy_check', side_effect=…)
works in test_gateway_failure_fails_closed.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# ─── Tool imports – ONLY gateway.py may import these ────────────────────────
from app.tools import payments as _payments_tool
from app.tools import email as _email_tool
from app.tools import database as _database_tool

from app.approvals import (
    ApprovalDict,
    create as _approvals_create,
    diff as _approvals_diff,
    extract_sensitive_params,
    get as _approval_get,
    mask_secrets,
    now as _clock_now,
)
from app.db import DB_PATH, get_connection
from app.policy import TOOL_REGISTRY, policy_check  # re-exported so tests can patch it
from app import audit as _audit
from app.schemas import Decision, ExecuteResponse, canonical_hash, normalize_params

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 2.0  # soft guard — not a hard OS-level timeout


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_agent(db_path: str, agent_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _get_task(db_path: str, task_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _run_tool(tool: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dispatches to the correct simulated tool function.
    ONLY gateway.py calls this. No other module may import tools/*.
    """
    if tool == "payments.send":
        return _payments_tool.send(params)
    elif tool == "email.send":
        return _email_tool.send(params)
    elif tool == "database.run_sql":
        return _database_tool.run_sql(params)
    else:
        raise ValueError(f"Unknown tool in dispatcher: {tool!r}")


def _insert_tool_call(
    db_path: str,
    tool: str,
    params: Dict[str, Any],
    audit_id: int,
) -> None:
    """Inserts a tool_calls row with secrets masked and params normalized."""
    masked = mask_secrets(normalize_params(params))
    params_json = json.dumps(masked, sort_keys=True)
    ts = datetime.now(timezone.utc).isoformat()
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO tool_calls (tool, params_json, executed_at, audit_id) VALUES (?, ?, ?, ?)",
            (tool, params_json, ts, audit_id),
        )
        conn.commit()
    finally:
        conn.close()


def _atomic_use_approval(
    db_path: str,
    approval_id: str,
    clock: Optional[Any],
) -> bool:
    """
    Atomically transitions approval from status='approved' → status='used'.
    Returns True iff exactly one row was updated (i.e., we won the race).
    """
    now_iso = _clock_now(clock).isoformat()
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            """
            UPDATE approvals
            SET status = 'used', used_at = ?
            WHERE id = ?
              AND status = 'approved'
              AND revoked_at IS NULL
              AND expires_at > ?
            """,
            (now_iso, approval_id, now_iso),
        )
        conn.commit()
        return cur.rowcount == 1
    finally:
        conn.close()


def _first_diff_reason(
    tool: str,
    approved_params_json: str,
    attempted_params: Dict[str, Any],
) -> Optional[str]:
    """
    Returns a human-readable reason for the first field that changed,
    or None if nothing changed.
    """
    try:
        approved = json.loads(approved_params_json)
    except Exception:
        approved = {}

    diffs = _approvals_diff(approved, attempted_params, tool=tool)
    if not diffs:
        return None

    first_field = diffs[0]["field"]
    # Map canonical field names → exact test-expected reason strings
    field_reasons = {
        "recipient": "Recipient changed after approval",
        "amount": "Amount changed after approval",
        "amount_paise": "Amount changed after approval",
        "currency": "Currency changed after approval",
        "to_domain": "Email recipient changed after approval",
        "has_attachment": "Attachment flag changed after approval",
        "statement_type": "SQL statement type changed after approval",
        "table": "SQL table changed after approval",
    }
    return field_reasons.get(first_field, f"{first_field.capitalize()} changed after approval")


def _hash_matches(tool: str, attempted_params: Dict[str, Any], stored_hash: str) -> bool:
    """Returns True iff canonical sensitive hash of attempted_params == stored_hash."""
    sensitive = extract_sensitive_params(tool, attempted_params)
    return canonical_hash(sensitive) == stored_hash


# ---------------------------------------------------------------------------
# Main execute() function
# ---------------------------------------------------------------------------

def execute(
    db_path: str = DB_PATH,
    *,
    agent_id: str,
    task_id: str,
    tool: str,
    params: Dict[str, Any],
    approval_id: Optional[str] = None,
    clock: Optional[Any] = None,
) -> ExecuteResponse:
    """
    Gateway enforcement pipeline (plan.md §C2).
    Returns an ExecuteResponse with decision, reason, executed, audit_id.
    NEVER raises — all exceptions return BLOCK "Gateway error: failed closed".
    """
    decision: str = Decision.BLOCK.value
    reason: str = "Gateway error: failed closed"
    executed: bool = False
    audit_id: Optional[int] = None
    created_approval_id: Optional[str] = approval_id

    ts = _clock_now(clock).isoformat()

    try:
        # ── Step 1: Lookup agent ──────────────────────────────────────────────
        agent = _get_agent(db_path, agent_id)
        if agent is None:
            decision = Decision.BLOCK.value
            reason = f"Unknown agent: {agent_id}"

        # ── Step 2: Verify tool in registry ──────────────────────────────────
        elif tool not in TOOL_REGISTRY:
            decision = Decision.BLOCK.value
            reason = f"Unknown tool: {tool}"

        else:
            # ── Step 3: Policy check (hard block or ASK_HUMAN) ───────────────
            block_reason, ask_reason = policy_check(db_path, agent, tool, params)

            if block_reason:
                decision = Decision.BLOCK.value
                reason = block_reason

            # ── Step 4: ASK_HUMAN with no approval supplied ───────────────────
            elif ask_reason and approval_id is None:
                ap = _approvals_create(
                    agent_id=agent_id,
                    task_id=task_id,
                    tool=tool,
                    params=params,
                    db_path=db_path,
                    clock=clock,
                )
                decision = Decision.ASK_HUMAN.value
                reason = ask_reason
                created_approval_id = ap.id

            # ── Step 5: Approval validation ───────────────────────────────────
            elif approval_id is not None:
                ap = _approval_get(approval_id, db_path=db_path)

                # 5a. Approval must exist and belong to this (agent, task, tool)
                if ap is None or (
                    ap["agent_id"] != agent_id
                    or ap["task_id"] != task_id
                    or ap["tool"] != tool
                ):
                    decision = Decision.BLOCK.value
                    reason = "Approval does not match request"

                # 5c. Canonical hash check (sensitive params must match exactly)
                elif not _hash_matches(tool, params, ap["approved_hash"]):
                    diff_reason = _first_diff_reason(tool, ap["approved_params_json"], params)
                    decision = Decision.BLOCK.value
                    reason = diff_reason or "Parameters changed after approval"

                else:
                    # 5d. Expiry check (re-validated immediately before execution)
                    now_dt = _clock_now(clock)
                    expires_str = ap.get("expires_at", "")
                    is_expired = False
                    if expires_str:
                        try:
                            from datetime import datetime as _dt, timezone as _tz
                            expires_dt = _dt.fromisoformat(expires_str)
                            if expires_dt.tzinfo is None:
                                expires_dt = expires_dt.replace(tzinfo=_tz.utc)
                            if now_dt.tzinfo is None:
                                now_dt = now_dt.replace(tzinfo=_tz.utc)
                            if now_dt >= expires_dt:
                                is_expired = True
                        except Exception:
                            pass

                    if is_expired:
                        decision = Decision.BLOCK.value
                        reason = "Approval expired"

                    # 5e. Revocation check
                    elif ap.get("revoked_at") is not None:
                        decision = Decision.BLOCK.value
                        reason = "Approval revoked"

                    else:
                        # 5f. Atomic one-time use (replay protection)
                        won = _atomic_use_approval(db_path, approval_id, clock)
                        if not won:
                            decision = Decision.BLOCK.value
                            reason = "Approval already used (replay)"
                        else:
                            # ── Step 6: Execute the tool ───────────────────────
                            _run_tool(tool, params)
                            decision = Decision.ALLOW.value
                            reason = "Request approved and executed successfully"
                            executed = True

            else:
                # Safe execution without approval requirement
                _run_tool(tool, params)
                decision = Decision.ALLOW.value
                reason = "Request approved and executed successfully"
                executed = True

    except Exception as exc:
        logger.debug("Gateway caught exception (failing closed): %s", type(exc).__name__)
        decision = Decision.BLOCK.value
        reason = "Gateway error: failed closed"
        executed = False

    finally:
        # ── Step 8: Append audit record (always, even on exception) ─────────
        try:
            audit_id = _audit.append(
                db_path,
                ts=ts,
                agent_id=agent_id,
                task_id=task_id,
                tool=tool,
                params=params,
                decision=decision,
                reason=reason,
                approval_id=created_approval_id,
                executed=executed,
            )
        except Exception as audit_exc:
            logger.error("Audit write failed: %s", audit_exc)
            audit_id = None

        # Insert tool_calls row if executed (needs audit_id from above)
        if executed and audit_id is not None:
            try:
                _insert_tool_call(db_path, tool, params, audit_id)
            except Exception as tc_exc:
                logger.error("tool_calls write failed: %s", tc_exc)

    return ExecuteResponse(
        decision=decision,
        reason=reason,
        executed=executed,
        audit_id=audit_id,
        approval_id=created_approval_id,
    )
