# `policy/` — AI governance service

Org identity, AI-tool policy, approval workflow, and usage events. Serves the
admin console at `/`.

**Spec:** [`docs/superpowers/specs/2026-07-19-ai-governance-platform-design.md`](../../docs/superpowers/specs/2026-07-19-ai-governance-platform-design.md)

> **Testing the whole product (backend + extension + ethics)?** The end-to-end
> setup and test cases for Plans A + B + C live in
> [`../extension/README.md`](../extension/README.md#ai-governance-platform-plans-a--b--c--setup--testing).

## The boundary with `backend/` — do not merge these

`backend/` parses files and keeps nothing;
[`test_zero_retention.py`](../backend/tests/test_zero_retention.py) defends that
in executable form. This service is the opposite: org state is its whole job.

Note that `backend/README.md` describes itself as *"policy, dictionary, and
hashed audit ingest"* — that is **this** service. What was built under
`backend/` is the file pipeline. The split is deliberate, not accidental.

## Run it

🔴 **Build the console BEFORE starting the server. The order below is not a
suggestion.** `app/static/` is git-ignored and only exists after `npm run
build`; whether `/` serves the console is decided **once, at import time**
(`app/main.py`, `_STATIC.exists()`). Start uvicorn first and `/` 404s until
you **restart the process** -- finishing the build afterwards does not fix
a server that already imported. On stage that reads as a broken product.

```bash
python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"
cd admin && npm install && npm run build && cd ..   # MUST run before uvicorn starts
.venv/Scripts/python scripts/seed.py          # builds the demo world, writes DEMO-TOKENS.md
.venv/Scripts/python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

If you started the server before building: build the console, then **restart**
uvicorn -- reloading `/` in the browser is not enough. The server also logs a
loud warning at startup (`console not built: ... / will 404 ...`) if it was
launched with no build present, so a missing console is visible in the log,
not just as a mysterious 404.

`--host 0.0.0.0` is required for the two-laptop demo (spec §5.4).

## Signup, login, and enrolment — three tiers

The service has three tiers of identity, each with its own credential:

1. **Company** — self-signup at `/` with just a company name. The response is
   a **Company Admin secret, shown once** and never stored except as a
   SHA-256 hash. There is no separate "create an account" password step.
2. **Department** — the company dashboard creates departments; each one gets
   its own **Department Admin secret** (also shown once). A department admin
   sees and decides only its own department's requests, appeals, and tokens.
3. **Employee** — a department dashboard mints employee enrolment tokens; the
   employee pastes one into the extension, which exchanges it once for a
   pseudonymous `pseudo_id`.

Login is a single endpoint with a role picker: `POST /v1/admin/login
{"role": "company"|"department", "secret": "..."}`. Both roles share the same
`vg_admin` session cookie; server-side `role` (never the client) decides which
routes -- `/v1/admin/*` (company) or `/v1/dept/*` (department) -- the session
may reach.

**Reseed the demo:** delete `policy.db`, then run `python scripts/seed.py` --
it builds a fresh company/department/employee world and writes every secret
and token to `DEMO-TOKENS.md` (git-ignored; regenerated per machine, never
committed).

## Standing constraints

- 🔴 **I3: classes, counts, salted hashes. NEVER prompt text.** `UsageEvent` sets
  `extra="forbid"`, so an event carrying a `prompt` field is **rejected**, not
  ignored. `tests/test_events.py` is that rule in executable form.
- 🔴 **Admin authority is server-side, on every request.** The console is a view.
- 🔴 **The 422 handler in `app/main.py` is a privacy control, not a formatting
  nicety.** Pydantic's `RequestValidationError.errors()` embeds the rejected
  value verbatim under `input` — for a `missing`-field error that can be the
  **entire request body**. FastAPI's default handler serialises `errors()`
  straight into the response, so a prompt sent to `/v1/events` under the wrong
  key would come straight back out in the 422 body. The handler strips `input`
  (and `ctx`) before responding. **Do not "simplify" this back to FastAPI's
  default handler — the default is the vulnerability it exists to close.**
- **Employees are pseudonymous.** No name or email column exists in `employees`.
- **Every policy write calls `bump_policy_version()`.** It is the ETag; a missed
  bump is a client that never refreshes.
- 🔴 **Revoking an enrolment token blocks FUTURE enrolments only.** It does not
  deprovision employees who already enrolled with that token — there is no
  per-employee revocation in this system. The Tokens screen states this in the
  UI; this is the same fact stated here.
- **Demo-grade.** SQLite, one admin password per org, no SSO. Spec §9 carries the
  honest answer for each.
