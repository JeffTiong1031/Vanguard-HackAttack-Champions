"""Admin API.

Authority is decided HERE, server-side, on every request. The console is a
view; it never adjudicates whether its user is an admin. A client-side admin
check is bypassed with devtools in under a minute and would ship a control
whose audit trail claims it worked -- doc 00 section 6's worst case.

Every route below except /login calls `_require_admin`, including /logout:
logout still needs to resolve an org_id to know which session row to delete,
and a blanket "every admin endpoint" rule is easier to hold to if there is no
carved-out exception to remember. Login is the one legitimate exception --
it is how a session is obtained in the first place, so it cannot itself
require one.

Policy-version bumps: `POST /tools/{llm_id}` and an *approved* decision on
`POST /requests/{request_id}` change what `org_llm_policy` holds, which is
exactly what `GET /v1/policy` serialises -- so both call
`bump_policy_version`. Minting and revoking enrolment tokens touch
`enroll_tokens`, a table `read_policy()` never reads, so a currently-enrolled
extension's view is unchanged either way -- no bump, and said so at each call
site rather than left to be inferred. A *denied* decision is reasoned through
at `decide_request` below, not assumed.
"""
import uuid

from fastapi import APIRouter, Body, Cookie, HTTPException, Response

from app.authz import require_company
from app.db import bump_policy_version
from app.deps import get_conn
from app.models import AdminLogin, AppealDecision
from app.security import hash_token, issue_session, new_token, now_iso, session_org

router = APIRouter(prefix="/v1/admin")
SESSION_COOKIE = "vg_admin"


def _require_admin(session: str | None) -> str:
    org_id = session_org(get_conn(), session)
    if org_id is None:
        raise HTTPException(status_code=401, detail="admin session required")
    return org_id


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
    org_id = _require_admin(vg_admin)
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
    org_id = _require_admin(vg_admin)
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


@router.get("/tokens")
async def list_tokens(vg_admin: str | None = Cookie(default=None)) -> list[dict]:
    """Never returns plaintext. The token is shown once, at mint time."""
    org_id = _require_admin(vg_admin)
    return [dict(r) for r in get_conn().execute(
        "SELECT id, department, label, created_at, revoked FROM enroll_tokens"
        " WHERE org_id = ? ORDER BY created_at DESC",
        (org_id,),
    )]


@router.post("/tokens", status_code=201)
async def mint_token(
    department: str = Body(embed=True),
    vg_admin: str | None = Cookie(default=None),
) -> dict[str, str]:
    org_id = _require_admin(vg_admin)
    plain, hashed = new_token(department[:3])
    token_id = uuid.uuid4().hex
    conn = get_conn()
    conn.execute(
        "INSERT INTO enroll_tokens (id, org_id, department, token_hash, label, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (token_id, org_id, department, hashed, department, now_iso()),
    )
    conn.commit()
    # enroll_tokens is never read by read_policy() -- an already-enrolled
    # extension's policy view is unaffected. No bump.
    return {"id": token_id, "department": department, "token": plain}


@router.post("/tokens/{token_id}/revoke")
async def revoke_token(token_id: str, vg_admin: str | None = Cookie(default=None)) -> dict[str, bool]:
    """Revoke an enrolment token to prevent FUTURE enrolments.

    Revoking a token marks it as revoked in the database, preventing new
    employees from enrolling with that token. However, this endpoint does NOT
    deprovisioning employees who already enrolled with the token -- employees
    are keyed by (org_id, pseudo_id) and have no foreign key back to
    enroll_tokens, so they continue polling indefinitely.

    For a compliance product where "revoke" typically means cutting off access,
    this is a gap. A real deprovisioning feature would require:
    - A per-employee revocation mechanism to mark specific (org_id, pseudo_id)
      pairs as inactive.
    - A policy change so polling against a revoked employee returns a distinct
      status signaling their access is cut.

    For Phase 0 (demo), this limitation is acceptable; it must not be silent.
    """
    org_id = _require_admin(vg_admin)
    conn = get_conn()
    conn.execute(
        "UPDATE enroll_tokens SET revoked = 1 WHERE id = ? AND org_id = ?",
        (token_id, org_id),
    )
    conn.commit()
    # Same reasoning as mint_token: enroll_tokens is outside read_policy()'s
    # reach, so a currently-enrolled extension sees no difference. No bump.
    return {"ok": True}


