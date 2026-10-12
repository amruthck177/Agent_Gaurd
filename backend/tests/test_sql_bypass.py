"""
backend/tests/test_sql_bypass.py

Security tests for R5: SQL CTE and comment/stacked statement bypass prevention.
Verifies that:
- Destructive operations hidden in CTEs, subqueries, stacked statements,
  or comment-split keywords are BLOCKED.
- Case variations (lowercase, mixed case) are normalized and BLOCKED.
- Legitimate queries (SELECT count(*), literals like 'please delete this',
  and columns named 'deleted_at') are ALLOWED without false blocks.
"""

import pytest

from app.db import get_connection, reset_db, seed_demo
from app.gateway import execute
from app.policy import classify_sql, hard_block
from app.schemas import Decision, ExecuteRequest


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def clean_db(tmp_path):
    db_file = str(tmp_path / "test_sql_bypass.db")
    reset_db(db_file)
    seed_demo(db_file)
    return db_file


# ---------------------------------------------------------------------------
# 1. SQL Classification Tests (Unit)
# ---------------------------------------------------------------------------
def test_cte_delete_bypass_blocked():
    """WITH x AS (DELETE FROM customers) SELECT 1 must be marked destructive."""
    sql = "WITH x AS (DELETE FROM customers) SELECT 1"
    c = classify_sql(sql)
    assert c["is_destructive"] is True, f"Expected destructive for CTE DELETE: {c}"


def test_cte_mutations_blocked():
    """Mutating statements inside CTEs must be marked destructive."""
    c_ins = classify_sql("WITH x AS (INSERT INTO customers (name) VALUES ('evil')) SELECT 1")
    assert c_ins["is_destructive"] is True

    c_upd = classify_sql("WITH x AS (UPDATE customers SET name = 'evil') SELECT 1")
    assert c_upd["is_destructive"] is True

    c_del_where = classify_sql("WITH x AS (DELETE FROM customers WHERE id = 1) SELECT 1")
    assert c_del_where["is_destructive"] is True


def test_stacked_statements_blocked():
    """Stacked statements with destructive operations must be marked destructive."""
    c1 = classify_sql("SELECT 1; DROP TABLE customers")
    assert c1["is_destructive"] is True

    c2 = classify_sql("SELECT 1 WHERE 1=1; DELETE FROM customers")
    assert c2["is_destructive"] is True


def test_comment_split_keywords_blocked():
    """Keywords split by comments like DR/**/OP must be detected and blocked."""
    c_drop = classify_sql("DR/**/OP TABLE customers")
    assert c_drop["is_destructive"] is True

    c_del = classify_sql("DE/**/LETE FROM customers")
    assert c_del["is_destructive"] is True

    c_trunc = classify_sql("TRUN/**/CATE orders")
    assert c_trunc["is_destructive"] is True


def test_case_variations_blocked():
    """Lowercase and mixed-case destructive keywords must be blocked."""
    assert classify_sql("drop table customers")["is_destructive"] is True
    assert classify_sql("DrOp Table customers")["is_destructive"] is True
    assert classify_sql("with x as (delete from customers) select 1")["is_destructive"] is True
    assert classify_sql("select 1; drop table customers")["is_destructive"] is True


def test_alter_table_blocked():
    """ALTER TABLE must be blocked."""
    assert classify_sql("ALTER TABLE customers ADD COLUMN evil TEXT")["is_destructive"] is True
    assert classify_sql("alter table customers drop column city")["is_destructive"] is True


def test_legitimate_queries_allowed():
    """Legitimate queries must not be falsely blocked."""
    # SELECT count(*)
    c1 = classify_sql("SELECT count(*) FROM orders")
    assert c1["is_destructive"] is False

    # String literal containing destructive keyword
    c2 = classify_sql("SELECT 'please delete this' AS note FROM orders")
    assert c2["is_destructive"] is False

    # Column name containing 'delete' as substring
    c3 = classify_sql("SELECT deleted_at FROM orders WHERE deleted_at IS NULL")
    assert c3["is_destructive"] is False

    # Normal allowed statements
    c4 = classify_sql("SELECT id, name FROM customers WHERE id = 1")
    assert c4["is_destructive"] is False

    c5 = classify_sql("UPDATE customers SET city = 'Mangaluru' WHERE id = 2")
    assert c5["is_destructive"] is False

    c6 = classify_sql("DELETE FROM customers WHERE id = 10")
    assert c6["is_destructive"] is False


# ---------------------------------------------------------------------------
# 2. Gateway End-to-End Tests
# ---------------------------------------------------------------------------
def test_gateway_blocks_cte_bypass(clean_db):
    """Gateway must hard-block CTE delete bypass attempt."""
    resp = execute(
        db_path=clean_db,
        agent_id="accounts-agent",
        task_id="task-accounts-1",
        tool="database.run_sql",
        params={"query": "WITH x AS (DELETE FROM customers) SELECT 1", "database": "production"},
    )
    decision = resp.decision if isinstance(resp.decision, str) else resp.decision.value
    assert decision == Decision.BLOCK.value
    assert resp.reason == "Destructive database operation prohibited"
    assert resp.executed is False


def test_gateway_blocks_comment_split_drop(clean_db):
    """Gateway must hard-block DR/**/OP attempt."""
    resp = execute(
        db_path=clean_db,
        agent_id="accounts-agent",
        task_id="task-accounts-1",
        tool="database.run_sql",
        params={"query": "DR/**/OP TABLE customers", "database": "production"},
    )
    decision = resp.decision if isinstance(resp.decision, str) else resp.decision.value
    assert decision == Decision.BLOCK.value
    assert resp.reason == "Destructive database operation prohibited"
    assert resp.executed is False


def test_gateway_allows_legitimate_query_with_literal(clean_db):
    """Gateway must allow legitimate query with 'delete' inside string literal."""
    resp = execute(
        db_path=clean_db,
        agent_id="accounts-agent",
        task_id="task-accounts-1",
        tool="database.run_sql",
        params={"query": "SELECT 'please delete this' AS note", "database": "production"},
    )
    decision = resp.decision if isinstance(resp.decision, str) else resp.decision.value
    assert decision == Decision.ALLOW.value
    assert resp.executed is True

