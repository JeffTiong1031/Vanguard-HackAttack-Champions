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
| **3 — Generic protection + block unapproved** | ✅ Full detail | **Unblocked 2026-08-05 by U31 PASS** |
| **4 — Awareness + protection lists** | ✅ Full detail | Depends on Piece 3 |
| **5 — Feedback button** | ✅ Full detail | Rides on Piece 4's tool registry |

🔴 **Pieces 3–5 were withheld until Piece 0 reported, and it has.** **U31 PASSED 8/8** on 2026-08-05
(ASSUMPTIONS.md): `execCommand('insertText')` after `selectAll` was accepted and survived on all
eight surfaces, across **four distinct editor technologies** (ProseMirror ×2, Tiptap ×2, Quill ×1,
plain `textarea` ×2, one unidentified contenteditable), with send-through confirmed on ChatGPT and
Claude. **That licenses generic-first**, and Piece 3 below is written against it.

⚠️ **Carry U31's three narrowings into every task below.** **(1)** The read-back check **never
fired** — zero negatives in eight runs, so its failure-detection is **unexercised, not proven**;
Task 3.2 exists to give it a test. **(2)** Send-through was **2 of 8** — the other six proved DOM
insertion only. **(3)** One browser, one OS, one date — these move on the **D4** clock, which is
why Task 3.3 measures capability **at runtime** instead of trusting a table.

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

# PIECE 3 — Generic protection + blocking unapproved tools

**Depends on:** U31 (✅ PASS). **Does not depend on** Pieces 1–2 — it touches only the extension.

**The architecture U31 licenses.** One generic engine replaces the need for a hand-written adapter
per site. Detection was always site-independent (text in → findings out); what varies is the
**plumbing**, and U31 measured that the plumbing generalises. Four rungs, each independently
testable at runtime:

| Rung | Needs | Gives the user |
|---|---|---|
| 1 — read the box | find the composer | detection runs |
| 2 — catch the send | Enter / click / submit | we can **block** |
| 3 — write back | `execCommand` + read-back | we can **fix it for them** |
| 4 — see attachments | find the file input | file + PDF checking |

🔴 **The rule that makes this safe: silence must never mean "all clear."** A site where rung 1 or 2
fails must say *"Vanguard can't protect this page"* — an extension that sits there looking healthy
while seeing nothing is worse than no extension (doc 00 §6).

### Task 3.1: Generic composer locator and reader

**Files:**
- Create: `code/extension/src/adapters/generic-locate.ts`
- Test: `code/extension/tests/adapters/generic-locate.test.ts`

**Interfaces:**
- Produces: `trackFocus(): void` — installs the `focusin` listener. Call once at content-script start.
- Produces: `locateComposer(path?: EventTarget[]): { el: HTMLElement; kind: LocateKind } | null`
- Produces: `type LocateKind = 'event-path' | 'last-focused' | 'active' | 'query'`
- Produces: `readComposerText(el: HTMLElement): string`

- [ ] **Step 1: Write the failing test**

```typescript
// code/extension/tests/adapters/generic-locate.test.ts
import { describe, it, expect, beforeEach } from 'vitest';
import { trackFocus, locateComposer, readComposerText } from '../../src/adapters/generic-locate';

function mkEditable(id: string): HTMLElement {
  const el = document.createElement('div');
  el.id = id;
  el.setAttribute('contenteditable', 'true');
  // jsdom does not derive isContentEditable from the attribute.
  Object.defineProperty(el, 'isContentEditable', { value: true, configurable: true });
  document.body.append(el);
  return el;
}

describe('locateComposer', () => {
  beforeEach(() => { document.body.innerHTML = ''; trackFocus(); });

  it('returns null when the page has no editable at all', () => {
    expect(locateComposer()).toBeNull();
  });

  it('prefers the element in the event path over everything else', () => {
    mkEditable('decoy');
    const real = mkEditable('real');
    const found = locateComposer([real]);
    expect(found!.el.id).toBe('real');
    expect(found!.kind).toBe('event-path');
  });

  it('falls back to the last focused editable when no path is given', () => {
    mkEditable('decoy');
    const real = mkEditable('real');
    real.dispatchEvent(new FocusEvent('focusin', { bubbles: true }));
    const found = locateComposer();
    expect(found!.el.id).toBe('real');
    expect(found!.kind).toBe('last-focused');
  });

  it('reports kind "query" when it had to guess, so callers can distrust it', () => {
    mkEditable('only');
    const found = locateComposer();
    expect(found!.kind).toBe('query');
  });

  it('ignores a detached element that was focused then removed', () => {
    const el = mkEditable('gone');
    el.dispatchEvent(new FocusEvent('focusin', { bubbles: true }));
    el.remove();
    expect(locateComposer()).toBeNull();
  });
});

describe('readComposerText', () => {
  it('reads a textarea by value', () => {
    const ta = document.createElement('textarea');
    ta.value = 'hello';
    expect(readComposerText(ta)).toBe('hello');
  });
  it('reads a contenteditable by innerText', () => {
    const el = mkEditable('ce');
    el.innerText = 'world';
    expect(readComposerText(el)).toBe('world');
  });
});
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd code/extension && npx vitest run tests/adapters/generic-locate.test.ts`
Expected: FAIL — cannot resolve `../../src/adapters/generic-locate`

- [ ] **Step 3: Implement**

```typescript
// code/extension/src/adapters/generic-locate.ts
/** Finding the composer without a per-site adapter.
 *
 *  U31 measured that the WRITE generalises across ProseMirror, Tiptap, Quill
 *  and plain textareas. Locating is the other half, and its failure mode is
 *  worse: picking the wrong element looks identical to picking the right one.
 *  So every result carries HOW it was found, and callers treat a guess as a
 *  guess.
 */
export type LocateKind = 'event-path' | 'last-focused' | 'active' | 'query';

function isEditable(node: unknown): node is HTMLElement {
  if (node instanceof HTMLTextAreaElement) return true;
  if (node instanceof HTMLInputElement) return node.type === 'text';
  return node instanceof HTMLElement && node.isContentEditable;
}

let lastFocused: HTMLElement | null = null;

/** Install once at content-script start. Survives the user clicking away —
 *  which `document.activeElement` does not. */
export function trackFocus(): void {
  window.addEventListener(
    'focusin',
    (e) => { for (const n of e.composedPath()) if (isEditable(n)) { lastFocused = n; return; } },
    { capture: true },
  );
}

export function locateComposer(path?: EventTarget[]): { el: HTMLElement; kind: LocateKind } | null {
  if (path) for (const n of path) if (isEditable(n) && n.isConnected) return { el: n, kind: 'event-path' };
  if (lastFocused?.isConnected) return { el: lastFocused, kind: 'last-focused' };
  if (isEditable(document.activeElement)) return { el: document.activeElement, kind: 'active' };
  const guess = document.querySelector('[contenteditable="true"], textarea');
  return isEditable(guess) ? { el: guess, kind: 'query' } : null;
}

export function readComposerText(el: HTMLElement): string {
  if (el instanceof HTMLTextAreaElement || el instanceof HTMLInputElement) return el.value;
  return el.innerText;
}
```

- [ ] **Step 4: Run it and watch it pass**

Run: `cd code/extension && npx vitest run tests/adapters/generic-locate.test.ts`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add code/extension/src/adapters/generic-locate.ts code/extension/tests/adapters/generic-locate.test.ts
git commit -m "feat(ext): generic composer locator with provenance"
```

### Task 3.2: Verified generic write-back

**Files:**
- Create: `code/extension/src/adapters/generic-write.ts`
- Test: `code/extension/tests/adapters/generic-write.test.ts`

**Interfaces:**
- Consumes: `readComposerText` from Task 3.1.
- Produces: `writeVerified(el, text): Promise<WriteResult>` where
  `type WriteResult = { ok: true } | { ok: false; reason: 'refused' | 'reverted' | 'detached' }`

🔴 **This task exists because U31's read-back never fired.** Eight surfaces all succeeded, so the
failure path has never run. These tests are the first exercise it gets — the revert and detach cases
are simulated here precisely because no real site produced them.

- [ ] **Step 1: Write the failing test**

```typescript
// code/extension/tests/adapters/generic-write.test.ts
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { writeVerified } from '../../src/adapters/generic-write';

function textarea(initial = ''): HTMLTextAreaElement {
  const el = document.createElement('textarea');
  el.value = initial;
  document.body.append(el);
  return el;
}

/** Stand-in for the browser's editing pipeline. jsdom has no execCommand. */
function stubExec(behaviour: (cmd: string, arg?: string) => boolean) {
  (document as any).execCommand = vi.fn((cmd: string, _ui?: boolean, arg?: string) =>
    behaviour(cmd, arg));
}

