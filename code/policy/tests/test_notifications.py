"""Unit tests for employee notification creation, retrieval, and email alert dispatching."""
import uuid
from fastapi.testclient import TestClient

from app.deps import get_conn
from app.main import app
from app.seed import seed_company, create_department, mint_employee_token

client = TestClient(app)


def _setup_notification_test(dept_name="NotifDept"):
    org_id, co_secret = seed_company(get_conn(), "NotifOrg " + uuid.uuid4().hex[:6])
    dept_id, dept_secret = create_department(get_conn(), org_id, dept_name)
    token = mint_employee_token(get_conn(), org_id, dept_id, dept_name)
    pseudo = client.post("/v1/enroll", json={"token": token}).json()["pseudo_id"]
    dc = TestClient(app)
    dc.post("/v1/admin/login", json={"role": "department", "secret": dept_secret})
    return org_id, dept_id, pseudo, dc


def test_notifications_lifecycle():
    org_id, dept_id, pseudo, dc = _setup_notification_test()

    # 1. Post access request (triggers submission notification)
    req = client.post("/v1/requests", json={
        "pseudo_id": pseudo,
        "llm_id": "google",
        "reason": "Need Google for documentation synthesis",
    })
    assert req.status_code == 201
    req_id = req.json()["id"]

    # Submission notification is logged
    notifs_sub = client.get(f"/v1/notifications?pseudo_id={pseudo}").json()
    assert len(notifs_sub) == 1
    assert "Submitted" in notifs_sub[0]["title"]

    # 2. Dept Manager approves request (triggers decision notification)
    decide_res = dc.post(f"/v1/dept/requests/{req_id}", json={
        "decision": "approved",
        "access_mode": "standard",
        "note": "Approved for project work",
    })
    assert decide_res.status_code == 200

    # 3. Employee checks notifications (submission + decision = 2)
    notifs = client.get(f"/v1/notifications?pseudo_id={pseudo}").json()
    assert len(notifs) == 2
    assert "Approved" in notifs[0]["title"]
    assert "Google" in notifs[0]["title"]
    assert notifs[0]["status"] == "unread"
    assert "Manager note: Approved for project work" in notifs[0]["message"]

    # 4. Mark read
    mark_res = client.post("/v1/notifications/mark-read", json={
        "pseudo_id": pseudo,
        "notification_ids": [notifs[0]["id"]],
    })
    assert mark_res.status_code == 200

    notifs_after = client.get(f"/v1/notifications?pseudo_id={pseudo}").json()
    assert notifs_after[0]["status"] == "read"


def test_prompt_review_request_notifications():
    org_id, dept_id, pseudo, dc = _setup_notification_test("PromptNotifDept")

    # 1. Employee submits prompt review appeal
    scope_fp = "a" * 64
    appeal_res = client.post("/v1/appeals", json={
        "pseudo_id": pseudo,
        "decision_type": "ethics",
        "category": "covert_surveillance",
        "reason": "Auditing internal system defense",
        "scope_fingerprint": scope_fp,
    })
    assert appeal_res.status_code == 201
    appeal_id = appeal_res.json()["id"]

    # Check notification created on prompt review submission
    notifs = client.get(f"/v1/notifications?pseudo_id={pseudo}").json()
    assert len(notifs) == 1
    assert "Prompt Review Submitted" in notifs[0]["title"]
    assert "Covert Surveillance" in notifs[0]["title"]

    # 2. Manager overturns/approves the appeal
    decide_appeal = dc.post(f"/v1/dept/appeals/{appeal_id}", json={
        "decision": "approved",
        "note": "Approved for defensive auditing",
    })
    assert decide_appeal.status_code == 200

    # 3. Employee checks decision notification
    notifs_after = client.get(f"/v1/notifications?pseudo_id={pseudo}").json()
    assert len(notifs_after) == 2
    assert "Approved" in notifs_after[0]["title"]
    assert "Manager note: Approved for defensive auditing" in notifs_after[0]["message"]
