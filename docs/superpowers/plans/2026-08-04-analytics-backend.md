# Analytics & Insider-Risk — Backend Plan (1 of 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add server-side support for the analytics dashboards: admin-supplied employee names on tokens, a shared aggregation helper over `usage_events`, and company- and department-scoped analytics endpoints, plus demo seed data.

**Architecture:** A new `app/analytics.py` computes a summary and an alerts list with plain SQL over the existing `usage_events` (no rollup tables). Names are an admin label carried on `enroll_tokens.name` and copied to `employees.name` at enrol. Company routes use `require_company`; department routes use `require_department` and pass the session's `department_id` as a filter.

**Tech Stack:** Python 3, FastAPI, raw `sqlite3`, pydantic v2, pytest.

**Spec:** `docs/superpowers/specs/2026-08-04-analytics-insider-risk-design.md` §2–3, §6–7.

## Global Constraints

- **Raw `sqlite3`, no ORM.** Match `app/db.py` style. `PRAGMA foreign_keys = ON` is always set by `connect()`.
- **I3:** no prompt-content column, no prompt text anywhere. Analytics reads only class/count/host/type/ts and the admin-supplied name.
- **Risk weights (fixed, exact):** `ethics_block=5`, `pii_block=3`, `warn_shown=1`, `visit_unapproved=1`, `request_sent=0`.
- **Severity:** high = `{ethics_block, pii_block}`, medium = `{warn_shown}`, low = `{visit_unapproved, request_sent}`.
- **Action labels:** `pii_block`/`ethics_block` → `Blocked`, `warn_shown` → `Warned`, `visit_unapproved` → `Visited`, `request_sent` → `Requested`.
- **Windowing:** `WHERE substr(u.ts,1,10) >= date('now', ?)` with `?` = `'-' || (days-1) || ' days'`. `days` ∈ {7, 30} (anything not 30 → 7). `limit` default 50, capped at 200.
- **Tenant scope:** every query filters `u.org_id = ?`; department scope adds `AND e.department_id = ?`.
- **Tests:** in-memory DB (`tests/conftest.py`), process-wide singleton — each test seeds its own company. Run from `code/policy/`: `./.venv/Scripts/python -m pytest -q`.
- **Commits: sole author, no `Co-Authored-By` trailer.**

---

### Task 1: `name` columns + migration

**Files:**
- Modify: `code/policy/app/db.py` (add `_migrate_analytics`, wire into `init_schema`)
- Test: `code/policy/tests/test_analytics_schema.py` (create)

**Interfaces:**
- Produces: `employees.name TEXT`, `enroll_tokens.name TEXT` (both nullable).

- [ ] **Step 1: Write the failing test**

```python
# code/policy/tests/test_analytics_schema.py
from app.db import connect, init_schema


def test_name_columns_exist():
    conn = connect(":memory:")
    init_schema(conn)
    def cols(t): return {r["name"] for r in conn.execute(f"PRAGMA table_info({t})")}
    assert "name" in cols("employees")
    assert "name" in cols("enroll_tokens")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd code/policy && ./.venv/Scripts/python -m pytest tests/test_analytics_schema.py -q`
Expected: FAIL (`name` not in columns).

- [ ] **Step 3: Add the migration and wire it in**

In `app/db.py`, add after `_migrate_hierarchy`:

```python
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
```

Update `init_schema`:

```python
def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    _migrate_appeals(conn)
    _migrate_hierarchy(conn)
    _migrate_analytics(conn)
    conn.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd code/policy && ./.venv/Scripts/python -m pytest tests/test_analytics_schema.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add code/policy/app/db.py code/policy/tests/test_analytics_schema.py
git commit -m "feat(policy): admin-supplied employee name columns on tokens and employees"
```

---

### Task 2: Name plumbing through mint, list, and enrol

**Files:**
- Modify: `code/policy/app/routes/dept.py` (`dept_mint_token` accepts `name`; `dept_tokens` returns `name`)
- Modify: `code/policy/app/routes/enroll.py` (copy `name` to `employees.name`)
- Test: `code/policy/tests/test_token_names.py` (create)

