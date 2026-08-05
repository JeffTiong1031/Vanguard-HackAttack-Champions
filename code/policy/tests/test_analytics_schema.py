"""Analytics schema tests — Postgres / information_schema version."""
from app.deps import get_conn


def test_name_columns_exist():
    conn = get_conn()
    def cols(t):
        return {r["column_name"] for r in conn.execute(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_schema = 'public' AND table_name = %s",
            (t,),
        ).fetchall()}
    assert "name" in cols("employees")
    assert "name" in cols("enroll_tokens")
    assert "risk_level" in cols("usage_events")
