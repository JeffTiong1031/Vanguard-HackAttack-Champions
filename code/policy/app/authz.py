"""Scoped authorization. Authority is decided server-side on every request.

A company session may reach /v1/admin/* only; a department session may reach
/v1/dept/* only. Role is read from the session row, never from the client."""
from fastapi import HTTPException

from app.deps import get_conn
from app.security import resolve_session


def _session(token: str | None):
    row = resolve_session(get_conn(), token)
    if row is None:
        raise HTTPException(status_code=401, detail="session required")
    return row


def require_company(token: str | None) -> str:
    row = _session(token)
    if row["role"] != "company":
        raise HTTPException(status_code=403, detail="company session required")
    return row["org_id"]


def require_department(token: str | None) -> tuple[str, str]:
    row = _session(token)
    if row["role"] != "department" or row["department_id"] is None:
        raise HTTPException(status_code=403, detail="department session required")
    return row["org_id"], row["department_id"]
