-- ============================================================
-- Vanguard policy service — Supabase / Postgres schema
-- Run once in the Supabase SQL Editor (or via psql).
-- ============================================================

CREATE TABLE IF NOT EXISTS orgs (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    admin_password_hash TEXT NOT NULL,
    admin_token_hash    TEXT,
    policy_version      INTEGER NOT NULL DEFAULT 1
);

-- Per-DEPARTMENT enrolment tokens. The department is encoded in the token so
-- an employee cannot self-declare it, and department is the axis the whole
-- usage dashboard is organised on.
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

-- I3: pseudo_id and department only — no name, no email.
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

-- admin_sessions.department_id is intentionally NOT a FK to departments.id:
-- a session is an ephemeral credential and we don't want a department removal
-- to cascade-delete live sessions or break tests.
CREATE TABLE IF NOT EXISTS admin_sessions (
    token         TEXT PRIMARY KEY,
    org_id        TEXT NOT NULL REFERENCES orgs(id),
    role          TEXT NOT NULL DEFAULT 'company' CHECK (role IN ('company','department')),
    department_id TEXT,
    created_at    TEXT NOT NULL
);

-- A department-level override of the company's org_llm_policy default.
-- Effective policy for an employee = COALESCE(dept override, company default).
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
