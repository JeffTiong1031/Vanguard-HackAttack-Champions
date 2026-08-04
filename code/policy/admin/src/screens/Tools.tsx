import { useEffect, useState } from 'preact/hooks';
import { api, UnauthorisedError, type Tool } from '../api';
import { ShieldIcon, SearchIcon, CheckCircleIcon, XCircleIcon } from '../icons';
import { StatCard } from './charts';

export function Tools() {
  const [tools, setTools] = useState<Tool[]>([]);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<'all' | 'approved' | 'blocked'>('all');

  async function load() {
    try {
      setTools(await api.get<Tool[]>('/v1/admin/tools'));
      setError('');
    } catch (err) {
      if (err instanceof UnauthorisedError) throw err;
      setError(err instanceof Error ? err.message : 'Could not load tools.');
    }
  }

  useEffect(() => { void load(); }, []);

  async function toggle(tool: Tool) {
    setBusy(tool.llm_id);
    setError('');
    try {
      const status = tool.status === 'approved' ? 'blocked' : 'approved';
      await api.post(`/v1/admin/tools/${tool.llm_id}`, { status });
      await load();
    } catch (err) {
      if (err instanceof UnauthorisedError) throw err;
      setError(err instanceof Error ? err.message : 'Could not update the tool.');
    } finally {
      setBusy('');
    }
  }

  const approved = tools.filter((t) => t.status === 'approved');
  const blocked = tools.filter((t) => t.status === 'blocked');

  const filteredTools = tools.filter((t) => {
    if (filter !== 'all' && t.status !== filter) return false;
    if (search.trim()) {
      const q = search.toLowerCase();
      return t.display_name.toLowerCase().includes(q) || t.host.toLowerCase().includes(q);
    }
    return true;
  });

  return (
    <div>
      {/* Top Stat Cards Grid */}
      <div class="kpi-grid">
        <StatCard
          label="Total Monitored AI Tools"
          value={tools.length.toLocaleString()}
          sub="Configured AI application hosts"
          icon={ShieldIcon}
          color="indigo"
        />
        <StatCard
          label="Approved AI Tools"
          value={approved.length.toLocaleString()}
          sub="Unrestricted policy access"
          icon={CheckCircleIcon}
          color="emerald"
        />
        <StatCard
          label="Restricted / Blocked"
          value={blocked.length.toLocaleString()}
          sub="Requires access approval"
          icon={XCircleIcon}
          color="rose"
        />
      </div>

      <div class="panel">
        <div class="panel-head">
          <span class="ico"><ShieldIcon /></span>
          <div>
            <h2>Global AI Tool Policy Matrix</h2>
            <p class="sub">Configure company-wide defaults. Approved tools execute seamlessly; blocked tools display governance notices.</p>
          </div>
          <span class="tag count">{tools.length} Managed Tools</span>
        </div>

        {error && <p class="error">{error}</p>}

        <div class="toolbar">
          <div class="filter-group">
            <button class={`filter-btn ${filter === 'all' ? 'active' : ''}`} onClick={() => setFilter('all')}>
              All ({tools.length})
            </button>
            <button class={`filter-btn ${filter === 'approved' ? 'active' : ''}`} onClick={() => setFilter('approved')}>
              Approved ({approved.length})
            </button>
            <button class={`filter-btn ${filter === 'blocked' ? 'active' : ''}`} onClick={() => setFilter('blocked')}>
              Blocked ({blocked.length})
            </button>
          </div>

          <div class="search-box">
            <SearchIcon />
            <input
              type="text"
              placeholder="Search tool name or domain…"
              value={search}
              onInput={(e) => setSearch((e.target as HTMLInputElement).value)}
            />
          </div>
        </div>

        {filteredTools.length === 0 && (
          <p class="empty">No AI tools match your current filter.</p>
        )}

        {filteredTools.length > 0 && (
          <div key={filter} class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Application Name</th>
                  <th>Domain Host</th>
                  <th>Global Policy Status</th>
                  <th style="text-align:right">Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredTools.map((t) => (
                  <tr key={t.llm_id}>
                    <td><span class="name">{t.display_name}</span></td>
                    <td><code>{t.host}</code></td>
                    <td><span class={`pill ${t.status}`}>{t.status}</span></td>
                    <td style="text-align:right">
                      <button
                        class={`btn-sm ${t.status === 'approved' ? 'btn-danger' : 'btn-primary'}`}
                        disabled={busy === t.llm_id}
                        onClick={() => toggle(t)}
                      >
                        {t.status === 'approved' ? 'Block Access' : 'Approve Access'}
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
