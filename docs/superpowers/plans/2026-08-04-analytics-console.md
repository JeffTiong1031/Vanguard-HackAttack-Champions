# Analytics & Insider-Risk — Console Plan (2 of 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the AI Usage and Insider Risk tabs to both consoles (inline-SVG charts, current design), a name field on the Employee-Tokens screen, and one truthful copy change in the extension.

**Architecture:** New pure chart helpers (`pivotTrend`, `scalePoints`) are unit-tested with Vitest (added to the admin app, which had no test runner). Presentational components (`Bars`, `LineChart`, `AlertsTable`) live in one `charts.tsx`. Two screens (`AiUsage`, `InsiderRisk`) take a `scope` prop that swaps `/v1/admin/analytics/*` ↔ `/v1/dept/analytics/*`, mirroring the hierarchy screens.

**Tech Stack:** Preact, Vite, TypeScript, Vitest (new to the admin app). Extension: WXT + Vitest.

**Depends on:** the backend plan merged (all `/analytics/*` endpoints + `employees.name`).

**Spec:** `docs/superpowers/specs/2026-08-04-analytics-insider-risk-design.md` §4–5, §7.

## Global Constraints

- **No chart library** — inline SVG only (CSP-clean, dependency-light, matches the console's hand-rolled bars + inline SVG icons).
- **Preact `class=` not `className=`**; reuse existing `style.css` classes (`panel`, `panel-head`, `bars-group`, `bar-row`, `bar-track`, `bar-fill`, `lbl`, `val`, `table`, `pill`, `tag`, `field`, `btn-primary`, `btn-sm`, `empty`); inline styles for the SVG chart/legend.
- **Scope prop:** `company` → `/v1/admin/analytics/*`, `department` → `/v1/dept/analytics/*`. In department scope, hide *Top Departments*.
- **Risk weights shown in the UI** (legend): ethics_block 5 · pii_block 3 · warn 1 · visit 1 · request 0. Risk is a labelled heuristic.
- **Range presets only:** 7 or 30 days.
- **Admin app build gates:** from `code/policy/admin/`: `npx tsc --noEmit` (no errors) AND `npm run build` (succeeds). Helper tests: `npm test`.
- **Extension gates:** from `code/extension/`: `npm test` and `npm run build`; commit regenerated `dist/`.
- **Commits: sole author, no `Co-Authored-By` trailer.**

---

### Task 1: Add Vitest to the admin app

**Files:**
- Modify: `code/policy/admin/package.json`
- Test: `code/policy/admin/src/_sanity.test.ts` (create, temporary sanity check)

- [ ] **Step 1: Add a test script and Vitest dev dependency**

Edit `code/policy/admin/package.json` — add `"test": "vitest run"` to `scripts`, and `"vitest": "^2.0.0"` to `devDependencies`. Result:

```json
{
  "name": "vanguard-admin",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "test": "vitest run"
  },
  "dependencies": { "preact": "^10.24.0" },
  "devDependencies": {
    "@preact/preset-vite": "^2.9.0",
    "typescript": "^5.6.0",
    "vite": "^5.4.0",
    "vitest": "^2.0.0"
  }
}
```

- [ ] **Step 2: Install**

Run: `cd code/policy/admin && npm install`
Expected: installs Vitest (network required). If the environment is offline, this is the one step that needs connectivity — surface it rather than working around it.

- [ ] **Step 3: Add a sanity test and run it**

```typescript
// code/policy/admin/src/_sanity.test.ts
import { test, expect } from 'vitest';
test('vitest runs', () => { expect(1 + 1).toBe(2); });
```

Run: `cd code/policy/admin && npm test`
Expected: PASS (1 passed).

- [ ] **Step 4: Remove the sanity test and commit the setup**

```bash
rm code/policy/admin/src/_sanity.test.ts
git add code/policy/admin/package.json code/policy/admin/package-lock.json
git commit -m "chore(console): add vitest for pure helper tests"
```

---

### Task 2: Analytics types in `api.ts`

**Files:**
- Modify: `code/policy/admin/src/api.ts`

**Interfaces:**
- Produces: `TrendPoint`, `TimelinePoint`, `RiskPoint`, `TopApp`, `TopEmployee`, `TopDepartment`, `SeverityCount`, `AnalyticsSummary`, `AlertRow`; `TokenRow` gains `name?`.

- [ ] **Step 1: Add the types**

Append to `code/policy/admin/src/api.ts`:

```typescript
export type TrendPoint = { date: string; department: string; events: number };
export type TimelinePoint = { date: string; high: number; medium: number; low: number };
export type RiskPoint = { date: string; risk: number };
export type TopApp = { host: string; events: number };
export type TopEmployee = { name: string; department: string; events: number; risk: number };
export type TopDepartment = { department: string; events: number; risk: number };
export type SeverityCount = { severity: string; count: number };

export type AnalyticsSummary = {
  usage_trend: TrendPoint[];
  alerts_timeline: TimelinePoint[];
  risk_timeline: RiskPoint[];
  top_apps: TopApp[];
  top_employees: TopEmployee[];
  top_departments: TopDepartment[];
  alerts_by_severity: SeverityCount[];
  totals: { events: number; active_employees: number; days: number };
};

export type AlertRow = {
  ts: string; department: string; name: string; host: string;
  type: string; category: string | null; action: string; severity: string;
};
```

And change `TokenRow` to add an optional `name`:

```typescript
export type TokenRow = {
  id: string; department: string; label: string; name?: string; created_at: string; revoked: number;
};
```

- [ ] **Step 2: Typecheck**

Run: `cd code/policy/admin && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add code/policy/admin/src/api.ts
git commit -m "feat(console): analytics summary and alert types"
```

---

### Task 3: Pure chart helpers (`pivotTrend`, `scalePoints`)

**Files:**
- Create: `code/policy/admin/src/screens/chart-helpers.ts`
- Test: `code/policy/admin/src/screens/chart-helpers.test.ts`

**Interfaces:**
- Produces:
  - `type TrendSeries = { dates: string[]; series: { department: string; points: number[] }[] }`
  - `pivotTrend(rows: {date:string; department:string; events:number}[]): TrendSeries`
  - `scalePoints(values: number[], width: number, height: number, max?: number, pad?: number): {x:number;y:number}[]`

- [ ] **Step 1: Write the failing test**

```typescript
// code/policy/admin/src/screens/chart-helpers.test.ts
import { test, expect } from 'vitest';
import { pivotTrend, scalePoints } from './chart-helpers';

test('pivotTrend aligns departments to a shared sorted date axis and zero-fills gaps', () => {
  const { dates, series } = pivotTrend([
    { date: '2026-08-02', department: 'Eng', events: 3 },
    { date: '2026-08-01', department: 'Eng', events: 1 },
    { date: '2026-08-02', department: 'Sales', events: 5 },
  ]);
  expect(dates).toEqual(['2026-08-01', '2026-08-02']);
  const eng = series.find((s) => s.department === 'Eng')!;
  const sales = series.find((s) => s.department === 'Sales')!;
  expect(eng.points).toEqual([1, 3]);
  expect(sales.points).toEqual([0, 5]); // no event on 08-01 -> 0
});

test('scalePoints spreads x evenly and inverts y against the max', () => {
  const pts = scalePoints([0, 10], 100, 100, 10, 0); // pad 0, max 10
  expect(pts[0]).toEqual({ x: 0, y: 100 });   // value 0 -> bottom
  expect(pts[1]).toEqual({ x: 100, y: 0 });   // value 10 (=max) -> top
});

test('scalePoints centers a single point and never divides by zero', () => {
  const pts = scalePoints([5], 100, 100, 5, 0);
  expect(pts).toEqual([{ x: 50, y: 0 }]);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd code/policy/admin && npm test`
Expected: FAIL (`Cannot find module './chart-helpers'`).

- [ ] **Step 3: Create `chart-helpers.ts`**

```typescript
export type TrendSeries = { dates: string[]; series: { department: string; points: number[] }[] };

/** Turn flat [{date, department, events}] rows into one aligned series per
 *  department over a shared, sorted date axis (missing days -> 0). */
export function pivotTrend(rows: { date: string; department: string; events: number }[]): TrendSeries {
  const dates = [...new Set(rows.map((r) => r.date))].sort();
  const byDept = new Map<string, Map<string, number>>();
  for (const r of rows) {
    if (!byDept.has(r.department)) byDept.set(r.department, new Map());
    byDept.get(r.department)!.set(r.date, r.events);
  }
  const series = [...byDept.entries()].map(([department, m]) => ({
    department,
    points: dates.map((d) => m.get(d) ?? 0),
  }));
  return { dates, series };
}

/** Map values to SVG coordinates: x evenly spaced across width, y inverted
 *  against `max` (default = the series max, floored at 1). A single point is
 *  centered. `pad` insets both axes. */
export function scalePoints(
  values: number[], width: number, height: number,
  max: number = Math.max(1, ...values), pad = 4,
): { x: number; y: number }[] {
  const n = values.length;
  const m = Math.max(1, max);
  const innerW = Math.max(1, width - pad * 2);
  const innerH = Math.max(1, height - pad * 2);
  return values.map((v, i) => ({
    x: pad + (n <= 1 ? innerW / 2 : (i / (n - 1)) * innerW),
    y: pad + innerH - (v / m) * innerH,
  }));
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd code/policy/admin && npm test`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add code/policy/admin/src/screens/chart-helpers.ts code/policy/admin/src/screens/chart-helpers.test.ts
git commit -m "feat(console): pure chart helpers (pivotTrend, scalePoints)"
```

---

### Task 4: Chart components (`Bars`, `LineChart`, `AlertsTable`, `RangeSelector`)

**Files:**
- Create: `code/policy/admin/src/screens/charts.tsx`

**Interfaces:**
- Consumes: `scalePoints` from `chart-helpers`; `AlertRow` from `api`.
- Produces: `Bars`, `LineChart`, `AlertsTable`, `RangeSelector` components.

- [ ] **Step 1: Create `charts.tsx`**

```tsx
import { scalePoints } from './chart-helpers';
import type { AlertRow } from '../api';

const COLORS = ['#4f46e5', '#e11d48', '#059669', '#d97706', '#0891b2', '#7c3aed', '#db2777'];

/** Horizontal bar list — the console's existing style (moved out of Usage). */
export function Bars({ title, rows }: { title: string; rows: { label: string; value: number }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <div class="bars-group">
      <h3>{title}</h3>
      {rows.length === 0 && <p class="empty">No data yet.</p>}
      {rows.map((r) => (
        <div class="bar-row" key={r.label}>
          <span class="lbl">{r.label}</span>
          <span class="bar-track">
            <span class="bar-fill" style={`width:${Math.max(4, (r.value / max) * 100)}%`} />
          </span>
          <span class="val">{r.value}</span>
        </div>
      ))}
    </div>
  );
}

/** Multi-series inline-SVG line chart. All series share one y-scale (global max)
 *  so lines are comparable. */
export function LineChart({
  title, series, height = 140,
}: { title: string; series: { department: string; points: number[] }[]; height?: number }) {
  const width = 640;
  const globalMax = Math.max(1, ...series.flatMap((s) => s.points));
  const hasData = series.some((s) => s.points.length > 0);
  return (
    <div class="bars-group">
      <h3>{title}</h3>
      {!hasData && <p class="empty">No data yet.</p>}
      {hasData && (
        <>
          <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none"
               style="width:100%;height:160px;background:#f8fafc;border-radius:6px">
            {series.map((s, i) => {
              const pts = scalePoints(s.points, width, height, globalMax);
              const d = pts.map((p, j) => `${j === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
              return <path d={d} fill="none" stroke={COLORS[i % COLORS.length]} stroke-width="2" />;
            })}
          </svg>
          <div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:8px;font-size:12px;color:#475569">
            {series.map((s, i) => (
              <span style="display:inline-flex;align-items:center;gap:4px">
                <i style={`width:10px;height:10px;border-radius:2px;background:${COLORS[i % COLORS.length]}`} />
                {s.department}
              </span>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

const SEV_CLASS: Record<string, string> = { high: 'blocked', medium: 'revoked', low: 'active' };

export function AlertsTable({ rows }: { rows: AlertRow[] }) {
  if (rows.length === 0) return <p class="empty">No alerts in this window.</p>;
  return (
    <table>
      <thead><tr>
        <th>Time</th><th>Department</th><th>Employee</th><th>Tool</th>
        <th>Type</th><th>Action</th><th>Severity</th>
      </tr></thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>
            <td><code>{new Date(r.ts).toLocaleString()}</code></td>
            <td>{r.department}</td>
            <td><span class="name">{r.name}</span></td>
            <td><code>{r.host}</code></td>
            <td>{r.type}{r.category ? ` · ${r.category}` : ''}</td>
            <td>{r.action}</td>
            <td><span class={`pill ${SEV_CLASS[r.severity] ?? 'active'}`}>{r.severity}</span></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function RangeSelector({ days, onChange }: { days: number; onChange: (d: number) => void }) {
  return (
    <div style="display:flex;gap:8px;margin-bottom:12px">
      {[7, 30].map((d) => (
        <button class={days === d ? 'btn-primary btn-sm' : 'btn-sm'} onClick={() => onChange(d)}>
          Last {d} days
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd code/policy/admin && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add code/policy/admin/src/screens/charts.tsx
git commit -m "feat(console): inline-SVG chart components"
```

---

### Task 5: AI Usage screen

**Files:**
- Create: `code/policy/admin/src/screens/AiUsage.tsx`

**Interfaces:**
- Consumes: `api`, `AnalyticsSummary`, `Scope`; `Bars`, `LineChart`, `RangeSelector`; `pivotTrend`.

- [ ] **Step 1: Create `AiUsage.tsx`**

```tsx
import { useEffect, useState } from 'preact/hooks';
import { api, UnauthorisedError, type AnalyticsSummary, type Scope } from '../api';
import { BarIcon } from '../icons';
import { Bars, LineChart, RangeSelector } from './charts';
import { pivotTrend } from './chart-helpers';

export function AiUsage({ scope }: { scope: Scope }) {
  const base = scope === 'company' ? '/v1/admin/analytics' : '/v1/dept/analytics';
  const [days, setDays] = useState(7);
  const [data, setData] = useState<AnalyticsSummary | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    async function load() {
      try { setData(await api.get<AnalyticsSummary>(`${base}/summary?days=${days}`)); setError(''); }
      catch (err) { if (err instanceof UnauthorisedError) throw err; setError(err instanceof Error ? err.message : 'Could not load usage.'); }
    }
    void load();
  }, [base, days]);

  if (!data) return <section class="panel"><p class="empty">{error || 'Loading…'}</p></section>;
  const trend = pivotTrend(data.usage_trend);

  return (
    <section class="panel">
      <div class="panel-head">
        <span class="ico"><BarIcon /></span>
        <div>
          <h2>AI Usage</h2>
          <p class="sub">Governance events — class, count, host, never prompt text.</p>
        </div>
        <span class="tag">{data.totals.events} events · {data.totals.active_employees} people</span>
      </div>
      <RangeSelector days={days} onChange={setDays} />
      {error && <p class="error">{error}</p>}
      <LineChart title="Usage trend by department" series={trend.series} />
      <Bars title="Top apps / domains" rows={data.top_apps.map((a) => ({ label: a.host, value: a.events }))} />
      <Bars title="Top employees" rows={data.top_employees.map((e) => ({ label: `${e.name} · ${e.department}`, value: e.events }))} />
    </section>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd code/policy/admin && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add code/policy/admin/src/screens/AiUsage.tsx
git commit -m "feat(console): AI Usage tab (trend, top apps, top employees)"
```

---

### Task 6: Insider Risk screen

**Files:**
- Create: `code/policy/admin/src/screens/InsiderRisk.tsx`

**Interfaces:**
- Consumes: `api`, `AnalyticsSummary`, `AlertRow`, `Scope`; `Bars`, `LineChart`, `AlertsTable`, `RangeSelector`.

- [ ] **Step 1: Create `InsiderRisk.tsx`**

```tsx
import { useEffect, useState } from 'preact/hooks';
import { api, UnauthorisedError, type AnalyticsSummary, type AlertRow, type Scope } from '../api';
import { ShieldIcon } from '../icons';
import { Bars, LineChart, AlertsTable, RangeSelector } from './charts';

const WEIGHTS = 'Risk weights: ethics block 5 · PII block 3 · warning 1 · unapproved visit 1 · access request 0';

export function InsiderRisk({ scope }: { scope: Scope }) {
  const base = scope === 'company' ? '/v1/admin/analytics' : '/v1/dept/analytics';
  const [days, setDays] = useState(7);
  const [data, setData] = useState<AnalyticsSummary | null>(null);
  const [alerts, setAlerts] = useState<AlertRow[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    async function load() {
      try {
        setData(await api.get<AnalyticsSummary>(`${base}/summary?days=${days}`));
        setAlerts(await api.get<AlertRow[]>(`${base}/alerts?limit=50`));
        setError('');
      } catch (err) { if (err instanceof UnauthorisedError) throw err; setError(err instanceof Error ? err.message : 'Could not load risk data.'); }
    }
    void load();
  }, [base, days]);

  if (!data) return <section class="panel"><p class="empty">{error || 'Loading…'}</p></section>;

  const riskLine = [{ department: 'Risk', points: data.risk_timeline.map((r) => r.risk) }];
  const alertLines = [
    { department: 'High', points: data.alerts_timeline.map((r) => r.high) },
    { department: 'Medium', points: data.alerts_timeline.map((r) => r.medium) },
    { department: 'Low', points: data.alerts_timeline.map((r) => r.low) },
  ];

  return (
    <section class="panel">
      <div class="panel-head">
        <span class="ico"><ShieldIcon /></span>
        <div>
          <h2>Insider Risk</h2>
          <p class="sub">A transparent heuristic over governance events. It ranks; it does not diagnose.</p>
        </div>
        <span class="tag">{data.totals.events} events</span>
      </div>
      <RangeSelector days={days} onChange={setDays} />
      <p class="hint">{WEIGHTS}</p>
      {error && <p class="error">{error}</p>}

      <LineChart title="Risk score timeline" series={riskLine} />
      <LineChart title="Alerts timeline (by severity)" series={alertLines} />
      <Bars title="Top risky employees"
            rows={data.top_employees.map((e) => ({ label: `${e.name} · ${e.department}`, value: e.risk }))} />
      {scope === 'company' && (
        <Bars title="Top risky departments"
              rows={data.top_departments.map((d) => ({ label: d.department, value: d.risk }))} />
      )}
      <Bars title="Alerts by severity"
            rows={data.alerts_by_severity.map((s) => ({ label: s.severity, value: s.count }))} />
      <h3 style="margin-top:20px">Review alerts</h3>
      <AlertsTable rows={alerts} />
    </section>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd code/policy/admin && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add code/policy/admin/src/screens/InsiderRisk.tsx
git commit -m "feat(console): Insider Risk tab (timelines, risky ranks, alerts table)"
```

---

### Task 7: Wire the tabs; retire the old Usage screen

**Files:**
- Modify: `code/policy/admin/src/main.tsx`
- Delete: `code/policy/admin/src/screens/Usage.tsx`

- [ ] **Step 1: Update imports in `main.tsx`**

Replace the `Usage` import line with the two new screens:

```typescript
import { AiUsage } from './screens/AiUsage';
import { InsiderRisk } from './screens/InsiderRisk';
```

(Remove `import { Usage } from './screens/Usage';`.)

- [ ] **Step 2: Update the tab arrays in `Dashboard`**

Replace the company `tabs` array's `usage` entry and append Insider Risk:

```tsx
  const tabs: TabDef[] = isCompany
    ? [
        ['departments', 'Departments', KeyIcon, <Departments />],
        ['tools', 'Tools', ShieldIcon, <Tools />],
        ['requests', 'Requests', InboxIcon, <Requests scope="company" />],
        ['reviews', 'Reviews', GavelIcon, <Reviews scope="company" />],
        ['usage', 'AI Usage', BarIcon, <AiUsage scope="company" />],
        ['risk', 'Insider Risk', ShieldIcon, <InsiderRisk scope="company" />],
      ]
    : [
        ['requests', 'Requests', InboxIcon, <Requests scope="department" />],
        ['reviews', 'Reviews', GavelIcon, <Reviews scope="department" />],
        ['tokens', 'Employee Tokens', KeyIcon, <Tokens />],
        ['tools', 'Tools', ShieldIcon, <DeptTools />],
        ['usage', 'AI Usage', BarIcon, <AiUsage scope="department" />],
        ['risk', 'Insider Risk', ShieldIcon, <InsiderRisk scope="department" />],
      ];
```

- [ ] **Step 3: Delete the retired screen**

```bash
rm code/policy/admin/src/screens/Usage.tsx
```

- [ ] **Step 4: Typecheck + build**

Run: `cd code/policy/admin && npx tsc --noEmit && npm run build`
Expected: no type errors; build succeeds (nothing imports the deleted `Usage` anymore).

- [ ] **Step 5: Commit**

```bash
git add code/policy/admin/src/main.tsx code/policy/admin/src/screens/Usage.tsx
git commit -m "feat(console): add AI Usage and Insider Risk tabs to both dashboards"
```

---

### Task 8: Name field on the Employee-Tokens screen

**Files:**
- Modify: `code/policy/admin/src/screens/Tokens.tsx`

- [ ] **Step 1: Add a name input and send it on mint**

In `Tokens.tsx`, add a `name` state and field, and post it. Replace the `mint` function and the mint `<div class="field">` block:

```tsx
  const [name, setName] = useState('');
  // ...
  async function mint() {
    setBusy('mint'); setError('');
    try {
      const r = await api.post<{ token: string }>('/v1/dept/tokens', { name: name.trim() });
      setMinted(r.token);
      setName('');
      await load();
    } catch (err) {
      if (err instanceof UnauthorisedError) throw err;
      setError(err instanceof Error ? err.message : 'Could not mint a token.');
    } finally { setBusy(''); }
  }
```

```tsx
      <div class="field">
        <input value={name} placeholder="Employee name (optional)"
               onInput={(e) => setName((e.target as HTMLInputElement).value)} />
        <button class="btn-primary" disabled={busy === 'mint'} onClick={mint}>Mint employee token</button>
      </div>
```

Add a `Name` column to the table header and rows:

```tsx
          <thead><tr><th>Name</th><th>Department</th><th>Created</th><th>State</th><th></th></tr></thead>
```

```tsx
              <tr key={row.id}>
                <td>{row.name || <span style="color:#94a3b8">—</span>}</td>
                <td><span class="name">{row.department}</span></td>
                <td><code>{new Date(row.created_at).toLocaleString()}</code></td>
                <td><span class={`pill ${row.revoked ? 'revoked' : 'active'}`}>{row.revoked ? 'revoked' : 'active'}</span></td>
                <td>
                  {!row.revoked && (
                    <button class="btn-danger btn-sm" disabled={busy === row.id} onClick={() => revoke(row.id)}>Revoke</button>
                  )}
                </td>
              </tr>
```

- [ ] **Step 2: Typecheck + build**

Run: `cd code/policy/admin && npx tsc --noEmit && npm run build`
Expected: no errors; build succeeds.

- [ ] **Step 3: Commit**

```bash
git add code/policy/admin/src/screens/Tokens.tsx
git commit -m "feat(console): name field when minting an employee token"
```

---

### Task 9: Extension copy — keep the privacy promise truthful

**Files:**
- Modify: `code/extension/entrypoints/options/main.tsx`

- [ ] **Step 1: Reword the enrolment blurb**

In `Organisation()`'s not-enrolled branch, replace:

```tsx
      <p style="color:#475569">
        Paste the enrolment token your admin gave you. It identifies your department,
        not you — Vanguard never stores your name or email address.
      </p>
```

with:

```tsx
      <p style="color:#475569">
        Paste the enrolment token your admin gave you. Vanguard never collects your name,
        email, or prompt text. Your organisation may label your enrolment with your name
        for its own records.
      </p>
```

- [ ] **Step 2: Build, sync dist, run the extension suite**

Run: `cd code/extension && npm run build && npm test`
Expected: build succeeds; all tests pass (`dist-drift` passes after rebuild).

- [ ] **Step 3: Commit (src + regenerated dist)**

```bash
git add code/extension/entrypoints/options/main.tsx code/extension/dist
git commit -m "docs(ext): truthful enrolment copy now that admins may label names"
```

---

### Task 10: Manual acceptance (verification only)

**Files:** none. Requires the backend running with a reseeded DB (backend plan merged).

- [ ] **Step 1: Reseed and serve**

```bash
cd code/policy && rm -f policy.db && ./.venv/Scripts/python scripts/seed.py
cd admin && npm run build && cd ..
./.venv/Scripts/python -m uvicorn app.main:app --port 8001
```

- [ ] **Step 2: Verify company analytics**

At `http://localhost:8001/`, log in as Company Admin. Open **AI Usage** — a multi-department trend line, top apps, and **named** top employees render, and the range toggle (7/30) changes the data. Open **Insider Risk** — risk + alerts timelines, top risky employees/departments (named), alerts-by-severity, the weights legend, and the review-alerts table all populate.

- [ ] **Step 3: Verify department scope**

Log in as a Department Admin (second tab). Confirm **AI Usage** and **Insider Risk** show only that department's data, and **Top Risky Departments is hidden**. On **Employee Tokens**, mint a token with a name and confirm it appears in the table.

- [ ] **Step 4: Commit any doc fixes surfaced**

```bash
git add -A && git commit -m "docs: acceptance fixes for analytics dashboards" || echo "nothing to fix"
```

---

## Self-Review

**Spec coverage (§4–5, §7):** Vitest setup → Task 1. Types → Task 2. `pivotTrend`/`scalePoints` (unit-tested) → Task 3. `Bars`/`LineChart`/`AlertsTable`/`RangeSelector` → Task 4. AI Usage tab (trend/top apps/top employees) → Task 5. Insider Risk tab (risk + alerts timelines, top risky employees/departments, severity bars, weights legend, review table) → Task 6. Tabs in both dashboards + scope prop + dept hides Top Departments → Tasks 5–7. Name field → Task 8. Extension copy → Task 9. Manual acceptance → Task 10.

**Placeholder scan:** every code step is complete; every run step has a command + expected result. No TBD/TODO.

**Type consistency:** `AnalyticsSummary` fields (`usage_trend`, `alerts_timeline`, `risk_timeline`, `top_apps`, `top_employees`, `top_departments`, `alerts_by_severity`, `totals`) defined in Task 2 match the backend plan's return keys and are consumed in Tasks 5/6. `pivotTrend`/`scalePoints` signatures in Task 3 match their use in Task 4 (`charts.tsx`) and Task 5 (`AiUsage`). `Bars` takes `{label, value}` rows — every call site (Tasks 5/6) maps to that shape (note: this differs from the old `Usage.tsx` `Bars`, which took `{label, events}`; the old component is deleted in Task 7, so there is no clash). `AlertRow` fields match the backend `analytics_alerts` row shape. `TokenRow.name` (Task 2) is read in Task 8.

**Ordering:** Task 7 deletes `Usage.tsx` only after Tasks 4–6 provide its replacements; `main.tsx` stops importing `Usage` in the same task, so the first fully-green console build is Task 7 Step 4.
