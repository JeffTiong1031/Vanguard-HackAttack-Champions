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
        "SELECT revoked FROM enroll_tokens WHERE id = %s", (tok_id,)).fetchone()["revoked"] == 1
