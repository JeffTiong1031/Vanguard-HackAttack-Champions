# Approved Prompt Restoration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn an approved ethics appeal into a safe, visible, one-time prompt restoration on ChatGPT and Claude, while protecting newer work and requiring the employee to press Send.

**Architecture:** The policy service owns an atomic one-time claim. The extension background worker owns a session-only draft vault, decision polling, tab routing, and persistent notifications. Content scripts own verified composer restoration, status toasts, and the synchronous send gate; they receive raw text only for the selected local restoration action.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, PostgreSQL, pytest, TypeScript, WXT Manifest V3, Chrome `storage.session`/`alarms`/`notifications`/`tabs`, Vitest, jsdom, ChatGPT and Claude adapters.

**Design source:** `docs/superpowers/specs/2026-08-06-approved-prompt-restoration-design.md`

## Global Constraints

- The employee always presses Send; no extension code may submit a provider form or click a provider Send control.
- Raw prompt text remains in `chrome.storage.session` for at most 24 hours and does not survive a full Chrome exit.
- Raw prompt text reaches the policy service only when the employee explicitly selects **Include the exact text**.
- The background service worker is the sole storage owner. Content scripts receive one selected draft through typed messages; they cannot enumerate session storage.
- The unpacked pitch build polls once every 2.5 seconds only while at least one local draft is pending. One request covers all pending IDs.
- Three consecutive polling failures back off first to 10 seconds and then to 30 seconds; one healthy response restores 2.5-second polling.
- A server approval is claimed atomically once. The corresponding local pass permits exactly one physical send.
- ChatGPT and Claude are the only restoration targets in this plan.
- An unchanged prompt already in the original composer is never duplicated.
- Different unsent text is never overwritten. If the original conversation advances after review submission, **Restore in new chat** opens a completely new conversation.
- Restoration succeeds only when the destination node remains connected and its read-back SHA-256 equals the approved prompt hash.
- Ethics approval never bypasses PII, file, or other policy checks.
- Rejection deletes Vanguard's local raw draft and pass but never edits the provider composer.
- Notifications and logs never contain raw prompt text.
- Every commit uses the repository's configured `JeffTiong1031 <jefftiong1031@gmail.com>` identity and contains no co-author or other trailer.

## Binding Phase Gate

The following sequence applies to every implementation task below and overrides any instruction to commit immediately after automated tests:

1. Codex implements only the current task using red-green TDD.
2. Codex runs the task-specific checks and the stated regression suite.
3. Codex reports the exact commands, pass counts, changed files, and success-criteria evidence.
4. Codex gives the user the task's numbered manual-check instructions and expected observations.
5. Codex stops. No commit is created while user review is pending.
6. If the user finds a problem, Codex fixes it, reruns the checks, and presents the same gate again.
7. Only after the user explicitly approves does Codex stage only that task's files, run `git diff --cached --check`, verify the staged path list, and create the listed commit.
8. Codex verifies commit author/body/path scope, then starts the next task.

## Execution Setup

At execution time, use `superpowers:using-git-worktrees` to create an isolated branch named `codex/approved-prompt-restoration` from the commit containing this plan. Use `superpowers:executing-plans` in the primary session because the user requires a live approval pause after every task.

Before Task 1, establish the baseline:

```powershell
Set-Location 'code/policy'
.venv/Scripts/python -m pytest -q
Set-Location '../extension'
npm run build
npm test
git status --short
```

**Baseline success criteria:** both suites exit `0`, the WXT build exits `0`, the committed distribution matches the fresh build, and the isolated worktree is clean. If any baseline check fails, diagnose it before changing feature code and report it separately from this plan.

## File Responsibility Map

### Policy service

- `code/policy/app/models.py` — validates the one-time claim request.
- `code/policy/app/db.py` — fresh-schema columns and idempotent startup migration.
- `code/policy/migrations/001_initial.sql` — fresh manual PostgreSQL setup parity.
- `code/policy/migrations/003_one_time_appeal_claim.sql` — existing deployment migration.
- `code/policy/app/routes/appeals.py` — appeal creation, status reads, and atomic claim endpoint.
- `code/policy/tests/test_appeals.py` — privacy, ownership, idempotency, and one-winner claim behavior.
- `code/policy/tests/test_schema.py` — deployed column existence.

### Extension background and local state

- `code/extension/src/appeals/types.ts` — shared draft, transition, payload, and notice types.
- `code/extension/src/appeals/draft-vault.ts` — the only `chrome.storage.session` read/write boundary.
- `code/extension/src/appeals/decision-poller.ts` — one-request reconciliation and backoff state machine.
- `code/extension/src/appeals/background-routing.ts` — tab validation, notification IDs, click routing, and options-page routing.
- `code/extension/src/policy/appeals.ts` — HTTP create/list/claim client; no raw local prompt field.
- `code/extension/src/policy/messages.ts` — typed content/background protocol.
- `code/extension/entrypoints/background.ts` — thin Chrome event wiring around the modules above.

### Extension content and UI

- `code/extension/src/appeals/restoration.ts` — pure target decision plus two-frame write/read-back verification.
- `code/extension/src/gate/approval-token.ts` — layered one-time pass carrying the optional appeal ID.
- `code/extension/src/gate/gate.ts` — ethics/PII layer enforcement and paired-event deduplication.
- `code/extension/src/adapters/types.ts` — adapter contract, including each provider's blank-conversation URL.
- `code/extension/src/adapters/chatgpt.ts` — ChatGPT blank route and existing composer integration.
- `code/extension/src/adapters/claude.ts` — Claude blank route and existing composer integration.
- `code/extension/src/ui/appeal-toast.ts` — fixed green/red, accessible, no-timer status UI.
- `code/extension/src/ui/ethics-modal.ts` — awaited review submission with visible retry behavior.
- `code/extension/entrypoints/content.ts` — content coordinator, restoration listener, advanced-conversation reporting, and cleanup.
- `code/extension/entrypoints/options/main.tsx` — durable `#my-reviews` rejection destination and current status colors.

### Tests and proof

- `code/extension/tests/appeal-draft-vault.test.ts` — storage ownership, expiry, isolation, and cleanup.
- `code/extension/tests/appeal-poller.test.ts` — polling, claim, rejection, and backoff.
- `code/extension/tests/appeal-background-routing.test.ts` — exact tab/URL routing and persistent notification actions.
- `code/extension/tests/appeal-restoration.test.ts` — unchanged/empty/occupied/advanced/write-failure outcomes.
- `code/extension/tests/appeal-toast.test.ts` — green/red UI, persistence, accessibility, and action callbacks.
- `code/extension/tests/ui/options-appeal-reviews.test.tsx` — durable rejection destination and current status styling.
- `code/extension/tests/appeal-flow.test.ts` — submission, one-send consumption, conversation advancement, and combined ethics/PII behavior.
- Existing focused tests modified where their public contracts change: `appeals-client.test.ts`, `ethics-modal.test.ts`, `adapters.test.ts`, `approval-token.test.ts`, `gate.test.ts`, `manifest-permissions.test.ts`, and `options-mode-lock.test.tsx` only if its options render fixture needs the new anchor.
- `code/extension/ACCEPTANCE.md` — final manual evidence and reproducible pitch steps.

## Design Acceptance Coverage

