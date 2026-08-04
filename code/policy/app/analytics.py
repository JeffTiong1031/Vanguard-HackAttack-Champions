"""Analytics aggregation over usage_events.

Plain SQL, computed on demand -- the data is small and read far more than
written, matching the rest of app/. I3: no prompt text is read or returned;
only class, count, host, type, ts, and the admin-supplied name.

Postgres notes vs the former SQLite version:
  * date('now', '-N days')  →  CURRENT_DATE - INTERVAL '...'
  * substr(ts, 1, 10)       →  LEFT(ts, 10)  (ts is stored as ISO-8601 TEXT)
  * Placeholders are %s, not ?
"""

WEIGHTS_SQL = (
    "CASE u.type WHEN 'ethics_block' THEN 5 WHEN 'pii_block' THEN 3"
    " WHEN 'warn_shown' THEN 1 WHEN 'visit_unapproved' THEN 1 ELSE 0 END"
)
SEVERITY_SQL = (
    "CASE WHEN u.type IN ('ethics_block','pii_block') THEN 'high'"
    " WHEN u.type = 'warn_shown' THEN 'medium' ELSE 'low' END"
)
ACTION_SQL = (
    "CASE u.type WHEN 'pii_block' THEN 'Blocked' WHEN 'ethics_block' THEN 'Blocked'"
    " WHEN 'warn_shown' THEN 'Warned' WHEN 'visit_unapproved' THEN 'Visited'"
    " WHEN 'request_sent' THEN 'Requested' ELSE u.type END"
)
_NAME = "COALESCE(NULLIF(e.name,''),'Unnamed')"


def analytics_summary(conn, org_id: str, days: int, department_id: str | None) -> dict:
    # Postgres interval: cast days to text inside the query
    scope = " AND e.department_id = %s" if department_id else ""
    base = (
        "FROM usage_events u JOIN employees e ON e.id = u.employee_id"
        " WHERE u.org_id = %s AND LEFT(u.ts, 10) >= (CURRENT_DATE - (%s || ' days')::INTERVAL)::TEXT"
        + scope
    )
    p = (org_id, str(days - 1)) + ((department_id,) if department_id else ())

    def q(sql):
        return [dict(r) for r in conn.execute(sql, p).fetchall()]

    usage_trend = q(
        f"SELECT LEFT(u.ts,10) AS date, e.department AS department, COUNT(*) AS events "
        f"{base} GROUP BY date, e.department ORDER BY date")
    alerts_timeline = q(
        f"SELECT LEFT(u.ts,10) AS date,"
        f" SUM(CASE WHEN u.type IN ('ethics_block','pii_block') THEN 1 ELSE 0 END) AS high,"
        f" SUM(CASE WHEN u.type = 'warn_shown' THEN 1 ELSE 0 END) AS medium,"
        f" SUM(CASE WHEN u.type IN ('visit_unapproved','request_sent') THEN 1 ELSE 0 END) AS low "
        f"{base} GROUP BY date ORDER BY date")
    risk_timeline = q(
        f"SELECT LEFT(u.ts,10) AS date, SUM({WEIGHTS_SQL}) AS risk "
        f"{base} GROUP BY date ORDER BY date")
    top_apps = q(
        f"SELECT u.host AS host, COUNT(*) AS events {base} GROUP BY u.host ORDER BY events DESC LIMIT 10")
    top_employees = q(
        f"SELECT {_NAME} AS name, e.department AS department, COUNT(*) AS events,"
        f" SUM({WEIGHTS_SQL}) AS risk {base} GROUP BY e.id, e.name, e.department ORDER BY risk DESC, events DESC LIMIT 10")
    top_departments = q(
        f"SELECT e.department AS department, COUNT(*) AS events, SUM({WEIGHTS_SQL}) AS risk "
        f"{base} GROUP BY e.department ORDER BY risk DESC LIMIT 10")
    alerts_by_severity = q(
        f"SELECT {SEVERITY_SQL} AS severity, COUNT(*) AS count {base} GROUP BY severity")

    row = conn.execute(
        f"SELECT COUNT(*) AS events, COUNT(DISTINCT u.employee_id) AS active_employees {base}", p
    ).fetchone()
    totals = {"events": row["events"], "active_employees": row["active_employees"], "days": int(days)}

    return {
        "usage_trend": usage_trend, "alerts_timeline": alerts_timeline,
        "risk_timeline": risk_timeline, "top_apps": top_apps,
        "top_employees": top_employees, "top_departments": top_departments,
        "alerts_by_severity": alerts_by_severity, "totals": totals,
    }


def analytics_alerts(conn, org_id: str, limit: int, department_id: str | None) -> list[dict]:
    scope = " AND e.department_id = %s" if department_id else ""
    params = (org_id,) + ((department_id,) if department_id else ()) + (int(limit),)
    rows = conn.execute(
        f"SELECT u.ts AS ts, e.department AS department, {_NAME} AS name, u.host AS host,"
        f" u.type AS type, u.category AS category, {ACTION_SQL} AS action, {SEVERITY_SQL} AS severity"
        f" FROM usage_events u JOIN employees e ON e.id = u.employee_id"
        f" WHERE u.org_id = %s{scope} ORDER BY u.ts DESC LIMIT %s",
        params,
    ).fetchall()
    return [dict(r) for r in rows]
