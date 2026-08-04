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
        self._conn = psycopg2.connect(dsn)
        self._conn.autocommit = False

    def execute(self, sql: str, params=()) -> psycopg2.extras.RealDictCursor:
        if self._conn.get_transaction_status() == psycopg2.extensions.TRANSACTION_STATUS_INERROR:
            self._conn.rollback()
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute(sql, params or ())
            return cur
        except Exception:
            self._conn.rollback()
            raise

    def executemany(self, sql: str, seq) -> None:
        if self._conn.get_transaction_status() == psycopg2.extensions.TRANSACTION_STATUS_INERROR:
            self._conn.rollback()
        cur = self._conn.cursor()
        try:
            cur.executemany(sql, seq)
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
    status      TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'blocked')),
    created_at  TEXT NOT NULL,
    decided_at  TEXT,
    admin_note  TEXT,
    reason_code TEXT
);

CREATE TABLE IF NOT EXISTS decision_appeals (
    id              TEXT PRIMARY KEY,
    org_id          TEXT NOT NULL REFERENCES orgs(id),
    employee_id     TEXT NOT NULL REFERENCES employees(id),
    decision_type   TEXT NOT NULL CHECK (decision_type IN ('ethics', 'pii')),
    category        TEXT NOT NULL,
    employee_reason TEXT NOT NULL,
    disclosed_text  TEXT,
    status          TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'blocked')),
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
    status        TEXT NOT NULL CHECK (status IN ('approved','blocked')),
    PRIMARY KEY (department_id, llm_id)
);

CREATE INDEX IF NOT EXISTS ix_events_org_ts ON usage_events (org_id, ts);
CREATE INDEX IF NOT EXISTS ix_requests_org_status ON access_requests (org_id, status);
CREATE INDEX IF NOT EXISTS ix_appeals_org_status ON decision_appeals (org_id, status);
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
_MIGRATIONS = [
    # M001: admin feedback on access-request decisions
    "ALTER TABLE access_requests ADD COLUMN IF NOT EXISTS admin_note TEXT;",
    """ALTER TABLE access_requests DROP CONSTRAINT IF EXISTS access_requests_status_check;
       UPDATE access_requests SET status = 'blocked' WHERE status = 'denied';
       ALTER TABLE access_requests ADD CONSTRAINT access_requests_status_check
         CHECK (status IN ('pending', 'approved', 'blocked'));""",
    "ALTER TABLE access_requests ADD COLUMN IF NOT EXISTS reason_code TEXT;",
    """ALTER TABLE decision_appeals DROP CONSTRAINT IF EXISTS decision_appeals_status_check;
       UPDATE decision_appeals SET status = CASE
         WHEN status = 'overturned' THEN 'approved'
         WHEN status = 'upheld' THEN 'blocked'
         ELSE status END;
       ALTER TABLE decision_appeals ADD CONSTRAINT decision_appeals_status_check
         CHECK (status IN ('pending', 'approved', 'blocked'));""",
    "ALTER TABLE decision_appeals ADD COLUMN IF NOT EXISTS scope_fingerprint TEXT;",
    "ALTER TABLE decision_appeals ADD COLUMN IF NOT EXISTS reason_code TEXT;",
    """DO $$ BEGIN
         IF EXISTS (
           SELECT 1 FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = 'decision_appeals'
             AND column_name = 'prompt_hash'
         ) THEN
           EXECUTE 'UPDATE decision_appeals SET scope_fingerprint = prompt_hash '
                   'WHERE scope_fingerprint IS NULL AND prompt_hash IS NOT NULL';
         END IF;
       END $$;""",
    "ALTER TABLE decision_appeals DROP COLUMN IF EXISTS prompt_hash;",
    "ALTER TABLE decision_appeals DROP COLUMN IF EXISTS pass_used;",
]


def migrate_schema(conn: "_Connection") -> None:
    """Apply any outstanding incremental schema changes.

    Each statement is idempotent (IF NOT EXISTS / IF EXISTS guards).
    Run AFTER init_schema on every startup so new deployments catch up.
    """
    for sql in _MIGRATIONS:
        try:
            conn.execute(sql)
            conn.commit()
        except Exception:
            # Column already exists or equivalent — safe to ignore.
            conn.rollback()



def bump_policy_version(conn: "_Connection", org_id: str) -> int:
    """Increment and return the org's policy version.

    Every write that changes what an extension would see MUST call this. It is
    the ETag, so a missed bump means a stale client that never refreshes.
    """
    conn.execute(
        "UPDATE orgs SET policy_version = policy_version + 1 WHERE id = %s", (org_id,)
    )
    conn.commit()
    row = conn.execute(
        "SELECT policy_version FROM orgs WHERE id = %s", (org_id,)
    ).fetchone()
    return int(row["policy_version"])
