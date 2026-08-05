from fastapi.testclient import TestClient

from app.deps import get_conn
from app.main import app
from app.seed import seed_company
from app.security import now_iso

client = TestClient(app)
SECRET = "Ahmad bin Ali 880101-14-5566"


def _enrolled_pseudo_id() -> str:
    import uuid
    from app.security import new_token
    org_id, _ = seed_company(get_conn(), "Acme Corp")
    plain, hashed = new_token("ENG")
    get_conn().execute(
        "INSERT INTO enroll_tokens (id, org_id, department, token_hash, label, created_at)"
        " VALUES (%s, %s, 'Engineering', %s, 'Engineering', %s)",
        (uuid.uuid4().hex, org_id, hashed, now_iso()),
    )
    get_conn().commit()
    return client.post("/v1/enroll", json={"token": plain}).json()["pseudo_id"]


def _event(**over):
    base = {"host": "gemini.google.com", "type": "visit_unapproved", "ts": now_iso()}
    base.update(over)
    return base


def test_a_valid_batch_is_accepted_and_stored():
    pid = _enrolled_pseudo_id()
    r = client.post("/v1/events", json={"pseudo_id": pid, "events": [_event()]})
    assert r.status_code == 202
    n = get_conn().execute(
        "SELECT COUNT(*) AS n FROM usage_events WHERE host = 'gemini.google.com'"
    ).fetchone()["n"]
    assert n >= 1


def test_a_sent_prompt_with_each_risk_level_is_accepted_and_stored():
    pid = _enrolled_pseudo_id()
    events = [
        _event(type="prompt_sent", risk_level=level)
        for level in ("low", "medium", "high")
    ]
    r = client.post("/v1/events", json={"pseudo_id": pid, "events": events})
    assert r.status_code == 202
    rows = get_conn().execute(
        "SELECT risk_level FROM usage_events WHERE type = 'prompt_sent'"
        " AND employee_id = (SELECT id FROM employees WHERE pseudo_id = %s)",
        (pid,),
    ).fetchall()
    assert {row["risk_level"] for row in rows} == {"low", "medium", "high"}


def test_a_sent_prompt_requires_a_valid_risk_level():
    pid = _enrolled_pseudo_id()
    missing = client.post("/v1/events", json={
        "pseudo_id": pid, "events": [_event(type="prompt_sent")],
    })
    invalid = client.post("/v1/events", json={
        "pseudo_id": pid,
        "events": [_event(type="prompt_sent", risk_level="critical")],
    })
    assert missing.status_code == 422
    assert invalid.status_code == 422


def test_an_event_carrying_prompt_text_is_REJECTED_not_silently_ignored():
    """I3. A field that is ignored today is a field someone stores tomorrow."""
    pid = _enrolled_pseudo_id()
    r = client.post("/v1/events", json={
        "pseudo_id": pid,
        "events": [_event(prompt=SECRET)],
    })
    assert r.status_code == 422


def test_the_422_body_never_echoes_the_rejected_prompt_value():
    """Critical: pydantic's default error includes `input` verbatim, and
    FastAPI's default handler serialises it straight into the response body.
    An `extra="forbid"` rejection must not become a secondary leak channel --
    a reverse proxy, API gateway, or error-tracking SDK that captures response
    bodies by default would otherwise walk away with the exact prompt text the
    whole endpoint exists to keep out of storage.
    """
    pid = _enrolled_pseudo_id()
    r = client.post("/v1/events", json={
        "pseudo_id": pid,
        "events": [_event(prompt=SECRET)],
    })
    assert r.status_code == 422
    assert SECRET not in r.text


def test_the_422_body_still_names_the_rejected_field():
    """The fix must scrub the VALUE, not blind developers to WHICH field
    failed and why -- `loc` and `msg` are still owed."""
    pid = _enrolled_pseudo_id()
    r = client.post("/v1/events", json={
        "pseudo_id": pid,
        "events": [_event(prompt=SECRET)],
    })
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert any("prompt" in e.get("loc", []) for e in detail)


def test_a_non_hex_finding_hash_is_rejected():
    pid = _enrolled_pseudo_id()
    r = client.post("/v1/events", json={
        "pseudo_id": pid,
        "events": [_event(finding_hash=SECRET)],
    })
    assert r.status_code == 422


def test_no_event_payload_reaches_the_logs(caplog):
    import logging
    pid = _enrolled_pseudo_id()
    DISTINCTIVE_CATEGORY = "nric-collision-canary"
    DISTINCTIVE_HASH = "ab" * 32  # valid 64-hex finding_hash
    with caplog.at_level(logging.DEBUG):
        client.post("/v1/events", json={
            "pseudo_id": pid,
            "events": [_event(category=DISTINCTIVE_CATEGORY, finding_hash=DISTINCTIVE_HASH)],
        })
    joined = "\n".join(r.getMessage() for r in caplog.records)
    assert SECRET not in joined
    assert "gemini.google.com" not in joined
    assert DISTINCTIVE_CATEGORY not in joined
    assert DISTINCTIVE_HASH not in joined


def test_an_unknown_pseudo_id_is_401():
    r = client.post("/v1/events", json={"pseudo_id": "nope", "events": [_event()]})
    assert r.status_code == 401
