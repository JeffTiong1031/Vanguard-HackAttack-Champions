# Vanguard ΓÇö comprehensive test guide

**Scope:** every shipped feature of the browser extension and the governance dashboard, with a
step-by-step procedure and a checkbox per claim.

**Written:** 2026-08-05, against `main` @ `3b353c6`. Built by reading the source, not by inheriting
the older checklists ΓÇö [`code/extension/ACCEPTANCE.md`](code/extension/ACCEPTANCE.md) is still the
Slice 1 / Slice 2 acceptance record and this document does not replace it.

> ### ≡ƒö┤ Read this before following any older runbook
>
> Four things changed in the last 63 commits and the existing docs have **not** caught up. Following
> them will send you looking for UI that no longer exists.
>
> | Older doc says | Reality in the code today |
> |---|---|
> | Log in as **`Acme Corp` / `vanguard`** (`ref/README.md` ┬º1) | Login is a **role picker** (Company Admin / Department Admin) + a **secret key**. No org-name field. `admin/src/screens/Login.tsx` |
> | Data lives in **SQLite `policy.db`**; delete it to reseed | Data lives in **Supabase Postgres** via `DATABASE_URL`. There is no `policy.db`. `app/db.py`, `SUPABASE_SETUP.md` |
> | Console ΓåÆ **Requests** ΓåÆ **Approve** (as the company admin) | The **company** dashboard is **read-only** for Requests and Reviews (`readOnly = scope === 'company'`). Only a **Department Admin** can approve or block. |
> | Console tabs: **Tools**, **Usage**, **Reviews** | Six tabs per role, renamed and regrouped ΓÇö see ┬º2.2 |
>
> `ref/README.md` is the moved root README (commit `37fd568`). Treat its *setup* steps as stale and
> its *test prompts* as still good.

---

## 0. How to use this document

- **┬º1** is the feature inventory ΓÇö what exists, and where it is tested below.
- **┬º2** is environment setup. Do it once. Nothing below works without it.
- **┬º3** is the automated gates. Run them first; they are cheap and they fail loudly.
- **┬º4** tests the **extension**. **┬º5** tests the **dashboard**. **┬º6** is end-to-end.
- **┬º7** is the privacy invariants ΓÇö the rows a compliance buyer would actually audit.
- **┬º8** is the known gaps. **Do not invent a PASS for anything in ┬º8.**

**Marking:** leave a box blank until you have observed it. Use `PASS` / `FAIL` / `SKIP` / `BLOCKED`.
A step you did not run is `SKIP`, not an empty pass.

**Two surfaces:** every extension test runs on **both** `https://chatgpt.com` **and**
`https://claude.ai` unless a step says otherwise. The adapters are separate code paths and break
independently (doc 05 ┬º4.4).

---

## 1. Feature inventory

### 1.1 Browser extension

| # | Feature | Where it lives | Mode | Tested in |
|---|---|---|---|---|
| E1 | **Personal / Enterprise mode gate** ΓÇö first-run picker, capability switch | `src/mode/mode.ts`, `entrypoints/options` | both | ┬º4.1 |
| E2 | **L1 deterministic detectors** ΓÇö NRIC, SSM, TIN, email, card | `src/detection/l1/` | both | ┬º4.3 |
| E3 | **L1 typing hints** ΓÇö rose underline, hover popover, Accept / Dismiss; never blocks Send | `src/ui/composer-hints` | both | ┬º4.2 |
| E4 | **L2 on-device NER** ΓÇö stock multilingual PERSON / ORG (LOC off), ONNX in offscreen doc | `src/detection/l2/`, `entrypoints/offscreen` | both | ┬º4.3 |
| E5 | **Send-time gate** ΓÇö capture at `window`, `composedPath()`, Enter + click + submit | `src/gate/` | both | ┬º4.3 |
| E6 | **Send-time per-span review** ΓÇö Accept / Ignore-with-reason, Proceed gated on every span | `src/ui/send-review-logic.ts`, `review-panes.ts` | both | ┬º4.3 |
| E7 | **Approval token** ΓÇö hash-bound, single-use, 60 s TTL; **you** press Send | `src/gate/approval-token.ts` | both | ┬º4.3 |
| E8 | **Span repair** ΓÇö pulls the honorific into the masked span (`Encik Rahman`, `µ₧ùσÑ│σú½`) | `src/detection/l2/span-repair.ts` | both | ┬º4.4 |
| E9 | **Org dictionary** ΓÇö exact-match, case-sensitive; inert unless loaded | `src/detection/l2/org-dictionary.ts` | both | ┬º4.5 |
| E10 | **Ethics classifier** ΓÇö 6 categories, on-device TF-IDF + LinearSVC, blocks outright | `src/detection/ethics/`, `code/classifier/` | Enterprise | ┬º4.6 |
| E11 | **Appeals / request a review** ΓÇö opt-in text disclosure, one-time pass on overturn | `src/policy/appeals.ts`, `src/ui/ethics-modal` | Enterprise | ┬º4.7, ┬º6.3 |
| E12 | **Voice data-leak warning** ΓÇö intercepts mic-start controls, anchored dropdown | `src/ui/voice-warning.ts` | both | ┬º4.8 |
| E13 | **File capture + content checking** ΓÇö hold attach, cloud extract, on-device detect, redact | `src/files/` | Enterprise | ┬º4.9 |
| E14 | **Oversize dialog** ΓÇö files over the client limit | `src/ui/oversized-dialog.tsx` | Enterprise | ┬º4.9 |
| E15 | **Tool-policy warn banner** ΓÇö amber banner on unapproved tools, 8-host registry | `entrypoints/guard.content.ts`, `src/ui/warn-banner.ts` | Enterprise | ┬º4.10 |
| E16 | **Request access** ΓÇö from the banner, one click + reason | `guard.content.ts` ΓåÆ `/v1/requests` | Enterprise | ┬º4.10, ┬º6.2 |
| E17 | **Enrolment** ΓÇö paste token, exchange once for a pseudonymous id | `src/policy/store.ts`, options page | Enterprise | ┬º4.1 |
| E18 | **Popup** ΓÇö tool status, org, department, policy version | `entrypoints/popup` | both | ┬º4.11 |
| E19 | **My reviews** ΓÇö appeal outcomes in the options page | options page | Enterprise | ┬º4.7 |
| E20 | **Degrade to advisory** ΓÇö dead engine never fail-closes (ADR 0014) | `content.ts`, `src/ui/mount.ts` | both | ┬º4.12 |
| E21 | **Local audit log** ΓÇö class + count + salted hash only (I3 / U26) | `src/audit/audit.ts` | both | ┬º7 |

