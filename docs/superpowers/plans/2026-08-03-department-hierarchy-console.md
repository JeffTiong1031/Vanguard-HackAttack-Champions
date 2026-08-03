# Department Hierarchy — Console UI + Extension Wiring Plan (Plan 2 of 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the Preact admin console a role-picker login + self-signup, a role-gated shell that mounts a **Company** dashboard or a **Department** dashboard, reuse the existing screens under each scope, add a Departments screen, and teach the browser extension to poll department-scoped policy.

**Architecture:** One Preact app (`code/policy/admin`). `main.tsx` holds a `Session` (`role`, `org_id`, `org_name`, and for department sessions `department_id`/`department`), persisted in `localStorage` and verified on mount by a role-appropriate authenticated call. A `Shell` renders the topbar + tabs; the existing `Requests`/`Reviews`/`Usage` screens take a `scope` prop that swaps `/v1/admin/*` ↔ `/v1/dept/*` and read-only ↔ actionable. The extension stores `department_id` from enrolment and sends it as a `/v1/policy` query param.

**Tech Stack:** Preact 10, Vite 5, TypeScript. Extension: WXT + Vitest.

**Depends on:** Plan 1 (backend) merged — every endpoint this plan calls is delivered there.

**Spec:** `docs/superpowers/specs/2026-08-03-multi-tenant-department-hierarchy-design.md` §6 and the §5 extension-poll bullet.

## Global Constraints

- **Console never adjudicates authority.** It is a view; the server decides role/scope. The console only reflects what login returned. A 401 anywhere bounces to login (existing `unhandledrejection` handler in `main.tsx`).
- **`api.ts` uses `credentials: 'include'`** — the HttpOnly `vg_admin` cookie is the sole authority; the console holds no token.
- **Secrets are shown once.** Signup and department-secret mint/regenerate display the plaintext with a copy-now banner and never re-fetch it.
- **No PII columns rendered.** Department views show pseudonymous employees grouped by department — no names.
- **Preact, `class=` not `className=`**, inline SVG icons from `icons.tsx`, styles from `style.css` (reuse existing classes: `panel`, `panel-head`, `btn-primary`, `btn-danger`, `pill`, `mint-result`, `tag`, `field`, etc.).
- **Commits: sole author, no `Co-Authored-By` trailer.**
- **Build gate:** from `code/policy/admin/`: `npm run build` must succeed. Extension gate: from `code/extension/`: `npm test` stays green and `npm run build` succeeds.
- **Manual acceptance runs against the real backend:** `code/policy` running on `http://localhost:8001` after `python scripts/seed.py`, console served from the backend static mount after `npm run build`.

---

### Task 1: `api.ts` — types for sessions and departments

**Files:**
- Modify: `code/policy/admin/src/api.ts`

**Interfaces:**
- Produces: `Session`, `Department`, `LoginResult`, `Scope` types used by every screen below.

- [ ] **Step 1: Add the types**

Append to `code/policy/admin/src/api.ts`:

```typescript
export type Scope = 'company' | 'department';

export type Session = {
  role: Scope;
  org_id: string;
  org_name: string;
  department_id?: string;
  department?: string;
};

export type LoginResult = {
  role: Scope;
  org_id: string;
  org_name: string;
  department_id?: string;
  department?: string;
};

export type Department = {
  id: string;
  name: string;
  created_at: string;
  active_tokens: number;
};
```

`TokenRow` already exists and matches `/v1/dept/tokens`. `RequestRow`, `AppealRow`, `Usage`, `Tool` are unchanged and serve both scopes.

- [ ] **Step 2: Typecheck**

Run: `cd code/policy/admin && npm run build`
Expected: build succeeds (types compile; nothing consumes them yet).

- [ ] **Step 3: Commit**

```bash
git add code/policy/admin/src/api.ts
git commit -m "feat(console): session, department, and scope types"
```

---

### Task 2: Login screen — role picker + secret, link to signup

**Files:**
- Modify: `code/policy/admin/src/screens/Login.tsx`

**Interfaces:**
- Consumes: `api.post('/v1/admin/login', {role, secret})` → `LoginResult`.
- Produces: `Login({ onDone, onCreate })` where `onDone(session: Session)` and `onCreate()` switches to signup.

- [ ] **Step 1: Rewrite `Login.tsx`**

