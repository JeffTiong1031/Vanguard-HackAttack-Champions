import uuid

from fastapi.testclient import TestClient

from app.deps import get_conn
from app.main import app
from app.seed import seed_company
from app.security import new_token, now_iso

client = TestClient(app)


def _mint(department: str) -> str:
    org_id, _ = seed_company(get_conn(), "Acme Corp")
    plain, hashed = new_token(department[:3])
    get_conn().execute(
        "INSERT INTO enroll_tokens (id, org_id, department, token_hash, label, created_at)"
        " VALUES (%s, %s, %s, %s, %s, %s)",
        (uuid.uuid4().hex, org_id, department, hashed, department, now_iso()),
    )
    get_conn().commit()
    return plain


def test_enrol_returns_the_department_from_the_token_not_the_client():
    token = _mint("Engineering")
    r = client.post("/v1/enroll", json={"token": token})
    assert r.status_code == 200
    body = r.json()
    assert body["department"] == "Engineering"
    assert body["policy"]["version"] >= 1
    assert any(t["host"] == "chatgpt.com" and t["status"] == "approved"
               for t in body["policy"]["tools"])


def test_enrol_mints_a_distinct_pseudo_id_per_person():
    """Two different people (two different tokens) get different identities.

    Was: minted a fresh pseudo_id on every call to the SAME token. That is
    the exact bug task 1.2 fixes -- a reinstall must reuse the identity, not
    split it -- so same-token idempotence is now covered by
    test_enrolment_identity.py::test_same_token_twice_returns_one_identity,
    and this test moved to what it was actually meant to pin: distinctness
    across people.
    """
    a = client.post("/v1/enroll", json={"token": _mint("Engineering")}).json()["pseudo_id"]
    b = client.post("/v1/enroll", json={"token": _mint("Engineering")}).json()["pseudo_id"]
    assert a != b


def test_a_bad_token_is_401():
    assert client.post("/v1/enroll", json={"token": "ENG-nope"}).status_code == 401


def test_a_revoked_token_is_401():
    token = _mint("Finance")
    get_conn().execute("UPDATE enroll_tokens SET revoked = 1")
    get_conn().commit()
    assert client.post("/v1/enroll", json={"token": token}).status_code == 401


def test_the_client_cannot_choose_its_own_department():
    token = _mint("Engineering")
    r = client.post("/v1/enroll", json={"token": token, "department": "Executive"})
    assert r.status_code == 422  # extra="forbid"


def test_department_from_body_is_rejected_not_silently_ignored():
    """Stronger than a bare 422: prove the request never reached the handler.

    If the route accidentally read `department` off the body (instead of the
    token) this would still be caught by pydantic's extra="forbid" -- but only
    because the field name happens to collide with a model field. This test
    pins the *reason* for the 422: the body is rejected at validation, before
    any department lookup happens, by asserting the response is a pydantic
    validation error shape, not an application-level rejection.
    """
    token = _mint("Engineering")
    r = client.post("/v1/enroll", json={"token": token, "department": "Executive"})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert any(e.get("type") == "extra_forbidden" for e in detail)


def test_pseudo_id_is_a_fresh_uuid4_not_derived_from_the_token():
    """Pin the randomness contract, not just "looks different across calls".

    A pseudo_id computed as e.g. sha256(token) would fail the "distinct each
    call" test (it's constant), but sha256(f"{token}:{call_count}") is
    DIFFERENT on every call while still being fully determined by public
    inputs (the token plus how many times it's been used) -- i.e. guessable,
    which defeats pseudonymity just as badly as a constant id. A 64-hex-char
    sha256 digest cannot parse as a UUID, so this assertion catches the NAIVE
    derivation family that an inequality check (a != b) alone would miss.

    Scope, stated honestly: this pins the FORMAT, not the entropy source. A
    deliberately crafted mutant -- truncate the digest to 32 hex chars and force
    the version and variant nibbles -- is still fully derived from the token and
    still parses as a UUIDv4, so it would pass. Closing that would need a
    statistical or source-level check, which is not worth it here: the shipped
    code is uuid.uuid4(), whose randomness comes from the platform CSPRNG.

    Uses two different tokens, not one token twice: since task 1.2, the same
    token returns the SAME pseudo_id on a second call (find-or-create), so
    "distinct" now has to be measured across two different people, not two
    calls of one enrolment.
    """
    a = client.post("/v1/enroll", json={"token": _mint("Engineering")}).json()["pseudo_id"]
    b = client.post("/v1/enroll", json={"token": _mint("Engineering")}).json()["pseudo_id"]
    for pid in (a, b):
        parsed = uuid.UUID(hex=pid)
        assert parsed.version == 4
    assert a != b


def test_the_422_body_never_echoes_a_rejected_token_value():
    """Critical: same defect as the events endpoint. `EnrollRequest` also sets
    extra="forbid", and pydantic's default validation error embeds the
    offending value verbatim. Reproduced two ways:

    (a) the task's literal repro shape -- a valid token plus an extra
    `department` field. The value that actually gets echoed here by pydantic
    is the extra field's own value ("Executive"), so this is the genuine
    RED-to-GREEN case for *this* endpoint's scrubbing.

    (b) a client that mistypes the token's field name (a realistic bug) sends
    the actual secret token value under an unrecognised key -- extra="forbid"
    then echoes the enrolment token itself verbatim in `input`. This is the
    scenario the finding names explicitly: "an enrolment token would come
    back in a 422 body."
    """
    r = client.post("/v1/enroll", json={"token": "some-token-value", "department": "Executive"})
    assert r.status_code == 422
    assert "some-token-value" not in r.text
    assert "Executive" not in r.text

    SECRET_TOKEN = "ENG-9f3c7b1a2e4d5f60"
    r2 = client.post("/v1/enroll", json={"toke": SECRET_TOKEN})
    assert r2.status_code == 422
    assert SECRET_TOKEN not in r2.text


def test_two_different_tokens_same_department_get_different_pseudo_ids_and_correct_department():
    """Cross-check the department comes from each token's own row, not a shared default."""
    eng_token = _mint("Engineering")
    fin_token = _mint("Finance")
    eng = client.post("/v1/enroll", json={"token": eng_token}).json()
    fin = client.post("/v1/enroll", json={"token": fin_token}).json()
    assert eng["department"] == "Engineering"
    assert fin["department"] == "Finance"
    assert eng["pseudo_id"] != fin["pseudo_id"]
