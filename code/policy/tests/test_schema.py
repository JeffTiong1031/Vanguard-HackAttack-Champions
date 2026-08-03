from app.db import connect, init_schema


def _cols(conn, table):
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


def test_hierarchy_tables_and_columns_exist():
    conn = connect(":memory:")
    init_schema(conn)
    tables = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"departments", "dept_llm_policy"} <= tables
    assert "admin_token_hash" in _cols(conn, "orgs")
    assert {"role", "department_id"} <= _cols(conn, "admin_sessions")
    assert "department_id" in _cols(conn, "employees")
    assert "department_id" in _cols(conn, "enroll_tokens")


def test_migration_is_idempotent_on_a_legacy_db():
    # A DB created with the OLD schema (no new columns) must gain them without error.
    conn = connect(":memory:")
    conn.executescript(
        "CREATE TABLE orgs (id TEXT PRIMARY KEY, name TEXT NOT NULL,"
        " admin_password_hash TEXT NOT NULL, policy_version INTEGER NOT NULL DEFAULT 1);"
        "CREATE TABLE admin_sessions (token TEXT PRIMARY KEY, org_id TEXT NOT NULL,"
        " created_at TEXT NOT NULL);"
        "CREATE TABLE employees (id TEXT PRIMARY KEY, org_id TEXT NOT NULL,"
        " pseudo_id TEXT NOT NULL UNIQUE, department TEXT NOT NULL, created_at TEXT NOT NULL);"
        "CREATE TABLE enroll_tokens (id TEXT PRIMARY KEY, org_id TEXT NOT NULL,"
        " department TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE, label TEXT NOT NULL,"
        " created_at TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0);"
    )
    init_schema(conn)  # must not raise
    assert "admin_token_hash" in _cols(conn, "orgs")
    assert "department_id" in _cols(conn, "admin_sessions")
