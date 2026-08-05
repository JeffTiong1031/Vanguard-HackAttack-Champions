import uuid

from fastapi import APIRouter, HTTPException

from app.deps import get_conn
from app.models import AccessRequestCreate
from app.remediation import get_remediation_guidance
from app.security import now_iso

router = APIRouter()


@router.post("/v1/requests", status_code=201)
async def create_request(body: AccessRequestCreate) -> dict[str, str]:
    conn = get_conn()
    emp = conn.execute(
        "SELECT id, org_id FROM employees WHERE pseudo_id = %s", (body.pseudo_id,)
    ).fetchone()
    if emp is None:
        raise HTTPException(status_code=401, detail="unknown enrolment")

    tool = conn.execute(
        "SELECT id FROM llm_registry WHERE id = %s", (body.llm_id,)
    ).fetchone()
    if tool is None:
        raise HTTPException(status_code=404, detail="unknown tool")

    now_str = now_iso()
    # Pre-screen 1: an already-approved or active temporary/trial/conditional policy needs no new queue item.
    effective = conn.execute(
        "SELECT COALESCE(dp.status, cp.status) AS status,"
        "       COALESCE(dp.expires_at, cp.expires_at) AS expires_at"
        " FROM employees e"
        " JOIN org_llm_policy cp ON cp.org_id = e.org_id AND cp.llm_id = %s"
        " LEFT JOIN dept_llm_policy dp ON dp.department_id = e.department_id AND dp.llm_id = %s"
        " WHERE e.id = %s",
        (body.llm_id, body.llm_id, emp["id"]),
    ).fetchone()
    if (
        effective
        and effective["status"] in ("approved", "temporary", "trial", "conditional")
        and (not effective["expires_at"] or effective["expires_at"] >= now_str)
    ):
        return {
            "id": f"policy:{body.llm_id}", "status": effective["status"],
            "request_state": "decided", "access_state": effective["status"],
            "pre_screen": "already_approved",
        }

    # One pending request per employee per tool. Clicking twice is not two
    # requests, and the admin queue should not fill with duplicates.
    existing = conn.execute(
        "SELECT id FROM access_requests"
        " WHERE employee_id = %s AND llm_id = %s AND status = 'pending'",
        (emp["id"], body.llm_id),
    ).fetchone()
    if existing:
        return {
            "id": existing["id"], "status": "pending",
            "request_state": "submitted", "access_state": "blocked",
            "pre_screen": "duplicate",
        }

    request_id = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO access_requests"
        " (id, org_id, employee_id, llm_id, reason, status, created_at)"
        " VALUES (%s, %s, %s, %s, %s, 'pending', %s)",
        (request_id, emp["org_id"], emp["id"], body.llm_id, body.reason, now_str),
    )

    from app.routes.notifications import create_notification
    tool = conn.execute("SELECT display_name FROM llm_registry WHERE id = %s", (body.llm_id,)).fetchone()
    tool_name = tool["display_name"] if tool and tool.get("display_name") else body.llm_id
    title = f"Access Request Submitted: {tool_name}"
    msg_text = f"Your request for access to {tool_name} has been submitted and is in review with your manager."
    if body.reason:
        msg_text += f" Reason: {body.reason}"
    create_notification(conn, emp["org_id"], emp["id"], "request_submitted", title, msg_text)

    conn.commit()
    return {
        "id": request_id, "status": "pending",
        "request_state": "submitted", "access_state": "blocked",
        "pre_screen": "ready_for_review",
    }


@router.get("/v1/requests")
async def list_my_requests(pseudo_id: str) -> list[dict]:
    """Employee-visible status with actionable remediation guidance when blocked."""
    conn = get_conn()
    emp = conn.execute(
        "SELECT id FROM employees WHERE pseudo_id = %s", (pseudo_id,)
    ).fetchone()
    if emp is None:
        raise HTTPException(status_code=401, detail="unknown enrolment")
    
    rows = conn.execute(
        "SELECT a.id, a.llm_id, r.display_name, a.status, a.access_mode, a.expires_at, a.reason_code, a.admin_note,"
        " a.created_at, a.decided_at,"
        " CASE WHEN a.status IN ('approved','temporary','trial','conditional') THEN a.status ELSE 'blocked' END AS access_state,"
        " CASE WHEN a.status = 'pending' THEN 'in_review' ELSE 'decided' END AS request_state"
        " FROM access_requests a JOIN llm_registry r ON r.id = a.llm_id"
        " WHERE a.employee_id = %s ORDER BY a.created_at DESC",
        (emp["id"],),
    ).fetchall()

    res = []
    for r in rows:
        item = dict(r)
        if item["access_state"] == "blocked":
            item["remediation_guidance"] = get_remediation_guidance(item["reason_code"])
        res.append(item)
    return res