```tsx
import { useState } from 'preact/hooks';
import { api, UnauthorisedError, NetworkError, type LoginResult, type Session, type Scope } from '../api';
import { LayersIcon } from '../icons';

export function Login({ onDone, onCreate }: { onDone: (s: Session) => void; onCreate: () => void }) {
  const [role, setRole] = useState<Scope>('company');
  const [secret, setSecret] = useState('');
  const [error, setError] = useState('');

  async function submit(e: Event) {
    e.preventDefault();
    setError('');
    try {
      const r = await api.post<LoginResult>('/v1/admin/login', { role, secret });
      onDone({
        role: r.role, org_id: r.org_id, org_name: r.org_name,
        department_id: r.department_id, department: r.department,
      });
    } catch (err) {
      if (err instanceof UnauthorisedError) setError('That secret was not recognised for this role.');
      else if (err instanceof NetworkError) setError(err.message);
      else if (err instanceof Error) setError(`Service error: ${err.message}`);
      else setError('An unexpected error occurred.');
    }
  }

  return (
    <div class="login-wrap">
      <form class="login-card" onSubmit={submit}>
        <div class="brand">
          <span class="brand-mark"><LayersIcon /></span>
          <div>
            <div class="brand-name">Vanguard</div>
            <div class="brand-sub">AI Governance</div>
          </div>
        </div>
        <h1 class="login-title">Sign in</h1>
        <p class="login-caption">Choose your role, then paste your access secret.</p>

        <div class="role-toggle" style="display:flex;gap:8px;margin-bottom:12px">
          <button type="button"
            class={role === 'company' ? 'btn-primary' : ''}
            style="flex:1" onClick={() => setRole('company')}>Company Admin</button>
          <button type="button"
            class={role === 'department' ? 'btn-primary' : ''}
            style="flex:1" onClick={() => setRole('department')}>Department Admin</button>
        </div>

        <label>Access secret<input type="password" value={secret}
          placeholder="Paste the secret you were given"
          onInput={(e) => setSecret((e.target as HTMLInputElement).value)} /></label>
        <button type="submit">Sign in</button>
        {error && <p class="error">{error}</p>}
        <p class="login-caption" style="margin-top:12px">
          New company? <a href="#" onClick={(e) => { e.preventDefault(); onCreate(); }}>Create one</a>.
        </p>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: Build (will fail until `main.tsx` passes the new props — expected)**

Run: `cd code/policy/admin && npm run build`
Expected: FAIL (`main.tsx` still calls `<Login onDone={...} />` with the old `(org: string)` signature). Fixed in Task 4.

- [ ] **Step 3: Commit**

```bash
git add code/policy/admin/src/screens/Login.tsx
git commit -m "feat(console): role-picker login on a pasted secret"
```

---

### Task 3: Signup screen

**Files:**
- Create: `code/policy/admin/src/screens/Signup.tsx`

**Interfaces:**
- Consumes: `api.post('/v1/signup', {company_name})` → `{org_id, secret}`.
- Produces: `Signup({ onBack })` — creates a company, shows the secret once, then returns to login.

- [ ] **Step 1: Create `Signup.tsx`**

```tsx
import { useState } from 'preact/hooks';
import { api, NetworkError } from '../api';
import { LayersIcon } from '../icons';

