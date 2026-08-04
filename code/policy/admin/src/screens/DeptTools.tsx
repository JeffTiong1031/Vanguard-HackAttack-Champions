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