| Design criterion | Implemented and proved by |
|---|---|
| 1. Healthy approval reaches the employee within five seconds | Task 3 poll timing; Task 7 measured latency |
| 2. Already-present text is not duplicated | Task 5 restoration unit/live checks |
| 3. Closed-tab restoration works on ChatGPT and Claude | Tasks 4-5 routing; Task 7 matrix |
| 4. A different conversation remains byte-identical | Tasks 4-5 routing/restoration checks |
| 5. A non-empty changed composer is never overwritten | Task 5 occupied-composer test/live check |
| 6. Success requires connected read-back hash equality | Task 5 failure-outcome tests |
| 7. Employee presses Send; no auto-submit exists | Gate constraint in Task 6; forbidden-path search in Task 7 |
| 8. One server claim and one physical send | Task 1 atomic claim; Task 6 token consumption |
| 9. Repeating the prompt blocks again | Task 6 automated/live check |
| 10. Server receives raw text only after disclosure opt-in | Tasks 1-2 privacy assertions |
| 11. Rejection/expiry/logout/re-enrol/revocation/Chrome exit clear local raw text | Tasks 2-4 cleanup; Task 7 restart check |
| 12. Ethics approval does not bypass PII or other gates | Task 6 layered decision tests/live check |
| 13. Zero pending drafts means zero fast polling | Task 3 scheduler test/live alarm check |
| 14. Dismissed notification has in-page recovery | Task 4 startup recovery test; Task 7 matrix |
| 15. Advanced original conversation restores only in a new conversation | Tasks 5-6 advanced-state checks |
| 16. Rejection deletes Vanguard state without editing provider text | Tasks 3-4 rejection checks |
| 17. Rejection UI is durable, prompt-free, and links to My Reviews | Task 4 toast/options tests/live check |
| 18. Network/malformed uncertainty never appears as rejection | Task 3 poller tests |

---

### Task 1: Policy-Service One-Time Appeal Claim

**Files:**

- Modify: `code/policy/app/models.py:132`
- Modify: `code/policy/app/db.py:169` (fresh schema and `_COLUMN_ADDS` near line 247)
- Modify: `code/policy/migrations/001_initial.sql:70`
- Create: `code/policy/migrations/003_one_time_appeal_claim.sql`
- Modify: `code/policy/app/routes/appeals.py:30-132`
- Modify: `code/policy/tests/test_appeals.py`
- Modify: `code/policy/tests/test_schema.py`

**Interfaces:**

- Consumes: existing employee identity lookup by `pseudo_id` and `decision_appeals.scope_fingerprint`.
- Produces: `AppealClaim`, `claim_approved_appeal(...)`, `POST /v1/appeals/{appeal_id}/claim`, nullable `claim_id`/`claimed_at`, and approved-scope reads that exclude claimed rows.

- [ ] **Step 1: Write the failing schema and claim tests**

Add tests with fixed, falsifiable outcomes:

```python
def _create_and_approve(pid: str, dept: TestClient, scope: str) -> str:
    appeal_id = client.post("/v1/appeals", json={
        "pseudo_id": pid, "decision_type": "ethics", "category": "security_evasion",
        "reason": "defensive test", "scope_fingerprint": scope,
    }).json()["id"]
    assert dept.post(
        f"/v1/dept/appeals/{appeal_id}", json={"decision": "approved"}
    ).status_code == 200
    return appeal_id


def _claim(appeal_id: str, pid: str, scope: str, claim_id: str):
    return client.post(f"/v1/appeals/{appeal_id}/claim", json={
        "pseudo_id": pid, "prompt_hash": scope, "claim_id": claim_id,
    })


def test_decision_appeals_has_claim_columns():
    assert {"claim_id", "claimed_at"} <= _cols(get_conn(), "decision_appeals")


def test_approved_ethics_appeal_claim_is_idempotent_for_same_claim_id():
    pid, dept = _enrol()
    appeal_id = _create_and_approve(pid, dept, "c" * 64)
    body = {"pseudo_id": pid, "prompt_hash": "c" * 64, "claim_id": "1" * 32}
    first = client.post(f"/v1/appeals/{appeal_id}/claim", json=body)
    retry = client.post(f"/v1/appeals/{appeal_id}/claim", json=body)
    assert first.status_code == retry.status_code == 200
    assert first.json() == retry.json()


def test_different_claim_id_cannot_reclaim_approval():
    pid, dept = _enrol()
    appeal_id = _create_and_approve(pid, dept, "d" * 64)
    assert _claim(appeal_id, pid, "d" * 64, "1" * 32).status_code == 200
    assert _claim(appeal_id, pid, "d" * 64, "2" * 32).status_code == 409


def test_appeal_decision_accepts_only_approved_or_blocked():
    pid, dept = _enrol()
    appeal_id = client.post("/v1/appeals", json={
        "pseudo_id": pid, "decision_type": "ethics", "category": "x",
        "reason": "test", "scope_fingerprint": "e" * 64,
    }).json()["id"]
    assert dept.post(
        f"/v1/dept/appeals/{appeal_id}", json={"decision": "temporary"}
    ).status_code == 422
```

- [ ] **Step 2: Run the focused tests and prove RED**

```powershell
Set-Location 'code/policy'
.venv/Scripts/python -m pytest tests/test_schema.py::test_decision_appeals_has_claim_columns tests/test_appeals.py -q
```

**Expected RED:** missing columns/model/route or a failing persistence assertion. A collection failure unrelated to those missing contracts must be fixed before proceeding.

- [ ] **Step 3: Add the validated request and idempotent schema migration**

Implement the request contract:

```python
class AppealDecision(BinaryDecision):
    decision: Literal["approved", "blocked"]


class AppealClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pseudo_id: str
    prompt_hash: str = Field(min_length=64, max_length=64)
    claim_id: str = Field(min_length=32, max_length=64)

    @field_validator("prompt_hash", "claim_id")
    @classmethod
    def hashes_are_lower_hex(cls, value: str) -> str:
        if any(ch not in "0123456789abcdef" for ch in value.lower()):
            raise ValueError("must be lowercase-compatible hexadecimal")
        return value.lower()
```

Add both columns to the fresh schema and `_COLUMN_ADDS`, and create the deploy migration:

```sql
ALTER TABLE decision_appeals ADD COLUMN IF NOT EXISTS claim_id TEXT;
ALTER TABLE decision_appeals ADD COLUMN IF NOT EXISTS claimed_at TEXT;
```

- [ ] **Step 4: Implement the atomic claim and retire permanent re-grants**

Use one conditional `UPDATE ... RETURNING`, not a read-then-write claim:

```python
def claim_approved_appeal(
    conn, employee_id: str, appeal_id: str, prompt_hash: str, claim_id: str,
) -> dict | None:
    row = conn.execute(
        "UPDATE decision_appeals SET claim_id = %s, claimed_at = COALESCE(claimed_at, %s)"
        " WHERE id = %s AND employee_id = %s AND status = 'approved'"
        " AND scope_fingerprint = %s AND (claim_id IS NULL OR claim_id = %s)"
        " RETURNING id, claim_id, claimed_at",
        (claim_id, now_iso(), appeal_id, employee_id, prompt_hash, claim_id),
    ).fetchone()
    return dict(row) if row else None
```

Return `409 approval unavailable` when it yields no row. Add `AND claim_id IS NULL` to the create-appeal approved pre-screen and `/approved-scopes` query so a claimed approval cannot be granted again.

- [ ] **Step 5: Add denial, privacy, and concurrency coverage**

Cover wrong employee, wrong hash, pending, blocked, malformed ID, two different claims, same-ID response-loss retry, `disclosed_text IS NULL`, and exactly one winner across two independent database connections. The concurrent assertion is:

```python
def run_claim(claim_id: str) -> int:
    conn = connect(os.environ["DATABASE_URL"])
    try:
        row = claim_approved_appeal(conn, employee_id, appeal_id, scope, claim_id)
        conn.commit()
        return 200 if row else 409
    finally:
        conn.close()


with ThreadPoolExecutor(max_workers=2) as pool:
    statuses = sorted(pool.map(run_claim, ["a" * 32, "b" * 32]))
assert statuses == [200, 409]
```

- [ ] **Step 6: Run focused and full policy verification**

