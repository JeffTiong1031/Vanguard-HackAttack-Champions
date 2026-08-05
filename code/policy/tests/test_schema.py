"""Schema existence tests — Postgres / information_schema version.

SQLite-specific introspection (sqlite_master, PRAGMA table_info) replaced with
information_schema queries. The 'migration idempotency' test is not applicable
to Postgres (there are no ALTER TABLE migrations -- the schema is declared once
in db.py and applied via CREATE TABLE IF NOT EXISTS). That test is replaced
with a simpler 'schema is idempotent' check: calling init_schema a second time
on the live connection must not raise.
"""
from app.db import init_schema
from app.deps import get_conn


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
