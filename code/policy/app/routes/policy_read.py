"""Reading an org's policy. Shared by enrolment and the polling endpoint."""
from app.models import CategoryPolicy, PolicyBody, ToolPolicy


def read_policy(conn, org_id: str, department_id: str | None = None) -> PolicyBody:
    org = conn.execute(
        "SELECT name, policy_version FROM orgs WHERE id = %s", (org_id,)
    ).fetchone()
    if department_id is None:
        tool_rows = conn.execute(
            "SELECT r.id, r.host, r.display_name, p.status"
            " FROM llm_registry r JOIN org_llm_policy p ON p.llm_id = r.id"
            " WHERE p.org_id = %s ORDER BY r.display_name",
            (org_id,),
        ).fetchall()
    else:
        tool_rows = conn.execute(
            "SELECT r.id, r.host, r.display_name,"
            "       COALESCE(dp.status, cp.status) AS status"
            " FROM llm_registry r"
            " JOIN org_llm_policy cp ON cp.llm_id = r.id AND cp.org_id = %s"
            " LEFT JOIN dept_llm_policy dp ON dp.llm_id = r.id AND dp.department_id = %s"
            " ORDER BY r.display_name",
            (org_id, department_id),
        ).fetchall()
    tools = [
        ToolPolicy(
            llm_id=r["id"], host=r["host"],
            display_name=r["display_name"], status=r["status"],
        )
        for r in tool_rows
    ]
    categories = [
        CategoryPolicy(key=r["key"], label=r["label"], enabled=bool(r["enabled"]))
        for r in conn.execute(
            "SELECT key, label, enabled FROM policy_category WHERE org_id = %s ORDER BY key",
            (org_id,),
        ).fetchall()
    ]
    return PolicyBody(
        org_id=org_id, org_name=org["name"], version=int(org["policy_version"]),
        tools=tools, categories=categories,
    )
