"""
backend/app/audit.py

Cryptographically verifiable SHA-256 hash-chained audit log for AgentGuard 2.0 (plan.md §C3).

Key guarantees:
  - hash = SHA256(prev_hash + canonical_json(record_without_hash))
  - Genesis prev_hash = 64 zeros ("0" * 64)
  - Secrets (sk-..., api keys, bearer tokens, full account numbers -> keep last 4)
    are masked BEFORE hashing and storing.
  - Appends are strictly serialized across threads and processes via a threading Lock
    and SQLite 'BEGIN IMMEDIATE' transaction.
  - verify() -> {ok, checked, broken_at} recomputes the entire chain from genesis.
  - list(filters) -> queries audit records with optional filters.
  - export_csv() -> exports audit records as standard CSV format.
  - tamper(record_id) -> [DEMO ONLY] directly alters a stored record in SQL without
    updating hashes to prove cryptographic tamper detection.
"""

from __future__ import annotations

import builtins
import csv
import hashlib
import io
import json
import logging
import re
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

_builtin_list = builtins.list

from app.db import DB_PATH, get_connection
from app.schemas import AuditVerifyResponse, Decision

logger = logging.getLogger(__name__)

GENESIS_HASH = "0" * 64

# Global lock to serialize hash-chain appends in multi-threaded environments
_APPEND_LOCK = threading.Lock()

# ---------------------------------------------------------------------------
# Secret Masking Patterns & Helpers (plan.md §C3)
# ---------------------------------------------------------------------------
SECRET_KEY_PATTERNS = re.compile(
    r"(?:api[_-]?key|secret|token|password|auth|credential|access[_-]?token|private[_-]?key)",
    re.IGNORECASE,
)

ACCOUNT_KEY_PATTERNS = re.compile(
    r"(?:account[_-]?num(?:ber)?|acc[_-]?no|card[_-]?num(?:ber)?|iban|bank[_-]?acc(?:ount)?)",
    re.IGNORECASE,
)

SK_KEY_PATTERN = re.compile(r"sk-[a-zA-Z0-9_\-]{6,}")
BEARER_PATTERN = re.compile(r"Bearer\s+[a-zA-Z0-9_\-\.]{6,}", re.IGNORECASE)
ACCOUNT_NUMBER_PATTERN = re.compile(r"\b(?:\d[ -]?){8,17}\d\b")


def mask_account_number(val: Any) -> str:
    """
    Masks a full account or card number while preserving the last 4 digits.
    Example: '123456789012' -> '********9012'
    """
    s = str(val)
    digits = re.sub(r"[ -]", "", s)
    if len(digits) >= 5:
        return "*" * (len(digits) - 4) + digits[-4:]
    return s


def mask_secrets(data: Any) -> Any:
    """
    Recursively masks sensitive credentials, tokens, API keys, and account numbers.
    Rules:
      - Keys matching SECRET_KEY_PATTERNS -> '[MASKED]'
      - Keys matching ACCOUNT_KEY_PATTERNS -> mask keeping last 4 digits
      - sk-... pattern in strings -> '[MASKED]'
      - Bearer tokens in strings -> 'Bearer [MASKED]'
      - 9-18 digit account numbers in strings -> mask keeping last 4 digits
    """
    if isinstance(data, dict):
        masked: Dict[str, Any] = {}
        for k, v in data.items():
            k_str = str(k)
            if ACCOUNT_KEY_PATTERNS.search(k_str):
                masked[k] = mask_account_number(v)
            elif SECRET_KEY_PATTERNS.search(k_str):
                masked[k] = "[MASKED]"
            else:
                masked[k] = mask_secrets(v)
        return masked

    elif isinstance(data, _builtin_list):
        return [mask_secrets(item) for item in data]

    elif isinstance(data, str):
        val = data
        # Mask sk-... keys
        val = SK_KEY_PATTERN.sub("[MASKED]", val)
        # Mask Bearer tokens
        val = BEARER_PATTERN.sub("Bearer [MASKED]", val)

        # Mask standalone 9-18 digit account numbers in text (preserving last 4)
        def _repl_acc(match: re.Match) -> str:
            m_text = match.group(0)
            digits = re.sub(r"[ -]", "", m_text)
            if 9 <= len(digits) <= 18:
                return "*" * (len(digits) - 4) + digits[-4:]
            return m_text

        val = ACCOUNT_NUMBER_PATTERN.sub(_repl_acc, val)
        return val

    return data


