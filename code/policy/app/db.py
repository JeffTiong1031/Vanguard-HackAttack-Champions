"""SQLite access for the governance service.

Raw sqlite3 rather than an ORM, matching code/backend/'s dependency-light
style. The schema is small, fixed, and read far more than it is written.
"""
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS orgs (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    admin_password_hash TEXT NOT NULL,
    admin_token_hash    TEXT,
    policy_version      INTEGER NOT NULL DEFAULT 1
);

-- Per-DEPARTMENT, never per-org. The department is encoded in the token so an
-- employee cannot self-declare it, and department is the axis the whole usage
-- dashboard is organised on.
CREATE TABLE IF NOT EXISTS enroll_tokens (
    id            TEXT PRIMARY KEY,
    org_id        TEXT NOT NULL REFERENCES orgs(id),
    department    TEXT NOT NULL,
    department_id TEXT REFERENCES departments(id),
    token_hash    TEXT NOT NULL UNIQUE,
    label         TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    revoked       INTEGER NOT NULL DEFAULT 0
);

-- I3 / spec section 8: pseudo_id and department only. There is deliberately no
-- column here that could hold a name or an email address.
CREATE TABLE IF NOT EXISTS employees (
    id            TEXT PRIMARY KEY,
    org_id        TEXT NOT NULL REFERENCES orgs(id),
    pseudo_id     TEXT NOT NULL UNIQUE,
    department    TEXT NOT NULL,
    department_id TEXT REFERENCES departments(id),
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS llm_registry (
    id           TEXT PRIMARY KEY,
    host         TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS org_llm_policy (
    org_id TEXT NOT NULL REFERENCES orgs(id),
    llm_id TEXT NOT NULL REFERENCES llm_registry(id),
    status TEXT NOT NULL CHECK (status IN ('approved', 'blocked')),
    PRIMARY KEY (org_id, llm_id)
);

CREATE TABLE IF NOT EXISTS policy_category (
    org_id  TEXT NOT NULL REFERENCES orgs(id),
    key     TEXT NOT NULL,
    label   TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (org_id, key)
);

CREATE TABLE IF NOT EXISTS access_requests (
    id          TEXT PRIMARY KEY,
    org_id      TEXT NOT NULL REFERENCES orgs(id),
    employee_id TEXT NOT NULL REFERENCES employees(id),
    llm_id      TEXT NOT NULL REFERENCES llm_registry(id),
    reason      TEXT NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'denied')),
    created_at  TEXT NOT NULL,
    decided_at  TEXT
);

CREATE TABLE IF NOT EXISTS decision_appeals (
    id              TEXT PRIMARY KEY,
    org_id          TEXT NOT NULL REFERENCES orgs(id),
    employee_id     TEXT NOT NULL REFERENCES employees(id),
    decision_type   TEXT NOT NULL CHECK (decision_type IN ('ethics', 'pii')),
    category        TEXT NOT NULL,
    employee_reason TEXT NOT NULL,
    disclosed_text  TEXT,
    status          TEXT NOT NULL CHECK (status IN ('pending', 'upheld', 'overturned')),
    admin_note      TEXT,
    created_at      TEXT NOT NULL,
    decided_at      TEXT,
    -- One-time pass: an overturned ethics appeal carries a hash of the prompt so
    -- the extension can grant a single pass on that exact prompt. pass_used flips
    -- to 1 the moment the pass is granted, so it is never handed out twice.
    prompt_hash     TEXT,
    pass_used       INTEGER NOT NULL DEFAULT 0
);

-- finding_hash is a salted hash reference. There is no column for prompt text
-- and there must never be one.
CREATE TABLE IF NOT EXISTS usage_events (
    id           TEXT PRIMARY KEY,
    org_id       TEXT NOT NULL REFERENCES orgs(id),
    employee_id  TEXT NOT NULL REFERENCES employees(id),
    host         TEXT NOT NULL,
    type         TEXT NOT NULL,
    category     TEXT,
    finding_hash TEXT,
    ts           TEXT NOT NULL
);

-- department_id is deliberately NOT a `REFERENCES departments(id)` FK, unlike
-- the other department_id columns in this file: a session is an ephemeral
-- credential, not a record of the department's existence, and PRAGMA
-- foreign_keys=ON would otherwise reject a session row the instant a
-- department is ever removed. (Also required so unit tests can exercise
-- issue_session()/resolve_session() with a bare placeholder id, decoupled
-- from a real departments row.)
CREATE TABLE IF NOT EXISTS admin_sessions (
    token         TEXT PRIMARY KEY,
    org_id        TEXT NOT NULL REFERENCES orgs(id),
    role          TEXT NOT NULL DEFAULT 'company' CHECK (role IN ('company','department')),
    department_id TEXT,
    created_at    TEXT NOT NULL
);

