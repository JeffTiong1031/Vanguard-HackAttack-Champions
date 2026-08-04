import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_conn
from app.seed import seed_company, create_department, mint_employee_token

client = TestClient(app)
SCOPE_A = "a" * 64
SCOPE_B = "b" * 64


def _enrol():
    org_id, _co_secret = seed_company(get_conn(), "Prescreen Co " + uuid.uuid4().hex[:6])
    dept_id, dept_secret = create_department(get_conn(), org_id, "Engineering")
    token = mint_employee_token(get_conn(), org_id, dept_id, "Engineering")
    pseudo_id = client.post("/v1/enroll", json={"token": token}).json()["pseudo_id"]
    dept = TestClient(app)
    dept.post("/v1/admin/login", json={"role": "department", "secret": dept_secret})
    return pseudo_id, dept, org_id, dept_id


def test_appeal_prescreening_and_remediation():
    pid, dept, org_id, dept_id = _enrol()

    # 1. Initial submit -> ready_for_review
    r1 = client.post("/v1/appeals", json={
        "pseudo_id": pid, "decision_type": "ethics",
        "category": "covert_surveillance", "reason": "Authorized test scope",
        "scope_fingerprint": SCOPE_A,
    })
    assert r1.status_code == 201
    b1 = r1.json()
    assert b1["status"] == "pending"
    assert b1["pre_screen"] == "ready_for_review"

    # 2. Duplicate submit -> duplicate
    r2 = client.post("/v1/appeals", json={
        "pseudo_id": pid, "decision_type": "ethics",
        "category": "covert_surveillance", "reason": "Duplicate attempt",
        "scope_fingerprint": SCOPE_A,
    })
    assert r2.status_code == 201
    b2 = r2.json()
    assert b2["status"] == "pending"
    assert b2["pre_screen"] == "duplicate"
    assert b2["id"] == b1["id"]

    # 3. Check remediation guidance while pending (blocked access_state)
    list1 = client.get("/v1/appeals", params={"pseudo_id": pid}).json()
    assert len(list1) == 1
    assert list1[0]["access_state"] == "blocked"
    assert "remediation_guidance" in list1[0]
    assert list1[0]["remediation_guidance"]["title"].startswith("Access Blocked")

    # 4. Admin approves appeal
    dept_resp = dept.post(f"/v1/dept/appeals/{b1['id']}", json={
        "decision": "approved",
    })
    assert dept_resp.status_code == 200

    # 5. Subsequent submit with approved scope fingerprint -> auto-approved pre_screen
    r3 = client.post("/v1/appeals", json={
        "pseudo_id": pid, "decision_type": "ethics",
        "category": "covert_surveillance", "reason": "Re-check approved scope",
        "scope_fingerprint": SCOPE_A,
    })
    assert r3.status_code == 201
    b3 = r3.json()
    assert b3["status"] == "approved"
    assert b3["access_state"] == "approved"
    assert b3["pre_screen"] == "already_approved"


def test_requests_remediation_guidance():
    pid, dept, org_id, dept_id = _enrol()

    # Submit request for blocked tool ('google')
    r = client.post("/v1/requests", json={
        "pseudo_id": pid, "llm_id": "google", "reason": "Need tool for development"
    })
    assert r.status_code == 201
    req_id = r.json()["id"]

    # Admin keeps blocked with reason_code
    dept.post(f"/v1/dept/requests/{req_id}", json={
        "decision": "blocked",
        "reason_code": "prohibited_use",
        "note": "Prohibited data usage detected",
    })

    # Employee views requests -> receives remediation_guidance
    my_requests = client.get("/v1/requests", params={"pseudo_id": pid}).json()
    assert len(my_requests) == 1
    assert my_requests[0]["access_state"] == "blocked"
    assert "remediation_guidance" in my_requests[0]
    assert "Prohibited Use" in my_requests[0]["remediation_guidance"]["title"]
    assert "prohibited under company security policy" in my_requests[0]["remediation_guidance"]["summary"]