```powershell
Set-Location 'code/policy'
.venv/Scripts/python -m pytest tests/test_schema.py tests/test_appeals.py tests/test_dept_appeals.py tests/test_notifications.py -q
.venv/Scripts/python -m pytest -q
```

**Task 1 automated success criteria:** all commands exit `0`; the same claim ID retries successfully; a different ID loses; claimed rows disappear from approved scopes; and the default appeal still stores `NULL` for `disclosed_text`.

**Task 1 guided user check:**

1. Open a PowerShell terminal in `code/policy`.
2. Run `.venv/Scripts/python -m pytest tests/test_appeals.py -q`.
3. Confirm the summary contains `0 failed`.
4. Run `.venv/Scripts/python -m pytest tests/test_schema.py::test_decision_appeals_has_claim_columns -q`.
5. Confirm the single schema test passes.
6. Tell Codex whether Task 1 is approved. Codex must not commit before this response.

**Commit after user approval:**

```powershell
git add -- code/policy/app/models.py code/policy/app/db.py code/policy/app/routes/appeals.py code/policy/migrations/001_initial.sql code/policy/migrations/003_one_time_appeal_claim.sql code/policy/tests/test_appeals.py code/policy/tests/test_schema.py
git diff --cached --check
git commit -m "feat(policy): claim appeal approvals once"
```

---

### Task 2: Session Draft Vault and Awaited Review Submission

**Files:**

- Create: `code/extension/src/appeals/types.ts`
- Create: `code/extension/src/appeals/draft-vault.ts`
- Create: `code/extension/tests/appeal-draft-vault.test.ts`
- Modify: `code/extension/tests/setup-dom.ts`
- Modify: `code/extension/src/policy/appeals.ts:13-59`
- Modify: `code/extension/tests/appeals-client.test.ts`
- Modify: `code/extension/src/policy/messages.ts:14-41`
- Modify: `code/extension/entrypoints/background.ts:94-166`
- Modify: `code/extension/entrypoints/content.ts:162-184`
- Modify: `code/extension/src/ui/ethics-modal.ts:27-221`
- Modify: `code/extension/tests/ethics-modal.test.ts`
- Regenerate: `code/extension/dist/chrome-mv3/**`

**Interfaces:**

- Consumes: Task 1's appeal creation response `{id,status,access_state,pre_screen}`.
- Produces: `PendingPromptDraft`, prompt-free `AppealDecisionNotice`, `DraftVault`, `AppealSubmitResponse`, and an awaited modal callback that saves only server-accepted reviews.

- [ ] **Step 1: Define the draft and protocol types**

```ts
export type SupportedAppealHost = 'chatgpt.com' | 'claude.ai';

export type PendingPromptDraft = {
  version: 1;
  appealId: string;
  claimId: string;
  promptHash: string;
  promptText: string;
  host: SupportedAppealHost;
  conversationUrl: string;
  originalTabId: number;
  conversationAdvanced: boolean;
  createdAt: number;
  expiresAt: number;
  state: 'pending' | 'approved_ready';
  adminNote?: string | null;
  restoreTargetTabId?: number;
};

export type AppealDecisionNotice = {
  appealId: string;
  host: SupportedAppealHost;
  kind: 'rejected' | 'unavailable';
  adminNote: string | null;
  createdAt: number;
};

export type DraftVaultState = {
  version: 1;
  ownerPseudoId: string;
  drafts: Record<string, PendingPromptDraft>;
  notices: Record<string, AppealDecisionNotice>;
};

export type RestorationPayload = Pick<
  PendingPromptDraft,
  'appealId' | 'promptHash' | 'promptText' | 'host' | 'conversationUrl' |
  'conversationAdvanced' | 'adminNote'
>;

export type AppealReadySummary = {
  appealId: string;
  host: SupportedAppealHost;
  adminNote: string | null;
  target: 'saved' | 'new';
};

export type AppealSubmitResponse =
  | { kind: 'appeal-submit-result'; ok: true; appealId: string }
  | { kind: 'appeal-submit-result'; ok: false; error: string };
```

The submit message carries `localPromptText`, `promptHash`, `host`, and `conversationUrl` as distinct local fields. Only `disclosedText` is eligible for the HTTP body.

- [ ] **Step 2: Write failing vault tests**

```ts
function draft(over: Partial<PendingPromptDraft> = {}): PendingPromptDraft {
  return {
    version: 1, appealId: 'appeal-1', claimId: '1'.repeat(32),
    promptHash: 'a'.repeat(64), promptText: 'local prompt', host: 'chatgpt.com',
    conversationUrl: 'https://chatgpt.com/c/one', originalTabId: 7,
    conversationAdvanced: false, createdAt: 0, expiresAt: 86_400_000,
    state: 'pending', ...over,
  };
}

function memorySession(): Pick<chrome.storage.StorageArea, 'get' | 'set' | 'remove'> {
  const bag: Record<string, unknown> = {};
  return {
    get: vi.fn(async (key: string) => ({ [key]: bag[key] })),
    set: vi.fn(async (items: Record<string, unknown>) => { Object.assign(bag, items); }),
    remove: vi.fn(async (key: string) => { delete bag[key]; }),
  } as Pick<chrome.storage.StorageArea, 'get' | 'set' | 'remove'>;
}

it('expires raw drafts at 24 hours', async () => {
  const vault = createDraftVault(memorySession(), () => 86_400_001);
  await vault.save(draft({ createdAt: 0, expiresAt: 86_400_000 }));
  expect(await vault.purgeExpired()).toEqual(['appeal-1']);
  expect(await vault.get('appeal-1')).toBeNull();
});

it('clears every draft when the enrolment owner changes', async () => {
  await vault.ensureOwner('employee-a');
  await vault.save(draft());
  await vault.ensureOwner('employee-b');
  expect(await vault.list()).toEqual([]);
});
```

Also test isolated update by appeal ID, monotonic `conversationAdvanced`, approved-ready transition, rejection/consumption deletion, earliest expiry, owner removal/change cleanup, and no public enumerate message for content scripts.

- [ ] **Step 3: Run the vault tests and prove RED**

```powershell
Set-Location 'code/extension'
npx vitest run tests/appeal-draft-vault.test.ts
```

**Expected RED:** module or exported vault functions do not exist.

- [ ] **Step 4: Implement the background-only vault**

Use a single key and injected storage for deterministic tests:

```ts
export const APPEAL_DRAFTS_KEY = 'vg_appeal_drafts_v1';

export type DraftVault = {
  ensureOwner(pseudoId: string): Promise<void>;
  save(draft: PendingPromptDraft): Promise<void>;
  get(appealId: string): Promise<PendingPromptDraft | null>;
  list(): Promise<PendingPromptDraft[]>;
  markAdvanced(appealId: string): Promise<void>;
  markApproved(appealId: string, adminNote?: string | null): Promise<PendingPromptDraft | null>;
  setRestoreTarget(appealId: string, tabId: number): Promise<void>;
  remove(appealId: string): Promise<void>;
  saveNotice(notice: AppealDecisionNotice): Promise<void>;
  listNotices(host: SupportedAppealHost): Promise<AppealDecisionNotice[]>;
  acknowledgeNotice(appealId: string): Promise<void>;
  purgeExpired(): Promise<string[]>;
  clear(): Promise<void>;
};
```

Call `chrome.storage.session.setAccessLevel({accessLevel: 'TRUSTED_CONTEXTS'})` during background startup. Never log the state object or `promptText`. Rejection/unavailable notices contain metadata only; removing a draft deletes its raw prompt even while its notice remains available until acknowledgement or Chrome exit.

At background startup call `ensureOwner(currentEnrolment.pseudo_id)`. In the existing `chrome.storage.onChanged` listener, inspect `vg_enrolment`: removal clears the vault; a new/different `pseudo_id` calls `ensureOwner` and therefore clears drafts owned by the previous enrolment. Keep the existing configuration-cache invalidation in the same listener.