### 1.2 Governance dashboard

Served by the policy service at `/`. Two roles, six tabs each ΓÇö **the tab set differs by role**.

| # | Tab | Company Admin | Department Admin | Tested in |
|---|---|---|---|---|
| D1 | **Insider Risk** ΓÇö risk timeline, risky ranks, alerts table | whole org | own dept only | ┬º5.4 |
| D2 | **AI Usage & Telemetry** ΓÇö usage trend, top apps / employees / departments | whole org | own dept only | ┬º5.5 |
| D3 | **Access Requests** ΓÇö tool access approvals | **read-only** | **decides** | ┬º5.6 |
| D4 | **Prompt Audits & Appeals** ΓÇö contested blocks | **read-only** | **decides** | ┬º5.7 |
| D5 | **Tools Policy Matrix** (company) / **Department Tools** (dept) | approve / block 8 tools | view | ┬º5.8 |
| D6 | **Departments & Secrets** (company) / **Employee Tokens** (dept) | create dept, regenerate secret | mint / revoke token | ┬º5.9, ┬º5.10 |
| D7 | **Signup** ΓÇö provision a new organisation, secret shown once | public | ΓÇö | ┬º5.2 |
| D8 | **Login** ΓÇö role picker + secret, `vg_admin` cookie session | both | both | ┬º5.3 |

### 1.3 Backend services

| Service | Port | Purpose | Needed for |
|---|---|---|---|
| `code/policy` | 8001 | Org state, policy, requests, appeals, events, analytics ΓÇö **and serves the dashboard at `/`** | Enterprise mode, all of ┬º5 |
| `code/backend` | 8000 | `/v1/extract` + `/v1/redact` ΓÇö parses files, masks them. **No detection.** | File checking (E13) only |

Chat-only testing (E2ΓÇôE8, E12) needs **neither** service.

---

## 2. Environment setup

### 2.1 What is already installed on this machine

Checked 2026-08-05. Fill the gaps before the sections that need them.

| Path | State | Needed for |
|---|---|---|
| `code/policy/.venv` | Γ£à present | ┬º5, ┬º6 |
| `code/policy/app/static` (built console) | Γ£à present | ┬º5 |
| `code/policy/.env` | Γ£à present | ┬º5, ┬º6 |
| `code/policy/admin/node_modules` | Γ£à present | rebuilding the console |
| `code/extension/node_modules` | Γ¥î **missing** | ┬º3 automated gates only |
| `code/backend/.venv` | Γ¥î **missing** | ┬º4.9 file checking |
| `code/classifier/.venv` | Γ¥î **missing** | ┬º3 classifier tests only |

Loading the extension unpacked needs **none** of these ΓÇö `dist/` is committed.

### 2.2 Policy service + dashboard

> ≡ƒö┤ **`DATABASE_URL` points at a live Supabase Postgres.** There is no local database file. Whatever
> that connection string points at is what you are testing against **and writing into**. Check
> `code/policy/.env` before you seed or run pytest.

```bash
cd code/policy
# one-time, if .venv is missing:
python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"
# one-time, if app/static is missing:
cd admin && npm install && npm run build && cd ..

.venv/Scripts/python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

- [ ] `http://localhost:8001/healthz` returns `{"ok":true}`
- [ ] `http://localhost:8001/` serves the console (not a 404)

> ≡ƒö┤ **If `/` 404s:** the static mount is decided **once, at import time**. Build the console, then
> **restart uvicorn** ΓÇö reloading the browser does nothing. The server logs
> `console not built: ΓÇª / will 404` at startup when this happens.

**Demo data (optional but recommended):**

```bash
cd code/policy && .venv/Scripts/python scripts/seed.py
```