describe('writeVerified', () => {
  beforeEach(() => { document.body.innerHTML = ''; });

  it('reports ok when the text lands and stays', async () => {
    const el = textarea('old');
    stubExec((cmd, arg) => { if (cmd === 'insertText') el.value = arg ?? ''; return true; });
    expect(await writeVerified(el, 'new')).toEqual({ ok: true });
    expect(el.value).toBe('new');
  });

  it('reports refused when the browser rejects the insert', async () => {
    const el = textarea('old');
    stubExec(() => false);
    expect(await writeVerified(el, 'new')).toEqual({ ok: false, reason: 'refused' });
  });

  it('reports reverted when a framework puts the old value back', async () => {
    const el = textarea('old');
    stubExec((cmd, arg) => {
      if (cmd === 'insertText') { el.value = arg ?? ''; queueMicrotask(() => { el.value = 'old'; }); }
      return true;
    });
    expect(await writeVerified(el, 'new')).toEqual({ ok: false, reason: 'reverted' });
  });

  it('reports detached when the node is replaced rather than edited', async () => {
    const el = textarea('old');
    stubExec((cmd, arg) => {
      if (cmd === 'insertText') { el.value = arg ?? ''; queueMicrotask(() => el.remove()); }
      return true;
    });
    expect(await writeVerified(el, 'new')).toEqual({ ok: false, reason: 'detached' });
  });

  it('never reports ok on text it did not verify', async () => {
    const el = textarea('old');
    stubExec(() => true);          // claims success, changes nothing
    const r = await writeVerified(el, 'new');
    expect(r.ok).toBe(false);
  });
});
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd code/extension && npx vitest run tests/adapters/generic-write.test.ts`
Expected: FAIL — cannot resolve `../../src/adapters/generic-write`

- [ ] **Step 3: Implement**

```typescript
// code/extension/src/adapters/generic-write.ts
import { readComposerText } from './generic-locate';

export type WriteResult = { ok: true } | { ok: false; reason: 'refused' | 'reverted' | 'detached' };

/** Replace the composer's contents through the BROWSER's editing pipeline.
 *
 *  U31: accepted on ProseMirror, Tiptap, Quill and plain textareas, because the
 *  site's own framework sees a normal edit rather than an outside mutation.
 *  `execCommand` is deprecated and deliberate — no modern API produces a
 *  trusted-looking edit from an extension.
 *
 *  🔴 The verification is the point, not the write. A controlled editor that
 *  rejects an outside change re-renders from its own state, so the revert is
 *  observable. Never report ok on an unverified write: the caller mints a
 *  send-approval token from this result, and a false ok sends the ORIGINAL text.
 */
export async function writeVerified(el: HTMLElement, text: string): Promise<WriteResult> {
  el.focus();
  document.execCommand('selectAll', false, undefined);
  if (!document.execCommand('insertText', false, text)) return { ok: false, reason: 'refused' };

  // Two frames: a controlled editor reverts on its next render.
  await new Promise<void>((r) => requestAnimationFrame(() => requestAnimationFrame(() => r())));

  if (!el.isConnected) return { ok: false, reason: 'detached' };
  return readComposerText(el) === text ? { ok: true } : { ok: false, reason: 'reverted' };
}
```

- [ ] **Step 4: Run it and watch it pass**

Run: `cd code/extension && npx vitest run tests/adapters/generic-write.test.ts`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add code/extension/src/adapters/generic-write.ts code/extension/tests/adapters/generic-write.test.ts
git commit -m "feat(ext): verified generic write-back, never ok without proof"
```

### Task 3.3: Runtime capability probe

**Files:**
- Create: `code/extension/src/adapters/capability.ts`
- Test: `code/extension/tests/adapters/capability.test.ts`

**Interfaces:**
- Consumes: `locateComposer` (3.1).
- Produces: `type Rungs = { read: boolean; send: boolean; write: boolean; files: boolean }`
- Produces: `type ProtectionLevel = 'full' | 'basic' | 'none'`
- Produces: `levelFor(rungs: Rungs): ProtectionLevel`
- Produces: `probeRungs(deps): Rungs`

🔴 **Measured at runtime, not read from a table.** U31's result is one browser on one date; sites
redeploy (D4). A capability table in code goes stale silently — a probe cannot.

- [ ] **Step 1: Write the failing test**

```typescript
// code/extension/tests/adapters/capability.test.ts
import { describe, it, expect } from 'vitest';
import { levelFor, probeRungs } from '../../src/adapters/capability';

const R = (o: Partial<Record<'read'|'send'|'write'|'files', boolean>> = {}) =>
  ({ read: false, send: false, write: false, files: false, ...o });

describe('levelFor', () => {
  it('is none without a readable composer', () => {
    expect(levelFor(R({ write: true, files: true }))).toBe('none');
  });
  it('is none when sends cannot be caught — detection we cannot act on is not protection', () => {
    expect(levelFor(R({ read: true, write: true }))).toBe('none');
  });
  it('is basic when we can read and block but not rewrite', () => {
    expect(levelFor(R({ read: true, send: true }))).toBe('basic');
  });
  it('is basic when rewriting works but attachments are invisible', () => {
    expect(levelFor(R({ read: true, send: true, write: true }))).toBe('basic');
  });
  it('is full only with all four rungs', () => {
    expect(levelFor(R({ read: true, send: true, write: true, files: true }))).toBe('full');
  });
});

describe('probeRungs', () => {
  it('reports read false when no composer is found', () => {
    const r = probeRungs({ locate: () => null, hasFileInput: () => false });
    expect(r.read).toBe(false);
    expect(r.write).toBe(false);
  });
  it('does not claim write on a guessed composer', () => {
    const el = document.createElement('textarea');
    const r = probeRungs({ locate: () => ({ el, kind: 'query' }), hasFileInput: () => true });
    expect(r.read).toBe(true);
    expect(r.write).toBe(false);
  });
  it('claims write on a confidently located composer', () => {
    const el = document.createElement('textarea');
    const r = probeRungs({ locate: () => ({ el, kind: 'last-focused' }), hasFileInput: () => true });
    expect(r.write).toBe(true);
    expect(r.files).toBe(true);
  });
});
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd code/extension && npx vitest run tests/adapters/capability.test.ts`
Expected: FAIL — cannot resolve `../../src/adapters/capability`

- [ ] **Step 3: Implement**

```typescript
// code/extension/src/adapters/capability.ts
import type { LocateKind } from './generic-locate';

export type Rungs = { read: boolean; send: boolean; write: boolean; files: boolean };
export type ProtectionLevel = 'full' | 'basic' | 'none';

/** `send` is always true where the gate is installed: a `window` capture
 *  listener is browser behaviour, not site behaviour (U12-a). It is a field
 *  rather than a constant so a surface that defeats the gate can set it false
 *  without changing every call site. */
export function probeRungs(deps: {
  locate: () => { el: HTMLElement; kind: LocateKind } | null;
  hasFileInput: () => boolean;
}): Rungs {
  const found = deps.locate();
  const read = found !== null;
  // A guessed composer is not a basis for rewriting. Masking the wrong element
  // is worse than not masking: the user sees a clean box and sends dirty text.
  const confident = found !== null && found.kind !== 'query';
  return { read, send: read, write: confident, files: deps.hasFileInput() };
}

export function levelFor(rungs: Rungs): ProtectionLevel {
  if (!rungs.read || !rungs.send) return 'none';
  return rungs.write && rungs.files ? 'full' : 'basic';
}
```

- [ ] **Step 4: Run it and watch it pass**

Run: `cd code/extension && npx vitest run tests/adapters/capability.test.ts`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add code/extension/src/adapters/capability.ts code/extension/tests/adapters/capability.test.ts
git commit -m "feat(ext): runtime capability probe, measured not tabulated"
```

### Task 3.4: Generic adapter, and the registry falls back to it

**Files:**
- Create: `code/extension/src/adapters/generic.ts`
- Modify: `code/extension/src/adapters/registry.ts`
- Test: `code/extension/tests/adapters/registry-fallback.test.ts`

**Interfaces:**
- Consumes: `locateComposer`, `readComposerText` (3.1); `writeVerified` (3.2).
- Produces: `genericAdapter: SurfaceAdapter` conforming to `src/adapters/types.ts`.
- Produces: `pickAdapter(hostname)` **never returns null** for a governed host — it returns
  `genericAdapter` when no hand-written adapter exists.

- [ ] **Step 1: Write the failing test**

```typescript
// code/extension/tests/adapters/registry-fallback.test.ts
import { describe, it, expect } from 'vitest';
import { pickAdapter } from '../../src/adapters/registry';

