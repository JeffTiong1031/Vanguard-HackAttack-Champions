# Token Identity, Deprovisioning & Generic Protection — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the enrolment token the durable identity for an employee, so usage counts survive reinstalls, revoking genuinely deprovisions, and the admin can see who never enrolled — then verify whether generic (adapter-free) composer write-back works, which decides the shape of the follow-up plan.

**Architecture:** The server currently copies an employee's *name* off their enrolment token and throws away the link. Every defect below follows from that. Piece 1 stores the link, turns enrolment into find-or-create, and makes revocation cascade. Piece 2 reads that link back into the console. Piece 0 is an independent measurement spike whose result determines whether adapter-free protection is viable across all AI tools.

**Tech Stack:** FastAPI + psycopg2 + Supabase Postgres (`code/policy`) · Preact + Vite admin console (`code/policy/admin`) · WXT + TypeScript MV3 extension (`code/extension`) · pytest · vitest · raw MV3 for spikes (no build).

---

## Global Constraints

- **Commits carry sole authorship. NEVER add a `Co-Authored-By` trailer.** `git config user.name/user.email` is already `JeffTiong1031 <jefftiong1031@gmail.com>`; authorship is correct by default.
- **Commit after every task**, with a message naming the deliverable.
- 🔴 **HUMAN GATE BETWEEN PIECES.** Stop after each Piece, report results, and wait for the founder's explicit go-ahead. Do not begin the next Piece unprompted.
- 🔴 **`code/policy` tests run against the live `DATABASE_URL`** (`tests/conftest.py`) and **take ~18 minutes** (133 tests, measured 2026-08-05). They print nothing until they finish. **Do not kill the run early.** Every test that creates data must use `uuid` identifiers.
- 🔴 **I3 holds everywhere in this plan: classes, counts, salted hashes. NEVER prompt text.** No task here adds a prompt-text path.
- **`code/extension` needs `npm install` before any test runs** — `node_modules` is absent on this machine.
- **After any change under `code/extension/`, run `npm run build` then `npm run check:dist`.** The committed `dist/` is a second source of truth and drifts silently.
- **Nothing in `code/spikes/` ships.** Spikes are measuring instruments (ADR 0012; U26 — the harness may log raw values the product must never inherit).
- **Every number reported from a spike is either measured or tagged `(estimate)`.** No invented figures.

---

## Scope of THIS plan

| Piece | In this document | Why |
|---|---|---|
| **0 — Spike: generic write-back (U31)** | ✅ Full detail | Independent; runs first |
| **1 — Token = identity, revoke = out** | ✅ Full detail | Independent of the spike |
| **2 — Console: usage, enrolments, last active** | ✅ Full detail | Depends only on Piece 1 |
| **3 — Generic protection + block unapproved** | ❌ **Follow-up plan** | Its tasks depend on what Piece 0 measures |
| **4 — Awareness + protection lists** | ❌ Follow-up plan | Shape depends on Piece 3 |
| **5 — Feedback button** | ❌ Follow-up plan | Rides on Piece 4's tool registry |

🔴 **Pieces 3–5 are deliberately not specified yet.** Writing implementation steps for a technique that has not been measured would be fiction, and this package has a standing rule against confident invention. The follow-up plan gets written the day Piece 0 reports.

---

## File Structure

**Piece 0 — new, throwaway**

| File | Responsibility |
|---|---|
| `code/spikes/u31-generic-writeback/manifest.json` | Raw MV3, zero build, zero deps |
| `code/spikes/u31-generic-writeback/probe.js` | Content script: find composer, attempt write, read back, log raw observations |
| `code/spikes/u31-generic-writeback/README.md` | How to run, what each field means, how to read the raw log |
| `code/spikes/u31-generic-writeback/results/` | Saved JSON captures (evidence) |

**Piece 1 — server + extension**

| File | Responsibility |
|---|---|
| `code/policy/app/db.py:247` | Add `employees.enroll_token_id` to `_COLUMN_ADDS` |
| `code/policy/app/routes/enroll.py` | Find-or-create; record token id; reject expired-and-unused; reject revoked |
| `code/policy/app/routes/events.py` | Reject events from a revoked lineage |
| `code/policy/app/routes/policy.py` | Optional `pseudo_id`; 403 when that enrolment is revoked |
| `code/policy/app/enrolment.py` | **New.** Pure helpers: `token_is_expired()`, `employee_for_token()` — testable without HTTP |
| `code/extension/src/policy/client.ts` | Detect the 403 revoked signal |
| `code/extension/src/policy/revoked.ts` | **New.** `handleRevoked()` — clear enrolment, force Personal, raise the notice flag |
| `code/extension/entrypoints/options/main.tsx` | Lock the mode switch while enrolled; warning copy; revoked notice |

**Piece 2 — server + console**

| File | Responsibility |
|---|---|
| `code/policy/app/routes/dept.py:155` | `/v1/dept/tokens` returns usage, enrolments, last active, status |
| `code/policy/app/token_stats.py` | **New.** The aggregation SQL, isolated so it is unit-testable |
| `code/policy/admin/src/screens/Tokens.tsx` | Unused / Used / Revoked pill + the three new columns |
| `code/policy/app/analytics.py` | Group employees by token, not by employee row |

---

# PIECE 0 — Spike: does generic write-back work? (U31)

**Register entry:** U31 — *"A composer rewrite performed through the browser's own text-insertion path is accepted by the site's editor framework, and a read-back check reliably detects the cases where it is not."*

**Why this shape.** Ledger #10 and #11 in `CLAUDE.md` were both harness bugs that produced confident wrong answers, caught only because a human read a raw log. So this spike **records raw observations and computes no verdict in code.** The `PASS`/`FAIL` column is filled in by a human reading the capture.

### Task 0.1: Build the probe

**Files:**
- Create: `code/spikes/u31-generic-writeback/manifest.json`
- Create: `code/spikes/u31-generic-writeback/probe.js`
- Create: `code/spikes/u31-generic-writeback/README.md`

**Interfaces:**
- Produces: a JSON capture per surface with fields `host`, `composerFound`, `composerKind`, `wrote`, `readBack`, `matches`, `frameworkHint` — consumed by the human-filled results table in Task 0.3.

- [ ] **Step 1: Create the manifest**

