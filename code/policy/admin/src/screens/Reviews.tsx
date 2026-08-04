import { useEffect, useRef, useState } from 'preact/hooks';
import { api, UnauthorisedError, type AppealRow, type Scope } from '../api';
import { GavelIcon } from '../icons';

export function Reviews({ scope }: { scope: Scope }) {
  const base = scope === 'company' ? '/v1/admin/appeals' : '/v1/dept/appeals';
  const readOnly = scope === 'company';
  const [rows, setRows] = useState<AppealRow[]>([]);
  const [busyId, setBusyId] = useState('');
  const [error, setError] = useState('');
  const [notes, setNotes] = useState<Record<string, string>>({});
  const seq = useRef(0);

  async function load() {
    const mine = ++seq.current;
    try {
      const data = await api.get<AppealRow[]>(base);
      if (mine !== seq.current) return;
      setRows(data); setError('');
    } catch (err) {
      if (err instanceof UnauthorisedError) throw err;
      setError(err instanceof Error ? err.message : 'Could not load reviews.');
    }
  }

  useEffect(() => {
    void load();
    const t = setInterval(() => { void load(); }, 3000);
    return () => clearInterval(t);
  }, [base]);

  async function decide(id: string, decision: 'approved' | 'blocked') {
    setBusyId(id); setError('');
    try {
      await api.post(`${base}/${id}`, decision === 'blocked'
        ? { decision, reason_code: 'policy_requirement_not_met', note: notes[id]?.trim() }
        : { decision, note: notes[id]?.trim() || undefined });
      await load();
    } catch (err) {
      if (err instanceof UnauthorisedError) throw err;
      setError(err instanceof Error ? err.message : 'Could not update the review.');
    } finally { setBusyId(''); }
  }

  const pending = rows.filter((r) => r.status === 'pending');

  return (
    <section class="panel">
      <div class="panel-head">
        <span class="ico"><GavelIcon /></span>
        <div>
          <h2>Reviews</h2>
          <p class="sub">Employees contesting an automated block. Commit one final access state: Approved or Blocked.</p>
        </div>
        <span class="tag count">{pending.length} pending</span>
      </div>
      {error && <p class="error">{error}</p>}
      {rows.length === 0 && <p class="empty">No review requests yet.</p>}
      {rows.length > 0 && (
        <table>
          <thead><tr><th>Type</th><th>Category</th><th>Dept</th><th>Employee's reason</th><th>Shared text</th><th></th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td><span class="name">{r.decision_type}</span></td>
                <td><code>{r.category}</code></td>
                <td>{r.department}</td>
                <td>{r.employee_reason}</td>
                <td>{r.disclosed_text
                  ? <code title="the employee chose to share this">{r.disclosed_text}</code>
                  : <span style="color:#94a3b8">not shared</span>}</td>
                <td>
                  {r.status === 'pending' && !readOnly ? (
                    <div style="display:flex;flex-direction:column;gap:6px;align-items:flex-end">
                      <input
                        placeholder="Explanation required when blocked"
                        value={notes[r.id] ?? ''}
                        onInput={(e) => setNotes({ ...notes, [r.id]: (e.target as HTMLInputElement).value })}
                        style="width:200px;padding:6px 8px;border:1px solid #cbd5e1;border-radius:6px;font-size:12.5px"
                      />
                      <div class="row-actions">
                        <button class="btn-danger btn-sm" disabled={busyId === r.id || !notes[r.id]?.trim()} onClick={() => decide(r.id, 'blocked')}>Keep blocked</button>
                        <button class="btn-primary btn-sm" disabled={busyId === r.id} onClick={() => decide(r.id, 'approved')}>Approve</button>
                      </div>
                    </div>
                  ) : (
                    <div>
                      <span class={`pill ${r.access_state}`}>{r.access_state}</span>
                      {r.status === 'pending' && <div style="font-size:12px;color:#64748b;margin-top:4px">Review in progress</div>}
                      {r.admin_note && <div style="font-size:12px;color:#475569;margin-top:4px">“{r.admin_note}”</div>}
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
