import uuid

from fastapi.testclient import TestClient

from app.main import app, get_conn
from app.seed import seed_company, create_department, mint_employee_token
from app.security import now_iso

client = TestClient(app)


def _company_client() -> tuple[TestClient, str]:
    """A logged-in COMPANY client and its org_id."""
    org_id, secret = seed_company(get_conn(), "Acme " + uuid.uuid4().hex[:6])
    c = TestClient(app)
    assert c.post("/v1/admin/login", json={"role": "company", "secret": secret}).status_code == 200
    return c, org_id


def test_every_admin_route_refuses_an_unauthenticated_caller():
    fresh = TestClient(app)
    for method, path in [
        ("get", "/v1/admin/tools"), ("get", "/v1/admin/departments"),
        ("get", "/v1/admin/requests"), ("get", "/v1/admin/usage"),
    ]:
        assert getattr(fresh, method)(path).status_code == 401, path


def test_approving_a_tool_bumps_the_policy_version():
    c, org_id = _company_client()
    before = get_conn().execute(
        "SELECT policy_version AS v FROM orgs WHERE id = ?", (org_id,)
    ).fetchone()["v"]
    r = c.post("/v1/admin/tools/google", json={"status": "approved"})
    assert r.status_code == 200
    after = get_conn().execute(
        "SELECT policy_version AS v FROM orgs WHERE id = ?", (org_id,)
    ).fetchone()["v"]
    assert after > before


def test_setting_an_unknown_tool_is_404_and_does_not_bump_the_version():
    """The UPDATE in set_tool matches zero rows for a made-up llm_id --
    previously that was silently treated as success and the version bumped
    anyway, so every enrolled extension discarded a valid cache and
    refetched a byte-identical policy. Mirrors POST /v1/requests, which
    already 404s an unknown llm_id."""
    c, org_id = _company_client()
    before = get_conn().execute(
        "SELECT policy_version AS v FROM orgs WHERE id = ?", (org_id,)
    ).fetchone()["v"]

    r = c.post("/v1/admin/tools/NOT_A_TOOL", json={"status": "approved"})
    assert r.status_code == 404

    after = get_conn().execute(
        "SELECT policy_version AS v FROM orgs WHERE id = ?", (org_id,)
    ).fetchone()["v"]
    assert after == before


def test_usage_aggregates_by_department_and_category():
    c, org_id = _company_client()
    dept_id, _ = create_department(get_conn(), org_id, "Engineering")
    token = mint_employee_token(get_conn(), org_id, dept_id, "Engineering")
    pid = client.post("/v1/enroll", json={"token": token}).json()["pseudo_id"]
    client.post("/v1/events", json={"pseudo_id": pid, "events": [
        {"host": "gemini.google.com", "type": "visit_unapproved", "ts": now_iso()},
        {"host": "chatgpt.com", "type": "ethics_block",
         "category": "covert_surveillance", "ts": now_iso()},
    ]})
    body = c.get("/v1/admin/usage").json()
    assert any(d["department"] == "Engineering" for d in body["by_department"])
    assert any(x["category"] == "covert_surveillance" for x in body["by_category"])


# --- Additional coverage beyond the brief's six tests -----------------------
#
# The task brief's sweep (test_every_admin_route_refuses_an_unauthenticated_
# caller, above) only walks the read-only GET routes. The task instructions
# ask for EVERY admin route, "not a sample" -- so this repeats the sweep
# across the mutating POST routes and /logout too, since require_company is
# called on every non-login route.


def test_every_mutating_admin_route_and_logout_refuse_an_unauthenticated_caller():
    fresh = TestClient(app)
    checks = [
        ("post", "/v1/admin/logout", None),
        ("post", "/v1/admin/tools/google", {"status": "approved"}),
        ("post", "/v1/admin/departments", {"name": "Finance"}),
        ("post", "/v1/admin/departments/does-not-matter/regenerate", None),
    ]
    for method, path, body in checks:
        r = getattr(fresh, method)(path, json=body) if body is not None else getattr(fresh, method)(path)
        assert r.status_code == 401, path


def test_logout_actually_invalidates_the_session_not_just_the_cookie():
    """A client that replays the OLD session token after logout must still
    get 401 -- deleting the cookie client-side is not the control; deleting
    the admin_sessions row server-side is."""
    c, _ = _company_client()
    old_cookie = c.cookies.get("vg_admin")
    assert c.post("/v1/admin/logout").status_code == 200

    replay = TestClient(app)
    replay.cookies.set("vg_admin", old_cookie)
    assert replay.get("/v1/admin/tools").status_code == 401


def test_company_oversight_requests_and_appeals_are_read_only():
    c, org_id = _company_client()
    # the POST decide routes no longer exist on /v1/admin
    assert c.post("/v1/admin/requests/anything", json={"decision": "approved"}).status_code == 404
    assert c.post("/v1/admin/tokens", json={"department": "X"}).status_code == 404


def test_company_can_see_all_departments_usage():
    c, org_id = _company_client()
    body = c.get("/v1/admin/usage").json()
    assert set(body.keys()) == {"by_department", "by_tool", "by_category"}