- [ ] **Step 5: Make appeal creation return its server identity without leaking local text**

```ts
export type AppealCreateResult = {
  id: string;
  status: 'pending' | 'approved';
  access_state: 'blocked' | 'approved';
  pre_screen: 'ready_for_review' | 'duplicate' | 'already_approved';
};

export async function submitAppeal(input: AppealInput): Promise<AppealCreateResult> {
  // Build the existing HTTP body. Never add localPromptText.
  // Validate response.ok and required string fields before returning.
}
```

The background generates `claimId = crypto.randomUUID().replaceAll('-', '')`, awaits `submitAppeal`, obtains `sender.tab.id`, validates that the URL host equals the declared supported host, and only then saves the draft with `expiresAt = Date.now() + 86_400_000`.

- [ ] **Step 6: Make review submission visibly await success**

Change the modal contract to:

```ts
onRequestReview: (reason: string, disclosedText?: string) => Promise<void>;
```

On click, reject a blank reason, disable the button, show **Sending review…**, and await the callback. On success, hide the modal. On failure, keep the modal and entered reason open, re-enable **Retry**, and show **We couldn't send this review. Check your connection and try again.**

- [ ] **Step 7: Prove storage-after-acceptance and default privacy**

Add tests asserting:

```ts
expect(httpBody).not.toHaveProperty('localPromptText');
expect(httpBody).not.toHaveProperty('disclosed_text');
expect(vault.save).not.toHaveBeenCalled(); // rejected HTTP response
expect(vault.save).toHaveBeenCalledOnce(); // accepted HTTP response
```

The opt-in test must still assert `disclosed_text` equals the employee-selected exact text.

- [ ] **Step 8: Run focused tests, build, and full extension regression**

```powershell
Set-Location 'code/extension'
npx vitest run tests/appeal-draft-vault.test.ts tests/appeals-client.test.ts tests/ethics-modal.test.ts
npm run build
npm test
```

**Task 2 automated success criteria:** all commands exit `0`; no failed submission creates a draft; accepted submission creates one 24-hour session draft; logout, revocation, and enrolment-owner change clear it; non-opt-in HTTP bodies contain no raw text; build/dist drift is clean.

**Task 2 guided user check:**

1. Start the local policy service and load `code/extension/dist/chrome-mv3` unpacked.
2. On ChatGPT, enter a prompt that triggers the ethics block and choose **Request a review**.
3. Enter a reason without selecting exact-text disclosure, then press **Send review**.
4. Confirm the button shows a sending state and the modal closes only after success.
5. Open the extension service worker DevTools, run:

   ```js
   const state = (await chrome.storage.session.get('vg_appeal_drafts_v1')).vg_appeal_drafts_v1;
   Object.values(state.drafts).map(({ promptText, ...safe }) => safe);
   ```

6. Confirm one safe metadata row exists and `expiresAt - createdAt` is `86400000`.
7. Stop the policy service, submit a second review, and confirm the modal remains open with Retry.
8. Reconnect the service, have the department admin revoke that employee token, trigger the normal policy refresh, and confirm `chrome.storage.session.get('vg_appeal_drafts_v1')` contains no old draft; re-enrolling with a new token must not restore it.
9. Tell Codex whether Task 2 is approved. Codex must not commit before this response.

**Commit after user approval:**

```powershell
git add -- code/extension/src/appeals/types.ts code/extension/src/appeals/draft-vault.ts code/extension/src/policy/appeals.ts code/extension/src/policy/messages.ts code/extension/src/ui/ethics-modal.ts code/extension/entrypoints/background.ts code/extension/entrypoints/content.ts code/extension/tests/appeal-draft-vault.test.ts code/extension/tests/appeals-client.test.ts code/extension/tests/ethics-modal.test.ts code/extension/tests/setup-dom.ts code/extension/dist/chrome-mv3
git diff --cached --check
git commit -m "feat(ext): retain pending appeal prompts for the Chrome session"
```

---

### Task 3: Decision Polling, Atomic Claim, Backoff, and Expiry

**Files:**

- Create: `code/extension/src/appeals/decision-poller.ts`
- Create: `code/extension/tests/appeal-poller.test.ts`
- Modify: `code/extension/src/policy/appeals.ts`
- Modify: `code/extension/tests/appeals-client.test.ts`
- Modify: `code/extension/entrypoints/background.ts`
- Regenerate: `code/extension/dist/chrome-mv3/**`

**Interfaces:**

- Consumes: Task 1's claim endpoint and Task 2's `DraftVault`.
- Produces: one-request decision reconciliation, `DecisionTransition[]`, adaptive alarm scheduling, and approved-ready/rejected local transitions.

- [ ] **Step 1: Correct the wire statuses and add the claim client**

```ts
export type AppealRow = {
  id: string;
  decision_type: 'ethics' | 'pii';
  category: string;
  status: 'pending' | 'approved' | 'blocked';
  admin_note: string | null;
  created_at: string;
  decided_at: string | null;
};

export type AppealClaimResult =
  | { status: 'claimed' }
  | { status: 'unavailable' };

export async function claimAppeal(
  appealId: string,
  promptHash: string,
  claimId: string,
): Promise<AppealClaimResult>;
```

The claim body contains only `pseudo_id`, `prompt_hash`, and `claim_id`. Map HTTP `409` to `{status:'unavailable'}`; throw for network/5xx failures so the poller can retain and retry the pending draft.

- [ ] **Step 2: Write failing state-machine tests**

```ts
it('fetches once for multiple pending drafts and claims only matching approvals', async () => {
  const { poller, fetchMyAppeals, claimAppeal, vault } = makePollerHarness();
  await poller.pollOnce();
  expect(fetchMyAppeals).toHaveBeenCalledOnce();
  expect(claimAppeal).toHaveBeenCalledWith('a1', 'hash-1', 'claim-1');
  expect(vault.markApproved).toHaveBeenCalledWith('a1', 'Approved for defence');
});

it('backs off after three failures and resets on success', async () => {
  const { poller, fetchMyAppeals, schedule } = makePollerHarness();
  fetchMyAppeals.mockRejectedValueOnce(new Error('offline'));
  fetchMyAppeals.mockRejectedValueOnce(new Error('offline'));
  fetchMyAppeals.mockRejectedValueOnce(new Error('offline'));
  await poller.pollOnce(); await poller.pollOnce(); await poller.pollOnce();
  expect(schedule).toHaveBeenLastCalledWith(10);
  fetchMyAppeals.mockResolvedValueOnce([]);
  await poller.pollOnce();
  expect(schedule).toHaveBeenLastCalledWith(2.5);
});
```

Define `makePollerHarness()` at the top of the test file to return a poller plus typed Vitest mocks for every dependency. Also assert: no drafts means no fetch/alarm; one fetch covers all IDs; malformed rows are ignored; network claim failure retains pending state; claim conflict deletes raw text and stores only an unavailable notice; blocked deletes raw text and stores only rejection metadata; expiry removes pending and approved-ready drafts; 10-second failure continues to 30 seconds; success resets failure count.

- [ ] **Step 3: Run the poller tests and prove RED**

```powershell
Set-Location 'code/extension'
npx vitest run tests/appeal-poller.test.ts tests/appeals-client.test.ts
```

**Expected RED:** missing decision-poller and claim client exports.

- [ ] **Step 4: Implement the pure reconciliation core**

```ts
export type DecisionTransition =
  | { kind: 'approved'; draft: PendingPromptDraft }
  | { kind: 'rejected'; appealId: string; host: SupportedAppealHost; adminNote: string | null }
  | { kind: 'unavailable'; appealId: string; host: SupportedAppealHost };

export type DecisionPoller = {
  startIfNeeded(): Promise<void>;
  pollOnce(): Promise<DecisionTransition[]>;
  expireNow(): Promise<string[]>;
};
```