describe('pickAdapter', () => {
  it('keeps the hand-written adapter for chatgpt.com', () => {
    expect(pickAdapter('chatgpt.com').host).toBe('chatgpt.com');
  });
  it('keeps the hand-written adapter for claude.ai', () => {
    expect(pickAdapter('claude.ai').host).toBe('claude.ai');
  });
  it('falls back to generic on a site with no hand-written adapter', () => {
    expect(pickAdapter('gemini.google.com').host).toBe('*');
  });
  it('never returns null — an unrecognised host still gets the generic engine', () => {
    expect(pickAdapter('some-new-ai.example')).not.toBeNull();
  });
});
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd code/extension && npx vitest run tests/adapters/registry-fallback.test.ts`
Expected: FAIL — `pickAdapter('gemini.google.com')` returns `null`

- [ ] **Step 3: Implement the generic adapter**

```typescript
// code/extension/src/adapters/generic.ts
import type { SurfaceAdapter } from './types';
import { locateComposer, readComposerText } from './generic-locate';
import { writeVerified } from './generic-write';

/** Sites with no hand-written adapter.
 *
 *  U31 (8/8, four editor technologies) is why this is the default rather than
 *  a last resort. A hand-written adapter now earns its place only where this
 *  engine measurably falls short — which the capability probe reports.
 */
export const genericAdapter: SurfaceAdapter = {
  host: '*',
  getComposer: (path) => locateComposer(path)?.el ?? null,
  readText: (path) => {
    const found = locateComposer(path);
    return found ? readComposerText(found.el) : null;
  },
  writeText: (text, target) => {
    const el = target ?? locateComposer()?.el ?? null;
    // Fire-and-forget at this interface; callers needing the verdict call
    // writeVerified directly (Task 3.6 does, for the clipboard fallback).
    if (el) void writeVerified(el, text);
  },
  isSendControl: (path) =>
    path.some((n) =>
      n instanceof HTMLElement &&
      /send|submit/i.test(
        [n.getAttribute('aria-label'), n.getAttribute('title'), n.getAttribute('data-testid')]
          .filter(Boolean).join(' '),
      ),
    ),
  onPaste: (cb) => {
    window.addEventListener('paste', (e) => {
      const text = (e as ClipboardEvent).clipboardData?.getData('text');
      if (text) cb(text);
    }, { capture: true });
  },
  fileInputs: () => [...document.querySelectorAll('input[type="file"]')] as HTMLInputElement[],
};
```

- [ ] **Step 4: Change the registry**

```typescript
// code/extension/src/adapters/registry.ts — replace the whole file
import type { SurfaceAdapter } from './types';
import { chatgptAdapter } from './chatgpt';
import { claudeAdapter } from './claude';
import { genericAdapter } from './generic';

/** Never null. Before U31 a missing adapter meant no protection at all; now it
 *  means the generic engine, and the capability probe reports what that buys
 *  on this particular page. */
export function pickAdapter(hostname: string): SurfaceAdapter {
  if (hostname.endsWith('chatgpt.com')) return chatgptAdapter;
  if (hostname.endsWith('claude.ai')) return claudeAdapter;
  return genericAdapter;
}
```

⚠️ `entrypoints/content.ts` currently does `const adapter = pickAdapter(...); if (!adapter) return;`
That early return is now dead and must go — leaving it is harmless but misleading. Remove those two
lines in this task.

- [ ] **Step 5: Run and watch them pass**

Run: `cd code/extension && npx vitest run tests/adapters/`
Expected: PASS

- [ ] **Step 6: Rebuild, drift-check, full suite**

Run: `cd code/extension && npm run build && npm run check:dist && npx vitest run`
Expected: all exit 0

- [ ] **Step 7: Commit**

```bash
git add code/extension/src/adapters/ code/extension/tests/adapters/ code/extension/entrypoints/content.ts code/extension/dist
git commit -m "feat(ext): generic adapter is the default, registry never returns null"
```

### Task 3.5: "Vanguard can't protect this page"

**Files:**
- Create: `code/extension/src/ui/unprotected-banner.ts`
- Test: `code/extension/tests/unprotected-banner.test.ts`

**Interfaces:**
- Consumes: `ProtectionLevel` (3.3).
- Produces: `showUnprotected(reason: string): void`, `hideUnprotected(): void`
- Produces: `UNPROTECTED_MESSAGE`

- [ ] **Step 1: Write the failing test**

```typescript
// code/extension/tests/unprotected-banner.test.ts
import { describe, it, expect, beforeEach } from 'vitest';
import { showUnprotected, hideUnprotected, UNPROTECTED_MESSAGE } from '../src/ui/unprotected-banner';

const host = () => document.querySelector('[data-vanguard-ui="unprotected"]');

describe('unprotected banner', () => {
  beforeEach(() => { document.body.innerHTML = ''; });

  it('says plainly that the page is not protected', () => {
    expect(UNPROTECTED_MESSAGE).toContain("can't protect");
  });
  it('mounts in a shadow root so page CSS cannot hide it', () => {
    showUnprotected('no composer found');
    expect(host()!.shadowRoot).not.toBeNull();
  });
  it('shows the reason so a bug report is actionable', () => {
    showUnprotected('no composer found');
    expect(host()!.shadowRoot!.textContent).toContain('no composer found');
  });
  it('does not stack duplicates', () => {
    showUnprotected('a'); showUnprotected('b');
    expect(document.querySelectorAll('[data-vanguard-ui="unprotected"]').length).toBe(1);
  });
  it('hides cleanly', () => {
    showUnprotected('a'); hideUnprotected();
    expect(host()).toBeNull();
  });
});
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd code/extension && npx vitest run tests/unprotected-banner.test.ts`
Expected: FAIL — cannot resolve `../src/ui/unprotected-banner`

- [ ] **Step 3: Implement**

```typescript
// code/extension/src/ui/unprotected-banner.ts
export const UNPROTECTED_MESSAGE =
  "Vanguard can't protect this page. Nothing you type here is being checked.";

const ATTR = 'data-vanguard-ui';

/** The one banner that must never be quiet.
 *
 *  doc 00 §6: a control that appears to work while seeing nothing is the worst
 *  failure for a compliance buyer, because the audit trail says it worked.
 *  An extension icon sitting there calmly IS that failure. Say it on the page.
 */
export function showUnprotected(reason: string): void {
  hideUnprotected();
  const host = document.createElement('div');
  host.setAttribute(ATTR, 'unprotected');
  host.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:2147483647';
  const root = host.attachShadow({ mode: 'open' });
  root.innerHTML = `
    <style>
      :host { all: initial; }
      .bar { box-sizing:border-box; width:100%; padding:10px 16px;
             background:#fef2f2; border-bottom:2px solid #dc2626; color:#7f1d1d;
             font:600 13px/1.4 system-ui, sans-serif; }
      .why { font-weight:400; color:#991b1b; }
    </style>
    <div class="bar" role="alert">
      ${UNPROTECTED_MESSAGE} <span class="why"></span>
    </div>`;
  root.querySelector('.why')!.textContent = `(${reason})`;
  (document.body || document.documentElement).append(host);
}

export function hideUnprotected(): void {
  document.querySelector(`[${ATTR}="unprotected"]`)?.remove();
}
```

- [ ] **Step 4: Run and watch it pass**

Run: `cd code/extension && npx vitest run tests/unprotected-banner.test.ts`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add code/extension/src/ui/unprotected-banner.ts code/extension/tests/unprotected-banner.test.ts
git commit -m "feat(ext): say so when the page cannot be protected"
```

### Task 3.6: Clipboard fallback when write-back fails

**Files:**
- Create: `code/extension/src/ui/rewrite-fallback.ts`
- Test: `code/extension/tests/rewrite-fallback.test.ts`

**Interfaces:**
- Consumes: `WriteResult` (3.2).
- Produces: `applyRewrite(el, text, deps): Promise<'written' | 'clipboard' | 'failed'>`

🔴 **The rung-3 degradation.** When the site rejects our rewrite, the user must still get the clean
text — the protection is not lost, only the convenience. What must **never** happen is minting a
send-approval token after a failed write: that sends the original.

- [ ] **Step 1: Write the failing test**

```typescript
// code/extension/tests/rewrite-fallback.test.ts
import { describe, it, expect, vi } from 'vitest';
import { applyRewrite } from '../src/ui/rewrite-fallback';

const el = () => document.createElement('textarea');

describe('applyRewrite', () => {
  it('reports written when the composer accepted it', async () => {
    const copy = vi.fn();
    const r = await applyRewrite(el(), 'clean', {
      write: async () => ({ ok: true as const }), copy, notify: vi.fn(),
    });
    expect(r).toBe('written');
    expect(copy).not.toHaveBeenCalled();
  });

  it('falls back to the clipboard when the editor reverted', async () => {
    const copy = vi.fn().mockResolvedValue(undefined);
    const notify = vi.fn();
    const r = await applyRewrite(el(), 'clean', {
      write: async () => ({ ok: false as const, reason: 'reverted' as const }), copy, notify,
    });
    expect(r).toBe('clipboard');
    expect(copy).toHaveBeenCalledWith('clean');
    expect(notify).toHaveBeenCalled();
  });

  it('reports failed — never silent — when the clipboard also fails', async () => {
    const r = await applyRewrite(el(), 'clean', {
      write: async () => ({ ok: false as const, reason: 'refused' as const }),
      copy: async () => { throw new Error('denied'); }, notify: vi.fn(),
    });
    expect(r).toBe('failed');
  });

  it('tells the user what to do, not just that something broke', async () => {
    const notify = vi.fn();
    await applyRewrite(el(), 'clean', {
      write: async () => ({ ok: false as const, reason: 'detached' as const }),
      copy: vi.fn().mockResolvedValue(undefined), notify,
    });
    expect(notify.mock.calls[0][0]).toMatch(/paste/i);
  });
});
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd code/extension && npx vitest run tests/rewrite-fallback.test.ts`
Expected: FAIL — cannot resolve `../src/ui/rewrite-fallback`