-- Each row is a department AND its login secret (admin_token_hash). A
-- department has no independent identity outside an org: (org_id, name) is
-- unique, so two orgs may each have an "Engineering" department.
CREATE TABLE IF NOT EXISTS departments (
    id               TEXT PRIMARY KEY,
    org_id           TEXT NOT NULL REFERENCES orgs(id),
    name             TEXT NOT NULL,
    admin_token_hash TEXT NOT NULL UNIQUE,
    created_at       TEXT NOT NULL,
    UNIQUE (org_id, name)
);

-- A department-level override of the company's org_llm_policy default.
-- Effective policy for an employee = coalesce(dept override, company default).
CREATE TABLE IF NOT EXISTS dept_llm_policy (
    org_id        TEXT NOT NULL REFERENCES orgs(id),
    department_id TEXT NOT NULL REFERENCES departments(id),
    llm_id        TEXT NOT NULL REFERENCES llm_registry(id),
    status        TEXT NOT NULL CHECK (status IN ('approved','blocked')),
    PRIMARY KEY (department_id, llm_id)
);

CREATE INDEX IF NOT EXISTS ix_events_org_ts ON usage_events (org_id, ts);
CREATE INDEX IF NOT EXISTS ix_requests_org_status ON access_requests (org_id, status);
CREATE INDEX IF NOT EXISTS ix_appeals_org_status ON decision_appeals (org_id, status);
"""


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    _migrate_appeals(conn)
    _migrate_hierarchy(conn)
    _migrate_analytics(conn)
    conn.commit()


def _migrate_appeals(conn: sqlite3.Connection) -> None:
    """Idempotently add the one-time-pass columns to a decision_appeals table that
    predates them. `CREATE TABLE IF NOT EXISTS` never alters an existing table, so
    a DB seeded before this feature needs the columns added by hand."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(decision_appeals)")}
    if "prompt_hash" not in cols:
        conn.execute("ALTER TABLE decision_appeals ADD COLUMN prompt_hash TEXT")
    if "pass_used" not in cols:
        conn.execute("ALTER TABLE decision_appeals ADD COLUMN pass_used INTEGER NOT NULL DEFAULT 0")


def _migrate_hierarchy(conn: sqlite3.Connection) -> None:
    """Add hierarchy columns to a DB that predates them. CREATE TABLE IF NOT
    EXISTS never alters an existing table, so older DBs need columns by hand.
    The two new TABLES are handled by SCHEMA's IF NOT EXISTS already."""
    def cols(table: str) -> set[str]:
        return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
    adds = [
        ("orgs", "admin_token_hash", "ALTER TABLE orgs ADD COLUMN admin_token_hash TEXT"),
        ("admin_sessions", "role",
         "ALTER TABLE admin_sessions ADD COLUMN role TEXT NOT NULL DEFAULT 'company'"),
        ("admin_sessions", "department_id",
         "ALTER TABLE admin_sessions ADD COLUMN department_id TEXT"),
        ("employees", "department_id",
         "ALTER TABLE employees ADD COLUMN department_id TEXT"),
        ("enroll_tokens", "department_id",
         "ALTER TABLE enroll_tokens ADD COLUMN department_id TEXT"),
    ]
    for table, column, ddl in adds:
        if column not in cols(table):
            conn.execute(ddl)


def _migrate_analytics(conn: sqlite3.Connection) -> None:
    """Add the admin-supplied employee-name label to tokens and employees.
    Migration-only: init_schema runs this after executescript(SCHEMA), so a
    fresh DB (whose SCHEMA has no `name`) gets the column here too."""
    def cols(table: str) -> set[str]:
        return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
    if "name" not in cols("enroll_tokens"):
        conn.execute("ALTER TABLE enroll_tokens ADD COLUMN name TEXT")
    if "name" not in cols("employees"):
        conn.execute("ALTER TABLE employees ADD COLUMN name TEXT")


def bump_policy_version(conn: sqlite3.Connection, org_id: str) -> int:
    """Increment and return the org's policy version.

    Every write that changes what an extension would see MUST call this. It is
    the ETag, so a missed bump means a stale client that never refreshes.
    """
    conn.execute(
        "UPDATE orgs SET policy_version = policy_version + 1 WHERE id = ?", (org_id,)
    )
    conn.commit()
    row = conn.execute(
        "SELECT policy_version FROM orgs WHERE id = ?", (org_id,)
    ).fetchone()
    return int(row["policy_version"])