`pollOnce()` first purges expired records, lists only `state === 'pending'`, performs one `fetchMyAppeals()`, maps rows by ID, claims approved rows with their saved claim ID, and marks them ready only after `{status:'claimed'}`. On `{status:'unavailable'}`, copy safe metadata, remove the raw draft, save an unavailable notice, and emit the transition. For blocked rows, copy appeal ID/host/admin note, remove the raw draft, save a rejected notice, and emit the transition. A notice never contains `promptText`, `promptHash`, or `conversationUrl`.

- [ ] **Step 5: Wire pitch and expiry alarms**

Use two named alarms:

```ts
const APPEAL_POLL_ALARM = 'vg-appeal-poll';
const APPEAL_EXPIRY_ALARM = 'vg-appeal-expiry';
const PITCH_POLL_SECONDS = 2.5;
```

Create/recreate the polling alarm only when pending drafts exist. Schedule the expiry alarm for the earliest pending or approved-ready `expiresAt`. Stop the fast poll at zero pending drafts even when approved-ready drafts remain.

- [ ] **Step 6: Remove the content-time permanent allowance dependency**

Keep `/approved-scopes` client compatibility temporarily for other callers, but stop using `grantPassIfAllowed` from `content.ts`. Task 6 removes the obsolete types/functions after the restored local pass is wired. This intermediate task may mark a draft approved-ready but must not let it pass the send gate yet.

- [ ] **Step 7: Run focused tests, build, and full regression**

```powershell
Set-Location 'code/extension'
npx vitest run tests/appeal-poller.test.ts tests/appeals-client.test.ts tests/appeal-draft-vault.test.ts
npm run build
npm test
```

**Task 3 automated success criteria:** one fetch reconciles all drafts; 2.5/10/30-second scheduling follows the exact state machine; a draft becomes approved-ready only after claim success; network uncertainty stays pending; claim conflict deletes raw text and never arms; zero pending drafts means zero fast polling; expiry deletes raw text; all extension tests/build pass.

**Task 3 guided user check:**

1. Reload the unpacked extension and submit one ChatGPT review.
2. In service-worker DevTools, display only safe vault metadata with the Task 2 snippet.
3. Confirm its state is `pending`.
4. Approve the review in the department dashboard.
5. Within five seconds, rerun the safe metadata snippet and confirm the state is `approved_ready`.
6. Run `await chrome.alarms.get('vg-appeal-poll')` and confirm it returns `undefined` once no pending drafts remain.
7. Tell Codex whether Task 3 is approved. Codex must not commit before this response.

**Commit after user approval:**

```powershell
git add -- code/extension/src/appeals/decision-poller.ts code/extension/src/policy/appeals.ts code/extension/entrypoints/background.ts code/extension/tests/appeal-poller.test.ts code/extension/tests/appeals-client.test.ts code/extension/dist/chrome-mv3
git diff --cached --check
git commit -m "feat(ext): poll and claim appeal decisions"
```

---

### Task 4: Approval and Rejection Delivery UI

**Files:**

- Create: `code/extension/src/appeals/background-routing.ts`
- Create: `code/extension/src/ui/appeal-toast.ts`
- Create: `code/extension/tests/appeal-background-routing.test.ts`
- Create: `code/extension/tests/appeal-toast.test.ts`
- Create: `code/extension/tests/ui/options-appeal-reviews.test.tsx`
- Modify: `code/extension/src/policy/messages.ts`
- Modify: `code/extension/entrypoints/background.ts`
- Modify: `code/extension/entrypoints/content.ts`
- Modify: `code/extension/entrypoints/options/main.tsx:162-190`
- Modify: `code/extension/tests/manifest-permissions.test.ts`
- Regenerate: `code/extension/dist/chrome-mv3/**`

**Interfaces:**

- Consumes: Task 3's `DecisionTransition[]`.
- Produces: stable notification IDs, in-page approved/rejected messages, `View review`, and safe notification click routing.

- [ ] **Step 1: Define the delivery messages without a storage-dump operation**

```ts
export type AppealContentMessage =
  | { kind: 'appeal-approved-ready'; draft: RestorationPayload }
  | { kind: 'appeal-rejected'; appealId: string; adminNote: string | null }
  | { kind: 'appeal-approval-unavailable'; appealId: string }
  | { kind: 'appeal-hide'; appealId: string };

export type AppealActionRequest =
  | { kind: 'appeal-open-target'; appealId: string; target: 'saved' | 'new' }
  | { kind: 'appeal-open-reviews' }
  | { kind: 'appeal-state-for-host'; host: SupportedAppealHost }
  | { kind: 'appeal-acknowledge-notice'; appealId: string };

export type AppealActionResponse =
  | { kind: 'appeal-startup-state'; ok: true; drafts: AppealReadySummary[]; notices: AppealDecisionNotice[] }
  | { kind: 'appeal-restoration-payload'; ok: true; draft: RestorationPayload }
  | { kind: 'appeal-action-result'; ok: true }
  | { kind: 'appeal-action-result'; ok: false; error: string };
```

`appeal-state-for-host` returns approved summaries and prompt-free decision notices sufficient to display recovery UI. Raw `promptText` is returned only for a selected `appeal-open-target`/restoration target.

- [ ] **Step 2: Write failing routing and toast tests**

Test these exact rules:

```ts
const savedPromptText = 'raw prompt held only in session storage';
const { notification, currentDifferentTab, openOptions } = makeRoutingHarness({
  promptText: savedPromptText,
});
expect(notification.options.requireInteraction).toBe(true);
expect(JSON.stringify(notification.options)).not.toContain(savedPromptText);
expect(currentDifferentTab.sendMessage).not.toHaveBeenCalled();
expect(openOptions).toHaveBeenCalledWith('#my-reviews');
```

Define `makeRoutingHarness()` in the routing test to return captured notification options and typed tab/options spies. The toast tests must prove green approved copy, red rejected copy, approval-unavailable copy, admin note as `textContent`, no automatic timer, reload recovery from a metadata-only notice, explicit acknowledgement, **Restore in new chat**, **Copy approved prompt**, and **View review** callbacks. The options test must prove `#my-reviews` focus plus `approved`/`blocked` colors.

- [ ] **Step 3: Run the focused tests and prove RED**

```powershell
Set-Location 'code/extension'
npx vitest run tests/appeal-background-routing.test.ts tests/appeal-toast.test.ts tests/ui/options-appeal-reviews.test.tsx
```

**Expected RED:** routing/toast modules and message variants are absent.

- [ ] **Step 4: Implement exact tab and notification routing**

```ts
export function approvedNotificationId(appealId: string): string {
  return `vg-appeal-approved:${appealId}`;
}

export function rejectedNotificationId(appealId: string): string {
  return `vg-appeal-rejected:${appealId}`;
}
```

Deliver approved content directly only when `originalTabId` still exists, its normalized URL matches `conversationUrl`, and it is the active tab. Otherwise create the persistent system notification. Never send to a merely active different conversation.

On rejection, remove the raw draft/pass first. Send a red in-page message to the original supported tab when available; otherwise create a persistent system notification containing only fixed copy and the admin note. Both actions route to `chrome.runtime.getURL('options.html#my-reviews')`.

An unavailable claim uses the same safe delivery path with **Approval unavailable — request a new review** and no send pass. It contains no raw prompt and links to My Reviews. Clicking **View review**, explicitly dismissing the in-page notice, or activating its system notification acknowledges and removes the metadata-only notice.

- [ ] **Step 5: Prevent duplicate generic decision notifications**

Change the existing notification poll filter to exclude `kind === 'appeal_decision'`. The appeal-aware coordinator is the only owner of approval/rejection decision notifications; submission notifications may remain generic.

- [ ] **Step 6: Implement the fixed, theme-consistent toasts**