- [ ] **Step 3: Implement**

```typescript
// code/extension/src/ui/rewrite-fallback.ts
import type { WriteResult } from '../adapters/generic-write';

export type RewriteOutcome = 'written' | 'clipboard' | 'failed';

/** What happens when the site refuses our rewrite.
 *
 *  The masked text still exists and the user should still get it — protection
 *  degrades to one extra paste, not to nothing. The caller must NOT mint a
 *  send-approval token unless this returns 'written': on 'clipboard' the
 *  composer still holds the ORIGINAL text.
 */
export async function applyRewrite(
  el: HTMLElement,
  text: string,
  deps: {
    write: (el: HTMLElement, text: string) => Promise<WriteResult>;
    copy: (text: string) => Promise<void>;
    notify: (message: string) => void;
  },
): Promise<RewriteOutcome> {
  const result = await deps.write(el, text);
  if (result.ok) return 'written';

  try {
    await deps.copy(text);
    deps.notify(
      "This site wouldn't accept the edit. The cleaned text is on your clipboard — " +
        'select everything in the box and paste it before sending.',
    );
    return 'clipboard';
  } catch {
    deps.notify(
      "This site wouldn't accept the edit and the clipboard is unavailable. " +
        'Please remove the highlighted text yourself before sending.',
    );
    return 'failed';
  }
}
```

- [ ] **Step 4: Run and watch it pass**

Run: `cd code/extension && npx vitest run tests/rewrite-fallback.test.ts`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add code/extension/src/ui/rewrite-fallback.ts code/extension/tests/rewrite-fallback.test.ts
git commit -m "feat(ext): clipboard fallback when a site rejects the rewrite"
```

### Task 3.7: Block sends on unapproved tools

**Files:**
- Create: `code/extension/src/policy/enforcement.ts`
- Test: `code/extension/tests/policy-enforcement.test.ts`

**Interfaces:**
- Consumes: `Policy`, `Tool` from `src/policy/types`; `toolForHost` from `src/policy/lookup`.
- Produces: `type SendDecision = 'allow' | 'block-unapproved' | 'review'`
- Produces: `decideSend(args): SendDecision`

🔴 **This is a policy block, not a failure mode — it does not contradict ADR 0014.** ADR 0014 governs
what happens when the *engine* dies (degrade to advisory). Deliberately blocking a tool the
organisation has not approved is the product working. Personal mode never blocks on tool policy.

- [ ] **Step 1: Write the failing test**

```typescript
// code/extension/tests/policy-enforcement.test.ts
import { describe, it, expect } from 'vitest';
import { decideSend } from '../src/policy/enforcement';

const approved = { llm_id: 'x', display_name: 'X', status: 'approved' as const, hosts: ['x.com'] };
const blocked = { ...approved, status: 'blocked' as const };

describe('decideSend', () => {
  it('blocks an unapproved tool in enterprise mode', () => {
    expect(decideSend({ enterprise: true, tool: blocked, dirty: false })).toBe('block-unapproved');
  });
  it('blocks it even when the prompt is clean — the tool is the problem', () => {
    expect(decideSend({ enterprise: true, tool: blocked, dirty: false })).toBe('block-unapproved');
  });
  it('reviews a dirty prompt on an approved tool', () => {
    expect(decideSend({ enterprise: true, tool: approved, dirty: true })).toBe('review');
  });
  it('allows a clean prompt on an approved tool', () => {
    expect(decideSend({ enterprise: true, tool: approved, dirty: false })).toBe('allow');
  });
  it('never blocks on tool policy in personal mode', () => {
    expect(decideSend({ enterprise: false, tool: blocked, dirty: false })).toBe('allow');
  });
  it('still reviews sensitive content in personal mode', () => {
    expect(decideSend({ enterprise: false, tool: blocked, dirty: true })).toBe('review');
  });
  it('does not block a host that is not a governed tool at all', () => {
    expect(decideSend({ enterprise: true, tool: null, dirty: false })).toBe('allow');
  });
  it('fails OPEN on tool policy when the policy is unknown', () => {
    expect(decideSend({ enterprise: true, tool: undefined, dirty: false })).toBe('allow');
  });
});
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd code/extension && npx vitest run tests/policy-enforcement.test.ts`
Expected: FAIL — cannot resolve `../src/policy/enforcement`

- [ ] **Step 3: Implement**

```typescript
// code/extension/src/policy/enforcement.ts
import type { Tool } from './types';

export type SendDecision = 'allow' | 'block-unapproved' | 'review';

/** Tool policy first, content second.
 *
 *  An unapproved tool is blocked whether or not the prompt is sensitive: the
 *  organisation's objection is to the destination. Content review only matters
 *  once the destination is permitted.
 *
 *  🔴 `tool === undefined` means we do not KNOW the policy (worker restarting,
 *  never enrolled, cache cold). That fails OPEN, per ADR 0014 — a cold cache
 *  must not lock someone out of a tool their org approved.
 */
export function decideSend(args: {
  enterprise: boolean;
  tool: Tool | null | undefined;
  dirty: boolean;
}): SendDecision {
  if (args.enterprise && args.tool && args.tool.status !== 'approved') return 'block-unapproved';
  return args.dirty ? 'review' : 'allow';
}
```

- [ ] **Step 4: Run and watch it pass**

Run: `cd code/extension && npx vitest run tests/policy-enforcement.test.ts`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add code/extension/src/policy/enforcement.ts code/extension/tests/policy-enforcement.test.ts
git commit -m "feat(ext): block sends on unapproved tools, fail open when policy unknown"
```

### Task 3.8: Wire it into the content script

**Files:**
- Modify: `code/extension/entrypoints/content.ts`
- Modify: `code/extension/entrypoints/guard.content.ts`
- Test: `code/extension/tests/content-wiring.test.ts`

**Interfaces:**
- Consumes: everything from 3.1–3.7.

- [ ] **Step 1: Write the failing test**

