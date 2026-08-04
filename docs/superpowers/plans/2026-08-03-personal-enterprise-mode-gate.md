# Personal vs Enterprise Mode Gate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicit first-run Personal/Enterprise mode choice to the extension: Enterprise is today's full flow; Personal runs the same local detection engine with all org wiring (reporting, ethics, files, tool policy) removed so nothing leaves the device.

**Architecture:** A tiny `src/mode/` module holds the mode (in `chrome.storage.local`) and a pure `capabilitiesFor(mode)` returning four feature flags. The two content scripts read the mode once at load and consult those flags at four seams; the Options page routes to a picker / Personal panel / Enterprise settings; the popup and background adapt. No backend change.

**Tech Stack:** WXT, Preact, TypeScript, Vitest.

**Spec:** `docs/superpowers/specs/2026-08-03-personal-enterprise-mode-gate-design.md`.

## Global Constraints

- **Personal = all capabilities false; Enterprise = all true.** `capabilitiesFor('personal') → { reporting:false, ethics:false, files:false, toolPolicy:false }`; `capabilitiesFor('enterprise') → { reporting:true, ethics:true, files:true, toolPolicy:true }`.
- **Unset mode fail-safes to Personal** everywhere it is read before a choice is made: `capabilitiesFor((await getMode()) ?? 'personal')`.
- **The send-gate must register synchronously at `document_start`** (U12). In `content.ts`, `installGate(...)` runs BEFORE any `await`; the mode is resolved AFTER it. Never `await` before `installGate`.
- **Enterprise behaviour must stay byte-for-byte the current code path** — every gate evaluates to `true` under Enterprise.
- **I3 / privacy:** no new data collection. Do not add any field, log, or network call. This work only *removes* wiring in Personal.
- **Storage key:** `vg_mode`, values `'personal' | 'enterprise'`, absent ⇒ not chosen.
- **Commit the regenerated `dist/` with any entrypoint change.** `npm run build` runs `postbuild` (`check-dist-drift --write`) which updates the committed `dist/`; the `dist-drift` test fails if `dist/` is stale. Workflow for entrypoint tasks: edit `src`/`entrypoints` → `npm run build` → `npm test` (green) → commit `src` + `dist`.
- **Commits: sole author, no `Co-Authored-By` trailer.**
- **All commands run from `code/extension/`.** Tests: `npm test` (vitest run). Build: `npm run build`.

---

### Task 1: The mode module (pure logic + storage)

**Files:**
- Create: `code/extension/src/mode/mode.ts`
- Test: `code/extension/tests/mode.test.ts`

**Interfaces:**
- Produces:
  - `type Mode = 'personal' | 'enterprise'`
  - `type ModeCapabilities = { reporting: boolean; ethics: boolean; files: boolean; toolPolicy: boolean }`
  - `capabilitiesFor(mode: Mode): ModeCapabilities`
  - `getMode(): Promise<Mode | null>` (null = not chosen)
  - `setMode(mode: Mode): Promise<void>`
  - `optionsView(mode: Mode | null): 'picker' | 'personal' | 'enterprise'`

- [ ] **Step 1: Write the failing test**

```typescript
// code/extension/tests/mode.test.ts
import { describe, it, expect, beforeEach } from 'vitest';

// Map-backed chrome.storage.local shim (same pattern as tests/policy-client.test.ts).
const store = new Map<string, unknown>();
(globalThis as any).chrome = {
  storage: { local: {
    get: async (k: string) => ({ [k]: store.get(k) }),
    set: async (o: Record<string, unknown>) => { for (const k in o) store.set(k, o[k]); },
  } },
};

import { capabilitiesFor, getMode, setMode, optionsView } from '../src/mode/mode';

describe('capabilitiesFor', () => {
  it('personal disables every org capability', () => {
    expect(capabilitiesFor('personal')).toEqual(
      { reporting: false, ethics: false, files: false, toolPolicy: false });
  });
  it('enterprise enables every capability', () => {
    expect(capabilitiesFor('enterprise')).toEqual(
      { reporting: true, ethics: true, files: true, toolPolicy: true });
  });
});

describe('getMode/setMode', () => {
  beforeEach(() => store.clear());
  it('returns null when unset', async () => {
    expect(await getMode()).toBeNull();
  });
  it('round-trips a stored mode', async () => {
    await setMode('enterprise');
    expect(await getMode()).toBe('enterprise');
  });
});

describe('optionsView', () => {
  it('routes null to the picker', () => { expect(optionsView(null)).toBe('picker'); });
  it('routes personal to personal', () => { expect(optionsView('personal')).toBe('personal'); });
  it('routes enterprise to enterprise', () => { expect(optionsView('enterprise')).toBe('enterprise'); });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd code/extension && npm test -- mode`
