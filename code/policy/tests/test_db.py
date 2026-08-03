import sqlite3

from app.db import bump_policy_version, connect, init_schema


def _conn() -> sqlite3.Connection:
    conn = connect(":memory:")
    init_schema(conn)
    return conn


def test_schema_creates_every_table():
    conn = _conn()
    names = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert {
        "orgs", "enroll_tokens", "employees", "llm_registry",
        "org_llm_policy", "policy_category", "access_requests", "usage_events",
    } <= names


def test_rows_are_addressable_by_column_name():
    conn = _conn()
    conn.execute(
        "INSERT INTO orgs (id, name, admin_password_hash, policy_version)"
        " VALUES ('o1', 'Acme', 'x', 1)"
    )
    row = conn.execute("SELECT name FROM orgs WHERE id='o1'").fetchone()
    assert row["name"] == "Acme"


def test_bump_returns_the_new_version_and_persists_it():
    conn = _conn()
    conn.execute(
        "INSERT INTO orgs (id, name, admin_password_hash, policy_version)"
        " VALUES ('o1', 'Acme', 'x', 1)"
    )
    assert bump_policy_version(conn, "o1") == 2
    assert bump_policy_version(conn, "o1") == 3
    stored = conn.execute("SELECT policy_version FROM orgs WHERE id='o1'").fetchone()
    assert stored["policy_version"] == 3


def test_employees_table_has_no_column_that_could_hold_a_name():
    """Pseudonymity is a schema property, not a convention (spec section 8).

    `department_id` (added by the department-hierarchy migration) is a UUID
    foreign key into `departments`, not a name or email column -- it is
    included in the allowed set deliberately. The assertion's job is to catch
    a NAME/EMAIL column, not to freeze the column count.
    """
    conn = _conn()
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(employees)")}
    assert cols == {"id", "org_id", "pseudo_id", "department", "department_id", "created_at"}
    assert not cols & {"name", "full_name", "email", "email_address"}


def test_decision_appeals_table_exists_with_expected_columns():
    conn = _conn()
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(decision_appeals)")}
    assert cols == {
        "id", "org_id", "employee_id", "decision_type", "category",
        "employee_reason", "disclosed_text", "status", "admin_note",
        "created_at", "decided_at", "prompt_hash", "pass_used",
    }


def test_decision_appeals_nullability_matches_the_privacy_design():
    """disclosed_text MUST be nullable: a default appeal stores no prompt text.

    This is a schema-level enforcement of the privacy design (spec section 6.5).
    Raw prompt text only ever reaches the server via an explicit opt-in, so the
    default must store NULL. A typo making this NOT NULL would silently defeat
    the entire architecture for appeals without disclosure.
    """
    conn = _conn()
    cols = {r["name"]: r for r in conn.execute("PRAGMA table_info(decision_appeals)")}
    # disclosed_text MUST be nullable: a default appeal stores no prompt text.
    assert cols["disclosed_text"]["notnull"] == 0
    assert cols["admin_note"]["notnull"] == 0
    assert cols["decided_at"]["notnull"] == 0
    # the load-bearing required columns must NOT be nullable
    assert cols["employee_reason"]["notnull"] == 1
    assert cols["decision_type"]["notnull"] == 1
