# Design — Multi-tenant department hierarchy (three-tier governance)

> **Date:** 2026-08-03 · **Branch:** `transparency-redressal` · **Status:** approved design, pre-plan
>
> This is **sub-project 1 of 3** from the founder's request. The other two —
> the extension **Personal vs Enterprise** mode gate, and the **analytics
> widgets** from the reference dashboards — are explicitly **out of scope here**
> and get their own spec → plan → build cycle afterward. This one is the *spine*:
> it reshapes the token model and DB schema the other two will read from, which
> is why it goes first.

---

## 1. Goal

Turn the current **two-tier** governance model (one company admin → per-department
enrolment tokens used directly in the extension) into a **three-tier** model:

```
Company owner ──(self-signup)──► Company dashboard   (all departments, all stats)
     │  creates departments, mints a Department Admin secret per department
     ▼
Department admin ─(dept secret)─► Department dashboard (that department only)
     │  approves requests & appeals for its dept, mints Employee tokens
     ▼
Employee ────────(employee token)─► Extension only    (governed; no dashboard)
```

Two credential *kinds*:
- **Dashboard login secrets** — Company Admin and Department Admin. Generated,
  shown once, hash-stored, pasted into a role-picker login page.
- **Employee tokens** — exactly today's per-department enrolment tokens, just
  renamed and re-homed under the department admin who mints them. Pasted into the
  **extension**; there is no employee dashboard.

**Non-goals (this spec):** the extension mode gate; analytics/insider-risk
widgets; a UI to edit ethics categories; per-employee deprovisioning (a
pre-existing, documented gap — not made worse here). The pseudonymity invariant
(no employee names/PII columns; salted-hash audit) is **preserved unchanged**.

---

## 2. Approach (decided)

- **Company defaults + department overrides.** `org_llm_policy` stays the
  company-wide default (set on the company Tools screen); a new `dept_llm_policy`
  table holds per-department overrides. Effective tool status for an employee =
  `coalesce(dept override, company default)`. A department admin approving a
  request writes an override for **their department only**; other departments are
  untouched, and company-level changes still propagate to any department that has
  not overridden. *(Rejected: fully independent per-department policy sets —
  duplicates every tool row per department and stops company changes propagating.)*
- **One role-gated Preact app.** The login role-picker routes to a Company view or
  a Department view; the existing `Requests`/`Reviews`/`Usage`/`Tokens` screens are
  reused with a `scope` prop that swaps the API base path and read-only/actionable
  mode. *(Rejected: two separate console apps — needless duplication.)*
- **All console credentials are high-entropy generated secrets → SHA-256.**
  `security.py` already argues the rule: generated secrets get fast SHA-256, only
  low-entropy human passwords need scrypt. Since every credential is now generated,
  the scrypt password path retires for the console.

---

## 3. Data model (SQLite)

### New tables

```sql
CREATE TABLE departments (
    id               TEXT PRIMARY KEY,
    org_id           TEXT NOT NULL REFERENCES orgs(id),
    name             TEXT NOT NULL,
    admin_token_hash TEXT NOT NULL UNIQUE,   -- SHA-256 of the Department Admin secret
    created_at       TEXT NOT NULL,
    UNIQUE (org_id, name)
);

CREATE TABLE dept_llm_policy (
    org_id        TEXT NOT NULL REFERENCES orgs(id),
    department_id TEXT NOT NULL REFERENCES departments(id),
    llm_id        TEXT NOT NULL REFERENCES llm_registry(id),
    status        TEXT NOT NULL CHECK (status IN ('approved','blocked')),
    PRIMARY KEY (department_id, llm_id)
);
```

### Changed tables

- **`orgs`** — add `admin_token_hash TEXT` (SHA-256 of the Company Admin secret).
  `admin_password_hash` becomes a dead column (left NULL-able / unused until a
  future cleanup); the reseed populates `admin_token_hash` only.
- **`admin_sessions`** — add `role TEXT NOT NULL CHECK (role IN ('company','department'))`
  and `department_id TEXT` (NULL for company sessions). One session table serves
  both dashboards; the server always knows the scope from the session row.
