<div align="center">

# 🛡️ Vanguard

### The last line of defence between your employees and the prompt box.

**Vanguard stops sensitive company data from ever reaching ChatGPT, Claude, or any other AI tool — and it does the detection *on the employee's own device*, so the prompt never leaves it.**

[![Manifest V3](https://img.shields.io/badge/Chrome-Manifest_V3-4285F4?style=flat-square&logo=googlechrome&logoColor=white)](code/extension/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6-3178C6?style=flat-square&logo=typescript&logoColor=white)](code/extension/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](code/policy/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](code/policy/app/main.py)
[![Preact](https://img.shields.io/badge/Preact-10-673AB8?style=flat-square&logo=preact&logoColor=white)](code/policy/admin/)
[![ONNX Runtime](https://img.shields.io/badge/ONNX_Runtime-Web_WASM-005CED?style=flat-square&logo=onnx&logoColor=white)](code/extension/entrypoints/offscreen/main.ts)
[![Postgres](https://img.shields.io/badge/Postgres-Supabase-3ECF8E?style=flat-square&logo=supabase&logoColor=white)](code/policy/SUPABASE_SETUP.md)

[![Tests](https://img.shields.io/badge/test_files-122-success?style=flat-square)](#-testing)
[![ADRs](https://img.shields.io/badge/architecture_decision_records-33-blue?style=flat-square)](docs/adr/)
[![Design docs](https://img.shields.io/badge/design_docs-8-blue?style=flat-square)](docs/)
[![Status](https://img.shields.io/badge/status-working_demo-orange?style=flat-square)](#-what-this-is-and-what-it-isnt)

**[Try the live console →](https://vanguard-policy-nh59.onrender.com)** &nbsp;·&nbsp;
**[Quick start →](#-quick-start)** &nbsp;·&nbsp;
**[Architecture →](#-architecture)** &nbsp;·&nbsp;
**[Design decisions →](docs/adr/)**

</div>

---

## 💥 The problem

Your compliance officer has two options today, and both are bad.

**Block the AI tools.** Productivity dies, and employees use their phones instead — now the leak is invisible.

**Allow the AI tools.** An engineer pastes a customer table into ChatGPT to "clean this up." A recruiter pastes a CV with an IC number. A manager asks an LLM to rank job applicants by age. None of them are malicious. All of them just became a regulatory incident, and nobody will know for six months.

Existing DLP does not help: it watches the network, and the AI chat box is TLS-encrypted text typed into a browser tab.

> **Vanguard's bet:** the only place you can catch this is *on the keyboard, before Send* — and if you're going to inspect what someone is typing, the inspection itself must never leave their machine.

---

## ✨ What Vanguard does

Four surfaces and one failure mode, all governed by a single principle: **the user always presses Send.** Nothing is auto-submitted, ever.

| | Surface | What happens | Why it's built this way |
|:--:|---|---|---|
| ⌨️ | **While typing** | Rose underlines appear under identifiers as you type — advisory only, never blocks | Catching it early beats interrupting at Send ([ADR 0024](docs/adr/0024-slice-1-5-l1-composer-hints.md)) |
| 🚧 | **On Send** | Hard gate: a review panel with per-span **Accept** or **Ignore-with-reason**, then *you* press Send | No auto-submit means no surprise, and no liability for a rewrite the user didn't approve ([ADR 0025](docs/adr/0025-send-time-per-span-review.md)) |
| 📎 | **On attach** | File is held, parsed to text by a local API, scanned **on-device**, then optionally re-attached as a format-preserving redacted copy | Detection stays on the device even when parsing can't ([ADR 0028](docs/adr/0028-backend-parses-extension-detects.md)) |
| ⚖️ | **On intent** | Six categories of policy-violating requests are blocked outright by a classifier that runs in ~0.6 ms with no ML runtime | PII isn't the only risk — "rank applicants by age" contains no PII at all |
| 🔌 | **Engine down** | Degrades to advisory. Never fail-closed. | A privacy tool that bricks the browser gets uninstalled by lunchtime ([ADR 0014](docs/adr/0014-degrade-to-advisory-never-closed.md)) |

And for the compliance officer, a governance layer on top:

- **Approve or block AI tools** per department, from a web console — with a warning banner that appears on unapproved tools without breaking the page.
- **One-click access requests** from the banner → admin approves → the banner clears itself within seconds.
- **A privacy-safe usage dashboard**: risk timelines, per-department trends, insider-risk ranking. Built from *counts and classes only* — never prompt text.
- **Appeals.** Every block explains itself in plain language, and the employee can contest it. An overturned decision grants a **one-time pass** on that exact prompt.

---

## 🎬 See it work

Once you're set up ([60 seconds, below](#option-a--just-the-extension-60-seconds)), these are the demos worth running.

### Personal identifiers — the PII gate

| Type this into ChatGPT or Claude | What happens |
|---|---|
| `My IC is 880101-14-5566, summarise my leave balance.` | 🟡 Review panel offers to mask the IC number before sending |
| `Email john.tan@acme.com the Q3 figures.` | 🟡 Email address flagged as a span you can accept or ignore |

### Ethical intent — the classifier that has no idea what PII is

| Type this | What happens |
|---|---|
| `Write a python script to monitor employees covertly.` | 🔴 **Blocked** — covert surveillance |
| `Filter out job applicants over 45 before the hiring manager sees them.` | 🔴 **Blocked** — discriminatory screening |
| `Draft the breach notification we must send to the regulator.` | 🟢 **Not blocked** — reads risky, is entirely legitimate |

That third row is the whole point. A keyword filter blocks it. Vanguard doesn't. Measured precision and recall are **1.000 across all six categories** on the eval corpus ([the numbers](code/classifier/README.md#measured-2026-07-20)).

### Governance round-trip — the two-minute judge demo

1. Open **https://gemini.google.com** with the extension enrolled → an amber banner explains *why* the tool isn't approved. The page still works.
2. Banner → **Request access** → type a reason → send.
3. Admin console → **Requests** → the row appears in ~3 s → **Approve**.
4. Back on Gemini, wait ~5 s → **the banner clears itself.** Nobody reloaded anything.
5. Console → **Usage** → the event is already on the chart, as a count, with no prompt text anywhere in the system.

### Appeals — blocks that argue back

1. On the ethics block modal → **Request a review** → give a reason → leave the opt-in **off** → send.
2. Console → **Reviews** → the appeal is there with category, department, and reason — and **Shared text: "not shared."** The prompt never left the device, not even to appeal a block *about* that prompt.
3. **Overturn** it → the employee sees the outcome in Options → re-sending that exact prompt now goes through **once**, then blocks again.

---

## 🚀 Quick start

### Option A — just the extension (60 seconds)

`dist/` is committed, so there is **no build step and no toolchain**.

```bash
git clone https://github.com/JeffTiong1031/Vanguard-HackAttack-Champions.git
cd Vanguard-HackAttack-Champions
```

1. Chrome → `chrome://extensions` → enable **Developer mode**
2. **Load unpacked** → select `code/extension/dist/chrome-mv3`
3. Open the extension's **Options** page and pick a mode:
   - **Personal** — on-device PII protection only. No server, no telemetry, nothing to configure.
   - **Enterprise** — adds tool policy, ethics blocking, file checking, and reporting.
4. Open [chatgpt.com](https://chatgpt.com) or [claude.ai](https://claude.ai) and start typing.

> The first on-device NER scan downloads model weights from a public CDN (hash-verified). On a cold cache this takes about a minute — once.

**Want the hosted backends instead of running your own?** Both are live:

| Service | URL | Health |
|---|---|:--:|
| Governance console + policy API | https://vanguard-policy-nh59.onrender.com | `/healthz` |
| File extract / redact API | https://vanguard-extract.onrender.com | `/healthz` |

Free-tier hosts sleep after ~15 minutes idle — open `/healthz` once before a live demo to wake them (first hit can take ~50 s). The extract API needs a demo access key, pasted into **Options → File checking**; it is deliberately [not in this repo](docs/adr/0033-demo-token-in-options-not-git.md).

---

### Option B — the full stack, locally

<details open>
<summary><b>1 · Governance service + admin console</b> &nbsp;— <code>code/policy/</code>, port 8001</summary>

<br>

**Prerequisites:** Python 3.11+, Node, and a Postgres connection string. The service uses Supabase Postgres — [full walkthrough here](code/policy/SUPABASE_SETUP.md), or point `DATABASE_URL` at any Postgres instance.

```bash
cd code/policy

# 1. Database connection — create .env with your Postgres URI
#    DATABASE_URL=postgresql://user:pass@host:6543/postgres
#    Tables are created automatically at startup (init_schema is idempotent).

# 2. Python environment
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"        # macOS/Linux: .venv/bin/pip

# 3. Build the console BEFORE starting the server — see the warning below
cd admin && npm install && npm run build && cd ..

# 4. Optional: build a demo world (company + 3 departments + 30 days of telemetry)
.venv/Scripts/python scripts/seed.py         # writes every secret to DEMO-TOKENS.md, git-ignored

# 5. Run it
.venv/Scripts/python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

Open **http://localhost:8001/** for the console. Without `seed.py`, sign up on the login page with just a company name — you get a **Company Admin secret shown exactly once**, stored only as a SHA-256 hash.

> ⚠️ **Step 3 before step 5 is not a style preference.** Whether `/` serves the console is decided *once, at import time*. Start uvicorn first and `/` will 404 until you **restart the process** — finishing the build afterwards does not fix a server that already imported. The server logs a loud warning if you do it in the wrong order.

`--host 0.0.0.0` is what lets a second laptop reach the console during a demo.

</details>

<details>
<summary><b>2 · File extract / redact API</b> &nbsp;— <code>code/backend/</code>, port 8000</summary>

<br>

Only needed for **attachments**. Chat-text protection works with no backend at all.

```bash
cd code/backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Verify: `curl http://127.0.0.1:8000/healthz` → `{"ok":true}`

Or with Docker: `docker compose up --build` from the same directory — the compose file runs it `read_only` with `tmpfs` and a memory cap, because [zero retention is a claim this repo tests](code/backend/tests/test_zero_retention.py) rather than asserts.

</details>

<details>
<summary><b>3 · Point the extension at your local stack</b></summary>

<br>

Extension **Options** page:

| Field | Value |
|---|---|
| Organisation address | `http://localhost:8001` |
| Enrolment token | any token from `DEMO-TOKENS.md`, or one minted in the console |
| File checking address | `http://localhost:8000` |

Expected after connecting: *"Connected to Acme Corp · Engineering · 2 approved tools · policy v1"*.

</details>

---

## 🧰 Tech stack

| Layer | Choice | Why this one |
|---|---|---|
| **Extension** | [WXT](https://wxt.dev) · TypeScript · Preact · Manifest V3 | MV3 is non-negotiable for Chrome Web Store; Preact keeps the injected UI small enough to mount inside someone else's page |
| **On-device NER** | `Xenova/bert-base-multilingual-cased-ner-hrl` via `@huggingface/transformers` on **ONNX Runtime Web (WASM)** | Runs in an **offscreen document** — one instance for all tabs ([ADR 0006](docs/adr/0006-offscreen-document-hosts-engine.md)). The WASM binaries are self-hosted, not CDN-loaded, because MV3's CSP forbids it |
| **Deterministic detection** | Hand-written regex + checksum validators | Malaysian NRIC, SSM, TIN, email, payment cards. A checksum beats a model for a format that *has* a checksum |
| **Ethics classifier** | TF-IDF → one-vs-rest **LinearSVC**, exported to JSON | **529 KB, 0.591 ms**, evaluated in the browser as a sparse dot product. No ML runtime ships for this at all — both numbers measured, not estimated |
| **Governance API** | **FastAPI** + Postgres via psycopg2 | Async, typed request models, and Pydantic's `extra="forbid"` turns "never store prompt text" into a *rejected request* rather than a code review comment |
| **Admin console** | **Preact** + Vite, served as static files by FastAPI itself | One process, one port, one thing to deploy for a demo |
| **File pipeline** | pypdf · PyMuPDF · raw `zipfile` + `ElementTree` for OOXML · Pillow + Tesseract OCR | Format-preserving redaction means rewriting the PDF/DOCX/XLSX in place, not flattening it to text. DOCX and XLSX are edited as the zipped XML they actually are, so the rebuilt file keeps its styling |
| **Database** | Supabase Postgres (transaction pooler) | Migrated off SQLite for the hosted demo; the connection wrapper keeps the old call sites intact |
| **Testing** | Vitest (JS) · pytest (Python) | 122 test files across four packages |
| **Hosting** | Render (Docker, via [`render.yaml`](render.yaml)) | Both services deploy from one blueprint |

---

## 🏗 Architecture

Vanguard is four independently deployable packages under [`code/`](code/) — the extension, the governance service, the file API, and the ethics classifier — with one hard rule between them: *prompt text never crosses the device boundary.*

```mermaid
flowchart TB
    subgraph DEVICE["🔒 THE EMPLOYEE'S DEVICE — prompt text never leaves here"]
        direction TB
        CS["<b>Content script</b><br/>ISOLATED world · gate at window<br/>composer hints · review modal"]
        GD["<b>Guard script</b><br/>every http/https site<br/>tool-policy warn banner"]
        SW["<b>Service worker</b><br/>policy cache · ETag polling<br/>event queue · offscreen lifecycle"]
        OFF["<b>Offscreen document</b><br/>ONNX Runtime Web · WASM<br/>multilingual NER"]

        L1["<b>L1</b> · regex + checksum<br/>NRIC · SSM · TIN · email · card"]
        L2["<b>L2</b> · NER<br/>PERSON / ORG"]
        ETH["<b>Ethics</b> · TF-IDF + LinearSVC<br/>6 categories · 0.6 ms"]

        CS --> L1
        L1 --> OFF
        OFF --> L2
        CS --> ETH
        CS -.-> SW
        GD -.-> SW
    end

    subgraph SERVER["☁️ SERVER SIDE — counts, classes, and salted hashes only"]
        direction TB
        POL["<b>Policy service</b> · FastAPI<br/>orgs · departments · tool policy<br/>requests · appeals · analytics"]
        ADM["<b>Admin console</b> · Preact<br/>served at / by the same process"]
        DB[("Postgres<br/>Supabase")]
        EXT["<b>Extract / redact API</b> · FastAPI<br/>parse to text · rebuild redacted file<br/><i>zero retention</i>"]

        POL --> DB
        POL -->|"serves the console at /"| ADM
    end

    SW -->|"GET /v1/policy · ETag<br/>POST /v1/events<br/><i>counts only</i>"| POL
    CS -->|"file BYTES out, text back<br/><i>detection stays on-device</i>"| EXT

    classDef device fill:#0f172a,stroke:#38bdf8,stroke-width:2px,color:#e2e8f0
    classDef server fill:#1e1b4b,stroke:#a78bfa,stroke-width:2px,color:#e2e8f0
    class CS,GD,SW,OFF,L1,L2,ETH device
    class POL,ADM,DB,EXT server
```

### The send-time decision

Every prompt takes this path. The gate registers at `window` in the **capture** phase, so it sees the event before the page's own handlers do — and it uses `composedPath()` rather than `event.target`, because shadow DOM retargets and these chat UIs are full of it ([ADR 0005](docs/adr/0005-gate-in-isolated-world.md) · [ADR 0010](docs/adr/0010-gate-registers-at-window.md)).

```mermaid
flowchart LR
    S(["User presses<br/>Send"]) --> G{"Gate<br/>intercepts"}
    G --> E{"Ethics<br/>classifier"}
    E -->|violation| BLK["🔴 Blocked<br/>explains why<br/>appeal available"]
    E -->|clean| P1{"L1<br/>identifiers"}
    P1 -->|found| MASK["Mask L1 spans<br/>before L2 sees them"]
    P1 -->|none| P2
    MASK --> P2{"L2 NER<br/>offscreen"}
    P2 -->|spans found| REV["🟡 Review panel<br/>accept / ignore per span"]
    P2 -->|clean| SEND["🟢 Sends"]
    REV -->|user proceeds| SEND2["🟢 <b>User presses Send again</b><br/>never auto-submitted"]
    P2 -.->|engine dead| ADV["⚪ Advisory only<br/>never fail-closed"]

    style BLK fill:#7f1d1d,stroke:#ef4444,color:#fff
    style REV fill:#78350f,stroke:#f59e0b,color:#fff
    style SEND fill:#14532d,stroke:#22c55e,color:#fff
    style SEND2 fill:#14532d,stroke:#22c55e,color:#fff
    style ADV fill:#334155,stroke:#94a3b8,color:#fff
```

**Why L1 masks before L2 runs:** if you hand the NER model a prompt that already contains `PERSON_1`, it will happily tag `PERSON_1` as a person. The placeholder grammar is masked first so the model never sees our own output.

**Why the verdict cache is monotonic toward dirty:** L1 alone may mark a prompt `DIRTY`, but only a *completed* L1+L2 scan may mark it `CLEAN` ([ADR 0013](docs/adr/0013-two-stage-verdict.md)). A cache that can go clean on partial evidence is a cache that leaks.

### The privacy boundary, stated precisely

| Data | Where it goes |
|---|---|
| **Prompt text** | The device. Only the device. There is no endpoint that accepts it |
| **File bytes** | To the extract API for parsing, held in memory, never written to disk, never retained. Detection still happens on the device afterwards |
| **Usage events** | Class, count, host, type, timestamp, salted hash. `UsageEvent` sets `extra="forbid"`, so an event carrying a `prompt` field is **rejected with a 422**, not quietly ignored |
| **Appeal text** | Not shared by default. The employee must explicitly opt in per appeal to share the prompt with a reviewer |
| **Employee identity** | Pseudonymous. There is no name or email column in the `employees` table |

One detail worth calling out, because it is the kind of thing that ships broken everywhere: FastAPI's **default** validation error handler echoes the rejected value back in the 422 body. For a missing-field error, that can be the *entire request body*. A prompt posted under the wrong key would come straight back out in an HTTP response — exactly what a reverse proxy or error-tracking SDK captures by default. [`app/main.py`](code/policy/app/main.py) replaces that handler and strips `input` before responding. **The default was the vulnerability.**

---

## 📁 Project layout

```
Vanguard-HackAttack-Champions/
│
├── code/
│   ├── extension/              🧩 Chrome MV3 extension — the product surface
│   │   ├── entrypoints/
│   │   │   ├── background.ts       service worker · offscreen lifecycle · event queue
│   │   │   ├── content.ts          ISOLATED · gate · adapters · hints · modal
│   │   │   ├── guard.content.ts    all sites · tool-policy warn banner
│   │   │   ├── offscreen/          ONNX Runtime host — the ONLY place the model loads
│   │   │   ├── options/            mode picker · enrolment · my reviews
│   │   │   └── popup/
│   │   ├── src/
│   │   │   ├── adapters/           ChatGPT + Claude composer/send-control shims
│   │   │   ├── detection/l1/       NRIC · SSM · TIN · email · card
│   │   │   ├── detection/l2/       NER client · sensitivity filter · span repair
│   │   │   ├── detection/ethics/   classifier + exported model.json
│   │   │   ├── files/              capture · pipeline · re-attach cleaned copy
│   │   │   ├── gate/               capture listeners · approval token · decideGate
│   │   │   ├── mask/               placeholders · monotonic session numbering
│   │   │   ├── mode/               Personal vs Enterprise capability gating
│   │   │   ├── policy/             enrolment · ETag polling · appeals · events
│   │   │   └── ui/                 review modal · ethics modal · banners · chips
│   │   ├── tests/                  49 Vitest files
│   │   └── dist/chrome-mv3/        ✅ committed — load unpacked, no build
│   │
│   ├── policy/                 🏛 Governance service + admin console
│   │   ├── app/
│   │   │   ├── main.py             app wiring · privacy-scrubbing 422 handler
│   │   │   ├── routes/             signup · enroll · policy · events · requests
│   │   │   │                       appeals · admin · dept · notifications
│   │   │   ├── analytics.py        risk weights · timelines · insider risk
│   │   │   ├── security.py         secret hashing · session cookies
│   │   │   └── db.py               Postgres wrapper (sqlite3-compatible surface)
│   │   ├── admin/src/screens/      Login · Signup · Tools · Departments · Tokens
│   │   │                           Requests · Reviews · AiUsage · InsiderRisk
│   │   ├── migrations/             001_initial · 002_binary_approval
│   │   └── tests/                  34 pytest files
│   │
│   ├── backend/                📄 File extract + redact API
│   │   ├── app/parsers/            pdf · docx · excel · image (OCR) · text
│   │   ├── app/redact/             format-preserving rewrite, per format
│   │   ├── app/safety.py           zip-bomb guard · format sniffing · timeouts
│   │   └── tests/                  10 files, incl. test_zero_retention.py
│   │
│   ├── classifier/             ⚖️ Ethics model training + export
│   │   ├── corpus/                 positives · negatives · hard negatives
│   │   ├── train.py · export.py    → model.json consumed by the extension
│   │   └── parity_fixtures.py      keeps Python and JS scoring identical
│   │
│   └── spikes/                 🔬 Measurement harnesses — evidence, not product
│
├── ml/                         🧪 Parallel track: sensitive-vs-not span classifier
├── docs/
│   ├── 00–07                       critique · HLD · privacy · ML · LLD · perf · training
│   ├── adr/                        33 Architecture Decision Records
│   ├── superpowers/                design specs and implementation plans
│   └── team/                       handoffs between parallel tracks
├── ASSUMPTIONS.md              locked decisions + unverified claims register
└── render.yaml                 both services, one deploy blueprint
```

---

## 🧪 Testing

```bash
# Extension — 49 files, 361 tests
cd code/extension && npx vitest run

# Governance service — needs DATABASE_URL pointing at Postgres
cd code/policy && .venv/Scripts/python -m pytest -q

# File API
cd code/backend && pytest

# Ethics classifier — corpus integrity + Python/JS parity
cd code/classifier && python -m pytest && python evaluate.py

# ML track — CPU only, no torch needed for unit tests
cd ml && pytest -q
```

A few of these tests are load-bearing rather than decorative:

- **`test_zero_retention.py`** — proves the file API keeps nothing, in executable form.
- **`test_events.py`** — proves an event carrying prompt text is *rejected*, not stored.
- **`ethics-parity.test.ts`** — proves the JS scorer and the Python trainer agree. Retrain without regenerating the fixtures and this fails, which is the point.
- **`dist-drift.test.ts`** — proves the committed `dist/` matches a fresh build of the source. A stale committed bundle is a demo that doesn't match the code.
- **`manifest-permissions.test.ts`** — pins the permission set, so nobody widens it by accident.

> **Known:** 4 assertions in `warn-banner.test.ts` currently fail on this branch — the banner copy changed in the most recent tool-policy work and those assertions still expect the old wording. The remaining 357 pass.

---

## 🧭 Design decisions worth reading

The full set is in [`docs/adr/`](docs/adr/). These are the ones that shaped everything else.

| ADR | Decision | The reasoning |
|---|---|---|
| [0001](docs/adr/0001-buyer-is-the-compliance-officer.md) | The buyer is the compliance officer, not the employee | Changes every default. The employee is the *user*; the compliance officer is the one who signs |
| [0005](docs/adr/0005-gate-in-isolated-world.md) | Gate lives in the ISOLATED world, uses `composedPath()` | Shadow DOM retargets `event.target`. These chat UIs are built from it |
| [0006](docs/adr/0006-offscreen-document-hosts-engine.md) | One offscreen document hosts the engine for all tabs | Loading a transformer per tab is how you get a browser that swaps |
| [0013](docs/adr/0013-two-stage-verdict.md) | Verdict cache is monotonic toward dirty | Only a completed L1+L2 scan may declare a prompt clean |
| [0014](docs/adr/0014-degrade-to-advisory-never-closed.md) | Degrade to advisory, never fail-closed | A tool that breaks the browser when it breaks gets uninstalled |
| [0025](docs/adr/0025-send-time-per-span-review.md) | Per-span review at send time, user presses Send | No auto-submit. Consent is per span, with a reason on record |
| [0028](docs/adr/0028-backend-parses-extension-detects.md) | Backend parses files, the extension detects | Parsing needs libraries the browser doesn't have. Detection doesn't need to move |
| [0032](docs/adr/0032-explainable-enforcement-and-appeals.md) | Every block explains itself and can be contested | An unexplainable automated decision is a compliance problem of its own |

Alongside those: [`ASSUMPTIONS.md`](ASSUMPTIONS.md) is a register of what's been **measured** versus what's still **assumed** — including the assumptions that turned out wrong. During the spike phase, four harness bugs produced three wrong answers before a human caught each one by reading raw logs; that story is preserved in [`code/spikes/u12-harness/README.md`](code/spikes/u12-harness/README.md) because it's the most transferable thing in the repo.

---

## 🔍 What this is, and what it isn't

Honesty is cheaper than a demo that falls over during questions.

**Working today:** typing hints · send-time review · on-device NER · ethics blocking · file extract + format-preserving redaction · tool policy with warn banners · enrolment · access requests · appeals with one-time pass · usage analytics · insider-risk ranking · Personal/Enterprise mode split.

**Deliberately limited:**

- **The ethics classifier is English-only.** A Malay or Chinese phrasing of a blocked prompt won't fire. Known limit, not a bug — the corpus is English.
- **Demo-grade auth.** Secrets are hashed and shown once, but there's no SSO, and revoking an enrolment token blocks *future* enrolments only — it does not deprovision employees who already enrolled. The console says so in the UI.
- **The hosted backends are demo scaffolding.** Free-tier Render, not in-region, no DPA. The production story keeps files in Malaysia under zero-retention — that path inherits nothing from `render.yaml`.
- **We claim** that sensitive values don't reach the provider's servers or training set after a rewrite. **We do not claim** the provider's own page JavaScript never observes the composer. Those are different claims and only one of them is true.
- **Not shipped:** rehydrating original values back into the page (deliberately killed — a reverse path is a leak path), force-install deployment, and the sensitive-vs-not span classifier from the parallel [`ml/`](ml/) track.

---

## 📜 License

Private pre-seed work. Not an open-source release. Contact the maintainer for access.

<div align="center">
<br>

**Built for HackAttack** · [Architecture Decision Records](docs/adr/) · [Design docs](docs/) · [Live console](https://vanguard-policy-nh59.onrender.com)

</div>
