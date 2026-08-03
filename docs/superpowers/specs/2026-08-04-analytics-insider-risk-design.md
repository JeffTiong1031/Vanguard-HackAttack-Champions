# Design — Analytics & Insider-Risk dashboards

> **Date:** 2026-08-04 · **Branch:** `transparency-redressal` · **Status:** approved design, pre-plan
>
> The analytics/insider-risk widgets from the founder's reference images, rendered in the existing
> console's design. Builds on the department hierarchy (company/department dashboards, `usage_events`).
> Touches `code/policy` (schema + aggregation + console) and one copy string in `code/extension`.

---

## 1. Goal

Add two dashboard tabs — **AI Usage** and **Insider Risk** — to both the company and department consoles,
populated from Vanguard's own governance telemetry (`usage_events`), rendered in the current console
style. This delivers the *shape* of the founder's reference images without adopting their data model.

**Three deliberate departures from the images, each settled during brainstorming:**
1. **No EDR / MITRE ATT&CK behaviour telemetry** (file deletes, process discovery, technique IDs). Vanguard
   is a browser prompt-privacy extension, not an endpoint agent — that data does not exist and will not be
   faked. The images' "Behavior Alerts" are repopulated with our events (`pii_block`, `ethics_block`,
   `visit_unapproved`, warns).
2. **Named employees, via admin-supplied labels — not extension-collected identity.** The founder chose
   named employees; the name is a label the *department admin* attaches to an employee token at mint time,
   stored server-side. **The extension still collects and transmits nothing about identity** (only
   pseudo_id + department + salted hashes), and prompt-content audit stays salted-hash. This reverses the
   *employee-anonymity* posture (I3 as applied to the actor) but preserves the stronger claim: the tool
   never learns the user's identity or prompt content.
3. **A transparent weighted risk score**, not an ML "risk model." Fixed, visible weights over governance
   events. Explicitly labelled a heuristic.

**Non-goals:** endpoint/EDR telemetry; configurable risk weights; a full date-range picker (two presets
only); "Create Widget", per-widget filters, CSV export; any new prompt-content storage.

---

## 2. Data model changes (SQLite)

- **`enroll_tokens`** — add `name TEXT` (the admin-supplied label, set at mint; nullable).
- **`employees`** — add `name TEXT` (inherited from the token at enrol, like `department`; nullable).
- Idempotent migration (same pattern as `_migrate_hierarchy`): `ALTER TABLE ... ADD COLUMN name TEXT`
  for both tables if absent.
- **No new tables, no prompt-content columns.** Everything else reads existing `usage_events`.

**Risk weights (fixed constants, defined once server-side and shown in the UI):**

| event type | weight | rationale |
|---|---|---|
| `ethics_block` | 5 | highest-severity governance event |
| `pii_block` | 3 | sensitive data caught at the gate |
| `warn_shown` | 1 | unapproved-tool warning surfaced |
| `visit_unapproved` | 1 | visited an unapproved tool |
| `request_sent` | 0 | asking permission is not risk |

**Severity mapping** (alerts widgets): high = `{ethics_block, pii_block}`, medium = `{warn_shown}`,
low = `{visit_unapproved, request_sent}`.

**Action labels** (review table): `pii_block`/`ethics_block` → "Blocked", `warn_shown` → "Warned",
`visit_unapproved` → "Visited", `request_sent` → "Requested".

---

## 3. Backend — aggregation

A shared helper computes a summary and an alerts list, scoped by org and optionally department:

```
analytics_summary(conn, org_id, days: int, department_id: str | None) -> dict
analytics_alerts(conn, org_id, limit: int, department_id: str | None) -> list[dict]
```

`analytics_summary` returns:
- `usage_trend`: `[{date, department, events}]` — per-department per-day counts (frontend pivots to lines).
- `alerts_timeline`: `[{date, high, medium, low}]` — per-day counts by severity.
- `top_apps`: `[{host, events}]` — top hosts in the window.
- `top_employees`: `[{name, department, events, risk}]` — ranked by `risk` desc.
- `top_departments`: `[{department, events, risk}]` — ranked by `risk` desc.
- `alerts_by_severity`: `[{severity, count}]` — high/medium/low totals.
- `totals`: `{events, active_employees, days}`.

`analytics_alerts` returns newest-first: `[{ts, department, name, host, type, category, action, severity}]`.

**Mechanics (all queries):**
- Org-scoped: `WHERE u.org_id = ?`. Department scope adds `AND e.department_id = ?`.
- Windowing: `WHERE substr(u.ts,1,10) >= date('now', ?)` with `?` = `'-' || (days-1) || ' days'`
  (lexicographic date compare on the ISO `ts` — no timezone-format pitfalls).
- Risk: `SUM(CASE u.type WHEN 'ethics_block' THEN 5 WHEN 'pii_block' THEN 3 WHEN 'warn_shown' THEN 1
  WHEN 'visit_unapproved' THEN 1 ELSE 0 END)`.
- Names: `COALESCE(NULLIF(e.name,''), 'Unnamed')`.
- Severity in SQL via `CASE u.type` into `high`/`medium`/`low` sums.

