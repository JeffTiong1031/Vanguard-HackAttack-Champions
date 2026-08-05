import uuid
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_conn
from app.enrolment import token_is_expired
from app.seed import seed_company, create_department, mint_employee_token

client = TestClient(app)

NOW = datetime(2026, 8, 5, tzinfo=timezone.utc)

def _world():
    conn = get_conn()
    org_id, _ = seed_company(conn, f"T-{uuid.uuid4().hex[:8]}")
    dept_id, _ = create_department(conn, org_id, "Engineering")
    return conn, org_id, dept_id

def test_same_token_twice_returns_one_identity():
    """A reinstall must not split the person in two."""
    conn, org_id, dept_id = _world()
    token = mint_employee_token(conn, org_id, dept_id, "Engineering")

    first = client.post("/v1/enroll", json={"token": token}).json()
    second = client.post("/v1/enroll", json={"token": token}).json()

    assert first["pseudo_id"] == second["pseudo_id"]
    rows = conn.execute(
        "SELECT id FROM employees WHERE org_id = %s", (org_id,)
    ).fetchall()
    assert len(rows) == 1, "second enrolment created a duplicate employee"

def test_enrolment_records_the_token_used():
    conn, org_id, dept_id = _world()
    token = mint_employee_token(conn, org_id, dept_id, "Engineering")
    client.post("/v1/enroll", json={"token": token})

    row = conn.execute(
        "SELECT enroll_token_id FROM employees WHERE org_id = %s", (org_id,)
    ).fetchone()
    assert row["enroll_token_id"] is not None

def test_unused_token_expires_after_seven_days():
    old = (NOW - timedelta(days=8)).isoformat()
    assert token_is_expired(old, NOW, used=False) is True

def test_unused_token_inside_the_window_is_fine():
    recent = (NOW - timedelta(days=6)).isoformat()
    assert token_is_expired(recent, NOW, used=False) is False

def test_a_used_token_never_expires():
    """Alice reinstalling in month three must still work."""
    ancient = (NOW - timedelta(days=400)).isoformat()
    assert token_is_expired(ancient, NOW, used=True) is False

def test_expired_unused_token_is_rejected_by_the_route():
    """The route wires token_is_expired in: an unused token past the TTL 401s,
    the same as an unrecognised one -- and never creates an employee."""
    conn, org_id, dept_id = _world()
    token = mint_employee_token(conn, org_id, dept_id, "Engineering")
    stale = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    conn.execute(
        "UPDATE enroll_tokens SET created_at = %s WHERE org_id = %s",
        (stale, org_id),
    )
    conn.commit()

    resp = client.post("/v1/enroll", json={"token": token})

    assert resp.status_code == 401
    rows = conn.execute(
        "SELECT id FROM employees WHERE org_id = %s", (org_id,)
    ).fetchall()
    assert len(rows) == 0

def test_used_token_still_enrols_after_the_ttl_would_have_expired_it():
    """Once a token has created an employee, it is that person's permanent
    identity -- a reinstall past the 7-day window must still succeed."""
    conn, org_id, dept_id = _world()
    token = mint_employee_token(conn, org_id, dept_id, "Engineering")
    first = client.post("/v1/enroll", json={"token": token}).json()

    stale = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
    conn.execute(
        "UPDATE enroll_tokens SET created_at = %s WHERE org_id = %s",
        (stale, org_id),
    )
    conn.commit()

    second = client.post("/v1/enroll", json={"token": token})

    assert second.status_code == 200
    assert second.json()["pseudo_id"] == first["pseudo_id"]