Creates `Acme Corp` with Engineering / Sales / Compliance, 2 employee tokens each, and **30 days of
synthetic telemetry** so the dashboards have curves instead of two points. Every secret is written to
`code/policy/DEMO-TOKENS.md` (git-ignored).

- [ ] `DEMO-TOKENS.md` exists and holds 1 company secret, 3 department secrets, 6 employee tokens

> ΓÜá∩╕Å Seeded telemetry is **synthetic** (`SEED_RNG = 20260804`, fixed). It proves the charts render.
> It proves nothing about detection quality.

### 2.3 File-checking backend (only for ┬º4.9)

```bash
cd code/backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # PowerShell;  macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- [ ] `http://127.0.0.1:8000/healthz` returns `{"ok":true}`

Alternative: `docker compose up --build` in the same directory, or the hosted demo host
(`https://vanguard-extract.onrender.com` ΓÇö needs the demo access key, and wake it first; the free
tier sleeps).

### 2.4 Load the extension

1. Chrome ΓåÆ `chrome://extensions` ΓåÆ **Developer mode** on
2. **Load unpacked** ΓåÆ `code/extension/dist/chrome-mv3`
3. Open the extension **Options** page

- [ ] Extension loads with no manifest error
- [ ] Options page shows the **Personal / Enterprise** picker on first run

> First on-device L2 scan downloads quantized NER weights from a public CDN (hash-verified). On a
> cold cache this can take **up to a minute** ΓÇö the in-code timeout is 120 s. A "protection degraded"
> banner during the first scan is expected; it should clear once the download lands.

---

## 3. Automated gates

Run these before any manual session. Record the actual output ΓÇö a claimed check is not a check.

| Gate | Command | Expected | Last run here |
|---|---|---|---|
| Extension unit + integration | `cd code/extension && npm install && npx vitest run` | all pass | not run ΓÇö deps missing |
| Committed `dist/` matches `src/` | `cd code/extension && npm run check:dist` | exit 0 | not run ΓÇö deps missing |
| Policy service | `cd code/policy && .venv/Scripts/python -m pytest -q` | all pass | Γ£à **133 passed, 2026-08-05** ΓÇö took **18m 21s** |
| File backend | `cd code/backend && python -m pytest -q` | all pass | not run ΓÇö venv missing |
| Ethics classifier | `cd code/classifier && .venv/Scripts/python -m pytest -q` | all pass | not run ΓÇö venv missing |

> ≡ƒö┤ **Budget 20 minutes for the policy suite, and do not kill it early.** 133 tests took **18m 21s**
> on this machine ΓÇö roughly **8 seconds per test**, because every one round-trips to a Supabase
> pooler in `ap-northeast-1` (Tokyo). It produces **no output at all until it finishes**, so it looks
> identical to a hang for the first eighteen minutes. It is not hanging. It is paying network latency
> per test.

> ≡ƒö┤ **`check:dist` is not optional.** `dist/` is a committed build artifact and a second source of
> truth. If it drifts, the team tests code that no longer exists (ADR 0017 ┬º3).

> ≡ƒö┤ **The policy test suite is NOT hermetic.** `tests/conftest.py` points pytest at the real
> `DATABASE_URL` and the tests write rows into it. Run it against a throwaway Supabase project, not
> against anything you care about. **133 tests ├ù ~8 s of round trips is also 133 tests' worth of rows
> written into whatever that connection string points at.**

> ΓÜá∩╕Å `npm install` has not been run in `code/extension` on this machine, so the first two gates are
> currently **unrunnable** ΓÇö `vitest` is not installed. That does not block manual testing.

---

## 4. Extension test procedures

### 4.1 Mode gate + enrolment (E1, E17)

The mode picker is the first decision and it gates four capabilities at once
(`capabilitiesFor()` ΓÇö reporting, ethics, files, toolPolicy).

**Personal mode**

1. Options page ΓåÆ **Personal**
- [ ] Options shows the Personal panel ΓÇö no Organisation section, no File checking section
- [ ] Popup shows *"Personal mode ΓÇª Nothing leaves your device"*
- [ ] On chatgpt.com: typing hints and the PII send gate **still work** (local scanning is not gated)
- [ ] Open `https://gemini.google.com` ΓåÆ **no** amber banner (toolPolicy off)
- [ ] Send an ethics-violating prompt (┬º4.6) ΓåÆ **not blocked** (ethics off in Personal)
- [ ] Attach a file ΓåÆ **not intercepted** (files off in Personal)

**Enterprise mode + enrolment**

2. Options ΓåÆ **Switch to Enterprise** ΓåÆ Organisation section appears
3. Set policy address `http://localhost:8001`, paste an employee token from `DEMO-TOKENS.md`
4. **Connect**

- [ ] Shows *"Connected to Acme Corp ┬╖ Engineering ┬╖ N approved tools ┬╖ policy vN"*
- [ ] Popup now shows the org, department, and policy version
- [ ] **Disconnect** clears it; **Switch to Personal** also disconnects and stops reporting

> Test the PersonalΓåÆEnterpriseΓåÆPersonal round trip explicitly. `toPersonal()` calls
> `clearEnrolment()` **before** setting the mode ΓÇö if reporting survived the switch that would be a
> privacy defect, not a cosmetic one.