**Routes** (mirroring the hierarchy's company/department split):
- Company (`require_company`): `GET /v1/admin/analytics/summary?days=7`, `GET /v1/admin/analytics/alerts?limit=50`.
- Department (`require_department`, auto-scoped): `GET /v1/dept/analytics/summary?days=7`,
  `GET /v1/dept/analytics/alerts?limit=50`.
- `days` accepts `7` or `30` (clamp/validate; default 7). `limit` default 50, capped (e.g. 200).

**Token/enrol plumbing for names:**
- `POST /v1/dept/tokens` gains optional `name: str` in the body; stored on `enroll_tokens.name`.
- `enroll` copies `enroll_tokens.name` → `employees.name` (alongside `department`/`department_id`).

---

## 4. Console UI (Preact, current design, inline SVG — no chart library)

**Tabs** — the existing simple `Usage` screen is absorbed into a richer **AI Usage** tab; a new **Insider
Risk** tab is added. Both appear in both dashboards and take a `scope: 'company' | 'department'` prop that
swaps the endpoint base (`/v1/admin/analytics/*` ↔ `/v1/dept/analytics/*`), exactly like the hierarchy
screens.

- **Company tabs:** Departments · Tools · Requests · Reviews · **AI Usage** · **Insider Risk**
- **Department tabs:** Requests · Reviews · Employee Tokens · Tools · **AI Usage** · **Insider Risk**

**AI Usage tab:**
- *Usage Trend by Department* — inline-SVG `LineChart` (one line per department; a single line in
  department scope).
- *Top Apps / Domains* — existing `Bars`.
- *Top Employees* — `Bars`, named, ranked by activity (events).

**Insider Risk tab:**
- *Risk Score Timeline* and *Alerts Timeline* — inline-SVG `LineChart`.
- *Top Risky Employees* (named) and *Top Risky Departments* — `Bars` ranked by risk, with a small visible
  **weights legend**.
- *Alerts by Severity* — `Bars` (high/medium/low).
- *Review Alerts table* — `AlertsTable`: timestamp · department · employee · tool · type/category · action ·
  severity, from `/analytics/alerts`.

**Department scope collapses gracefully:** *Top Risky Departments* is hidden (single department) and
*Usage Trend by Department* shows that department's single daily line.

**Shared pieces (new, small, focused):**
- `LineChart` (inline SVG) — with a pure `scalePoints(series, width, height)` helper (unit-tested).
- `AlertsTable` — renders the alerts rows.
- A pure `pivotTrend(rows) -> { dates, series }` helper turning `[{date, department, events}]` into
  per-department series (unit-tested).
- A range selector (Last 7 days / Last 30 days) → `days` param.
- `Bars` is reused unchanged.

**Employee-Tokens screen** gains an optional **Name** field beside the mint button (department admin's
label for the person the token is for).

---

## 5. Extension change (one copy string)

The employee-facing text in `entrypoints/options/main.tsx` currently reads:
*"It identifies your department, not you — Vanguard never stores your name or email address."*

Reword to stay truthful now that an admin may label the enrolment:
*"Vanguard never collects your name, email, or prompt text. Your organisation may label your enrolment with
your name for its own records."*

No behavioural change to the extension; it still transmits only pseudo_id + department + salted hashes.

---

## 6. Seed data

Extend the demo seed so the charts are populated:
- Label each seeded employee token with a person name.
- Generate varied `usage_events` across the seeded departments, event types, and several days (spanning the
  7- and 30-day windows), so every widget renders with data.

---

## 7. Testing

**Backend** (the aggregation is the risk surface):
- `risk` equals the weighted sum for a seeded mix of event types (table test over the weight map).
- Windowing: events older than `days` are excluded; `7` vs `30` include the right rows.
- `top_employees` joins names and shows "Unnamed" when the label is blank.
- Severity buckets and `analytics_alerts` action/severity mapping are correct.
- **Department scope isolation:** a department summary/alerts call returns only that department's rows; a
  second department's events never appear.
- Name plumbing: `POST /v1/dept/tokens {name}` → enrol → `employees.name` set → surfaces in analytics.

**Frontend** (Vitest):
- `pivotTrend(rows)` pure helper — correct per-department series and date axis.
- `scalePoints(...)` pure helper — data values map to expected SVG coordinates (incl. a flat/one-point series).
- Components verified by build + suite green; the mint name-field flow.

**Seed script** writes populated demo data; `npm run build` (console) + `pytest` (policy) stay green.

---

## 8. Consequences & trade-offs

- **Employee anonymity (I3 as applied to the actor) is intentionally relaxed** — names are admin-supplied
  labels held server-side. The extension's collection posture is unchanged; the reworded copy keeps the
  promise truthful. This is a founder decision, recorded here, reversing the *employee-anonymity* half of
  decision #5 while preserving the *prompt-content* half.
- **The risk score is invented but transparent** — fixed weights, shown in the UI, labelled a heuristic.
  It ranks; it does not diagnose.
- **On-demand SQL aggregation** (no rollup tables) is fine at this scale and matches `/v1/admin/usage`.
- **No chart library** — inline SVG keeps the console CSP-clean and dependency-light, consistent with its
  hand-rolled bars and inline SVG icons.
- **Likely split at planning time** into a backend plan (schema + name plumbing + aggregation + seed) and a
  console plan (tabs, chart components, name field, extension copy), as the hierarchy was.
