import { useEffect, useState } from 'preact/hooks';
import { api, UnauthorisedError, type Tool } from '../api';
import { ShieldIcon, SearchIcon, CheckCircleIcon, XCircleIcon } from '../icons';
import { StatCard } from './charts';

export function DeptTools() {
  const [rows, setRows] = useState<Tool[]>([]);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');

  useEffect(() => {
    async function load() {
      try { setRows(await api.get<Tool[]>('/v1/dept/tools')); setError(''); }
      catch (err) { if (err instanceof UnauthorisedError) throw err; setError(err instanceof Error ? err.message : 'Could not load tools.'); }
    }
    void load();
    const t = setInterval(() => { void load(); }, 3000);
    return () => clearInterval(t);
  }, []);

  const approved = rows.filter((t) => t.status === 'approved');
  const blocked = rows.filter((t) => t.status === 'blocked');

  const filtered = rows.filter((t) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return t.display_name.toLowerCase().includes(q) || t.host.toLowerCase().includes(q);
  });

  return (
    <div>
      {/* Top Stat Cards Grid */}
      <div class="kpi-grid">
        <StatCard
          label="Department Monitored Tools"
          value={rows.length.toLocaleString()}
          sub="Active tool registry"
          icon={ShieldIcon}
          color="indigo"
        />
        <StatCard
          label="Approved for Department"
          value={approved.length.toLocaleString()}
          sub="Company default & granted requests"
          icon={CheckCircleIcon}
          color="emerald"
        />
        <StatCard
          label="Restricted Tools"
          value={blocked.length.toLocaleString()}
          sub="Access request required"
          icon={XCircleIcon}
          color="crimson"
        />
      </div>

      <div class="panel">
        <div class="panel-head">
          <span class="ico"><ShieldIcon /></span>
          <div>
            <h2>Department AI Tools Status</h2>
            <p class="sub">Effective status for this department (combines company defaults and approved access requests).</p>
          </div>
          <span class="tag count">{rows.length} Registered</span>
        </div>

        {error && <p class="error">{error}</p>}

        <div class="toolbar">
          <div class="search-box">
            <SearchIcon />
            <input
              type="text"
              placeholder="Search tool or domain host…"
              value={search}
              onInput={(e) => setSearch((e.target as HTMLInputElement).value)}
            />
          </div>
        </div>

        {filtered.length === 0 && (
          <p class="empty">{rows.length === 0 ? 'Loading tools registry…' : 'No tools match search criteria.'}</p>
        )}

        {filtered.length > 0 && (
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Application Name</th>
                  <th>Domain Host</th>
                  <th>Department Status</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((t) => (
                  <tr key={t.llm_id}>
                    <td><span class="name">{t.display_name}</span></td>
                    <td><code>{t.host}</code></td>
                    <td><span class={`pill ${t.status === 'approved' ? 'approved' : 'blocked'}`}>{t.status}</span></td>
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