export function Signup({ onBack }: { onBack: () => void }) {
  const [name, setName] = useState('');
  const [secret, setSecret] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function submit(e: Event) {
    e.preventDefault();
    setBusy(true); setError('');
    try {
      const r = await api.post<{ org_id: string; secret: string }>('/v1/signup', { company_name: name });
      setSecret(r.secret);
    } catch (err) {
      if (err instanceof NetworkError) setError(err.message);
      else setError(err instanceof Error ? `Service error: ${err.message}` : 'Could not create the company.');
    } finally { setBusy(false); }
  }

  return (
    <div class="login-wrap">
      <div class="login-card">
        <div class="brand">
          <span class="brand-mark"><LayersIcon /></span>
          <div>
            <div class="brand-name">Vanguard</div>
            <div class="brand-sub">AI Governance</div>
          </div>
        </div>

        {!secret ? (
          <form onSubmit={submit}>
            <h1 class="login-title">Create a company</h1>
            <p class="login-caption">We generate your Company Admin secret. Save it — it is shown once.</p>
            <label>Company name<input value={name}
              placeholder="e.g. Acme Corp"
              onInput={(e) => setName((e.target as HTMLInputElement).value)} /></label>
            <button type="submit" disabled={busy || !name.trim()}>Create company</button>
            {error && <p class="error">{error}</p>}
            <p class="login-caption" style="margin-top:12px">
              <a href="#" onClick={(e) => { e.preventDefault(); onBack(); }}>Back to sign in</a>
            </p>
          </form>
        ) : (
          <div>
            <h1 class="login-title">Company created</h1>
            <div class="mint-result">
              <strong>Copy this Company Admin secret now — it will not be shown again.</strong><br />
              Sign in with the <em>Company Admin</em> role and paste it.
              <code>{secret}</code>
            </div>
            <button onClick={onBack}>I&apos;ve saved it — go to sign in</button>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add code/policy/admin/src/screens/Signup.tsx
git commit -m "feat(console): self-signup screen that shows the company secret once"
```

---

### Task 4: App shell — session model, role routing, verify-on-mount

**Files:**
- Modify: `code/policy/admin/src/main.tsx`

**Interfaces:**
- Consumes: `Login`, `Signup`, all screens, `Session`.
- Produces: role-gated `Company` and `Department` dashboards; session persisted under `vg_admin_session`.

- [ ] **Step 1: Rewrite `main.tsx`**

```tsx
import { render } from 'preact';
import { useEffect, useState } from 'preact/hooks';
import { api, UnauthorisedError, type Session, type Scope } from './api';
import { Login } from './screens/Login';
import { Signup } from './screens/Signup';
import { Tools } from './screens/Tools';
import { Departments } from './screens/Departments';
import { Requests } from './screens/Requests';
import { Reviews } from './screens/Reviews';
import { Usage } from './screens/Usage';
import { Tokens } from './screens/Tokens';
import { DeptTools } from './screens/DeptTools';
import { LayersIcon, ShieldIcon, InboxIcon, BarIcon, KeyIcon, GavelIcon } from './icons';
import './style.css';

const SESSION_KEY = 'vg_admin_session';

type TabDef = [string, string, typeof ShieldIcon, preact.ComponentChildren];

function loadSession(): Session | null {
  try { return JSON.parse(localStorage.getItem(SESSION_KEY) ?? 'null'); } catch { return null; }
}

function App() {
  const [session, setSession] = useState<Session | null>(loadSession);
  const [view, setView] = useState<'login' | 'signup'>('login');
  const [checking, setChecking] = useState(() => !!loadSession());

  // Verify a cached session with a role-appropriate authenticated call. A 401
  // means it expired -> drop it. Any other failure leaves it alone (the backend
  // may simply be down); the user retries with a reload. Timeout so a hung
  // request degrades the same way a rejection does.
  useEffect(() => {
    const cached = loadSession();
    if (!cached) return;
    const probe = cached.role === 'company' ? '/v1/admin/departments' : '/v1/dept/requests';
    const timeout = new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error('session check timed out')), 5000));
    Promise.race([api.get(probe), timeout])
      .then(() => { setSession(cached); setChecking(false); })
      .catch((err) => {
        if (err instanceof UnauthorisedError) localStorage.removeItem(SESSION_KEY);
        setChecking(false);
      });
  }, []);

  // A 401 anywhere bounces to login (screens don't catch UnauthorisedError).
  useEffect(() => {
    function onRejection(event: PromiseRejectionEvent) {
      if (event.reason instanceof UnauthorisedError) {
        event.preventDefault();
        localStorage.removeItem(SESSION_KEY);
        setSession(null);
      }
    }
    window.addEventListener('unhandledrejection', onRejection);
    return () => window.removeEventListener('unhandledrejection', onRejection);
  }, []);

  function handleLogin(s: Session) {
    localStorage.setItem(SESSION_KEY, JSON.stringify(s));
    setSession(s);
    setView('login');
  }

  async function logout() {
    try { await api.post('/v1/admin/logout'); } catch { /* clear locally regardless */ }
    localStorage.removeItem(SESSION_KEY);
    setSession(null);
  }

  if (checking) return <div class="login-wrap"><p class="empty">Checking session…</p></div>;
  if (!session) {
    return view === 'signup'
      ? <Signup onBack={() => setView('login')} />
      : <Login onDone={handleLogin} onCreate={() => setView('signup')} />;
  }
  return <Dashboard session={session} onLogout={logout} />;
}

function Dashboard({ session, onLogout }: { session: Session; onLogout: () => void }) {
  const isCompany = session.role === 'company';
  const tabs: TabDef[] = isCompany
    ? [
        ['departments', 'Departments', KeyIcon, <Departments />],
        ['tools', 'Tools', ShieldIcon, <Tools />],
        ['requests', 'Requests', InboxIcon, <Requests scope="company" />],
        ['reviews', 'Reviews', GavelIcon, <Reviews scope="company" />],
        ['usage', 'Usage', BarIcon, <Usage scope="company" />],
      ]
    : [
        ['requests', 'Requests', InboxIcon, <Requests scope="department" />],
        ['reviews', 'Reviews', GavelIcon, <Reviews scope="department" />],
        ['tokens', 'Employee Tokens', KeyIcon, <Tokens />],
        ['tools', 'Tools', ShieldIcon, <DeptTools />],
        ['usage', 'Usage', BarIcon, <Usage scope="department" />],
      ];
  const [active, setActive] = useState(tabs[0][0]);

  return (
    <div class="app">
      <header class="topbar">
        <div class="brand">
          <span class="brand-mark"><LayersIcon /></span>
          <div>
            <div class="brand-name">Vanguard</div>
            <div class="brand-sub">{isCompany ? 'Company Admin' : 'Department Admin'}</div>
          </div>
        </div>
        <div class="topbar-right">
          <span class="chip"><span class="dot" style="background:#4f46e5"></span> <strong>{session.org_name}</strong></span>
          {!isCompany && <span class="chip"><strong>{session.department}</strong></span>}
          <button class="btn-sm" onClick={onLogout}>Sign out</button>
        </div>
      </header>

      <nav class="tabs">
        {tabs.map(([id, label, Icon]) => (
          <button key={id} class={active === id ? 'active' : ''} onClick={() => setActive(id)}>
            <Icon /> {label}
          </button>
        ))}
      </nav>

      <main>{tabs.find((t) => t[0] === active)![3]}</main>
    </div>
  );
}

render(<App />, document.getElementById('root')!);
```

- [ ] **Step 2: Build (fails until Tasks 5–7 land the new/edited screens — expected)**

Run: `cd code/policy/admin && npm run build`
Expected: FAIL (`Departments`, `DeptTools`, and the `scope` props don't exist yet). Land Tasks 5–7 then rebuild.

- [ ] **Step 3: Commit**

```bash
git add code/policy/admin/src/main.tsx
git commit -m "feat(console): role-gated shell with session persistence and logout"
```

---

### Task 5: Departments screen (company)

**Files:**
- Create: `code/policy/admin/src/screens/Departments.tsx`

**Interfaces:**
- Consumes: `api.get('/v1/admin/departments')` → `Department[]`; `api.post('/v1/admin/departments', {name})` → `{id, name, secret}`; `api.post('/v1/admin/departments/{id}/regenerate')` → `{id, secret}`.

- [ ] **Step 1: Create `Departments.tsx`**

```tsx
import { useEffect, useState } from 'preact/hooks';
import { api, UnauthorisedError, type Department } from '../api';
import { KeyIcon } from '../icons';

export function Departments() {
  const [rows, setRows] = useState<Department[]>([]);
  const [name, setName] = useState('');
  const [minted, setMinted] = useState<{ name: string; secret: string } | null>(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  async function load() {
    try { setRows(await api.get<Department[]>('/v1/admin/departments')); setError(''); }
    catch (err) { if (err instanceof UnauthorisedError) throw err; setError(err instanceof Error ? err.message : 'Could not load departments.'); }
  }
  useEffect(() => { void load(); }, []);

  async function create() {
    setBusy('create'); setError('');
    try {
      const r = await api.post<{ id: string; name: string; secret: string }>('/v1/admin/departments', { name });
      setMinted({ name: r.name, secret: r.secret });
      setName('');
      await load();
    } catch (err) {
      if (err instanceof UnauthorisedError) throw err;
      setError(err instanceof Error ? err.message : 'Could not create the department.');
    } finally { setBusy(''); }
  }

  async function regenerate(id: string, deptName: string) {
    setBusy(id); setError('');
    try {
      const r = await api.post<{ id: string; secret: string }>(`/v1/admin/departments/${id}/regenerate`);
      setMinted({ name: deptName, secret: r.secret });
    } catch (err) {
      if (err instanceof UnauthorisedError) throw err;
      setError(err instanceof Error ? err.message : 'Could not regenerate the secret.');
    } finally { setBusy(''); }
  }

  return (
    <section class="panel">
      <div class="panel-head">
        <span class="ico"><KeyIcon /></span>
        <div>
          <h2>Departments</h2>
          <p class="sub">Create a department to get its Department Admin secret. The department admin signs in with it, then mints employee tokens.</p>
        </div>
        <span class="tag count">{rows.length}</span>
      </div>

      <div class="field">
        <input value={name} placeholder="Department name (e.g. Engineering)"
               onInput={(e) => setName((e.target as HTMLInputElement).value)} />
        <button class="btn-primary" disabled={busy === 'create' || !name.trim()} onClick={create}>Create department</button>
      </div>
      {error && <p class="error">{error}</p>}
      {minted && (
        <div class="mint-result">
          <strong>Department Admin secret for {minted.name} — copy it now, shown once.</strong>
          <code>{minted.secret}</code>
        </div>
      )}

      {rows.length === 0 && <p class="empty">No departments yet.</p>}
      {rows.length > 0 && (
        <table>
          <thead><tr><th>Department</th><th>Created</th><th>Active tokens</th><th></th></tr></thead>
          <tbody>
            {rows.map((d) => (
              <tr key={d.id}>
                <td><span class="name">{d.name}</span></td>
                <td><code>{new Date(d.created_at).toLocaleString()}</code></td>
                <td>{d.active_tokens}</td>
                <td>
                  <button class="btn-sm" disabled={busy === d.id} onClick={() => regenerate(d.id, d.name)}>
                    Regenerate secret
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add code/policy/admin/src/screens/Departments.tsx
git commit -m "feat(console): company departments screen (create + regenerate secret)"
```

---

### Task 6: `scope` prop on Requests, Reviews, Usage

**Files:**
- Modify: `code/policy/admin/src/screens/Requests.tsx`, `Reviews.tsx`, `Usage.tsx`

**Interfaces:**
- Produces: each screen takes `{ scope: Scope }`. `company` → `/v1/admin/*`, read-only. `department` → `/v1/dept/*`, actionable.

- [ ] **Step 1: Edit `Requests.tsx`**

Add the prop and derive the base path + read-only flag. Replace the signature and the two API calls:

```tsx
import { useEffect, useRef, useState } from 'preact/hooks';
import { api, UnauthorisedError, type RequestRow, type Scope } from '../api';
import { InboxIcon } from '../icons';

export function Requests({ scope }: { scope: Scope }) {
  const base = scope === 'company' ? '/v1/admin/requests' : '/v1/dept/requests';
  const readOnly = scope === 'company';
  const [rows, setRows] = useState<RequestRow[]>([]);
  const [busyId, setBusyId] = useState('');
  const [error, setError] = useState('');
  const seq = useRef(0);

  async function load() {
    const mine = ++seq.current;
    try {
      const data = await api.get<RequestRow[]>(base);
      if (mine !== seq.current) return;
      setRows(data); setError('');
    } catch (err) {
      if (err instanceof UnauthorisedError) throw err;
      setError(err instanceof Error ? err.message : 'Could not load requests.');
    }
  }

  useEffect(() => {
    void load();
    const timer = setInterval(() => { void load(); }, 3000);
    return () => clearInterval(timer);
  }, [base]);

  async function decide(id: string, decision: 'approved' | 'denied') {
    setBusyId(id); setError('');
    try {
      await api.post(`${base}/${id}`, { decision });
      await load();
    } catch (err) {
      if (err instanceof UnauthorisedError) throw err;
      setError(err instanceof Error ? err.message : 'Could not update the request.');
    } finally { setBusyId(''); }
  }

  const pending = rows.filter((r) => r.status === 'pending');

  return (
    <section class="panel">
      <div class="panel-head">
        <span class="ico"><InboxIcon /></span>
        <div>
          <h2>Access Requests</h2>
          <p class="sub">{readOnly
            ? 'Every department’s requests, across the company (read-only). Departments approve their own.'
            : 'Employees request a blocked tool; approve to unblock it for this department.'}</p>
        </div>
        <span class="tag count">{pending.length} pending</span>
      </div>
      {error && <p class="error">{error}</p>}
      {rows.length === 0 && <p class="empty">No requests yet.</p>}
      {rows.length > 0 && (
        <table>
          <thead><tr><th>Department</th><th>Tool</th><th>Reason</th><th>Raised</th><th></th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td><span class="name">{r.department}</span></td>
                <td>{r.display_name}</td>
                <td>{r.reason}</td>
                <td><code>{new Date(r.created_at).toLocaleTimeString()}</code></td>
                <td>
                  {r.status === 'pending' && !readOnly ? (
                    <div class="row-actions">
                      <button class="btn-primary btn-sm" disabled={busyId === r.id} onClick={() => decide(r.id, 'approved')}>Approve</button>
                      <button class="btn-danger btn-sm" disabled={busyId === r.id} onClick={() => decide(r.id, 'denied')}>Deny</button>
                    </div>
                  ) : (
                    <span class={`pill ${r.status}`}>{r.status}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
```

- [ ] **Step 2: Edit `Reviews.tsx`**

Same pattern. Change the signature to `Reviews({ scope }: { scope: Scope })`, add `const base = scope === 'company' ? '/v1/admin/appeals' : '/v1/dept/appeals';` and `const readOnly = scope === 'company';`. Replace `api.get<AppealRow[]>('/v1/admin/appeals')` with `api.get<AppealRow[]>(base)`, replace the decide POST `/v1/admin/appeals/${id}` with `${base}/${id}`, add `[base]` to the `useEffect` deps, and in the row render show the uphold/overturn buttons only when `r.status === 'pending' && !readOnly` (otherwise the existing decided-state `pill` + note). Import `type Scope` from `../api`.

- [ ] **Step 3: Edit `Usage.tsx`**

Change the signature to `Usage({ scope }: { scope: Scope })`, add `const url = scope === 'company' ? '/v1/admin/usage' : '/v1/dept/usage';`, replace `api.get<UsageData>('/v1/admin/usage')` with `api.get<UsageData>(url)`, and add `[url]` to the `useEffect` deps (move `load` above the effect or keep it inside as today, keyed on `url`). Both endpoints return the same `{by_department, by_tool, by_category}` shape, so the render is unchanged. Import `type Scope` from `../api`.

- [ ] **Step 4: Commit**

```bash
git add code/policy/admin/src/screens/Requests.tsx code/policy/admin/src/screens/Reviews.tsx code/policy/admin/src/screens/Usage.tsx
git commit -m "feat(console): scope-prop reuse of Requests/Reviews/Usage for both dashboards"
```

---

### Task 7: Employee Tokens (department) + read-only DeptTools

**Files:**
- Modify: `code/policy/admin/src/screens/Tokens.tsx` (department-scoped; no department input)
- Create: `code/policy/admin/src/screens/DeptTools.tsx`

**Interfaces:**
- `Tokens` now calls `/v1/dept/tokens` (mint with empty body), `/v1/dept/tokens/{id}/revoke`.
- `DeptTools` calls `/v1/dept/tools` and renders the effective policy read-only.

- [ ] **Step 1: Rewrite `Tokens.tsx` for the department scope**

```tsx
import { useEffect, useState } from 'preact/hooks';
import { api, UnauthorisedError, type TokenRow } from '../api';
import { KeyIcon } from '../icons';

export function Tokens() {
  const [rows, setRows] = useState<TokenRow[]>([]);
  const [minted, setMinted] = useState('');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  async function load() {
    try { setRows(await api.get<TokenRow[]>('/v1/dept/tokens')); setError(''); }
    catch (err) { if (err instanceof UnauthorisedError) throw err; setError(err instanceof Error ? err.message : 'Could not load tokens.'); }
  }
  useEffect(() => { void load(); }, []);

  async function mint() {
    setBusy('mint'); setError('');
    try {
      const r = await api.post<{ token: string }>('/v1/dept/tokens', {});
      setMinted(r.token);
      await load();
    } catch (err) {
      if (err instanceof UnauthorisedError) throw err;
      setError(err instanceof Error ? err.message : 'Could not mint a token.');
    } finally { setBusy(''); }
  }

  async function revoke(id: string) {
    setBusy(id); setError('');
    try { await api.post(`/v1/dept/tokens/${id}/revoke`); await load(); }
    catch (err) { if (err instanceof UnauthorisedError) throw err; setError(err instanceof Error ? err.message : 'Could not revoke the token.'); }
    finally { setBusy(''); }
  }

  return (
    <section class="panel">
      <div class="panel-head">
        <span class="ico"><KeyIcon /></span>
        <div>
          <h2>Employee Tokens</h2>
          <p class="sub">Each token enrols one employee into this department. Give one token per person; they paste it into the extension.</p>
        </div>
        <span class="tag count">{rows.filter((r) => !r.revoked).length} active</span>
      </div>

      <div class="field">
        <button class="btn-primary" disabled={busy === 'mint'} onClick={mint}>Mint employee token</button>
      </div>
      {error && <p class="error">{error}</p>}
      {minted && (
        <div class="mint-result">
          <strong>Copy this token now — it will not be shown again.</strong>
          <code>{minted}</code>
        </div>
      )}
      <p class="hint">
        <strong>Revoke</strong> stops a token being used for <em>new</em> enrolments. It does not cut
        off anyone already enrolled with it.
      </p>

      {rows.length === 0 && <p class="empty">No tokens minted yet.</p>}
      {rows.length > 0 && (
        <table>
          <thead><tr><th>Department</th><th>Created</th><th>State</th><th></th></tr></thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td><span class="name">{row.department}</span></td>
                <td><code>{new Date(row.created_at).toLocaleString()}</code></td>
                <td><span class={`pill ${row.revoked ? 'revoked' : 'active'}`}>{row.revoked ? 'revoked' : 'active'}</span></td>
                <td>
                  {!row.revoked && (
                    <button class="btn-danger btn-sm" disabled={busy === row.id} onClick={() => revoke(row.id)}>Revoke</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
```

- [ ] **Step 2: Create `DeptTools.tsx`**

```tsx
import { useEffect, useState } from 'preact/hooks';
import { api, UnauthorisedError, type Tool } from '../api';
import { ShieldIcon } from '../icons';

export function DeptTools() {
  const [rows, setRows] = useState<Tool[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    async function load() {
      try { setRows(await api.get<Tool[]>('/v1/dept/tools')); setError(''); }
      catch (err) { if (err instanceof UnauthorisedError) throw err; setError(err instanceof Error ? err.message : 'Could not load tools.'); }
    }
    void load();
    const t = setInterval(() => { void load(); }, 3000);
    return () => clearInterval(t);
  }, []);

  return (
    <section class="panel">
      <div class="panel-head">
        <span class="ico"><ShieldIcon /></span>
        <div>
          <h2>Tools</h2>
          <p class="sub">What is approved for this department — the company default, plus any tool this department has unblocked via an access request. Read-only here.</p>
        </div>
      </div>
      {error && <p class="error">{error}</p>}
      {rows.length === 0 && <p class="empty">Loading…</p>}
      {rows.length > 0 && (
        <table>
          <thead><tr><th>Tool</th><th>Host</th><th>Status</th></tr></thead>
          <tbody>
            {rows.map((t) => (
              <tr key={t.llm_id}>
                <td><span class="name">{t.display_name}</span></td>
                <td><code>{t.host}</code></td>
                <td><span class={`pill ${t.status === 'approved' ? 'approved' : 'blocked'}`}>{t.status}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
```

- [ ] **Step 3: Build the whole console**

Run: `cd code/policy/admin && npm run build`
Expected: PASS (all screens, shell, signup, and login compile together).

- [ ] **Step 4: Commit**

```bash
git add code/policy/admin/src/screens/Tokens.tsx code/policy/admin/src/screens/DeptTools.tsx
git commit -m "feat(console): department employee-tokens and read-only effective tools"
```

---

### Task 8: Extension — carry `department_id` through enrolment and polling

**Files:**
- Modify: `code/extension/src/policy/types.ts` (add `department_id?` to `Enrolment`)
- Modify: `code/extension/src/policy/client.ts` (save it on enrol; send it on poll)
- Test: `code/extension/tests/policy-client.test.ts` (create, if no client test exists)

**Interfaces:**
- Consumes: `EnrollResponse.department_id` from the backend (Plan 1 Task 12).
- Produces: `GET /v1/policy` requests include `&department_id=…` when known.

- [ ] **Step 1: Write the failing test**

```typescript
// code/extension/tests/policy-client.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';

// Minimal chrome.storage.local shim backed by a Map.
const store = new Map<string, unknown>();
(globalThis as any).chrome = {
  storage: { local: {
    get: async (k: string) => ({ [k]: store.get(k) }),
    set: async (o: Record<string, unknown>) => { for (const k in o) store.set(k, o[k]); },
    remove: async (ks: string[]) => { ks.forEach((k) => store.delete(k)); },
  } },
};

vi.mock('../src/policy/config', () => ({
  POLICY_CONFIG: { requestTimeoutMs: 1000 },
  getPolicyBase: async () => 'http://policy.test',
}));

import { refreshPolicy } from '../src/policy/client';
import { saveEnrolment } from '../src/policy/store';

describe('refreshPolicy', () => {
  beforeEach(() => { store.clear(); });

  it('sends department_id when the enrolment has one', async () => {
    await saveEnrolment(
      { org_id: 'org1', org_name: 'Acme', pseudo_id: 'p1', department: 'Eng', department_id: 'dept1' },
      { org_id: 'org1', org_name: 'Acme', version: 1, tools: [], categories: [] },
    );
    const fetchMock = vi.fn(async () => new Response('{}', { status: 304 }));
    (globalThis as any).fetch = fetchMock;

    await refreshPolicy();

    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain('org_id=org1');
    expect(url).toContain('department_id=dept1');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd code/extension && npm test -- policy-client`
Expected: FAIL (URL lacks `department_id` — the client doesn't send it yet).

- [ ] **Step 3: Add the field to `types.ts`**

In `Enrolment`:

```typescript
export type Enrolment = {
  org_id: string;
  org_name: string;
  pseudo_id: string;
  department: string;
  department_id?: string;
};
```

- [ ] **Step 4: Persist and send it in `client.ts`**

In `enrol`, include `department_id` when building the saved enrolment:

```typescript
  const enrolment: Enrolment = {
    org_id: body.org_id, org_name: body.org_name,
    pseudo_id: body.pseudo_id, department: body.department,
    department_id: (body as Enrolment).department_id,
  };
```

In `refreshPolicy`, append the query param when present:

```typescript
    const deptParam = enrolment.department_id
      ? `&department_id=${encodeURIComponent(enrolment.department_id)}`
      : '';
    const response = await timedFetch(
      `${base}/v1/policy?org_id=${encodeURIComponent(enrolment.org_id)}${deptParam}`,
      { headers: etag ? { 'If-None-Match': etag } : {} },
    );
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd code/extension && npm test -- policy-client`
Expected: PASS (1 passed).

- [ ] **Step 6: Full extension suite + build stay green**

Run: `cd code/extension && npm test && npm run build`
Expected: PASS (no regression; the new field is optional so existing enrolments still poll).

- [ ] **Step 7: Commit**

```bash
git add code/extension/src/policy/types.ts code/extension/src/policy/client.ts code/extension/tests/policy-client.test.ts
git commit -m "feat(ext): poll department-scoped policy via department_id"
```

---

### Task 9: End-to-end manual acceptance

**Files:** none (verification only). Requires Plan 1 merged.

- [ ] **Step 1: Seed and run the backend**

```bash
cd code/policy
rm -f policy.db
python scripts/seed.py            # writes DEMO-TOKENS.md
cd admin && npm run build && cd ..
python -m uvicorn app.main:app --port 8001
```

- [ ] **Step 2: Walk the three tiers in the browser at http://localhost:8001/**

Confirm each, using secrets from `DEMO-TOKENS.md`:
- **Signup:** "Create one" → company name → a Company Admin secret is shown once.
- **Company Admin login:** paste the company secret with the Company Admin role → lands on **Departments / Tools / Requests / Reviews / Usage**. Requests and Reviews show every department read-only (no Approve/Deny buttons). Create a department → a Department Admin secret is shown once; Regenerate produces a new one.
- **Department Admin login** (new tab): paste a Department Admin secret with the Department Admin role → lands on **Requests / Reviews / Employee Tokens / Tools / Usage**, showing only that department. Mint an employee token.
- **Isolation:** the department dashboard never shows another department's requests, tokens, or usage.

- [ ] **Step 3: Extension round-trip**

Enrol the extension with a minted employee token; confirm it reports the right department, that a tool the department has approved via a request shows as approved on the employee's next poll, and that a different department's employee does not get that approval.

- [ ] **Step 4: Commit any doc fixes surfaced**

```bash
git add -A
git commit -m "docs: acceptance fixes for department hierarchy console"
```

---

## Self-Review

**Spec coverage (§6 + extension bullet):** Signup screen → Task 3. Role-picker login → Task 2. Role-gated shell + session → Task 4. Company tabs (Departments/Tools/Usage/oversight Requests+Reviews) → Tasks 4–6. Department tabs (Requests/Reviews/Employee Tokens/Tools/Usage) → Tasks 4, 6, 7. `scope`-prop reuse → Task 6. Departments screen → Task 5. DeptTools (effective, read-only) → Task 7. Extension `department_id` poll → Task 8. Pseudonymity preserved — no screen renders a name; department views group by department only.

**Placeholder scan:** every screen has complete code; Tasks 6 (Reviews/Usage edits) describe exact signature/line changes against files quoted in full in Plan 1's reading. No TBD/TODO.

**Type consistency:** `Session`/`Scope`/`Department`/`LoginResult` defined in Task 1 and consumed identically in Tasks 2, 4, 5, 6. `Requests`/`Reviews`/`Usage` all take `{ scope: Scope }`; `Tokens` and `DeptTools` take no props (department comes from the session server-side). `Enrolment.department_id?` added in Task 8 and read in the same task's `client.ts`. All API paths match Plan 1's routes (`/v1/admin/departments`, `/v1/dept/tokens`, `/v1/dept/tools`, `/v1/policy?...department_id=`).

**Build ordering:** Tasks 2 and 4 intentionally leave the build red until their dependent screens (Tasks 5–7) land; Task 7 Step 3 is the first green console build. Task 8 is independent of the console and green on its own.
