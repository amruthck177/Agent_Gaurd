"""
backend/app/policy.py

Rule engine and policy evaluator for AgentGuard 2.0 (plan.md §C6).
Loads active policies from DB, provides SQL statement classification via tokenization,
enforces email domain allowlists, and exposes:
  - load_active_policies(db_path) -> List[Dict[str, Any]]
  - permitted(agent, task, tool) -> bool
  - hard_block(req) -> Optional[str]
  - requires_approval(req) -> Optional[str]
  - classify_sql(sql) -> Dict[str, Any]
  - tokenize_sql(sql) -> List[str]
  - policy_check(...) -> (block_reason, ask_human_reason)  [patchable gateway entry point]
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from app.db import DB_PATH, get_connection
from app.schemas import Decision, ExecuteRequest, parse_money_to_paise

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known tool registry — gateway blocks unknown tools immediately
# ---------------------------------------------------------------------------
TOOL_REGISTRY: Set[str] = {"payments.send", "email.send", "database.run_sql"}

# Known SQL statement keywords
STATEMENT_TYPES: Set[str] = {"SELECT", "INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE"}

# Default email allowlist per plan.md §C6 / db seed
DEFAULT_ALLOWED_EMAIL_DOMAINS: Set[str] = {"internal.corp", "company.com", "example.com"}

# Exact reason strings per plan.md §C2, §C6, §D
REASON_NO_PERMISSION = "Agent lacks write permission"
REASON_DESTRUCTIVE_SQL = "Destructive database operation prohibited"
REASON_OVER_THRESHOLD = "Payment exceeds ₹10,000 limit: human approval required"
REASON_UNKNOWN_EMAIL_DOMAIN = "Sending email to unknown external domain"


# ---------------------------------------------------------------------------
# Database Policy Loader
# ---------------------------------------------------------------------------
def load_active_policies(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """
    Loads all active policies from the policies table in the SQLite database.
    Returns a list of dicts with keys:
      id, agent_id, task_id, tool, condition_json, decision, version, active.
    """
    try:
        conn = get_connection(db_path)
        try:
            cur = conn.cursor()
            rows = cur.execute(
                "SELECT * FROM policies WHERE active = 1 ORDER BY id ASC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("Could not load active policies from %s: %s", db_path, exc)
        return []


def _get_agent_from_db(db_path: str, agent_id: str) -> Optional[Dict[str, Any]]:
    try:
        conn = get_connection(db_path)
        try:
            row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    except Exception:
        return None


def _get_task_from_db(db_path: str, task_id: str) -> Optional[Dict[str, Any]]:
    try:
        conn = get_connection(db_path)
        try:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# SQL Tokenizer & Classifier
# ---------------------------------------------------------------------------
def tokenize_sql(sql: str) -> List[str]:
    """
    Tokenizes SQL statement into a list of uppercase tokens,
    stripping single-line (--) and multi-line (/* */) comments to prevent bypasses.
    """
    if not sql or not isinstance(sql, str):
        return []
    # Strip multi-line comments
    clean = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    # Strip single-line comments
    clean = re.sub(r"--.*$", " ", clean, flags=re.MULTILINE)
    # Tokenize words and non-whitespace punctuation
    raw_tokens = re.findall(r"[A-Za-z0-9_]+|[^\s\w]", clean)
    return [t.upper() for t in raw_tokens]


def classify_sql(sql: str) -> Dict[str, Any]:
    """
    Classifies a SQL string via a simple tokenizer:
      - statement_type: SELECT / INSERT / UPDATE / DELETE / DROP / TRUNCATE / UNKNOWN
      - is_destructive: True if statement contains DROP, TRUNCATE, or is DELETE without WHERE.
      - has_where: True if statement contains a WHERE clause token.
    """
    tokens = tokenize_sql(sql)
    stmt_type = "UNKNOWN"

    for tok in tokens:
        if tok in STATEMENT_TYPES:
            stmt_type = tok
            break
        elif tok.isalpha():
            stmt_type = tok
            break

    has_where = "WHERE" in tokens

    # Plan.md §C6: DROP, TRUNCATE and DELETE without WHERE are hard blocks.
    is_destructive = (
        "DROP" in tokens
        or "TRUNCATE" in tokens
        or (stmt_type == "DELETE" and not has_where)
    )

    return {
        "tokens": tokens,
        "statement_type": stmt_type,
        "is_destructive": is_destructive,
        "has_where": has_where,
    }


# ---------------------------------------------------------------------------
# Email Domain Extractor
# ---------------------------------------------------------------------------
def extract_email_domains(to_val: Any) -> List[str]:
    """Extracts lowercase unique domains from an email address or recipient list."""
    if not to_val:
        return []
    if isinstance(to_val, list):
        res: List[str] = []
        for item in to_val:
            res.extend(extract_email_domains(item))
        return list(dict.fromkeys(res))
    if not isinstance(to_val, str):
        return []

    domains: List[str] = []
    # Handle comma/semicolon separated email lists
    parts = re.split(r"[,;]+", to_val)
    for part in parts:
        clean = part.strip().rstrip(">").strip()
        if "@" in clean:
            domain = clean.split("@")[-1].strip().lower()
            if domain:
                domains.append(domain)
        elif "." in clean:
            domains.append(clean.lower())

    return list(dict.fromkeys(domains))


# ---------------------------------------------------------------------------
# Permission Evaluator: permitted(agent, task, tool)
# ---------------------------------------------------------------------------
def permitted(
    agent: Union[Dict[str, Any], str],
    task: Optional[Union[Dict[str, Any], str]],
    tool: str,
    db_path: str = DB_PATH,
) -> bool:
    """
    Checks if an agent is permitted to execute the given tool on the given task.
    Returns True iff:
      - Agent exists and role is NOT 'reader' (reader-role agents cannot call write tools).
      - Tool is present in agent's permissions_json.
      - If task has allowed_tools defined, tool must be in that list.
    """
    # Resolve agent dict
    if isinstance(agent, str):
        agent_dict = _get_agent_from_db(db_path, agent)
        if not agent_dict:
            return False
    elif isinstance(agent, dict):
        agent_dict = agent
    else:
        return False

    # 1. Role check: reader role cannot execute write tools
    role = agent_dict.get("role", "reader")
    if role == "reader":
        return False

    # 2. Permissions check on agent
    perms: List[str] = []
    try:
        raw_perms = agent_dict.get("permissions_json") or "[]"
        perms = json.loads(raw_perms) if isinstance(raw_perms, str) else list(raw_perms)
    except Exception:
        perms = []

    if tool not in perms and "*" not in perms:
        return False

    # 3. Task scope check if task is supplied
    if task is not None:
        if isinstance(task, str):
            task_dict = _get_task_from_db(db_path, task)
        elif isinstance(task, dict):
            task_dict = task
        else:
            task_dict = None

        if task_dict:
            try:
                raw_scope = task_dict.get("scope_json") or "{}"
                scope = json.loads(raw_scope) if isinstance(raw_scope, str) else dict(raw_scope)
                allowed_tools = scope.get("allowed_tools")
                if allowed_tools is not None and tool not in allowed_tools and "*" not in allowed_tools:
                    return False
            except Exception:
                pass

    return True


# Backward compatibility helper
def agent_has_permission(agent: Dict[str, Any], tool: str) -> bool:
    """Alias for permitted(agent, None, tool)."""
    return permitted(agent, None, tool)


# ---------------------------------------------------------------------------
# Request Unpacker Helper
# ---------------------------------------------------------------------------
def _unpack_request(
    req: Any,
    *args: Any,
    **kwargs: Any,
) -> Tuple[str, Optional[Dict[str, Any]], str, Dict[str, Any], Optional[str]]:
    """
    Normalizes caller arguments into:
      (db_path, agent_dict, tool, params, task_id)
    Supports both:
      - hard_block(req) / requires_approval(req) with ExecuteRequest or dict
      - hard_block(db_path, agent, tool, params) legacy/test calls
    """
    # Check if called as (db_path, agent, tool, params, [task_id])
    if isinstance(req, str) and len(args) >= 3:
        db_path = req
        agent_arg = args[0]
        tool = str(args[1])
        params = args[2] if isinstance(args[2], dict) else {}
        task_id = kwargs.get("task_id") or (args[3] if len(args) > 3 and isinstance(args[3], str) else None)

        if isinstance(agent_arg, dict):
            agent_dict = agent_arg
        else:
            agent_dict = _get_agent_from_db(db_path, str(agent_arg))
        return db_path, agent_dict, tool, params, task_id

    # Called with a request object (ExecuteRequest or dict)
    db_path = kwargs.get("db_path", DB_PATH)
    if isinstance(req, dict):
        agent_id = req.get("agent_id", "")
        task_id = req.get("task_id")
        tool = req.get("tool", "")
        params = req.get("params", {})
    else:
        agent_id = getattr(req, "agent_id", "")
        task_id = getattr(req, "task_id", None)
        tool = getattr(req, "tool", "")
        params = getattr(req, "params", {})

    agent_dict = _get_agent_from_db(db_path, agent_id) if agent_id else None
    return db_path, agent_dict, tool, params, task_id


# ---------------------------------------------------------------------------
# Hard-block Evaluator: hard_block(req)
# ---------------------------------------------------------------------------
def hard_block(req: Any, *args: Any, **kwargs: Any) -> Optional[str]:
    """
    Evaluates whether a request violates hard security policies.
    Returns the block reason string if blocked, None otherwise.

    Hard blocks (plan.md §C6):
      1. Agent lacks write permission (role reader or missing tool permission)
      2. Destructive SQL operations (DROP, TRUNCATE, DELETE without WHERE)
      3. Active DB policies with decision == 'BLOCK'
    """
    db_path, agent, tool, params, task_id = _unpack_request(req, *args, **kwargs)

    # 1. Permission check
    if agent is None:
        return "Unknown agent"

    if not permitted(agent, task_id, tool, db_path=db_path):
        return REASON_NO_PERMISSION

    # 2. Database destructive operation checks
    if tool == "database.run_sql":
        sql = str(params.get("query") or params.get("sql") or "")
        classification = classify_sql(sql)
        if classification["is_destructive"]:
            return REASON_DESTRUCTIVE_SQL

    # 3. Active DB policies
    policies = load_active_policies(db_path)
    for pol in policies:
        if pol.get("decision") != Decision.BLOCK.value and pol.get("decision") != "BLOCK":
            continue

        p_tool = pol.get("tool")
        if p_tool != "*" and p_tool != tool:
            continue

        p_agent = pol.get("agent_id")
        if p_agent and agent and agent.get("id") != p_agent:
            continue

        p_task = pol.get("task_id")
        if p_task and task_id != p_task:
            continue

        # Condition checks
        try:
            cond = json.loads(pol.get("condition_json") or "{}")
        except Exception:
            cond = {}

        if cond.get("type") == "disallow_write_tools" or cond.get("role") == "reader":
            if agent.get("role") == "reader":
                return cond.get("description", REASON_NO_PERMISSION)

        if tool == "database.run_sql" and (cond.get("forbidden_keywords") or cond.get("delete_requires_where")):
            sql = str(params.get("query") or params.get("sql") or "")
            if classify_sql(sql)["is_destructive"]:
                return cond.get("description", REASON_DESTRUCTIVE_SQL)

    return None


# ---------------------------------------------------------------------------
# Approval-required Evaluator: requires_approval(req)
# ---------------------------------------------------------------------------
def requires_approval(req: Any, *args: Any, **kwargs: Any) -> Optional[str]:
    """
    Evaluates whether a request requires human approval (ASK_HUMAN).
    Returns the reason string if approval is required, None if ALLOW.

    Requires approval (plan.md §C6):
      1. payments.send amount > ₹10,000 (1,000,000 paise)
      2. email.send to an external domain not in the allowlist
      3. Active DB policies with decision == 'ASK_HUMAN'
    """
    db_path, agent, tool, params, task_id = _unpack_request(req, *args, **kwargs)

    # Load active policies to check configured thresholds and domain allowlists
    policies = load_active_policies(db_path)

    # 1. payments.send threshold check
    if tool == "payments.send":
        amt_raw = params.get("amount") if "amount" in params else params.get("amount_paise")
        if amt_raw is not None:
            try:
                paise = parse_money_to_paise(amt_raw)
            except Exception:
                paise = 0

            # Find configured threshold from DB policies or default to 1,000,000 paise
            threshold_paise = 1000000
            threshold_desc = REASON_OVER_THRESHOLD

            for pol in policies:
                if pol.get("tool") == "payments.send" and pol.get("decision") in ("ASK_HUMAN", Decision.ASK_HUMAN.value):
                    try:
                        cond = json.loads(pol.get("condition_json") or "{}")
                        if cond.get("operator") == ">" and "value" in cond:
                            threshold_paise = int(cond["value"])
                            threshold_desc = cond.get("reason") or REASON_OVER_THRESHOLD
                            break
                    except Exception:
                        pass

            if paise > threshold_paise:
                return REASON_OVER_THRESHOLD

    # 2. email.send domain allowlist check
    if tool == "email.send":
        to_val = params.get("to") or params.get("recipient")
        domains = extract_email_domains(to_val)

        allowed_domains = set(DEFAULT_ALLOWED_EMAIL_DOMAINS)
        domain_desc = REASON_UNKNOWN_EMAIL_DOMAIN

        for pol in policies:
            if pol.get("tool") == "email.send" and pol.get("decision") in ("ASK_HUMAN", Decision.ASK_HUMAN.value):
                try:
                    cond = json.loads(pol.get("condition_json") or "{}")
                    if "allowed_domains" in cond:
                        allowed_domains = set(d.lower() for d in cond["allowed_domains"])
                        domain_desc = cond.get("description", REASON_UNKNOWN_EMAIL_DOMAIN)
                        break
                except Exception:
                    pass

        # If any recipient domain is not in the allowlist -> ASK_HUMAN
        for dom in domains:
            if dom not in allowed_domains:
                return domain_desc

    # 3. Generic DB policies with decision == ASK_HUMAN
    for pol in policies:
        if pol.get("decision") not in ("ASK_HUMAN", Decision.ASK_HUMAN.value):
            continue

        p_tool = pol.get("tool")
        if p_tool != "*" and p_tool != tool:
            continue

        p_agent = pol.get("agent_id")
        if p_agent and agent and agent.get("id") != p_agent:
            continue

        p_task = pol.get("task_id")
        if p_task and task_id != p_task:
            continue

        try:
            cond = json.loads(pol.get("condition_json") or "{}")
        except Exception:
            cond = {}

        # Evaluate condition if applicable
        if cond.get("field") == "amount_paise" and cond.get("operator") == ">":
            amt_raw = params.get("amount") if "amount" in params else params.get("amount_paise")
            if amt_raw is not None:
                try:
                    paise = parse_money_to_paise(amt_raw)
                    if paise > int(cond.get("value", 1000000)):
                        return cond.get("reason") or REASON_OVER_THRESHOLD
                except Exception:
                    pass

    return None


# ---------------------------------------------------------------------------
# Patchable gateway entry point: policy_check(...)
# ---------------------------------------------------------------------------
def policy_check(
    db_path: str,
    agent: Dict[str, Any],
    tool: str,
    params: Dict[str, Any],
    task_id: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Combined policy evaluation entry point called by gateway.py.
    Returns (block_reason, ask_human_reason).
    This function is monkeypatched in test_gateway_failure_fails_closed.
    """
    block = hard_block(db_path, agent, tool, params, task_id=task_id)
    if block:
        return (block, None)

    ask = requires_approval(db_path, agent, tool, params, task_id=task_id)
    return (None, ask)