```json
{
  "manifest_version": 3,
  "name": "U31 generic write-back probe",
  "version": "0.1",
  "description": "MEASUREMENT INSTRUMENT. Not a product. Logs raw observations only.",
  "permissions": ["clipboardWrite"],
  "host_permissions": [
    "https://chatgpt.com/*", "https://claude.ai/*",
    "https://gemini.google.com/*", "https://copilot.microsoft.com/*",
    "https://www.perplexity.ai/*", "https://chat.deepseek.com/*",
    "https://chat.mistral.ai/*", "https://grok.com/*"
  ],
  "content_scripts": [{
    "matches": [
      "https://chatgpt.com/*", "https://claude.ai/*",
      "https://gemini.google.com/*", "https://copilot.microsoft.com/*",
      "https://www.perplexity.ai/*", "https://chat.deepseek.com/*",
      "https://chat.mistral.ai/*", "https://grok.com/*"
    ],
    "js": ["probe.js"],
    "run_at": "document_idle",
    "world": "ISOLATED"
  }]
}
```

- [ ] **Step 2: Write the probe**

```javascript
// U31 MEASUREMENT INSTRUMENT — records observations, decides nothing.
// Ledger #10/#11: verdict strings in an analyser are where wrong answers come
// from. This file writes no verdict. A human reads the capture.

const MARKER = 'VG_U31_' + Math.random().toString(36).slice(2, 8);

function findComposer() {
  const active = document.activeElement;
  if (active instanceof HTMLTextAreaElement) return { el: active, kind: 'textarea' };
  if (active instanceof HTMLElement && active.isContentEditable) {
    return { el: active, kind: 'contenteditable' };
  }
  const ce = document.querySelector('[contenteditable="true"]');
  if (ce instanceof HTMLElement) return { el: ce, kind: 'contenteditable-query' };
  const ta = document.querySelector('textarea');
  if (ta instanceof HTMLTextAreaElement) return { el: ta, kind: 'textarea-query' };
  return null;
}

function readText(el) {
  return el instanceof HTMLTextAreaElement ? el.value : el.innerText;
}

// The technique under test: ask the browser to insert text through its own
// editing pipeline, so the site's framework sees a normal edit.
function genericWrite(el, text) {
  el.focus();
  document.execCommand('selectAll', false, undefined);
  return document.execCommand('insertText', false, text);
}

async function probe() {
  const found = findComposer();
  const capture = {
    marker: MARKER,
    host: location.hostname,
    at: new Date().toISOString(),
    composerFound: !!found,
    composerKind: found ? found.kind : null,
    before: null, execCommandReturned: null, readBack: null, matches: null,
    frameworkHint: Object.keys(found?.el ?? {}).filter((k) => k.startsWith('__react')).join(',') || null,
  };

  if (found) {
    capture.before = readText(found.el);
    capture.execCommandReturned = genericWrite(found.el, MARKER);
    // Two frames: a controlled editor reverts on its next render, and that
    // revert is precisely the signal we are here to observe.
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    capture.readBack = readText(found.el);
    capture.matches = capture.readBack.includes(MARKER);
  }

  console.log('[U31 CAPTURE]', JSON.stringify(capture, null, 2));
  return capture;
}

window.__vgU31 = probe;
console.log('[U31] loaded. Click into the composer, then run: await __vgU31()');
```

- [ ] **Step 3: Write the README**

```markdown
# U31 — generic composer write-back

**MEASUREMENT INSTRUMENT. Nothing here ships** (ADR 0012 · U26).

## Claim under test
A composer rewrite performed via the browser's own text-insertion path is
accepted by the site's editor framework — and when it is not, a read-back
check detects it.

## Run it
1. `chrome://extensions` → Developer mode → Load unpacked → this folder
2. Open a surface, **click into the composer**, type a word so it is focused
3. DevTools console: `await __vgU31()`
4. Copy the `[U31 CAPTURE]` JSON into `results/<host>.json`

## Reading a capture — the verdict is YOURS, not the probe's
| Field | Means |
|---|---|
| `composerFound: false` | rung 1 fails. Nothing else is meaningful |
| `execCommandReturned: false` | the browser refused the insert outright |
| `matches: true` | text landed AND survived two frames |
| `matches: false` with `execCommandReturned: true` | 🔴 **the interesting case** — the editor reverted it. This is what read-back exists to catch |

⚠️ `matches: true` proves the text is in the DOM. It does **not** prove the
site would send it. Confirm by actually sending a marked message on at least
ChatGPT and Claude, and checking the sent message contains the marker.
```

- [ ] **Step 4: Commit**

```bash
git add code/spikes/u31-generic-writeback/
git commit -m "spike(u31): probe for generic composer write-back"
```

### Task 0.2: Run it on all eight surfaces

- [ ] **Step 1: Run the probe on each surface**

Load unpacked, then for each of the eight hosts: open, click into the composer, run `await __vgU31()`, save the JSON to `results/<host>.json`.

- [ ] **Step 2: Confirm end-to-end on the two known surfaces**

On ChatGPT and Claude only: after a `matches: true` capture, **actually press Send** and confirm the sent message contains the marker string.

This is the step that separates *"the box shows it"* from *"the site sent it"* — the exact failure the whole spike exists to rule out.

- [ ] **Step 3: Commit the captures**

```bash
git add code/spikes/u31-generic-writeback/results/
git commit -m "spike(u31): captures from eight surfaces"
```

### Task 0.3: Record the result, human-filled

- [ ] **Step 1: Fill the table in the README from the raw captures**

```markdown
## Results (filled by a human reading results/*.json)

| Host | Composer found | Insert accepted | Survived 2 frames | Sent text carried marker | Verdict |
|---|---|---|---|---|---|
| chatgpt.com | | | | | |
| claude.ai | | | | | |
| gemini.google.com | | | | n/a | |
| copilot.microsoft.com | | | | n/a | |
| www.perplexity.ai | | | | n/a | |
| chat.deepseek.com | | | | n/a | |
| chat.mistral.ai | | | | n/a | |
| grok.com | | | | n/a | |

