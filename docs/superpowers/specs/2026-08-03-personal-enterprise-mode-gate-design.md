# Design — Personal vs Enterprise mode gate (extension)

> **Date:** 2026-08-03 · **Branch:** `transparency-redressal` · **Status:** approved design, pre-plan
>
> Sub-project 3 of 3 from the founder's original request (after the department hierarchy, which is
> built). The analytics/insider-risk widgets remain a separate spec. This one touches only the
> **extension** (`code/extension`) — no backend change.

---

## 1. Goal

Give the extension an explicit **first-run choice** between two modes, and make each mode's behaviour
and surfaces reflect it:

- **Enterprise** — today's full flow, unchanged: enrol with a token, obey org policy, warn on
  unapproved tools, report governance events, raise requests/appeals, and use cloud file checking.
- **Personal** — the **same local detection engine** with the org wiring removed: L1 + L2
  PII/sensitive detection, the send-gate, masking, and the PII modal, all advisory, with **nothing
  sent off the device**.

This realises locked **decision #3** ("gate = admin-enforced for enterprise, advisory for solo — one
engine, two policy modes"). The engine already runs locally without enrolment; what is missing is an
explicit mode, and the surfaces (Options, popup) currently assume Enterprise.

**Non-goals:** no change to detection accuracy, the gate mechanism, or the backend; no per-mode
builds; no Personal-mode settings beyond the mode itself; file checking and org features stay
Enterprise-only. The analytics widgets are a separate sub-project.

---

## 2. Personal mode — exact behaviour

| Capability | Personal | Enterprise |
|---|---|---|
| L1 + L2 PII/sensitive detection | ✅ on | ✅ on |
| Send-gate, masking, PII modal (advisory) | ✅ on | ✅ on |
| Local audit (`chrome.storage.local`, salted, never sent) | ✅ on (harmless) | ✅ on |
| **Governance events → policy server** (`reporting`) | ❌ off | ✅ on |
| **Ethics block + ethics modal + appeals** (`ethics`) | ❌ off | ✅ on |
| **File capture → cloud extract/redact** (`files`) | ❌ off | ✅ on |
| **Tool warn-banner + enrolment/org** (`toolPolicy`) | ❌ off | ✅ on |

**Why files are off in Personal:** the file pipeline sends content to the cloud extract/redact
backend. That would break "nothing leaves the device," so Personal is chat-text protection only.

**Why ethics is off in Personal:** ethics categories are an org-defined compliance control; applying a
built-in default set to an individual is unjustified. Personal protects the user's own data, it does
not police their prompts.

---

## 3. Mode model (`src/mode/mode.ts`, new)

```ts
export type Mode = 'personal' | 'enterprise';

export type ModeCapabilities = {
  reporting: boolean;   // send governance events to the policy server
  ethics: boolean;      // ethics detection + block + appeals
  files: boolean;       // file capture / cloud extract-redact
  toolPolicy: boolean;  // warn banner + enrolment/org surface
};

export function capabilitiesFor(mode: Mode): ModeCapabilities;
//   'personal'   -> { reporting:false, ethics:false, files:false, toolPolicy:false }
//   'enterprise' -> { reporting:true,  ethics:true,  files:true,  toolPolicy:true  }

export async function getMode(): Promise<Mode | null>;   // null = not chosen yet
export async function setMode(mode: Mode): Promise<void>;
```

- **Storage:** key `vg_mode` in `chrome.storage.local`; absent ⇒ `null` ⇒ show the picker.
- `capabilitiesFor` is **pure** (unit-tested). Every mode-dependent branch consults it — no scattered
  string comparisons, no seam missed.

---

## 4. First-run + Options UI (`entrypoints/options/main.tsx`)

**Auto-open on install:** `entrypoints/background.ts` adds a `chrome.runtime.onInstalled` listener that,
when `details.reason === 'install'`, calls `chrome.runtime.openOptionsPage()`.

**Options is mode-routed at the top level**, keyed on `getMode()` via a pure helper
`optionsView(mode): 'picker' | 'personal' | 'enterprise'` (`null → 'picker'`):

