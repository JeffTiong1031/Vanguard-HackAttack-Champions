# Approved prompt restoration — design spec

**Date:** 2026-08-06

**Status:** Design agreed in conversation; awaiting written-spec review

**Scope:** ChatGPT and Claude, unpacked pitch build first

## 1. Goal

Turn an approved ethics appeal into a visible, one-time continuation of the
employee's original work:

1. An ethics finding blocks a prompt.
2. The employee requests human review and gives a reason.
3. A department admin approves the exact prompt fingerprint.
4. Vanguard tells the employee within a few seconds.
5. Vanguard makes the exact approved prompt ready in the original conversation.
6. The employee presses Send.
7. Vanguard consumes the approval and deletes its temporary copy of the prompt.

The pitch moment is **Approve in the dashboard -> green "Approved — ready to
send once" message beside the employee's composer**. Vanguard restores text;
it never submits text on the employee's behalf.

This extends ADR 0032's exact-prompt, one-time ethics allowance. It does not
change the existing optional disclosure rule: the company server receives the
exact prompt only when the employee ticks **Include the exact text**.

## 2. Decisions

| Question | Decision |
|---|---|
| Final action | Vanguard restores; the employee presses Send |
| Retention boundary | `chrome.storage.session`; survives an AI-tab close, not a full Chrome exit |
| Local expiry | 24 hours, or earlier on rejection/send/logout |
| First surfaces | ChatGPT and Claude |
| Open original tab | Verify the existing text; do not paste a duplicate |
| Closed original tab | Persistent system notification opens the saved conversation |
| Employee using another conversation | Never touch it; open the saved conversation separately |
| Non-empty, changed composer | Never overwrite; show **Approved prompt ready — Restore** |
| Admin visibility | Existing opt-in disclosure behavior remains unchanged |
| Pitch polling | One status request every 2.5 seconds while at least one draft is pending |
| Production polling | At least 30 seconds when no supported tab is open, or replace with push later |
| Allowance | Exact hash, one claim, one send |
| Clipboard | User-clicked fallback only when verified write-back fails |

## 3. Explicit non-goals

- No automatic provider submission.
- No prompt persistence across a full Chrome/browser restart.
- No server-side raw-prompt storage beyond the existing employee opt-in path.
- No WebSocket, SSE, FCM, or cross-device delivery in the pitch slice.
- No support beyond ChatGPT and Claude in this slice.
- No voice or file restoration. Existing file and voice gates remain separate.
- No overwrite of a composer containing different employee work.
- No ethics allowance bypass for PII, file, tool-policy, or other gates.

## 4. User experience

### 4.1 Original tab remains open

The blocked prompt normally remains in the composer after the employee submits
the review. On approval, Vanguard reads the composer and hashes it.

- If the hash matches, Vanguard does not rewrite the text. It shows a fixed
  green toast on the right: **Approved — ready to send once**.
- If the composer is empty, Vanguard writes the saved text through the site's
  editing path, reads it back, verifies the hash, then shows the toast.
- If the composer contains different text, Vanguard does not touch it. The
  toast instead says **Approved prompt ready** and offers **Restore**.

The ready toast follows the existing Vanguard visual language: green status
head, check icon, compact explanation, optional admin note, and no automatic
dismiss timer. It disappears after the approved send is consumed. Editing the
composer into a different hash changes the toast to the Restore state.

### 4.2 Original tab was closed

While Chrome remains running, the unpacked pitch build continues checking for
the decision. Approval creates a system notification with:

- `requireInteraction: true`;
- a stable ID derived from the appeal ID;
- title **Prompt approved**;
- message **Open the original conversation and send it once**; and
- an **Open approved prompt** action.

Chrome defines `requireInteraction` as remaining visible until the user
activates or dismisses the notification. Vanguard clears it on activation or
successful send, but cannot and must not prevent an OS/user dismissal:
<https://developer.chrome.com/docs/extensions/reference/api/notifications>.

Clicking the notification opens the saved conversation URL in a new tab. After
the supported composer appears, Vanguard applies the same hash/empty/changed
rules as section 4.1.

### 4.3 Employee is using another conversation

Vanguard stores the original tab ID and conversation URL. A tab is an automatic
restore target only when both still identify the saved conversation. If the
employee navigated that tab to another conversation, or is working elsewhere,
Vanguard leaves the active composer untouched and uses the system notification.
The notification opens the saved conversation separately.