- **`employees`** — add `department_id TEXT REFERENCES departments(id)`. The
  `department` *name* stays (the Usage dashboard groups on it), but all
  **scoping/filtering keys on `department_id`**.
- **`enroll_tokens`** — add `department_id TEXT REFERENCES departments(id)`.
  On enrol, the employee inherits both `department_id` and `department` name from
  the token.

`access_requests` and `decision_appeals` are **unchanged** — they reach a
department by joining `employees.department_id`, so no duplicated column.

---

## 4. Auth & sessions

### Self-signup
`POST /v1/signup {company_name}`:
1. Create the org, seed the tool registry defaults + ethics categories (today's
   `seed_demo_org` logic).
2. Mint the **Company Admin secret** (`new_token("CO")` style), store its hash.
3. Return the plaintext **once**.

### Login (role picker)
`POST /v1/admin/login {role, secret}` (replaces `{org_name, password}`):
- `role='company'`  → `sha256(secret)` matched against `orgs.admin_token_hash`
  → issue session `(role=company, org_id, department_id=NULL)`.
- `role='department'` → matched against `departments.admin_token_hash`
  → issue session `(role=department, org_id, department_id)`.

The secret self-identifies the company/department; no org name or username is
typed. Comparison uses a constant-time compare. The scrypt dummy-hash timing
defense is **removed** — there is no low-entropy password to brute-force, so it
protected nothing here.

### Scoped guards
Replace the single `_require_admin` with:
- `_require_company(session) -> org_id`
- `_require_department(session) -> (org_id, department_id)`

Every route declares which it needs; a company session hitting a `/v1/dept/*`
route (or vice-versa) is rejected 401/403.

---

## 5. API surface

### Company routes — require a company session
| Method & path | Purpose |
|---|---|
| `GET  /v1/admin/departments` | list departments (+ active employee-token count) |
| `POST /v1/admin/departments {name}` | create department, mint dept secret, return **once** |
| `POST /v1/admin/departments/{id}/regenerate` | rotate the dept secret, return **once** |
| `GET  /v1/admin/tools` · `POST /v1/admin/tools/{llm_id}` | company **default** policy (existing) |
| `GET  /v1/admin/usage` | all-department stats (existing) |
| `GET  /v1/admin/requests` · `GET /v1/admin/appeals` | **read-only** oversight across all depts |

Deciding requests/appeals is **not** a company-tier action — it moves to the
department tier.

### Department routes — require a department session, auto-scoped to `department_id`
| Method & path | Purpose |
|---|---|
| `GET  /v1/dept/requests` | this dept's employees' access requests |
| `POST /v1/dept/requests/{id} {decision}` | approve → write `dept_llm_policy` override for **this dept** + bump org policy version; deny → record only |
| `GET  /v1/dept/appeals` · `POST /v1/dept/appeals/{id}` | existing appeal logic incl. one-time-pass, scoped to this dept |
| `GET  /v1/dept/tokens` · `POST /v1/dept/tokens` · `POST /v1/dept/tokens/{id}/revoke` | mint/list/revoke **employee tokens** carrying this `department_id` |
| `GET  /v1/dept/tools` | **effective** policy (defaults + overrides), read-only |
| `GET  /v1/dept/usage` | this department's stats only |

A `POST /v1/dept/requests/{id}` decision derives the target department from the
request's employee and **must** match the session's `department_id` (else 404).

### Changed shared paths
- `read_policy(conn, org_id, department_id)` — tool status becomes
  `coalesce(dept override, company default)`.
- `GET /v1/policy` gains a `department_id` query param; **ETag becomes
  `org_id-department_id-version`**. `enroll` now also returns `department_id`
  so the extension can send it on every poll.
- `create_request` (employee-side, keyed on `pseudo_id`) is unchanged.

---

## 6. Console UI (one role-gated Preact app)

- **`Signup` (new)** — company name → shows the Company Admin secret once
  (copy-now banner, same pattern as token minting).
- **`Login` (rewritten)** — role toggle *Company Admin / Department Admin* + one
  secret field → `POST /v1/admin/login`. The shell reads the session role and
  mounts the matching dashboard.