```typescript
// code/extension/tests/content-wiring.test.ts
import { describe, it, expect } from 'vitest';
import { levelFor } from '../src/adapters/capability';
import { decideSend } from '../src/policy/enforcement';

/** The two seams the content script must honour, asserted together because
 *  their INTERACTION is what a reviewer cannot see in either unit test. */
describe('content-script contract', () => {
  it('an unprotectable page never silently allows a dirty send', () => {
    const level = levelFor({ read: false, send: false, write: false, files: false });
    expect(level).toBe('none');
    // With level 'none' the script must show the banner; it cannot review,
    // because it cannot read. The banner is the only honest output.
  });

  it('a basic page still blocks an unapproved tool', () => {
    const level = levelFor({ read: true, send: true, write: false, files: false });
    expect(level).toBe('basic');
    expect(decideSend({
      enterprise: true,
      tool: { llm_id: 'g', display_name: 'G', status: 'blocked', hosts: ['g.com'] },
      dirty: false,
    })).toBe('block-unapproved');
  });

  it('blocking a tool does not require the ability to rewrite', () => {
    // Rung 3 absent, rung 2 present: enforcement still works.
    const level = levelFor({ read: true, send: true, write: false, files: false });
    expect(level).not.toBe('none');
  });
});
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd code/extension && npx vitest run tests/content-wiring.test.ts`
Expected: FAIL until 3.1–3.7 are present; PASS once they are (this task's job is the wiring below).

- [ ] **Step 3: Wire the content script**

In `entrypoints/content.ts`:
1. Call `trackFocus()` **synchronously at the top of `main()`**, before `installGate` — it must be
   listening before the user's first click. It adds one listener and cannot delay gate registration.
2. After `pickAdapter`, remove the `if (!adapter) return;` early return (now unreachable).
3. After mode resolution, run `probeRungs` and `levelFor`. On `'none'`, call
   `showUnprotected(reason)` and **do not** register the review flow.
4. In `onBlocked`, consult `decideSend`. On `'block-unapproved'`, show the block UI with the
   Request Access action instead of the content review modal.
5. Where the modal's `onProceed` currently calls `adapter.writeText(finalText, blockedComposer)`,
   route through `applyRewrite`. **Mint the approval token only when it returns `'written'`.** On
   `'clipboard'` or `'failed'`, leave the modal open and do not approve.

In `entrypoints/guard.content.ts`: leave the warn banner for advisory cases, but when the tool is
unapproved and mode is enterprise, the block in `content.ts` is now the enforcement point — the
banner becomes the explanation, not the control.

- [ ] **Step 4: Run the full suite**

Run: `cd code/extension && npx vitest run`
Expected: PASS

- [ ] **Step 5: Rebuild and drift-check**

Run: `cd code/extension && npm run build && npm run check:dist`
Expected: both exit 0

- [ ] **Step 6: Commit**

```bash
git add code/extension/entrypoints/ code/extension/tests/content-wiring.test.ts code/extension/dist
git commit -m "feat(ext): wire generic protection, capability gating and tool blocking"
```

## ✅ Piece 3 success criteria

| | Criterion | How to verify |
|---|---|---|
| 1 | Composer located on all eight surfaces, provenance recorded | `generic-locate.test.ts` + manual |
| 2 | Write-back verified; **never** reports ok without proof | `generic-write.test.ts` (5 cases incl. revert + detach) |
| 3 | Capability measured at runtime, not tabulated | `capability.test.ts` |
| 4 | `pickAdapter` never returns null | `registry-fallback.test.ts` |
| 5 | Unprotectable page shows the banner — **never silent** | `unprotected-banner.test.ts` + manual |
| 6 | Failed rewrite → clipboard + instruction; **no approval token minted** | `rewrite-fallback.test.ts` |
| 7 | Unapproved tool blocks sends in enterprise; personal never blocks on tool policy | `policy-enforcement.test.ts` |
| 8 | Unknown policy fails **open** | `policy-enforcement.test.ts` |
| 9 | Full extension suite green, `dist` in sync | `npx vitest run && npm run check:dist` |

**Manual check, on at least Gemini and one other non-adapter surface:** type an IC → it is detected
→ Send is blocked → the rewrite lands (or the clipboard fallback fires with an instruction) → you
press Send yourself. Then set that tool to blocked in the console and confirm sends stop entirely.

> 🔴 **STOP. Report to the founder. Wait for go-ahead before Piece 4.**

---

# PIECE 4 — Awareness and protection lists, server-driven

**Depends on:** Piece 3. **The distinction that makes this cheap:** knowing a site is an AI tool
costs a string comparison; *reading* that site costs a scary permission. So the lists are different
sizes and are fed by the same queue.

| | What it is | Permission cost | Size |
|---|---|---|---|
| **Awareness** | hostnames to compare against | tab address only | hundreds |
| **Protection** | sites the extension may read and modify | the install prompt | ~20 |

⚠️ **The manifest still bounds everything.** The server can activate any host **already declared**;
a never-declared host needs a release. Declare generously (~20) so activation is usually a row.

### Task 4.1: `ai_tools` registry table and read endpoint

**Files:**
- Modify: `code/policy/app/db.py` (append to `_COLUMN_ADDS` / add DDL following the `notifications` pattern)
- Create: `code/policy/app/routes/tools_registry.py`
- Test: `code/policy/tests/test_tools_registry.py`

**Interfaces:**
- Produces: table `ai_tools(id, hostname UNIQUE, display_name, tier, added_at)` where
  `tier IN ('awareness','protection')`.
- Produces: `GET /v1/tools/registry` → `{"awareness": [hostname…], "protection": [hostname…]}`.
  **Unauthenticated and org-independent** — it is a product catalogue, not tenant data.

- [ ] **Step 1: Write the failing test**

```python
# code/policy/tests/test_tools_registry.py
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_conn

client = TestClient(app)

def test_registry_returns_both_tiers():
    r = client.get("/v1/tools/registry")
    assert r.status_code == 200
    body = r.json()
    assert "awareness" in body and "protection" in body
    assert isinstance(body["awareness"], list)

def test_protection_hosts_also_appear_in_awareness():
    """A protected tool is by definition a known tool; a client comparing only
    against the awareness list must not miss it."""
    body = client.get("/v1/tools/registry").json()
    assert set(body["protection"]).issubset(set(body["awareness"]))

def test_a_new_awareness_row_shows_up_without_a_release():
    conn = get_conn()
    host = f"t-{uuid.uuid4().hex[:8]}.example"
    conn.execute(
        "INSERT INTO ai_tools (id, hostname, display_name, tier, added_at)"
        " VALUES (%s, %s, %s, 'awareness', NOW())",
        (uuid.uuid4().hex, host, "Test Tool"),
    )
    conn.commit()
    assert host in client.get("/v1/tools/registry").json()["awareness"]

def test_registry_needs_no_session():
    """It is a catalogue, not tenant data — an unenrolled client must be able
    to read it, or a Personal user gets no awareness list at all."""
    assert client.get("/v1/tools/registry").status_code == 200
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd code/policy && .venv/Scripts/python -m pytest tests/test_tools_registry.py -q`
Expected: FAIL — 404, the route does not exist

- [ ] **Step 3: Add the table**

Follow `_NOTIFICATIONS_DDL`'s pattern in `app/db.py`:

```python
_AI_TOOLS_DDL = """
CREATE TABLE IF NOT EXISTS ai_tools (
    id           TEXT PRIMARY KEY,
    hostname     TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    tier         TEXT NOT NULL DEFAULT 'awareness',
    added_at     TEXT NOT NULL
);
"""
```

Execute it from `migrate_schema()` alongside the notifications DDL, and seed the eight known hosts
from `app/seed.py`'s `REGISTRY` at tier `protection` using `ON CONFLICT DO NOTHING`.

- [ ] **Step 4: Add the route**

```python
# code/policy/app/routes/tools_registry.py
"""The AI-tool catalogue. Product data, not tenant data — deliberately
unauthenticated so Personal-mode clients can read it too."""
from fastapi import APIRouter

from app.deps import get_conn

router = APIRouter()


@router.get("/v1/tools/registry")
async def registry() -> dict[str, list[str]]:
    rows = get_conn().execute("SELECT hostname, tier FROM ai_tools ORDER BY hostname").fetchall()
    awareness = [r["hostname"] for r in rows]
    protection = [r["hostname"] for r in rows if r["tier"] == "protection"]
    # Protection ⊆ awareness by construction: a client that only holds the
    # awareness list must never be blind to a tool we actively protect.
    return {"awareness": awareness, "protection": protection}
```

Register it in `app/main.py` alongside the other routers.

- [ ] **Step 5: Run and watch them pass**

Run: `cd code/policy && .venv/Scripts/python -m pytest tests/test_tools_registry.py -q`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add code/policy/app/db.py code/policy/app/routes/tools_registry.py code/policy/app/main.py code/policy/app/seed.py code/policy/tests/test_tools_registry.py
git commit -m "feat(policy): server-driven AI tool registry with two tiers"
```

### Task 4.2: Extension consumes the registry

**Files:**
- Create: `code/extension/src/policy/registry-cache.ts`
- Test: `code/extension/tests/registry-cache.test.ts`

**Interfaces:**
- Produces: `fetchRegistry(base): Promise<Registry | null>`, `getCachedRegistry(): Promise<Registry>`,
  `classifyHost(registry, hostname): 'protected' | 'known' | 'unknown'`
- Produces: `type Registry = { awareness: string[]; protection: string[] }`

- [ ] **Step 1: Write the failing test**

```typescript
// code/extension/tests/registry-cache.test.ts
import { describe, it, expect } from 'vitest';
import { classifyHost } from '../src/policy/registry-cache';

const reg = { awareness: ['a.com', 'b.com', 'c.com'], protection: ['a.com'] };

describe('classifyHost', () => {
  it('protected when the extension can actually read the site', () => {
    expect(classifyHost(reg, 'a.com')).toBe('protected');
  });
  it('known when we recognise it but cannot inspect it', () => {
    expect(classifyHost(reg, 'b.com')).toBe('known');
  });
  it('unknown when it is on neither list', () => {
    expect(classifyHost(reg, 'zzz.com')).toBe('unknown');
  });
  it('matches subdomains, since providers move their app to one', () => {
    expect(classifyHost(reg, 'chat.a.com')).toBe('protected');
  });
  it('does not match a lookalike suffix', () => {
    expect(classifyHost(reg, 'evil-a.com')).toBe('unknown');
  });
  it('treats an empty registry as unknown rather than throwing', () => {
    expect(classifyHost({ awareness: [], protection: [] }, 'a.com')).toBe('unknown');
  });
});
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd code/extension && npx vitest run tests/registry-cache.test.ts`
Expected: FAIL — cannot resolve `../src/policy/registry-cache`

- [ ] **Step 3: Implement**

```typescript
// code/extension/src/policy/registry-cache.ts
export type Registry = { awareness: string[]; protection: string[] };

const KEY = 'vg_tool_registry';
const EMPTY: Registry = { awareness: [], protection: [] };

/** Suffix match on a DOT boundary. `evil-a.com` must not match `a.com` —
 *  a lookalike domain is exactly how someone would dodge the list. */
function hostMatches(hostname: string, entry: string): boolean {
  return hostname === entry || hostname.endsWith(`.${entry}`);
}

export function classifyHost(reg: Registry, hostname: string): 'protected' | 'known' | 'unknown' {
  if (reg.protection.some((e) => hostMatches(hostname, e))) return 'protected';
  if (reg.awareness.some((e) => hostMatches(hostname, e))) return 'known';
  return 'unknown';
}

export async function fetchRegistry(base: string): Promise<Registry | null> {
  try {
    const res = await fetch(`${base}/v1/tools/registry`);
    if (!res.ok) return null;
    const reg = (await res.json()) as Registry;
    await chrome.storage.local.set({ [KEY]: reg });
    return reg;
  } catch {
    return null;   // cached copy keeps working (ADR 0014)
  }
}

export async function getCachedRegistry(): Promise<Registry> {
  return ((await chrome.storage.local.get(KEY))[KEY] as Registry | undefined) ?? EMPTY;
}
```

- [ ] **Step 4: Run and watch it pass**

Run: `cd code/extension && npx vitest run tests/registry-cache.test.ts`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add code/extension/src/policy/registry-cache.ts code/extension/tests/registry-cache.test.ts
git commit -m "feat(ext): cache the tool registry, classify hosts by tier"
```

### Task 4.3: Declare the wider host list and handle awareness-only sites

**Files:**
- Modify: `code/extension/wxt.config.ts` (host permissions + content-script matches)
- Modify: `code/extension/entrypoints/guard.content.ts`
- Test: `code/extension/tests/awareness-handling.test.ts`

**Interfaces:**
- Consumes: `classifyHost` (4.2), `showUnprotected` (3.5).
- Produces: `awarenessAction(classification, enterprise, approved): 'protect' | 'warn-unprotected' | 'ignore'`

- [ ] **Step 1: Write the failing test**

```typescript
// code/extension/tests/awareness-handling.test.ts
import { describe, it, expect } from 'vitest';
import { awarenessAction } from '../src/policy/awareness';

describe('awarenessAction', () => {
  it('protects a site we can actually read', () => {
    expect(awarenessAction('protected', true, true)).toBe('protect');
  });
  it('warns on a known-but-unreadable AI tool rather than staying silent', () => {
    expect(awarenessAction('known', true, false)).toBe('warn-unprotected');
  });
  it('still warns on a known tool even if the org approved it — we cannot cover it', () => {
    expect(awarenessAction('known', true, true)).toBe('warn-unprotected');
  });
  it('ignores an ordinary website', () => {
    expect(awarenessAction('unknown', true, false)).toBe('ignore');
  });
  it('warns in personal mode too — the user deserves to know', () => {
    expect(awarenessAction('known', false, false)).toBe('warn-unprotected');
  });
});
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd code/extension && npx vitest run tests/awareness-handling.test.ts`
Expected: FAIL — cannot resolve `../src/policy/awareness`

- [ ] **Step 3: Implement**

```typescript
// code/extension/src/policy/awareness.ts
/** What to do about a site we know of but may not be able to read.
 *
 *  The silent case is the one to avoid: a recognised AI tool where the
 *  extension does nothing looks exactly like a protected one. Approval status
 *  does not change this — an org approving a tool we cannot inspect does not
 *  give us the ability to inspect it, and pretending otherwise is the
 *  approved-≠-protected trap.
 */
export function awarenessAction(
  classification: 'protected' | 'known' | 'unknown',
  _enterprise: boolean,
  _approved: boolean,
): 'protect' | 'warn-unprotected' | 'ignore' {
  if (classification === 'protected') return 'protect';
  if (classification === 'known') return 'warn-unprotected';
  return 'ignore';
}
```

- [ ] **Step 4: Widen the manifest**

In `wxt.config.ts`, extend `host_permissions` and the guard content script's `matches` from the
current eight to a declared set of ~20 known AI tools. Keep the existing eight first, then add
others you can name today. **Do not use `<all_urls>`** — a named list of AI tools is defensible on a
security questionnaire; blanket access is not.

- [ ] **Step 5: Run the suite, rebuild, drift-check**

Run: `cd code/extension && npx vitest run && npm run build && npm run check:dist`
Expected: all exit 0

- [ ] **Step 6: Commit**

```bash
git add code/extension/src/policy/awareness.ts code/extension/tests/awareness-handling.test.ts code/extension/wxt.config.ts code/extension/dist
git commit -m "feat(ext): awareness tier warns instead of staying silent"
```

### Task 4.4: Admin manages the registry

**Files:**
- Modify: `code/policy/app/routes/admin.py`
- Create: `code/policy/admin/src/screens/ToolRegistry.tsx`
- Modify: `code/policy/admin/src/main.tsx`
- Test: `code/policy/tests/test_registry_admin.py`

**Interfaces:**
- Produces: `POST /v1/admin/tools/registry {hostname, display_name, tier}` → 201; company role only.
- Produces: `POST /v1/admin/tools/registry/{id}/tier {tier}` → 200.

- [ ] **Step 1: Write the failing test**

```python
# code/policy/tests/test_registry_admin.py
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_conn
from app.seed import seed_company

client = TestClient(app)

def _company_session():
    conn = get_conn()
    _, secret = seed_company(conn, f"T-{uuid.uuid4().hex[:8]}")
    client.post("/v1/admin/login", json={"role": "company", "secret": secret})
    return conn

def test_company_admin_can_add_an_awareness_host():
    _company_session()
    host = f"t-{uuid.uuid4().hex[:8]}.example"
    r = client.post("/v1/admin/tools/registry",
                    json={"hostname": host, "display_name": "T", "tier": "awareness"})
    assert r.status_code == 201
    assert host in client.get("/v1/tools/registry").json()["awareness"]

def test_adding_a_duplicate_hostname_is_rejected_not_duplicated():
    _company_session()
    host = f"t-{uuid.uuid4().hex[:8]}.example"
    client.post("/v1/admin/tools/registry", json={"hostname": host, "display_name": "T", "tier": "awareness"})
    r = client.post("/v1/admin/tools/registry", json={"hostname": host, "display_name": "T", "tier": "awareness"})
    assert r.status_code == 409

def test_unauthenticated_cannot_add():
    client.post("/v1/admin/logout")
    r = client.post("/v1/admin/tools/registry",
                    json={"hostname": "x.example", "display_name": "X", "tier": "awareness"})
    assert r.status_code == 401
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd code/policy && .venv/Scripts/python -m pytest tests/test_registry_admin.py -q`
Expected: FAIL — 404

- [ ] **Step 3: Implement the routes**

Add to `app/routes/admin.py`, following the existing `require_company(vg_admin)` pattern used by
`create_department_route`. Return **409** on a unique-constraint violation rather than letting the
psycopg2 error surface as a 500.

- [ ] **Step 4: Add the console screen**

`ToolRegistry.tsx`: table of hostname / display name / tier, an add form, and a tier toggle. Register
it in `main.tsx` under the company role's **Management** category. 🔴 Show a plain warning next to
any host at tier `awareness`: *"Vanguard can warn on this tool but cannot inspect prompts on it
until a release adds it."*

- [ ] **Step 5: Run, rebuild the console**

Run: `cd code/policy && .venv/Scripts/python -m pytest tests/test_registry_admin.py -q`
then `cd admin && npm run build`
Expected: PASS, build exits 0. 🔴 **Restart uvicorn** — the static mount is decided at import time.

- [ ] **Step 6: Commit**

```bash
git add code/policy/app/routes/admin.py code/policy/admin/src/ code/policy/tests/test_registry_admin.py code/policy/app/static
git commit -m "feat(console): manage the AI tool registry"
```

## ✅ Piece 4 success criteria

| | Criterion | How to verify |
|---|---|---|
| 1 | Registry serves both tiers; protection ⊆ awareness | `test_tools_registry.py` |
| 2 | Registry readable without a session (Personal needs it) | `test_tools_registry.py` |
| 3 | A new awareness row reaches clients with **no release** | `test_tools_registry.py` + manual |
| 4 | Subdomains match; lookalike domains do **not** | `registry-cache.test.ts` |
| 5 | A known-but-unreadable tool **warns** rather than staying silent | `awareness-handling.test.ts` |
| 6 | Approved ≠ protected is visible to the admin | manual, console |
| 7 | Duplicate hostname → 409, not 500 | `test_registry_admin.py` |
| 8 | Manifest declares a **named list**, never `<all_urls>` | inspect `wxt.config.ts` |

> 🔴 **STOP. Report to the founder. Wait for go-ahead before Piece 5.**

---

# PIECE 5 — The feedback button

**Depends on:** Piece 4 (the registry is where tool requests land).

**Two functions, and they have very different privacy weights:**

| | Sends | Personal | Enterprise |
|---|---|---|---|
| **Report a wrong detection** | the prompt text + what was wrong | ✅ works | **only if the org opted in** |
| **Request tool support** | a hostname + reason | ✅ direct to Vanguard | via their admin |

🔴 **Founder decision, 2026-08-05: prompt sharing is PERSONAL-MODE ONLY by default.** In Personal
mode the user *is* the data owner — their consent is the consent that matters, no DPA needed. In
Enterprise, the employee cannot consent on their employer's behalf, so the **organisation** must opt
in first and the button is inert until it does.

⚠️ **This is the first real prompt text entering Vanguard's systems.** It triggers the package's
standing legal-review requirement (ADR 0015 / U25): privacy-policy wording, a stated purpose, and a
retention period. **Those are deliverables outside this plan** — the code must not ship enabled
without them.

### Task 5.1: Feedback payload rules

**Files:**
- Create: `code/extension/src/feedback/payload.ts`
- Test: `code/extension/tests/feedback-payload.test.ts`

**Interfaces:**
- Produces: `canSharePrompt(mode, orgOptIn): boolean`
- Produces: `buildDetectionFeedback(args): DetectionFeedback`
- Produces: `type DetectionFeedback = { kind: 'detection'; cls: string; wrongWay: 'false-alarm' | 'missed'; promptText?: string }`

- [ ] **Step 1: Write the failing test**

```typescript
// code/extension/tests/feedback-payload.test.ts
import { describe, it, expect } from 'vitest';
import { canSharePrompt, buildDetectionFeedback } from '../src/feedback/payload';

describe('canSharePrompt', () => {
  it('allows it in personal mode with no toggle', () => {
    expect(canSharePrompt('personal', false)).toBe(true);
  });
  it('forbids it in enterprise when the org has not opted in', () => {
    expect(canSharePrompt('enterprise', false)).toBe(false);
  });
  it('allows it in enterprise once the org opted in', () => {
    expect(canSharePrompt('enterprise', true)).toBe(true);
  });
});

describe('buildDetectionFeedback', () => {
  it('carries the prompt when sharing is allowed', () => {
    const f = buildDetectionFeedback({
      cls: 'PERSON', wrongWay: 'false-alarm', promptText: 'call Ahmad', allowed: true });
    expect(f.promptText).toBe('call Ahmad');
  });

  it('OMITS the prompt entirely when sharing is not allowed', () => {
    const f = buildDetectionFeedback({
      cls: 'PERSON', wrongWay: 'false-alarm', promptText: 'call Ahmad', allowed: false });
    expect(f.promptText).toBeUndefined();
    expect(JSON.stringify(f)).not.toContain('Ahmad');
  });

  it('never emits an empty-string prompt, which would look like consent to send nothing', () => {
    const f = buildDetectionFeedback({
      cls: 'NRIC', wrongWay: 'missed', promptText: '', allowed: true });
    expect(f.promptText).toBeUndefined();
  });

  it('keeps the class and direction regardless — that is the useful signal', () => {
    const f = buildDetectionFeedback({
      cls: 'ORG', wrongWay: 'missed', promptText: 'x', allowed: false });
    expect(f.cls).toBe('ORG');
    expect(f.wrongWay).toBe('missed');
  });
});
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd code/extension && npx vitest run tests/feedback-payload.test.ts`
Expected: FAIL — cannot resolve `../src/feedback/payload`

- [ ] **Step 3: Implement**

```typescript
// code/extension/src/feedback/payload.ts
import type { Mode } from '../mode/mode';

export type DetectionFeedback = {
  kind: 'detection';
  cls: string;
  wrongWay: 'false-alarm' | 'missed';
  promptText?: string;
};

/** Personal: the user owns the data, so their click is sufficient.
 *  Enterprise: the prompt is the EMPLOYER's, and an employee cannot consent on
 *  their behalf — the organisation opts in first, or nothing is sent. */
export function canSharePrompt(mode: Mode, orgOptIn: boolean): boolean {
  return mode === 'personal' ? true : orgOptIn;
}

/** The field is absent, not empty, when sharing is disallowed. An empty string
 *  would still serialise a `promptText` key and read as "the user shared
 *  nothing" rather than "sharing was never permitted". */
export function buildDetectionFeedback(args: {
  cls: string;
  wrongWay: 'false-alarm' | 'missed';
  promptText: string;
  allowed: boolean;
}): DetectionFeedback {
  const base: DetectionFeedback = { kind: 'detection', cls: args.cls, wrongWay: args.wrongWay };
  if (args.allowed && args.promptText.length > 0) base.promptText = args.promptText;
  return base;
}
```

- [ ] **Step 4: Run and watch it pass**

Run: `cd code/extension && npx vitest run tests/feedback-payload.test.ts`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add code/extension/src/feedback/payload.ts code/extension/tests/feedback-payload.test.ts
git commit -m "feat(ext): feedback payload rules, prompt omitted unless permitted"
```

### Task 5.2: Feedback endpoints

**Files:**
- Create: `code/policy/app/routes/feedback.py`
- Modify: `code/policy/app/models.py`
- Modify: `code/policy/app/db.py`
- Test: `code/policy/tests/test_feedback.py`

**Interfaces:**
- Produces: `POST /v1/feedback/tool {hostname, reason}` → 201
- Produces: `POST /v1/feedback/detection {cls, wrong_way, prompt_text?}` → 201
- Produces: tables `tool_requests(id, hostname, reason, requested_at, status)` and
  `detection_feedback(id, cls, wrong_way, prompt_text, created_at)`.

🔴 **`detection_feedback` is the only table in this service that may hold prompt text.** It gets its
own table and its own retention clock. It must never be joined into `usage_events`.

- [ ] **Step 1: Write the failing test**

```python
# code/policy/tests/test_feedback.py
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_conn

client = TestClient(app)

def test_tool_request_is_recorded():
    host = f"t-{uuid.uuid4().hex[:8]}.example"
    r = client.post("/v1/feedback/tool", json={"hostname": host, "reason": "team uses it"})
    assert r.status_code == 201
    row = get_conn().execute(
        "SELECT hostname FROM tool_requests WHERE hostname = %s", (host,)).fetchone()
    assert row is not None

def test_detection_feedback_without_prompt_text_is_accepted():
    r = client.post("/v1/feedback/detection", json={"cls": "PERSON", "wrong_way": "false-alarm"})
    assert r.status_code == 201

def test_detection_feedback_with_prompt_text_is_accepted():
    r = client.post("/v1/feedback/detection",
                    json={"cls": "PERSON", "wrong_way": "false-alarm", "prompt_text": "call Ahmad"})
    assert r.status_code == 201

def test_unknown_field_is_rejected_not_stored():
    """extra='forbid' — the same defence /v1/events uses."""
    r = client.post("/v1/feedback/detection",
                    json={"cls": "PERSON", "wrong_way": "missed", "employee_email": "a@b.com"})
    assert r.status_code == 422

def test_the_422_body_does_not_echo_the_rejected_value():
    r = client.post("/v1/feedback/detection",
                    json={"cls": "PERSON", "wrong_way": "missed", "secret_field": "hunter2"})
    assert r.status_code == 422
    assert "hunter2" not in r.text

def test_prompt_text_never_lands_in_usage_events():
    client.post("/v1/feedback/detection",
                json={"cls": "NRIC", "wrong_way": "missed", "prompt_text": "IC 880101-14-5566"})
    cols = {r["column_name"] for r in get_conn().execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'usage_events'"
    ).fetchall()}
    assert not any("prompt" in c or "text" in c for c in cols)
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd code/policy && .venv/Scripts/python -m pytest tests/test_feedback.py -q`
Expected: FAIL — 404

- [ ] **Step 3: Implement**

Add both DDL blocks to `db.py` following `_NOTIFICATIONS_DDL`. Add pydantic models to `models.py`
with `extra="forbid"` (matching `UsageEvent`). Create `routes/feedback.py` and register it in
`main.py`.

🔴 **In the models, validators must describe the RULE, never quote the input** — the app-wide 422
handler strips `input` and `ctx`, but `msg` passes through untouched.

- [ ] **Step 4: Run and watch them pass**

Run: `cd code/policy && .venv/Scripts/python -m pytest tests/test_feedback.py -q`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add code/policy/app/routes/feedback.py code/policy/app/models.py code/policy/app/db.py code/policy/app/main.py code/policy/tests/test_feedback.py
git commit -m "feat(policy): feedback endpoints, prompt text isolated to its own table"
```

