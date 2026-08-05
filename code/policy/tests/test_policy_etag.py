from fastapi.testclient import TestClient

from app.db import bump_policy_version
from app.deps import get_conn
from app.main import app
from app.seed import seed_company

client = TestClient(app)


def _org_id() -> str:
    return seed_company(get_conn(), "Acme Corp")[0]


def test_first_fetch_returns_a_body_and_an_etag():
    org_id = _org_id()
    r = client.get("/v1/policy", params={"org_id": org_id})
    assert r.status_code == 200
    assert r.headers["etag"]
    assert r.json()["org_id"] == org_id


def test_matching_etag_returns_304_with_no_body():
    org_id = _org_id()
    etag = client.get("/v1/policy", params={"org_id": org_id}).headers["etag"]
    r = client.get("/v1/policy", params={"org_id": org_id}, headers={"If-None-Match": etag})
    assert r.status_code == 304
    assert r.content == b""


def test_a_mismatched_etag_returns_200_with_a_full_body():
    """Mutation guard for the 304 test above.

    A handler that ignores If-None-Match and always returns 200 would still
    pass a naive "send If-None-Match, check status" test if that test used the
    right etag by accident. This sends a WRONG etag and requires 200 + a full
    body, which a status-only assertion elsewhere would not force.
    """
    org_id = _org_id()
    r = client.get(
        "/v1/policy", params={"org_id": org_id}, headers={"If-None-Match": 'W/"not-the-real-tag"'}
    )
    assert r.status_code == 200
    assert r.json()["org_id"] == org_id


def test_a_policy_change_invalidates_the_etag_within_one_poll():
    org_id = _org_id()
    etag = client.get("/v1/policy", params={"org_id": org_id}).headers["etag"]
    bump_policy_version(get_conn(), org_id)
    r = client.get("/v1/policy", params={"org_id": org_id}, headers={"If-None-Match": etag})
    assert r.status_code == 200
    assert r.headers["etag"] != etag


def test_unknown_org_is_404():
    assert client.get("/v1/policy", params={"org_id": "nope"}).status_code == 404