**Measured:** _/8 composers found · _/8 inserts survived · read-back caught _ of _ failures.
```

- [ ] **Step 2: Add U31 to the register**

Append to `ASSUMPTIONS.md` §3, following the existing row format, with the measured counts and the date.

- [ ] **Step 3: Commit**

```bash
git add ASSUMPTIONS.md code/spikes/u31-generic-writeback/README.md
git commit -m "spike(u31): record measured result in the register"
```

## ✅ Piece 0 success criteria

| | Criterion |
|---|---|
| 1 | A capture JSON exists in `results/` for **all eight** hosts |
| 2 | The README results table is filled from those captures, by a human |
| 3 | Send-through confirmed on ChatGPT **and** Claude (marker present in the sent message) |
| 4 | `ASSUMPTIONS.md` carries U31 with **measured counts**, no estimates |
| 5 | At least one `matches: false` case is either found, or its absence is stated explicitly — *"read-back never fired"* is a finding, not a blank |

**Decision this unlocks:** ≥6/8 surviving → Piece 3 is generic-first. ≤3/8 → Piece 3 is adapter-first and materially larger. In between → tiered, with the fallback path carrying real weight.

> 🔴 **STOP. Report to the founder. Wait for go-ahead before Piece 1.**

---

# PIECE 1 — The token is the identity

### Task 1.1: Add the `enroll_token_id` column

**Files:**
- Modify: `code/policy/app/db.py:247` (the `_COLUMN_ADDS` list)
- Test: `code/policy/tests/test_schema.py`

**Interfaces:**
- Produces: `employees.enroll_token_id TEXT` — nullable, referenced by every task below.

- [ ] **Step 1: Write the failing test**

```python
# code/policy/tests/test_schema.py — append
def test_employees_has_enroll_token_id():
    """The link that makes revocation and coverage possible."""
    conn = get_conn()
    cols = {r["column_name"] for r in conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'employees'"
    ).fetchall()}
    assert "enroll_token_id" in cols
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd code/policy && .venv/Scripts/python -m pytest tests/test_schema.py -q`
Expected: FAIL — `assert 'enroll_token_id' in {...}`

- [ ] **Step 3: Add the migration**

```python
# code/policy/app/db.py — append to _COLUMN_ADDS
    ("employees", "enroll_token_id",
     "ALTER TABLE employees ADD COLUMN IF NOT EXISTS enroll_token_id TEXT"),
```

Nullable and unconstrained on purpose: rows enrolled before this change have no token to point at, and a `NOT NULL` would fail the migration on a live database.

- [ ] **Step 4: Run it and watch it pass**

Run: `cd code/policy && .venv/Scripts/python -m pytest tests/test_schema.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add code/policy/app/db.py code/policy/tests/test_schema.py
git commit -m "feat(policy): link employees to the enrolment token they used"
```

### Task 1.2: Enrolment becomes find-or-create

**Files:**
- Create: `code/policy/app/enrolment.py`
- Modify: `code/policy/app/routes/enroll.py`
- Test: `code/policy/tests/test_enrolment_identity.py`

**Interfaces:**
- Produces: `employee_for_token(conn, token_id) -> dict | None` returning `{"id", "pseudo_id"}` or `None`.

- [ ] **Step 1: Write the failing test**

```python
# code/policy/tests/test_enrolment_identity.py
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_conn
from app.seed import seed_company, create_department, mint_employee_token

client = TestClient(app)

def _world():
    conn = get_conn()
    org_id, _ = seed_company(conn, f"T-{uuid.uuid4().hex[:8]}")
    dept_id, _ = create_department(conn, org_id, "Engineering")
    return conn, org_id, dept_id

def test_same_token_twice_returns_one_identity():
    """A reinstall must not split the person in two."""
    conn, org_id, dept_id = _world()
    token = mint_employee_token(conn, org_id, dept_id, "Engineering")

    first = client.post("/v1/enroll", json={"token": token}).json()
    second = client.post("/v1/enroll", json={"token": token}).json()

    assert first["pseudo_id"] == second["pseudo_id"]
    rows = conn.execute(
        "SELECT id FROM employees WHERE org_id = %s", (org_id,)
    ).fetchall()
    assert len(rows) == 1, "second enrolment created a duplicate employee"

def test_enrolment_records_the_token_used():
    conn, org_id, dept_id = _world()
    token = mint_employee_token(conn, org_id, dept_id, "Engineering")
    client.post("/v1/enroll", json={"token": token})

    row = conn.execute(
        "SELECT enroll_token_id FROM employees WHERE org_id = %s", (org_id,)
    ).fetchone()
    assert row["enroll_token_id"] is not None
```

- [ ] **Step 2: Run and watch both fail**

Run: `cd code/policy && .venv/Scripts/python -m pytest tests/test_enrolment_identity.py -q`
Expected: FAIL — two employee rows; `enroll_token_id` is `None`

- [ ] **Step 3: Write the helper**

```python
# code/policy/app/enrolment.py
"""Enrolment identity helpers.

The token is the durable identity. An employee row is a consequence of a
token, never an independent thing — which is what makes revocation able to
cascade and coverage able to be counted.
"""


def employee_for_token(conn, token_id: str) -> dict | None:
    """The employee this token already created, if any."""
    row = conn.execute(
        "SELECT id, pseudo_id FROM employees WHERE enroll_token_id = %s",
        (token_id,),
    ).fetchone()
    return dict(row) if row else None
```

- [ ] **Step 4: Rewrite the enrol route**

```python
# code/policy/app/routes/enroll.py — replace the body of enroll()
    conn = get_conn()
    row = conn.execute(
        "SELECT id, org_id, department, department_id, name FROM enroll_tokens"
        " WHERE token_hash = %s AND revoked = 0",
        (hash_token(body.token),),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=401, detail="enrolment token not recognised")

    existing = employee_for_token(conn, row["id"])
    if existing:
        # A reinstall. Hand back the same identity so history does not split.
        pseudo_id = existing["pseudo_id"]
    else:
        employee_id, pseudo_id = uuid.uuid4().hex, uuid.uuid4().hex
        conn.execute(
            "INSERT INTO employees"
            " (id, org_id, pseudo_id, department, department_id, name, created_at, enroll_token_id)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (employee_id, row["org_id"], pseudo_id, row["department"],
             row["department_id"], row["name"], now_iso(), row["id"]),
        )
        conn.commit()
```

Add the import: `from app.enrolment import employee_for_token`.

- [ ] **Step 5: Run and watch them pass**

Run: `cd code/policy && .venv/Scripts/python -m pytest tests/test_enrolment_identity.py tests/test_enroll.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add code/policy/app/enrolment.py code/policy/app/routes/enroll.py code/policy/tests/test_enrolment_identity.py
git commit -m "feat(policy): enrolment is find-or-create, keyed on the token"
```

### Task 1.3: Unused tokens expire after 7 days

**Files:**
- Modify: `code/policy/app/enrolment.py`
- Modify: `code/policy/app/routes/enroll.py`
- Test: `code/policy/tests/test_enrolment_identity.py`

**Interfaces:**
- Produces: `token_is_expired(created_at: str, now: datetime, used: bool) -> bool`. `used=True` always returns `False`.

- [ ] **Step 1: Write the failing test**

```python
# code/policy/tests/test_enrolment_identity.py — append
from datetime import datetime, timedelta, timezone
from app.enrolment import token_is_expired

