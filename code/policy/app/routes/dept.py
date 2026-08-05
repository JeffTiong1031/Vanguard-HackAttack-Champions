"""Department dashboard API. Every route is scoped to the session's
department_id -- a department admin can only ever see and act on its own
department's employees, requests, appeals, and tokens."""
import uuid

from fastapi import APIRouter, Body, Cookie, HTTPException

from app.analytics import analytics_summary, analytics_alerts
from app.authz import require_department
from app.db import bump_policy_version
from app.deps import get_conn
from app.models import AccessDecision, AppealDecision
from app.security import new_token, now_iso

router = APIRouter(prefix="/v1/dept")


def _current_version(conn, org_id: str) -> int:
    return int(conn.execute(
        "SELECT policy_version FROM orgs WHERE id = %s", (org_id,)
    ).fetchone()["policy_version"])


@router.get("/requests")
async def dept_requests(vg_admin: str | None = Cookie(default=None)) -> list[dict]:
    org_id, dept_id = require_department(vg_admin)
    return [dict(r) for r in get_conn().execute(
        "SELECT a.id, a.reason, a.status, a.access_mode, a.expires_at, a.created_at, e.department,"
        "       r.display_name, r.host, a.llm_id"
        " FROM access_requests a"
        " JOIN employees e ON e.id = a.employee_id"
        " JOIN llm_registry r ON r.id = a.llm_id"
        " WHERE a.org_id = %s AND e.department_id = %s ORDER BY a.created_at DESC",
        (org_id, dept_id),
    ).fetchall()]


@router.post("/requests/{request_id}")
async def dept_decide_request(
    request_id: str, body: AccessDecision,
    vg_admin: str | None = Cookie(default=None),
) -> dict[str, int | str]:
    from datetime import datetime, timedelta, timezone

    org_id, dept_id = require_department(vg_admin)
    conn = get_conn()
    row = conn.execute(
        "SELECT a.llm_id, a.employee_id, r.display_name FROM access_requests a"
        " JOIN employees e ON e.id = a.employee_id"
        " LEFT JOIN llm_registry r ON r.id = a.llm_id"
        " WHERE a.id = %s AND a.org_id = %s AND e.department_id = %s AND a.status = 'pending'",
        (request_id, org_id, dept_id),
    ).fetchone()
    if row is None:
        exists = conn.execute(
            "SELECT 1 FROM access_requests a JOIN employees e ON e.id = a.employee_id"
            " WHERE a.id = %s AND a.org_id = %s AND e.department_id = %s",
            (request_id, org_id, dept_id),
        ).fetchone()
        raise HTTPException(status_code=404 if exists is None else 409,
                            detail="unknown request" if exists is None else "request already decided")

    expires_at = None
    if body.duration_days:
        expires_at = (datetime.now(timezone.utc) + timedelta(days=body.duration_days)).isoformat()
    elif body.expires_at:
        expires_at = body.expires_at

    conn.execute(
        "UPDATE access_requests SET status = %s, reason_code = %s, admin_note = %s, decided_at = %s,"
        " access_mode = %s, expires_at = %s"
        " WHERE id = %s",
        (body.decision, body.reason_code, body.note, now_iso(), body.access_mode, expires_at, request_id),
    )

    from app.routes.notifications import create_notification
    tool_name = row["display_name"] if row and row.get("display_name") else row["llm_id"]
    title = f"Access Request {body.decision.capitalize()}: {tool_name}"
    msg_text = f"Your request for access to {tool_name} was reviewed and set to {body.decision.upper()}."
    if body.note:
        msg_text += f" Manager note: {body.note}"
    create_notification(conn, org_id, row["employee_id"], "request_decision", title, msg_text)

    if body.decision != "blocked":
        conn.execute(
            "INSERT INTO dept_llm_policy (org_id, department_id, llm_id, status, access_mode, expires_at)"
            " VALUES (%s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (department_id, llm_id) DO UPDATE SET status = EXCLUDED.status,"
            " access_mode = EXCLUDED.access_mode, expires_at = EXCLUDED.expires_at",
            (org_id, dept_id, row["llm_id"], body.decision, body.access_mode, expires_at),
        )
        return {"version": bump_policy_version(conn, org_id), "access_state": body.decision}

    conn.execute(
        "INSERT INTO dept_llm_policy (org_id, department_id, llm_id, status, access_mode, expires_at)"
        " VALUES (%s, %s, %s, 'blocked', 'standard', NULL)"
        " ON CONFLICT (department_id, llm_id) DO UPDATE SET status = 'blocked',"
        " access_mode = 'standard', expires_at = NULL",
        (org_id, dept_id, row["llm_id"]),
    )
    conn.commit()
    return {"version": bump_policy_version(conn, org_id), "access_state": "blocked"}