### Task 5.3: The org opt-in switch

**Files:**
- Modify: `code/policy/app/db.py` (`_COLUMN_ADDS`: `orgs.feedback_sharing_enabled`)
- Modify: `code/policy/app/routes/admin.py`
- Modify: `code/policy/app/routes/policy_read.py`
- Test: `code/policy/tests/test_feedback_optin.py`

**Interfaces:**
- Produces: `orgs.feedback_sharing_enabled INTEGER NOT NULL DEFAULT 0` — **off by default**.
- Produces: `POST /v1/admin/feedback-sharing {enabled: bool}` — company role only.
- Produces: the flag on the policy body the extension already polls.

- [ ] **Step 1: Write the failing test**

```python
# code/policy/tests/test_feedback_optin.py
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_conn
from app.seed import seed_company

client = TestClient(app)

def test_sharing_is_off_by_default():
    conn = get_conn()
    org_id, _ = seed_company(conn, f"T-{uuid.uuid4().hex[:8]}")
    row = conn.execute(
        "SELECT feedback_sharing_enabled FROM orgs WHERE id = %s", (org_id,)).fetchone()
    assert row["feedback_sharing_enabled"] == 0

def test_company_admin_can_turn_it_on():
    conn = get_conn()
    org_id, secret = seed_company(conn, f"T-{uuid.uuid4().hex[:8]}")
    client.post("/v1/admin/login", json={"role": "company", "secret": secret})
    assert client.post("/v1/admin/feedback-sharing", json={"enabled": True}).status_code == 200
    row = conn.execute(
        "SELECT feedback_sharing_enabled FROM orgs WHERE id = %s", (org_id,)).fetchone()
    assert row["feedback_sharing_enabled"] == 1

def test_the_flag_reaches_the_extension_through_policy():
    conn = get_conn()
    org_id, secret = seed_company(conn, f"T-{uuid.uuid4().hex[:8]}")
    client.post("/v1/admin/login", json={"role": "company", "secret": secret})
    client.post("/v1/admin/feedback-sharing", json={"enabled": True})
    body = client.get(f"/v1/policy?org_id={org_id}").json()
    assert body["feedback_sharing_enabled"] is True
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd code/policy && .venv/Scripts/python -m pytest tests/test_feedback_optin.py -q`
Expected: FAIL — column does not exist

