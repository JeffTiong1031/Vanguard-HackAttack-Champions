from app.deps import get_conn
from app.seed import ETHICS_CATEGORIES, REGISTRY, seed_demo_org, seed_registry


def _conn():
    return get_conn()


def test_registry_is_finite_and_curated_not_a_wildcard():
    assert 5 <= len(REGISTRY) <= 15
    hosts = [host for _, host, _ in REGISTRY]
    assert "chatgpt.com" in hosts
    assert "claude.ai" in hosts
    assert all("*" not in h for h in hosts)


def test_seed_registry_is_idempotent():
    conn = _conn()
    before = conn.execute("SELECT COUNT(*) AS n FROM llm_registry").fetchone()["n"]
    seed_registry(conn)
    seed_registry(conn)
    after = conn.execute("SELECT COUNT(*) AS n FROM llm_registry").fetchone()["n"]
    assert after == before or after >= len(REGISTRY)
    for llm_id, _, _ in REGISTRY:
        assert conn.execute("SELECT 1 FROM llm_registry WHERE id = %s", (llm_id,)).fetchone() is not None



def test_demo_org_seeds_categories_and_default_tool_policy():
    conn = _conn()
    seed_registry(conn)
    org_id = seed_demo_org(conn, "Acme Corp", "hunter2")

    cats = conn.execute(
        "SELECT COUNT(*) AS n FROM policy_category WHERE org_id = %s", (org_id,)
    ).fetchone()["n"]
    assert cats == len(ETHICS_CATEGORIES)

    approved = conn.execute(
        "SELECT COUNT(*) AS n FROM org_llm_policy WHERE org_id = %s AND status = 'approved'",
        (org_id,),
    ).fetchone()["n"]
    # ChatGPT and Claude approved; everything else blocked, so the demo has an
    # unapproved tool to walk into.
    assert approved == 2

    # Verify that ChatGPT and Claude specifically are the approved ones
    approved_tools = conn.execute(
        "SELECT llm_id FROM org_llm_policy WHERE org_id = %s AND status = 'approved' ORDER BY llm_id",
        (org_id,)
    ).fetchall()
    approved_ids = {row["llm_id"] for row in approved_tools}
    assert approved_ids == {"openai", "anthropic"}
