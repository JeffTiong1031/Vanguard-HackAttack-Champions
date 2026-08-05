"""Tests for db.py — adapted for Postgres / psycopg2.

SQLite-specific introspection (sqlite_master, PRAGMA table_info) replaced with
information_schema queries that work on Postgres / Supabase.
"""
import uuid

from app.db import bump_policy_version, connect, init_schema
from app.deps import get_conn


def _table_names(conn) -> set:
    rows = conn.execute(
        "SELECT table_name FROM information_schema.tables"
        " WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
    ).fetchall()
    return {r["table_name"] for r in rows}


def _col_names(conn, table: str) -> set:
    rows = conn.execute(
        "SELECT column_name FROM information_schema.columns"
        " WHERE table_schema = 'public' AND table_name = %s",
        (table,),
    ).fetchall()
    return {r["column_name"] for r in rows}


def _nullable(conn, table: str, column: str) -> bool:
    row = conn.execute(
        "SELECT is_nullable FROM information_schema.columns"
        " WHERE table_schema = 'public' AND table_name = %s AND column_name = %s",
        (table, column),
    ).fetchone()
    return row["is_nullable"] == "YES"


def test_schema_creates_every_table():
    conn = get_conn()
    names = _table_names(conn)
    assert {
        "orgs", "enroll_tokens", "employees", "llm_registry",
        "org_llm_policy", "policy_category", "access_requests", "usage_events",
    } <= names


def test_rows_are_addressable_by_column_name():
    conn = get_conn()
    oid = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO orgs (id, name, admin_password_hash, policy_version)"
        " VALUES (%s, %s, 'x', 1)",
        (oid, "Acme-" + oid),
    )
    conn.commit()
    row = conn.execute("SELECT name FROM orgs WHERE id = %s", (oid,)).fetchone()
    assert row["name"] == "Acme-" + oid


def test_bump_returns_the_new_version_and_persists_it():
    conn = get_conn()
    oid = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO orgs (id, name, admin_password_hash, policy_version)"
        " VALUES (%s, %s, 'x', 1)",
        (oid, "Bump-" + oid),
    )
    conn.commit()
    assert bump_policy_version(conn, oid) == 2
    assert bump_policy_version(conn, oid) == 3
    stored = conn.execute("SELECT policy_version FROM orgs WHERE id = %s", (oid,)).fetchone()
    assert stored["policy_version"] == 3


def test_employees_table_has_no_email_column():
    """Pseudonymity is a schema property, not a convention (spec section 8).

    `department_id` (added by the department-hierarchy migration) is a UUID
    foreign key into `departments`, not a name or email column -- it is
    included in the allowed set deliberately. `name` (added by the analytics
    migration, 2026-08-04) is an admin-supplied label carried from
    `enroll_tokens.name` -- an org-chosen display string, not employee-typed
    PII, and explicitly in scope per the analytics spec. `enroll_token_id`
    (added on the token-identity branch) is a foreign key into
    `enroll_tokens.id` -- an opaque internal identifier, not a name, email,
    or anything employee-typed; it carries no personal data. It exists so
    that revoking a token can deprovision the employee it enrolled.

    The exact-set comparison below is maintained deliberately: every new
    column has to be vetted against the pseudonymity property and added here
    explicitly, with a reason, before the test will pass. That is the
    assertion's real job -- not to freeze the column count for its own sake,
    but to force a reviewer to look at each addition. Catching an EMAIL
    column -- the one identifier this schema must never be able to hold --
    is what that vetting is for.
    """
    conn = get_conn()
    cols = _col_names(conn, "employees")
    assert cols == {
        "id", "org_id", "pseudo_id", "department", "department_id",
        "name", "enroll_token_id", "created_at",
    }
    assert not cols & {"email", "email_address"}


def test_decision_appeals_table_exists_with_expected_columns():
    conn = get_conn()
    cols = _col_names(conn, "decision_appeals")
    assert cols == {
        "id", "org_id", "employee_id", "decision_type", "category",
        "employee_reason", "disclosed_text", "status", "admin_note",
        "created_at", "decided_at", "scope_fingerprint", "reason_code",
    }


def test_decision_appeals_nullability_matches_the_privacy_design():
    """disclosed_text MUST be nullable: a default appeal stores no prompt text.

    This is a schema-level enforcement of the privacy design (spec section 6.5).
    Raw prompt text only ever reaches the server via an explicit opt-in, so the
    default must store NULL. A typo making this NOT NULL would silently defeat
    the entire architecture for appeals without disclosure.
    """
    conn = get_conn()
    assert _nullable(conn, "decision_appeals", "disclosed_text")
    assert _nullable(conn, "decision_appeals", "admin_note")
    assert _nullable(conn, "decision_appeals", "decided_at")
    # The load-bearing required columns must NOT be nullable
    assert not _nullable(conn, "decision_appeals", "employee_reason")
    assert not _nullable(conn, "decision_appeals", "decision_type")
