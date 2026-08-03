import uuid

from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_conn
from app.seed import seed_company, create_department, mint_employee_token

client = TestClient(app)


def _enrol():
    """A fresh enrolled employee; returns (pseudo_id, department-admin TestClient)."""
    org_id, _co_secret = seed_company(get_conn(), "Acme " + uuid.uuid4().hex[:6])
    dept_id, dept_secret = create_department(get_conn(), org_id, "Engineering")
    token = mint_employee_token(get_conn(), org_id, dept_id, "Engineering")
    pseudo_id = client.post("/v1/enroll", json={"token": token}).json()["pseudo_id"]
    dept = TestClient(app)
    dept.post("/v1/admin/login", json={"role": "department", "secret": dept_secret})
    return pseudo_id, dept


def test_submit_appeal_without_opt_in_stores_no_prompt_text():
    pid, _dept = _enrol()
    r = client.post("/v1/appeals", json={
        "pseudo_id": pid, "decision_type": "ethics",
        "category": "covert_surveillance", "reason": "I was asking about defending our own systems",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending"
    # 🔴 The load-bearing privacy assertion: default appeal has no disclosed text.
    mine = client.get("/v1/appeals", params={"pseudo_id": pid}).json()
    assert len(mine) == 1
    assert "disclosed_text" not in mine[0]  # the list view never returns it
    # and it is NULL in storage
    row = get_conn().execute(
        "SELECT disclosed_text FROM decision_appeals WHERE id = ?", (body["id"],)
    ).fetchone()
    assert row["disclosed_text"] is None


def test_submit_appeal_with_opt_in_stores_disclosed_text():
    pid, _dept = _enrol()
    r = client.post("/v1/appeals", json={
        "pseudo_id": pid, "decision_type": "pii", "category": "NRIC",
        "reason": "that is a product code, not an IC", "disclosed_text": "SKU 880101-14-5566",
    })
    assert r.status_code == 201
    row = get_conn().execute(
        "SELECT disclosed_text FROM decision_appeals WHERE id = ?", (r.json()["id"],)
    ).fetchone()
    assert row["disclosed_text"] == "SKU 880101-14-5566"


def test_unknown_pseudo_id_is_401():
    r = client.post("/v1/appeals", json={
        "pseudo_id": "nope", "decision_type": "ethics", "category": "x", "reason": "y",
    })
    assert r.status_code == 401


def test_smuggled_prompt_field_is_422_and_not_echoed():
    pid, _dept = _enrol()
    r = client.post("/v1/appeals", json={
        "pseudo_id": pid, "decision_type": "ethics", "category": "x",
        "reason": "y", "prompt": "the secret prompt text",
    })
    assert r.status_code == 422
    assert "the secret prompt text" not in r.text


def test_list_returns_only_the_callers_appeals():
    a, _dept_a = _enrol()
    b, _dept_b = _enrol()
    client.post("/v1/appeals", json={"pseudo_id": a, "decision_type": "ethics", "category": "x", "reason": "ra"})
    client.post("/v1/appeals", json={"pseudo_id": b, "decision_type": "ethics", "category": "x", "reason": "rb"})
    assert len(client.get("/v1/appeals", params={"pseudo_id": a}).json()) == 1


def test_dept_appeals_queue_requires_a_session():
    assert TestClient(app).get("/v1/dept/appeals").status_code == 401


def test_dept_admin_sees_the_appeal_with_department_and_decides_it():
    pid, dept = _enrol()
    appeal_id = client.post("/v1/appeals", json={
        "pseudo_id": pid, "decision_type": "ethics", "category": "covert_surveillance",
        "reason": "defence not attack",
    }).json()["id"]
    queue = dept.get("/v1/dept/appeals").json()
    mine = [a for a in queue if a["id"] == appeal_id]
    assert len(mine) == 1
    assert mine[0]["department"] == "Engineering"
    assert mine[0]["category"] == "covert_surveillance"

    r = dept.post(f"/v1/dept/appeals/{appeal_id}", json={"decision": "overturned", "note": "fair point"})
    assert r.status_code == 200
    assert r.json()["status"] == "overturned"
    # the employee now sees the outcome
    mine = client.get("/v1/appeals", params={"pseudo_id": pid}).json()
    assert mine[0]["status"] == "overturned"
    assert mine[0]["admin_note"] == "fair point"


def test_deciding_twice_is_409():
    pid, dept = _enrol()
    appeal_id = client.post("/v1/appeals", json={
        "pseudo_id": pid, "decision_type": "pii", "category": "NRIC", "reason": "x",
    }).json()["id"]
    assert dept.post(f"/v1/dept/appeals/{appeal_id}", json={"decision": "upheld"}).status_code == 200
    assert dept.post(f"/v1/dept/appeals/{appeal_id}", json={"decision": "overturned"}).status_code == 409


def test_overturned_ethics_appeal_grants_a_one_time_pass_that_burns():
    pid, dept = _enrol()
    # employee appeals an ethics block, carrying a hash of the prompt
    aid = client.post("/v1/appeals", json={
        "pseudo_id": pid, "decision_type": "ethics", "category": "security_evasion",
        "reason": "defending our own systems", "prompt_hash": "abc123",
    }).json()["id"]
    # no pass yet -- still pending
    assert client.get("/v1/appeals/allowances", params={"pseudo_id": pid}).json() == []
    # department admin overturns
    dept.post(f"/v1/dept/appeals/{aid}", json={"decision": "overturned"})
    # now the hash is an active allowance
    assert client.get("/v1/appeals/allowances", params={"pseudo_id": pid}).json() == ["abc123"]
    # consuming it burns it
    assert client.post("/v1/appeals/allowances/consume", json={"pseudo_id": pid, "prompt_hash": "abc123"}).json()["consumed"] == 1
    assert client.get("/v1/appeals/allowances", params={"pseudo_id": pid}).json() == []
    # a second consume is a no-op (one-time)
    assert client.post("/v1/appeals/allowances/consume", json={"pseudo_id": pid, "prompt_hash": "abc123"}).json()["consumed"] == 0


def test_upheld_appeal_grants_no_pass():
    pid, dept = _enrol()
    aid = client.post("/v1/appeals", json={
        "pseudo_id": pid, "decision_type": "ethics", "category": "x",
        "reason": "y", "prompt_hash": "deadbeef",
    }).json()["id"]
    dept.post(f"/v1/dept/appeals/{aid}", json={"decision": "upheld"})
    assert client.get("/v1/appeals/allowances", params={"pseudo_id": pid}).json() == []