If the appeal originated on a new-chat URL, reopening that saved URL naturally
starts a new conversation. Otherwise Vanguard preserves the original
conversation context.

### 4.4 Missed-notification fallback

Dismissing or missing the system notification does not discard the approval.
When a ChatGPT or Claude content script next starts, it asks the background for
approved-ready drafts for that host. It then shows **Approved prompt ready**.
The employee's click opens the saved conversation; it never injects the text
into whichever conversation happens to be active.

### 4.5 Rejection

Rejection creates a normal decision notification, removes the raw local prompt,
and removes the pending draft. The existing My Reviews UI remains the durable
place to read the admin note and remediation guidance.

## 5. Architecture

```mermaid
sequenceDiagram
    participant C as Content script
    participant B as Background worker
    participant S as Policy service
    participant A as Admin console

    C->>B: Submit review + local restoration draft
    B->>S: Appeal hash/category/reason (+ optional disclosed text)
    S-->>B: appeal_id, pending
    B->>B: Save raw draft in chrome.storage.session
    A->>S: Approve appeal
    loop Every 2.5 s while pending (pitch build)
        B->>S: Fetch this employee's appeal statuses
    end
    B->>S: Atomically claim approved appeal
    S-->>B: One-time claim granted
    B-->>C: Approval ready, restore/verify exact hash
    C->>C: Green ready-to-send-once toast
    C->>C: Employee presses Send; consume local pass
    C->>B: Delete draft and clear notification
```

### 5.1 Background-owned session draft vault

The background service worker is the sole owner of raw saved prompts. Content
scripts use typed messages and never access the storage area directly.

```ts
type PendingPromptDraft = {
  version: 1;
  appealId: string;
  claimId: string;          // random, 128 bits or stronger; idempotent server claim key
  promptHash: string;
  promptText: string;       // local session only; never logged
  host: 'chatgpt.com' | 'claude.ai';
  conversationUrl: string;
  originalTabId: number;
  createdAt: number;
  expiresAt: number;
  state: 'pending' | 'approved_ready';
  adminNote?: string;
};
```

Records live under one versioned `chrome.storage.session` key and are indexed
by appeal ID. The vault provides isolated operations: save, list pending, mark
approved-ready, get by appeal/host, consume, reject, and expire. There is no
generic "dump storage" API exposed to a content script.

The raw prompt and conversation URL are local product state, not telemetry.
They must not appear in console logs, governance events, notification text, or
error payloads.

### 5.2 Review submission

The ethics modal's submission becomes an awaited operation:

1. Content script computes the existing exact prompt hash.
2. It sends the prompt, hash, host, current URL, tab context, category, reason,
   and optional disclosed text to the background.
3. Background creates a random `claimId` and submits the appeal.
4. Only after the server accepts and returns `appealId` does background commit
   the restoration draft to session storage.
5. The modal shows success and closes. On failure it stays open with Retry; no
   false pending state is created.

The API request continues to omit `disclosed_text` entirely unless the employee
opted in. The raw prompt used by the local vault is not added to that request.

### 5.3 Decision poller

One poll checks all locally pending appeal IDs for the enrolled employee. It is
not one request per prompt.

- Start the alarm when the first draft becomes pending.
- Pitch/unpacked build period: 2.5 seconds.
- Stop the alarm when no pending drafts remain.
- On a healthy response, update every matching local record.
- On three consecutive failures, back off to 10 seconds and then 30 seconds;
  return to 2.5 seconds after the next success.
- Never infer approval from a timeout, notification, cached policy, or error.

Chrome normally limits packaged extension alarms to one wake-up every 30
seconds and may delay them further. Chrome documents an unpacked-extension
debugging exemption, which is why 2.5 seconds is an explicit pitch setting and
not a production claim:
<https://developer.chrome.com/docs/extensions/reference/api/alarms>.

The approval-aware poller owns prompt-review decision notifications. The
existing generic notification loop must skip the same appeal-decision records
so the employee does not receive duplicate popups.

### 5.4 Server-side one-time claim

The current permanent approved-scope list can re-grant an approval after a tab
or content-script restart. One-time behavior therefore needs a server-owned
claim, not only an in-memory `Set`.

Add nullable `claim_id` and `claimed_at` fields to `decision_appeals`, plus:

`POST /v1/appeals/{appeal_id}/claim`

Request fields:

- `pseudo_id`;
- `prompt_hash`; and
- `claim_id`.

