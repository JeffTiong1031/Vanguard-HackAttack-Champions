"""Company admin (dashboard) API.

Authority is decided HERE, server-side, on every request. The console is a
view; it never adjudicates whether its user is an admin. A client-side admin
check is bypassed with devtools in under a minute and would ship a control
whose audit trail claims it worked -- doc 00 section 6's worst case.

Every route below except /login calls `require_company` (app/authz.py),
including /logout. Login is the one legitimate exception -- it is how a
session is obtained in the first place, so it cannot itself require one.

This router is company-scoped and, since the department hierarchy landed,
oversight-only: it can see every department's tools/usage/requests/appeals
but it does not decide requests or appeals, and it does not mint employee
enrolment tokens -- those actions moved to `app/routes/dept.py`, scoped to
one department at a time. `POST /tools/{llm_id}` is the one write left here,
because tool approval is a company-wide default, not a department override.

Policy-version bumps: `POST /tools/{llm_id}` changes what `org_llm_policy`
holds, which is exactly what `GET /v1/policy` serialises -- so it calls
`bump_policy_version`. Department creation/regeneration touches
`departments`/`admin_sessions`, tables `read_policy()` never reads, so a
currently-enrolled extension's view is unchanged either way -- no bump.
"""
import uuid

from fastapi import APIRouter, Body, Cookie, HTTPException, Response

from app.analytics import analytics_summary, analytics_alerts
from app.authz import require_company
from app.db import bump_policy_version
from app.deps import get_conn
from app.models import AdminLogin, AccessDecision
from app.security import hash_token, issue_session, new_token, now_iso

router = APIRouter(prefix="/v1/admin")
SESSION_COOKIE = "vg_admin"


