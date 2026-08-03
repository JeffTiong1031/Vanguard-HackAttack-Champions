import uuid

from fastapi import APIRouter, HTTPException

from app.deps import get_conn
from app.models import EnrollRequest, EnrollResponse
from app.routes.policy_read import read_policy
from app.security import hash_token, now_iso

router = APIRouter()


@router.post("/v1/enroll", response_model=EnrollResponse)
async def enroll(body: EnrollRequest) -> EnrollResponse:
    """Exchange a department token for a pseudonymous identity plus policy.

    The department comes from the TOKEN, never from the request body, so an
    employee cannot self-declare which department they are in.
    """
    conn = get_conn()
    row = conn.execute(
        "SELECT org_id, department, department_id FROM enroll_tokens"
        " WHERE token_hash = ? AND revoked = 0",
        (hash_token(body.token),),
    ).fetchone()
    if row is None:
        # Log the failure, never the token.
        raise HTTPException(status_code=401, detail="enrolment token not recognised")

    employee_id = uuid.uuid4().hex
    pseudo_id = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO employees (id, org_id, pseudo_id, department, department_id, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (employee_id, row["org_id"], pseudo_id, row["department"], row["department_id"], now_iso()),
    )
    conn.commit()

    policy = read_policy(conn, row["org_id"], row["department_id"])
    return EnrollResponse(
        org_id=row["org_id"], org_name=policy.org_name, pseudo_id=pseudo_id,
        department=row["department"], department_id=row["department_id"], policy=policy,
    )
