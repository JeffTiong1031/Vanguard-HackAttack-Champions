from fastapi import APIRouter, Header, HTTPException, Response

from app.deps import get_conn
from app.enrolment import enrolment_is_revoked
from app.models import PolicyBody
from app.routes.policy_read import read_policy

router = APIRouter()


def _etag(org_id: str, department_id: str | None, version: int) -> str:
    return f'W/"{org_id}-{department_id or "_"}-{version}"'


@router.get("/v1/policy", response_model=PolicyBody)
async def get_policy(
    org_id: str,
    response: Response,
    if_none_match: str | None = Header(default=None),
    department_id: str | None = None,
    pseudo_id: str | None = None,
):
    """Return the org's policy, or 304 if the caller already has this version.

    The ETag is the org's policy_version (plus the department_id, since the
    effective policy differs by department), so any write that calls
    bump_policy_version() invalidates every client's cache on its next poll.

    `pseudo_id` is optional so an older extension build that never sends it
    keeps working (backwards compatible) — it just skips the revocation
    check.
    """
    conn = get_conn()
    if pseudo_id and enrolment_is_revoked(conn, pseudo_id):
        raise HTTPException(status_code=403, detail="enrolment revoked")

    row = conn.execute(
        "SELECT policy_version FROM orgs WHERE id = %s", (org_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="unknown org")

    tag = _etag(org_id, department_id, int(row["policy_version"]))
    if if_none_match == tag:
        return Response(status_code=304, headers={"ETag": tag})

    response.headers["ETag"] = tag
    return read_policy(conn, org_id, department_id)
