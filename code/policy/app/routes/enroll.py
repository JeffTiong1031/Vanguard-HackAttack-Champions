import uuid

from fastapi import APIRouter, HTTPException

from app.deps import get_conn
from app.enrolment import employee_for_token
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
        "SELECT id, org_id, department, department_id, name FROM enroll_tokens"
        " WHERE token_hash = %s AND revoked = 0",
        (hash_token(body.token),),
    ).fetchone()
    if row is None:
        # Log the failure, never the token.
        raise HTTPException(status_code=401, detail="enrolment token not recognised")

    existing = employee_for_token(conn, row["id"])
    if existing:
        # A reinstall. Hand back the same identity so history does not split.
        pseudo_id = existing["pseudo_id"]
    else:
        employee_id, pseudo_id = uuid.uuid4().hex, uuid.uuid4().hex
        cur = conn.execute(
            "INSERT INTO employees"
            " (id, org_id, pseudo_id, department, department_id, name, created_at, enroll_token_id)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (enroll_token_id) DO NOTHING",
            (employee_id, row["org_id"], pseudo_id, row["department"],
             row["department_id"], row["name"], now_iso(), row["id"]),
        )
        conn.commit()
        if cur.rowcount == 0:
            # Lost a concurrent race for this token: another request's INSERT
            # won under the unique index. Hand back the winner's identity so
            # both callers agree on one pseudo_id instead of erroring or
            # silently minting a second person.
            winner = employee_for_token(conn, row["id"])
            pseudo_id = winner["pseudo_id"]

    policy = read_policy(conn, row["org_id"], row["department_id"])
    return EnrollResponse(
        org_id=row["org_id"], org_name=policy.org_name, pseudo_id=pseudo_id,
        department=row["department"], department_id=row["department_id"], policy=policy,
    )