@router.get("/appeals")
async def dept_appeals(vg_admin: str | None = Cookie(default=None)) -> list[dict]:
    org_id, dept_id = require_department(vg_admin)
    return [dict(r) for r in get_conn().execute(
        "SELECT a.id, a.decision_type, a.category, a.employee_reason, a.disclosed_text,"
        "       a.status, a.reason_code, a.admin_note, a.created_at, e.department,"
        "       CASE WHEN a.status = 'approved' THEN 'approved' ELSE 'blocked' END AS access_state"
        " FROM decision_appeals a JOIN employees e ON e.id = a.employee_id"
        " WHERE a.org_id = %s AND e.department_id = %s ORDER BY a.created_at DESC",
        (org_id, dept_id),
    ).fetchall()]


@router.post("/appeals/{appeal_id}")
async def dept_decide_appeal(
    appeal_id: str, body: AppealDecision,
    vg_admin: str | None = Cookie(default=None),
) -> dict[str, str]:
    org_id, dept_id = require_department(vg_admin)
    conn = get_conn()
    row = conn.execute(
        "SELECT a.employee_id, a.category, a.decision_type FROM decision_appeals a"
        " JOIN employees e ON e.id = a.employee_id"
        " WHERE a.id = %s AND a.org_id = %s AND e.department_id = %s AND a.status = 'pending'",
        (appeal_id, org_id, dept_id),
    ).fetchone()
    if row is None:
        exists = conn.execute(
            "SELECT 1 FROM decision_appeals a JOIN employees e ON e.id = a.employee_id"
            " WHERE a.id = %s AND a.org_id = %s AND e.department_id = %s",
            (appeal_id, org_id, dept_id),
        ).fetchone()
        raise HTTPException(status_code=404 if exists is None else 409,
                            detail="unknown appeal" if exists is None else "appeal already decided")
    conn.execute(
        "UPDATE decision_appeals SET status = %s, reason_code = %s, admin_note = %s, decided_at = %s"
        " WHERE id = %s",
        (body.decision, body.reason_code, body.note, now_iso(), appeal_id),
    )

    from app.routes.notifications import create_notification
    cat_name = row["category"].replace("_", " ").title() if row and row.get("category") else "Ethics Review"
    title = f"Review Appeal {body.decision.capitalize()}: {cat_name}"
    msg_text = f"Your appeal for {cat_name} was reviewed and set to {body.decision.upper()}."
    if body.note:
        msg_text += f" Manager note: {body.note}"
    create_notification(conn, org_id, row["employee_id"], "appeal_decision", title, msg_text)

    conn.commit()
    return {"status": body.decision, "access_state": body.decision}


@router.get("/tokens")
async def dept_tokens(vg_admin: str | None = Cookie(default=None)) -> list[dict]:
    org_id, dept_id = require_department(vg_admin)
    return [dict(r) for r in get_conn().execute(
        "SELECT id, department, name, label, created_at, revoked FROM enroll_tokens"
        " WHERE org_id = %s AND department_id = %s ORDER BY created_at DESC",
        (org_id, dept_id),
    ).fetchall()]


