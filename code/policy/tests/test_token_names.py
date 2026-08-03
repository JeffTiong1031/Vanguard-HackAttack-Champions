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