NOW = datetime(2026, 8, 5, tzinfo=timezone.utc)

def test_unused_token_expires_after_seven_days():
    old = (NOW - timedelta(days=8)).isoformat()
    assert token_is_expired(old, NOW, used=False) is True

def test_unused_token_inside_the_window_is_fine():
    recent = (NOW - timedelta(days=6)).isoformat()
    assert token_is_expired(recent, NOW, used=False) is False

def test_a_used_token_never_expires():
    """Alice reinstalling in month three must still work."""
    ancient = (NOW - timedelta(days=400)).isoformat()
    assert token_is_expired(ancient, NOW, used=True) is False
```

- [ ] **Step 2: Run and watch it fail**

Run: `cd code/policy && .venv/Scripts/python -m pytest tests/test_enrolment_identity.py -q -k expire`
Expected: FAIL — `ImportError: cannot import name 'token_is_expired'`

- [ ] **Step 3: Implement it**

```python
# code/policy/app/enrolment.py — append
from datetime import datetime, timedelta

UNUSED_TOKEN_TTL = timedelta(days=7)


def token_is_expired(created_at: str, now: datetime, used: bool) -> bool:
    """Expiry applies to CLAIMING a token, never to keeping it.

    Once a token has created an employee it is that person's permanent
    identity, so a reinstall a year later still resolves. Only a token
    nobody ever used goes stale — which is the leaked-email case.
    """
    if used:
        return False
    return datetime.fromisoformat(created_at) + UNUSED_TOKEN_TTL < now
```

- [ ] **Step 4: Enforce it in the route**

```python
# code/policy/app/routes/enroll.py — after `existing = employee_for_token(...)`
    if token_is_expired(row["created_at"], datetime.now(timezone.utc), used=existing is not None):
        raise HTTPException(status_code=401, detail="enrolment token expired")
```

Add `created_at` to the token `SELECT`, and the imports `from datetime import datetime, timezone` and `token_is_expired`.

- [ ] **Step 5: Run and watch them pass**

Run: `cd code/policy && .venv/Scripts/python -m pytest tests/test_enrolment_identity.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add code/policy/app/enrolment.py code/policy/app/routes/enroll.py code/policy/tests/test_enrolment_identity.py
git commit -m "feat(policy): unused enrolment tokens expire after 7 days"
```

### Task 1.4: Revocation cuts off existing enrolments

**Files:**
- Modify: `code/policy/app/routes/events.py`
- Modify: `code/policy/app/routes/policy.py`
- Test: `code/policy/tests/test_deprovision.py`

**Interfaces:**
- Produces: HTTP **403** with `{"detail": "enrolment revoked"}` from `/v1/events` and from `/v1/policy` when `pseudo_id` names a revoked lineage. The extension keys on this exact status + detail.

- [ ] **Step 1: Write the failing test**

```python
# code/policy/tests/test_deprovision.py
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_conn
from app.seed import seed_company, create_department, mint_employee_token

client = TestClient(app)

def _enrolled():
    conn = get_conn()
    org_id, _ = seed_company(conn, f"T-{uuid.uuid4().hex[:8]}")
    dept_id, _ = create_department(conn, org_id, "Engineering")
    token = mint_employee_token(conn, org_id, dept_id, "Engineering")
    pseudo = client.post("/v1/enroll", json={"token": token}).json()["pseudo_id"]
    return conn, org_id, pseudo

def _revoke_all(conn, org_id):
    conn.execute(
        "UPDATE enroll_tokens SET revoked = 1 WHERE org_id = %s", (org_id,))
    conn.commit()

EVENT = {"host": "chatgpt.com", "type": "prompt_sent", "ts": "2026-08-05T00:00:00Z"}

def test_events_accepted_before_revocation():
    conn, org_id, pseudo = _enrolled()
    r = client.post("/v1/events", json={"pseudo_id": pseudo, "events": [EVENT]})
    assert r.status_code == 202

def test_events_rejected_after_revocation():
    conn, org_id, pseudo = _enrolled()
    _revoke_all(conn, org_id)
    r = client.post("/v1/events", json={"pseudo_id": pseudo, "events": [EVENT]})
    assert r.status_code == 403
    assert r.json()["detail"] == "enrolment revoked"

def test_policy_rejected_after_revocation():
    conn, org_id, pseudo = _enrolled()
    _revoke_all(conn, org_id)
    r = client.get(f"/v1/policy?org_id={org_id}&pseudo_id={pseudo}")
    assert r.status_code == 403
    assert r.json()["detail"] == "enrolment revoked"

def test_policy_without_pseudo_id_still_works():
    """Backwards compatible: an older build sends no pseudo_id."""
    conn, org_id, pseudo = _enrolled()
    _revoke_all(conn, org_id)
    assert client.get(f"/v1/policy?org_id={org_id}").status_code == 200
```

- [ ] **Step 2: Run and watch three of four fail**

Run: `cd code/policy && .venv/Scripts/python -m pytest tests/test_deprovision.py -q`
Expected: FAIL — revoked calls still return 202 / 200

- [ ] **Step 3: Add the shared check**

```python
# code/policy/app/enrolment.py — append

def enrolment_is_revoked(conn, pseudo_id: str) -> bool:
    """True when this employee's originating token has been revoked.

    Returns False for employees enrolled before enroll_token_id existed —
    they have no lineage to revoke, and failing them closed would cut off
    people no admin has acted on.
    """
    row = conn.execute(
        "SELECT t.revoked AS revoked FROM employees e"
        " JOIN enroll_tokens t ON t.id = e.enroll_token_id"
        " WHERE e.pseudo_id = %s",
        (pseudo_id,),
    ).fetchone()
    return bool(row and row["revoked"])
```

- [ ] **Step 4: Enforce it in both routes**

```python
# code/policy/app/routes/events.py — after the unknown-enrolment check
    if enrolment_is_revoked(conn, batch.pseudo_id):
        raise HTTPException(status_code=403, detail="enrolment revoked")