- [ ] **Step 3: Implement**

Append to `_COLUMN_ADDS`:

```python
    ("orgs", "feedback_sharing_enabled",
     "ALTER TABLE orgs ADD COLUMN IF NOT EXISTS feedback_sharing_enabled INTEGER NOT NULL DEFAULT 0"),
```

Add the route to `admin.py` (company role), add the field to `PolicyBody` in `models.py`, and read it
in `policy_read.py`. **Every policy write calls `bump_policy_version()`** — this one included, or
clients never see the change.

- [ ] **Step 4: Run and watch them pass**

Run: `cd code/policy && .venv/Scripts/python -m pytest tests/test_feedback_optin.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add code/policy/app/db.py code/policy/app/routes/admin.py code/policy/app/routes/policy_read.py code/policy/app/models.py code/policy/tests/test_feedback_optin.py
git commit -m "feat(policy): org opt-in for prompt sharing, off by default"
```

### Task 5.4: The feedback UI

**Files:**
- Create: `code/extension/src/ui/feedback-dialog.tsx`
- Modify: `code/extension/entrypoints/content.ts`
- Test: `code/extension/tests/feedback-dialog.test.tsx`

**Interfaces:**
- Consumes: `canSharePrompt`, `buildDetectionFeedback` (5.1).
- Produces: `FeedbackDialog` (Preact), `SHARING_NOTICE`.

