import pytest
from fastapi import HTTPException

from app import authz
from app.deps import get_conn
from app.security import issue_session, resolve_session


def _org() -> str:
    from app.seed import seed_company           # Task 4
    org_id, _secret = seed_company(get_conn(), "Authz Co")
    return org_id


def test_company_session_resolves_and_authorizes():
    conn = get_conn()
    org_id = _org()
    token = issue_session(conn, org_id, "company", None)
    row = resolve_session(conn, token)
    assert row["role"] == "company" and row["org_id"] == org_id
    assert authz.require_company(token) == org_id
    with pytest.raises(HTTPException) as e:
        authz.require_department(token)
    assert e.value.status_code == 403


def test_department_session_carries_department_id():
    conn = get_conn()
    org_id = _org()
    token = issue_session(conn, org_id, "department", "dept-123")
    assert authz.require_department(token) == (org_id, "dept-123")
    with pytest.raises(HTTPException) as e:
        authz.require_company(token)
    assert e.value.status_code == 403


def test_no_session_is_401():
    with pytest.raises(HTTPException) as e:
        authz.require_company(None)
    assert e.value.status_code == 401
