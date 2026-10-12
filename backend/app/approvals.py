"""
backend/app/approvals.py

Approval CRUD, state-machine transitions, canonical sensitive parameter hashing,
injectable clock, and field-level diffing for AgentGuard 2.0.

Plan.md §C2 defines the approval lifecycle:
  pending → approved | rejected
  approved → used (atomic, one-time) | revoked | expired

Sensitive params per tool:
  - payments.send    -> recipient, amount (as integer paise), currency
  - email.send       -> to domain, has_attachment
  - database.run_sql -> statement type, table

Diff helper:
  diff(approved_params, attempted_params) -> list of {field, approved, attempted}
"""

from __future__ import annotations

import builtins
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

_list = builtins.list

from app.db import DB_PATH, get_connection
from app.schemas import (
    Approval,
    canonical,
    canonical_hash,
    normalize_params,
    normalize_recipient,
    parse_money_to_paise,
)

APPROVAL_TTL_SECONDS = int(os.getenv("APPROVAL_TTL_SECONDS", "600"))

# ---------------------------------------------------------------------------
# Clock abstraction (injectable & replaceable in tests)
# ---------------------------------------------------------------------------
_custom_clock: Optional[Any] = None


def get_clock() -> Optional[Any]:
    """Returns the currently active custom clock, or None if using system time."""
    return _custom_clock


def set_clock(clock: Any) -> None:
    """Sets a custom clock for testing (e.g. FakeClock instance or callable)."""
    global _custom_clock
    _custom_clock = clock


def reset_clock() -> None:
    """Resets clock back to default UTC system time."""
    global _custom_clock
    _custom_clock = None


def now(clock: Optional[Any] = None) -> datetime:
    """
    Returns the current UTC datetime.
    Priority:
      1. Explicit clock parameter passed to this function
      2. Global custom clock set via set_clock()
      3. datetime.now(timezone.utc)
    """
    clk = clock if clock is not None else _custom_clock
    if clk is not None:
        if hasattr(clk, "now"):
            res = clk.now()
            if isinstance(res, datetime):
                return res
            if isinstance(res, str):
                return datetime.fromisoformat(res)
        if callable(clk):
            res = clk()
            if isinstance(res, datetime):
                return res
            if isinstance(res, str):
                return datetime.fromisoformat(res)
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Secret masking helper (plan.md §C3: mask secrets before storing)
# ---------------------------------------------------------------------------
SECRET_KEY_PATTERNS = re.compile(
    r"(?:api[_-]?key|secret|token|password|auth|credential|access[_-]?token|private[_-]?key)",
    re.IGNORECASE,
)
SECRET_VALUE_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_\-]{8,}"),
    re.compile(r"Bearer\s+[a-zA-Z0-9_\-\.]{8,}", re.IGNORECASE),
]


def mask_secrets(data: Any) -> Any:
    """
    Recursively masks credentials, API keys, and sensitive tokens.
    Guarantees secrets are never stored in plain text in approvals.approved_params_json.
    """
    if isinstance(data, dict):
        masked: Dict[str, Any] = {}
        for k, v in data.items():
            if SECRET_KEY_PATTERNS.search(str(k)):
                masked[k] = "[MASKED]"
            else:
                masked[k] = mask_secrets(v)
        return masked
    elif isinstance(data, _list):
        return [mask_secrets(item) for item in data]
    elif isinstance(data, str):
        val = data
        for pat in SECRET_VALUE_PATTERNS:
            val = pat.sub("[MASKED]", val)
        return val
    return data


# ---------------------------------------------------------------------------
# Sensitive parameters extraction per tool
# ---------------------------------------------------------------------------
def extract_email_domain(to_val: Any) -> str:
    """Extracts lowercase domain(s) from email addresses."""
    if isinstance(to_val, _list):
        domains = [extract_email_domain(item) for item in to_val if item]
        return ",".join(sorted(set(d for d in domains if d)))
    if not isinstance(to_val, str):
        return ""
    s = to_val.strip()
    if "@" in s:
        domain = s.split("@")[-1].strip().lower().rstrip(">").strip()
        return domain
    return s.lower()