- [ ] **Step 1: Write the failing test**

```tsx
// code/extension/tests/feedback-dialog.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/preact';
import { FeedbackDialog, SHARING_NOTICE } from '../src/ui/feedback-dialog';

describe('FeedbackDialog', () => {
  it('shows an EDITABLE copy of the prompt, so the user can trim it', () => {
    render(<FeedbackDialog mode="personal" orgOptIn={false} promptText="my IC is 880101"
                           onSend={() => {}} onClose={() => {}} />);
    const box = screen.getByLabelText(/what you will send/i) as HTMLTextAreaElement;
    expect(box.value).toBe('my IC is 880101');
    expect(box.readOnly).toBe(false);
  });

  it('states what happens to the text', () => {
    expect(SHARING_NOTICE).toMatch(/improve detection/i);
    expect(SHARING_NOTICE).toMatch(/confidential/i);
  });

  it('hides the prompt box entirely when the org has not opted in', () => {
    render(<FeedbackDialog mode="enterprise" orgOptIn={false} promptText="secret"
                           onSend={() => {}} onClose={() => {}} />);
    expect(screen.queryByLabelText(/what you will send/i)).toBeNull();
  });

  it('explains WHY it is unavailable rather than just hiding it', () => {
    render(<FeedbackDialog mode="enterprise" orgOptIn={false} promptText="secret"
                           onSend={() => {}} onClose={() => {}} />);
    expect(screen.getByText(/your organisation/i)).toBeTruthy();
  });

  it('sends what the user edited, not the original', async () => {
    let sent: any = null;
    render(<FeedbackDialog mode="personal" orgOptIn={false} promptText="original"
                           onSend={(p) => { sent = p; }} onClose={() => {}} />);
    const box = screen.getByLabelText(/what you will send/i) as HTMLTextAreaElement;
    box.value = 'edited';
    box.dispatchEvent(new Event('input', { bubbles: true }));
    (screen.getByRole('button', { name: /send/i }) as HTMLButtonElement).click();
    expect(sent.promptText).toBe('edited');
  });
});
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd code/extension && npx vitest run tests/feedback-dialog.test.tsx`
Expected: FAIL — cannot resolve `../src/ui/feedback-dialog`

- [ ] **Step 3: Implement**

Build the Preact dialog in a shadow root (same pattern as `src/ui/modal.tsx`). It must:
- Render an **editable** `<textarea>` pre-filled with the prompt, labelled *"What you will send"*
- Render `SHARING_NOTICE` beneath it
- Omit the textarea entirely when `canSharePrompt(mode, orgOptIn)` is false, replacing it with an
  explanation naming the organisation as the reason
- Always offer the **Request tool support** action, which never sends prompt text

```typescript
export const SHARING_NOTICE =
  "We'll use this to improve detection. Don't include anything confidential to your employer.";
```

- [ ] **Step 4: Run and watch it pass**

Run: `cd code/extension && npx vitest run tests/feedback-dialog.test.tsx`
Expected: PASS (5 passed)

- [ ] **Step 5: Wire it in, rebuild, drift-check**

Add a **Report** affordance to the review modal and a **Request tool support** action to the
unprotected banner (3.5) and the block screen (3.7).

Run: `cd code/extension && npx vitest run && npm run build && npm run check:dist`
Expected: all exit 0

- [ ] **Step 6: Commit**

```bash
git add code/extension/src/ui/feedback-dialog.tsx code/extension/tests/feedback-dialog.test.tsx code/extension/entrypoints/content.ts code/extension/dist
git commit -m "feat(ext): feedback dialog - editable share, tool requests"
```

## ✅ Piece 5 success criteria

| | Criterion | How to verify |
|---|---|---|
| 1 | Personal mode shares without a toggle | `feedback-payload.test.ts` |
| 2 | Enterprise **cannot** share unless the org opted in | `feedback-payload.test.ts`, `test_feedback_optin.py` |
| 3 | Org sharing is **off by default** | `test_feedback_optin.py` |
| 4 | Prompt field is **absent**, not empty, when disallowed | `feedback-payload.test.ts` |
| 5 | The user sees and can **edit** exactly what is sent | `feedback-dialog.test.tsx` |
| 6 | Unknown fields → 422, and the 422 body does not echo the value | `test_feedback.py` |
| 7 | Prompt text lives only in `detection_feedback` | `test_feedback.py` |
| 8 | Tool requests carry a hostname, never prompt text | `test_feedback.py` |
| 9 | Full suites green both sides; `dist` in sync | `pytest -q`, `npx vitest run`, `check:dist` |

> 🔴 **Before this ships enabled:** privacy-policy wording, a stated purpose, and a retention period
> for `detection_feedback` (ADR 0015 / U25). **Code complete ≠ safe to enable.**

---

## Risks carried into the follow-up plan

1. **Blocking unapproved tools may relocate the leak.** Employees blocked in Chrome may use the vendor's desktop app or their phone — channels with no telemetry at all. The block is still right for a governance product; it must not be *sold* as "we stopped the leak."
2. **Approved ≠ protected.** Once Sarah can approve tools the extension cannot fully handle, the console must show protection level separately from policy status, or staff will assume cover they do not have.
3. **`/v1/policy` has no authentication.** Any holder of an `org_id` can read an org's tool policy. Task 1.4 adds an optional `pseudo_id` but does not close this. It belongs on the security-questionnaire list before any customer deployment.
4. **The awareness list needs permission to see tab addresses** — a real privacy step, and the mechanics are unverified. Needs its own spike before it is designed.
5. **Personal-mode prompt sharing puts the first real prompts into your systems**, which triggers the package's standing legal-review requirement. It is a privacy-policy and retention decision, not only code.
