import uuid

from fastapi.testclient import TestClient

from app.main import app, bootstrap_demo, get_conn
from app.seed import seed_demo_org, seed_company, create_department, mint_employee_token
from app.security import new_token, now_iso

client = TestClient(app)


def _company_client() -> tuple[TestClient, str]:
    """A logged-in COMPANY client and its org_id."""
    org_id, secret = seed_company(get_conn(), "Acme " + uuid.uuid4().hex[:6])
    c = TestClient(app)
    assert c.post("/v1/admin/login", json={"role": "company", "secret": secret}).status_code == 200
    return c, org_id


def _login() -> TestClient:
    bootstrap_demo("Acme Corp", "vanguard")
    c = TestClient(app)
    r = c.post("/v1/admin/login", json={"org_name": "Acme Corp", "password": "vanguard"})
    assert r.status_code == 200
    return c


def _pseudo_id() -> str:
    org_id = bootstrap_demo()
    plain, hashed = new_token("ENG")
    get_conn().execute(
        "INSERT INTO enroll_tokens (id, org_id, department, token_hash, label, created_at)"
        " VALUES (?, ?, 'Engineering', ?, 'Engineering', ?)",
        (uuid.uuid4().hex, org_id, hashed, now_iso()),
    )
    get_conn().commit()
    return client.post("/v1/enroll", json={"token": plain}).json()["pseudo_id"]


def test_every_admin_route_refuses_an_unauthenticated_caller():
    fresh = TestClient(app)
    for method, path in [
        ("get", "/v1/admin/tools"), ("get", "/v1/admin/tokens"),
        ("get", "/v1/admin/requests"), ("get", "/v1/admin/usage"),
    ]:
        assert getattr(fresh, method)(path).status_code == 401, path


def test_approving_a_tool_bumps_the_policy_version():
    c = _login()
    org_id = bootstrap_demo()
    before = get_conn().execute(
        "SELECT policy_version AS v FROM orgs WHERE id = ?", (org_id,)
    ).fetchone()["v"]
    r = c.post("/v1/admin/tools/google", json={"status": "approved"})
    assert r.status_code == 200
    after = get_conn().execute(
        "SELECT policy_version AS v FROM orgs WHERE id = ?", (org_id,)
    ).fetchone()["v"]
    assert after > before


def test_minting_a_token_returns_the_plaintext_exactly_once():
    c = _login()
    r = c.post("/v1/admin/tokens", json={"department": "Finance"})
    assert r.status_code == 201
    plain = r.json()["token"]
    assert plain.startswith("FIN-")
    listed = c.get("/v1/admin/tokens").json()
    assert all("token" not in row for row in listed)


def test_deciding_a_request_approves_the_tool_and_bumps_the_version():
    c = _login()
    pid = _pseudo_id()
    req_id = client.post("/v1/requests", json={
        "pseudo_id": pid, "llm_id": "perplexity", "reason": "research",
    }).json()["id"]

    org_id = bootstrap_demo()
    before = get_conn().execute(
        "SELECT policy_version AS v FROM orgs WHERE id = ?", (org_id,)
    ).fetchone()["v"]
    r = c.post(f"/v1/admin/requests/{req_id}", json={"decision": "approved"})
    assert r.status_code == 200

    status = get_conn().execute(
        "SELECT status FROM org_llm_policy WHERE org_id = ? AND llm_id = 'perplexity'",
        (org_id,),
    ).fetchone()["status"]
    assert status == "approved"
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
    c = _login()
    org_id = bootstrap_demo()
    before = get_conn().execute(
        "SELECT policy_version AS v FROM orgs WHERE id = ?", (org_id,)
    ).fetchone()["v"]

    r = c.post("/v1/admin/tools/NOT_A_TOOL", json={"status": "approved"})
    assert r.status_code == 404

    after = get_conn().execute(
        "SELECT policy_version AS v FROM orgs WHERE id = ?", (org_id,)
    ).fetchone()["v"]
    assert after == before