### 4.2 Typing hints (E3)

On both surfaces, in the composer:

- [ ] Type `My IC is 880101-14-5566` ΓåÆ **rose underline** under the IC while typing
- [ ] Send is **not** blocked by the underline alone (hints are advisory, ADR 0024)
- [ ] Hover the underline ΓåÆ popover with the **class** and a **recommendation**
- [ ] **Accept** ΓåÆ that span becomes `NRIC_1`; the text is still editable afterwards
- [ ] **Dismiss** ΓåÆ underline disappears and stays gone until the span text changes
- [ ] Type `what is 1 + 1` ΓåÆ **no** underline (the arithmetic guardrail: L1 matches identifier
      grammars, never "a number is present")
- [ ] Type a bare year like `2026` ΓåÆ **no** underline

### 4.3 Send-time gate + per-span review (E2, E4, E5, E6, E7)

- [ ] Type `Please call Ahmad about the deal.` ΓåÆ press Enter ΓåÆ **blocked**, review popup opens
- [ ] The popup is the **per-span review** (Accept / Ignore each span), not a bulk-approve modal
- [ ] **Proceed is disabled** until every span is either Accepted or Ignored
- [ ] **Ignore requires a reason** ΓÇö an empty reason will not submit
- [ ] Accept all ΓåÆ composer holds `Please call PERSON_1 about the deal.`, caret at end, focus in the
      composer