```ts
export type AppealToastOptions =
  | { kind: 'approved'; appealId: string; adminNote?: string | null; mode: 'ready' | 'restore_new'; onRestore(): void; onCopy(): void }
  | { kind: 'rejected'; appealId: string; adminNote?: string | null; onViewReview(): void; onAcknowledge(): void }
  | { kind: 'unavailable'; appealId: string; onViewReview(): void; onAcknowledge(): void };
```

Mount under `data-vanguard-ui="appeal-toast"` in a shadow root at the right side. Approved uses the existing green `#15803d`; rejection uses `#b91c1c`. Do not set a dismissal timer. All dynamic values use `textContent`.

On every ChatGPT/Claude content-script startup, send `appeal-state-for-host`. If approved-ready summaries exist after a notification was dismissed or missed, show **Approved prompt ready**; clicking it requests the selected target and never injects into the currently active unrelated conversation. If an unacknowledged rejection/unavailable notice exists, recreate its prompt-free in-page toast. This makes the no-timer rejection message survive page reloads during the same Chrome session without retaining the rejected prompt.

- [ ] **Step 7: Make My Reviews a direct durable destination**

Add `id="my-reviews"`, update status styling from obsolete `overturned/upheld` to `approved/blocked`, and scroll/focus the section when `location.hash === '#my-reviews'`.

- [ ] **Step 8: Run focused tests, build, and full regression**

```powershell
Set-Location 'code/extension'
npx vitest run tests/appeal-background-routing.test.ts tests/appeal-toast.test.ts tests/ui/options-appeal-reviews.test.tsx tests/manifest-permissions.test.ts
npm run build
npm test
```

**Task 4 automated success criteria:** persistent notifications contain no raw prompt; an unrelated composer receives no message; approval/rejection are not duplicated by the generic loop; dismissed approval notifications recover on the next supported-site start; unacknowledged rejection metadata recreates its prompt-free toast after reload; unavailable claims never arm; the in-page toast has no timer; View review reaches the anchored options section; all extension tests/build pass.

**Task 4 guided user check:**

1. Keep the original ChatGPT review tab active and approve its request.
2. Confirm a green right-side **Approved prompt ready** message appears and remains visible.
3. Submit a second review, keep its tab open, and reject it with an admin note.
4. Confirm the red toast appears and its provider composer text was not cleared; reload the tab and confirm the prompt-free toast returns, then click **View review** and confirm Options opens at the blocked row and admin note.
5. Submit a third review, close its tab, reject it, and confirm a persistent **Review rejected** system notification appears without prompt text.
6. Click the notification and confirm Options again opens at **My reviews**.
7. Tell Codex whether Task 4 is approved. Codex must not commit before this response.

**Commit after user approval:**

```powershell
git add -- code/extension/src/appeals/background-routing.ts code/extension/src/ui/appeal-toast.ts code/extension/src/policy/messages.ts code/extension/entrypoints/background.ts code/extension/entrypoints/content.ts code/extension/entrypoints/options/main.tsx code/extension/tests/appeal-background-routing.test.ts code/extension/tests/appeal-toast.test.ts code/extension/tests/ui/options-appeal-reviews.test.tsx code/extension/tests/manifest-permissions.test.ts code/extension/dist/chrome-mv3
git diff --cached --check
git commit -m "feat(ext): deliver appeal decision notifications"
```

---

### Task 5: Verified Restoration and New-Conversation Protection

**Files:**

- Create: `code/extension/src/appeals/restoration.ts`
- Create: `code/extension/tests/appeal-restoration.test.ts`
- Modify: `code/extension/src/adapters/types.ts:1-12`
- Modify: `code/extension/src/adapters/chatgpt.ts:7-71`
- Modify: `code/extension/src/adapters/claude.ts:7-65`
- Modify: `code/extension/tests/adapters.test.ts`
- Modify: `code/extension/src/appeals/background-routing.ts`
- Modify: `code/extension/entrypoints/background.ts`
- Modify: `code/extension/entrypoints/content.ts`
- Modify: `code/extension/src/ui/appeal-toast.ts`
- Regenerate: `code/extension/dist/chrome-mv3/**`

**Interfaces:**

- Consumes: Task 4's selected restoration payload/action.
- Produces: deterministic restoration outcomes, provider blank-conversation routes, verified browser-path insertion, and user-clicked clipboard fallback.

- [ ] **Step 1: Extend the adapter contract with explicit blank routes**

```ts
export type SurfaceAdapter = {
  host: string;
  newConversationUrl: string;
  getComposer(path?: EventTarget[]): HTMLElement | null;
  readText(path?: EventTarget[]): string | null;
  writeText(text: string, target?: HTMLElement | null): void;
  isSendControl(path: EventTarget[]): boolean;
  onPaste(cb: (text: string) => void): void;
  fileInputs(): HTMLInputElement[];
};
```

Set ChatGPT to `https://chatgpt.com/` and Claude to `https://claude.ai/new`.

- [ ] **Step 2: Write failing restoration outcome tests**

```ts
it('does not duplicate an already-present exact prompt', async () => {
  const h = makeRestorationHarness({ currentText: PROMPT, promptHash: HASH });
  const result = await restoreApprovedPrompt(h.input);
  expect(result.kind).toBe('already_present');
  expect(h.genericWrite).not.toHaveBeenCalled();
});

it('protects a changed composer by requiring a new conversation', async () => {
  const h = makeRestorationHarness({ currentText: 'newer work' });
  const result = await restoreApprovedPrompt(h.input);
  expect(result.kind).toBe('new_conversation_required');
  expect(h.genericWrite).not.toHaveBeenCalled();
});
```

Define `makeRestorationHarness(overrides)` in the test file to return the exact `restoreApprovedPrompt` input plus spies for `genericWrite`, `readText`, and `hash`. Also cover `conversationAdvanced`, empty verified write, `execCommand` false, detached node, two-frame reversion, hash mismatch, unavailable/login composer timeout, and no arming on any failure.

- [ ] **Step 3: Run focused tests and prove RED**

```powershell
Set-Location 'code/extension'
npx vitest run tests/appeal-restoration.test.ts tests/adapters.test.ts
```

**Expected RED:** restoration module/new adapter field absent.

- [ ] **Step 4: Implement the pure decision and verified writer**

```ts
export type RestorationOutcome =
  | { kind: 'already_present' }
  | { kind: 'restored' }
  | { kind: 'new_conversation_required' }
  | { kind: 'unavailable' }
  | { kind: 'write_failed'; reason: 'rejected' | 'detached' | 'hash_mismatch' };

export async function restoreApprovedPrompt(input: {
  promptHash: string;
  conversationAdvanced: boolean;
  composer: HTMLElement | null;
  readText(): string | null;
  genericWrite(text: string): boolean;
  promptText: string;
  hash(text: string): Promise<string>;
  twoFrames(): Promise<void>;
}): Promise<RestorationOutcome>;
```

The browser-path writer must match the measured U31 mechanism:

```ts
composer.focus();
document.execCommand('selectAll', false, undefined);
const accepted = document.execCommand('insertText', false, promptText);
await twoAnimationFrames();
```

Require `accepted`, `composer.isConnected`, and exact read-back hash equality.

- [ ] **Step 5: Route Restore to a separate blank tab when work is protected**

When outcome is `new_conversation_required`, show **Restore in new chat**. Its click asks background to create the adapter's `newConversationUrl`, stores that created `tab.id` as `restoreTargetTabId`, and supplies the selected payload only to that tab. The new tab writes only when its composer is empty.

For a closed unchanged original tab, notification click opens `conversationUrl`. For an advanced record, it opens `newConversationUrl` instead.

- [ ] **Step 6: Add bounded readiness and clipboard fallback**

