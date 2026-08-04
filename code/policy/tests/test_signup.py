from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_signup_returns_a_secret_that_logs_in_as_company():
    r = client.post("/v1/signup", json={"company_name": "Newco"})
    assert r.status_code == 201
    secret = r.json()["secret"]
    login = client.post("/v1/admin/login", json={"role": "company", "secret": secret})
    assert login.status_code == 200
    assert login.json()["org_name"] == "Newco"


def test_signup_forbids_a_smuggled_field():
    r = client.post("/v1/signup", json={"company_name": "X", "password": "y"})
    assert r.status_code == 422