# ---------------------------------------------------------------------------
# Cryptographic Hash Computation
# ---------------------------------------------------------------------------
def _compute_hash(prev_hash: str, record_without_hash: Dict[str, Any]) -> str:
    """
    Computes SHA-256 of (prev_hash + canonical_json(record_without_hash)).
    Keys are strictly sorted with no whitespace separators for deterministic hashing.
    """
    clean_record = {k: v for k, v in record_without_hash.items() if k != "hash"}
    canonical_json = json.dumps(clean_record, sort_keys=True, separators=(",", ":"))
    raw = prev_hash + canonical_json
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _mask_params_to_json(params: Any) -> str:
    """Masks secrets and returns sorted-key compact JSON string."""
    if isinstance(params, str):
        try:
            parsed = json.loads(params)
            masked = mask_secrets(parsed)
            return json.dumps(masked, sort_keys=True, separators=(",", ":"))
        except Exception:
            # Plain string
            masked_str = mask_secrets(params)
            return json.dumps(masked_str, separators=(",", ":"))
    elif isinstance(params, dict):
        masked = mask_secrets(params)
        return json.dumps(masked, sort_keys=True, separators=(",", ":"))
    else:
        masked = mask_secrets(params)
        return json.dumps(masked, sort_keys=True, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Unpack Arguments Helper
# ---------------------------------------------------------------------------
def _unpack_append_args(
    record: Any = None,
    *args: Any,
    **kwargs: Any,
) -> Tuple[str, Dict[str, Any]]:
    """
    Normalizes append() calls whether called as:
      - append(record_dict, db_path=...)
      - append(db_path, *, ts=..., agent_id=..., ...)
      - append(*, ts=..., agent_id=..., db_path=...)
    """
    if isinstance(record, str) and not kwargs.get("agent_id"):
        # First argument is db_path
        db_path = record
        data = dict(kwargs)
    elif isinstance(record, dict):
        db_path = kwargs.get("db_path", DB_PATH)
        data = {**record, **{k: v for k, v in kwargs.items() if k != "db_path"}}
    elif hasattr(record, "model_dump"):
        db_path = kwargs.get("db_path", DB_PATH)
        data = {**record.model_dump(), **{k: v for k, v in kwargs.items() if k != "db_path"}}
    elif isinstance(record, str) and (kwargs.get("agent_id") or kwargs.get("tool")):
        db_path = record
        data = dict(kwargs)
    else:
        db_path = kwargs.get("db_path", DB_PATH)
        data = dict(kwargs)

    return db_path, data


# ---------------------------------------------------------------------------
# Serialized Append: append(record) -> id
# ---------------------------------------------------------------------------
def append(
    record: Any = None,
    *args: Any,
    **kwargs: Any,
) -> int:
    """
    Appends a new decision record to the audit hash chain and returns the new row id.
    Appends are serialized via an internal threading lock and SQLite BEGIN IMMEDIATE.
    Secrets in params are masked BEFORE hashing and storing.
    """
    db_path, data = _unpack_append_args(record, *args, **kwargs)

    ts = data.get("ts") or datetime.now(timezone.utc).isoformat()
    agent_id = str(data.get("agent_id", ""))
    task_id = str(data.get("task_id", ""))
    tool = str(data.get("tool", ""))

    raw_params = data.get("params")
    if raw_params is None and "params_masked" in data:
        raw_params = data["params_masked"]
    params_masked = _mask_params_to_json(raw_params or {})

    decision_val = data.get("decision", "BLOCK")
    if isinstance(decision_val, Decision):
        decision_str = decision_val.value
    else:
        decision_str = str(decision_val)

    reason = str(data.get("reason", ""))
    approval_id = data.get("approval_id")
    executed_int = 1 if data.get("executed") else 0

    # Serialization: acquiring Python thread lock and SQLite transaction lock
    with _APPEND_LOCK:
        conn = get_connection(db_path)
        try:
            conn.execute("BEGIN IMMEDIATE;")

            # 1. Get the latest previous hash (or genesis if table is empty)
            row = conn.execute("SELECT hash FROM audit ORDER BY id DESC LIMIT 1").fetchone()
            prev_hash = row["hash"] if row else GENESIS_HASH

            # 2. Build record_without_hash
            record_without_hash = {
                "ts": ts,
                "agent_id": agent_id,
                "task_id": task_id,
                "tool": tool,
                "params_masked": params_masked,
                "decision": decision_str,
                "reason": reason,
                "approval_id": approval_id,
                "executed": executed_int,
                "prev_hash": prev_hash,
            }

            # 3. Compute hash = SHA256(prev_hash + canonical_json(record_without_hash))
            new_hash = _compute_hash(prev_hash, record_without_hash)

            # 4. Insert into database
            cur = conn.execute(
                """
                INSERT INTO audit (
                    ts, agent_id, task_id, tool, params_masked, decision,
                    reason, approval_id, executed, prev_hash, hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts,
                    agent_id,
                    task_id,
                    tool,
                    params_masked,
                    decision_str,
                    reason,
                    approval_id,
                    executed_int,
                    prev_hash,
                    new_hash,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Verify Full Chain: verify() -> {ok, checked, broken_at}
# ---------------------------------------------------------------------------
def verify(db_path: str = DB_PATH) -> AuditVerifyResponse:
    """
    Recomputes the cryptographic hash chain from genesis ("0" * 64) and returns:
      {ok: bool, checked: int, broken_at: Optional[int]}

    broken_at is the database id of the first record where:
      - prev_hash linkage is broken, OR
      - stored hash != SHA256(prev_hash + canonical_json(record_without_hash))
    """
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT id, ts, agent_id, task_id, tool, params_masked, decision,
                   reason, approval_id, executed, prev_hash, hash
            FROM audit
            ORDER BY id ASC
            """
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return AuditVerifyResponse(ok=True, checked=0, broken_at=None)

    expected_prev = GENESIS_HASH

    for i, row in enumerate(rows):
        row_id = row["id"]
        row_prev = row["prev_hash"]
        row_hash = row["hash"]

        # 1. Check prev_hash matches previous record's hash
        if row_prev != expected_prev:
            return AuditVerifyResponse(ok=False, checked=i, broken_at=row_id)

        # 2. Recompute hash
        record_without_hash = {
            "ts": row["ts"],
            "agent_id": row["agent_id"],
            "task_id": row["task_id"],
            "tool": row["tool"],
            "params_masked": row["params_masked"],
            "decision": row["decision"],
            "reason": row["reason"],
            "approval_id": row["approval_id"],
            "executed": int(row["executed"]),
            "prev_hash": row_prev,
        }
        computed = _compute_hash(row_prev, record_without_hash)

        if computed != row_hash:
            return AuditVerifyResponse(ok=False, checked=i, broken_at=row_id)

        expected_prev = row_hash

    return AuditVerifyResponse(ok=True, checked=len(rows), broken_at=None)


# ---------------------------------------------------------------------------
# List Audit Records: list(filters)
# ---------------------------------------------------------------------------
def list(
    filters: Optional[Dict[str, Any]] = None,
    db_path: str = DB_PATH,
    **kwargs: Any,
) -> List[Dict[str, Any]]:
    """
    Queries audit log records with optional filtering.
    Filters supported:
      agent_id, task_id, tool, decision, executed, approval_id, since, until, limit, offset, order.
    """
    merged_filters: Dict[str, Any] = {}
    if filters and isinstance(filters, dict):
        merged_filters.update(filters)
    merged_filters.update(kwargs)

    clauses: List[str] = []
    params: List[Any] = []

    if "agent_id" in merged_filters and merged_filters["agent_id"]:
        clauses.append("agent_id = ?")
        params.append(merged_filters["agent_id"])

    if "task_id" in merged_filters and merged_filters["task_id"]:
        clauses.append("task_id = ?")
        params.append(merged_filters["task_id"])

    if "tool" in merged_filters and merged_filters["tool"]:
        clauses.append("tool = ?")
        params.append(merged_filters["tool"])

    if "decision" in merged_filters and merged_filters["decision"]:
        clauses.append("decision = ?")
        params.append(str(merged_filters["decision"]).upper())

    if "executed" in merged_filters and merged_filters["executed"] is not None:
        clauses.append("executed = ?")
        params.append(1 if merged_filters["executed"] else 0)

    if "approval_id" in merged_filters and merged_filters["approval_id"]:
        clauses.append("approval_id = ?")
        params.append(merged_filters["approval_id"])

    if "since" in merged_filters and merged_filters["since"]:
        clauses.append("ts >= ?")
        params.append(merged_filters["since"])

    if "until" in merged_filters and merged_filters["until"]:
        clauses.append("ts <= ?")
        params.append(merged_filters["until"])

    if "search" in merged_filters and merged_filters["search"]:
        s = f"%{merged_filters['search']}%"
        clauses.append("(reason LIKE ? OR params_masked LIKE ? OR agent_id LIKE ? OR tool LIKE ?)")
        params.extend([s, s, s, s])

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    order_direction = "DESC" if str(merged_filters.get("order", "DESC")).upper() == "DESC" else "ASC"

    query = f"""
        SELECT id, ts, agent_id, task_id, tool, params_masked, decision,
               reason, approval_id, executed, prev_hash, hash
        FROM audit
        {where_sql}
        ORDER BY id {order_direction}
    """

    limit = merged_filters.get("limit")
    if limit is not None:
        query += " LIMIT ?"
        params.append(int(limit))
        offset = merged_filters.get("offset")
        if offset is not None:
            query += " OFFSET ?"
            params.append(int(offset))

    conn = get_connection(db_path)
    try:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# Alias for list()
list_records = list


# ---------------------------------------------------------------------------
# CSV Export: export_csv()
# ---------------------------------------------------------------------------
def export_csv(
    db_path: str = DB_PATH,
    filters: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> str:
    """
    Exports audit records matching filters to a standard CSV string.
    """
    # Fetch in chronological order (ASC)
    query_filters = dict(filters or {})
    query_filters.update(kwargs)
    query_filters["order"] = "ASC"
    query_filters["limit"] = None

    records = list(filters=query_filters, db_path=db_path)

    output = io.StringIO()
    writer = csv.writer(output)

    headers = [
        "id",
        "ts",
        "agent_id",
        "task_id",
        "tool",
        "params_masked",
        "decision",
        "reason",
        "approval_id",
        "executed",
        "prev_hash",
        "hash",
    ]
    writer.writerow(headers)

    for r in records:
        writer.writerow([
            r["id"],
            r["ts"],
            r["agent_id"],
            r["task_id"],
            r["tool"],
            r["params_masked"],
            r["decision"],
            r["reason"],
            r.get("approval_id") or "",
            r["executed"],
            r["prev_hash"],
            r["hash"],
        ])

    return output.getvalue()


# ---------------------------------------------------------------------------
# Demo Tamper Helper: tamper(record_id)
# ---------------------------------------------------------------------------
def tamper(record_id: int, db_path: str = DB_PATH) -> bool:
    """
    [DEMO ONLY] Directly edits a stored decision in SQL without updating hashes.
    Guarded for testing and demonstration of cryptographic verification failure.
    Returns True if the record was found and modified, False otherwise.
    """
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        row = cur.execute("SELECT id, decision FROM audit WHERE id = ?", (record_id,)).fetchone()
        if not row:
            return False

        current_decision = row["decision"]
        new_decision = "BLOCK" if current_decision == "ALLOW" else "ALLOW"
        tampered_reason = f"Tampered record #{record_id} without updating cryptographic hash"

        cur.execute(
            """
            UPDATE audit
            SET decision = ?, reason = ?
            WHERE id = ?
            """,
            (new_decision, tampered_reason, record_id),
        )
        conn.commit()
        return cur.rowcount == 1
    finally:
        conn.close()