@router.post("/login")
async def login(body: AdminLogin, response: Response) -> dict[str, str]:
    conn = get_conn()
    h = hash_token(body.secret)
    if body.role == "company":
        row = conn.execute(
            "SELECT id, name FROM orgs WHERE admin_token_hash = %s", (h,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=401, detail="invalid credentials")
        token = issue_session(conn, row["id"], "company", None)
        response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax")
        return {"role": "company", "org_id": row["id"], "org_name": row["name"]}
    # department
    row = conn.execute(
        "SELECT d.id AS dept_id, d.org_id, d.name AS dept_name, o.name AS org_name"
        " FROM departments d JOIN orgs o ON o.id = d.org_id"
        " WHERE d.admin_token_hash = %s", (h,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = issue_session(conn, row["org_id"], "department", row["dept_id"])
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax")
    return {
        "role": "department", "org_id": row["org_id"], "org_name": row["org_name"],
        "department_id": row["dept_id"], "department": row["dept_name"],
    }


@router.post("/logout")
async def logout(response: Response, vg_admin: str | None = Cookie(default=None)) -> dict[str, bool]:
    from app.security import resolve_session
    if resolve_session(get_conn(), vg_admin) is None:
        raise HTTPException(status_code=401, detail="session required")
    get_conn().execute("DELETE FROM admin_sessions WHERE token = %s", (vg_admin,))
    get_conn().commit()
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@router.get("/departments")
async def list_departments(vg_admin: str | None = Cookie(default=None)) -> list[dict]:
    org_id = require_company(vg_admin)
    return [dict(r) for r in get_conn().execute(
        "SELECT d.id, d.name, d.created_at,"
        " (SELECT COUNT(*) FROM enroll_tokens t"
        "    WHERE t.department_id = d.id AND t.revoked = 0) AS active_tokens"
        " FROM departments d WHERE d.org_id = %s ORDER BY d.created_at DESC",
        (org_id,),
    ).fetchall()]


@router.post("/departments", status_code=201)
async def create_department_route(
    name: str = Body(embed=True), vg_admin: str | None = Cookie(default=None),
) -> dict[str, str]:
    org_id = require_company(vg_admin)
    conn = get_conn()
    if conn.execute(
        "SELECT 1 FROM departments WHERE org_id = %s AND name = %s", (org_id, name)
    ).fetchone():
        raise HTTPException(status_code=409, detail="department already exists")
    dept_id = uuid.uuid4().hex
    plain, hashed = new_token(name[:3])
    conn.execute(
        "INSERT INTO departments (id, org_id, name, admin_token_hash, created_at)"
        " VALUES (%s, %s, %s, %s, %s)",
        (dept_id, org_id, name, hashed, now_iso()),
    )
    conn.commit()
    # departments is never read by read_policy() -- no version bump.
    return {"id": dept_id, "name": name, "secret": plain}


@router.post("/departments/{dept_id}/regenerate")
async def regenerate_department(
    dept_id: str, vg_admin: str | None = Cookie(default=None),
) -> dict[str, str]:
    org_id = require_company(vg_admin)
    conn = get_conn()
    plain, hashed = new_token("DEP")
    cur = conn.execute(
        "UPDATE departments SET admin_token_hash = %s WHERE id = %s AND org_id = %s",
        (hashed, dept_id, org_id),
    )
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="unknown department")
    # Old secret is now dead; also drop any live sessions opened with it.
    conn.execute("DELETE FROM admin_sessions WHERE department_id = %s", (dept_id,))
    conn.commit()
    return {"id": dept_id, "secret": plain}


@router.get("/tools")
async def list_tools(vg_admin: str | None = Cookie(default=None)) -> list[dict]:
    org_id = require_company(vg_admin)
    return [dict(r) for r in get_conn().execute(
        "SELECT r.id AS llm_id, r.host, r.display_name, p.status, p.access_mode, p.expires_at"
        " FROM llm_registry r JOIN org_llm_policy p ON p.llm_id = r.id"
        " WHERE p.org_id = %s ORDER BY r.display_name",
        (org_id,),
    ).fetchall()]


@router.post("/tools", status_code=201)
async def create_tool(
    host: str = Body(embed=True),
    display_name: str = Body(embed=True),
    status: str = Body(default="approved", embed=True),
    access_mode: str = Body(default="standard", embed=True),
    vg_admin: str | None = Cookie(default=None),
) -> dict:
    import re
    org_id = require_company(vg_admin)
    if status not in ("approved", "blocked", "temporary", "trial", "conditional"):
        raise HTTPException(status_code=422, detail="invalid status")
    if access_mode not in ("standard", "strict_redaction", "no_file_uploads"):
        raise HTTPException(status_code=422, detail="invalid access_mode")

    clean_host = host.strip().lower()
    if clean_host.startswith("http://"):
        clean_host = clean_host[7:]
    elif clean_host.startswith("https://"):
        clean_host = clean_host[8:]
    clean_host = clean_host.split('/')[0].strip()

    clean_name = display_name.strip()
    if not clean_host or not clean_name:
        raise HTTPException(status_code=422, detail="host and display_name are required")

    conn = get_conn()
    existing = conn.execute("SELECT id FROM llm_registry WHERE host = %s", (clean_host,)).fetchone()
    if existing:
        llm_id = existing["id"]
        conn.execute("UPDATE llm_registry SET display_name = %s WHERE id = %s", (clean_name, llm_id))
    else:
        slug = re.sub(r"[^a-z0-9]", "_", clean_host)
        llm_id = f"tool_{slug}" if slug else uuid.uuid4().hex[:12]
        if conn.execute("SELECT 1 FROM llm_registry WHERE id = %s", (llm_id,)).fetchone():
            llm_id = f"tool_{uuid.uuid4().hex[:8]}"
        conn.execute(
            "INSERT INTO llm_registry (id, host, display_name) VALUES (%s, %s, %s)",
            (llm_id, clean_host, clean_name),
        )

    conn.execute(
        "INSERT INTO org_llm_policy (org_id, llm_id, status, access_mode) VALUES (%s, %s, %s, %s)"
        " ON CONFLICT (org_id, llm_id) DO UPDATE SET status = EXCLUDED.status, access_mode = EXCLUDED.access_mode",
        (org_id, llm_id, status, access_mode),
    )
    conn.commit()
    version = bump_policy_version(conn, org_id)
    return {
        "llm_id": llm_id,
        "host": clean_host,
        "display_name": clean_name,
        "status": status,
        "access_mode": access_mode,
        "version": version,
    }


@router.post("/tools/{llm_id}")
@router.put("/tools/{llm_id}")
async def set_tool(
    llm_id: str,
    status: str = Body(default="approved", embed=True),
    access_mode: str = Body(default="standard", embed=True),
    host: str | None = Body(default=None, embed=True),
    display_name: str | None = Body(default=None, embed=True),
    duration_days: int | None = Body(default=None, embed=True),
    expires_at: str | None = Body(default=None, embed=True),
    vg_admin: str | None = Cookie(default=None),
) -> dict:
    from datetime import datetime, timedelta, timezone

    org_id = require_company(vg_admin)
    if status not in ("approved", "blocked", "temporary", "trial", "conditional"):
        raise HTTPException(status_code=422, detail="invalid status")
    if access_mode not in ("standard", "strict_redaction", "no_file_uploads"):
        raise HTTPException(status_code=422, detail="invalid access_mode")

    final_expires_at = None
    if duration_days:
        final_expires_at = (datetime.now(timezone.utc) + timedelta(days=duration_days)).isoformat()
    elif expires_at:
        final_expires_at = expires_at

    conn = get_conn()
    tool_row = conn.execute("SELECT id, host, display_name FROM llm_registry WHERE id = %s", (llm_id,)).fetchone()
    if not tool_row:
        raise HTTPException(status_code=404, detail="unknown tool")

    if host is not None or display_name is not None:
        new_host = tool_row["host"]
        if host is not None:
            clean_host = host.strip().lower()
            if clean_host.startswith("http://"):
                clean_host = clean_host[7:]
            elif clean_host.startswith("https://"):
                clean_host = clean_host[8:]
            clean_host = clean_host.split('/')[0].strip()
            if not clean_host:
                raise HTTPException(status_code=422, detail="invalid host")
            dup = conn.execute("SELECT id FROM llm_registry WHERE host = %s AND id != %s", (clean_host, llm_id)).fetchone()
            if dup:
                raise HTTPException(status_code=409, detail="host already exists in registry")
            new_host = clean_host

        new_name = tool_row["display_name"]
        if display_name is not None:
            clean_name = display_name.strip()
            if not clean_name:
                raise HTTPException(status_code=422, detail="invalid display_name")
            new_name = clean_name

        conn.execute(
            "UPDATE llm_registry SET host = %s, display_name = %s WHERE id = %s",
            (new_host, new_name, llm_id),
        )

    cur = conn.execute(
        "UPDATE org_llm_policy SET status = %s, access_mode = %s, expires_at = %s WHERE org_id = %s AND llm_id = %s",
        (status, access_mode, final_expires_at, org_id, llm_id),
    )
    if cur.rowcount == 0:
        conn.execute(
            "INSERT INTO org_llm_policy (org_id, llm_id, status, access_mode, expires_at)"
            " VALUES (%s, %s, %s, %s, %s)",
            (org_id, llm_id, status, access_mode, final_expires_at),
        )
    conn.commit()
    return {"version": bump_policy_version(conn, org_id)}



@router.get("/requests")
async def list_requests(vg_admin: str | None = Cookie(default=None)) -> list[dict]:
    """Company-wide oversight, read-only. Deciding a request is a department
    action now (`POST /v1/dept/requests/{request_id}` -- app/routes/dept.py);
    the company dashboard can see every department's queue but cannot act on it."""
    org_id = require_company(vg_admin)
    return [dict(r) for r in get_conn().execute(
        "SELECT a.id, a.reason, a.status, a.access_mode, a.expires_at, a.reason_code, a.admin_note, a.created_at, e.department,"
        "       CASE WHEN a.status IN ('approved','temporary','trial','conditional') THEN a.status ELSE 'blocked' END AS access_state,"
        "       r.display_name, r.host, a.llm_id"
        " FROM access_requests a"
        " JOIN employees e ON e.id = a.employee_id"
        " JOIN llm_registry r ON r.id = a.llm_id"
        " WHERE a.org_id = %s ORDER BY a.created_at DESC",
        (org_id,),
    ).fetchall()]


@router.post("/requests/{request_id}")
async def admin_decide_request(
    request_id: str, body: AccessDecision,
    vg_admin: str | None = Cookie(default=None),
) -> dict[str, int | str]:
    from datetime import datetime, timedelta, timezone

    org_id = require_company(vg_admin)
    conn = get_conn()
    row = conn.execute(
        "SELECT a.llm_id, a.employee_id, r.display_name, e.department_id FROM access_requests a"
        " JOIN employees e ON e.id = a.employee_id"
        " LEFT JOIN llm_registry r ON r.id = a.llm_id"
        " WHERE a.id = %s AND a.org_id = %s AND a.status = 'pending'",
        (request_id, org_id),
    ).fetchone()
    if row is None:
        exists = conn.execute(
            "SELECT 1 FROM access_requests a"
            " WHERE a.id = %s AND a.org_id = %s",
            (request_id, org_id),
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
            (org_id, row["department_id"], row["llm_id"], body.decision, body.access_mode, expires_at),
        )
        return {"version": bump_policy_version(conn, org_id), "access_state": body.decision}

    conn.execute(
        "INSERT INTO dept_llm_policy (org_id, department_id, llm_id, status, access_mode, expires_at)"
        " VALUES (%s, %s, %s, 'blocked', 'standard', NULL)"
        " ON CONFLICT (department_id, llm_id) DO UPDATE SET status = 'blocked',"
        " access_mode = 'standard', expires_at = NULL",
        (org_id, row["department_id"], row["llm_id"]),
    )
    conn.commit()
    return {"version": bump_policy_version(conn, org_id), "access_state": "blocked"}


@router.get("/appeals")
async def list_appeals(vg_admin: str | None = Cookie(default=None)) -> list[dict]:
    """Company-wide oversight, read-only -- see `list_requests` above; the
    decide route is `POST /v1/dept/appeals/{appeal_id}` (app/routes/dept.py)."""
    org_id = require_company(vg_admin)
    return [dict(r) for r in get_conn().execute(
        "SELECT a.id, a.decision_type, a.category, a.employee_reason, a.disclosed_text,"
        "       a.status, a.reason_code, a.admin_note, a.created_at, e.department,"
        "       CASE WHEN a.status = 'approved' THEN 'approved' ELSE 'blocked' END AS access_state"
        " FROM decision_appeals a"
        " JOIN employees e ON e.id = a.employee_id"
        " WHERE a.org_id = %s ORDER BY a.created_at DESC",
        (org_id,),
    ).fetchall()]


@router.get("/usage")
async def usage(vg_admin: str | None = Cookie(default=None)) -> dict[str, list[dict]]:
    org_id = require_company(vg_admin)
    conn = get_conn()
    by_department = [dict(r) for r in conn.execute(
        "SELECT e.department, COUNT(*) AS events"
        " FROM usage_events u JOIN employees e ON e.id = u.employee_id"
        " WHERE u.org_id = %s GROUP BY e.department ORDER BY events DESC",
        (org_id,),
    ).fetchall()]
    by_tool = [dict(r) for r in conn.execute(
        "SELECT host, COUNT(*) AS events FROM usage_events"
        " WHERE org_id = %s GROUP BY host ORDER BY events DESC",
        (org_id,),
    ).fetchall()]
    by_category = [dict(r) for r in conn.execute(
        "SELECT category, COUNT(*) AS events FROM usage_events"
        " WHERE org_id = %s AND category IS NOT NULL"
        " GROUP BY category ORDER BY events DESC",
        (org_id,),
    ).fetchall()]
    return {"by_department": by_department, "by_tool": by_tool, "by_category": by_category}


def _days(days: int) -> int:
    return 30 if int(days) == 30 else 7


@router.get("/analytics/summary")
async def admin_analytics_summary(
    days: int = 7, vg_admin: str | None = Cookie(default=None)
) -> dict:
    org_id = require_company(vg_admin)
    return analytics_summary(get_conn(), org_id, _days(days), None)


@router.get("/analytics/alerts")
async def admin_analytics_alerts(
    limit: int = 50, vg_admin: str | None = Cookie(default=None)
) -> list[dict]:
    org_id = require_company(vg_admin)
    return analytics_alerts(get_conn(), org_id, min(max(int(limit), 1), 200), None)
