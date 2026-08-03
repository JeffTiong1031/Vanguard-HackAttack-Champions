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

from app.authz import require_company
from app.db import bump_policy_version
from app.deps import get_conn
from app.models import AdminLogin
from app.security import hash_token, issue_session, new_token, now_iso

router = APIRouter(prefix="/v1/admin")
SESSION_COOKIE = "vg_admin"


@router.post("/login")
async def login(body: AdminLogin, response: Response) -> dict[str, str]:
    conn = get_conn()
    h = hash_token(body.secret)
    if body.role == "company":
        row = conn.execute(
            "SELECT id, name FROM orgs WHERE admin_token_hash = ?", (h,)
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
        " WHERE d.admin_token_hash = ?", (h,)
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
    get_conn().execute("DELETE FROM admin_sessions WHERE token = ?", (vg_admin,))
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
        " FROM departments d WHERE d.org_id = ? ORDER BY d.created_at DESC",
        (org_id,),
    )]


@router.post("/departments", status_code=201)
async def create_department_route(
    name: str = Body(embed=True), vg_admin: str | None = Cookie(default=None),
) -> dict[str, str]:
    org_id = require_company(vg_admin)
    conn = get_conn()
    if conn.execute(
        "SELECT 1 FROM departments WHERE org_id = ? AND name = ?", (org_id, name)
    ).fetchone():
        raise HTTPException(status_code=409, detail="department already exists")
    dept_id = uuid.uuid4().hex
    plain, hashed = new_token(name[:3])
    conn.execute(
        "INSERT INTO departments (id, org_id, name, admin_token_hash, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
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
        "UPDATE departments SET admin_token_hash = ? WHERE id = ? AND org_id = ?",
        (hashed, dept_id, org_id),
    )
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="unknown department")
    # Old secret is now dead; also drop any live sessions opened with it.
    conn.execute("DELETE FROM admin_sessions WHERE department_id = ?", (dept_id,))
    conn.commit()
    return {"id": dept_id, "secret": plain}


@router.get("/tools")
async def list_tools(vg_admin: str | None = Cookie(default=None)) -> list[dict]:
    org_id = require_company(vg_admin)
    return [dict(r) for r in get_conn().execute(
        "SELECT r.id AS llm_id, r.host, r.display_name, p.status"
        " FROM llm_registry r JOIN org_llm_policy p ON p.llm_id = r.id"
        " WHERE p.org_id = ? ORDER BY r.display_name",
        (org_id,),
    )]


@router.post("/tools/{llm_id}")
async def set_tool(
    llm_id: str,
    status: str = Body(embed=True),
    vg_admin: str | None = Cookie(default=None),
) -> dict[str, int]:
    org_id = require_company(vg_admin)
    if status not in ("approved", "blocked"):
        raise HTTPException(status_code=422, detail="status must be approved or blocked")
    conn = get_conn()
    cur = conn.execute(
        "UPDATE org_llm_policy SET status = ? WHERE org_id = ? AND llm_id = ?",
        (status, org_id, llm_id),
    )
    if cur.rowcount == 0:
        # No row matched -- either llm_id doesn't exist or this org has no
        # policy row for it. Either way nothing changed, so nothing to
        # commit and nothing to bump: a no-op write must not look like one.
        raise HTTPException(status_code=404, detail="unknown tool")
    conn.commit()
    # Changes what GET /v1/policy serves for this org -- bump.
    return {"version": bump_policy_version(conn, org_id)}


@router.get("/requests")
async def list_requests(vg_admin: str | None = Cookie(default=None)) -> list[dict]:
    """Company-wide oversight, read-only. Deciding a request is a department
    action now (`POST /v1/dept/requests/{request_id}` -- app/routes/dept.py);
    the company dashboard can see every department's queue but cannot act on it."""
    org_id = require_company(vg_admin)
    return [dict(r) for r in get_conn().execute(
        "SELECT a.id, a.reason, a.status, a.created_at, e.department,"
        "       r.display_name, r.host, a.llm_id"
        " FROM access_requests a"
        " JOIN employees e ON e.id = a.employee_id"
        " JOIN llm_registry r ON r.id = a.llm_id"
        " WHERE a.org_id = ? ORDER BY a.created_at DESC",
        (org_id,),
    )]


@router.get("/appeals")
async def list_appeals(vg_admin: str | None = Cookie(default=None)) -> list[dict]:
    """Company-wide oversight, read-only -- see `list_requests` above; the
    decide route is `POST /v1/dept/appeals/{appeal_id}` (app/routes/dept.py)."""
    org_id = require_company(vg_admin)
    return [dict(r) for r in get_conn().execute(
        "SELECT a.id, a.decision_type, a.category, a.employee_reason, a.disclosed_text,"
        "       a.status, a.admin_note, a.created_at, e.department"
        " FROM decision_appeals a"
        " JOIN employees e ON e.id = a.employee_id"
        " WHERE a.org_id = ? ORDER BY a.created_at DESC",
        (org_id,),
    )]


@router.get("/usage")
async def usage(vg_admin: str | None = Cookie(default=None)) -> dict[str, list[dict]]:
    org_id = require_company(vg_admin)
    conn = get_conn()
    by_department = [dict(r) for r in conn.execute(
        "SELECT e.department, COUNT(*) AS events"
        " FROM usage_events u JOIN employees e ON e.id = u.employee_id"
        " WHERE u.org_id = ? GROUP BY e.department ORDER BY events DESC",
        (org_id,),
    )]
    by_tool = [dict(r) for r in conn.execute(
        "SELECT host, COUNT(*) AS events FROM usage_events"
        " WHERE org_id = ? GROUP BY host ORDER BY events DESC",
        (org_id,),
    )]
    by_category = [dict(r) for r in conn.execute(
        "SELECT category, COUNT(*) AS events FROM usage_events"
        " WHERE org_id = ? AND category IS NOT NULL"
        " GROUP BY category ORDER BY events DESC",
        (org_id,),
    )]
    return {"by_department": by_department, "by_tool": by_tool, "by_category": by_category}
