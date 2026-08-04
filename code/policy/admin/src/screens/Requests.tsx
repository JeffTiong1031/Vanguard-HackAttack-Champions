import { useEffect, useRef, useState } from 'preact/hooks';
import { api, UnauthorisedError, type RequestRow, type Scope } from '../api';
import { InboxIcon, SearchIcon, CheckCircleIcon, XCircleIcon, AlertTriangleIcon } from '../icons';
import { StatCard } from './charts';

export function Requests({ scope }: { scope: Scope }) {
  const base = scope === 'company' ? '/v1/admin/requests' : '/v1/dept/requests';
  const readOnly = scope === 'company';
  const [rows, setRows] = useState<RequestRow[]>([]);
  const [busyId, setBusyId] = useState('');
  const [error, setError] = useState('');
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [filter, setFilter] = useState<'all' | 'pending' | 'approved' | 'blocked'>('all');
  const [search, setSearch] = useState('');
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
  const approved = rows.filter((r) => r.status === 'approved');
  const blocked = rows.filter((r) => r.status === 'blocked');

  const filteredRows = rows.filter((r) => {
    if (filter !== 'all' && r.status !== filter) return false;
    if (search.trim()) {
      const q = search.toLowerCase();
      return (
        r.department.toLowerCase().includes(q) ||
        r.display_name.toLowerCase().includes(q) ||
        (r.reason && r.reason.toLowerCase().includes(q))
      );
    }
    return true;
  });

  return (
    <div>
      {/* Top Stat Cards */}
      <div class="kpi-grid">
        <StatCard
          label="Pending Requests"
          value={pending.length.toLocaleString()}
          sub="Awaiting admin approval"
          icon={AlertTriangleIcon}
          color="orange"
        />
        <StatCard
          label="Approved Tools"
          value={approved.length.toLocaleString()}
          sub="Granted access requests"
          icon={CheckCircleIcon}
          color="emerald"
        />
        <StatCard
          label="Blocked Requests"
          value={blocked.length.toLocaleString()}
          sub="Access declined/blocked"
          icon={XCircleIcon}
          color="crimson"
        />
        <StatCard
          label="Total Request Volume"
          value={rows.length.toLocaleString()}
          sub="All submissions"
          icon={InboxIcon}
          color="indigo"
        />
      </div>

      <div class="panel">
        <div class="panel-head">
          <span class="ico"><InboxIcon /></span>
          <div>
            <h2>Tool Access Requests</h2>
            <p class="sub">{readOnly
              ? 'Every department’s tool unblock requests across the company (read-only view).'
              : 'Review employees requesting unblocked access to restricted AI tools.'}</p>
          </div>
          <span class="tag count">{pending.length} pending action</span>
        </div>

        {error && <p class="error">{error}</p>}

        <div class="toolbar">
          <div class="filter-group">
            <button class={`filter-btn ${filter === 'all' ? 'active' : ''}`} onClick={() => setFilter('all')}>
              All ({rows.length})
            </button>
            <button class={`filter-btn ${filter === 'pending' ? 'active' : ''}`} onClick={() => setFilter('pending')}>
              Pending ({pending.length})
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
              placeholder="Search tool or department…"
              value={search}
              onInput={(e) => setSearch((e.target as HTMLInputElement).value)}
            />
          </div>
        </div>

        {filteredRows.length === 0 && (
          <p class="empty">{rows.length === 0 ? 'No access requests raised yet.' : 'No requests match your current filter.'}</p>
        )}

        {filteredRows.length > 0 && (
          <div key={filter} class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Department</th>
                  <th>Requested Tool</th>
                  <th>Justification / Reason</th>
                  <th>Raised Time</th>
                  <th style="text-align:right">Status / Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((r) => (
                  <tr key={r.id}>
                    <td><span class="name">{r.department}</span></td>
                    <td><strong>{r.display_name}</strong></td>
                    <td>{r.reason}</td>
                    <td><code>{new Date(r.created_at).toLocaleTimeString()}</code></td>
                    <td style="text-align:right">
                      {r.status === 'pending' && !readOnly ? (
                        <div style="display:flex;flex-direction:column;gap:6px;align-items:flex-end">
                          <input
                            placeholder="Explanation required when blocked"
                            value={notes[r.id] ?? ''}
                            onInput={(e) => setNotes({ ...notes, [r.id]: (e.target as HTMLInputElement).value })}
                            style="width:220px;padding:6px 8px;border:1px solid var(--line);border-radius:var(--r-md);font-size:12.5px"
                          />
                          <div class="row-actions">
                            <button class="btn-success btn-sm" disabled={busyId === r.id} onClick={() => decide(r.id, 'approved')}>
                              Approve
                            </button>
                            <button class="btn-danger btn-sm" disabled={busyId === r.id || !notes[r.id]?.trim()} onClick={() => decide(r.id, 'blocked')}>
                              Keep blocked
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div>
                          <span class={`pill ${r.status}`}>{r.status}</span>
                          {r.admin_note && <div style="font-size:12px;color:var(--ink-3);margin-top:4px">{r.admin_note}</div>}
                        </div>
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
