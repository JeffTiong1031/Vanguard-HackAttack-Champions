import { useEffect, useRef, useState } from 'preact/hooks';
import { api, UnauthorisedError, type AppealRow, type Scope } from '../api';
import { GavelIcon, SearchIcon, AlertTriangleIcon, CheckCircleIcon, XCircleIcon } from '../icons';
import { StatCard } from './charts';

export function Reviews({ scope }: { scope: Scope }) {
  const base = scope === 'company' ? '/v1/admin/appeals' : '/v1/dept/appeals';
  const readOnly = scope === 'company';
  const [rows, setRows] = useState<AppealRow[]>([]);
  const [busyId, setBusyId] = useState('');
  const [error, setError] = useState('');
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [filter, setFilter] = useState<'all' | 'pending' | 'approved' | 'blocked'>('all');
  const [search, setSearch] = useState('');
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
  const approved = rows.filter((r) => r.status === 'approved');
  const blocked = rows.filter((r) => r.status === 'blocked');

  const filteredRows = rows.filter((r) => {
    if (filter !== 'all' && r.status !== filter) return false;
    if (search.trim()) {
      const q = search.toLowerCase();
      return (
        r.department.toLowerCase().includes(q) ||
        r.decision_type.toLowerCase().includes(q) ||
        r.category.toLowerCase().includes(q) ||
        (r.employee_reason && r.employee_reason.toLowerCase().includes(q))
      );
    }
    return true;
  });

  return (
    <div>
      {/* Top Stat Cards Grid */}
      <div class="kpi-grid">
        <StatCard
          label="Pending Audits"
          value={pending.length.toLocaleString()}
          sub="Awaiting review decision"
          icon={AlertTriangleIcon}
          color="orange"
        />
        <StatCard
          label="Approved Appeals"
          value={approved.length.toLocaleString()}
          sub="Redaction/block waived"
          icon={CheckCircleIcon}
          color="emerald"
        />
        <StatCard
          label="Maintained Blocks"
          value={blocked.length.toLocaleString()}
          sub="Policy decision upheld"
          icon={XCircleIcon}
          color="crimson"
        />
        <StatCard
          label="Total Contested Appeals"
          value={rows.length.toLocaleString()}
          sub="All prompt reviews"
          icon={GavelIcon}
          color="indigo"
        />
      </div>

      <div class="panel">
        <div class="panel-head">
          <span class="ico"><GavelIcon /></span>
          <div>
            <h2>Prompt Audit Reviews & Appeals</h2>
            <p class="sub">Review employee appeals contesting automated policy blocks or PII redactions.</p>
          </div>
          <span class="tag count">{pending.length} pending review</span>
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
              placeholder="Search category or department…"
              value={search}
              onInput={(e) => setSearch((e.target as HTMLInputElement).value)}
            />
          </div>
        </div>

        {filteredRows.length === 0 && (
          <p class="empty">{rows.length === 0 ? 'No review requests submitted yet.' : 'No audit entries match your search filter.'}</p>
        )}

        {filteredRows.length > 0 && (
          <div key={filter} class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Decision Type</th>
                  <th>Category</th>
                  <th>Department</th>
                  <th>Employee Explanation</th>
                  <th>Disclosed Sample</th>
                  <th style="text-align:right">Review Resolution</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((r) => (
                  <tr key={r.id}>
                    <td><span class="name">{r.decision_type}</span></td>
                    <td><code>{r.category}</code></td>
                    <td>{r.department}</td>
                    <td>{r.employee_reason}</td>
                    <td>
                      {r.disclosed_text ? (
                        <code title="Employee disclosed snippet">{r.disclosed_text}</code>
                      ) : (
                        <span style="color:var(--ink-4);font-size:12px">Not disclosed</span>
                      )}
                    </td>
                    <td style="text-align:right">
                      {r.status === 'pending' && !readOnly ? (
                        <div style="display:flex;flex-direction:column;gap:8px;align-items:flex-end">
                          <input
                            placeholder="Explanation required when blocked"
                            value={notes[r.id] ?? ''}
                            onInput={(e) => setNotes({ ...notes, [r.id]: (e.target as HTMLInputElement).value })}
                            style="width:230px;padding:6px 10px;font-size:12.5px"
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
                          {r.admin_note && <div style="font-size:12px;color:var(--ink-3);margin-top:4px">“{r.admin_note}”</div>}
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