@router.post("/tokens", status_code=201)
async def dept_mint_token(
    name: str = Body(default="", embed=True),
    vg_admin: str | None = Cookie(default=None),
) -> dict[str, str]:
    org_id, dept_id = require_department(vg_admin)
    conn = get_conn()
    dept_name = conn.execute(
        "SELECT name FROM departments WHERE id = %s", (dept_id,)
    ).fetchone()["name"]
    plain, hashed = new_token(dept_name[:3])
    token_id = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO enroll_tokens (id, org_id, department, department_id, token_hash, label, name, created_at)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (token_id, org_id, dept_name, dept_id, hashed, dept_name, name, now_iso()),
    )
    conn.commit()
    # enroll_tokens is never read by read_policy() -- no version bump.
    return {"id": token_id, "department": dept_name, "name": name, "token": plain}


@router.post("/tokens/{token_id}/revoke")
async def dept_revoke_token(
    token_id: str, vg_admin: str | None = Cookie(default=None),
) -> dict[str, bool]:
    org_id, dept_id = require_department(vg_admin)
    conn = get_conn()
    conn.execute(
        "UPDATE enroll_tokens SET revoked = 1"
        " WHERE id = %s AND org_id = %s AND department_id = %s",
        (token_id, org_id, dept_id),
    )
    conn.commit()
    return {"ok": True}


@router.get("/tools")
async def dept_tools(vg_admin: str | None = Cookie(default=None)) -> list[dict]:
    org_id, dept_id = require_department(vg_admin)
    return [dict(r) for r in get_conn().execute(
        "SELECT r.id AS llm_id, r.host, r.display_name,"
        "       COALESCE(dp.status, cp.status) AS status"
        " FROM llm_registry r"
        " JOIN org_llm_policy cp ON cp.llm_id = r.id AND cp.org_id = %s"
        " LEFT JOIN dept_llm_policy dp ON dp.llm_id = r.id AND dp.department_id = %s"
        " ORDER BY r.display_name",
        (org_id, dept_id),
    ).fetchall()]


@router.get("/usage")
async def dept_usage(vg_admin: str | None = Cookie(default=None)) -> dict[str, list[dict]]:
    org_id, dept_id = require_department(vg_admin)
    conn = get_conn()
    by_department = [dict(r) for r in conn.execute(
        "SELECT e.department, COUNT(*) AS events"
        " FROM usage_events u JOIN employees e ON e.id = u.employee_id"
        " WHERE u.org_id = %s AND e.department_id = %s GROUP BY e.department",
        (org_id, dept_id),
    ).fetchall()]
    by_tool = [dict(r) for r in conn.execute(
        "SELECT u.host, COUNT(*) AS events"
        " FROM usage_events u JOIN employees e ON e.id = u.employee_id"
        " WHERE u.org_id = %s AND e.department_id = %s GROUP BY u.host ORDER BY events DESC",
        (org_id, dept_id),
    ).fetchall()]
    by_category = [dict(r) for r in conn.execute(
        "SELECT u.category, COUNT(*) AS events"
        " FROM usage_events u JOIN employees e ON e.id = u.employee_id"
        " WHERE u.org_id = %s AND e.department_id = %s AND u.category IS NOT NULL"
        " GROUP BY u.category ORDER BY events DESC",
        (org_id, dept_id),
    ).fetchall()]
    return {"by_department": by_department, "by_tool": by_tool, "by_category": by_category}


def _days(days: int) -> int:
    return 30 if int(days) == 30 else 7


@router.get("/analytics/summary")
async def dept_analytics_summary(
    days: int = 7, vg_admin: str | None = Cookie(default=None)
) -> dict:
    org_id, dept_id = require_department(vg_admin)
    return analytics_summary(get_conn(), org_id, _days(days), dept_id)


@router.get("/analytics/alerts")
async def dept_analytics_alerts(
    limit: int = 50, vg_admin: str | None = Cookie(default=None)
) -> list[dict]:
    org_id, dept_id = require_department(vg_admin)
    return analytics_alerts(get_conn(), org_id, min(max(int(limit), 1), 200), dept_id)
