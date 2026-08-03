# Department Hierarchy — Backend Implementation Plan (Plan 1 of 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `code/policy` from a two-tier (one admin → per-department enrolment tokens used in the extension) model into a three-tier one: self-signup **company** → **department dashboards** (dept-scoped approvals + employee-token minting) → **employee tokens** used only in the extension.

**Architecture:** FastAPI + raw `sqlite3`. Add a `departments` table (each row is a department *and* its login secret) and a `dept_llm_policy` overrides table. All console credentials become high-entropy generated secrets (SHA-256, not scrypt). One `admin_sessions` table gains `role` + `department_id` so one session store serves both dashboards. Effective tool policy = `coalesce(dept override, company default)`. `/v1/policy` and `/v1/enroll` become department-aware.

**Tech Stack:** Python 3, FastAPI, Starlette `TestClient`, `sqlite3`, pydantic v2, pytest.

**Spec:** `docs/superpowers/specs/2026-08-03-multi-tenant-department-hierarchy-design.md`. This plan covers spec §3–§5, §7–§10 (backend). Plan 2 covers §6 (console UI) and the extension poll change (§5 last bullet).

## Global Constraints

- **Raw `sqlite3`, no ORM.** Match the existing `app/db.py` style: SQL strings, `sqlite3.Row`, `PRAGMA foreign_keys = ON`.
- **I3 — no prompt text ever gets a column or a field.** Wire models set `model_config = ConfigDict(extra="forbid")`. Do not add any field that could carry prompt text. Do not quote a rejected input value in a validator `msg` (see `app/main.py`'s handler docstring).
- **Secret hashing rule (`app/security.py`):** generated high-entropy secrets → fast **SHA-256** (`hash_token`); only low-entropy human passwords need scrypt. Every credential in this plan is generated, so all use `hash_token`. Do **not** call `hash_password`/`verify_password` in new code.
- **Generated secrets are shown once, stored only as a hash.** `new_token(prefix)` returns `(plaintext, sha256hex)`.
- **Commits: sole author, no `Co-Authored-By` trailer** (repo convention — `git config user` already correct).
- **Tests use an in-memory DB.** `tests/conftest.py` sets `VANGUARD_POLICY_DB=":memory:"` before `app.main` imports. The connection is a **process-wide singleton shared across all test files**, so every test seeds its own company and resolves ids from what it authenticated as — never a bare `SELECT ... LIMIT 1`.
- **Run tests:** from `code/policy/`: `python -m pytest -q` (use the repo's `.venv`).
- **Cookie name stays `vg_admin`.** Session cookie is `httponly`, `samesite="lax"`.
- **`bump_policy_version(conn, org_id)` commits and returns the new int.** Every write that changes what `GET /v1/policy` would serve must call it. `policy_version` is per-org (a dept override bumps the whole org — accepted over-fetch, spec §10).

---

### Task 1: Schema + idempotent migration

**Files:**
- Modify: `code/policy/app/db.py` (extend `SCHEMA`, add `_migrate_hierarchy`, call it from `init_schema`)
- Test: `code/policy/tests/test_schema.py` (create)

**Interfaces:**
- Produces: tables `departments(id, org_id, name, admin_token_hash, created_at)`, `dept_llm_policy(org_id, department_id, llm_id, status)`; new columns `orgs.admin_token_hash`, `admin_sessions.role`, `admin_sessions.department_id`, `employees.department_id`, `enroll_tokens.department_id`.

- [ ] **Step 1: Write the failing test**

```python
# code/policy/tests/test_schema.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd code/policy && python -m pytest tests/test_schema.py -q`
Expected: FAIL (`departments` not in tables / columns missing).

- [ ] **Step 3: Add the new tables to `SCHEMA`**

Append these two `CREATE TABLE` blocks to the `SCHEMA` string in `app/db.py` (before the closing `"""`), and add `role`/`department_id` to the `admin_sessions` block, `admin_token_hash` to `orgs`, and `department_id` to `employees` and `enroll_tokens`. Full new definitions:

```sql
-- in orgs: add admin_token_hash (nullable: legacy rows had a password instead)
--   ... existing columns ...
--   admin_token_hash    TEXT,

-- replace the admin_sessions block with:
CREATE TABLE IF NOT EXISTS admin_sessions (
    token         TEXT PRIMARY KEY,
    org_id        TEXT NOT NULL REFERENCES orgs(id),
    role          TEXT NOT NULL DEFAULT 'company' CHECK (role IN ('company','department')),
    department_id TEXT REFERENCES departments(id),
    created_at    TEXT NOT NULL
);

-- new tables:
CREATE TABLE IF NOT EXISTS departments (
    id               TEXT PRIMARY KEY,
    org_id           TEXT NOT NULL REFERENCES orgs(id),
    name             TEXT NOT NULL,
    admin_token_hash TEXT NOT NULL UNIQUE,
    created_at       TEXT NOT NULL,
    UNIQUE (org_id, name)
);

CREATE TABLE IF NOT EXISTS dept_llm_policy (
    org_id        TEXT NOT NULL REFERENCES orgs(id),
    department_id TEXT NOT NULL REFERENCES departments(id),
    llm_id        TEXT NOT NULL REFERENCES llm_registry(id),
    status        TEXT NOT NULL CHECK (status IN ('approved','blocked')),
    PRIMARY KEY (department_id, llm_id)
);
```

In the `orgs` block add `admin_token_hash TEXT,` after `admin_password_hash`. In the `employees` and `enroll_tokens` blocks add `department_id TEXT REFERENCES departments(id),`.

- [ ] **Step 4: Add the migration for existing DBs**

In `app/db.py`, add and wire a migration mirroring `_migrate_appeals`:

```python
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
```

Update `init_schema`:

```python
def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    _migrate_appeals(conn)
    _migrate_hierarchy(conn)
    conn.commit()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd code/policy && python -m pytest tests/test_schema.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add code/policy/app/db.py code/policy/tests/test_schema.py
git commit -m "feat(policy): add departments, dept_llm_policy, and hierarchy columns"
```

---

### Task 2: Session helpers + scoped authorization guards

**Files:**
- Modify: `code/policy/app/security.py` (extend `issue_session`, add `resolve_session`)
- Create: `code/policy/app/authz.py`
- Test: `code/policy/tests/test_authz.py` (create)

**Interfaces:**
- Produces:
  - `issue_session(conn, org_id: str, role: str, department_id: str | None = None) -> str`
  - `resolve_session(conn, token: str | None) -> sqlite3.Row | None` (columns `org_id, role, department_id`)
  - `authz.require_company(token: str | None) -> str` (returns `org_id`; 401 if no session, 403 if not a company session)
  - `authz.require_department(token: str | None) -> tuple[str, str]` (returns `(org_id, department_id)`; 401 if no session, 403 if not a department session)

- [ ] **Step 1: Write the failing test**

```python
# code/policy/tests/test_authz.py
import pytest
from fastapi import HTTPException

from app import authz
from app.deps import get_conn
from app.security import issue_session, resolve_session


def _org() -> str:
    from app.seed import seed_company           # Task 4
    org_id, _secret = seed_company(get_conn(), "Authz Co")
    return org_id


def test_company_session_resolves_and_authorizes():
    conn = get_conn()
    org_id = _org()
    token = issue_session(conn, org_id, "company", None)
    row = resolve_session(conn, token)
    assert row["role"] == "company" and row["org_id"] == org_id
    assert authz.require_company(token) == org_id
    with pytest.raises(HTTPException) as e:
        authz.require_department(token)
    assert e.value.status_code == 403


def test_department_session_carries_department_id():
    conn = get_conn()
    org_id = _org()
    token = issue_session(conn, org_id, "department", "dept-123")
    assert authz.require_department(token) == (org_id, "dept-123")
    with pytest.raises(HTTPException) as e:
        authz.require_company(token)
    assert e.value.status_code == 403


def test_no_session_is_401():
    with pytest.raises(HTTPException) as e:
        authz.require_company(None)
    assert e.value.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd code/policy && python -m pytest tests/test_authz.py -q`
Expected: FAIL (`ImportError: cannot import name 'resolve_session'` or `app.authz`).

- [ ] **Step 3: Extend `security.py`**

Replace `issue_session` and `session_org` in `app/security.py` with:

```python
def issue_session(
    conn: sqlite3.Connection, org_id: str, role: str,
    department_id: str | None = None,
) -> str:
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO admin_sessions (token, org_id, role, department_id, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (token, org_id, role, department_id, now_iso()),
    )
    conn.commit()
    return token


def resolve_session(conn: sqlite3.Connection, token: str | None) -> sqlite3.Row | None:
    if not token:
        return None
    return conn.execute(
        "SELECT org_id, role, department_id FROM admin_sessions WHERE token = ?",
        (token,),
    ).fetchone()
```

- [ ] **Step 4: Create `app/authz.py`**

```python
"""Scoped authorization. Authority is decided server-side on every request.

A company session may reach /v1/admin/* only; a department session may reach
/v1/dept/* only. Role is read from the session row, never from the client."""
from fastapi import HTTPException

from app.deps import get_conn
from app.security import resolve_session


def _session(token: str | None):
    row = resolve_session(get_conn(), token)
    if row is None:
        raise HTTPException(status_code=401, detail="session required")
    return row


def require_company(token: str | None) -> str:
    row = _session(token)
    if row["role"] != "company":
        raise HTTPException(status_code=403, detail="company session required")
    return row["org_id"]


def require_department(token: str | None) -> tuple[str, str]:
    row = _session(token)
    if row["role"] != "department" or row["department_id"] is None:
        raise HTTPException(status_code=403, detail="department session required")
    return row["org_id"], row["department_id"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd code/policy && python -m pytest tests/test_authz.py -q`
Expected: PASS (3 passed). (Depends on Task 4's `seed_company`; if running strictly in order, implement Task 4 first — the two are commit-independent but this test imports `seed_company`.)

- [ ] **Step 6: Commit**

```bash
git add code/policy/app/security.py code/policy/app/authz.py code/policy/tests/test_authz.py
git commit -m "feat(policy): role-scoped sessions and authz guards"
```

---

### Task 3: Wire-model updates (login/signup/enroll response)

**Files:**
- Modify: `code/policy/app/models.py`
- Test: `code/policy/tests/test_models_hierarchy.py` (create)

**Interfaces:**
- Produces: `AdminLogin(role: Literal['company','department'], secret: str)`; `SignupRequest(company_name: str)`; `EnrollResponse` gains `department_id: str | None`.

- [ ] **Step 1: Write the failing test**

```python
# code/policy/tests/test_models_hierarchy.py
import pytest
from pydantic import ValidationError
from app.models import AdminLogin, SignupRequest, EnrollResponse


def test_admin_login_requires_a_valid_role():
    assert AdminLogin(role="company", secret="x").role == "company"
    with pytest.raises(ValidationError):
        AdminLogin(role="root", secret="x")


def test_signup_forbids_extra_fields():
    assert SignupRequest(company_name="Acme").company_name == "Acme"
    with pytest.raises(ValidationError):
        SignupRequest(company_name="Acme", password="sneaky")


def test_enroll_response_has_department_id_field():
    assert "department_id" in EnrollResponse.model_fields
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd code/policy && python -m pytest tests/test_models_hierarchy.py -q`
Expected: FAIL (`AdminLogin` still has `org_name`/`password`; `SignupRequest` undefined).

- [ ] **Step 3: Edit `app/models.py`**

Replace the `AdminLogin` class and add `SignupRequest`:

```python
class AdminLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["company", "department"]
    secret: str = Field(max_length=200)


class SignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company_name: str = Field(min_length=1, max_length=120)
```

In `EnrollResponse`, add the field:

```python
class EnrollResponse(BaseModel):
    org_id: str
    org_name: str
    pseudo_id: str
    department: str
    department_id: str | None = None
    policy: PolicyBody
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd code/policy && python -m pytest tests/test_models_hierarchy.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add code/policy/app/models.py code/policy/tests/test_models_hierarchy.py
git commit -m "feat(policy): role/secret login, signup, and department_id enrol models"
```

---

### Task 4: Seed helpers (company, department, employee token)

**Files:**
- Modify: `code/policy/app/seed.py`
- Test: `code/policy/tests/test_seed_helpers.py` (create)

**Interfaces:**
- Produces:
  - `seed_org_policy(conn, org_id: str) -> None` (inserts default `org_llm_policy` + `policy_category`)
  - `seed_company(conn, name: str) -> tuple[str, str]` → `(org_id, secret_plaintext)`
  - `create_department(conn, org_id: str, name: str) -> tuple[str, str]` → `(department_id, secret_plaintext)`
  - `mint_employee_token(conn, org_id: str, department_id: str, department_name: str) -> str` → token plaintext
- Consumes: `app.security.new_token`, `now_iso`; `REGISTRY`, `ETHICS_CATEGORIES`, `_DEFAULT_APPROVED`.

- [ ] **Step 1: Write the failing test**

```python
# code/policy/tests/test_seed_helpers.py
from app.deps import get_conn
from app.seed import seed_company, create_department, mint_employee_token
from app.security import hash_token


def test_seed_company_stores_only_the_hash_and_seeds_policy():
    conn = get_conn()
    org_id, secret = seed_company(conn, "Seedco")
    row = conn.execute("SELECT admin_token_hash FROM orgs WHERE id = ?", (org_id,)).fetchone()
    assert row["admin_token_hash"] == hash_token(secret)
    n = conn.execute("SELECT COUNT(*) c FROM org_llm_policy WHERE org_id = ?", (org_id,)).fetchone()["c"]
    assert n == 8  # one row per registry tool


def test_create_department_and_mint_token_are_linked_by_department_id():
    conn = get_conn()
    org_id, _ = seed_company(conn, "Seedco2")
    dept_id, dsecret = create_department(conn, org_id, "Engineering")
    assert conn.execute("SELECT admin_token_hash FROM departments WHERE id = ?", (dept_id,)).fetchone()["admin_token_hash"] == hash_token(dsecret)
    token = mint_employee_token(conn, org_id, dept_id, "Engineering")
    row = conn.execute("SELECT department_id, department FROM enroll_tokens WHERE token_hash = ?", (hash_token(token),)).fetchone()
    assert row["department_id"] == dept_id and row["department"] == "Engineering"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd code/policy && python -m pytest tests/test_seed_helpers.py -q`
Expected: FAIL (`ImportError: seed_company`).

- [ ] **Step 3: Refactor `app/seed.py`**

Add `import` of `new_token, now_iso` at top (`from app.security import hash_password, new_token, now_iso`). Replace `seed_demo_org` with the split helpers (keep `REGISTRY`, `ETHICS_CATEGORIES`, `_DEFAULT_APPROVED`, `seed_registry` unchanged):

```python
def seed_org_policy(conn: sqlite3.Connection, org_id: str) -> None:
    conn.executemany(
        "INSERT OR IGNORE INTO org_llm_policy (org_id, llm_id, status) VALUES (?, ?, ?)",
        [(org_id, llm_id, "approved" if llm_id in _DEFAULT_APPROVED else "blocked")
         for llm_id, _, _ in REGISTRY],
    )
    conn.executemany(
        "INSERT OR IGNORE INTO policy_category (org_id, key, label, enabled) VALUES (?, ?, ?, 1)",
        [(org_id, key, label) for key, label in ETHICS_CATEGORIES],
    )
    conn.commit()


def seed_company(conn: sqlite3.Connection, name: str) -> tuple[str, str]:
    """Create a company and return (org_id, admin_secret_plaintext)."""
    org_id = uuid.uuid4().hex
    plain, hashed = new_token("VG")
    conn.execute(
        "INSERT INTO orgs (id, name, admin_password_hash, admin_token_hash, policy_version)"
        " VALUES (?, ?, '', ?, 1)",
        (org_id, name, hashed),
    )
    seed_org_policy(conn, org_id)
    return org_id, plain


def create_department(conn: sqlite3.Connection, org_id: str, name: str) -> tuple[str, str]:
    dept_id = uuid.uuid4().hex
    plain, hashed = new_token(name[:3])
    conn.execute(
        "INSERT INTO departments (id, org_id, name, admin_token_hash, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (dept_id, org_id, name, hashed, now_iso()),
    )
    conn.commit()
    return dept_id, plain


def mint_employee_token(conn: sqlite3.Connection, org_id: str, department_id: str, department_name: str) -> str:
    plain, hashed = new_token(department_name[:3])
    conn.execute(
        "INSERT INTO enroll_tokens (id, org_id, department, department_id, token_hash, label, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (uuid.uuid4().hex, org_id, department_name, department_id, hashed, department_name, now_iso()),
    )
    conn.commit()
    return plain
```

`hash_password` stays imported only if still referenced elsewhere; if not, drop it from the import to avoid an unused-import lint. (It is now unused here — remove it.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd code/policy && python -m pytest tests/test_seed_helpers.py tests/test_authz.py -q`
Expected: PASS (5 passed — Task 2's test now resolves `seed_company`).

- [ ] **Step 5: Commit**

```bash
git add code/policy/app/seed.py code/policy/tests/test_seed_helpers.py
git commit -m "feat(policy): seed_company/create_department/mint_employee_token helpers"
```

---

### Task 5: Signup route

**Files:**
- Create: `code/policy/app/routes/signup.py`
- Modify: `code/policy/app/main.py` (include the router — see Task 12 for the full wiring; adding this router here is fine)
- Test: `code/policy/tests/test_signup.py` (create)

**Interfaces:**
- Consumes: `models.SignupRequest`, `seed.seed_company`.
- Produces: `POST /v1/signup {company_name}` → `201 {"org_id", "secret"}`; the secret then logs in as `role='company'`.

- [ ] **Step 1: Write the failing test**

```python
# code/policy/tests/test_signup.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_signup_returns_a_secret_that_logs_in_as_company():
    r = client.post("/v1/signup", json={"company_name": "Newco"})
    assert r.status_code == 201
    secret = r.json()["secret"]
    login = client.post("/v1/admin/login", json={"role": "company", "secret": secret})
    assert login.status_code == 200
    assert login.json()["org_name"] == "Newco"


def test_signup_forbids_a_smuggled_field():
    r = client.post("/v1/signup", json={"company_name": "X", "password": "y"})
    assert r.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd code/policy && python -m pytest tests/test_signup.py -q`
Expected: FAIL (404 on `/v1/signup`). *(The login half also depends on Task 6.)*

- [ ] **Step 3: Create `app/routes/signup.py`**

```python
from fastapi import APIRouter

from app.deps import get_conn
from app.models import SignupRequest
from app.seed import seed_company

router = APIRouter()


@router.post("/v1/signup", status_code=201)
async def signup(body: SignupRequest) -> dict[str, str]:
    """Create a company and return its Company Admin secret ONCE.

    The plaintext is returned here and never again -- only its SHA-256 is
    stored (orgs.admin_token_hash)."""
    org_id, secret = seed_company(get_conn(), body.company_name)
    return {"org_id": org_id, "secret": secret}
```

- [ ] **Step 4: Register the router in `app/main.py`**

In the router-import block, add `from app.routes import signup as _signup  # noqa: E402` and `app.include_router(_signup.router)` alongside the others.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd code/policy && python -m pytest tests/test_signup.py -q`
Expected: PASS **after Task 6** (login accepts `role/secret`). If run before Task 6, `test_signup_returns_a_secret_that_logs_in_as_company` fails at the login step — implement Task 6 next, then this passes.

- [ ] **Step 6: Commit**

```bash
git add code/policy/app/routes/signup.py code/policy/app/main.py code/policy/tests/test_signup.py
git commit -m "feat(policy): self-signup mints a company admin secret"
```

---

### Task 6: Role/secret login + logout

**Files:**
- Modify: `code/policy/app/routes/admin.py` (rewrite `login`; keep `logout`)
- Modify: `code/policy/tests/test_admin.py` (rewrite the two login tests + `_login` helper)
- Test: `code/policy/tests/test_login_roles.py` (create)

**Interfaces:**
- Consumes: `models.AdminLogin`, `security.issue_session`, `security.hash_token`.
- Produces:
  - `POST /v1/admin/login {role:'company', secret}` → `200 {"role":"company","org_id","org_name"}` + `vg_admin` cookie.
  - `POST /v1/admin/login {role:'department', secret}` → `200 {"role":"department","org_id","org_name","department_id","department"}` + cookie.
  - Bad secret → `401` with a body **identical** across "no such secret" for both roles.

- [ ] **Step 1: Write the failing test**

```python
# code/policy/tests/test_login_roles.py
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_conn
from app.seed import seed_company, create_department

client = TestClient(app)


def test_company_and_department_secrets_route_to_their_roles():
    org_id, co_secret = seed_company(get_conn(), "RolesCo")
    dept_id, dept_secret = create_department(get_conn(), org_id, "Sales")

    co = client.post("/v1/admin/login", json={"role": "company", "secret": co_secret})
    assert co.status_code == 200 and co.json()["role"] == "company"

    dept = client.post("/v1/admin/login", json={"role": "department", "secret": dept_secret})
    assert dept.status_code == 200
    body = dept.json()
    assert body["role"] == "department" and body["department"] == "Sales"
    assert body["department_id"] == dept_id


def test_a_company_secret_does_not_work_as_a_department_login():
    org_id, co_secret = seed_company(get_conn(), "RolesCo2")
    r = client.post("/v1/admin/login", json={"role": "department", "secret": co_secret})
    assert r.status_code == 401


def test_both_bad_secret_failures_are_identical():
    a = client.post("/v1/admin/login", json={"role": "company", "secret": "nope-1"})
    b = client.post("/v1/admin/login", json={"role": "department", "secret": "nope-2"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd code/policy && python -m pytest tests/test_login_roles.py -q`
Expected: FAIL (login still expects `org_name`/`password`; 422 or wrong shape).

- [ ] **Step 3: Rewrite `login` in `app/routes/admin.py`**

Replace the imports and the `login` function. New imports:

```python
from app.models import AppealDecision, AdminLogin
from app.security import hash_token, issue_session, now_iso
from app.authz import require_company
```

Remove the `_DUMMY_HASH`, `hash_password`, `verify_password`, `session_org` usages and the old `_require_admin`. New `login`:

```python
@router.post("/login")
async def login(body: AdminLogin, response: Response) -> dict[str, str]:
    conn = get_conn()
    h = hash_token(body.secret)
    if body.role == "company":
        row = conn.execute(
            "SELECT id, name FROM orgs WHERE admin_token_hash = ?", (h,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=401, detail="invalid credentials")
        token = issue_session(conn, row["id"], "company", None)
        response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax")
        return {"role": "company", "org_id": row["id"], "org_name": row["name"]}
    # department
    row = conn.execute(
        "SELECT d.id AS dept_id, d.org_id, d.name AS dept_name, o.name AS org_name"
        " FROM departments d JOIN orgs o ON o.id = d.org_id"
        " WHERE d.admin_token_hash = ?", (h,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = issue_session(conn, row["org_id"], "department", row["dept_id"])
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax")
    return {
        "role": "department", "org_id": row["org_id"], "org_name": row["org_name"],
        "department_id": row["dept_id"], "department": row["dept_name"],
    }
```

The secret is high-entropy, so a hash lookup is not password-guessable — the scrypt dummy-hash timing defense is intentionally gone. Update `logout` to use the guard:

```python
@router.post("/logout")
async def logout(response: Response, vg_admin: str | None = Cookie(default=None)) -> dict[str, bool]:
    require_company(vg_admin) if False else None  # replaced below
```

Actually replace `logout` cleanly — it must accept EITHER role, so it just needs a valid session:

```python
@router.post("/logout")
async def logout(response: Response, vg_admin: str | None = Cookie(default=None)) -> dict[str, bool]:
    from app.security import resolve_session
    if resolve_session(get_conn(), vg_admin) is None:
        raise HTTPException(status_code=401, detail="session required")
    get_conn().execute("DELETE FROM admin_sessions WHERE token = ?", (vg_admin,))
    get_conn().commit()
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}
```

- [ ] **Step 4: Fix `tests/test_admin.py`'s login helper and delete obsolete tests**

In `tests/test_admin.py`, replace `_login`, `_pseudo_id`, and the two password-era login tests. New helpers (used by later tasks too):

```python
from app.seed import seed_company, create_department, mint_employee_token

def _company_client() -> tuple[TestClient, str]:
    """A logged-in COMPANY client and its org_id."""
    org_id, secret = seed_company(get_conn(), "Acme " + uuid.uuid4().hex[:6])
    c = TestClient(app)
    assert c.post("/v1/admin/login", json={"role": "company", "secret": secret}).status_code == 200
    return c, org_id
```

Delete `test_login_with_the_wrong_password_is_401` and `test_login_nonexistent_org_and_wrong_password_return_same_response` (their replacements live in `test_login_roles.py`). The rest of `test_admin.py` is repaired in Task 8/9.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd code/policy && python -m pytest tests/test_login_roles.py tests/test_signup.py -q`
Expected: PASS (5 passed).

- [ ] **Step 6: Commit**

```bash
git add code/policy/app/routes/admin.py code/policy/tests/test_login_roles.py code/policy/tests/test_admin.py
git commit -m "feat(policy): role-picker login (company/department) on generated secrets"
```

---

### Task 7: Company departments routes (list / create / regenerate)

**Files:**
- Modify: `code/policy/app/routes/admin.py`
- Test: `code/policy/tests/test_departments.py` (create)

**Interfaces:**
- Consumes: `authz.require_company`, `seed.create_department` (reused for the create logic), `security.new_token`, `now_iso`.
- Produces:
  - `GET /v1/admin/departments` → `[{id, name, created_at, active_tokens}]`
  - `POST /v1/admin/departments {name}` → `201 {id, name, secret}` (409 on duplicate name)
  - `POST /v1/admin/departments/{id}/regenerate` → `200 {id, secret}` (404 if not this org's; also deletes that dept's live sessions)

- [ ] **Step 1: Write the failing test**

```python
# code/policy/tests/test_departments.py
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_conn
from app.seed import seed_company
from app.security import hash_token

client_module = TestClient(app)


def _company():
    org_id, secret = seed_company(get_conn(), "Dept Co " + uuid.uuid4().hex[:6])
    c = TestClient(app)
    c.post("/v1/admin/login", json={"role": "company", "secret": secret})
    return c, org_id


def test_create_lists_and_regenerate_department():
    c, org_id = _company()
    created = c.post("/v1/admin/departments", json={"name": "Engineering"})
    assert created.status_code == 201
    dept_id, old_secret = created.json()["id"], created.json()["secret"]

    listed = c.get("/v1/admin/departments").json()
    assert any(d["id"] == dept_id and d["name"] == "Engineering" for d in listed)

    # duplicate name is rejected
    assert c.post("/v1/admin/departments", json={"name": "Engineering"}).status_code == 409

    # the new department secret logs in as that department
    assert TestClient(app).post("/v1/admin/login", json={"role": "department", "secret": old_secret}).status_code == 200

    regen = c.post(f"/v1/admin/departments/{dept_id}/regenerate")
    assert regen.status_code == 200
    new_secret = regen.json()["secret"]
    # old secret no longer works; new one does
    assert TestClient(app).post("/v1/admin/login", json={"role": "department", "secret": old_secret}).status_code == 401
    assert TestClient(app).post("/v1/admin/login", json={"role": "department", "secret": new_secret}).status_code == 200


def test_departments_route_refuses_a_department_session():
    c, org_id = _company()
    dept_id = c.post("/v1/admin/departments", json={"name": "Sales"}).json()["id"]
    dept_secret = c.post(f"/v1/admin/departments/{dept_id}/regenerate").json()["secret"]
    dc = TestClient(app)
    dc.post("/v1/admin/login", json={"role": "department", "secret": dept_secret})
    assert dc.get("/v1/admin/departments").status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd code/policy && python -m pytest tests/test_departments.py -q`
Expected: FAIL (404 on `/v1/admin/departments`).

- [ ] **Step 3: Add the routes to `app/routes/admin.py`**

Add `import uuid` (already present) and `from app.security import new_token`. Append:

```python
@router.get("/departments")
async def list_departments(vg_admin: str | None = Cookie(default=None)) -> list[dict]:
    org_id = require_company(vg_admin)
    return [dict(r) for r in get_conn().execute(
        "SELECT d.id, d.name, d.created_at,"
        " (SELECT COUNT(*) FROM enroll_tokens t"
        "    WHERE t.department_id = d.id AND t.revoked = 0) AS active_tokens"
        " FROM departments d WHERE d.org_id = ? ORDER BY d.created_at DESC",
        (org_id,),
    )]


@router.post("/departments", status_code=201)
async def create_department_route(
    name: str = Body(embed=True), vg_admin: str | None = Cookie(default=None),
) -> dict[str, str]:
    org_id = require_company(vg_admin)
    conn = get_conn()
    if conn.execute(
        "SELECT 1 FROM departments WHERE org_id = ? AND name = ?", (org_id, name)
    ).fetchone():
        raise HTTPException(status_code=409, detail="department already exists")
    dept_id = uuid.uuid4().hex
    plain, hashed = new_token(name[:3])
    conn.execute(
        "INSERT INTO departments (id, org_id, name, admin_token_hash, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (dept_id, org_id, name, hashed, now_iso()),
    )
    conn.commit()
    # departments is never read by read_policy() -- no version bump.
    return {"id": dept_id, "name": name, "secret": plain}


@router.post("/departments/{dept_id}/regenerate")
async def regenerate_department(
    dept_id: str, vg_admin: str | None = Cookie(default=None),
) -> dict[str, str]:
    org_id = require_company(vg_admin)
    conn = get_conn()
    plain, hashed = new_token("DEP")
    cur = conn.execute(
        "UPDATE departments SET admin_token_hash = ? WHERE id = ? AND org_id = ?",
        (hashed, dept_id, org_id),
    )
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="unknown department")
    # Old secret is now dead; also drop any live sessions opened with it.
    conn.execute("DELETE FROM admin_sessions WHERE department_id = ?", (dept_id,))
    conn.commit()
    return {"id": dept_id, "secret": plain}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd code/policy && python -m pytest tests/test_departments.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add code/policy/app/routes/admin.py code/policy/tests/test_departments.py
git commit -m "feat(policy): company can create, list, and regenerate departments"
```

---

### Task 8: Re-scope company Tools / Usage / oversight; remove decide + tokens from admin

**Files:**
- Modify: `code/policy/app/routes/admin.py` (swap `_require_admin` → `require_company`; drop `mint_token`/`revoke_token`/`decide_request`/`decide_appeal`; make `list_requests`/`list_appeals` read-only oversight)
- Modify: `code/policy/tests/test_admin.py` (repair surviving tests)

**Interfaces:**
- Produces: `GET/POST /v1/admin/tools`, `GET /v1/admin/tools`, `GET /v1/admin/usage`, `GET /v1/admin/requests`, `GET /v1/admin/appeals` — all company-scoped, read-only for requests/appeals. Deciding + token minting now live under `/v1/dept/*` (Tasks 9–11).

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_admin.py
def test_company_oversight_requests_and_appeals_are_read_only():
    c, org_id = _company_client()
    # the POST decide routes no longer exist on /v1/admin
    assert c.post("/v1/admin/requests/anything", json={"decision": "approved"}).status_code == 404
    assert c.post("/v1/admin/tokens", json={"department": "X"}).status_code == 404


def test_company_can_see_all_departments_usage():
    c, org_id = _company_client()
    body = c.get("/v1/admin/usage").json()
    assert set(body.keys()) == {"by_department", "by_tool", "by_category"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd code/policy && python -m pytest tests/test_admin.py::test_company_oversight_requests_and_appeals_are_read_only -q`
Expected: FAIL (the `/v1/admin/tokens` POST still exists → 401/201, not 404).

- [ ] **Step 3: Edit `app/routes/admin.py`**

Across the file, replace every `org_id = _require_admin(vg_admin)` with `org_id = require_company(vg_admin)`, and **delete** these functions: `mint_token`, `revoke_token`, `list_tokens`, `decide_request`, `decide_appeal`. Keep and re-scope: `list_tools`, `set_tool`, `usage`, and turn `list_requests`/`list_appeals` into read-only oversight (they already only SELECT — just ensure they use `require_company`). Remove the now-unused `_require_admin` and `AppealDecision` import if `decide_appeal` was the only user (it was). `set_tool` still calls `bump_policy_version`.

- [ ] **Step 4: Repair the surviving `test_admin.py` tests**

The tests that used `_login()` + `_pseudo_id()` and the deleted routes must be updated or moved:
- Delete `test_minting_a_token_returns_the_plaintext_exactly_once`, `test_minting_and_revoking_a_token_do_not_bump_the_policy_version`, `test_deciding_a_request_*`, `test_denying_a_request_*`, `test_deciding_an_already_decided_request_*`, and the cross-tenant token/request test — their behavior moves to `test_dept_*` (Tasks 9–11) and `test_isolation` (Task 13/16).
- Keep and repair `test_approving_a_tool_bumps_the_policy_version`, `test_setting_an_unknown_tool_is_404_*`, `test_usage_aggregates_by_department_and_category`, `test_logout_actually_invalidates_the_session_*`, and the auth-sweep tests — replace `_login()` with `_company_client()[0]` and `bootstrap_demo()` org lookups with the `org_id` that helper returns. For `test_usage_aggregates...`, seed an employee via `mint_employee_token` + `/v1/enroll` (see Task 11's helper).
- Update the auth-sweep list: unauthenticated GETs to `/v1/admin/tools`, `/v1/admin/departments`, `/v1/admin/requests`, `/v1/admin/usage` return 401.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd code/policy && python -m pytest tests/test_admin.py -q`
Expected: PASS (all surviving/added tests green).

- [ ] **Step 6: Commit**

```bash
git add code/policy/app/routes/admin.py code/policy/tests/test_admin.py
git commit -m "refactor(policy): company admin routes are oversight-only; decide/tokens move to dept"
```

---

### Task 9: Department router — requests (list + decide → department override)

**Files:**
- Create: `code/policy/app/routes/dept.py`
- Modify: `code/policy/app/main.py` (include `dept.router`)
- Test: `code/policy/tests/test_dept_requests.py` (create)

**Interfaces:**
- Consumes: `authz.require_department`, `db.bump_policy_version`, `security.now_iso`.
- Produces (all under `APIRouter(prefix="/v1/dept")`, cookie `vg_admin`):
  - `GET /v1/dept/requests` → this dept's employees' requests (same row shape as the old admin list).
  - `POST /v1/dept/requests/{request_id} {decision}` → approve writes `dept_llm_policy` override + bumps org version; deny records only; 404 unknown-in-this-dept, 409 already-decided.
- Also provides the shared helper `_current_version(conn, org_id) -> int` used by deny.

- [ ] **Step 1: Write the failing test**

```python
# code/policy/tests/test_dept_requests.py
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_conn
from app.seed import seed_company, create_department, mint_employee_token

emp = TestClient(app)


def _dept_setup(dept_name="Engineering"):
    org_id, co_secret = seed_company(get_conn(), "DeptReq " + uuid.uuid4().hex[:6])
    dept_id, dept_secret = create_department(get_conn(), org_id, dept_name)
    token = mint_employee_token(get_conn(), org_id, dept_id, dept_name)
    pseudo = emp.post("/v1/enroll", json={"token": token}).json()["pseudo_id"]
    dc = TestClient(app)
    dc.post("/v1/admin/login", json={"role": "department", "secret": dept_secret})
    return org_id, dept_id, pseudo, dc


def test_dept_approval_writes_a_dept_override_not_company_policy():
    org_id, dept_id, pseudo, dc = _dept_setup()
    req_id = emp.post("/v1/requests", json={
        "pseudo_id": pseudo, "llm_id": "google", "reason": "translation"}).json()["id"]

    assert any(r["id"] == req_id for r in dc.get("/v1/dept/requests").json())
    assert dc.post(f"/v1/dept/requests/{req_id}", json={"decision": "approved"}).status_code == 200

    conn = get_conn()
    override = conn.execute(
        "SELECT status FROM dept_llm_policy WHERE department_id = ? AND llm_id = 'google'",
        (dept_id,)).fetchone()
    assert override["status"] == "approved"
    company = conn.execute(
        "SELECT status FROM org_llm_policy WHERE org_id = ? AND llm_id = 'google'",
        (org_id,)).fetchone()
    assert company["status"] == "blocked"   # company default untouched


def test_dept_a_cannot_see_or_decide_dept_b_requests():
    org_id, dept_a, pseudo_a, dc_a = _dept_setup("Alpha")
    # a second department in the SAME company, with its own employee + request
    dept_b, secret_b = create_department(get_conn(), org_id, "Beta")
    token_b = mint_employee_token(get_conn(), org_id, dept_b, "Beta")
    pseudo_b = emp.post("/v1/enroll", json={"token": token_b}).json()["pseudo_id"]
    req_b = emp.post("/v1/requests", json={
        "pseudo_id": pseudo_b, "llm_id": "xai", "reason": "probe"}).json()["id"]

    assert all(r["id"] != req_b for r in dc_a.get("/v1/dept/requests").json())
    assert dc_a.post(f"/v1/dept/requests/{req_b}", json={"decision": "approved"}).status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd code/policy && python -m pytest tests/test_dept_requests.py -q`
Expected: FAIL (404 on `/v1/dept/requests`).

- [ ] **Step 3: Create `app/routes/dept.py`**

```python
"""Department dashboard API. Every route is scoped to the session's
department_id -- a department admin can only ever see and act on its own
department's employees, requests, appeals, and tokens."""
import uuid

from fastapi import APIRouter, Body, Cookie, HTTPException

from app.authz import require_department
from app.db import bump_policy_version
from app.deps import get_conn
from app.models import AppealDecision
from app.security import new_token, now_iso

router = APIRouter(prefix="/v1/dept")


def _current_version(conn, org_id: str) -> int:
    return int(conn.execute(
        "SELECT policy_version FROM orgs WHERE id = ?", (org_id,)
    ).fetchone()["policy_version"])


@router.get("/requests")
async def dept_requests(vg_admin: str | None = Cookie(default=None)) -> list[dict]:
    org_id, dept_id = require_department(vg_admin)
    return [dict(r) for r in get_conn().execute(
        "SELECT a.id, a.reason, a.status, a.created_at, e.department,"
        "       r.display_name, r.host, a.llm_id"
        " FROM access_requests a"
        " JOIN employees e ON e.id = a.employee_id"
        " JOIN llm_registry r ON r.id = a.llm_id"
        " WHERE a.org_id = ? AND e.department_id = ? ORDER BY a.created_at DESC",
        (org_id, dept_id),
    )]


@router.post("/requests/{request_id}")
async def dept_decide_request(
    request_id: str, decision: str = Body(embed=True),
    vg_admin: str | None = Cookie(default=None),
) -> dict[str, int]:
    org_id, dept_id = require_department(vg_admin)
    if decision not in ("approved", "denied"):
        raise HTTPException(status_code=422, detail="decision must be approved or denied")
    conn = get_conn()
    row = conn.execute(
        "SELECT a.llm_id FROM access_requests a JOIN employees e ON e.id = a.employee_id"
        " WHERE a.id = ? AND a.org_id = ? AND e.department_id = ? AND a.status = 'pending'",
        (request_id, org_id, dept_id),
    ).fetchone()
    if row is None:
        exists = conn.execute(
            "SELECT 1 FROM access_requests a JOIN employees e ON e.id = a.employee_id"
            " WHERE a.id = ? AND a.org_id = ? AND e.department_id = ?",
            (request_id, org_id, dept_id),
        ).fetchone()
        raise HTTPException(status_code=404 if exists is None else 409,
                            detail="unknown request" if exists is None else "request already decided")

    conn.execute(
        "UPDATE access_requests SET status = ?, decided_at = ? WHERE id = ?",
        (decision, now_iso(), request_id),
    )
    if decision == "approved":
        conn.execute(
            "INSERT INTO dept_llm_policy (org_id, department_id, llm_id, status)"
            " VALUES (?, ?, ?, 'approved')"
            " ON CONFLICT(department_id, llm_id) DO UPDATE SET status = 'approved'",
            (org_id, dept_id, row["llm_id"]),
        )
        return {"version": bump_policy_version(conn, org_id)}
    conn.commit()
    return {"version": _current_version(conn, org_id)}
```

- [ ] **Step 4: Register the router in `app/main.py`**

Add `from app.routes import dept as _dept  # noqa: E402` and `app.include_router(_dept.router)`.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd code/policy && python -m pytest tests/test_dept_requests.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add code/policy/app/routes/dept.py code/policy/app/main.py code/policy/tests/test_dept_requests.py
git commit -m "feat(policy): department dashboard approves requests as dept-scoped overrides"
```

---

### Task 10: Department router — appeals (list + decide)

**Files:**
- Modify: `code/policy/app/routes/dept.py`
- Test: `code/policy/tests/test_dept_appeals.py` (create)

**Interfaces:**
- Produces: `GET /v1/dept/appeals` (this dept only) and `POST /v1/dept/appeals/{appeal_id}` (body `AppealDecision`: `{decision:'upheld'|'overturned', note?}`), with the same 404/409 split. Uses the existing `decision_appeals` table and one-time-pass columns untouched.

- [ ] **Step 1: Write the failing test**

```python
# code/policy/tests/test_dept_appeals.py
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_conn
from app.seed import seed_company, create_department, mint_employee_token

emp = TestClient(app)


def _setup():
    org_id, _ = seed_company(get_conn(), "DeptAppeal " + uuid.uuid4().hex[:6])
    dept_id, dept_secret = create_department(get_conn(), org_id, "Compliance")
    token = mint_employee_token(get_conn(), org_id, dept_id, "Compliance")
    pseudo = emp.post("/v1/enroll", json={"token": token}).json()["pseudo_id"]
    dc = TestClient(app)
    dc.post("/v1/admin/login", json={"role": "department", "secret": dept_secret})
    return org_id, dept_id, pseudo, dc


def test_dept_admin_decides_its_own_appeal():
    org_id, dept_id, pseudo, dc = _setup()
    appeal_id = emp.post("/v1/appeals", json={
        "pseudo_id": pseudo, "decision_type": "ethics",
        "category": "security_evasion", "reason": "false positive"}).json()["id"]
    assert any(a["id"] == appeal_id for a in dc.get("/v1/dept/appeals").json())
    r = dc.post(f"/v1/dept/appeals/{appeal_id}", json={"decision": "overturned", "note": "ok"})
    assert r.status_code == 200 and r.json()["status"] == "overturned"
    # second decision on a decided appeal is 409
    assert dc.post(f"/v1/dept/appeals/{appeal_id}", json={"decision": "upheld"}).status_code == 409
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd code/policy && python -m pytest tests/test_dept_appeals.py -q`
Expected: FAIL (404 on `/v1/dept/appeals`).

- [ ] **Step 3: Add the routes to `app/routes/dept.py`**

```python
@router.get("/appeals")
async def dept_appeals(vg_admin: str | None = Cookie(default=None)) -> list[dict]:
    org_id, dept_id = require_department(vg_admin)
    return [dict(r) for r in get_conn().execute(
        "SELECT a.id, a.decision_type, a.category, a.employee_reason, a.disclosed_text,"
        "       a.status, a.admin_note, a.created_at, e.department"
        " FROM decision_appeals a JOIN employees e ON e.id = a.employee_id"
        " WHERE a.org_id = ? AND e.department_id = ? ORDER BY a.created_at DESC",
        (org_id, dept_id),
    )]


@router.post("/appeals/{appeal_id}")
async def dept_decide_appeal(
    appeal_id: str, body: AppealDecision,
    vg_admin: str | None = Cookie(default=None),
) -> dict[str, str]:
    org_id, dept_id = require_department(vg_admin)
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM decision_appeals a JOIN employees e ON e.id = a.employee_id"
        " WHERE a.id = ? AND a.org_id = ? AND e.department_id = ? AND a.status = 'pending'",
        (appeal_id, org_id, dept_id),
    ).fetchone()
    if row is None:
        exists = conn.execute(
            "SELECT 1 FROM decision_appeals a JOIN employees e ON e.id = a.employee_id"
            " WHERE a.id = ? AND a.org_id = ? AND e.department_id = ?",
            (appeal_id, org_id, dept_id),
        ).fetchone()
        raise HTTPException(status_code=404 if exists is None else 409,
                            detail="unknown appeal" if exists is None else "appeal already decided")
    conn.execute(
        "UPDATE decision_appeals SET status = ?, admin_note = ?, decided_at = ? WHERE id = ?",
        (body.decision, body.note, now_iso(), appeal_id),
    )
    conn.commit()
    return {"status": body.decision}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd code/policy && python -m pytest tests/test_dept_appeals.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add code/policy/app/routes/dept.py code/policy/tests/test_dept_appeals.py
git commit -m "feat(policy): department dashboard decides its own appeals"
```

---

### Task 11: Department router — employee tokens (list / mint / revoke)

**Files:**
- Modify: `code/policy/app/routes/dept.py`
- Test: `code/policy/tests/test_dept_tokens.py` (create)

**Interfaces:**
- Produces:
  - `GET /v1/dept/tokens` → `[{id, department, label, created_at, revoked}]` for this dept only.
  - `POST /v1/dept/tokens` → `201 {id, department, token}` (token carries this `department_id`; no version bump).
  - `POST /v1/dept/tokens/{token_id}/revoke` → `200 {ok}` (scoped to this dept).

- [ ] **Step 1: Write the failing test**

```python
# code/policy/tests/test_dept_tokens.py
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_conn
from app.seed import seed_company, create_department

emp = TestClient(app)


def _dept():
    org_id, _ = seed_company(get_conn(), "DeptTok " + uuid.uuid4().hex[:6])
    dept_id, secret = create_department(get_conn(), org_id, "Support")
    dc = TestClient(app)
    dc.post("/v1/admin/login", json={"role": "department", "secret": secret})
    return org_id, dept_id, dc


def test_minted_employee_token_enrols_into_this_department():
    org_id, dept_id, dc = _dept()
    minted = dc.post("/v1/dept/tokens", json={})
    assert minted.status_code == 201
    token = minted.json()["token"]
    enrolled = emp.post("/v1/enroll", json={"token": token}).json()
    assert enrolled["department"] == "Support"
    assert enrolled["department_id"] == dept_id
    # list never leaks plaintext
    assert all("token" not in r for r in dc.get("/v1/dept/tokens").json())


def test_revoke_is_scoped_to_the_department():
    org_id, dept_id, dc = _dept()
    tok_id = dc.post("/v1/dept/tokens", json={}).json()["id"]
    assert dc.post(f"/v1/dept/tokens/{tok_id}/revoke").status_code == 200
    assert get_conn().execute(
        "SELECT revoked FROM enroll_tokens WHERE id = ?", (tok_id,)).fetchone()["revoked"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd code/policy && python -m pytest tests/test_dept_tokens.py -q`
Expected: FAIL (404 on `/v1/dept/tokens`).

- [ ] **Step 3: Add the routes to `app/routes/dept.py`**

```python
@router.get("/tokens")
async def dept_tokens(vg_admin: str | None = Cookie(default=None)) -> list[dict]:
    org_id, dept_id = require_department(vg_admin)
    return [dict(r) for r in get_conn().execute(
        "SELECT id, department, label, created_at, revoked FROM enroll_tokens"
        " WHERE org_id = ? AND department_id = ? ORDER BY created_at DESC",
        (org_id, dept_id),
    )]


@router.post("/tokens", status_code=201)
async def dept_mint_token(vg_admin: str | None = Cookie(default=None)) -> dict[str, str]:
    org_id, dept_id = require_department(vg_admin)
    conn = get_conn()
    dept_name = conn.execute(
        "SELECT name FROM departments WHERE id = ?", (dept_id,)
    ).fetchone()["name"]
    plain, hashed = new_token(dept_name[:3])
    token_id = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO enroll_tokens (id, org_id, department, department_id, token_hash, label, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (token_id, org_id, dept_name, dept_id, hashed, dept_name, now_iso()),
    )
    conn.commit()
    # enroll_tokens is never read by read_policy() -- no version bump.
    return {"id": token_id, "department": dept_name, "token": plain}


@router.post("/tokens/{token_id}/revoke")
async def dept_revoke_token(
    token_id: str, vg_admin: str | None = Cookie(default=None),
) -> dict[str, bool]:
    org_id, dept_id = require_department(vg_admin)
    conn = get_conn()
    conn.execute(
        "UPDATE enroll_tokens SET revoked = 1"
        " WHERE id = ? AND org_id = ? AND department_id = ?",
        (token_id, org_id, dept_id),
    )
    conn.commit()
    return {"ok": True}
```

`POST /v1/dept/tokens` takes no body (department is from the session). The test posts `json={}`; FastAPI accepts an empty body for a no-parameter route.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd code/policy && python -m pytest tests/test_dept_tokens.py -q`
Expected: PASS **after Task 12** (enrol must return `department_id`). If run before Task 12, `enrolled["department_id"]` is `None` — implement Task 12, then this passes.

- [ ] **Step 5: Commit**

```bash
git add code/policy/app/routes/dept.py code/policy/tests/test_dept_tokens.py
git commit -m "feat(policy): department dashboard mints and revokes its own employee tokens"
```

---

### Task 12: Department-aware policy read, `/v1/policy`, and enrol

**Files:**
- Modify: `code/policy/app/routes/policy_read.py` (add `department_id` param + `coalesce`)
- Modify: `code/policy/app/routes/policy.py` (`department_id` query param + ETag)
- Modify: `code/policy/app/routes/enroll.py` (set `employees.department_id`; return `department_id`)
- Modify: `code/policy/app/routes/dept.py` (add `GET /v1/dept/tools` + `GET /v1/dept/usage`)
- Test: `code/policy/tests/test_dept_policy.py` (create)

**Interfaces:**
- Produces:
  - `read_policy(conn, org_id, department_id: str | None = None) -> PolicyBody` (tools = `coalesce(dept override, company default)` when `department_id` given).
  - `GET /v1/policy?org_id=&department_id=` with ETag `W/"{org_id}-{department_id or '_'}-{version}"`.
  - `/v1/enroll` returns `department_id` and stamps it on the employee.
  - `GET /v1/dept/tools` (effective, read-only) and `GET /v1/dept/usage` (`{by_department, by_tool, by_category}` for this dept).

- [ ] **Step 1: Write the failing test**

```python
# code/policy/tests/test_dept_policy.py
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_conn
from app.seed import seed_company, create_department, mint_employee_token

emp = TestClient(app)


def test_effective_policy_applies_the_department_override_only_to_that_dept():
    org_id, _ = seed_company(get_conn(), "PolCo " + uuid.uuid4().hex[:6])
    dept_a, sec_a = create_department(get_conn(), org_id, "Alpha")
    dept_b, sec_b = create_department(get_conn(), org_id, "Beta")
    tok_a = mint_employee_token(get_conn(), org_id, dept_a, "Alpha")
    tok_b = mint_employee_token(get_conn(), org_id, dept_b, "Beta")

    ea = emp.post("/v1/enroll", json={"token": tok_a}).json()
    eb = emp.post("/v1/enroll", json={"token": tok_b}).json()
    assert ea["department_id"] == dept_a

    # Dept A approves google via its dashboard.
    dc = TestClient(app)
    dc.post("/v1/admin/login", json={"role": "department", "secret": sec_a})
    req = emp.post("/v1/requests", json={
        "pseudo_id": ea["pseudo_id"], "llm_id": "google", "reason": "x"}).json()["id"]
    dc.post(f"/v1/dept/requests/{req}", json={"decision": "approved"})

    pa = emp.get("/v1/policy", params={"org_id": org_id, "department_id": dept_a}).json()
    pb = emp.get("/v1/policy", params={"org_id": org_id, "department_id": dept_b}).json()
    assert {t["llm_id"]: t["status"] for t in pa["tools"]}["google"] == "approved"
    assert {t["llm_id"]: t["status"] for t in pb["tools"]}["google"] == "blocked"


def test_policy_etag_differs_by_department():
    org_id, _ = seed_company(get_conn(), "PolEtag " + uuid.uuid4().hex[:6])
    dept_a, _ = create_department(get_conn(), org_id, "A")
    dept_b, _ = create_department(get_conn(), org_id, "B")
    ea = emp.get("/v1/policy", params={"org_id": org_id, "department_id": dept_a}).headers["etag"]
    eb = emp.get("/v1/policy", params={"org_id": org_id, "department_id": dept_b}).headers["etag"]
    assert ea != eb
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd code/policy && python -m pytest tests/test_dept_policy.py -q`
Expected: FAIL (`department_id` unknown param / ETag identical / override not applied).

- [ ] **Step 3: Update `read_policy`**

Replace the tools query in `app/routes/policy_read.py`:

```python
def read_policy(conn, org_id, department_id=None):
    org = conn.execute(
        "SELECT name, policy_version FROM orgs WHERE id = ?", (org_id,)
    ).fetchone()
    if department_id is None:
        tool_rows = conn.execute(
            "SELECT r.id, r.host, r.display_name, p.status"
            " FROM llm_registry r JOIN org_llm_policy p ON p.llm_id = r.id"
            " WHERE p.org_id = ? ORDER BY r.display_name",
            (org_id,),
        )
    else:
        tool_rows = conn.execute(
            "SELECT r.id, r.host, r.display_name,"
            "       COALESCE(dp.status, cp.status) AS status"
            " FROM llm_registry r"
            " JOIN org_llm_policy cp ON cp.llm_id = r.id AND cp.org_id = ?"
            " LEFT JOIN dept_llm_policy dp ON dp.llm_id = r.id AND dp.department_id = ?"
            " ORDER BY r.display_name",
            (org_id, department_id),
        )
    tools = [ToolPolicy(llm_id=r["id"], host=r["host"],
                        display_name=r["display_name"], status=r["status"]) for r in tool_rows]
    categories = [CategoryPolicy(key=r["key"], label=r["label"], enabled=bool(r["enabled"]))
                  for r in conn.execute(
        "SELECT key, label, enabled FROM policy_category WHERE org_id = ? ORDER BY key", (org_id,))]
    return PolicyBody(org_id=org_id, org_name=org["name"],
                      version=int(org["policy_version"]), tools=tools, categories=categories)
```

- [ ] **Step 4: Update `/v1/policy` (`app/routes/policy.py`)**

```python
def _etag(org_id: str, department_id: str | None, version: int) -> str:
    return f'W/"{org_id}-{department_id or "_"}-{version}"'


@router.get("/v1/policy", response_model=PolicyBody)
async def get_policy(
    org_id: str, response: Response,
    if_none_match: str | None = Header(default=None),
    department_id: str | None = None,
):
    conn = get_conn()
    row = conn.execute("SELECT policy_version FROM orgs WHERE id = ?", (org_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="unknown org")
    tag = _etag(org_id, department_id, int(row["policy_version"]))
    if if_none_match == tag:
        return Response(status_code=304, headers={"ETag": tag})
    response.headers["ETag"] = tag
    return read_policy(conn, org_id, department_id)
```

- [ ] **Step 5: Update `/v1/enroll` (`app/routes/enroll.py`)**

```python
    row = conn.execute(
        "SELECT org_id, department, department_id FROM enroll_tokens"
        " WHERE token_hash = ? AND revoked = 0",
        (hash_token(body.token),),
    ).fetchone()
    ...
    conn.execute(
        "INSERT INTO employees (id, org_id, pseudo_id, department, department_id, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (employee_id, row["org_id"], pseudo_id, row["department"], row["department_id"], now_iso()),
    )
    conn.commit()
    policy = read_policy(conn, row["org_id"], row["department_id"])
    return EnrollResponse(
        org_id=row["org_id"], org_name=policy.org_name, pseudo_id=pseudo_id,
        department=row["department"], department_id=row["department_id"], policy=policy,
    )
```

- [ ] **Step 6: Add `GET /v1/dept/tools` and `GET /v1/dept/usage` to `app/routes/dept.py`**

```python
@router.get("/tools")
async def dept_tools(vg_admin: str | None = Cookie(default=None)) -> list[dict]:
    org_id, dept_id = require_department(vg_admin)
    return [dict(r) for r in get_conn().execute(
        "SELECT r.id AS llm_id, r.host, r.display_name,"
        "       COALESCE(dp.status, cp.status) AS status"
        " FROM llm_registry r"
        " JOIN org_llm_policy cp ON cp.llm_id = r.id AND cp.org_id = ?"
        " LEFT JOIN dept_llm_policy dp ON dp.llm_id = r.id AND dp.department_id = ?"
        " ORDER BY r.display_name",
        (org_id, dept_id),
    )]


@router.get("/usage")
async def dept_usage(vg_admin: str | None = Cookie(default=None)) -> dict[str, list[dict]]:
    org_id, dept_id = require_department(vg_admin)
    conn = get_conn()
    by_department = [dict(r) for r in conn.execute(
        "SELECT e.department, COUNT(*) AS events"
        " FROM usage_events u JOIN employees e ON e.id = u.employee_id"
        " WHERE u.org_id = ? AND e.department_id = ? GROUP BY e.department",
        (org_id, dept_id),
    )]
    by_tool = [dict(r) for r in conn.execute(
        "SELECT u.host, COUNT(*) AS events"
        " FROM usage_events u JOIN employees e ON e.id = u.employee_id"
        " WHERE u.org_id = ? AND e.department_id = ? GROUP BY u.host ORDER BY events DESC",
        (org_id, dept_id),
    )]
    by_category = [dict(r) for r in conn.execute(
        "SELECT u.category, COUNT(*) AS events"
        " FROM usage_events u JOIN employees e ON e.id = u.employee_id"
        " WHERE u.org_id = ? AND e.department_id = ? AND u.category IS NOT NULL"
        " GROUP BY u.category ORDER BY events DESC",
        (org_id, dept_id),
    )]
    return {"by_department": by_department, "by_tool": by_tool, "by_category": by_category}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd code/policy && python -m pytest tests/test_dept_policy.py tests/test_dept_tokens.py -q`
Expected: PASS (4 passed).

- [ ] **Step 8: Commit**

```bash
git add code/policy/app/routes/policy_read.py code/policy/app/routes/policy.py code/policy/app/routes/enroll.py code/policy/app/routes/dept.py code/policy/tests/test_dept_policy.py
git commit -m "feat(policy): department-scoped effective policy, enrol, and dept tools/usage"
```

---

### Task 13: Rewire `main.py`, rewrite the seed script, write `DEMO-TOKENS.md`

**Files:**
- Modify: `code/policy/app/main.py` (remove `bootstrap_demo`/`seed_demo_org` usage; keep static mount + validation handler)
- Rewrite: `code/policy/scripts/seed.py`
- Test: `code/policy/tests/test_seed_script.py` (create)

**Interfaces:**
- Consumes: `seed.seed_company`, `seed.create_department`, `seed.mint_employee_token`.
- Produces: a runnable `python scripts/seed.py` that builds the demo world and writes `code/policy/DEMO-TOKENS.md`.

- [ ] **Step 1: Write the failing test**

```python
# code/policy/tests/test_seed_script.py
from pathlib import Path
import importlib


def test_build_demo_world_writes_a_tokens_file(tmp_path, monkeypatch):
    import scripts.seed as seedmod
    importlib.reload(seedmod)
    out = tmp_path / "DEMO-TOKENS.md"
    summary = seedmod.build_demo_world(out_path=out)
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "Company Admin secret" in text
    assert summary["company_secret"] in text
    # every department and its secret is recorded
    for dept in summary["departments"]:
        assert dept["name"] in text and dept["secret"] in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd code/policy && python -m pytest tests/test_seed_script.py -q`
Expected: FAIL (`build_demo_world` undefined).

- [ ] **Step 3: Rewrite `scripts/seed.py`**

```python
"""Build the demo world and record every secret/token in DEMO-TOKENS.md.

Run before a demo:  python scripts/seed.py

DEMO / TESTING ONLY. Real deployments never write secrets to disk -- a secret
is shown once and stored only as a hash. This file is git-ignored; each machine
regenerates its own set by running this script.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.deps import get_conn                                    # noqa: E402
from app.seed import seed_company, create_department, mint_employee_token  # noqa: E402

DEPARTMENTS = ["Engineering", "Sales", "Compliance"]
TOKENS_PER_DEPT = 2
DEFAULT_OUT = Path(__file__).parent.parent / "DEMO-TOKENS.md"


def build_demo_world(company: str = "Acme Corp", out_path: Path = DEFAULT_OUT) -> dict:
    conn = get_conn()
    org_id, company_secret = seed_company(conn, company)
    depts = []
    for name in DEPARTMENTS:
        dept_id, dept_secret = create_department(conn, org_id, name)
        tokens = [mint_employee_token(conn, org_id, dept_id, name) for _ in range(TOKENS_PER_DEPT)]
        depts.append({"id": dept_id, "name": name, "secret": dept_secret, "tokens": tokens})

    lines = [
        f"# Demo credentials — {company}", "",
        "> **DEMO / TESTING ONLY.** Real deployments never write secrets to disk;",
        "> a secret is shown once and stored only as a hash. This file is",
        "> git-ignored and regenerated on each machine by `python scripts/seed.py`.",
        "", "## Company dashboard (role: **Company Admin**)",
        "- URL: http://localhost:8001/",
        f"- Org ID: `{org_id}`",
        f"- **Company Admin secret:** `{company_secret}`", "",
        "## Department dashboards (role: **Department Admin**)", "",
        "| Department | Department Admin secret |", "|---|---|",
    ]
    for d in depts:
        lines.append(f"| {d['name']} | `{d['secret']}` |")
    lines += ["", "## Employee tokens (paste into the extension)", ""]
    for d in depts:
        lines.append(f"### {d['name']}")
        for t in d["tokens"]:
            lines.append(f"- `{t}`")
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return {"org_id": org_id, "company_secret": company_secret, "departments": depts}


if __name__ == "__main__":
    summary = build_demo_world()
    print(f"org: Acme Corp ({summary['org_id']})")
    print(f"company secret: {summary['company_secret']}")
    for d in summary["departments"]:
        print(f"  {d['name']:<12} dept secret: {d['secret']}")
    print(f"\nAll secrets written to {DEFAULT_OUT}")
```

- [ ] **Step 4: Clean up `app/main.py`**

Remove `from app.seed import seed_demo_org` and the `bootstrap_demo` function (nothing imports it after the test rewrites). Keep the validation handler, `/healthz`, all `include_router` calls (now including `_signup` and `_dept`), and the static mount. If any test still imports `bootstrap_demo`, it was replaced in Tasks 6/8 — grep to confirm: `git grep bootstrap_demo code/policy/tests` should return nothing.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd code/policy && python -m pytest tests/test_seed_script.py -q`
Expected: PASS (1 passed).

- [ ] **Step 6: Commit**

```bash
git add code/policy/scripts/seed.py code/policy/app/main.py code/policy/tests/test_seed_script.py
git commit -m "feat(policy): demo seed builds the three-tier world and records DEMO-TOKENS.md"
```

---

### Task 14: End-to-end sequence + cross-tenant isolation

**Files:**
- Rewrite: `code/policy/tests/test_end_to_end.py`
- Test: also covers cross-company isolation (folded in from the old `test_admin.py` cross-tenant test).

**Interfaces:**
- Consumes: everything above. This is the demo narrative through the real HTTP boundary.

- [ ] **Step 1: Write the failing/updated test**

```python
# code/policy/tests/test_end_to_end.py
"""signup -> create dept -> mint employee token -> enrol -> dept-scoped block
-> request -> department approves (override) -> employee's next poll sees it."""
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_conn
from app.seed import seed_company, create_department

employee = TestClient(app)
company = TestClient(app)


def test_full_three_tier_sequence():
    # 1. Self-signup creates the company.
    secret = company.post("/v1/signup", json={"company_name": "Acme " + uuid.uuid4().hex[:6]}).json()["secret"]
    login = company.post("/v1/admin/login", json={"role": "company", "secret": secret})
    assert login.status_code == 200
    org_id = login.json()["org_id"]

    # 2. Company creates a department -> gets its dept secret.
    created = company.post("/v1/admin/departments", json={"name": "Engineering"})
    dept_id, dept_secret = created.json()["id"], created.json()["secret"]

    # 3. Department admin logs in and mints an employee token.
    dept = TestClient(app)
    dept.post("/v1/admin/login", json={"role": "department", "secret": dept_secret})
    token = dept.post("/v1/dept/tokens", json={}).json()["token"]

    # 4. Employee enrols; google starts blocked (company default).
    enrolled = employee.post("/v1/enroll", json={"token": token}).json()
    assert enrolled["department_id"] == dept_id
    tools = {t["llm_id"]: t["status"] for t in enrolled["policy"]["tools"]}
    assert tools["google"] == "blocked"
    version_before = enrolled["policy"]["version"]

    poll = employee.get("/v1/policy", params={"org_id": org_id, "department_id": dept_id})
    etag_before = poll.headers["etag"]
    assert employee.get("/v1/policy",
                        params={"org_id": org_id, "department_id": dept_id},
                        headers={"If-None-Match": etag_before}).status_code == 304

    # 5. Employee requests google; department approves.
    req = employee.post("/v1/requests", json={
        "pseudo_id": enrolled["pseudo_id"], "llm_id": "google", "reason": "QA"}).json()["id"]
    assert any(r["id"] == req for r in dept.get("/v1/dept/requests").json())
    decided = dept.post(f"/v1/dept/requests/{req}", json={"decision": "approved"})
    assert decided.json()["version"] > version_before

    # 6. The employee's next poll sees google approved for THIS department.
    refreshed = employee.get("/v1/policy",
                             params={"org_id": org_id, "department_id": dept_id},
                             headers={"If-None-Match": etag_before})
    assert refreshed.status_code == 200
    assert {t["llm_id"]: t["status"] for t in refreshed.json()["tools"]}["google"] == "approved"


def test_two_companies_are_isolated():
    s1 = company.post("/v1/signup", json={"company_name": "One " + uuid.uuid4().hex[:6]}).json()["secret"]
    c1 = TestClient(app); c1.post("/v1/admin/login", json={"role": "company", "secret": s1})
    dept1 = c1.post("/v1/admin/departments", json={"name": "D1"}).json()

    s2 = company.post("/v1/signup", json={"company_name": "Two " + uuid.uuid4().hex[:6]}).json()["secret"]
    c2 = TestClient(app); c2.post("/v1/admin/login", json={"role": "company", "secret": s2})

    # Company Two must not see Company One's department, nor regenerate it.
    assert all(d["id"] != dept1["id"] for d in c2.get("/v1/admin/departments").json())
    assert c2.post(f"/v1/admin/departments/{dept1['id']}/regenerate").status_code == 404
```

- [ ] **Step 2: Run the whole suite**

Run: `cd code/policy && python -m pytest -q`
Expected: PASS (all files green). Fix any residual references to deleted helpers (`bootstrap_demo`, `_login`, `_pseudo_id`, `seed_demo_org`) surfaced here.

- [ ] **Step 3: Commit**

```bash
git add code/policy/tests/test_end_to_end.py
git commit -m "test(policy): three-tier end-to-end sequence and cross-company isolation"
```

---

### Task 15: Full-suite green + README/DEMO-TOKENS note

**Files:**
- Modify: `code/policy/README.md` (document signup, role login, department dashboards, reseed)
- Verify: whole `code/policy` suite.

- [ ] **Step 1: Run the full suite**

Run: `cd code/policy && python -m pytest -q`
Expected: PASS (0 failed). If red, fix the failing test's file (most likely a stale `test_appeals.py` helper that used the old admin decide route — repoint appeal decisions to `/v1/dept/appeals/{id}`).

- [ ] **Step 2: Check `test_appeals.py` specifically**

Run: `cd code/policy && python -m pytest tests/test_appeals.py -q`
Expected: PASS. If it used `/v1/admin/appeals/{id}` to decide, update those calls to log in as the department admin and POST `/v1/dept/appeals/{id}` (same body). The one-time-pass endpoints (`/v1/appeals/allowances*`) are unchanged.

- [ ] **Step 3: Update `code/policy/README.md`**

Replace the login/enrolment description with: self-signup at `/` (company name → Company Admin secret, once); role-picker login (Company Admin vs Department Admin, paste secret); company creates departments and hands each a Department Admin secret; department admin mints employee tokens; employees paste the token into the extension. Add: "Reseed the demo: delete `policy.db`, run `python scripts/seed.py` — every secret is written to `DEMO-TOKENS.md` (git-ignored)."

- [ ] **Step 4: Commit**

```bash
git add code/policy/README.md
git commit -m "docs(policy): document three-tier signup, role login, and reseed"
```

---

## Self-Review

**Spec coverage:**
- §3 data model → Task 1. §4 auth/sessions/signup/login → Tasks 2, 3, 5, 6. §5 API (company) → Tasks 7, 8; (department) → Tasks 9–12; shared policy/enrol → Task 12. §7 seed + DEMO-TOKENS → Task 13. §8 migration → Task 1 (`_migrate_hierarchy`). §9 tests → every task + Tasks 14–15. §10 consequences: per-org version bump (Task 9 comment + `bump_policy_version`), scrypt drop (Task 6), dept-secret regenerate recovery (Task 7), pseudonymity preserved (no name columns added anywhere).
- §6 console UI and the extension poll change are **Plan 2** (stated in the header) — not a gap.

**Placeholder scan:** every code step contains complete code; every run step has an exact command + expected result. No TBD/TODO.

**Type consistency:** `issue_session(conn, org_id, role, department_id=None)` and `resolve_session(...)` used identically in Tasks 2/6/9. `require_company`→`org_id`, `require_department`→`(org_id, department_id)` used consistently. `read_policy(conn, org_id, department_id=None)` signature matches its callers in `policy.py` and `enroll.py`. `EnrollResponse.department_id` added in Task 3 and populated in Task 12. `_etag(org_id, department_id, version)` matches its single call site.

**Cross-task ordering note:** Tasks 2 and 5 import symbols delivered in Tasks 4 and 6 respectively; the plan flags this inline. If executed strictly 1→15 the only red-until-next-task cases are called out in their Step 5 notes (Task 5 login, Task 11 enrol `department_id`). All resolve by Task 12; Task 14 runs the whole suite green.
