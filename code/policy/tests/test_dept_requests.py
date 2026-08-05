import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_conn
from app.seed import seed_company, create_department, mint_employee_token

emp = TestClient(app)


def _dept_setup(dept_name="Engineering"):
    org_id, co_secret = seed_company(get_conn(), "DeptReq " + uuid.uuid4().hex[:6])
    dept_id, dept_secret = create_department(get_conn(), org_id, dept_name)
    token = mint_employee_token(get_conn(), org_id, dept_id, dept_name)
    pseudo = emp.post("/v1/enroll", json={"token": token}).json()["pseudo_id"]
    dc = TestClient(app)
    dc.post("/v1/admin/login", json={"role": "department", "secret": dept_secret})
    return org_id, dept_id, pseudo, dc


def test_dept_approval_writes_a_dept_override_not_company_policy():
    org_id, dept_id, pseudo, dc = _dept_setup()
    req_id = emp.post("/v1/requests", json={
        "pseudo_id": pseudo, "llm_id": "google", "reason": "translation"}).json()["id"]

    assert any(r["id"] == req_id for r in dc.get("/v1/dept/requests").json())
    assert dc.post(f"/v1/dept/requests/{req_id}", json={"decision": "approved"}).status_code == 200

    conn = get_conn()
    override = conn.execute(
        "SELECT status FROM dept_llm_policy WHERE department_id = %s AND llm_id = 'google'",
        (dept_id,)).fetchone()
    assert override["status"] == "approved"
    company = conn.execute(
        "SELECT status FROM org_llm_policy WHERE org_id = %s AND llm_id = 'google'",
        (org_id,)).fetchone()
    assert company["status"] == "blocked"   # company default untouched


def test_dept_a_cannot_see_or_decide_dept_b_requests():
    org_id, dept_a, pseudo_a, dc_a = _dept_setup("Alpha")
    # a second department in the SAME company, with its own employee + request
    dept_b, secret_b = create_department(get_conn(), org_id, "Beta")
    token_b = mint_employee_token(get_conn(), org_id, dept_b, "Beta")
    pseudo_b = emp.post("/v1/enroll", json={"token": token_b}).json()["pseudo_id"]
    req_b = emp.post("/v1/requests", json={
        "pseudo_id": pseudo_b, "llm_id": "xai", "reason": "probe"}).json()["id"]

    assert all(r["id"] != req_b for r in dc_a.get("/v1/dept/requests").json())
    assert dc_a.post(f"/v1/dept/requests/{req_b}", json={"decision": "approved"}).status_code == 404


def test_dept_temporary_and_conditional_approval():
    org_id, dept_id, pseudo, dc = _dept_setup("TieredDept")
    req_id = emp.post("/v1/requests", json={
        "pseudo_id": pseudo, "llm_id": "google", "reason": "trial access"}).json()["id"]

    res = dc.post(f"/v1/dept/requests/{req_id}", json={
        "decision": "temporary",
        "duration_days": 7,
        "access_mode": "strict_redaction"
    })
    assert res.status_code == 200
    assert res.json()["access_state"] == "temporary"

    policy_res = emp.post("/v1/enroll", json={
        "token": mint_employee_token(get_conn(), org_id, dept_id, "TieredDept")
    }).json()["policy"]

    google_tool = next(t for t in policy_res["tools"] if t["llm_id"] == "google")
    assert google_tool["status"] == "temporary"
    assert google_tool["access_mode"] == "strict_redaction"
    assert google_tool["expires_at"] is not None


def test_expired_pass_evaluates_as_blocked():
    org_id, dept_id, pseudo, dc = _dept_setup("ExpiredDept")
    req_id = emp.post("/v1/requests", json={
        "pseudo_id": pseudo, "llm_id": "perplexity", "reason": "past pass"}).json()["id"]

    # Post an expired pass directly into DB
    conn = get_conn()
    conn.execute(
        "INSERT INTO dept_llm_policy (org_id, department_id, llm_id, status, access_mode, expires_at)"
        " VALUES (%s, %s, %s, 'temporary', 'standard', '2020-01-01T00:00:00+00:00')"
        " ON CONFLICT (department_id, llm_id) DO UPDATE SET status = EXCLUDED.status, expires_at = EXCLUDED.expires_at",
        (org_id, dept_id, "perplexity"),
    )
    conn.commit()

    from app.routes.policy_read import read_policy
    pol = read_policy(conn, org_id, dept_id)
    perps = next(t for t in pol.tools if t.llm_id == "perplexity")
    assert perps.status == "blocked"
    assert perps.expires_at is None