def extract_sql_statement_type_and_table(params: Dict[str, Any]) -> Tuple[str, str]:
    """
    Extracts SQL statement type (SELECT, DROP, UPDATE, etc.) and primary table name.
    """
    stmt_type = str(params.get("statement_type", "")).strip().upper()
    table = str(params.get("table", "")).strip().lower()

    sql = params.get("query") or params.get("sql") or ""
    if isinstance(sql, str) and sql.strip():
        sql_clean = sql.strip()
        # Remove SQL comments
        sql_clean = re.sub(r"--.*$", "", sql_clean, flags=re.MULTILINE)
        sql_clean = re.sub(r"/\*.*?\*/", "", sql_clean, flags=re.DOTALL).strip()

        words = sql_clean.split()
        if words and not stmt_type:
            stmt_type = words[0].upper()

        if not table:
            m_ddl = re.search(
                r"\b(?:DROP|TRUNCATE|ALTER|CREATE)\s+TABLE\s+(?:IF\s+(?:NOT\s+)?EXISTS\s+)?([`\"'\[]?[\w.]+[`\"'\]]?)",
                sql_clean,
                re.IGNORECASE,
            )
            if m_ddl:
                table = m_ddl.group(1)
            elif stmt_type == "TRUNCATE":
                m_trunc = re.search(r"\bTRUNCATE\s+(?:TABLE\s+)?([`\"'\[]?[\w.]+[`\"'\]]?)", sql_clean, re.IGNORECASE)
                if m_trunc:
                    table = m_trunc.group(1)
            elif stmt_type in ("SELECT", "DELETE"):
                m_from = re.search(r"\bFROM\s+([`\"'\[]?[\w.]+[`\"'\]]?)", sql_clean, re.IGNORECASE)
                if m_from:
                    table = m_from.group(1)
            elif stmt_type == "UPDATE":
                m_upd = re.search(r"\bUPDATE\s+([`\"'\[]?[\w.]+[`\"'\]]?)", sql_clean, re.IGNORECASE)
                if m_upd:
                    table = m_upd.group(1)
            elif stmt_type == "INSERT":
                m_ins = re.search(r"\bINSERT\s+INTO\s+([`\"'\[]?[\w.]+[`\"'\]]?)", sql_clean, re.IGNORECASE)
                if m_ins:
                    table = m_ins.group(1)

            if table:
                table = table.strip("`\"'[]").lower()

    return stmt_type, table


