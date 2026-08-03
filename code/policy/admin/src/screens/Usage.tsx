import { useEffect, useState } from 'preact/hooks';
import { api, UnauthorisedError, type Usage as UsageData, type Scope } from '../api';
import { BarIcon } from '../icons';

function Bars({ title, rows }: { title: string; rows: { label: string; events: number }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.events));
  return (
    <div class="bars-group">
      <h3>{title}</h3>
      {rows.length === 0 && <p class="empty">No events yet.</p>}
      {rows.map((r) => (
        <div class="bar-row" key={r.label}>
          <span class="lbl">{r.label}</span>
          <span class="bar-track">
            <span class="bar-fill" style={`width:${Math.max(4, (r.events / max) * 100)}%`} />
          </span>
          <span class="val">{r.events}</span>
        </div>
      ))}
    </div>
  );
}

export function Usage({ scope }: { scope: Scope }) {
  const url = scope === 'company' ? '/v1/admin/usage' : '/v1/dept/usage';
  const [data, setData] = useState<UsageData | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    async function load() {
      try {
        const d = await api.get<UsageData>(url);
        setData(d);
        setError('');
      } catch (err) {
        // Let the shell handle session expiry -- swallowing it here would
        // break the unhandledrejection-driven 401 bounce in main.tsx.
        if (err instanceof UnauthorisedError) throw err;
        setError(err instanceof Error ? err.message : 'Could not load usage data.');
      }
    }
    void load();
    const timer = setInterval(() => { void load(); }, 3000); // (estimate)
    return () => clearInterval(timer);
  }, [url]);

  if (!data) return (
    <section class="panel"><p class="empty">{error || 'Loading…'}</p></section>
  );

  return (
    <section class="panel">
      <div class="panel-head">
        <span class="ico"><BarIcon /></span>
        <div>
          <h2>AI Usage</h2>
          <p class="sub">Events carry a class, a count, and a salted hash — never prompt text.</p>
        </div>
        <span class="tag">Class · Count · Hash</span>
      </div>
      {error && <p class="error">{error}</p>}
      <Bars title="By department"
            rows={data.by_department.map((r) => ({ label: r.department, events: r.events }))} />
      <Bars title="By tool"
            rows={data.by_tool.map((r) => ({ label: r.host, events: r.events }))} />
      <Bars title="By policy category"
            rows={data.by_category.map((r) => ({ label: r.category, events: r.events }))} />
    </section>
  );
}
