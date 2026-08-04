from app.deps import get_conn
from app.seed import seed_company, create_department, mint_employee_token
from app.security import hash_token


def test_seed_company_stores_only_the_hash_and_seeds_policy():
    conn = get_conn()
    org_id, secret = seed_company(conn, "Seedco")
    row = conn.execute("SELECT admin_token_hash FROM orgs WHERE id = %s", (org_id,)).fetchone()
    assert row["admin_token_hash"] == hash_token(secret)
    n = conn.execute("SELECT COUNT(*) c FROM org_llm_policy WHERE org_id = %s", (org_id,)).fetchone()["c"]
    assert n == 8  # one row per registry tool


def test_create_department_and_mint_token_are_linked_by_department_id():
    conn = get_conn()
    org_id, _ = seed_company(conn, "Seedco2")
    dept_id, dsecret = create_department(conn, org_id, "Engineering")
    assert conn.execute("SELECT admin_token_hash FROM departments WHERE id = %s", (dept_id,)).fetchone()["admin_token_hash"] == hash_token(dsecret)
    token = mint_employee_token(conn, org_id, dept_id, "Engineering")
    row = conn.execute("SELECT department_id, department FROM enroll_tokens WHERE token_hash = %s", (hash_token(token),)).fetchone()
    assert row["department_id"] == dept_id and row["department"] == "Engineering"