- **Company dashboard** tabs: **Departments** (new — create, show-secret-once,
  regenerate, list) · **Tools** (company defaults) · **Usage** (all-dept) ·
  **Oversight** (read-only Requests + Reviews across depts).
- **Department dashboard** tabs: **Requests** · **Reviews** · **Employee Tokens**
  (today's `Tokens` screen, minting dept-scoped) · **Usage** (dept-scoped).
- `Requests` / `Reviews` / `Usage` / `Tokens` are reused with a `scope` prop that
  swaps `/v1/admin/*` ↔ `/v1/dept/*` and read-only ↔ actionable — no forked copies.

The department dashboard shows **pseudonymous** employees grouped by department;
no names, no new PII columns.

---

## 7. Seed data & the testing-secrets file

The seed builds a **demo world** so both dashboards are populated on first run:
- One demo company (mints Company Admin secret).
- 2–3 departments (e.g. Engineering, Sales, Compliance), each with a Department
  Admin secret.
- Several employee tokens per department; enrol a few pseudonymous employees.
- Demo usage events, access requests, and appeals spread across departments, plus
  one department override, so no screen is empty.

**Testing-secrets file:** the seed **writes every generated secret/token to
`code/policy/DEMO-TOKENS.md`**, labelled by role + department, so teammates know
exactly which secret to paste where and nothing is lost.
- The file **stays git-ignored** (it already is). Secrets are freshly minted on
  each reseed, so they are per-machine — committing them across machines is
  meaningless. A teammate runs the seed and reads their own file.
- The file carries a bold header: **demo/testing only — real deployments never
  write secrets to disk; secrets are shown once and hash-stored** — so it does not
  quietly contradict the product's own custody story.
- Re-running the seed regenerates and rewrites the file.

---

## 8. Migration

Two mechanisms, because `policy.db` already holds data:
- **Forward schema migration** (idempotent, like the existing `_migrate_appeals`):
  create the new tables and add the new columns so an existing DB still loads.
- **Reseed for the demo:** pre-existing departments have no recoverable secret, so
  the clean path is to **wipe and reseed `policy.db`**, giving every department a
  known, file-recorded secret. The forward migration keeps a non-demo DB from
  crashing; the reseed is what teammates actually run. Both are documented in the
  policy README.

---

## 9. Tests

Extend `test_admin.py`, `test_end_to_end.py`; add `test_departments.py`:
- Signup mints a working company secret; role login routes to the correct scope.
- **Isolation:** a Dept-A session cannot read or decide Dept-B's
  requests/appeals/tokens (403/404) and cannot see Dept-B usage.
- Approving a request writes a **dept override**, leaves `org_llm_policy`
  untouched; an enrolled employee in that dept then polls the new effective
  policy while an employee in another dept does not.
- Company admin sees all departments; oversight routes are read-only (no decide).
- Employee enrol returns `department_id`; `GET /v1/policy?department_id=…` returns
  dept-scoped effective policy with the `org-dept-version` ETag.
- Department-secret regenerate invalidates the old secret and issues a new one.

---

## 10. Consequences & trade-offs (recorded)

- **Per-org `policy_version`** means a single department's override bumps the
  version for **every** department in that org, so all clients refetch on next
  poll. This is *correct* (each refetch returns that client's own dept-scoped
  policy) but mildly over-fetches. A per-department policy version is a later
  optimisation, not needed now.
- **Dropping scrypt** for the console is safe: every credential is now
  high-entropy generated randomness, which SHA-256 lookup handles correctly (the
  same reasoning the codebase already applies to enrolment tokens).
- **Credential recovery:** a lost **department** secret is recoverable (company
  admin regenerates it); a lost **company** secret has **no** Phase-0 recovery
  (re-signup). Documented, not silently accepted.
- **Pseudonymity preserved:** this sub-project adds no employee-identifying data.
  The named-employee / EDR-style widgets in the reference images are a known
  tension deferred entirely to the analytics sub-project, where it will be
  confronted, not smuggled in here.
