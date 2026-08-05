import { useEffect, useState } from 'preact/hooks';
import { api, UnauthorisedError, type TokenRow } from '../api';
import { KeyIcon, CheckCircleIcon, XCircleIcon } from '../icons';
import { StatCard } from './charts';

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

  const activeTokens = rows.filter((r) => !r.revoked);
  const revokedTokens = rows.filter((r) => r.revoked);

  return (
    <div>
      {/* Top Stat Cards Grid */}
      <div class="kpi-grid">
        <StatCard
          label="Active Tokens"
          value={activeTokens.length.toLocaleString()}
          sub="Valid for employee enrolment"
          icon={CheckCircleIcon}
          color="emerald"
        />
        <StatCard
          label="Revoked Tokens"
          value={revokedTokens.length.toLocaleString()}
          sub="Disabled for new enrolments"
          icon={XCircleIcon}
          color="crimson"
        />
        <StatCard
          label="Total Minted"
          value={rows.length.toLocaleString()}
          sub="Issued department tokens"
          icon={KeyIcon}
          color="indigo"
        />
      </div>

      <div class="panel">
        <div class="panel-head">
          <span class="ico"><KeyIcon /></span>
          <div>
            <h2>Employee Enrolment Tokens</h2>
            <p class="sub">Mint individual tokens for employees to connect their Vanguard extension to this department.</p>
          </div>
          <span class="tag count">{activeTokens.length} Active</span>
        </div>

        <div class="field" style="margin-bottom:16px">
          <input
            value={name}
            placeholder="Employee name or ID (e.g. Alice Chen / ENG-402)…"
            onInput={(e) => setName((e.target as HTMLInputElement).value)}
          />
          <button class="btn-primary" disabled={busy === 'mint'} onClick={mint}>
            + Mint Employee Token
          </button>
        </div>

        {error && <p class="error">{error}</p>}

        {minted && (
          <div class="mint-result" role="status" aria-live="polite">
            <strong>Token Minted — Copy immediately (it will not be shown again):</strong>
            <code>{minted}</code>
          </div>
        )}

        <p class="hint">
          <strong>Note on Revocation:</strong> Revoking a token prevents it from being used for <em>new</em> extension enrolments. Existing enrolled extensions remain active.
        </p>

        {rows.length === 0 && <p class="empty">No employee tokens minted yet.</p>}

        {rows.length > 0 && (
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Employee Name</th>
                  <th>Department</th>
                  <th>Minted Date</th>
                  <th>Token Status</th>
                  <th style="text-align:right">Action</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>{row.name ? <span class="name">{row.name}</span> : <span style="color:var(--ink-4)">—</span>}</td>
                    <td>{row.department}</td>
                    <td><code>{new Date(row.created_at).toLocaleString()}</code></td>
                    <td>
                      <span class={`pill ${row.revoked ? 'revoked' : 'active'}`}>
                        {row.revoked ? 'Revoked' : 'Active'}
                      </span>
                    </td>
                    <td style="text-align:right">
                      {!row.revoked && (
                        <button class="btn-danger btn-sm" disabled={busy === row.id} onClick={() => revoke(row.id)}>
                          Revoke Token
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
