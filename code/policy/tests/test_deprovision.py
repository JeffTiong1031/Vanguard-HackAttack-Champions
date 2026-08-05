import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_conn
from app.seed import seed_company, create_department, mint_employee_token

client = TestClient(app)

def _enrolled():
    conn = get_conn()
    org_id, _ = seed_company(conn, f"T-{uuid.uuid4().hex[:8]}")
    dept_id, _ = create_department(conn, org_id, "Engineering")
    token = mint_employee_token(conn, org_id, dept_id, "Engineering")
    pseudo = client.post("/v1/enroll", json={"token": token}).json()["pseudo_id"]
    return conn, org_id, pseudo

def _revoke_all(conn, org_id):
    conn.execute(
        "UPDATE enroll_tokens SET revoked = 1 WHERE org_id = %s", (org_id,))
    conn.commit()

EVENT = {"host": "chatgpt.com", "type": "prompt_sent", "risk_level": "low", "ts": "2026-08-05T00:00:00Z"}

def test_events_accepted_before_revocation():
    conn, org_id, pseudo = _enrolled()
    r = client.post("/v1/events", json={"pseudo_id": pseudo, "events": [EVENT]})
    assert r.status_code == 202

def test_events_rejected_after_revocation():
    conn, org_id, pseudo = _enrolled()
    _revoke_all(conn, org_id)
    r = client.post("/v1/events", json={"pseudo_id": pseudo, "events": [EVENT]})
    assert r.status_code == 403
    assert r.json()["detail"] == "enrolment revoked"

def test_policy_rejected_after_revocation():
    conn, org_id, pseudo = _enrolled()
    _revoke_all(conn, org_id)
    r = client.get(f"/v1/policy?org_id={org_id}&pseudo_id={pseudo}")
    assert r.status_code == 403
    assert r.json()["detail"] == "enrolment revoked"

def test_policy_without_pseudo_id_still_works():
    """Backwards compatible: an older build sends no pseudo_id."""
    conn, org_id, pseudo = _enrolled()
    _revoke_all(conn, org_id)
    assert client.get(f"/v1/policy?org_id={org_id}").status_code == 200
