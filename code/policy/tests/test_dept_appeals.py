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
        "category": "security_evasion", "reason": "false positive",
        "scope_fingerprint": "a" * 64}).json()["id"]
    assert any(a["id"] == appeal_id for a in dc.get("/v1/dept/appeals").json())
    r = dc.post(f"/v1/dept/appeals/{appeal_id}", json={"decision": "approved", "note": "ok"})
    assert r.status_code == 200 and r.json()["status"] == "approved"
    # second decision on a decided appeal is 409
    assert dc.post(f"/v1/dept/appeals/{appeal_id}", json={
        "decision": "blocked", "reason_code": "policy_requirement_not_met", "note": "Still prohibited."
    }).status_code == 409