- **`'picker'`** — a two-card `ModePicker`:
  - *Personal*: "Protect your own sensitive data on this device. Nothing is sent anywhere."
  - *Enterprise*: "Connect to your organisation's policy, approvals, and file checking."
  - Choosing a card calls `setMode(...)` and re-routes.
- **`'personal'`** — a `PersonalPanel`: a one-line "Personal mode — Vanguard protects sensitive data
  locally on ChatGPT and Claude; nothing leaves this device," plus a **Switch to Enterprise** button.
  No Organisation / FileService / MyReviews sections.
- **`'enterprise'`** — the **existing** `Organisation` + `FileService` + `MyReviews`, plus a **Switch
  to Personal** control.

**Switch semantics:**
- **Enterprise → Personal:** confirm, then `clearEnrolment()` (disconnect + stop reporting) and
  `setMode('personal')`.
- **Personal → Enterprise:** `setMode('enterprise')`; the Organisation panel then lets the user enrol.

---

## 5. Popup (`entrypoints/popup/main.tsx`)

Reads `getMode()` and branches:
- **Personal:** "Personal mode · protecting this device" with the current site name. **No** "not
  connected to an organisation" message and **no** Connect button — that framing is Enterprise-only.
- **Enterprise, not enrolled:** today's "Connect" prompt (unchanged).
- **Enterprise, enrolled:** today's org / tool-status / department view (unchanged).

If mode is unset when the popup opens, it shows a short "Open Vanguard settings to choose Personal or
Enterprise" line with a button to `openOptionsPage()` (the picker is an Options surface, not a popup
one).

---

## 6. Content-script gating

Both content scripts read the mode once at `main()` and compute
`const caps = capabilitiesFor(mode ?? 'personal')` (an unset mode defaults to the safest, most-private
behaviour — Personal — until the user chooses).

**`entrypoints/content.ts`** gates exactly four seams; everything else is untouched:
1. `installFileCapture(...)` is called only if `caps.files`.
2. In `onBlocked`, the ethics-first branch (`checkEthics`, ethics modal, appeal submit, one-time-pass
   `appeal-allowance-check`) runs only if `caps.ethics`; otherwise `onBlocked` proceeds directly to
   the PII path.
3. Every `emitGovernance(...)` call is guarded by `caps.reporting`.
4. `recordFindings` / `recordIgnore` (local audit) are left as-is — local-only, harmless in Personal.

**`entrypoints/guard.content.ts`** returns immediately at the top of `main()` when `!caps.toolPolicy`
— in Personal it never polls, never warns, never emits.

**Mode-switch propagation:** the content scripts read the mode at load, so a switch takes effect on the
**next page load** of an open LLM tab. This matches how enrolment changes already propagate; there is
no live re-injection.

---

## 7. Testing (Vitest — existing runner)

- `capabilitiesFor()` — table test: Personal → all `false`; Enterprise → all `true`.
- `getMode`/`setMode` — round-trip and unset-default, using the `chrome.storage.local` Map shim
  already used in `tests/policy-client.test.ts`.
- `optionsView(mode)` — pure: `null → 'picker'`, `'personal' → 'personal'`, `'enterprise' →
  'enterprise'`.
- The full extension suite stays green and `npm run build` succeeds.

The four content-script seams are guarded by a single, tested pure function, so their correctness rests
on `capabilitiesFor` plus a straightforward read-and-branch — no DOM harness required.

---

## 8. Consequences & trade-offs

- **Unset mode defaults to Personal** everywhere it is read before a choice is made — fail-safe toward
  "nothing leaves the device," never toward silent reporting.
- **A mode switch needs a tab reload** to affect an already-open LLM page. Stated, not hidden; matches
  existing enrolment behaviour.
- **Local audit persists in Personal.** It never leaves the device, so it does not violate the privacy
  claim; it is simply unused by any Personal surface. Left in place to minimise change (YAGNI on
  clearing it).
- **Enterprise behaviour is byte-for-byte unchanged** — every gate is `capabilitiesFor('enterprise')`
  = all true, i.e. the current code path.
- **Pseudonymity/I3 untouched** — this sub-project adds no data collection; it only *removes* wiring in
  Personal.