- [ ] **You** press Enter ΓåÆ it sends. Nothing auto-submitted (decision #8)
- [ ] Press Enter again on the same (now clean) text ΓåÆ sends normally
- [ ] Repeat the whole flow using the **mouse Send button** instead of Enter ΓÇö the click path is a
      separate branch (`adapter.isSendControl`) and Enter passing proves nothing about it
- [ ] Paste `IC 890101-14-5555 and email me at a@b.com` ΓåÆ blocked; both NRIC and EMAIL appear
- [ ] Type `explain Einstein's theory` ΓåÆ **blocked** (stock NER PERSON). **This false positive is
      expected and is the measurement** ΓÇö Ignore-with-reason "public figure" and send
- [ ] Type `summarise Apple's earnings` ΓåÆ blocked on ORG. Same story
- [ ] Type `flights from Kuala Lumpur to Tokyo` ΓåÆ **NOT blocked** (LOC is off by design, ┬º8.1)
- [ ] Compose Chinese via Microsoft Pinyin ΓåÆ Enter **commits candidates normally**; only a
      send-intent Enter is gated (U12-b)
- [ ] Shift+Enter inserts a newline and does not trigger the gate

**Approval-token edge cases**

- [ ] After Accept ΓåÆ Proceed, **edit the composer**, then press Send ΓåÆ blocked again (the token is
      invalidated by any edit)
- [ ] After Proceed, wait **over 60 s**, then press Send ΓåÆ blocked again (TTL expiry)
- [ ] Cold-cache clean paste ΓåÆ immediate Send: the first press may be swallowed with no modal and a
      **second** press is required. This is fail-safe, not fail-open ΓÇö record it if you see it

### 4.4 Span repair (E8)

Stock NER proposes `Rahman`; the mask must cover `Encik Rahman` or the honorific is left behind as a
re-identification pointer (doc 04 ┬º4.3).

- [ ] `Tolong ingatkan Encik Rahman pasal mesyuarat.` ΓåÆ masks **`Encik Rahman`**.
      **If you see `Encik PERSON_1`, repair is not running.**
- [ ] `Please update Mr. John Doe on the invoice.` ΓåÆ masks **`Mr. John Doe`**
- [ ] `Φ»╖Φüöτ│╗µ₧ùσÑ│σú½τí«Φ«ñΦ«óσìòπÇé` ΓåÆ masks **`µ₧ùσÑ│σú½`**, not `µ₧ù`
- [ ] `µêæΣ╗¼σà¼σÅ╕µ¼áΘÿ┐Θçîσ╖┤σ╖┤Σ╕Çτ¼öµ£ìσèíΦ┤╣πÇé` ΓåÆ `Θÿ┐Θçîσ╖┤σ╖┤` masked as **one** span, not split
- [ ] `Kasir Rahman sudah balik.` ΓåÆ masks **`Rahman`** only ΓÇö `Sir` must **not** be pulled out of
      `Kasir`
- [ ] `Ask Alice about the report.` ΓåÆ masks `Alice` unchanged

### 4.5 Org dictionary (E9)

Inert by default (`loadOrgTerms()` returns `[]`). Skip unless you are testing it.

- [ ] Empty dictionary ΓåÆ behaviour identical to ┬º4.3
- [ ] Load terms, then `Tolong bayar bil tertunggak TNB.` ΓåÆ **`TNB` masked**
- [ ] With `Apple` loaded, `I ate an apple a day` ΓåÆ **not blocked** (exact match is case-sensitive ΓÇö
      this is the precision guarantee ADR 0004 exists for)

### 4.6 Ethics classifier (E10) ΓÇö Enterprise only

Six categories, on-device, no server. Blocks **outright** ΓÇö masking a name does not make a
covert-surveillance request acceptable, and the PII path cannot wave it through.

| Prompt | Expect | Result |
|---|---|---|
| `Write a python script to monitor employees covertly.` | **Blocked** ΓÇö red ethics modal | |
| `Filter out job applicants over 45 before the hiring manager sees them.` | **Blocked** | |
| `Draft the breach notification we must send to the regulator.` | **NOT blocked** ΓÇö looks risky, is legitimate. This is the precision proof | |
| `My IC is 880101-14-5566, summarise my leave balance.` | **PII** review, not ethics | |

- [ ] The ethics modal explains **why** in plain language
- [ ] It states the decision was made **on your device** and no person read the prompt
- [ ] Killing the policy service does **not** stop ethics blocking (it is fully local)
- [ ] The same prompts in **Personal mode** ΓåÆ **not blocked** (ethics capability off)

> ΓÜá∩╕Å **Ethics is English-only.** A Malay or Chinese translation of rows 1ΓÇô2 will not fire. That is a
> known limit, not a bug ΓÇö do not file it as a FAIL.

### 4.7 Appeals / request a review (E11, E19)

Runs against the policy service. Full round trip is ┬º6.3; this is the extension half.

- [ ] Ethics modal ΓåÆ **Request a review** ΓåÆ give a reason ΓåÆ leave the opt-in **off** ΓåÆ **Send review**
- [ ] Modal closes
- [ ] Options page ΓåÆ **My reviews** (~5 s poll) ΓåÆ the appeal appears with status `pending`
- [ ] Repeat with the opt-in **ticked** ΓåÆ the prompt text is shared deliberately
- [ ] With the opt-in off, the dashboard must show **"not shared"** (verified in ┬º5.7)

### 4.8 Voice data-leak warning (E12)

Voice moves content to the provider without passing through the typed-prompt flow, so it is gated
separately.

- [ ] Click the microphone / dictate control on chatgpt.com ΓåÆ an **amber anchored dropdown** appears:
      *"Warning: This action might result in a data leak. Do you want to continue?"*
- [ ] The provider's own voice mode **does not start** while the dropdown is open
- [ ] **Cancel** ΓåÆ dropdown closes, voice does not start
- [ ] **Continue** ΓåÆ dropdown closes and voice **does** start (the click is replayed once)
- [ ] Clicking a **stop / end / cancel** voice control does **not** raise the warning
- [ ] Clicking elsewhere on the page dismisses an open dropdown
- [ ] Repeat on claude.ai

### 4.9 File content checking (E13, E14) ΓÇö Enterprise only

**Requires the `code/backend` service on port 8000** and Options ΓåÆ File checking pointed at it.

| # | Step | Expect | ChatGPT | Claude |
|---|---|---|---|---|
| F1 | Attach a clean `.txt`, clean prompt, Send | Review ΓåÆ Proceed ΓåÆ **you** Send; file goes | | |
| F2 | Attach a `.docx` containing `880101-14-5566` | Chip appears; status **Reading ΓåÆ Checking ΓåÆ Checked** | | |
| F3 | Press Send | Review opens; **Prompt** tab first, **File** tab badged | | |
| F4 | Hover the NRIC in the File tab | Why + recommendation + Accept + Ignore | | |
| F5 | Accept ΓåÆ Proceed | `.redacted.docx` attached; **you** press Send | | |
| F6 | Download it, open in Word | Opens cleanly; the IC is masked | | |
| F7 | CSV with an IC | `.redacted.csv` | | |
| F8 | Ignore a span with a reason | **Original** `.docx` re-attached | | |
| F9 | File **larger than the client limit** | Oversize dialog; Proceed / Don't attach both work | | |
| F10 | Scanned (image-only) PDF | `no_text_layer` ΓÇö never "all good" | | |
| F11 | Password-protected DOCX | `password_protected` | | |
| F12 | Stop the API, then attach | `network` message; **the prompt gate still works** | | |
| F13 | Stop the API **after** review, then Proceed | Red failure banner; **nothing is attached** | | |
| F14 | Send before the chip reads `Checked` | Blocked; File tab shows `CheckingΓÇª` | | |
| F15 | Drag-and-drop a PDF | Same as F2 | | |
| F16 | Paste an image | `unsupported_type` | | |
| F17 | Attach two files at once | Two chips, two tabs | | |
| F18 | Acknowledge "unchecked" + Proceed | Original attaches; audit records the **reason**, never the filename | | |

> ≡ƒö┤ **F13 is the important one.** Redaction is a network round trip and it can fail. It must fail
> into *"nothing attached and you were told"* ΓÇö never into *"attach the original"* (a leak) and never
> into *"attach a `.txt`"* (a silent format change nobody asked for).

### 4.10 Tool-policy warn banner + access request (E15, E16) ΓÇö Enterprise only

Registry hosts: chatgpt.com, claude.ai, gemini.google.com, copilot.microsoft.com, perplexity.ai,
chat.deepseek.com, chat.mistral.ai, grok.com.

- [ ] Enrolled, open `https://gemini.google.com` ΓåÆ **amber banner**: not approved at Acme Corp
- [ ] **The page still works** ΓÇö nothing is blocked, this is advisory (ADR 0014)
- [ ] The banner explains **why** it is unapproved
- [ ] The banner does not cover the page content
- [ ] **Dismiss** ΓåÆ gone for this page load; **reload** ΓåÆ it warns again
- [ ] **Request access** ΓåÆ type a reason ΓåÆ *"Request sent"*
- [ ] Open an **approved** tool (chatgpt.com) ΓåÆ **no** banner
- [ ] Stop the policy service ΓåÆ the banner state does not crash the page; the cached policy holds

### 4.11 Popup (E18)

- [ ] Not connected ΓåÆ *"Vanguard is not connected to an organisation"* + **Connect** button
- [ ] Connected, on an **approved** host ΓåÆ green **Approved** pill + *"approves this tool for work"*
- [ ] Connected, on an **unapproved** host ΓåÆ amber **Unapproved** pill
- [ ] Connected, on a non-registry host ΓåÆ *"Vanguard is active on <host>"*
- [ ] Footer shows **Department** and **Policy vN**
- [ ] The ΓÜÖ button opens the Options page

### 4.12 Degradation (E20)

- [ ] `chrome://extensions` ΓåÆ inspect the offscreen document ΓåÆ **close it** mid-session
- [ ] Next send ΓåÆ **"protection degraded"** surfaced, and the send **does not hang**
- [ ] It degrades to **advisory** ΓÇö it does **not** fail closed (ADR 0014)
- [ ] The banner **clears itself** once a scan completes again
- [ ] Stop the policy service, then send a prompt ΓåÆ the PII gate still works (it is local)

---

## 5. Dashboard test procedures

Base URL `http://localhost:8001/`.

### 5.1 Console loads

- [ ] `/` serves the console, not a 404 (if it 404s, see ┬º2.2 ΓÇö restart uvicorn)
- [ ] Sidebar collapses and expands; breadcrumbs track the active tab
- [ ] Top bar shows **Live Guard**, **Org**, and (department role only) **Dept**

### 5.2 Signup (D7)

- [ ] Login screen ΓåÆ **Provision Organization**
- [ ] Enter a company name ΓåÆ submit
- [ ] A **Company Admin secret** is returned and displayed **once**
- [ ] Copy it. Reload the page ΓåÆ **it is not shown again** (stored only as a SHA-256 hash)
- [ ] The new secret logs in as Company Admin

### 5.3 Login + session (D8)

- [ ] **Company Admin** + company secret ΓåÆ company dashboard (6 tabs, ┬º1.2)
- [ ] **Department Admin** + department secret ΓåÆ department dashboard
- [ ] A **department** secret submitted under the **Company** role ΓåÆ *"not recognised for this role"*
- [ ] A wrong secret ΓåÆ the same message, with no hint about which part was wrong
- [ ] Reload the page ΓåÆ the session persists (`vg_admin` cookie)
- [ ] **Sign Out** ΓåÆ returns to login; reloading does not restore the session
- [ ] Stop the policy service, reload ΓåÆ *"Authenticating security sessionΓÇª"* resolves within ~5 s and
      falls back to login rather than hanging forever

> ≡ƒö┤ **Authority is server-side on every request.** Editing `localStorage.vg_admin_session` to say
> `"role":"company"` must **not** grant company routes ΓÇö the server decides from the cookie. Try it.

### 5.4 Insider Risk (D1)

- [ ] Risk timeline renders with a curve (needs seeded or real telemetry)
- [ ] Alerts table lists ts / department / name / host / action / severity
- [ ] Severity buckets look right: blocks = **high**, warns = **medium**, plain visits = **low**
- [ ] The alerts table scrolls rather than pushing the page wide
- [ ] Switching the window (7 / 30 days) changes the granularity ΓÇö hourly under 7 days, daily above
- [ ] **As Department Admin:** only that department's rows appear. Cross-check against the company
      view, which should show strictly more

### 5.5 AI Usage & Telemetry (D2)

- [ ] Usage trend renders by department over time, with axes
- [ ] Top apps / top employees / top departments populate and are ordered by risk then events
- [ ] Totals show event count and active employees
- [ ] Employee rows show the **admin-supplied name** or `Unnamed` ΓÇö never a prompt
- [ ] ≡ƒö┤ **No prompt text anywhere on this screen.** Only class, count, host, type, timestamp, name
- [ ] **As Department Admin:** scoped to that department only

### 5.6 Access Requests (D3)

**Department Admin** (the role that can decide):

- [ ] Pending requests appear within ~3 s of being sent from the extension
- [ ] Each row shows the tool, department, and the employee's reason
- [ ] Filters (all / pending / approved / blocked) and search both work
- [ ] **Approve** ΓåÆ status flips to `approved`
- [ ] **Block** ΓåÆ the **Block button is disabled until an explanation is typed**
- [ ] A blocked decision records a reason code and note

**Company Admin:**

- [ ] The same rows are visible **read-only** ΓÇö no Approve / Block controls
- [ ] Confirm this is intentional (`readOnly = scope === 'company'`), not a rendering bug

### 5.7 Prompt Audits & Appeals (D4)

**Department Admin:**

- [ ] An appeal submitted from the extension appears within ~3 s
- [ ] It shows category + department + the employee's reason
- [ ] ≡ƒö┤ **Shared text reads "not shared"** when the employee left the opt-in off ΓÇö this is the row a
      privacy auditor checks first
- [ ] With the opt-in ticked, the exact shared prompt appears
- [ ] Add a note ΓåÆ **Overturn** ΓåÆ status flips to `overturned`
- [ ] **Uphold** requires an explanation, same as Block
- [ ] The employee sees the outcome in **Options ΓåÆ My reviews** within ~5 s

**Company Admin:**

- [ ] Read-only, same as ┬º5.6

### 5.8 Tools policy (D5)

**Company Admin ΓÇö Tools Policy Matrix:**

- [ ] Eight tools listed; ChatGPT + Claude approved, the rest blocked (seeded default)
- [ ] Toggling a tool's status persists across a reload
- [ ] Every policy write **bumps the policy version** ΓÇö check the version in the extension popup
      changes after a toggle
- [ ] An enrolled extension picks up the change within ~5 s (the poll interval)

**Department Admin ΓÇö Department Tools:**

- [ ] Shows the effective tool list for that department
- [ ] Confirm whether it is view-only in your build and record which

### 5.9 Departments & Secrets (D6, company)

- [ ] Create a department ΓåÆ a **Department Admin secret** is shown **once**
- [ ] That secret logs in as Department Admin for that department
- [ ] **Regenerate** ΓåÆ a new secret is issued and the **old one stops working**
- [ ] The department list shows every department with its employee count

### 5.10 Employee Tokens (D6, department)

- [ ] **Mint** a token with a name/ID label ΓåÆ the token is shown once
- [ ] Pasting it into the extension enrols successfully (┬º4.1)
- [ ] The token's label appears against that employee in the analytics screens
- [ ] **Revoke** ΓåÆ the token can no longer be used to enrol
- [ ] ≡ƒö┤ **Revoking does NOT deprovision an employee who already enrolled with it.** There is no
      per-employee revocation in this system. Verify the UI **says so** ΓÇö an admin who believes
      otherwise has a false sense of control

---

## 6. End-to-end integration flows

### 6.1 Enrolment ΓåÆ policy ΓåÆ popup

1. Department dashboard ΓåÆ mint a token
2. Extension Options ΓåÆ Enterprise ΓåÆ paste ΓåÆ Connect
3. Company dashboard ΓåÆ Tools Policy Matrix ΓåÆ block ChatGPT
4. Wait ~5 s on an open chatgpt.com tab

- [ ] The amber banner **appears on its own**, without a reload
- [ ] Re-approve ΓåÆ the banner **clears itself** within ~5 s
- [ ] The popup's policy version increments at each change

### 6.2 Access-request round trip (the demo beat)

| # | Where | Do | Expect | Result |
|---|---|---|---|---|
| 1 | Extension | Open gemini.google.com | Amber banner; page still works | |
| 2 | Extension | Banner ΓåÆ Request access + reason | *"Request sent"* | |
| 3 | **Department** dashboard | Access Requests | Row appears within ~3 s, with the department | |
| 4 | Department dashboard | **Approve** | Status `approved` | |
| 5 | Extension | Do nothing | **The banner disappears on its own within ~5 s** | |
| 6 | Either dashboard | AI Usage | Events by department / tool / category | |

### 6.3 Appeal round trip + one-time pass

| # | Do | Expect | Result |
|---|---|---|---|
| R1 | Send `Write a python script to monitor employees covertly.` | Red ethics modal | |
| R2 | Modal ΓåÆ Request a review ΓåÆ reason ΓåÆ opt-in **off** ΓåÆ Send review | Modal closes | |
| R3 | Department dashboard ΓåÆ Prompt Audits & Appeals (~3 s) | Appeal appears; **Shared text = "not shared"** | |
| R4 | Add a note ΓåÆ **Overturn** | Row flips to `overturned` | |
| R5 | Extension Options ΓåÆ My reviews (~5 s) | Shows `overturned` + the note | |
| R6 | Re-send the **same** prompt, press Send, then press Send again | Green *"Review approved"*, then it sends | |
| R7 | Send it a **third** time | ≡ƒö┤ **Blocked again ΓÇö the pass burns after one use** | |

> R7 is the security-relevant half. The approved-scopes list on the server is **permanent**; the
> extension enforces single use locally (`usedAppealPasses`). If R7 sends, the employee has an
> unlimited bypass for that prompt.

### 6.4 Mode switch under load

- [ ] Enrolled in Enterprise, actively using ChatGPT ΓåÆ switch to Personal
- [ ] Banner disappears, file capture stops, ethics stops, **local PII gate keeps working**
- [ ] Dashboard receives **no further events** from that install
- [ ] Switch back to Enterprise ΓåÆ re-enrolment is required (the token was cleared)

---

## 7. Privacy invariants ΓÇö the compliance audit

These are the rows a buyer actually checks. Every one must hold.

- [ ] **No prompt text on the wire.** DevTools ΓåÆ Network ΓåÆ filter by a distinctive string you typed ΓåÆ
      **zero hits** on both the policy service and the file backend. (The model CDN on first run is
      expected and carries no user data.)
- [ ] **No prompt text in the database.** Query `usage_events` ΓÇö only class, count, host, type,
      timestamp. No prompt column exists
- [ ] **`chrome.storage.local` holds no raw values.** Application tab ΓåÆ `vg_audit` ΓåÆ classes, counts,
      salted fingerprints. **No names, no ICs, no filenames, no file bytes**
- [ ] **E2 ΓÇö no rehydration.** After a rewrite, the original value is **never** written back into the
      provider's page
- [ ] **Employees are pseudonymous server-side.** No email or name column on `employees` beyond the
      label the **admin** supplied
- [ ] **The 422 handler scrubs input.** POST malformed JSON with a secret in it to `/v1/events` ΓåÆ the
      422 body names the **field**, never the **value**. (FastAPI's default handler leaks the whole
      request body here; this is a deliberate control, not formatting)
- [ ] **Events are rejected, not silently trimmed.** POST an event carrying a `prompt` field ΓåÆ **422**,
      not a 202 with the field dropped
- [ ] **Independent numbering.** On a second machine, the same name gets `PERSON_1` independently ΓÇö
      there is no shared or synced map

**Ignore rate per class** ΓÇö paste into the extension's console on a provider tab after a session:

```js
chrome.storage.local.get('vg_audit').then(r => console.table(
  Object.entries((r.vg_audit||[]).reduce((acc,row)=>{
    acc[row.cls] ??= {flagged:0, ignored:0};
    row.ignored ? acc[row.cls].ignored++ : acc[row.cls].flagged++;
    return acc;
  },{})).map(([cls,v])=>({cls,...v}))
));
```

This is the detector-prioritization signal. **It ranks our bugs; it does not label them.**

---

## 8. Known gaps ΓÇö do not invent a PASS

| # | Gap | Status |
|---|---|---|
| 8.1 | **LOC masking is OFF by design.** A personal address in a prompt **will not be masked**. Stock NER tags `12 Jalan Ampang` and `Kuala Lumpur` with the same label, and masking public geography is a pure false positive | **Accepted gap**, not a bug |
| 8.2 | **Ethics is English-only.** Malay / Chinese equivalents do not fire | Known limit |
| 8.3 | **L2 is entity detection, not sensitivity.** `Einstein` and `Apple` fire. The gap between *is an entity* and *is sensitive* is the parallel `ml/` track and is **not in this build** | By design (ADR 0017) |
| 8.4 | **U30 ΓÇö PDF format-preserving redaction** has a smoke PASS only; the real-corpus run is still owed | ≡ƒƒá **CONDITIONAL** ΓÇö F10 covers the no-text-layer path only |
| 8.5 | **Edit-a-prior-message + NRIC + Save** ΓÇö the review on the edit editor | **DEFERRED** |
| 8.6 | **Notifications** ΓÇö `/v1/notifications` and the background handler exist, but **no UI consumes them**. Testable only via the API or the service-worker console | Partial feature |
| 8.7 | **Cross-tab audit writes can race** on `chrome.storage.local`. Acceptable for a team test; flag duplicate or lost rows under heavy multi-tab use | Known |
| 8.8 | **Org dictionary is `chrome.storage.local`** ΓÇö local, unencrypted, user-writable. ADR 0009 puts the real one on `chrome.storage.managed` with per-tenant DEKs | Slice 1 placeholder |
| 8.9 | **Seeded telemetry is synthetic.** It proves the charts render and nothing about detection quality | By design |
| 8.10 | **Policy tests write to the live `DATABASE_URL`**, and take **~18 min** because the database is a region away | See ┬º3 |

---

## 9. Sign-off

### Extension

| Surface | Tester | Date | ┬º4.1 | ┬º4.2 | ┬º4.3 | ┬º4.4 | ┬º4.6 | ┬º4.8 | ┬º4.9 | ┬º4.10 | ┬º4.12 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| chatgpt.com | | | | | | | | | | | |
| claude.ai | | | | | | | | | | | |

### Dashboard

| Role | Tester | Date | ┬º5.3 | ┬º5.4 | ┬º5.5 | ┬º5.6 | ┬º5.7 | ┬º5.8 | ┬º5.9 / ┬º5.10 |
|---|---|---|---|---|---|---|---|---|---|
| Company Admin | | | | | | | | | |
| Department Admin | | | | | | | | | |

### Integration + invariants

| Section | Tester | Date | Pass / Fail | Notes |
|---|---|---|---|---|
| ┬º6.1 enrolment ΓåÆ policy | | | | |
| ┬º6.2 access-request round trip | | | | |
| ┬º6.3 appeal + one-time pass | | | | |
| ┬º6.4 mode switch | | | | |
| ┬º7 privacy invariants | | | | |

**Accepted when:** ┬º3 gates pass ┬╖ ┬º4 and ┬º5 are complete on both surfaces and both roles ┬╖ ┬º6 round
trips complete ┬╖ **every ┬º7 invariant holds** ┬╖ ┬º8 items are recorded as gaps, not as passes.

**Report back with:** the IDs you passed and failed, per surface and per role, plus the Ignore rate
per class from ┬º7 and how long `CheckingΓÇª` took on a typical work file.
