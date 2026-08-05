import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_conn
from app.seed import seed_company, create_department, mint_employee_token

client = TestClient(app)

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
