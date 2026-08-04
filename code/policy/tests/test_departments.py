import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_conn
from app.seed import seed_company
from app.security import hash_token

client_module = TestClient(app)


def _company():
    org_id, secret = seed_company(get_conn(), "Dept Co " + uuid.uuid4().hex[:6])
    c = TestClient(app)
    c.post("/v1/admin/login", json={"role": "company", "secret": secret})
    return c, org_id


def test_create_lists_and_regenerate_department():
    c, org_id = _company()
    created = c.post("/v1/admin/departments", json={"name": "Engineering"})
    assert created.status_code == 201
    dept_id, old_secret = created.json()["id"], created.json()["secret"]

    listed = c.get("/v1/admin/departments").json()
    assert any(d["id"] == dept_id and d["name"] == "Engineering" for d in listed)

    # duplicate name is rejected
    assert c.post("/v1/admin/departments", json={"name": "Engineering"}).status_code == 409

    # the new department secret logs in as that department
    assert TestClient(app).post("/v1/admin/login", json={"role": "department", "secret": old_secret}).status_code == 200

    regen = c.post(f"/v1/admin/departments/{dept_id}/regenerate")
    assert regen.status_code == 200
    new_secret = regen.json()["secret"]
    # old secret no longer works; new one does
    assert TestClient(app).post("/v1/admin/login", json={"role": "department", "secret": old_secret}).status_code == 401
    assert TestClient(app).post("/v1/admin/login", json={"role": "department", "secret": new_secret}).status_code == 200


def test_departments_route_refuses_a_department_session():
    c, org_id = _company()
    dept_id = c.post("/v1/admin/departments", json={"name": "Sales"}).json()["id"]
    dept_secret = c.post(f"/v1/admin/departments/{dept_id}/regenerate").json()["secret"]
    dc = TestClient(app)
    dc.post("/v1/admin/login", json={"role": "department", "secret": dept_secret})
    assert dc.get("/v1/admin/departments").status_code == 403
