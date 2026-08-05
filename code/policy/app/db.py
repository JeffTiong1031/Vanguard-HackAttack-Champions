"""Postgres access for the governance service via psycopg2.

Replaces the previous sqlite3 layer. The connection object is a thin wrapper
that exposes the same .execute() / .executemany() / .commit() interface as
sqlite3.Connection, so every existing call site in app/ continues to work
without modification.

psycopg2 uses %s placeholders rather than sqlite3's ?. All SQL in this repo
has been updated accordingly.
"""
import psycopg2
import psycopg2.extras

# Applied via libpq `options=` so they survive Supabase transaction-mode pooler
# (a post-connect SET + COMMIT is discarded when the backend is returned).
_CONNECT_OPTIONS = "-c statement_timeout=15s -c lock_timeout=5s"


class _Connection:
    """Thin sqlite3-compatible wrapper around a psycopg2 connection.

    Exposes:
      .execute(sql, params)    → psycopg2 cursor (RealDictCursor)
      .executemany(sql, seq)   → psycopg2 cursor
      .executescript(sql)      → runs a multi-statement SQL string
      .commit()
      .close()

    Row objects returned by .execute().fetchone() / .fetchall() are plain
    dicts, so row["column"] access works exactly as it did with sqlite3.Row.
    """

    def __init__(self, dsn: str) -> None:
        # connect_timeout: fail fast on bad DNS/credentials (Render health check).
        # options=: statement/lock timeouts on every backend checkout (pooler-safe).
        self._conn = psycopg2.connect(
            dsn,
            connect_timeout=15,
            options=_CONNECT_OPTIONS,
        )
        self._conn.autocommit = False

    def execute(self, sql: str, params=()) -> psycopg2.extras.RealDictCursor:
        if self._conn.get_transaction_status() == psycopg2.extensions.TRANSACTION_STATUS_INERROR:
            self._conn.rollback()
        sql_pg = sql.replace("?", "%s").replace("datetime('now')", "NOW()").replace("datetime('now', 'localtime')", "NOW()")
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute(sql_pg, params or ())
            return cur
        except Exception:
            self._conn.rollback()
            raise

    def executemany(self, sql: str, seq) -> None:
        if self._conn.get_transaction_status() == psycopg2.extensions.TRANSACTION_STATUS_INERROR:
            self._conn.rollback()
        sql_pg = sql.replace("?", "%s").replace("datetime('now')", "NOW()").replace("datetime('now', 'localtime')", "NOW()")
        cur = self._conn.cursor()
        try:
            cur.executemany(sql_pg, seq)
        except Exception:
            self._conn.rollback()
            raise

    def executescript(self, sql: str) -> None:
        """Run a multi-statement SQL block (used by init_schema)."""
        if self._conn.get_transaction_status() == psycopg2.extensions.TRANSACTION_STATUS_INERROR:
            self._conn.rollback()
        cur = self._conn.cursor()
        try:
            cur.execute(sql)
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def commit(self) -> None:
        if self._conn.get_transaction_status() == psycopg2.extensions.TRANSACTION_STATUS_INERROR:
            self._conn.rollback()
        else:
            self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS orgs (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    admin_password_hash TEXT NOT NULL,
    admin_token_hash    TEXT,
    policy_version      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS departments (
    id               TEXT PRIMARY KEY,
    org_id           TEXT NOT NULL REFERENCES orgs(id),
    name             TEXT NOT NULL,
    admin_token_hash TEXT NOT NULL UNIQUE,
    created_at       TEXT NOT NULL,
    UNIQUE (org_id, name)
);

CREATE TABLE IF NOT EXISTS enroll_tokens (
    id            TEXT PRIMARY KEY,
    org_id        TEXT NOT NULL REFERENCES orgs(id),
    department    TEXT NOT NULL,
    department_id TEXT REFERENCES departments(id),
    token_hash    TEXT NOT NULL UNIQUE,
    label         TEXT NOT NULL,
    name          TEXT,
    created_at    TEXT NOT NULL,
    revoked       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS employees (
    id            TEXT PRIMARY KEY,
    org_id        TEXT NOT NULL REFERENCES orgs(id),
    pseudo_id     TEXT NOT NULL UNIQUE,
    department    TEXT NOT NULL,
    department_id TEXT REFERENCES departments(id),
    name          TEXT,
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
    status TEXT NOT NULL CHECK (status IN ('approved', 'blocked', 'temporary', 'trial', 'conditional')),
    access_mode TEXT NOT NULL DEFAULT 'standard' CHECK (access_mode IN ('standard', 'strict_redaction', 'no_file_uploads')),
    expires_at TEXT,
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
    status      TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'blocked', 'temporary', 'trial', 'conditional')),
    created_at  TEXT NOT NULL,
    decided_at  TEXT,
    admin_note  TEXT,
    reason_code TEXT,
    access_mode TEXT DEFAULT 'standard',
    expires_at  TEXT
);

