import { useEffect, useState } from 'preact/hooks';
import { api, UnauthorisedError, type Department } from '../api';
import { KeyIcon, BuildingIcon, UsersIcon, ShieldIcon } from '../icons';
import { StatCard } from './charts';

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

  const totalTokens = rows.reduce((acc, d) => acc + (d.active_tokens || 0), 0);

  return (
    <div>
      {/* Top Stat Cards */}
      <div class="kpi-grid">
        <StatCard
          label="Total Departments"
          value={rows.length.toLocaleString()}
          sub="Configured organizational units"
          icon={BuildingIcon}
          color="indigo"
        />
        <StatCard
          label="Active Tokens Total"
          value={totalTokens.toLocaleString()}
          sub="Issued department employee tokens"
          icon={UsersIcon}
          color="emerald"
        />
        <StatCard
          label="Department Secrets"
          value={rows.length.toLocaleString()}
          sub="Department Admin credentials"
          icon={KeyIcon}
          color="purple"
        />
      </div>

      <div class="panel">
        <div class="panel-head">
          <span class="ico"><BuildingIcon /></span>
          <div>
            <h2>Department Governance & Secret Provisioning</h2>
            <p class="sub">Provision departments and manage admin access secrets for delegated department control.</p>
          </div>
          <span class="tag count">{rows.length} Active Units</span>
        </div>

        <div class="field" style="margin-bottom:20px">
          <input
            value={name}
            placeholder="Department name (e.g. Finance, Product Engineering, HR)…"
            onInput={(e) => setName((e.target as HTMLInputElement).value)}
          />
          <button class="btn-primary" disabled={busy === 'create' || !name.trim()} onClick={create}>
            + Provision Department
          </button>
        </div>

        {error && <p class="error">{error}</p>}

        {minted && (
          <div class="mint-result">
            <strong>Secret Provisioned for {minted.name} — Copy immediately (shown only once):</strong>
            <code>{minted.secret}</code>
          </div>
        )}

        {rows.length === 0 && <p class="empty">No departments created yet.</p>}

        {rows.length > 0 && (
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Department Name</th>
                  <th>Date Provisioned</th>
                  <th>Active Tokens</th>
                  <th style="text-align:right">Action</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((d) => (
                  <tr key={d.id}>
                    <td><span class="name">{d.name}</span></td>
                    <td><code>{new Date(d.created_at).toLocaleString()}</code></td>
                    <td><span class="pill active">{d.active_tokens} tokens</span></td>
                    <td style="text-align:right">
                      <button class="btn-ghost btn-sm" disabled={busy === d.id} onClick={() => regenerate(d.id, d.name)}>
                        Regenerate Secret
                      </button>
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
