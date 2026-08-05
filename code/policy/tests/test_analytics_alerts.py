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
        " VALUES (%s, %s, %s, 'chatgpt.com', %s, 'covert_surveillance', NULL, %s)",
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


def test_prompt_send_uses_its_recorded_risk_level():
    org_id, _ = seed_company(get_conn(), "PromptAlerts " + uuid.uuid4().hex[:6])
    dept_id, _ = create_department(get_conn(), org_id, "Engineering")
    e = _emp(org_id, dept_id, "Engineering")
    get_conn().execute(
        "INSERT INTO usage_events"
        " (id, org_id, employee_id, host, type, category, finding_hash, risk_level, ts)"
        " VALUES (%s, %s, %s, 'chatgpt.com', 'prompt_sent', 'NRIC', NULL, 'medium', %s)",
        (uuid.uuid4().hex, org_id, e, "2026-08-05T10:00:00+00:00"),
    )
    get_conn().commit()

    row = analytics_alerts(get_conn(), org_id, 50, None)[0]
    assert row["type"] == "prompt_sent"
    assert row["action"] == "Sent"
    assert row["severity"] == "medium"
