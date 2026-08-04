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
            " VALUES (%s, %s, %s, 'chatgpt.com', 'pii_block', NULL, NULL, datetime('now'))",
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
