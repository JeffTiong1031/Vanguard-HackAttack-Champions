import { useEffect, useRef, useState } from 'preact/hooks';
import { api, UnauthorisedError, type RequestRow, type Scope } from '../api';
import { InboxIcon } from '../icons';

export function Requests({ scope }: { scope: Scope }) {
  const base = scope === 'company' ? '/v1/admin/requests' : '/v1/dept/requests';
  const readOnly = scope === 'company';
  const [rows, setRows] = useState<RequestRow[]>([]);
  const [busyId, setBusyId] = useState('');
  const [error, setError] = useState('');
  const [notes, setNotes] = useState<Record<string, string>>({});
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

  async function decide(id: string, decision: 'approved' | 'blocked') {
    setBusyId(id); setError('');
    try {
      await api.post(`${base}/${id}`, decision === 'blocked'
        ? { decision, reason_code: 'policy_requirement_not_met', note: notes[id]?.trim() }
        : { decision });
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
            : 'Employees request a blocked tool. Access stays blocked until you commit Approved.'}</p>
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
                    <div style="display:flex;flex-direction:column;gap:6px;align-items:flex-end">
                      <input placeholder="Required explanation when blocked"
                        value={notes[r.id] ?? ''}
                        onInput={(e) => setNotes({ ...notes, [r.id]: (e.target as HTMLInputElement).value })}
                        style="width:220px;padding:6px 8px;border:1px solid #cbd5e1;border-radius:6px;font-size:12.5px" />
                      <div class="row-actions">
                        <button class="btn-primary btn-sm" disabled={busyId === r.id} onClick={() => decide(r.id, 'approved')}>Approve</button>
                        <button class="btn-danger btn-sm" disabled={busyId === r.id || !notes[r.id]?.trim()} onClick={() => decide(r.id, 'blocked')}>Keep blocked</button>
                      </div>
                    </div>
                  ) : (
                    <div><span class={`pill ${r.access_state}`}>{r.access_state}</span>
                      {r.status === 'pending' && <div style="font-size:12px;color:#64748b;margin-top:4px">Review in progress</div>}
                      {r.admin_note && <div style="font-size:12px;color:#475569;margin-top:4px">{r.admin_note}</div>}
                    </div>
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