**Interfaces:**
- Consumes: `authz.require_department`, `security.new_token`/`now_iso`.
- Produces: `POST /v1/dept/tokens {name?}` stores `enroll_tokens.name`; `GET /v1/dept/tokens` rows include `name`; enrol copies it to `employees.name`.

- [ ] **Step 1: Write the failing test**

```python
# code/policy/tests/test_token_names.py
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_conn
from app.seed import seed_company, create_department

emp = TestClient(app)


def _dept():
    org_id, _ = seed_company(get_conn(), "NameCo " + uuid.uuid4().hex[:6])
    dept_id, secret = create_department(get_conn(), org_id, "Engineering")
    dc = TestClient(app)
    dc.post("/v1/admin/login", json={"role": "department", "secret": secret})
    return org_id, dept_id, dc


def test_minted_name_flows_to_the_enrolled_employee():
    org_id, dept_id, dc = _dept()
    token = dc.post("/v1/dept/tokens", json={"name": "Alice Tan"}).json()["token"]
    rows = dc.get("/v1/dept/tokens").json()
    assert any(r.get("name") == "Alice Tan" for r in rows)
    pid = emp.post("/v1/enroll", json={"token": token}).json()["pseudo_id"]
    name = get_conn().execute(
        "SELECT name FROM employees WHERE pseudo_id = ?", (pid,)).fetchone()["name"]
    assert name == "Alice Tan"


def test_name_is_optional():
    org_id, dept_id, dc = _dept()
    token = dc.post("/v1/dept/tokens", json={}).json()["token"]
    pid = emp.post("/v1/enroll", json={"token": token}).json()["pseudo_id"]
    name = get_conn().execute(
        "SELECT name FROM employees WHERE pseudo_id = ?", (pid,)).fetchone()["name"]
    assert name in (None, "")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd code/policy && ./.venv/Scripts/python -m pytest tests/test_token_names.py -q`
Expected: FAIL (name not stored/returned).

- [ ] **Step 3: Edit `dept_mint_token` and `dept_tokens` in `app/routes/dept.py`**

Add `Body` to the FastAPI import if not present (`from fastapi import APIRouter, Body, Cookie, HTTPException`). Replace `dept_mint_token`:

```python
@router.post("/tokens", status_code=201)
async def dept_mint_token(
    name: str = Body(default="", embed=True),
    vg_admin: str | None = Cookie(default=None),
) -> dict[str, str]:
    org_id, dept_id = require_department(vg_admin)
    conn = get_conn()
    dept_name = conn.execute(
        "SELECT name FROM departments WHERE id = ?", (dept_id,)
    ).fetchone()["name"]
    plain, hashed = new_token(dept_name[:3])
    token_id = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO enroll_tokens (id, org_id, department, department_id, token_hash, label, name, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (token_id, org_id, dept_name, dept_id, hashed, dept_name, name, now_iso()),
    )
    conn.commit()
    return {"id": token_id, "department": dept_name, "name": name, "token": plain}
```

In `dept_tokens`, add `name` to the SELECT:

```python
        "SELECT id, department, name, label, created_at, revoked FROM enroll_tokens"
        " WHERE org_id = ? AND department_id = ? ORDER BY created_at DESC",
```

- [ ] **Step 4: Edit `enroll` in `app/routes/enroll.py`**

Pull `name` from the token and stamp it on the employee:

```python
    row = conn.execute(
        "SELECT org_id, department, department_id, name FROM enroll_tokens"
        " WHERE token_hash = ? AND revoked = 0",
        (hash_token(body.token),),
    ).fetchone()
    ...
    conn.execute(
        "INSERT INTO employees (id, org_id, pseudo_id, department, department_id, name, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (employee_id, row["org_id"], pseudo_id, row["department"], row["department_id"], row["name"], now_iso()),
    )
```