def test_deciding_an_already_decided_request_is_409_and_does_not_re_decide():
    """A decided request must not be decidable again -- the console hides the
    buttons on decided rows, but authority is server-side, so the server
    itself must refuse a second decision rather than rely on the client not
    offering one. Denied-then-approved must not flip a denial into an
    approval, and the version must not move on the rejected second call."""
    c = _login()
    pid = _pseudo_id()
    req_id = client.post("/v1/requests", json={
        "pseudo_id": pid, "llm_id": "xai", "reason": "first pass",
    }).json()["id"]

    first = c.post(f"/v1/admin/requests/{req_id}", json={"decision": "denied"})
    assert first.status_code == 200

    org_id = bootstrap_demo()
    before_status = get_conn().execute(
        "SELECT status FROM access_requests WHERE id = ?", (req_id,)
    ).fetchone()["status"]
    before_version = get_conn().execute(
        "SELECT policy_version AS v FROM orgs WHERE id = ?", (org_id,)
    ).fetchone()["v"]

    second = c.post(f"/v1/admin/requests/{req_id}", json={"decision": "approved"})
    assert second.status_code == 409

    after_status = get_conn().execute(
        "SELECT status FROM access_requests WHERE id = ?", (req_id,)
    ).fetchone()["status"]
    after_version = get_conn().execute(
        "SELECT policy_version AS v FROM orgs WHERE id = ?", (org_id,)
    ).fetchone()["v"]

    assert after_status == before_status == "denied"
    assert after_version == before_version


def test_usage_aggregates_by_department_and_category():
    c = _login()
    pid = _pseudo_id()
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
# caller, above) only walks the four read-only GET routes. The task
# instructions ask for EVERY admin route, "not a sample" -- so this repeats
# the sweep across the mutating POST routes and /logout too, since
# _require_admin is called on all nine non-login routes.


def test_every_mutating_admin_route_and_logout_refuse_an_unauthenticated_caller():
    fresh = TestClient(app)
    checks = [
        ("post", "/v1/admin/logout", None),
        ("post", "/v1/admin/tools/google", {"status": "approved"}),
        ("post", "/v1/admin/tokens", {"department": "Finance"}),
        ("post", "/v1/admin/tokens/does-not-matter/revoke", None),
        ("post", "/v1/admin/requests/does-not-matter", {"decision": "approved"}),
    ]
    for method, path, body in checks:
        r = getattr(fresh, method)(path, json=body) if body is not None else getattr(fresh, method)(path)
        assert r.status_code == 401, path


def test_logout_actually_invalidates_the_session_not_just_the_cookie():
    """A client that replays the OLD session token after logout must still
    get 401 -- deleting the cookie client-side is not the control; deleting
    the admin_sessions row server-side is."""
    c = _login()
    old_cookie = c.cookies.get("vg_admin")
    assert c.post("/v1/admin/logout").status_code == 200

    replay = TestClient(app)
    replay.cookies.set("vg_admin", old_cookie)
    assert replay.get("/v1/admin/tools").status_code == 401


def test_denying_a_request_does_not_change_tool_status_or_bump_the_version():
    """Mirrors test_deciding_a_request_approves_the_tool_and_bumps_the_version
    but for the OTHER decision. A denial leaves org_llm_policy untouched, so
    GET /v1/policy would serve byte-identical tools/categories before and
    after -- the ETag must not move for a client that never needed to
    refresh."""
    c = _login()
    pid = _pseudo_id()
    req_id = client.post("/v1/requests", json={
        "pseudo_id": pid, "llm_id": "deepseek", "reason": "eval",
    }).json()["id"]

    org_id = bootstrap_demo()
    before_status = get_conn().execute(
        "SELECT status FROM org_llm_policy WHERE org_id = ? AND llm_id = 'deepseek'",
        (org_id,),
    ).fetchone()["status"]
    before_version = get_conn().execute(
        "SELECT policy_version AS v FROM orgs WHERE id = ?", (org_id,)
    ).fetchone()["v"]

    r = c.post(f"/v1/admin/requests/{req_id}", json={"decision": "denied"})
    assert r.status_code == 200

    after_status = get_conn().execute(
        "SELECT status FROM org_llm_policy WHERE org_id = ? AND llm_id = 'deepseek'",
        (org_id,),
    ).fetchone()["status"]
    after_version = get_conn().execute(
        "SELECT policy_version AS v FROM orgs WHERE id = ?", (org_id,)
    ).fetchone()["v"]

    assert after_status == before_status == "blocked"
    assert after_version == before_version


