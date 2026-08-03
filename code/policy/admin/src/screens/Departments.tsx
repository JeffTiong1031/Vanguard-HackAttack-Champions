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