```

```python
# code/policy/app/routes/policy.py — add the parameter and the check
async def get_policy(
    org_id: str,
    response: Response,
    if_none_match: str | None = Header(default=None),
    department_id: str | None = None,
    pseudo_id: str | None = None,
):
    conn = get_conn()
    if pseudo_id and enrolment_is_revoked(conn, pseudo_id):
        raise HTTPException(status_code=403, detail="enrolment revoked")
```

Import `enrolment_is_revoked` in both modules.

- [ ] **Step 5: Run and watch all four pass**

Run: `cd code/policy && .venv/Scripts/python -m pytest tests/test_deprovision.py -q`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add code/policy/app/enrolment.py code/policy/app/routes/events.py code/policy/app/routes/policy.py code/policy/tests/test_deprovision.py
git commit -m "feat(policy): revoking a token deprovisions its enrolment"
```

### Task 1.5: The extension drops to Personal when revoked

**Files:**
- Create: `code/extension/src/policy/revoked.ts`
- Modify: `code/extension/src/policy/client.ts`
- Test: `code/extension/tests/revoked.test.ts`

**Interfaces:**
- Produces: `handleRevoked(): Promise<void>` — clears enrolment, sets mode `personal`, sets `vg_revoked_notice = true`.
- Produces: `REVOKED_MESSAGE` — the exact copy the options page renders.

- [ ] **Step 1: Write the failing test**

```typescript
// code/extension/tests/revoked.test.ts
import { describe, it, expect, beforeEach } from 'vitest';

const store = new Map<string, unknown>();
(globalThis as any).chrome = {
  storage: { local: {
    get: async (k: string) => ({ [k]: store.get(k) }),
    set: async (o: Record<string, unknown>) => { for (const k in o) store.set(k, o[k]); },
    remove: async (keys: string[]) => { for (const k of keys) store.delete(k); },
  } },
};

import { handleRevoked, REVOKED_MESSAGE } from '../src/policy/revoked';
import { getMode } from '../src/mode/mode';

describe('handleRevoked', () => {
  beforeEach(() => {
    store.clear();
    store.set('vg_mode', 'enterprise');
    store.set('vg_enrolment', { org_name: 'Acme', pseudo_id: 'p1' });
    store.set('vg_policy', { version: 3, tools: [] });
  });

  it('forces Personal mode', async () => {
    await handleRevoked();
    expect(await getMode()).toBe('personal');
  });

  it('clears the enrolment and the cached policy', async () => {
    await handleRevoked();
    expect(store.get('vg_enrolment')).toBeUndefined();
    expect(store.get('vg_policy')).toBeUndefined();
  });

  it('raises the notice flag so the user is told once', async () => {
    await handleRevoked();
    expect(store.get('vg_revoked_notice')).toBe(true);
  });

  it('names the personal plan in the message', () => {
    expect(REVOKED_MESSAGE).toContain('no longer connected');
    expect(REVOKED_MESSAGE).toContain('protecting you personally');
  });
});
```

- [ ] **Step 2: Run and watch it fail**

Run: `cd code/extension && npm install && npx vitest run tests/revoked.test.ts`
Expected: FAIL — cannot resolve `../src/policy/revoked`

- [ ] **Step 3: Implement it**

```typescript
// code/extension/src/policy/revoked.ts
import { setMode } from '../mode/mode';
import { clearEnrolment } from './store';

export const REVOKED_MESSAGE =
  "You're no longer connected to an organisation. Vanguard is now protecting " +
  'you personally — upgrade for personal plan features.';

const K_NOTICE = 'vg_revoked_notice';

/** The server said this enrolment is revoked.
 *
 *  Drops to Personal rather than blocking. ADR 0014: a control that bricks
 *  the browser gets uninstalled, and then it protects nobody. The user keeps
 *  local protection and stops reporting — which is what "out of the org"
 *  actually means.
 */
export async function handleRevoked(): Promise<void> {
  await clearEnrolment();
  await setMode('personal');
  await chrome.storage.local.set({ [K_NOTICE]: true });
}

export async function takeRevokedNotice(): Promise<boolean> {
  const seen = (await chrome.storage.local.get(K_NOTICE))[K_NOTICE] === true;
  if (seen) await chrome.storage.local.set({ [K_NOTICE]: false });
  return seen;
}
```

- [ ] **Step 4: Run and watch it pass**

Run: `cd code/extension && npx vitest run tests/revoked.test.ts`
Expected: PASS (4 passed)

- [ ] **Step 5: Wire it into the policy client**

In `code/extension/src/policy/client.ts`, send `pseudo_id` on the policy fetch and call `handleRevoked()` on a 403:

```typescript
if (res.status === 403) {
  const body = await res.json().catch(() => null);
  if (body?.detail === 'enrolment revoked') { await handleRevoked(); return null; }
}
```

- [ ] **Step 6: Rebuild and check drift**

Run: `cd code/extension && npm run build && npm run check:dist`
Expected: both exit 0

- [ ] **Step 7: Commit**

```bash
git add code/extension/src/policy/revoked.ts code/extension/src/policy/client.ts code/extension/tests/revoked.test.ts code/extension/dist
git commit -m "feat(ext): a revoked enrolment drops to Personal with a notice"
```

### Task 1.6: Lock the mode switch and add the responsibility notice

**Files:**
- Modify: `code/extension/entrypoints/options/main.tsx`
- Test: `code/extension/tests/ui/options-mode-lock.test.tsx`

**Interfaces:**
- Consumes: `takeRevokedNotice()` from Task 1.5.
- Produces: `TOKEN_RESPONSIBILITY` — the copy rendered above the token input.

- [ ] **Step 1: Write the failing test**

```tsx
// code/extension/tests/ui/options-mode-lock.test.tsx
import { describe, it, expect } from 'vitest';
import { canSwitchToPersonal, TOKEN_RESPONSIBILITY } from '../../entrypoints/options/main';

describe('canSwitchToPersonal', () => {
  it('is blocked while enrolled', () => {
    expect(canSwitchToPersonal({ org_name: 'Acme' } as any)).toBe(false);
  });
  it('is allowed once the enrolment is gone', () => {
    expect(canSwitchToPersonal(null)).toBe(true);
  });
});

describe('TOKEN_RESPONSIBILITY', () => {
  it('tells the user activity is attributed to them', () => {
    expect(TOKEN_RESPONSIBILITY).toContain('private');
    expect(TOKEN_RESPONSIBILITY).toContain('attributed to you');
  });
});
```