def test_minting_and_revoking_a_token_do_not_bump_the_policy_version():
    """enroll_tokens is never read by read_policy() -- a currently-enrolled
    extension's cached policy is unaffected by either operation."""
    c = _login()
    org_id = bootstrap_demo()
    before = get_conn().execute(
        "SELECT policy_version AS v FROM orgs WHERE id = ?", (org_id,)
    ).fetchone()["v"]

    minted = c.post("/v1/admin/tokens", json={"department": "Legal"})
    assert minted.status_code == 201
    after_mint = get_conn().execute(
        "SELECT policy_version AS v FROM orgs WHERE id = ?", (org_id,)
    ).fetchone()["v"]
    assert after_mint == before

    token_id = minted.json()["id"]
    revoked = c.post(f"/v1/admin/tokens/{token_id}/revoke")
    assert revoked.status_code == 200
    after_revoke = get_conn().execute(
        "SELECT policy_version AS v FROM orgs WHERE id = ?", (org_id,)
    ).fetchone()["v"]
    assert after_revoke == before


def test_an_admin_session_cannot_read_or_act_on_another_orgs_data():
    """Cross-tenant isolation. Org A's session must not see Org B's tokens or
    requests, and acting on Org B's IDs from Org A's session must not affect
    Org B's rows."""
    a = _login()
    org_a = bootstrap_demo()
    org_b = seed_demo_org(get_conn(), "Umbrella Corp", "different-password")

    # A token minted under Org B...
    plain_b, hashed_b = new_token("SEC")
    token_b_id = uuid.uuid4().hex
    get_conn().execute(
        "INSERT INTO enroll_tokens (id, org_id, department, token_hash, label, created_at)"
        " VALUES (?, ?, 'Security', ?, 'Security', ?)",
        (token_b_id, org_b, hashed_b, now_iso()),
    )
    get_conn().commit()

    # ...must not appear in Org A's token list...
    a_tokens = a.get("/v1/admin/tokens").json()
    assert all(t["id"] != token_b_id for t in a_tokens)

    # ...and Org A's session must not be able to revoke it.
    r = a.post(f"/v1/admin/tokens/{token_b_id}/revoke")
    assert r.status_code == 200  # scoped UPDATE affects 0 rows, not an error
    still_live = get_conn().execute(
        "SELECT revoked FROM enroll_tokens WHERE id = ?", (token_b_id,)
    ).fetchone()["revoked"]
    assert still_live == 0

    # A request raised under Org B must not appear in Org A's request queue,
    # and Org A's session must not be able to decide it.
    b = TestClient(app)
    login_b = b.post("/v1/admin/login", json={"org_name": "Umbrella Corp", "password": "different-password"})
    assert login_b.status_code == 200

    plain_enroll, hashed_enroll = new_token("SEC")
    get_conn().execute(
        "INSERT INTO enroll_tokens (id, org_id, department, token_hash, label, created_at)"
        " VALUES (?, ?, 'Security', ?, 'Security', ?)",
        (uuid.uuid4().hex, org_b, hashed_enroll, now_iso()),
    )
    get_conn().commit()
    pid_b = client.post("/v1/enroll", json={"token": plain_enroll}).json()["pseudo_id"]
    req_b = client.post("/v1/requests", json={
        "pseudo_id": pid_b, "llm_id": "mistral", "reason": "cross-tenant probe",
    }).json()["id"]

    a_requests = a.get("/v1/admin/requests").json()
    assert all(r["id"] != req_b for r in a_requests)

    decide = a.post(f"/v1/admin/requests/{req_b}", json={"decision": "approved"})
    assert decide.status_code == 404

    org_a_status = get_conn().execute(
        "SELECT status FROM org_llm_policy WHERE org_id = ? AND llm_id = 'mistral'", (org_a,)
    ).fetchone()["status"]
    assert org_a_status == "blocked"  # unaffected by the cross-tenant attempt
