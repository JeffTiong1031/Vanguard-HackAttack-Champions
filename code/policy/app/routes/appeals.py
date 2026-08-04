"""Employee-facing appeals against automated enforcement decisions.

An appeal carries the finding CLASS and the employee's own reason. It carries
prompt text ONLY when the employee ticked the opt-in box in the modal, arriving
here as `disclosed_text`. `AppealCreate` sets extra="forbid", so the prompt
cannot be smuggled under any other key -- I3 holds by construction.
"""
import uuid

from fastapi import APIRouter, HTTPException

from app.deps import get_conn
from app.models import AppealCreate
from app.remediation import get_remediation_guidance
from app.security import now_iso

router = APIRouter()


def _employee(conn, pseudo_id: str):
    emp = conn.execute(
        "SELECT id, org_id FROM employees WHERE pseudo_id = %s", (pseudo_id,)
    ).fetchone()
    if emp is None:
        raise HTTPException(status_code=401, detail="unknown enrolment")
    return emp


@router.post("/v1/appeals", status_code=201)
async def create_appeal(body: AppealCreate) -> dict[str, str]:
    conn = get_conn()
    emp = _employee(conn, body.pseudo_id)

    # Pre-Screen 1: An already approved scope fingerprint requires no manual review.
    if body.scope_fingerprint:
        approved_scope = conn.execute(
            "SELECT id FROM decision_appeals"
            " WHERE employee_id = %s AND scope_fingerprint = %s AND status = 'approved'",
            (emp["id"], body.scope_fingerprint),
        ).fetchone()
        if approved_scope:
            return {
                "id": approved_scope["id"],
                "status": "approved",
                "access_state": "approved",
                "pre_screen": "already_approved",
            }

    # Pre-Screen 2: Deduplicate pending appeals for identical scope/category.
    if body.scope_fingerprint:
        existing = conn.execute(
            "SELECT id FROM decision_appeals"
            " WHERE employee_id = %s AND scope_fingerprint = %s AND status = 'pending'",
            (emp["id"], body.scope_fingerprint),
        ).fetchone()
    else:
        existing = conn.execute(
            "SELECT id FROM decision_appeals"
            " WHERE employee_id = %s AND decision_type = %s AND category = %s AND status = 'pending'",
            (emp["id"], body.decision_type, body.category),
        ).fetchone()

    if existing:
        return {
            "id": existing["id"],
            "status": "pending",
            "access_state": "blocked",
            "pre_screen": "duplicate",
        }

    appeal_id = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO decision_appeals"
        " (id, org_id, employee_id, decision_type, category, employee_reason,"
        "  disclosed_text, scope_fingerprint, status, created_at)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s)",
        (appeal_id, emp["org_id"], emp["id"], body.decision_type, body.category,
         body.reason, body.disclosed_text, body.scope_fingerprint, now_iso()),
    )
    conn.commit()
    return {
        "id": appeal_id,
        "status": "pending",
        "access_state": "blocked",
        "pre_screen": "ready_for_review",
    }


@router.get("/v1/appeals/approved-scopes")
async def list_approved_scopes(pseudo_id: str) -> list[str]:
    """Persistent scopes approved by a final binary decision.

    These approvals are neither consumed nor expired. Changed content has a
    different fingerprint and therefore starts blocked as a new scope.
    """
    conn = get_conn()
    emp = _employee(conn, pseudo_id)
    return [r["scope_fingerprint"] for r in conn.execute(
        "SELECT scope_fingerprint FROM decision_appeals"
        " WHERE employee_id = %s AND status = 'approved'"
        "   AND scope_fingerprint IS NOT NULL",
        (emp["id"],),
    ).fetchall()]


@router.get("/v1/appeals")
async def list_my_appeals(pseudo_id: str) -> list[dict]:
    """The caller's OWN appeals only with remediation guidance for blocked states."""
    conn = get_conn()
    emp = conn.execute(
        "SELECT id FROM employees WHERE pseudo_id = %s", (pseudo_id,)
    ).fetchone()
    if emp is None:
        raise HTTPException(status_code=401, detail="unknown enrolment")
    
    rows = conn.execute(
        "SELECT id, decision_type, category, status, reason_code, admin_note, created_at, decided_at,"
        " CASE WHEN status = 'approved' THEN 'approved' ELSE 'blocked' END AS access_state,"
        " CASE WHEN status = 'pending' THEN 'in_review' ELSE 'decided' END AS request_state"
        " FROM decision_appeals WHERE employee_id = %s ORDER BY created_at DESC",
        (emp["id"],),
    ).fetchall()

    res = []
    for r in rows:
        item = dict(r)
        if item["access_state"] == "blocked":
            item["remediation_guidance"] = get_remediation_guidance(item["reason_code"], item["category"])
        res.append(item)
    return res