Expected: FAIL (`Cannot find module '../src/mode/mode'`).

- [ ] **Step 3: Create `src/mode/mode.ts`**

```typescript
/**
 * Extension mode: Personal (local-only protection) vs Enterprise (org-governed).
 * One pure capabilities function is the single source of truth for every
 * mode-dependent seam, so no call site hard-codes a string comparison.
 */
export type Mode = 'personal' | 'enterprise';

export type ModeCapabilities = {
  reporting: boolean;   // send governance events to the policy server
  ethics: boolean;      // ethics detection + block + appeals
  files: boolean;       // file capture / cloud extract-redact
  toolPolicy: boolean;  // warn banner + enrolment/org surface
};

export function capabilitiesFor(mode: Mode): ModeCapabilities {
  const on = mode === 'enterprise';
  return { reporting: on, ethics: on, files: on, toolPolicy: on };
}

const KEY = 'vg_mode';

export async function getMode(): Promise<Mode | null> {
  const v = (await chrome.storage.local.get(KEY))[KEY] as Mode | undefined;
  return v === 'personal' || v === 'enterprise' ? v : null;
}

export async function setMode(mode: Mode): Promise<void> {
  await chrome.storage.local.set({ [KEY]: mode });
}

export function optionsView(mode: Mode | null): 'picker' | 'personal' | 'enterprise' {
  return mode ?? 'picker';
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd code/extension && npm test -- mode`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add code/extension/src/mode/mode.ts code/extension/tests/mode.test.ts
git commit -m "feat(ext): mode module with pure capabilities and storage"
```

---

### Task 2: Gate the content scripts by capability

**Files:**
- Modify: `code/extension/entrypoints/content.ts`
- Modify: `code/extension/entrypoints/guard.content.ts`

**Interfaces:**
- Consumes: `capabilitiesFor`, `getMode`, `ModeCapabilities` from `src/mode/mode.ts`.

- [ ] **Step 1: Edit `entrypoints/content.ts` — imports + async main + a resolvable `caps`**

Add the import near the other `src/...` imports:

```typescript
import { capabilitiesFor, getMode, type ModeCapabilities } from '../src/mode/mode';
```

Change the content-script definition to an **async** main and declare a mutable `caps` with a safe default at the very top of `main`, immediately after the adapter guard:

```typescript
  async main() {
    const adapter = pickAdapter(location.hostname);
    if (!adapter) return;

    // Resolved AFTER installGate (below) so gate registration stays synchronous
    // at document_start (U12). Until resolved, default to Personal — the private,
    // fail-safe direction. onBlocked/emit read this `let` at event time, long
    // after load, so they see the resolved value.
    let caps: ModeCapabilities = capabilitiesFor('personal');
```

- [ ] **Step 2: Edit `content.ts` — defer file capture behind the mode read**

The current code calls `installFileCapture({ ... })` near the top of `main`. **Cut that entire `installFileCapture({...});` call** from its current position and **paste it at the very end of `main`, wrapped in the mode read**, replacing the current trailing `adapter.onPaste(...)`-and-nothing-after region. Concretely, append this block as the LAST statements of `main` (after the `adapter.onPaste((text) => { ... });` call):

```typescript
    // Mode is resolved here, AFTER installGate/hints/scan are wired synchronously.
    caps = capabilitiesFor((await getMode()) ?? 'personal');

    // File capture is a cloud round-trip (extract/redact) -> Enterprise only.
    if (caps.files) {
      installFileCapture({
        onFiles: (picked) => {
          for (const file of picked) {
            if (file.size > CLIENT_LIMITS.maxUploadBytes) {
              showOversizedDialog({
                fileName: file.name,
                sizeBytes: file.size,
                onProceed: () => {
                  hideOversizedDialog();
                  const input = adapter.fileInputs()[0];
                  if (input) attachFiles(input, [file]);
                  else {
                    showRedactionFailure(
                      "Vanguard couldn't attach this file to the page. Please reload the tab and try again.",
                    );
                  }
                  void recordIgnore(
                    [{ cls: 'PERSON', start: 0, end: 0, text: '' }],
                    'file_unchecked:too_large: user trusted and attached without scan',
                  );
                },
                onDecline: () => { hideOversizedDialog(); },
              });
              continue;
            }
            const id = files.add(file);
            void processFile(files, id, defaultDeps(scanText));
          }
        },
      });
    }
```

(The body is the current `installFileCapture` argument verbatim — only its position and the `if (caps.files)` guard are new.)

- [ ] **Step 3: Edit `content.ts` — guard the ethics branch in `onBlocked`**

In `installGate({ ... onBlocked: async (text) => { ... } })`, the ethics section currently begins with `const ethics = checkEthics(text);`. Wrap the ethics handling so it only runs under `caps.ethics`. Replace:

```typescript
        const ethics = checkEthics(text);
        if (ethics) {
```

with:

```typescript
        const ethics = caps.ethics ? checkEthics(text) : null;
        if (ethics) {
```

(Everything inside `if (ethics) { ... }` is unchanged; in Personal `ethics` is `null`, so `onBlocked` falls through directly to the PII path.)

- [ ] **Step 4: Edit `content.ts` — guard every `emitGovernance` call**

There are three `emitGovernance({ ... })` calls in `onBlocked` (one `ethics_block`, one `pii_block` inside the findings loop, and the ethics one is already inside the now-guarded ethics branch). Guard the **two PII-path ones** with `caps.reporting`. For the `pii_block` loop, change:

```typescript
        for (const finding of promptDirty ? verdict!.findings : []) {
          emitGovernance({
            host: location.hostname,
            type: 'pii_block',
            category: finding.cls,
            ts: new Date().toISOString(),
          });
        }
```

to:

```typescript
        if (caps.reporting) {
          for (const finding of promptDirty ? verdict!.findings : []) {
            emitGovernance({
              host: location.hostname,
              type: 'pii_block',
              category: finding.cls,
              ts: new Date().toISOString(),
            });
          }
        }
```

The `ethics_block` `emitGovernance` is already inside `if (ethics)` (guarded by `caps.ethics`), so it needs no separate `caps.reporting` guard — ethics implies Enterprise. Leave it as-is.

- [ ] **Step 5: Edit `entrypoints/guard.content.ts` — early return in Personal**

Add the import at the top:

```typescript
import { capabilitiesFor, getMode } from '../src/mode/mode';
```

Change `main()` to async and return before any polling when tool policy is off:

```typescript
  world: 'ISOLATED',
  async main() {
    const caps = capabilitiesFor((await getMode()) ?? 'personal');
    if (!caps.toolPolicy) return;   // Personal: no warn banner, no polling, no events

    let shownFor: string | null = null;
```

(The rest of `main` is unchanged.)

- [ ] **Step 6: Build, sync dist, run the suite**

Run: `cd code/extension && npm run build && npm test`
Expected: build succeeds; **all tests pass** (the existing 321 + Task 1's 7; `dist-drift` passes because build rewrote `dist/`).

- [ ] **Step 7: Commit (src + regenerated dist)**

```bash
git add code/extension/entrypoints/content.ts code/extension/entrypoints/guard.content.ts code/extension/dist
git commit -m "feat(ext): gate reporting, ethics, files, and tool policy by mode"
```

---

### Task 3: Auto-open the picker on install

**Files:**
- Modify: `code/extension/entrypoints/background.ts`

**Interfaces:**
- Consumes: nothing from Task 1 (uses `chrome.runtime` directly).

- [ ] **Step 1: Add the install listener**

At the top of the `defineBackground(() => { ... })` body (right after `console.info('[vanguard] background alive');`), add:

```typescript
  // First run: land the user on the Personal/Enterprise chooser in Options.
  chrome.runtime.onInstalled.addListener((details) => {
    if (details.reason === 'install') void chrome.runtime.openOptionsPage();
  });
```

- [ ] **Step 2: Build, sync dist, run the suite**

Run: `cd code/extension && npm run build && npm test`
Expected: build succeeds; all tests pass.

- [ ] **Step 3: Commit**

```bash
git add code/extension/entrypoints/background.ts code/extension/dist
git commit -m "feat(ext): open the mode picker in options on install"
```

---

### Task 4: Options page — picker, Personal panel, mode routing

**Files:**
- Modify: `code/extension/entrypoints/options/main.tsx`

**Interfaces:**
- Consumes: `getMode`, `setMode`, `optionsView`, `type Mode` from `src/mode/mode.ts`; existing `clearEnrolment` from `src/policy/store`.

- [ ] **Step 1: Add imports**

Add to the imports at the top of `options/main.tsx`:

```typescript
import { getMode, setMode, optionsView, type Mode } from '../../src/mode/mode';
```

(`clearEnrolment` is already imported.)

- [ ] **Step 2: Add the `ModePicker` and `PersonalPanel` components**

Add these two components above `function Options()`:

```tsx
function ModePicker({ onChoose }: { onChoose: (m: Mode) => void }) {
  const card = 'flex:1;border:1px solid #e2e8f0;border-radius:10px;padding:20px;cursor:pointer;text-align:left;background:#fff';
  return (
    <section>
      <h2 style="font-size:16px">Choose how Vanguard runs</h2>
      <div style="display:flex;gap:16px;margin-top:12px">
        <button style={card} onClick={() => onChoose('personal')}>
          <strong style="display:block;font-size:15px;margin-bottom:6px">Personal</strong>
          <span style="color:#475569;font-size:13px">
            Protect your own sensitive data on this device. Nothing is sent anywhere.
          </span>
        </button>
        <button style={card} onClick={() => onChoose('enterprise')}>
          <strong style="display:block;font-size:15px;margin-bottom:6px">Enterprise</strong>
          <span style="color:#475569;font-size:13px">
            Connect to your organisation's policy, approvals, and file checking.
          </span>
        </button>
      </div>
    </section>
  );
}

function PersonalPanel({ onSwitch }: { onSwitch: () => void }) {
  return (
    <section>
      <h2 style="font-size:16px">Personal mode</h2>
      <p style="color:#475569">
        Vanguard protects sensitive data locally on ChatGPT and Claude. Nothing leaves this device —
        no organisation, no reporting, no file uploads.
      </p>
      <button onClick={onSwitch} style="padding:6px 12px;border:1px solid #cbd5e1;
              border-radius:6px;background:#fff;cursor:pointer">Switch to Enterprise</button>
    </section>
  );
}
```

- [ ] **Step 3: Rewrite `Options()` to route on mode**

Replace the existing `function Options() { ... }` with:

```tsx
function Options() {
  const [mode, setModeState] = useState<Mode | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => { void getMode().then((m) => { setModeState(m); setLoaded(true); }); }, []);

  async function choose(m: Mode) { await setMode(m); setModeState(m); }
  async function toPersonal() {
    await clearEnrolment();            // disconnect + stop reporting
    await setMode('personal');
    setModeState('personal');
  }

  const view = loaded ? optionsView(mode) : null;

  return (
    <div style="font:14px/1.5 system-ui, sans-serif; max-width:560px">
      <h1 style="font-size:18px">Vanguard</h1>
      {view === null && <p style="color:#64748b">Loading…</p>}
      {view === 'picker' && <ModePicker onChoose={choose} />}
      {view === 'personal' && <PersonalPanel onSwitch={() => void choose('enterprise')} />}
      {view === 'enterprise' && (
        <>
          <Organisation />
          <FileService />
          <MyReviews />
          <section style="margin-top:32px;border-top:1px solid #e2e8f0;padding-top:16px">
            <button onClick={() => void toPersonal()} style="padding:6px 12px;border:1px solid #cbd5e1;
                    border-radius:6px;background:#fff;cursor:pointer">Switch to Personal</button>
            <p style="color:#94a3b8;font-size:12px;margin-top:6px">
              Switching disconnects from your organisation and stops all reporting.
            </p>
          </section>
        </>
      )}
    </div>
  );
}
```

(The `Organisation`, `FileService`, `MyReviews` components and the bottom `render(<><Options /><SensitivityPanel /></>, ...)` are unchanged.)

- [ ] **Step 4: Build, sync dist, run the suite**

Run: `cd code/extension && npm run build && npm test`
Expected: build succeeds; all tests pass.

- [ ] **Step 5: Commit**

```bash
git add code/extension/entrypoints/options/main.tsx code/extension/dist
git commit -m "feat(ext): options picker, personal panel, and mode switching"
```

---

### Task 5: Popup — Personal vs Enterprise framing

**Files:**
- Modify: `code/extension/entrypoints/popup/main.tsx`

**Interfaces:**
- Consumes: `getMode`, `type Mode` from `src/mode/mode.ts`.

- [ ] **Step 1: Add imports and read the mode**

Add to the imports:

```typescript
import { getMode, type Mode } from '../../src/mode/mode';
```

In `Popup()`, add mode state and load it alongside the existing effects:

```typescript
  const [mode, setMode] = useState<Mode | null>(null);
```

Inside the existing `useEffect(() => { ... }, [])`, add:

```typescript
    void getMode().then(setMode);
```

- [ ] **Step 2: Branch the render on Personal**

Immediately before the existing `if (!enrolment || !policy) { ... }` block, add the Personal branch:

```tsx
  if (mode === 'personal') {
    return (
      <div style="width:300px;padding:16px;font:14px/1.5 system-ui,sans-serif">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px">
          <img src="/icon/48.png" style="width:24px;height:24px" alt="" />
          <h1 style="font-size:16px;margin:0">Vanguard</h1>
        </div>
        <p style="color:#0f172a;margin:0 0 6px 0"><strong>Personal mode</strong></p>
        <p style="color:#475569;margin:0">
          {host ? `Protecting sensitive data on ${host}.` : 'Protecting sensitive data on this device.'}
          {' '}Nothing leaves your device.
        </p>
      </div>
    );
  }
  if (mode === null) {
    return (
      <div style="width:300px;padding:16px;font:14px/1.5 system-ui,sans-serif">
        <p style="color:#475569;margin:0 0 12px 0">Choose Personal or Enterprise to get started.</p>
        <button onClick={openOptions} style="width:100%;padding:8px;border:none;
                border-radius:6px;background:#e11d48;color:#fff;cursor:pointer">Open settings</button>
      </div>
    );
  }
```

(`openOptions` and `host` are already defined above this point in `Popup()`. The Enterprise branches — the existing "not connected" prompt and the enrolled org view — remain unchanged below.)

- [ ] **Step 3: Build, sync dist, run the suite**

Run: `cd code/extension && npm run build && npm test`
Expected: build succeeds; all tests pass.

- [ ] **Step 4: Commit**

```bash
git add code/extension/entrypoints/popup/main.tsx code/extension/dist
git commit -m "feat(ext): popup reflects personal vs enterprise mode"
```

---

### Task 6: Manual acceptance (verification only)

**Files:** none.

- [ ] **Step 1: Load the unpacked build**

Run: `cd code/extension && npm run build`. In Chrome → Extensions → Developer mode → Load unpacked → select `code/extension/dist/chrome-mv3`.

- [ ] **Step 2: Verify first-run + Personal**

Confirm the Options page opens on install showing the two-card picker. Choose **Personal**. On `https://chatgpt.com`: type a prompt containing an NRIC/email → the PII modal appears and masking works; press Send after masking → it sends. Confirm **no** org warn-banner appears, and the popup shows "Personal mode … Nothing leaves your device." (No policy server needs to be running.)

- [ ] **Step 3: Verify Enterprise unchanged**

In Options, **Switch to Enterprise**, enrol with a token (needs the policy service from the hierarchy work running). Confirm the warn-banner, approvals, and file checking behave exactly as before. Switch back to **Personal** and confirm it disconnects.

- [ ] **Step 4: Commit any doc fixes surfaced**

```bash
git add -A && git commit -m "docs: acceptance fixes for mode gate" || echo "nothing to fix"
```

---

## Self-Review

**Spec coverage:** §2 behaviour table → Task 1 (`capabilitiesFor`) + Task 2 (the four seams). §3 mode model → Task 1. §4 first-run auto-open → Task 3; Options routing/picker/Personal panel/switch → Task 4. §5 popup → Task 5. §6 content-script gating (4 seams + guard early-return, gate-registers-first) → Task 2. §7 testing → Task 1 unit tests + build/suite gates in Tasks 2–5. §8 consequences: unset→Personal (Task 1 `?? 'personal'` in Tasks 2/4/5), reload-to-switch (inherent — content scripts read at load), Enterprise unchanged (every flag true → current path).

**Placeholder scan:** every code step contains complete code or an exact old→new edit; every run step has a command + expected result. No TBD/TODO.

**Type consistency:** `Mode`, `ModeCapabilities`, `capabilitiesFor`, `getMode`, `setMode`, `optionsView` are defined in Task 1 and consumed with those exact names/signatures in Tasks 2, 4, 5. `caps.reporting`/`caps.ethics`/`caps.files`/`caps.toolPolicy` match the `ModeCapabilities` fields. Popup shadows the imported `setMode` name with a local `useState` setter `setMode` — Task 5 uses `getMode` only (never calls the module `setMode`), so there is no collision; the local setter is the state updater. (Options uses a distinct local setter `setModeState` to avoid shadowing the imported `setMode` it *does* call.)

**Timing check:** Task 2 keeps `installGate` synchronous and resolves the mode only afterward, honoring the U12 document_start constraint from Global Constraints.
