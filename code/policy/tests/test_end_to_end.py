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
