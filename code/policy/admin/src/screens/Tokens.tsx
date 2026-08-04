import { useEffect, useState } from 'preact/hooks';
import { api, UnauthorisedError, type TokenRow } from '../api';
import { KeyIcon } from '../icons';

export function Tokens() {
  const [rows, setRows] = useState<TokenRow[]>([]);
  const [minted, setMinted] = useState('');
  const [name, setName] = useState('');
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
      const r = await api.post<{ token: string }>('/v1/dept/tokens', { name: name.trim() });
      setMinted(r.token);
      setName('');
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
        <input value={name} placeholder="Employee name (optional)"
               onInput={(e) => setName((e.target as HTMLInputElement).value)} />
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
          <thead><tr><th>Name</th><th>Department</th><th>Created</th><th>State</th><th></th></tr></thead>
          <tbody>
            {rows.map((row) => (
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
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