@router.get("/requests")
async def list_requests(vg_admin: str | None = Cookie(default=None)) -> list[dict]:
    org_id = _require_admin(vg_admin)
    return [dict(r) for r in get_conn().execute(
        "SELECT a.id, a.reason, a.status, a.created_at, e.department,"
        "       r.display_name, r.host, a.llm_id"
        " FROM access_requests a"
        " JOIN employees e ON e.id = a.employee_id"
        " JOIN llm_registry r ON r.id = a.llm_id"
        " WHERE a.org_id = ? ORDER BY a.created_at DESC",
        (org_id,),
    )]


@router.post("/requests/{request_id}")
async def decide_request(
    request_id: str,
    decision: str = Body(embed=True),
    vg_admin: str | None = Cookie(default=None),
) -> dict[str, int]:
    org_id = _require_admin(vg_admin)
    if decision not in ("approved", "denied"):
        raise HTTPException(status_code=422, detail="decision must be approved or denied")
    conn = get_conn()
    row = conn.execute(
        "SELECT llm_id FROM access_requests WHERE id = ? AND org_id = ? AND status = 'pending'",
        (request_id, org_id),
    ).fetchone()
    if row is None:
        # Distinguish "no such request" (404) from "exists, already decided"
        # (409) -- the console is a view, so the server must not silently
        # accept a re-decision the client merely declined to offer. A denied
        # request re-posted as "approved" must not flip, and a decided
        # request re-posted with the SAME decision must not double-bump.
        exists = conn.execute(
            "SELECT 1 FROM access_requests WHERE id = ? AND org_id = ?",
            (request_id, org_id),
        ).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail="unknown request")
        raise HTTPException(status_code=409, detail="request already decided")

    conn.execute(
        "UPDATE access_requests SET status = ?, decided_at = ?"
        " WHERE id = ? AND org_id = ? AND status = 'pending'",
        (decision, now_iso(), request_id, org_id),
    )
    if decision == "approved":
        conn.execute(
            "UPDATE org_llm_policy SET status = 'approved'"
            " WHERE org_id = ? AND llm_id = ?",
            (org_id, row["llm_id"]),
        )
    conn.commit()

    # A denial never touches org_llm_policy -- read_policy() serves the same
    # tools/categories body before and after, so the ETag it is keyed on must
    # not move. Only an approval changes org_llm_policy, so only an approval
    # bumps. (If a future change lets a denial affect anything read_policy()
    # serves -- e.g. a per-tool denial counter surfaced to the client -- this
    # exemption needs to be revisited alongside it.)
    version = bump_policy_version(conn, org_id) if decision == "approved" else conn.execute(
        "SELECT policy_version FROM orgs WHERE id = ?", (org_id,)
    ).fetchone()["policy_version"]
    return {"version": int(version)}


@router.get("/appeals")
async def list_appeals(vg_admin: str | None = Cookie(default=None)) -> list[dict]:
    org_id = _require_admin(vg_admin)
    return [dict(r) for r in get_conn().execute(
        "SELECT a.id, a.decision_type, a.category, a.employee_reason, a.disclosed_text,"
        "       a.status, a.admin_note, a.created_at, e.department"
        " FROM decision_appeals a"
        " JOIN employees e ON e.id = a.employee_id"
        " WHERE a.org_id = ? ORDER BY a.created_at DESC",
        (org_id,),
    )]


@router.post("/appeals/{appeal_id}")
async def decide_appeal(
    appeal_id: str,
    body: AppealDecision,
    vg_admin: str | None = Cookie(default=None),
) -> dict[str, str]:
    org_id = _require_admin(vg_admin)
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM decision_appeals WHERE id = ? AND org_id = ? AND status = 'pending'",
        (appeal_id, org_id),
    ).fetchone()
    if row is None:
        # Same 404-vs-409 split as decide_request: a decided appeal must not be
        # silently re-decided just because the console offered the buttons again.
        exists = conn.execute(
            "SELECT 1 FROM decision_appeals WHERE id = ? AND org_id = ?",
            (appeal_id, org_id),
        ).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail="unknown appeal")
        raise HTTPException(status_code=409, detail="appeal already decided")

    conn.execute(
        "UPDATE decision_appeals SET status = ?, admin_note = ?, decided_at = ?"
        " WHERE id = ? AND org_id = ? AND status = 'pending'",
        (body.decision, body.note, now_iso(), appeal_id, org_id),
    )
    conn.commit()
    return {"status": body.decision}


@router.get("/usage")
async def usage(vg_admin: str | None = Cookie(default=None)) -> dict[str, list[dict]]:
    org_id = _require_admin(vg_admin)
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
