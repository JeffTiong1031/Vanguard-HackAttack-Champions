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
