import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.deps import get_conn
from app.seed import seed_company
from app.security import new_token, now_iso

client = TestClient(app)


def _pseudo_id(department: str = "Engineering") -> str:
    org_id, _ = seed_company(get_conn(), "Acme Corp")
    plain, hashed = new_token("ENG")
    get_conn().execute(
        "INSERT INTO enroll_tokens (id, org_id, department, token_hash, label, created_at)"
        " VALUES (%s, %s, %s, %s, %s, %s)",
        (uuid.uuid4().hex, org_id, department, hashed, department, now_iso()),
    )
    get_conn().commit()
    return client.post("/v1/enroll", json={"token": plain}).json()["pseudo_id"]


def test_a_request_is_created_pending():
    pid = _pseudo_id()
    r = client.post("/v1/requests", json={
        "pseudo_id": pid, "llm_id": "google", "reason": "Need it for translation QA",
    })
    assert r.status_code == 201
    assert r.json()["status"] == "pending"
    assert r.json()["access_state"] == "blocked"
    assert r.json()["request_state"] == "submitted"
    assert r.json()["pre_screen"] == "ready_for_review"


def test_pre_screen_returns_an_existing_effective_approval_without_queueing():
    pid = _pseudo_id()
    r = client.post("/v1/requests", json={
        "pseudo_id": pid, "llm_id": "openai", "reason": "Already approved",
    })
    assert r.status_code == 201
    assert r.json()["access_state"] == "approved"
    assert r.json()["request_state"] == "decided"
    assert r.json()["pre_screen"] == "already_approved"


def test_requesting_an_unknown_tool_is_404():
    pid = _pseudo_id()
    r = client.post("/v1/requests", json={
        "pseudo_id": pid, "llm_id": "not-a-tool", "reason": "x",
    })
    assert r.status_code == 404
    # A routing 404 (wrong path) would say "Not Found" -- this must be the
    # handler's own unknown-tool rejection, not a mistyped route.
    assert r.json()["detail"] == "unknown tool"


def test_requesting_with_an_unknown_pseudo_id_is_401():
    r = client.post("/v1/requests", json={
        "pseudo_id": "not-a-real-pseudo-id", "llm_id": "google", "reason": "x",
    })
    assert r.status_code == 401


def test_a_duplicate_pending_request_does_not_create_a_second_row():
    pid = _pseudo_id()
    payload = {"pseudo_id": pid, "llm_id": "google", "reason": "again"}
    first = client.post("/v1/requests", json=payload).json()["id"]
    second = client.post("/v1/requests", json=payload).json()["id"]
    assert first == second

    rows = get_conn().execute(
        "SELECT id FROM access_requests WHERE id = %s", (first,)
    ).fetchall()
    all_rows = get_conn().execute(
        "SELECT access_requests.id FROM access_requests"
        " JOIN employees ON employees.id = access_requests.employee_id"
        " WHERE employees.pseudo_id = %s AND access_requests.llm_id = %s",
        (pid, "google"),
    ).fetchall()
    assert len(all_rows) == 1
    assert len(rows) == 1

    duplicate = client.post("/v1/requests", json=payload).json()
    assert duplicate["pre_screen"] == "duplicate"
    assert duplicate["access_state"] == "blocked"


def test_employee_status_never_calls_pending_access_pending():
    pid = _pseudo_id()
    client.post("/v1/requests", json={
        "pseudo_id": pid, "llm_id": "google", "reason": "Translation QA",
    })
    rows = client.get("/v1/requests", params={"pseudo_id": pid}).json()
    assert rows[0]["request_state"] == "in_review"
    assert rows[0]["access_state"] == "blocked"


def test_an_overlong_reason_is_rejected():
    pid = _pseudo_id()
    r = client.post("/v1/requests", json={
        "pseudo_id": pid, "llm_id": "google", "reason": "x" * 501,
    })
    assert r.status_code == 422


def test_the_422_body_does_not_echo_the_reason_text():
    pid = _pseudo_id()
    secret = "SECRET-" + ("y" * 501)
    r = client.post("/v1/requests", json={
        "pseudo_id": pid, "llm_id": "google", "reason": secret,
    })
    assert r.status_code == 422
    assert "SECRET" not in r.text


def test_two_employees_requesting_same_tool_get_separate_rows():
    """Dedup must consider both employee_id AND llm_id independently."""
    pid1 = _pseudo_id(department="Engineering")
    pid2 = _pseudo_id(department="Engineering")

    # Both request the same tool
    payload = {"llm_id": "perplexity", "reason": "Need it for translation QA"}
    first = client.post("/v1/requests", json={**payload, "pseudo_id": pid1}).json()["id"]
    second = client.post("/v1/requests", json={**payload, "pseudo_id": pid2}).json()["id"]

    # They must get different IDs
    assert first != second

    # Both rows must exist in the database (filtering by both employees and tool)
    all_rows = get_conn().execute(
        "SELECT access_requests.id FROM access_requests"
        " JOIN employees ON employees.id = access_requests.employee_id"
        " WHERE (employees.pseudo_id = %s OR employees.pseudo_id = %s)"
        " AND access_requests.llm_id = %s AND access_requests.status = 'pending'",
        (pid1, pid2, "perplexity"),
    ).fetchall()
    assert len(all_rows) == 2


def test_one_employee_requesting_two_tools_gets_separate_rows():
    """Dedup must consider both employee_id AND llm_id independently."""
    pid = _pseudo_id()

    # Same employee requests two different tools
    payload1 = {"pseudo_id": pid, "llm_id": "google", "reason": "Translation QA"}
    payload2 = {"pseudo_id": pid, "llm_id": "perplexity", "reason": "Research"}

    first = client.post("/v1/requests", json=payload1).json()["id"]
    second = client.post("/v1/requests", json=payload2).json()["id"]

    # They must get different IDs
    assert first != second

    # Both rows must exist for this employee
    all_rows = get_conn().execute(
        "SELECT access_requests.id FROM access_requests"
        " JOIN employees ON employees.id = access_requests.employee_id"
        " WHERE employees.pseudo_id = %s AND access_requests.status = 'pending'",
        (pid,),
    ).fetchall()
    assert len(all_rows) == 2


def test_blocked_request_can_be_re_requested():
    """After a request is blocked, materially new evidence can create a fresh request."""
    pid = _pseudo_id()
    payload = {"pseudo_id": pid, "llm_id": "microsoft", "reason": "Code review"}

    # Create initial request
    first_id = client.post("/v1/requests", json=payload).json()["id"]

    # Manually update its status to blocked in the database
    get_conn().execute(
        "UPDATE access_requests SET status = 'blocked' WHERE id = %s",
        (first_id,),
    )
    get_conn().commit()

    # Employee re-requests the same tool
    second_id = client.post("/v1/requests", json=payload).json()["id"]

    # Should get a NEW id (not the blocked one)
    assert first_id != second_id

    # Both rows must exist: the blocked one and the new pending one
    all_rows = get_conn().execute(
        "SELECT id, status FROM access_requests"
        " WHERE employee_id = ("
        "   SELECT id FROM employees WHERE pseudo_id = %s"
        " ) AND llm_id = %s",
        (pid, "microsoft"),
    ).fetchall()
    assert len(all_rows) == 2
    statuses = {row["status"] for row in all_rows}
    assert statuses == {"blocked", "pending"}
