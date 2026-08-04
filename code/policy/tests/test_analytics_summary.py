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
        " VALUES (%s, %s, %s, 'chatgpt.com', %s, NULL, NULL, %s)",
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