CREATE TABLE IF NOT EXISTS decision_appeals (
    id              TEXT PRIMARY KEY,
    org_id          TEXT NOT NULL REFERENCES orgs(id),
    employee_id     TEXT NOT NULL REFERENCES employees(id),
    decision_type   TEXT NOT NULL CHECK (decision_type IN ('ethics', 'pii')),
    category        TEXT NOT NULL,
    employee_reason TEXT NOT NULL,
    disclosed_text  TEXT,
    status          TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'blocked', 'temporary', 'trial', 'conditional')),
    admin_note      TEXT,
    created_at      TEXT NOT NULL,
    decided_at      TEXT,
    scope_fingerprint TEXT,
    reason_code     TEXT
);

CREATE TABLE IF NOT EXISTS usage_events (
    id           TEXT PRIMARY KEY,
    org_id       TEXT NOT NULL REFERENCES orgs(id),
    employee_id  TEXT NOT NULL REFERENCES employees(id),
    host         TEXT NOT NULL,
    type         TEXT NOT NULL,
    category     TEXT,
    finding_hash TEXT,
    risk_level   TEXT CHECK (risk_level IN ('low', 'medium', 'high')),
    ts           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS admin_sessions (
    token         TEXT PRIMARY KEY,
    org_id        TEXT NOT NULL REFERENCES orgs(id),
    role          TEXT NOT NULL DEFAULT 'company' CHECK (role IN ('company','department')),
    department_id TEXT,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dept_llm_policy (
    org_id        TEXT NOT NULL REFERENCES orgs(id),
    department_id TEXT NOT NULL REFERENCES departments(id),
    llm_id        TEXT NOT NULL REFERENCES llm_registry(id),
    status        TEXT NOT NULL CHECK (status IN ('approved','blocked','temporary','trial','conditional')),
    access_mode   TEXT NOT NULL DEFAULT 'standard' CHECK (access_mode IN ('standard', 'strict_redaction', 'no_file_uploads')),
    expires_at    TEXT,
    PRIMARY KEY (department_id, llm_id)
);

CREATE TABLE IF NOT EXISTS notifications (
    id           TEXT PRIMARY KEY,
    org_id       TEXT NOT NULL REFERENCES orgs(id),
    employee_id  TEXT NOT NULL REFERENCES employees(id),
    kind         TEXT NOT NULL,
    title        TEXT NOT NULL,
    message      TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'unread',
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_events_org_ts ON usage_events (org_id, ts);
CREATE INDEX IF NOT EXISTS ix_requests_org_status ON access_requests (org_id, status);
CREATE INDEX IF NOT EXISTS ix_appeals_org_status ON decision_appeals (org_id, status);
CREATE INDEX IF NOT EXISTS ix_notifications_emp ON notifications (employee_id, status);
"""


def connect(dsn: str) -> "_Connection":
    """Open and return a wrapped psycopg2 connection."""
    return _Connection(dsn)


def init_schema(conn: "_Connection") -> None:
    """Create all tables and indexes if they do not already exist."""
    conn.executescript(SCHEMA)


# ---------------------------------------------------------------------------
# Incremental migrations (idempotent — safe to run on every startup)
# ---------------------------------------------------------------------------
# (table, column, ALTER… ADD COLUMN IF NOT EXISTS …)
_COLUMN_ADDS: list[tuple[str, str, str]] = [
    ("org_llm_policy", "access_mode",
     "ALTER TABLE org_llm_policy ADD COLUMN IF NOT EXISTS access_mode TEXT NOT NULL DEFAULT 'standard'"),
    ("org_llm_policy", "expires_at",
     "ALTER TABLE org_llm_policy ADD COLUMN IF NOT EXISTS expires_at TEXT"),
    ("dept_llm_policy", "access_mode",
     "ALTER TABLE dept_llm_policy ADD COLUMN IF NOT EXISTS access_mode TEXT NOT NULL DEFAULT 'standard'"),
    ("dept_llm_policy", "expires_at",
     "ALTER TABLE dept_llm_policy ADD COLUMN IF NOT EXISTS expires_at TEXT"),
    ("access_requests", "access_mode",
     "ALTER TABLE access_requests ADD COLUMN IF NOT EXISTS access_mode TEXT DEFAULT 'standard'"),
    ("access_requests", "expires_at",
     "ALTER TABLE access_requests ADD COLUMN IF NOT EXISTS expires_at TEXT"),
    ("access_requests", "admin_note",
     "ALTER TABLE access_requests ADD COLUMN IF NOT EXISTS admin_note TEXT"),
    ("access_requests", "reason_code",
     "ALTER TABLE access_requests ADD COLUMN IF NOT EXISTS reason_code TEXT"),
    ("decision_appeals", "scope_fingerprint",
     "ALTER TABLE decision_appeals ADD COLUMN IF NOT EXISTS scope_fingerprint TEXT"),
    ("decision_appeals", "reason_code",
     "ALTER TABLE decision_appeals ADD COLUMN IF NOT EXISTS reason_code TEXT"),
    ("usage_events", "risk_level",
     "ALTER TABLE usage_events ADD COLUMN IF NOT EXISTS risk_level TEXT"),
]

_NOTIFICATIONS_DDL = """
CREATE TABLE IF NOT EXISTS notifications (
    id           TEXT PRIMARY KEY,
    org_id       TEXT NOT NULL REFERENCES orgs(id),
    employee_id  TEXT NOT NULL REFERENCES employees(id),
    kind         TEXT NOT NULL,
    title        TEXT NOT NULL,
    message      TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'unread',
    created_at   TEXT NOT NULL
);
"""

# (constraint_name, table, CHECK body). Skip DROP/ADD when already current —
# re-running DDL every boot is what hung Render on the Supabase pooler.
_STATUS_CHECK_MIGRATIONS = [
    (
        "org_llm_policy_status_check",
        "org_llm_policy",
        "status IN ('approved', 'blocked', 'temporary', 'trial', 'conditional')",
    ),
    (
        "dept_llm_policy_status_check",
        "dept_llm_policy",
        "status IN ('approved', 'blocked', 'temporary', 'trial', 'conditional')",
    ),
    (
        "access_requests_status_check",
        "access_requests",
        "status IN ('pending', 'approved', 'blocked', 'temporary', 'trial', 'conditional')",
    ),
    (
        "decision_appeals_status_check",
        "decision_appeals",
        "status IN ('pending', 'approved', 'blocked', 'temporary', 'trial', 'conditional')",
    ),
]


def status_constraint_is_current(conn: "_Connection", name: str) -> bool:
    """True when the named CHECK already allows temporary/trial/conditional."""
    row = conn.execute(
        "SELECT pg_get_constraintdef(oid) AS def FROM pg_constraint WHERE conname = %s",
        (name,),
    ).fetchone()
    if row is None:
        return False
    definition = row["def"] or ""
    return "temporary" in definition and "conditional" in definition


def _existing_columns(conn: "_Connection") -> set[tuple[str, str]]:
    """One round-trip: which (table, column) pairs already exist in public."""
    tables = sorted({t for t, _, _ in _COLUMN_ADDS})
    rows = conn.execute(
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = ANY(%s)",
        (tables,),
    ).fetchall()
    return {(r["table_name"], r["column_name"]) for r in rows}


def _table_exists(conn: "_Connection", name: str) -> bool:
    row = conn.execute(
        "SELECT 1 AS ok FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = %s",
        (name,),
    ).fetchone()
    return row is not None


def _current_status_constraints(conn: "_Connection") -> set[str]:
    """Names of status CHECKs that already allow temporary + conditional."""
    names = [n for n, _, _ in _STATUS_CHECK_MIGRATIONS]
    rows = conn.execute(
        "SELECT conname, pg_get_constraintdef(oid) AS def "
        "FROM pg_constraint WHERE conname = ANY(%s)",
        (names,),
    ).fetchall()
    out: set[str] = set()
    for row in rows:
        definition = row["def"] or ""
        if "temporary" in definition and "conditional" in definition:
            out.add(row["conname"])
    return out


def migrate_schema(conn: "_Connection") -> None:
    """Apply any outstanding incremental schema changes.

    Prefers catalog lookups over blind DDL: on a warm schema this is a few
    SELECTs. Re-running ALTER/ADD CONSTRAINT every boot hung Render behind the
    Supabase transaction pooler.
    """
    try:
        existing = _existing_columns(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        existing = set()

    for table, column, stmt in _COLUMN_ADDS:
        if (table, column) in existing:
            continue
        try:
            conn.execute(stmt)
            conn.commit()
        except Exception:
            conn.rollback()

    try:
        if not _table_exists(conn, "notifications"):
            conn.execute(_NOTIFICATIONS_DDL)
            conn.commit()
        else:
            conn.commit()
    except Exception:
        conn.rollback()

    try:
        current = _current_status_constraints(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        current = set()

    for name, table, check_expr in _STATUS_CHECK_MIGRATIONS:
        if name in current:
            continue
        try:
            conn.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}")
            conn.commit()
            conn.execute(
                f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({check_expr})"
            )
            conn.commit()
        except Exception:
            conn.rollback()


def migrate_on_dedicated_connection(dsn: str) -> None:
    """Run migrations on a private connection, then close it.

    Must not use the request-path singleton: a timed-out migrate thread racing
    handlers on one psycopg2 connection yields InFailedSqlTransaction.
    """
    conn = connect(dsn)
    try:
        migrate_schema(conn)
    finally:
        conn.close()


def bump_policy_version(conn: "_Connection", org_id: str) -> int:
    """Increment policy_version for an org and return the new version integer."""
    cur = conn.execute(
        "UPDATE orgs SET policy_version = policy_version + 1 WHERE id = %s RETURNING policy_version",
        (org_id,),
    )
    row = cur.fetchone()
    conn.commit()
    return int(row["policy_version"])
