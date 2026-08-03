from app.db import connect, init_schema


def test_name_columns_exist():
    conn = connect(":memory:")
    init_schema(conn)
    def cols(t): return {r["name"] for r in conn.execute(f"PRAGMA table_info({t})")}
    assert "name" in cols("employees")
    assert "name" in cols("enroll_tokens")
