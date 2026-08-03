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