- [ ] **Step 2: Run and watch it fail**

Run: `cd code/extension && npx vitest run tests/ui/options-mode-lock.test.tsx`
Expected: FAIL — exports do not exist

- [ ] **Step 3: Implement**

```tsx
// code/extension/entrypoints/options/main.tsx — add exports near the top

export const TOKEN_RESPONSIBILITY =
  'Keep this code private — activity recorded under it is attributed to you.';

/** Enterprise is a commitment, not a toggle: leaving requires the admin to
 *  revoke. Honest limit — the extension can still be removed in Chrome. */
export function canSwitchToPersonal(enrolment: Enrolment | null): boolean {
  return enrolment === null;
}
```

Render `TOKEN_RESPONSIBILITY` immediately above the token `<input>` in `Organisation()`, and gate the *Switch to Personal* button on `canSwitchToPersonal(enrolment)` with the disabled explanation *"Ask your admin to revoke your enrolment first."* Render `REVOKED_MESSAGE` at the top when `takeRevokedNotice()` returns true.

- [ ] **Step 4: Run and watch it pass**

Run: `cd code/extension && npx vitest run tests/ui/options-mode-lock.test.tsx`
Expected: PASS (3 passed)

- [ ] **Step 5: Rebuild, drift-check, full suite**

Run: `cd code/extension && npm run build && npm run check:dist && npx vitest run`
Expected: all exit 0

- [ ] **Step 6: Commit**

```bash
git add code/extension/entrypoints/options/main.tsx code/extension/tests/ui/options-mode-lock.test.tsx code/extension/dist
git commit -m "feat(ext): lock mode switch while enrolled; token responsibility notice"
```

## ✅ Piece 1 success criteria

| | Criterion | How to verify |
|---|---|---|
| 1 | Same token twice → **one** employee, same `pseudo_id` | `test_enrolment_identity.py` |
| 2 | Every new enrolment records `enroll_token_id` | `test_enrolment_identity.py` |
| 3 | Unused token dead after 7 days; **used token never expires** | `test_enrolment_identity.py` |
| 4 | Revoked → `/v1/events` **403**, `/v1/policy` with `pseudo_id` **403** | `test_deprovision.py` |
| 5 | `/v1/policy` without `pseudo_id` still 200 | `test_deprovision.py` |
| 6 | Revoked extension drops to Personal, shows the notice, **does not block prompts** | `revoked.test.ts` + manual |
| 7 | *Switch to Personal* disabled while enrolled | `options-mode-lock.test.tsx` |
| 8 | Responsibility copy sits above the token input | manual |
| 9 | Full policy suite green | `pytest -q` — **~18 min, do not kill** |
| 10 | Full extension suite green, `dist` in sync | `npx vitest run && npm run check:dist` |

**Manual check (both surfaces):** enrol → send a prompt → revoke in the console → within one poll the extension shows the notice, sits in Personal, **and the PII gate still works**.

> 🔴 **STOP. Report to the founder. Wait for go-ahead before Piece 2.**

---

# PIECE 2 — The console shows usage, enrolments and last active

### Task 2.1: Token statistics endpoint

**Files:**
- Create: `code/policy/app/token_stats.py`
- Modify: `code/policy/app/routes/dept.py:155`
- Test: `code/policy/tests/test_token_stats.py`

**Interfaces:**
- Produces: each `/v1/dept/tokens` row gains `status` (`"unused"|"used"|"revoked"`), `enrolments` (int), `times_used` (int), `last_active` (ISO string or `None`).

- [ ] **Step 1: Write the failing test**

```python
# code/policy/tests/test_token_stats.py
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_conn
from app.seed import seed_company, create_department, mint_employee_token
from app.token_stats import token_rows

client = TestClient(app)

def _world():
    conn = get_conn()
    org_id, _ = seed_company(conn, f"T-{uuid.uuid4().hex[:8]}")
    dept_id, _ = create_department(conn, org_id, "Engineering")
    return conn, org_id, dept_id

def test_unused_token_reports_unused():
    conn, org_id, dept_id = _world()
    mint_employee_token(conn, org_id, dept_id, "Engineering")
    row = token_rows(conn, org_id, dept_id)[0]
    assert row["status"] == "unused"
    assert row["enrolments"] == 0
    assert row["times_used"] == 0
    assert row["last_active"] is None

def test_used_token_reports_used():
    conn, org_id, dept_id = _world()
    token = mint_employee_token(conn, org_id, dept_id, "Engineering")
    client.post("/v1/enroll", json={"token": token})
    row = token_rows(conn, org_id, dept_id)[0]
    assert row["status"] == "used"
    assert row["enrolments"] == 1

def test_prompt_events_count_as_usage():
    conn, org_id, dept_id = _world()
    token = mint_employee_token(conn, org_id, dept_id, "Engineering")
    pseudo = client.post("/v1/enroll", json={"token": token}).json()["pseudo_id"]
    client.post("/v1/events", json={"pseudo_id": pseudo, "events": [
        {"host": "chatgpt.com", "type": "prompt_sent", "ts": "2026-08-05T10:00:00Z"},
        {"host": "chatgpt.com", "type": "prompt_sent", "ts": "2026-08-05T11:00:00Z"},
    ]})
    row = token_rows(conn, org_id, dept_id)[0]
    assert row["times_used"] == 2
    assert row["last_active"] == "2026-08-05T11:00:00Z"

def test_reinstall_does_not_split_the_count():
    """The whole reason the token is the identity."""
    conn, org_id, dept_id = _world()
    token = mint_employee_token(conn, org_id, dept_id, "Engineering")
    p1 = client.post("/v1/enroll", json={"token": token}).json()["pseudo_id"]
    p2 = client.post("/v1/enroll", json={"token": token}).json()["pseudo_id"]
    for p in (p1, p2):
        client.post("/v1/events", json={"pseudo_id": p, "events": [
            {"host": "chatgpt.com", "type": "prompt_sent", "ts": "2026-08-05T10:00:00Z"}]})
    row = token_rows(conn, org_id, dept_id)[0]
    assert row["enrolments"] == 1
    assert row["times_used"] == 2
```

- [ ] **Step 2: Run and watch it fail**

Run: `cd code/policy && .venv/Scripts/python -m pytest tests/test_token_stats.py -q`
Expected: FAIL — `ModuleNotFoundError: app.token_stats`