Wait up to 15 seconds for a supported composer via the existing mutation-observer binding. On timeout/write failure, keep the draft unarmed and show **Copy approved prompt**. Call `navigator.clipboard.writeText(promptText)` only inside that button's click handler; copying never consumes the pass.

- [ ] **Step 7: Run focused tests, build, and full regression**

```powershell
Set-Location 'code/extension'
npx vitest run tests/appeal-restoration.test.ts tests/adapters.test.ts tests/appeal-background-routing.test.ts tests/appeal-toast.test.ts
npm run build
npm test
```

**Task 5 automated success criteria:** exact text is never duplicated; occupied/advanced contexts are byte-identical; a new blank conversation receives the prompt; write success requires two-frame connected read-back equality; failures do not arm; clipboard runs only on click; all extension tests/build pass.

**Task 5 guided user check:** perform these on both ChatGPT and Claude.

1. **Unchanged original:** request review, leave the prompt untouched, approve, and confirm it is not duplicated.
2. **Empty original:** request review, clear the composer without sending other work, approve, and confirm the exact prompt returns in the same conversation.
3. **Different unsent text:** request review, type different text, approve, press **Restore in new chat**, and confirm the different text remains untouched while a new conversation receives the approved prompt.
4. **Advanced original:** request review, delete it, send another allowed prompt, approve, press **Restore in new chat**, and confirm the old conversation remains unchanged while a completely new conversation receives the approved prompt.
5. **Closed original:** request review, close the tab, approve, click the system notification, and confirm the saved target opens and restores.
6. Confirm none of these actions sends a message automatically.
7. Tell Codex whether Task 5 is approved. Codex must not commit before this response.

**Commit after user approval:**

```powershell
git add -- code/extension/src/appeals/restoration.ts code/extension/src/appeals/background-routing.ts code/extension/src/adapters/types.ts code/extension/src/adapters/chatgpt.ts code/extension/src/adapters/claude.ts code/extension/src/ui/appeal-toast.ts code/extension/entrypoints/background.ts code/extension/entrypoints/content.ts code/extension/tests/appeal-restoration.test.ts code/extension/tests/adapters.test.ts code/extension/tests/appeal-background-routing.test.ts code/extension/tests/appeal-toast.test.ts code/extension/dist/chrome-mv3
git diff --cached --check
git commit -m "feat(ext): restore approved prompts without overwriting work"
```

---

### Task 6: Layered Gate, One Physical Send, and Cleanup

**Files:**

- Modify: `code/extension/src/gate/approval-token.ts`
- Modify: `code/extension/src/gate/gate.ts`
- Modify: `code/extension/tests/approval-token.test.ts`
- Modify: `code/extension/tests/gate.test.ts`
- Create: `code/extension/tests/appeal-flow.test.ts`
- Modify: `code/extension/src/policy/messages.ts`
- Modify: `code/extension/src/policy/appeals.ts`
- Modify: `code/extension/entrypoints/background.ts`
- Modify: `code/extension/entrypoints/content.ts`
- Modify: `code/extension/src/ui/ethics-modal.ts:226-257`
- Regenerate: `code/extension/dist/chrome-mv3/**`

**Interfaces:**

- Consumes: Task 5's verified `already_present`/`restored` outcome.
- Produces: a layered approval token, exact one-send consumption, paired click/submit handling, advanced-conversation marking, and complete draft/notification/toast cleanup.

- [ ] **Step 1: Replace the hash-only token with explicit enforcement layers**

```ts
export type ApprovalLayers = { ethics: boolean; pii: boolean };

export type ApprovalToken = {
  hash: string;
  expiresAt: number;
  layers: ApprovalLayers;
  appealId?: string;
};

export class ApprovalStore {
  approve(input: Omit<ApprovalToken, 'expiresAt'>, ttlMs: number): void;
  current(): ApprovalToken | null;
  consumeIfMatch(hash: string): ApprovalToken | null;
  invalidate(): void;
}
```

An appeal restoration arms `{ethics:true, pii:false, appealId}`. A PII-only proceed arms `{ethics:false, pii:true}` after rechecking ethics. A PII rewrite derived from an active ethics claim carries the same `appealId` into `{ethics:true, pii:true}` for the new verified hash.

- [ ] **Step 2: Write failing layered-decision and paired-event tests**

```ts
it('ethics approval does not bypass dirty PII', () => {
  const approval: ApprovalToken = {
    hash: 'approved-hash', expiresAt: Date.now() + 60_000,
    layers: { ethics: true, pii: false }, appealId: 'appeal-1',
  };
  expect(decideGate({
    hash: 'approved-hash', cache: dirtyPiiCache(),
    ethicsBlocked: true, approval,
  })).toBe('BLOCK');
});

it('allows click then submit as one physical approved send', () => {
  const h = installGateHarness({ approvedAppeal: true });
  h.dispatch('click', 1_000);
  h.dispatch('submit', 1_100);
  expect(h.onAllowed).toHaveBeenCalledTimes(1);
  expect(h.onBlocked).not.toHaveBeenCalled();
  expect(h.consumeApproval).toHaveBeenCalledTimes(1);
});
```

Define `dirtyPiiCache()` and `installGateHarness()` as typed test helpers in `appeal-flow.test.ts`; the harness returns its `onAllowed`, `onBlocked`, and `consumeApproval` spies instead of relying on globals. Also assert two keydowns/two clicks are two physical sends, a second physical send blocks, editing invalidates only the page token while preserving the vault draft, wrong hash does not consume, and paired events produce one governance event.

- [ ] **Step 3: Run focused tests and prove RED**

```powershell
Set-Location 'code/extension'
npx vitest run tests/approval-token.test.ts tests/gate.test.ts tests/appeal-flow.test.ts
```

**Expected RED:** old hash-only API cannot express layer decisions or appeal cleanup.

- [ ] **Step 4: Refactor the pure gate decision**

```ts
export function decideGate(input: {
  hash: string;
  cache: VerdictCache;
  approval: ApprovalToken | null;
  ethicsBlocked: boolean;
  consumeApproval?: () => void;
}): 'PASS' | 'BLOCK' {
  const match = input.approval?.hash === input.hash ? input.approval : null;
  if (input.ethicsBlocked && !match?.layers.ethics) return 'BLOCK';
  const verdict = input.cache.getSync(input.hash);
  if ((!verdict || verdict.state === 'DIRTY') && !match?.layers.pii) return 'BLOCK';
  if (match) input.consumeApproval?.();
  return 'PASS';
}
```

Keep held-file handling before this function. Re-run `checkEthics(finalText)` before creating a PII-only token.

In `content.ts`'s `onBlocked`, inspect `approvals.current()` for the current hash. If ethics is dirty but the matching token has `layers.ethics === true`, do not reopen or resubmit an ethics appeal; continue into the existing PII review. When PII review produces `finalText`, carry the active `appealId` and ethics layer to the new verified hash while setting `pii:true`. If no ethics claim is active, set `ethics` from a fresh synchronous `checkEthics(finalText) === null` result.

- [ ] **Step 5: Deduplicate only provider event pairs**

Remember the first allowed event's hash, type, and timestamp. Permit a following `submit` for the same hash within 1,000 ms without a second consume or `onAllowed` call only when the first event was `click` or Enter `keydown`. Never deduplicate two clicks, two keydowns, or events outside the window.

- [ ] **Step 6: Mark advanced conversations and consume local state**

For every different allowed physical send, content sends:

```ts
{ kind: 'appeal-context-advanced', conversationUrl: location.href, sentPromptHash }
```

Background uses the trusted `sender.tab.id` and supported sender host to mark every pending draft with the same `originalTabId` and a different `promptHash` as advanced. Do not require the URL to remain equal: the provider may assign a conversation URL during that very send, and any navigation/newer work in the original tab is a reason to protect it. The transition is monotonic. Send this message before the existing `caps.reporting` early return so reporting configuration cannot disable context protection.