The endpoint grants only when:

- the appeal belongs to that employee;
- status is `approved`;
- `scope_fingerprint` equals `prompt_hash`; and
- `claim_id` is null or already equals this request's `claim_id`.

The first successful request atomically writes `claim_id` and `claimed_at`.
Retrying with the same ID is idempotently successful, including when the first
HTTP response was lost. A different claim ID is rejected. Rejected or pending
appeals cannot be claimed.

Claiming transfers the one allowed send into this Chrome session. The local
gate burns it on the first matching send. If Chrome exits after claim but
before send, both the draft and pass disappear and the claim is not reissued.
That is a deliberate consequence of the selected session-only retention model.

The old approved-scope endpoint must not continue granting claimed appeals.

### 5.5 Tab targeting and restoration coordinator

The background first tries `originalTabId`. It may message that tab only when
its current host and normalized conversation URL still match the saved record.
Otherwise it uses the persistent system notification.

The content-side coordinator has three inputs: saved draft, current adapter,
and current composer. It returns one explicit outcome:

- `already_present` — current hash matches; arm pass and show ready toast;
- `restored` — empty composer accepted text and read-back hash matches;
- `occupied` — different non-empty text; show Restore state, no write;
- `unavailable` — no supported composer before the bounded readiness timeout;
- `write_failed` — site rejected/reverted the insertion or hash mismatched.

Only `already_present` and `restored` arm the send pass. Restoration uses the
browser editing path and read-back verification established by U31; calling an
adapter method without verifying the final hash is not success.

`write_failed` exposes a user-clicked **Copy approved prompt** action. Copying
does not consume the pass. After paste, the normal exact-hash gate decides the
send.

### 5.6 Gate integration

The gate remains synchronous and keeps decision #8: the employee presses Send.
For an ethics-dirty prompt it passes exactly once when the current hash matches
an approved-ready local claim. On that physical send it:

1. consumes the in-page approval token;
2. asks background to remove the session draft;
3. clears the related system notification and green toast; and
4. records the existing governance event without prompt text.

The existing click-plus-submit deduplication must treat the provider's paired
events as one physical send, so the second event cannot turn the allowed send
back into a block.

An ethics claim affects only the ethics decision. The prompt still enters PII,
file, and policy enforcement. If PII review rewrites the text, its new hash is
not the approved ethics hash; the existing combined-flow rules must explicitly
carry the one-time ethics decision without silently approving unreviewed PII.

## 6. Failure handling

| Failure | Required behavior |
|---|---|
| Appeal submission fails | Keep modal open, show Retry, do not create a durable pending draft |
| Poll request fails | Retain draft, back off after repeated failures, never grant |
| Service returns malformed/mismatched appeal | Ignore it, retain pending state, record no raw data |
| Claim response is lost | Retry with same `claimId`; server response is idempotent |
| Claim was taken by another ID | Show approval unavailable; never arm the gate |
| Notification permission denied/dismissed | Preserve approved-ready draft; recover when supported site opens |
| Saved URL requires login | Wait for login/navigation and a supported composer; never inject into login UI |
| Saved URL no longer resolves | Keep approved-ready record and offer Copy from a supported-page user gesture |
| Composer has different text | Never overwrite; show Restore state |
| Write-back reverts or hash differs | Do not arm; offer user-clicked clipboard fallback |
| Review is rejected | Notify, delete raw prompt immediately, retain server-side review history |
| Draft reaches 24 hours | Delete raw prompt and pass; later approval cannot restore it |
| Chrome exits | `storage.session` clears; no cross-restart recovery |
| Employee logs out/re-enrols/token is revoked | Clear every local draft and pass for that enrolment |
| Multiple reviews | Isolate by appeal ID; one notification click cannot restore another draft |

The product fails closed only for the specific ethics allowance: uncertainty
means the blocked prompt remains blocked. It does not turn an unavailable
policy service into a global extension failure.

## 7. Testing

### 7.1 Extension unit tests

- Session vault saves, lists, transitions, consumes, rejects, and expires
  records without leaking raw text to logs/messages not intended to carry it.
- Appeal submission omits `disclosed_text` by default and stores the local raw
  draft only after the server accepts.
- Poller uses one request for multiple drafts, starts once, stops at zero, and
  follows the failure backoff/reset rules.
- Approval and rejection update only the matching appeal ID.
- Notification uses `requireInteraction`, stable appeal ID, and correct click
  routing.