- [ ] **Step 3: Implement**

```python
# code/policy/app/token_stats.py
"""Per-token statistics for the Employee Tokens screen.

Everything aggregates on enroll_tokens.id, so a reinstall adds no row and
splits no count. I3: counts and timestamps only, never prompt text.
"""

_SQL = """
SELECT t.id, t.department, t.name, t.label, t.created_at, t.revoked,
       COUNT(DISTINCT e.id)                                        AS enrolments,
       COUNT(u.id) FILTER (WHERE u.type = 'prompt_sent')           AS times_used,
       MAX(u.ts)                                                   AS last_active
FROM enroll_tokens t
LEFT JOIN employees e    ON e.enroll_token_id = t.id
LEFT JOIN usage_events u ON u.employee_id = e.id
WHERE t.org_id = %s AND t.department_id = %s
GROUP BY t.id, t.department, t.name, t.label, t.created_at, t.revoked
ORDER BY t.created_at DESC
"""


def _status(revoked: int, enrolments: int) -> str:
    """Revoked wins: an admin acted, and that outranks history."""
    if revoked:
        return "revoked"
    return "used" if enrolments > 0 else "unused"


def token_rows(conn, org_id: str, department_id: str) -> list[dict]:
    rows = [dict(r) for r in conn.execute(_SQL, (org_id, department_id)).fetchall()]
    for row in rows:
        row["status"] = _status(row["revoked"], row["enrolments"])
    return rows
```

- [ ] **Step 4: Use it in the route**

```python
# code/policy/app/routes/dept.py — replace the body of dept_tokens()
@router.get("/tokens")
async def dept_tokens(vg_admin: str | None = Cookie(default=None)) -> list[dict]:
    org_id, dept_id = require_department(vg_admin)
    return token_rows(get_conn(), org_id, dept_id)
```

Import `from app.token_stats import token_rows`.

- [ ] **Step 5: Run and watch them pass**

Run: `cd code/policy && .venv/Scripts/python -m pytest tests/test_token_stats.py tests/test_dept_tokens.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add code/policy/app/token_stats.py code/policy/app/routes/dept.py code/policy/tests/test_token_stats.py
git commit -m "feat(policy): per-token usage, enrolments and last-active"
```

### Task 2.2: The Tokens screen shows the truth

**Files:**
- Create: `code/policy/admin/src/screens/token-status.ts`
- Modify: `code/policy/admin/src/screens/Tokens.tsx`
- Test: `code/policy/admin/src/screens/token-status.test.ts`

**Interfaces:**
- Produces: `statusPill(status) -> { label, className }` and `formatLastActive(iso | null) -> string`.

- [ ] **Step 1: Write the failing test**

```typescript
// code/policy/admin/src/screens/token-status.test.ts
import { describe, it, expect } from 'vitest';
import { statusPill, formatLastActive } from './token-status';

describe('statusPill', () => {
  it('flags an unused token so it can be chased', () => {
    expect(statusPill('unused').label).toBe('Unused');
    expect(statusPill('unused').className).toBe('pill warn');
  });
  it('shows used', () => { expect(statusPill('used').label).toBe('Used'); });
  it('shows revoked', () => { expect(statusPill('revoked').label).toBe('Revoked'); });
});

describe('formatLastActive', () => {
  it('says never when there is no activity', () => {
    expect(formatLastActive(null)).toBe('Never');
  });
  it('renders a date when there is', () => {
    expect(formatLastActive('2026-08-05T11:00:00Z')).not.toBe('Never');
  });
});
```

- [ ] **Step 2: Run and watch it fail**

Run: `cd code/policy/admin && npx vitest run src/screens/token-status.test.ts`
Expected: FAIL — cannot resolve `./token-status`

- [ ] **Step 3: Implement**

```typescript
// code/policy/admin/src/screens/token-status.ts
export type TokenStatus = 'unused' | 'used' | 'revoked';

/** "Active" used to mean "not revoked", which made an untouched token
 *  indistinguishable from one in daily use. These three are distinguishable. */
export function statusPill(status: TokenStatus): { label: string; className: string } {
  if (status === 'revoked') return { label: 'Revoked', className: 'pill revoked' };
  if (status === 'used') return { label: 'Used', className: 'pill active' };
  return { label: 'Unused', className: 'pill warn' };
}

export function formatLastActive(iso: string | null): string {
  return iso ? new Date(iso).toLocaleString() : 'Never';
}
```

- [ ] **Step 4: Run and watch it pass**

Run: `cd code/policy/admin && npx vitest run src/screens/token-status.test.ts`
Expected: PASS (5 passed)

- [ ] **Step 5: Wire into the table**

In `Tokens.tsx`, replace the Active/Revoked pill with `statusPill(row.status)` and add three columns — **Enrolments**, **Times used**, **Last active** (`formatLastActive(row.last_active)`). Keep the existing revocation note.

- [ ] **Step 6: Rebuild the console**

Run: `cd code/policy/admin && npm run build`
Expected: exit 0, `code/policy/app/static/` refreshed

🔴 **Restart uvicorn afterwards** — the static mount is decided once, at import time.

- [ ] **Step 7: Commit**

```bash
git add code/policy/admin/src/screens/ code/policy/app/static
git commit -m "feat(console): tokens screen shows unused/used, counts and last active"
```

### Task 2.3: Analytics groups by token

**Files:**
- Modify: `code/policy/app/analytics.py:62-64`
- Test: `code/policy/tests/test_analytics_by_token.py`

**Interfaces:**
- Produces: `top_employees` rows gain `token_id`; grouping moves from `e.id` to `COALESCE(e.enroll_token_id, e.id)`.

- [ ] **Step 1: Write the failing test**

```python
# code/policy/tests/test_analytics_by_token.py
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_conn
from app.analytics import analytics_summary
from app.seed import seed_company, create_department, mint_employee_token

client = TestClient(app)

def test_reinstall_is_one_row_not_two():
    conn = get_conn()
    org_id, _ = seed_company(conn, f"T-{uuid.uuid4().hex[:8]}")
    dept_id, _ = create_department(conn, org_id, "Engineering")
    token = mint_employee_token(conn, org_id, dept_id, "Engineering")

    p1 = client.post("/v1/enroll", json={"token": token}).json()["pseudo_id"]
    p2 = client.post("/v1/enroll", json={"token": token}).json()["pseudo_id"]
    for p in (p1, p2):
        client.post("/v1/events", json={"pseudo_id": p, "events": [
            {"host": "chatgpt.com", "type": "pii_block", "ts": "2026-08-05T10:00:00Z"}]})

    people = analytics_summary(conn, org_id, days=30, department_id=dept_id)["top_employees"]
    assert len(people) == 1, "one human appeared as two rows"
    assert people[0]["events"] == 2
```