When an appeal token is consumed, send `{kind:'appeal-consume', appealId}`. Background removes the draft, clears both stable notification IDs, and replies before any later recovery query can re-arm it. Content removes the green toast immediately.

When `vg_enrolment` is removed or changes, background clears the vault and broadcasts `appeal-hide`; each open content script invalidates its `ApprovalStore` and removes appeal toasts. This covers logout, admin revocation, and re-enrolment without changing provider composers.

- [ ] **Step 7: Remove the permanent allowance path and obsolete modal**

Delete `grantPassIfAllowed`, `appeal-allowance-check`, `AllowanceResponse`, `usedAppealPasses`, and `showReviewApprovedModal`. An employee cannot obtain a pass by typing an approved hash; the pass originates only from a claimed, approved-ready local draft.

- [ ] **Step 8: Run focused tests, build, and full regression**

```powershell
Set-Location 'code/extension'
npx vitest run tests/approval-token.test.ts tests/gate.test.ts tests/appeal-flow.test.ts tests/appeal-restoration.test.ts tests/ethics-modal.test.ts
npm run build
npm test
```

**Task 6 automated success criteria:** first matching physical send consumes once; paired click/submit does not re-block; second physical send blocks; another allowed prompt marks the matching original conversation advanced; ethics approval still invokes PII review; cleanup prevents re-arming after reload; obsolete permanent-grant code is absent; all extension tests/build pass.

**Task 6 guided user check:** perform on ChatGPT first, then repeat the one-send check on Claude.

1. Restore an approved ethics-only prompt and press Send once; confirm it sends and the green toast disappears.
2. Paste the exact same prompt again and press Send; confirm Vanguard blocks it and offers a new review.
3. Restore an approved prompt that also contains test PII; press Send and confirm the PII review still appears.
4. Complete masking, press Send, and confirm the rewritten prompt sends once.
5. Repeat the rewritten prompt and confirm it blocks again.
6. Reload the tab after consumption and confirm **Approved prompt ready** does not return.
7. Tell Codex whether Task 6 is approved. Codex must not commit before this response.

**Commit after user approval:**

```powershell
git add -- code/extension/src/gate/approval-token.ts code/extension/src/gate/gate.ts code/extension/src/policy/messages.ts code/extension/src/policy/appeals.ts code/extension/src/ui/ethics-modal.ts code/extension/entrypoints/background.ts code/extension/entrypoints/content.ts code/extension/tests/approval-token.test.ts code/extension/tests/gate.test.ts code/extension/tests/appeal-flow.test.ts code/extension/tests/appeal-restoration.test.ts code/extension/tests/ethics-modal.test.ts code/extension/dist/chrome-mv3
git diff --cached --check
git commit -m "feat(ext): consume restored appeal prompts once"
```

---

### Task 7: Full Acceptance Proof and Pitch Runbook

**Files:**

- Modify: `code/extension/ACCEPTANCE.md`
- Modify: `code/extension/DEMO.md`

If verification exposes a product defect, return to the task that owns that file, repeat its red-green and user-review gate, and commit the fix there before resuming Task 7. The acceptance task itself changes documentation only.

**Interfaces:**

- Consumes: complete policy claim, vault, poller, routing, restoration, UI, and gate.
- Produces: reproducible automated and live evidence for all 18 design acceptance criteria.

- [ ] **Step 1: Run fresh full automated verification**

```powershell
Set-Location 'code/policy'
.venv/Scripts/python -m pytest -q
Set-Location '../extension'
npm run build
npm test
npm run check:dist
git diff --check
```

Record the actual pass counts and command exit codes in the Task 7 report. Do not reuse results from an earlier task.

- [ ] **Step 2: Run privacy and forbidden-behavior searches**

```powershell
rg -n "grantPassIfAllowed|appeal-allowance-check|showReviewApprovedModal|usedAppealPasses" code/extension --glob '!dist/**'
rg -n "click\(\).*send|submit\(\)|requestSubmit\(" code/extension/src/appeals code/extension/src/ui code/extension/entrypoints/content.ts
git status --short
```

**Expected:** the obsolete allowance search has no matches; any send/submit search match is inspected and proven not to auto-submit; status contains only intentional acceptance/runbook changes plus fresh build output already accounted for.

- [ ] **Step 3: Execute the live acceptance matrix on ChatGPT and Claude**

For each host, capture hashes/URLs/outcomes without prompt text:

1. unchanged original tab;
2. empty unchanged original composer;
3. closed original tab and persistent notification;
4. employee working in a different conversation;
5. changed unsent composer;
6. advanced original conversation opening a completely new conversation;
7. dismissed-notification recovery;
8. forced write failure and user-clicked clipboard fallback;
9. rejection with provider composer unchanged and View review;
10. first approved send succeeds, second identical physical send blocks;
11. ethics-plus-PII combined path;
12. Chrome restart boundary.

Measure notification-to-ready latency with `performance.now()` or timestamps and require at most 5 seconds on a healthy unpacked demo connection.

- [ ] **Step 4: Update the acceptance and demo documents with measured facts**

Add a dated section containing:

```markdown
## Approved prompt restoration — measured 2026-08-06

| Host | Scenario | Outcome | Latency | Evidence without prompt text |
|---|---|---|---|---|
```

Populate rows only from this run. Document the exact admin/employee click sequence, the 24-hour/session boundary, the 2.5-second unpacked-only polling limitation, and the recovery/clipboard fallbacks. Do not record the prompt text.

- [ ] **Step 5: Rerun verification after documentation changes**

```powershell
Set-Location 'code/policy'
.venv/Scripts/python -m pytest -q
Set-Location '../extension'
npm run build
npm test
npm run check:dist
git diff --check
```

**Task 7 automated success criteria:** both complete suites and build exit `0`; distribution drift check exits `0`; forbidden permanent-grant symbols are absent; no auto-submit path exists; Git diff has no whitespace errors.

**Task 7 live success criteria:** all 18 criteria in the design spec are supported by a measured row or an automated test; both ChatGPT and Claude restore and send once; advanced/different conversations remain byte-identical; healthy approval delivery is within five seconds; raw text appears in no notification/log/evidence; restart clears local recovery.

**Task 7 guided user check:**

1. Codex gives the user the rebuilt unpacked path: `code/extension/dist/chrome-mv3`.
2. Codex gives the exact local or deployed policy URL used for the run.
3. The user performs the pitch sequence: block -> request -> admin approve -> green ready message -> employee Send.
4. The user performs the advanced-conversation sequence and confirms Restore opens a completely new conversation.
5. The user performs one rejection and confirms View review plus unchanged provider composer.
6. The user repeats the one-send proof and confirms the second attempt blocks.
7. The user reviews the new measured table in `code/extension/ACCEPTANCE.md`.
8. The user explicitly approves or reports failures. Codex must not create the final evidence commit before this response.

**Commit after user approval:**

```powershell
git add -- code/extension/ACCEPTANCE.md code/extension/DEMO.md
git diff --cached --check
git commit -m "docs: record approved prompt restoration proof"
```

After this commit, use `superpowers:finishing-a-development-branch`, present the verified branch state, and ask before pushing or creating a pull request.

## Plan Completion Checklist

- [ ] Every design-spec section maps to at least one task.
- [ ] Every task begins with a failing test or baseline proof before implementation.
- [ ] Every task has focused tests, full relevant regression, explicit success criteria, and guided user checks.
- [ ] Every task stops for user approval before its commit.
- [ ] Every commit is scoped, verified, authored by the configured user, and trailer-free.
- [ ] No task automatically submits an LLM prompt.
- [ ] No task weakens the disclosure opt-in or other enforcement layers.
- [ ] The final evidence covers ChatGPT and Claude with prompt-text-free observations.