(The rest of `enroll` — `read_policy`, `EnrollResponse` — is unchanged; the response does not carry the name, so the extension never receives it.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd code/policy && ./.venv/Scripts/python -m pytest tests/test_token_names.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add code/policy/app/routes/dept.py code/policy/app/routes/enroll.py code/policy/tests/test_token_names.py
git commit -m "feat(policy): carry admin-supplied employee name through mint and enrol"
```

---

### Task 3: `analytics_summary` aggregation

**Files:**
- Create: `code/policy/app/analytics.py`
- Test: `code/policy/tests/test_analytics_summary.py` (create)

**Interfaces:**
- Produces:
  - `WEIGHTS_SQL`, `SEVERITY_SQL`, `ACTION_SQL` (module constants)
  - `analytics_summary(conn, org_id: str, days: int, department_id: str | None) -> dict`
- Return shape: `{usage_trend, alerts_timeline, top_apps, top_employees, top_departments, alerts_by_severity, totals}` as specified in the spec §3.

- [ ] **Step 1: Write the failing test**

```python
# code/policy/tests/test_analytics_summary.py
import uuid
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_conn
from app.seed import seed_company, create_department, mint_employee_token
from app.analytics import analytics_summary

emp = TestClient(app)


def _emp_id(org_id, dept_id, dept="Engineering"):
    tok = mint_employee_token(get_conn(), org_id, dept_id, dept)
    pid = emp.post("/v1/enroll", json={"token": tok}).json()["pseudo_id"]
    return get_conn().execute("SELECT id FROM employees WHERE pseudo_id=?", (pid,)).fetchone()["id"]


def _event(org_id, emp_id, etype, ts):
    get_conn().execute(
        "INSERT INTO usage_events (id, org_id, employee_id, host, type, category, finding_hash, ts)"
        " VALUES (?, ?, ?, 'chatgpt.com', ?, NULL, NULL, ?)",
        (uuid.uuid4().hex, org_id, emp_id, etype, ts))
    get_conn().commit()


def _iso(days_ago=0):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def test_risk_is_the_weighted_sum_and_names_join():
    org_id, _ = seed_company(get_conn(), "SumCo " + uuid.uuid4().hex[:6])
    dept_id, _ = create_department(get_conn(), org_id, "Engineering")
    e = _emp_id(org_id, dept_id)
    get_conn().execute("UPDATE employees SET name='Alice' WHERE id=?", (e,)); get_conn().commit()
    for t in ["ethics_block", "pii_block", "warn_shown", "visit_unapproved", "request_sent"]:
        _event(org_id, e, t, _iso(0))
    s = analytics_summary(get_conn(), org_id, 7, None)
    top = s["top_employees"][0]
    assert top["name"] == "Alice"
    assert top["events"] == 5
    assert top["risk"] == 5 + 3 + 1 + 1 + 0   # == 10
    assert s["totals"]["events"] == 5
    assert {r["severity"]: r["count"] for r in s["alerts_by_severity"]} == {"high": 2, "medium": 1, "low": 2}
    assert sum(r["risk"] for r in s["risk_timeline"]) == 10   # per-day risk sums to the total


def test_window_excludes_old_events():
    org_id, _ = seed_company(get_conn(), "WinCo " + uuid.uuid4().hex[:6])
    dept_id, _ = create_department(get_conn(), org_id, "Engineering")
    e = _emp_id(org_id, dept_id)
    _event(org_id, e, "pii_block", _iso(0))
    _event(org_id, e, "pii_block", _iso(40))
    assert analytics_summary(get_conn(), org_id, 7, None)["totals"]["events"] == 1
    assert analytics_summary(get_conn(), org_id, 30, None)["totals"]["events"] == 1


def test_department_scope_isolates():
    org_id, _ = seed_company(get_conn(), "IsoCo " + uuid.uuid4().hex[:6])
    da, _ = create_department(get_conn(), org_id, "Alpha")
    db, _ = create_department(get_conn(), org_id, "Beta")
    ea = _emp_id(org_id, da, "Alpha")
    eb = _emp_id(org_id, db, "Beta")
    _event(org_id, ea, "pii_block", _iso(0))
    _event(org_id, eb, "ethics_block", _iso(0))
    a = analytics_summary(get_conn(), org_id, 7, da)
    assert a["totals"]["events"] == 1
    assert all(d["department"] == "Alpha" for d in a["top_departments"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd code/policy && ./.venv/Scripts/python -m pytest tests/test_analytics_summary.py -q`
Expected: FAIL (`ModuleNotFoundError: app.analytics`).

- [ ] **Step 3: Create `app/analytics.py`**

```python
"""Analytics aggregation over usage_events.

Plain SQL, computed on demand -- the data is small and read far more than
written, matching the rest of app/. I3: no prompt text is read or returned;
only class, count, host, type, ts, and the admin-supplied name."""

WEIGHTS_SQL = (
    "CASE u.type WHEN 'ethics_block' THEN 5 WHEN 'pii_block' THEN 3"
    " WHEN 'warn_shown' THEN 1 WHEN 'visit_unapproved' THEN 1 ELSE 0 END"
)
SEVERITY_SQL = (
    "CASE WHEN u.type IN ('ethics_block','pii_block') THEN 'high'"
    " WHEN u.type = 'warn_shown' THEN 'medium' ELSE 'low' END"
)
ACTION_SQL = (
    "CASE u.type WHEN 'pii_block' THEN 'Blocked' WHEN 'ethics_block' THEN 'Blocked'"
    " WHEN 'warn_shown' THEN 'Warned' WHEN 'visit_unapproved' THEN 'Visited'"
    " WHEN 'request_sent' THEN 'Requested' ELSE u.type END"
)
_NAME = "COALESCE(NULLIF(e.name,''),'Unnamed')"


def analytics_summary(conn, org_id: str, days: int, department_id: str | None) -> dict:
    since = f"-{int(days) - 1} days"
    scope = " AND e.department_id = ?" if department_id else ""
    base = (
        "FROM usage_events u JOIN employees e ON e.id = u.employee_id"
        " WHERE u.org_id = ? AND substr(u.ts,1,10) >= date('now', ?)" + scope
    )
    p = (org_id, since) + ((department_id,) if department_id else ())

    def q(sql):
        return [dict(r) for r in conn.execute(sql, p)]

    usage_trend = q(
        f"SELECT substr(u.ts,1,10) AS date, e.department AS department, COUNT(*) AS events "
        f"{base} GROUP BY date, e.department ORDER BY date")
    alerts_timeline = q(
        f"SELECT substr(u.ts,1,10) AS date,"
        f" SUM(CASE WHEN u.type IN ('ethics_block','pii_block') THEN 1 ELSE 0 END) AS high,"
        f" SUM(CASE WHEN u.type = 'warn_shown' THEN 1 ELSE 0 END) AS medium,"
        f" SUM(CASE WHEN u.type IN ('visit_unapproved','request_sent') THEN 1 ELSE 0 END) AS low "
        f"{base} GROUP BY date ORDER BY date")
    risk_timeline = q(
        f"SELECT substr(u.ts,1,10) AS date, SUM({WEIGHTS_SQL}) AS risk "
        f"{base} GROUP BY date ORDER BY date")
    top_apps = q(
        f"SELECT u.host AS host, COUNT(*) AS events {base} GROUP BY u.host ORDER BY events DESC LIMIT 10")
    top_employees = q(
        f"SELECT {_NAME} AS name, e.department AS department, COUNT(*) AS events,"
        f" SUM({WEIGHTS_SQL}) AS risk {base} GROUP BY e.id ORDER BY risk DESC, events DESC LIMIT 10")
    top_departments = q(
        f"SELECT e.department AS department, COUNT(*) AS events, SUM({WEIGHTS_SQL}) AS risk "
        f"{base} GROUP BY e.department ORDER BY risk DESC LIMIT 10")
    alerts_by_severity = q(
        f"SELECT {SEVERITY_SQL} AS severity, COUNT(*) AS count {base} GROUP BY severity")

    row = conn.execute(
        f"SELECT COUNT(*) AS events, COUNT(DISTINCT u.employee_id) AS active_employees {base}", p
    ).fetchone()
    totals = {"events": row["events"], "active_employees": row["active_employees"], "days": int(days)}

    return {
        "usage_trend": usage_trend, "alerts_timeline": alerts_timeline,
        "risk_timeline": risk_timeline, "top_apps": top_apps,
        "top_employees": top_employees, "top_departments": top_departments,
        "alerts_by_severity": alerts_by_severity, "totals": totals,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd code/policy && ./.venv/Scripts/python -m pytest tests/test_analytics_summary.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add code/policy/app/analytics.py code/policy/tests/test_analytics_summary.py
git commit -m "feat(policy): analytics_summary aggregation with weighted risk"
```

---

### Task 4: `analytics_alerts` list

**Files:**
- Modify: `code/policy/app/analytics.py`
- Test: `code/policy/tests/test_analytics_alerts.py` (create)

**Interfaces:**
- Produces: `analytics_alerts(conn, org_id: str, limit: int, department_id: str | None) -> list[dict]`
  with rows `{ts, department, name, host, type, category, action, severity}`, newest first.

- [ ] **Step 1: Write the failing test**

```python
# code/policy/tests/test_analytics_alerts.py
import uuid
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_conn
from app.seed import seed_company, create_department, mint_employee_token
from app.analytics import analytics_alerts

emp = TestClient(app)


def _emp(org_id, dept_id, dept):
    tok = mint_employee_token(get_conn(), org_id, dept_id, dept)
    pid = emp.post("/v1/enroll", json={"token": tok}).json()["pseudo_id"]
    return get_conn().execute("SELECT id FROM employees WHERE pseudo_id=?", (pid,)).fetchone()["id"]


def _event(org_id, emp_id, etype, ts):
    get_conn().execute(
        "INSERT INTO usage_events (id, org_id, employee_id, host, type, category, finding_hash, ts)"
        " VALUES (?, ?, ?, 'chatgpt.com', ?, 'covert_surveillance', NULL, ?)",
        (uuid.uuid4().hex, org_id, emp_id, etype, ts))
    get_conn().commit()


def test_action_and_severity_mapping_newest_first():
    org_id, _ = seed_company(get_conn(), "AlCo " + uuid.uuid4().hex[:6])
    dept_id, _ = create_department(get_conn(), org_id, "Engineering")
    e = _emp(org_id, dept_id, "Engineering")
    _event(org_id, e, "warn_shown", "2026-08-01T10:00:00+00:00")
    _event(org_id, e, "ethics_block", "2026-08-02T10:00:00+00:00")
    rows = analytics_alerts(get_conn(), org_id, 50, None)
    assert rows[0]["type"] == "ethics_block"   # newest first
    assert rows[0]["action"] == "Blocked" and rows[0]["severity"] == "high"
    assert rows[1]["action"] == "Warned" and rows[1]["severity"] == "medium"


def test_limit_and_department_scope():
    org_id, _ = seed_company(get_conn(), "AlCo2 " + uuid.uuid4().hex[:6])
    da, _ = create_department(get_conn(), org_id, "Alpha")
    db, _ = create_department(get_conn(), org_id, "Beta")
    ea = _emp(org_id, da, "Alpha")
    eb = _emp(org_id, db, "Beta")
    _event(org_id, ea, "pii_block", "2026-08-01T10:00:00+00:00")
    _event(org_id, eb, "pii_block", "2026-08-01T10:00:00+00:00")
    only_a = analytics_alerts(get_conn(), org_id, 50, da)
    assert len(only_a) == 1 and only_a[0]["department"] == "Alpha"
    assert len(analytics_alerts(get_conn(), org_id, 1, None)) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd code/policy && ./.venv/Scripts/python -m pytest tests/test_analytics_alerts.py -q`
Expected: FAIL (`analytics_alerts` undefined).

- [ ] **Step 3: Append `analytics_alerts` to `app/analytics.py`**

```python
def analytics_alerts(conn, org_id: str, limit: int, department_id: str | None) -> list[dict]:
    scope = " AND e.department_id = ?" if department_id else ""
    params = (org_id,) + ((department_id,) if department_id else ()) + (int(limit),)
    rows = conn.execute(
        f"SELECT u.ts AS ts, e.department AS department, {_NAME} AS name, u.host AS host,"
        f" u.type AS type, u.category AS category, {ACTION_SQL} AS action, {SEVERITY_SQL} AS severity"
        f" FROM usage_events u JOIN employees e ON e.id = u.employee_id"
        f" WHERE u.org_id = ?{scope} ORDER BY u.ts DESC LIMIT ?",
        params,
    ).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd code/policy && ./.venv/Scripts/python -m pytest tests/test_analytics_alerts.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add code/policy/app/analytics.py code/policy/tests/test_analytics_alerts.py
git commit -m "feat(policy): analytics_alerts list with action/severity mapping"
```

---

### Task 5: Company + department analytics routes

**Files:**
- Modify: `code/policy/app/routes/admin.py` (company routes)
- Modify: `code/policy/app/routes/dept.py` (department routes)
- Test: `code/policy/tests/test_analytics_routes.py` (create)

**Interfaces:**
- Consumes: `analytics.analytics_summary`, `analytics.analytics_alerts`, `authz.require_company`, `authz.require_department`.
- Produces: `GET /v1/admin/analytics/summary?days=`, `GET /v1/admin/analytics/alerts?limit=`, `GET /v1/dept/analytics/summary?days=`, `GET /v1/dept/analytics/alerts?limit=`.

- [ ] **Step 1: Write the failing test**

```python
# code/policy/tests/test_analytics_routes.py
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_conn
from app.seed import seed_company, create_department, mint_employee_token

emp = TestClient(app)


def _world():
    org_id, co_secret = seed_company(get_conn(), "RtCo " + uuid.uuid4().hex[:6])
    da, sa = create_department(get_conn(), org_id, "Alpha")
    db, sb = create_department(get_conn(), org_id, "Beta")
    for dept_id, dept in [(da, "Alpha"), (db, "Beta")]:
        tok = mint_employee_token(get_conn(), org_id, dept_id, dept)
        pid = emp.post("/v1/enroll", json={"token": tok}).json()["pseudo_id"]
        eid = get_conn().execute("SELECT id FROM employees WHERE pseudo_id=?", (pid,)).fetchone()["id"]
        get_conn().execute(
            "INSERT INTO usage_events (id, org_id, employee_id, host, type, category, finding_hash, ts)"
            " VALUES (?, ?, ?, 'chatgpt.com', 'pii_block', NULL, NULL, datetime('now'))",
            (uuid.uuid4().hex, org_id, eid))
    get_conn().commit()
    co = TestClient(app); co.post("/v1/admin/login", json={"role": "company", "secret": co_secret})
    dc = TestClient(app); dc.post("/v1/admin/login", json={"role": "department", "secret": sa})
    return co, dc


def test_company_sees_all_departments_but_dept_sees_only_its_own():
    co, dc = _world()
    company = co.get("/v1/admin/analytics/summary?days=7").json()
    assert company["totals"]["events"] == 2
    dept = dc.get("/v1/dept/analytics/summary?days=7").json()
    assert dept["totals"]["events"] == 1
    assert all(d["department"] == "Alpha" for d in dept["top_departments"])
    assert len(dc.get("/v1/dept/analytics/alerts").json()) == 1
    assert len(co.get("/v1/admin/analytics/alerts").json()) == 2


def test_analytics_routes_reject_the_wrong_role():
    co, dc = _world()
    assert co.get("/v1/dept/analytics/summary").status_code == 403
    assert dc.get("/v1/admin/analytics/summary").status_code == 403
    assert TestClient(app).get("/v1/admin/analytics/summary").status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd code/policy && ./.venv/Scripts/python -m pytest tests/test_analytics_routes.py -q`
Expected: FAIL (404 on the analytics routes).

- [ ] **Step 3: Add company routes to `app/routes/admin.py`**

Add the import near the top: `from app.analytics import analytics_summary, analytics_alerts`. Append:

```python
def _days(days: int) -> int:
    return 30 if int(days) == 30 else 7


@router.get("/analytics/summary")
async def admin_analytics_summary(
    days: int = 7, vg_admin: str | None = Cookie(default=None)
) -> dict:
    org_id = require_company(vg_admin)
    return analytics_summary(get_conn(), org_id, _days(days), None)


@router.get("/analytics/alerts")
async def admin_analytics_alerts(
    limit: int = 50, vg_admin: str | None = Cookie(default=None)
) -> list[dict]:
    org_id = require_company(vg_admin)
    return analytics_alerts(get_conn(), org_id, min(max(int(limit), 1), 200), None)
```

- [ ] **Step 4: Add department routes to `app/routes/dept.py`**

Add the import: `from app.analytics import analytics_summary, analytics_alerts`. Append:

```python
def _days(days: int) -> int:
    return 30 if int(days) == 30 else 7


@router.get("/analytics/summary")
async def dept_analytics_summary(
    days: int = 7, vg_admin: str | None = Cookie(default=None)
) -> dict:
    org_id, dept_id = require_department(vg_admin)
    return analytics_summary(get_conn(), org_id, _days(days), dept_id)


@router.get("/analytics/alerts")
async def dept_analytics_alerts(
    limit: int = 50, vg_admin: str | None = Cookie(default=None)
) -> list[dict]:
    org_id, dept_id = require_department(vg_admin)
    return analytics_alerts(get_conn(), org_id, min(max(int(limit), 1), 200), dept_id)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd code/policy && ./.venv/Scripts/python -m pytest tests/test_analytics_routes.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add code/policy/app/routes/admin.py code/policy/app/routes/dept.py code/policy/tests/test_analytics_routes.py
git commit -m "feat(policy): company and department analytics endpoints"
```

---

### Task 6: Seed demo analytics data + full suite green

**Files:**
- Modify: `code/policy/scripts/seed.py` (`build_demo_world` labels tokens with names and generates varied events)
- Test: `code/policy/tests/test_seed_analytics.py` (create); then whole suite.

**Interfaces:**
- Consumes: `analytics_summary`.
- Produces: seeded names + multi-day events so every widget renders.

- [ ] **Step 1: Write the failing test**

```python
# code/policy/tests/test_seed_analytics.py
from pathlib import Path
import importlib


def test_seed_populates_named_analytics(tmp_path):
    import scripts.seed as seedmod
    importlib.reload(seedmod)
    summary = seedmod.build_demo_world(out_path=tmp_path / "DEMO-TOKENS.md")
    from app.deps import get_conn
    from app.analytics import analytics_summary
    s = analytics_summary(get_conn(), summary["org_id"], 30, None)
    assert s["totals"]["events"] > 0
    assert any(e["name"] != "Unnamed" for e in s["top_employees"])
    assert len(s["usage_trend"]) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd code/policy && ./.venv/Scripts/python -m pytest tests/test_seed_analytics.py -q`
Expected: FAIL (no events seeded / all Unnamed).

- [ ] **Step 3: Extend `build_demo_world` in `scripts/seed.py`**

After the existing department/token minting loop (which builds `depts` with `tokens`), add named enrolments and events. Add these imports at the top of `scripts/seed.py`:

```python
import uuid
from datetime import datetime, timedelta, timezone
```

And, inside `build_demo_world`, after `depts` is built and before writing the file, insert:

```python
    from app.security import hash_token  # local import: keep module top clean
    NAMES = {
        "Engineering": ["Alice Tan", "Ben Lee"],
        "Sales": ["Carol Ng", "Devi Rao"],
        "Compliance": ["Ethan Ho", "Farah Idris"],
    }
    EVENTS = ["pii_block", "ethics_block", "warn_shown", "visit_unapproved", "request_sent"]
    HOSTS = ["chatgpt.com", "claude.ai", "gemini.google.com"]
    for d in depts:
        names = NAMES.get(d["name"], ["Sam Roe", "Kim Yeo"])
        for i, tok in enumerate(d["tokens"]):
            # label the token, then enrol a pseudonymous employee that inherits the name
            person = names[i % len(names)]
            conn.execute("UPDATE enroll_tokens SET name = ? WHERE token_hash = ?",
                         (person, hash_token(tok)))
            emp_id, pseudo = uuid.uuid4().hex, uuid.uuid4().hex
            conn.execute(
                "INSERT INTO employees (id, org_id, pseudo_id, department, department_id, name, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (emp_id, org_id, pseudo, d["name"], d["id"], person,
                 datetime.now(timezone.utc).isoformat()))
            # spread events across the last ~20 days and the event types
            for k in range(6):
                ts = (datetime.now(timezone.utc) - timedelta(days=(k * 3) % 20, hours=k)).isoformat()
                etype = EVENTS[(i + k) % len(EVENTS)]
                conn.execute(
                    "INSERT INTO usage_events (id, org_id, employee_id, host, type, category, finding_hash, ts)"
                    " VALUES (?, ?, ?, ?, ?, ?, NULL, ?)",
                    (uuid.uuid4().hex, org_id, emp_id, HOSTS[k % len(HOSTS)], etype,
                     "covert_surveillance" if etype == "ethics_block" else None, ts))
    conn.commit()
```

(`conn` and `org_id` are already in scope in `build_demo_world`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd code/policy && ./.venv/Scripts/python -m pytest tests/test_seed_analytics.py -q`
Expected: PASS.

- [ ] **Step 5: Run the whole suite**

Run: `cd code/policy && ./.venv/Scripts/python -m pytest -q`
Expected: **0 failed.** Fix any red surfaced here (most likely a `test_seed_script.py` assertion that counts departments/tokens — the analytics additions don't change the file's token/department structure, so it should still pass).

- [ ] **Step 6: Commit**

```bash
git add code/policy/scripts/seed.py code/policy/tests/test_seed_analytics.py
git commit -m "feat(policy): seed named employees and multi-day analytics events"
```

---

## Self-Review

**Spec coverage:** §2 name columns → Task 1; risk weights/severity/action → Tasks 3/4 constants. §3 helpers + endpoints (company + dept, days/limit clamps, windowing, risk SQL, name coalesce, tenant+dept scope) → Tasks 3, 4, 5. Name plumbing (mint/list/enrol) → Task 2. §6 seed → Task 6. §7 backend tests (risk weighting, windowing, name join/Unnamed, severity, action, dept isolation, name plumbing) → Tasks 2–6. §8 on-demand SQL, no prompt storage → honored (analytics reads only class/count/host/type/ts/name).

**Placeholder scan:** every code step is complete; every run step has a command + expected result. No TBD/TODO.

**Type consistency:** `analytics_summary(conn, org_id, days, department_id)` and `analytics_alerts(conn, org_id, limit, department_id)` are defined in Tasks 3/4 and called with those exact argument orders in Task 5's routes and Task 6's test. `WEIGHTS_SQL`/`SEVERITY_SQL`/`ACTION_SQL`/`_NAME` are module constants used consistently. Return keys (`usage_trend`, `alerts_timeline`, `risk_timeline`, `top_apps`, `top_employees`, `top_departments`, `alerts_by_severity`, `totals`) match the console plan's consumers. `_days` clamp (7/30) and `limit` cap (200) match the Global Constraints.