- [ ] **Step 2: Run it — this one is expected to PASS immediately**

Run: `cd code/policy && .venv/Scripts/python -m pytest tests/test_analytics_by_token.py -q`
Expected: **PASS**, because Task 1.2 already made a reinstall reuse the employee row rather than create a second one.

🔴 **This is a regression test, not a red-green test, and that is deliberate.** It is the only executable statement that reinstalls must never split a person — the property Piece 1 delivered and Piece 2 depends on. If it ever goes red, something reintroduced duplicate employee rows. **Do not "fix" the code to make this step fail first.**

- [ ] **Step 3: Add `token_id` to the analytics output**

The grouping needs no change. The console does need the token id so Task 2.4 can label by it:

```python
    top_employees = q(
        f"SELECT {_NAME} AS name, e.department AS department, e.enroll_token_id AS token_id,"
        f" COUNT(*) AS events, SUM({WEIGHTS_SQL}) AS risk {base}"
        f" GROUP BY e.id, e.name, e.department, e.enroll_token_id"
        f" ORDER BY risk DESC, events DESC LIMIT 10")
```

- [ ] **Step 4: Run the analytics suite**

Run: `cd code/policy && .venv/Scripts/python -m pytest tests/test_analytics_summary.py tests/test_analytics_by_token.py -q`
Expected: PASS — including the existing summary tests, which must not regress on the added column

- [ ] **Step 5: Commit**

```bash
git add code/policy/app/analytics.py code/policy/tests/test_analytics_by_token.py
git commit -m "feat(policy): analytics carries token_id; reinstalls stay one row"
```

### Task 2.4: Risk screens label by token, not by asserted person

**Files:**
- Create: `code/policy/admin/src/screens/person-label.ts`
- Modify: `code/policy/admin/src/screens/InsiderRisk.tsx`
- Test: `code/policy/admin/src/screens/person-label.test.ts`

**Interfaces:**
- Produces: `personLabel(name, tokenId) -> string`.

- [ ] **Step 1: Write the failing test**

```typescript
// code/policy/admin/src/screens/person-label.test.ts
import { describe, it, expect } from 'vitest';
import { personLabel } from './person-label';

describe('personLabel', () => {
  it('shows the name with its token, because the token is what we know', () => {
    expect(personLabel('Alice Tan', 'tok_0001abcd')).toBe('Alice Tan (tok_0001)');
  });
  it('falls back to the token alone when unlabelled', () => {
    expect(personLabel(null, 'tok_0001abcd')).toBe('tok_0001');
  });
  it('handles pre-link rows with no token', () => {
    expect(personLabel('Alice Tan', null)).toBe('Alice Tan');
  });
});
```

- [ ] **Step 2: Run and watch it fail**

Run: `cd code/policy/admin && npx vitest run src/screens/person-label.test.ts`
Expected: FAIL — cannot resolve `./person-label`

- [ ] **Step 3: Implement**

```typescript
// code/policy/admin/src/screens/person-label.ts
/** The dashboard knows which TOKEN produced an event, not which human held
 *  it. Naming the token alongside the label keeps the screen from asserting
 *  more than the data supports — it matters most on the risk screens, where
 *  a row is close to an accusation. */
export function personLabel(name: string | null, tokenId: string | null): string {
  const short = tokenId ? tokenId.slice(0, 9) : null;
  if (name && short) return `${name} (${short})`;
  if (short) return short;
  return name ?? 'Unnamed';
}
```

- [ ] **Step 4: Run and watch it pass**

Run: `cd code/policy/admin && npx vitest run src/screens/person-label.test.ts`
Expected: PASS (3 passed)

- [ ] **Step 5: Use it in the risky-employee table**

In `InsiderRisk.tsx`, render `personLabel(row.name, row.token_id)` wherever the employee name is shown.

- [ ] **Step 6: Rebuild and commit**

```bash
cd code/policy/admin && npm run build
git add code/policy/admin/src/screens/ code/policy/app/static
git commit -m "feat(console): risk rows label by token alongside the name"
```

## ✅ Piece 2 success criteria

| | Criterion | How to verify |
|---|---|---|
| 1 | An unused token shows **Unused**, not "Active" | `test_token_stats.py` + console |
| 2 | Enrolling flips it to **Used** | `test_token_stats.py` |
| 3 | `times_used` counts `prompt_sent` events | `test_token_stats.py` |
| 4 | A reinstall adds **no** enrolment and splits **no** count | `test_token_stats.py`, `test_analytics_by_token.py` |
| 5 | `last_active` shows a date, or **Never** | `token-status.test.ts` |
| 6 | Risk rows read `Alice Tan (tok_0001)` | `person-label.test.ts` + console |
| 7 | Full policy suite green | `pytest -q` — **~18 min** |
| 8 | Console builds; **uvicorn restarted** | `npm run build`, restart, load `/` |

**Manual check:** mint two tokens, enrol one, send three prompts, reinstall and re-enrol with the same token. The screen must show **one** enrolment, **three** uses, and the second token as **Unused**.

> 🔴 **STOP. Report to the founder. Then write the Pieces 3–5 plan, informed by Piece 0's measurement.**

---

## Risks carried into the follow-up plan

1. **Blocking unapproved tools may relocate the leak.** Employees blocked in Chrome may use the vendor's desktop app or their phone — channels with no telemetry at all. The block is still right for a governance product; it must not be *sold* as "we stopped the leak."
2. **Approved ≠ protected.** Once Sarah can approve tools the extension cannot fully handle, the console must show protection level separately from policy status, or staff will assume cover they do not have.
3. **`/v1/policy` has no authentication.** Any holder of an `org_id` can read an org's tool policy. Task 1.4 adds an optional `pseudo_id` but does not close this. It belongs on the security-questionnaire list before any customer deployment.
4. **The awareness list needs permission to see tab addresses** — a real privacy step, and the mechanics are unverified. Needs its own spike before it is designed.
5. **Personal-mode prompt sharing puts the first real prompts into your systems**, which triggers the package's standing legal-review requirement. It is a privacy-policy and retention decision, not only code.