- Exact text already present is not written twice.
- Empty composer is written, read back, hashed, and armed only on equality.
- Different text is never overwritten.
- Failed write offers Copy and does not consume/arm prematurely.
- Notification fallback on a newly opened ChatGPT/Claude tab finds the right
  approved-ready draft.
- First matching send consumes the pass; a second send blocks.
- Click plus submit is one physical approved send.
- Ethics approval does not skip the PII path.
- Chrome/session cleanup, expiry, logout, and enrolment change clear drafts.

### 7.2 Policy-service tests

- Approved exact fingerprint can be claimed once.
- Same `claimId` retry is idempotent.
- Different `claimId` cannot claim an already claimed appeal.
- Wrong employee, org, department, hash, pending status, or rejected status is
  denied.
- Concurrent claim requests produce exactly one winning claim ID.
- Approved-scope reads exclude claimed appeals.
- Default appeal still stores `disclosed_text = NULL`.
- Department admins can decide only their own department's appeal.

### 7.3 Browser integration tests

Run against real unpacked builds on both ChatGPT and Claude:

1. **Open original tab:** block -> request -> approve -> green toast appears;
   prompt is not duplicated; one Send succeeds; toast disappears.
2. **Closed original tab:** block -> request -> close tab -> approve -> system
   notification -> click -> saved URL opens -> exact prompt restores -> one
   Send succeeds.
3. **Different conversation:** block -> request -> navigate/use another chat ->
   approve -> current composer remains byte-identical -> saved conversation
   opens separately.
4. **Changed composer:** edit after requesting -> approve -> no overwrite ->
   Restore action behaves deliberately.
5. **Missed notification:** dismiss it -> open supported site -> in-page
   Approved prompt ready recovery appears.
6. **Write-back failure:** force adapter rejection -> Copy fallback appears ->
   pasted matching prompt sends once.
7. **Restart boundary:** close Chrome before approval -> restart -> no raw draft
   and no restoration claim.

Raw observations must include the composer before/after text hash, selected tab
URL, restoration outcome, and notification-to-ready latency. They must not log
the prompt text.

## 8. Acceptance criteria

The feature is accepted only when all of the following hold:

| # | Criterion |
|---|---|
| 1 | Healthy unpacked demo: admin approval produces the correct in-page toast or system notification within 5 seconds |
| 2 | Open-tab approval never duplicates an already-present prompt |
| 3 | Closed-tab notification opens the saved conversation and restores the exact hash on ChatGPT and Claude |
| 4 | A different conversation's composer remains byte-identical |
| 5 | A non-empty changed composer is never overwritten |
| 6 | Restoration is called successful only after read-back hash equality |
| 7 | Employee must press Send; no code path auto-submits |
| 8 | The server claim and local gate permit exactly one matching send |
| 9 | Repeating the same prompt after consumption blocks again |
| 10 | Raw prompt reaches the server only through the existing explicit disclosure opt-in |
| 11 | Rejection, expiry, logout, enrolment change, and Chrome exit remove the local raw draft |
| 12 | Ethics approval does not bypass PII or other policy checks |
| 13 | No pending drafts means no fast status polling |
| 14 | System-notification dismissal still leaves an in-page recovery path |

## 9. Consequences and trade-offs

- **Pitch quality:** the dashboard action visibly completes the employee loop in
  a few seconds without employee retyping.
- **Privacy:** the raw prompt is temporarily retained on the employee device.
  This is more retention than the current composer-only state, but it remains
  session-bound and is never sent by default.
- **Lost approval:** a full Chrome exit deletes a claimed-but-unsent prompt and
  its local pass. This is intentional, not a recovery bug.
- **Demo/production split:** 2.5-second closed-tab alarms are an unpacked pitch
  behavior. A packaged extension uses the Chrome minimum or real-time push.
- **Conversation URL:** retaining it locally is necessary for correct targeting;
  it must be treated as private local state and never telemetry.
- **No overwrite:** safety wins over magic whenever the employee has newer text.
- **Server change:** one-time truth moves from a content-script `Set` to an
  idempotent server claim plus a session-local send token.

## 10. Implementation boundary

This design is one implementation plan with four bounded units:

1. policy-service claim schema/API;
2. background session vault, poller, and notification routing;
3. content-script restoration coordinator and green toast; and
4. gate integration plus automated/live verification.

No implementation begins until this written specification is reviewed and an
implementation plan is approved.
