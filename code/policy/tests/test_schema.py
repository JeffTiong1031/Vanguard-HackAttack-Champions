"""Schema existence tests — Postgres / information_schema version.

SQLite-specific introspection (sqlite_master, PRAGMA table_info) replaced with
information_schema queries. The 'migration idempotency' test is not applicable
to Postgres (there are no ALTER TABLE migrations -- the schema is declared once
in db.py and applied via CREATE TABLE IF NOT EXISTS). That test is replaced
with a simpler 'schema is idempotent' check: calling init_schema a second time
on the live connection must not raise.
"""
import uuid

import pytest

from app.db import init_schema
from app.deps import get_conn
from app.security import now_iso
from app.seed import seed_company


def _cols(conn, table: str) -> set:
    rows = conn.execute(
        "SELECT column_name FROM information_schema.columns"
        " WHERE table_schema = 'public' AND table_name = %s",
        (table,),
    ).fetchall()
    return {r["column_name"] for r in rows}


def _tables(conn) -> set:
    rows = conn.execute(
        "SELECT table_name FROM information_schema.tables"
        " WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
    ).fetchall()
    return {r["table_name"] for r in rows}


def test_hierarchy_tables_and_columns_exist():
    conn = get_conn()
    tables = _tables(conn)
    assert {"departments", "dept_llm_policy"} <= tables
    assert "admin_token_hash" in _cols(conn, "orgs")
    assert {"role", "department_id"} <= _cols(conn, "admin_sessions")
    assert "department_id" in _cols(conn, "employees")
    assert "department_id" in _cols(conn, "enroll_tokens")


def test_schema_is_idempotent():
    """init_schema uses CREATE TABLE IF NOT EXISTS — calling it again must not raise."""
    conn = get_conn()
    init_schema(conn)  # second call — must not raise


def test_employees_has_enroll_token_id():
    """The link that makes revocation and coverage possible."""
    conn = get_conn()
    cols = {r["column_name"] for r in conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'employees'"
    ).fetchall()}
    assert "enroll_token_id" in cols


def test_enroll_token_id_is_unique():
    """The find-or-create guarantee (task 1.2) is only real if the DB enforces
    it, not just the application's SELECT-then-INSERT. Two concurrent
    enrolments with the same token can both see `existing = None` and both
    reach the INSERT; without a DB-level unique constraint that produces two
    employee rows for one token, which corrupts per-token usage counts
    (Piece 2) silently. This asserts the constraint directly: a second
    employee row reusing an already-used enroll_token_id must be rejected.

    A true concurrency test isn't practical against a remote DB with one
    connection, so this pins the property that actually matters -- the
    database refuses the duplicate -- rather than trying to race two threads.
    """
    conn = get_conn()
    org_id, _ = seed_company(conn, f"T-{uuid.uuid4().hex[:8]}")
    token_id = uuid.uuid4().hex

    conn.execute(
        "INSERT INTO employees (id, org_id, pseudo_id, department, created_at, enroll_token_id)"
        " VALUES (%s, %s, %s, %s, %s, %s)",
        (uuid.uuid4().hex, org_id, uuid.uuid4().hex, "Engineering", now_iso(), token_id),
    )
    conn.commit()

    with pytest.raises(Exception, match="(?i)duplicate key|unique"):
        conn.execute(
            "INSERT INTO employees (id, org_id, pseudo_id, department, created_at, enroll_token_id)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            (uuid.uuid4().hex, org_id, uuid.uuid4().hex, "Engineering", now_iso(), token_id),
        )
    conn.rollback()
