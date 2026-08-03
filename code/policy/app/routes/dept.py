"""Department dashboard API. Every route is scoped to the session's
department_id -- a department admin can only ever see and act on its own
department's employees, requests, appeals, and tokens."""
import uuid

from fastapi import APIRouter, Body, Cookie, HTTPException

from app.authz import require_department
from app.db import bump_policy_version
from app.deps import get_conn
from app.models import AppealDecision
from app.security import new_token, now_iso

router = APIRouter(prefix="/v1/dept")


def _current_version(conn, org_id: str) -> int:
    return int(conn.execute(
        "SELECT policy_version FROM orgs WHERE id = ?", (org_id,)
    ).fetchone()["policy_version"])


@router.get("/requests")
async def dept_requests(vg_admin: str | None = Cookie(default=None)) -> list[dict]:
    org_id, dept_id = require_department(vg_admin)
    return [dict(r) for r in get_conn().execute(
        "SELECT a.id, a.reason, a.status, a.created_at, e.department,"
        "       r.display_name, r.host, a.llm_id"
        " FROM access_requests a"
        " JOIN employees e ON e.id = a.employee_id"
        " JOIN llm_registry r ON r.id = a.llm_id"
        " WHERE a.org_id = ? AND e.department_id = ? ORDER BY a.created_at DESC",
        (org_id, dept_id),
    )]


@router.post("/requests/{request_id}")
async def dept_decide_request(
    request_id: str, decision: str = Body(embed=True),
    vg_admin: str | None = Cookie(default=None),
) -> dict[str, int]:
    org_id, dept_id = require_department(vg_admin)
    if decision not in ("approved", "denied"):
        raise HTTPException(status_code=422, detail="decision must be approved or denied")
    conn = get_conn()
    row = conn.execute(
        "SELECT a.llm_id FROM access_requests a JOIN employees e ON e.id = a.employee_id"
        " WHERE a.id = ? AND a.org_id = ? AND e.department_id = ? AND a.status = 'pending'",
        (request_id, org_id, dept_id),
    ).fetchone()
    if row is None:
        exists = conn.execute(
            "SELECT 1 FROM access_requests a JOIN employees e ON e.id = a.employee_id"
            " WHERE a.id = ? AND a.org_id = ? AND e.department_id = ?",
            (request_id, org_id, dept_id),
        ).fetchone()
        raise HTTPException(status_code=404 if exists is None else 409,
                            detail="unknown request" if exists is None else "request already decided")

    conn.execute(
        "UPDATE access_requests SET status = ?, decided_at = ? WHERE id = ?",
        (decision, now_iso(), request_id),
    )
    if decision == "approved":
        conn.execute(
            "INSERT INTO dept_llm_policy (org_id, department_id, llm_id, status)"
            " VALUES (?, ?, ?, 'approved')"
            " ON CONFLICT(department_id, llm_id) DO UPDATE SET status = 'approved'",
            (org_id, dept_id, row["llm_id"]),
        )
        return {"version": bump_policy_version(conn, org_id)}
    conn.commit()
    return {"version": _current_version(conn, org_id)}