def extract_sensitive_params(tool: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts canonical sensitive parameters per tool for cryptographic hash binding:
      - payments.send    -> recipient, amount (as integer paise), currency
      - email.send       -> to domain, has_attachment
      - database.run_sql -> statement type, table
    """
    tool_clean = (tool or "").strip().lower()

    if tool_clean == "payments.send":
        recipient = (
            params.get("recipient")
            or params.get("recipient_id")
            or params.get("payee")
            or params.get("supplier")
            or params.get("vendor")
            or ""
        )
        amt_raw = params.get("amount") if "amount" in params else params.get("amount_paise", 0)
        curr = params.get("currency", "INR")
        return {
            "amount": parse_money_to_paise(amt_raw),
            "currency": str(curr).strip().upper(),
            "recipient": normalize_recipient(str(recipient)) if recipient else "",
        }

    elif tool_clean == "email.send":
        to_val = params.get("to") or params.get("recipient") or params.get("email") or ""
        has_att = bool(params.get("has_attachment") or params.get("attachments"))
        return {
            "has_attachment": has_att,
            "to_domain": extract_email_domain(to_val),
        }

    elif tool_clean == "database.run_sql":
        stmt_type, table = extract_sql_statement_type_and_table(params)
        return {
            "statement_type": stmt_type,
            "table": table,
        }

    else:
        # Fallback for custom/unregistered tools
        return normalize_params(params)


# ---------------------------------------------------------------------------
# ApprovalDict entity wrapper (supports dict indexing AND dot notation)
# ---------------------------------------------------------------------------
class ApprovalDict(dict):
    """
    Dictionary representing an approval row that supports both:
      - Dictionary access: row["status"], row["id"]
      - Attribute access:  row.status, row.id
    """

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"'ApprovalDict' has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value

    def to_model(self) -> Approval:
        return Approval(**self)

    def model_dump(self) -> Dict[str, Any]:
        return dict(self)

    def dict(self) -> Dict[str, Any]:
        return dict(self)


# ---------------------------------------------------------------------------
# Field-Level Diff Helper (shows UI exactly what changed)
# ---------------------------------------------------------------------------
def diff(
    approved_params: Union[str, Dict[str, Any]],
    attempted_params: Union[str, Dict[str, Any]],
    tool: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Compares approved parameters against attempted parameters and returns
    a list of field-level differences:
      [{"field": <name>, "approved": <val>, "attempted": <val>}, ...]

    Normalizes recipient and monetary values so surface-level formatting
    differences (e.g. whitespace, float vs paise) are not flagged as differences.
    """
    if isinstance(approved_params, str):
        try:
            approved_dict = json.loads(approved_params)
        except Exception:
            approved_dict = {}
    elif isinstance(approved_params, dict):
        approved_dict = approved_params
    else:
        approved_dict = {}

    if isinstance(attempted_params, str):
        try:
            attempted_dict = json.loads(attempted_params)
        except Exception:
            attempted_dict = {}
    elif isinstance(attempted_params, dict):
        attempted_dict = attempted_params
    else:
        attempted_dict = {}

    diffs: List[Dict[str, Any]] = []

    # If tool is known, first compare sensitive parameters
    if tool:
        sens_app = extract_sensitive_params(tool, approved_dict)
        sens_att = extract_sensitive_params(tool, attempted_dict)
        all_sens_keys = sorted(set(sens_app.keys()) | set(sens_att.keys()))

        for k in all_sens_keys:
            v_app = sens_app.get(k)
            v_att = sens_att.get(k)
            if v_app != v_att:
                # Provide human-readable field name and values
                display_field = k
                display_app = approved_dict.get(k, v_app)
                display_att = attempted_dict.get(k, v_att)
                diffs.append({
                    "field": display_field,
                    "approved": display_app,
                    "attempted": display_att,
                })
        if diffs:
            return diffs

    # General parameter diffing across all keys
    all_keys = sorted(set(approved_dict.keys()) | set(attempted_dict.keys()))
    checked_keys = set()

    for k in all_keys:
        if k in checked_keys:
            continue

        # Recipient-like fields
        if k in ("recipient", "recipient_id", "payee", "supplier", "vendor"):
            v_app = approved_dict.get(k)
            v_att = attempted_dict.get(k)
            norm_app = normalize_recipient(str(v_app)) if v_app is not None else None
            norm_att = normalize_recipient(str(v_att)) if v_att is not None else None
            if norm_app != norm_att:
                diffs.append({
                    "field": "recipient",
                    "approved": v_app,
                    "attempted": v_att,
                })
            checked_keys.add(k)
            continue

        # Monetary fields
        if k in ("amount", "amount_paise"):
            app_amt = approved_dict.get("amount") if "amount" in approved_dict else approved_dict.get("amount_paise")
            att_amt = attempted_dict.get("amount") if "amount" in attempted_dict else attempted_dict.get("amount_paise")
            try:
                paise_app = parse_money_to_paise(app_amt) if app_amt is not None else None
            except Exception:
                paise_app = app_amt
            try:
                paise_att = parse_money_to_paise(att_amt) if att_amt is not None else None
            except Exception:
                paise_att = att_amt

            if paise_app != paise_att:
                diffs.append({
                    "field": "amount",
                    "approved": app_amt,
                    "attempted": att_amt,
                })
            checked_keys.add("amount")
            checked_keys.add("amount_paise")
            continue

        # Currency
        if k == "currency":
            c_app = str(approved_dict.get(k, "")).strip().upper() if approved_dict.get(k) is not None else None
            c_att = str(attempted_dict.get(k, "")).strip().upper() if attempted_dict.get(k) is not None else None
            if c_app != c_att:
                diffs.append({
                    "field": "currency",
                    "approved": approved_dict.get(k),
                    "attempted": attempted_dict.get(k),
                })
            checked_keys.add(k)
            continue

        # Generic field comparison
        val_app = approved_dict.get(k)
        val_att = attempted_dict.get(k)
        if val_app != val_att:
            diffs.append({
                "field": k,
                "approved": val_app,
                "attempted": val_att,
            })
        checked_keys.add(k)

    return diffs


# ---------------------------------------------------------------------------
# Core Approvals CRUD and State Machine
# ---------------------------------------------------------------------------
def create(
    *args,
    db_path: Optional[str] = None,
    clock: Optional[Any] = None,
    ttl_seconds: Optional[int] = None,
    **kwargs,
) -> ApprovalDict:
    """
    Creates a PENDING approval row storing:
      - approved_params_json: Human-readable JSON with credentials/secrets masked
      - approved_hash: SHA-256 of canonical sensitive params
      - created_at: ISO8601 UTC timestamp
      - expires_at: created_at + APPROVAL_TTL_SECONDS
      - status: 'pending'

    Flexible call signatures supported:
      create(agent_id, task_id, tool, params)
      create(agent_id, task_id, tool, params, db_path=..., clock=...)
      create(db_path, agent_id, task_id, tool, params, clock=...)
    """
    # Parse positional vs keyword arguments
    if len(args) == 5:
        target_db, agent_id, task_id, tool, params = args
    elif len(args) == 4:
        agent_id, task_id, tool, params = args
        target_db = db_path
    elif len(args) == 0:
        agent_id = kwargs["agent_id"]
        task_id = kwargs["task_id"]
        tool = kwargs["tool"]
        params = kwargs.get("params", {})
        target_db = kwargs.get("db_path", db_path)
    else:
        raise ValueError(
            f"Invalid arguments for approvals.create(). Expected (agent_id, task_id, tool, params) "
            f"or (db_path, agent_id, task_id, tool, params), got {len(args)} positional arguments."
        )

    if target_db is None:
        target_db = kwargs.get("db_path") or db_path or DB_PATH

    effective_clock = clock or kwargs.get("clock")
    effective_ttl = ttl_seconds if ttl_seconds is not None else kwargs.get("ttl_seconds", APPROVAL_TTL_SECONDS)

    current_time = now(effective_clock)
    expires_time = current_time + timedelta(seconds=effective_ttl)

    # Canonical sensitive parameter hashing
    sensitive_params = extract_sensitive_params(tool, params)
    approved_hash = canonical_hash(sensitive_params)

    # Human-readable parameter storage with secrets masked
    masked_params = mask_secrets(normalize_params(params))
    approved_params_json = json.dumps(masked_params, sort_keys=True)

    approval_id = f"APR-{uuid.uuid4().hex[:8].upper()}"
    created_at_iso = current_time.isoformat()
    expires_at_iso = expires_time.isoformat()

    conn = get_connection(target_db)
    try:
        conn.execute(
            """
            INSERT INTO approvals
              (id, agent_id, task_id, tool, approved_params_json, approved_hash,
               status, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            """,
            (
                approval_id,
                agent_id,
                task_id,
                tool,
                approved_params_json,
                approved_hash,
                created_at_iso,
                expires_at_iso,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return ApprovalDict({
        "id": approval_id,
        "agent_id": agent_id,
        "task_id": task_id,
        "tool": tool,
        "approved_params_json": approved_params_json,
        "approved_hash": approved_hash,
        "status": "pending",
        "created_at": created_at_iso,
        "approved_at": None,
        "expires_at": expires_at_iso,
        "revoked_at": None,
        "used_at": None,
    })


def get(
    approval_id: str,
    db_path: Optional[str] = None,
) -> Optional[ApprovalDict]:
    """Retrieves an approval by ID, or returns None if not found."""
    target_db = db_path or DB_PATH
    conn = get_connection(target_db)
    try:
        row = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        if not row:
            return None
        return ApprovalDict(dict(row))
    finally:
        conn.close()


get_approval = get


def approve(
    *args,
    db_path: Optional[str] = None,
    clock: Optional[Any] = None,
    **kwargs,
) -> Optional[ApprovalDict]:
    """
    Transitions approval from pending → approved.
    Sets approved_at to current timestamp.

    Supports:
      approve(id)
      approve(id, db_path=..., clock=...)
      approve(db_path, id, clock=...)
    """
    if len(args) == 2:
        target_db, approval_id = args
    elif len(args) == 1:
        approval_id = args[0]
        target_db = db_path
    elif len(args) == 0:
        approval_id = kwargs.get("id") or kwargs.get("approval_id")
        target_db = kwargs.get("db_path", db_path)
    else:
        raise ValueError("Invalid arguments for approve()")

    if target_db is None:
        target_db = DB_PATH

    effective_clock = clock or kwargs.get("clock")
    current_time = now(effective_clock).isoformat()

    conn = get_connection(target_db)
    try:
        cur = conn.execute(
            """
            UPDATE approvals
            SET status = 'approved', approved_at = ?
            WHERE id = ? AND status = 'pending'
            """,
            (current_time, approval_id),
        )
        conn.commit()
    finally:
        conn.close()

    return get(approval_id, db_path=target_db)


def reject(
    *args,
    db_path: Optional[str] = None,
    clock: Optional[Any] = None,
    **kwargs,
) -> Optional[ApprovalDict]:
    """
    Transitions approval from pending → rejected.

    Supports:
      reject(id)
      reject(id, db_path=...)
      reject(db_path, id)
    """
    if len(args) == 2:
        target_db, approval_id = args
    elif len(args) == 1:
        approval_id = args[0]
        target_db = db_path
    elif len(args) == 0:
        approval_id = kwargs.get("id") or kwargs.get("approval_id")
        target_db = kwargs.get("db_path", db_path)
    else:
        raise ValueError("Invalid arguments for reject()")

    if target_db is None:
        target_db = DB_PATH

    conn = get_connection(target_db)
    try:
        conn.execute(
            """
            UPDATE approvals
            SET status = 'rejected'
            WHERE id = ? AND status = 'pending'
            """,
            (approval_id,),
        )
        conn.commit()
    finally:
        conn.close()

    return get(approval_id, db_path=target_db)


def revoke(
    *args,
    db_path: Optional[str] = None,
    clock: Optional[Any] = None,
    **kwargs,
) -> Optional[ApprovalDict]:
    """
    Revokes an approval: sets revoked_at timestamp and status='revoked'.

    Supports:
      revoke(id)
      revoke(id, db_path=..., clock=...)
      revoke(db_path, id, clock=...)
    """
    if len(args) == 2:
        target_db, approval_id = args
    elif len(args) == 1:
        approval_id = args[0]
        target_db = db_path
    elif len(args) == 0:
        approval_id = kwargs.get("id") or kwargs.get("approval_id")
        target_db = kwargs.get("db_path", db_path)
    else:
        raise ValueError("Invalid arguments for revoke()")

    if target_db is None:
        target_db = DB_PATH

    effective_clock = clock or kwargs.get("clock")
    current_time = now(effective_clock).isoformat()

    conn = get_connection(target_db)
    try:
        conn.execute(
            """
            UPDATE approvals
            SET status = 'revoked', revoked_at = ?
            WHERE id = ? AND status IN ('pending', 'approved')
            """,
            (current_time, approval_id),
        )
        conn.commit()
    finally:
        conn.close()

    return get(approval_id, db_path=target_db)


def list_approvals(
    status: Optional[str] = None,
    db_path: Optional[str] = None,
) -> List[ApprovalDict]:
    """
    Lists approval rows, optionally filtered by status ('pending', 'approved', etc.).
    Returns rows ordered by created_at DESC.
    """
    target_db = db_path or DB_PATH
    conn = get_connection(target_db)
    try:
        if status:
            rows = conn.execute(
                "SELECT * FROM approvals WHERE status = ? ORDER BY created_at DESC",
                (status.lower(),),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM approvals ORDER BY created_at DESC"
            ).fetchall()
        return [ApprovalDict(dict(row)) for row in rows]
    finally:
        conn.close()


# Alias requested in prompt: list(status)
list = list_approvals

__all__ = [
    "APPROVAL_TTL_SECONDS",
    "ApprovalDict",
    "approve",
    "create",
    "diff",
    "extract_email_domain",
    "extract_sensitive_params",
    "extract_sql_statement_type_and_table",
    "get",
    "get_approval",
    "get_clock",
    "list",
    "list_approvals",
    "mask_secrets",
    "now",
    "reject",
    "reset_clock",
    "revoke",
    "set_clock",
]
