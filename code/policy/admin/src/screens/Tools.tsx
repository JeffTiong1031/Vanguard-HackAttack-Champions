import { useEffect, useState } from 'preact/hooks';
import { api, UnauthorisedError, type Tool } from '../api';
import { ShieldIcon, SearchIcon, CheckCircleIcon, XCircleIcon, PlusIcon, EditIcon } from '../icons';
import { StatCard } from './charts';

export function Tools() {
  const [tools, setTools] = useState<Tool[]>([]);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<'all' | 'approved' | 'blocked'>('all');

  // Add Tool Modal state
  const [showAddModal, setShowAddModal] = useState(false);
  const [addHost, setAddHost] = useState('');
  const [addDisplayName, setAddDisplayName] = useState('');
  const [addStatus, setAddStatus] = useState<'approved' | 'blocked'>('approved');
  const [addAccessMode, setAddAccessMode] = useState<'standard' | 'strict_redaction' | 'no_file_uploads'>('standard');
  const [addError, setAddError] = useState('');
  const [adding, setAdding] = useState(false);

  // Edit Row state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editHost, setEditHost] = useState('');
  const [editDisplayName, setEditDisplayName] = useState('');
  const [editStatus, setEditStatus] = useState<'approved' | 'blocked' | 'temporary' | 'trial' | 'conditional'>('approved');
  const [editAccessMode, setEditAccessMode] = useState<'standard' | 'strict_redaction' | 'no_file_uploads'>('standard');
  const [savingEdit, setSavingEdit] = useState(false);

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

  async function handleAddTool(e: Event) {
    e.preventDefault();
    if (!addHost.trim() || !addDisplayName.trim()) {
      setAddError('Domain host and Display name are required.');
      return;
    }
    setAdding(true);
    setAddError('');
    try {
      await api.post('/v1/admin/tools', {
        host: addHost.trim(),
        display_name: addDisplayName.trim(),
        status: addStatus,
        access_mode: addAccessMode,
      });
      setShowAddModal(false);
      setAddHost('');
      setAddDisplayName('');
      setAddStatus('approved');
      setAddAccessMode('standard');
      await load();
    } catch (err) {
      if (err instanceof UnauthorisedError) throw err;
      setAddError(err instanceof Error ? err.message : 'Failed to add tool.');
    } finally {
      setAdding(false);
    }
  }

  function startEdit(t: Tool) {
    setEditingId(t.llm_id);
    setEditHost(t.host);
    setEditDisplayName(t.display_name);
    setEditStatus(t.status);
    setEditAccessMode(t.access_mode || 'standard');
    setError('');
  }

  function cancelEdit() {
    setEditingId(null);
  }

  async function saveEdit(llm_id: string) {
    if (!editHost.trim() || !editDisplayName.trim()) {
      setError('Domain host and Display name cannot be empty.');
      return;
    }
    setSavingEdit(true);
    setError('');
    try {
      await api.put(`/v1/admin/tools/${llm_id}`, {
        host: editHost.trim(),
        display_name: editDisplayName.trim(),
        status: editStatus,
        access_mode: editAccessMode,
      });
      setEditingId(null);
      await load();
    } catch (err) {
      if (err instanceof UnauthorisedError) throw err;
      setError(err instanceof Error ? err.message : 'Could not update tool details.');
    } finally {
      setSavingEdit(false);
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
          <div style="display:flex; gap:10px; align-items:center; margin-left:auto;">
            <button class="btn-primary btn-sm" onClick={() => setShowAddModal(true)} style="display:flex; align-items:center; gap:6px;">
              <PlusIcon style="width:14px; height:14px;" /> Add AI Tool
            </button>
            <span class="tag count">{tools.length} Managed Tools</span>
          </div>
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
                  <th>Access Mode</th>
                  <th style="text-align:right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredTools.map((t) => {
                  const isEditing = editingId === t.llm_id;
                  return (
                    <tr key={t.llm_id}>
                      <td>
                        {isEditing ? (
                          <input
                            type="text"
                            class="input-inline"
                            value={editDisplayName}
                            onInput={(e) => setEditDisplayName((e.target as HTMLInputElement).value)}
                          />
                        ) : (
                          <span class="name">{t.display_name}</span>
                        )}
                      </td>
                      <td>
                        {isEditing ? (
                          <input
                            type="text"
                            class="input-inline"
                            value={editHost}
                            onInput={(e) => setEditHost((e.target as HTMLInputElement).value)}
                          />
                        ) : (
                          <code>{t.host}</code>
                        )}
                      </td>
                      <td>
                        {isEditing ? (
                          <select
                            class="select-inline"
                            value={editStatus}
                            onChange={(e) => setEditStatus((e.target as any).value)}
                          >
                            <option value="approved">Approved</option>
                            <option value="blocked">Blocked</option>
                            <option value="temporary">Temporary</option>
                            <option value="trial">Trial</option>
                            <option value="conditional">Conditional</option>
                          </select>
                        ) : (
                          <span class={`pill ${t.status}`}>{t.status}</span>
                        )}
                      </td>
                      <td>
                        {isEditing ? (
                          <select
                            class="select-inline"
                            value={editAccessMode}
                            onChange={(e) => setEditAccessMode((e.target as any).value)}
                          >
                            <option value="standard">Standard</option>
                            <option value="strict_redaction">Strict Redaction</option>
                            <option value="no_file_uploads">No File Uploads</option>
                          </select>
                        ) : (
                          <span class="tag">{t.access_mode || 'standard'}</span>
                        )}
                      </td>
                      <td style="text-align:right">
                        <div class="action-cell">
                          {isEditing ? (
                            <>
                              <button
                                class="btn-sm btn-primary"
                                disabled={savingEdit}
                                onClick={() => saveEdit(t.llm_id)}
                              >
                                Save
                              </button>
                              <button
                                class="btn-sm btn-ghost"
                                disabled={savingEdit}
                                onClick={cancelEdit}
                              >
                                Cancel
                              </button>
                            </>
                          ) : (
                            <>
                              <button
                                class="btn-sm btn-ghost"
                                disabled={busy === t.llm_id}
                                onClick={() => startEdit(t)}
                                title="Edit tool details & policy"
                                style="display:inline-flex; align-items:center; gap:4px;"
                              >
                                <EditIcon style="width:13px; height:13px;" /> Edit
                              </button>
                              <button
                                class={`btn-sm ${t.status === 'approved' ? 'btn-danger' : 'btn-primary'}`}
                                disabled={busy === t.llm_id}
                                onClick={() => toggle(t)}
                              >
                                {t.status === 'approved' ? 'Block Access' : 'Approve Access'}
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add New Tool Modal */}
      {showAddModal && (
        <div class="modal-overlay" onClick={() => setShowAddModal(false)}>
          <div class="modal-card" onClick={(e) => e.stopPropagation()}>
            <div class="modal-head">
              <h3>Add New AI Application / Tool</h3>
              <button class="btn-ghost btn-sm" onClick={() => setShowAddModal(false)}>✕</button>
            </div>
            <form onSubmit={handleAddTool}>
              <div class="modal-body">
                {addError && <p class="error">{addError}</p>}
                
                <div class="form-group">
                  <label>Domain Host Name</label>
                  <p class="sub">The host domain of the AI application (e.g. <code>kimi.moonshot.cn</code> or <code>poe.com</code>)</p>
                  <input
                    type="text"
                    placeholder="e.g. kimi.moonshot.cn"
                    value={addHost}
                    onInput={(e) => setAddHost((e.target as HTMLInputElement).value)}
                    required
                  />
                </div>

                <div class="form-group">
                  <label>Application Display Name</label>
                  <p class="sub">Human-readable label shown in employee prompt governance notices</p>
                  <input
                    type="text"
                    placeholder="e.g. Kimi AI"
                    value={addDisplayName}
                    onInput={(e) => setAddDisplayName((e.target as HTMLInputElement).value)}
                    required
                  />
                </div>

                <div class="form-group">
                  <label>Initial Policy Access</label>
                  <select
                    value={addStatus}
                    onChange={(e) => setAddStatus((e.target as any).value)}
                  >
                    <option value="approved">Approved (Allowed for company employees)</option>
                    <option value="blocked">Blocked (Restricted / governance warning)</option>
                  </select>
                </div>

                <div class="form-group">
                  <label>Access Control Mode</label>
                  <select
                    value={addAccessMode}
                    onChange={(e) => setAddAccessMode((e.target as any).value)}
                  >
                    <option value="standard">Standard (Default Policy Rules)</option>
                    <option value="strict_redaction">Strict Redaction (Automatic PII Scrubbing)</option>
                    <option value="no_file_uploads">No File Uploads (Block Document Attachments)</option>
                  </select>
                </div>
              </div>

              <div class="modal-foot">
                <button type="button" class="btn-ghost" onClick={() => setShowAddModal(false)}>
                  Cancel
                </button>
                <button type="submit" class="btn-primary" disabled={adding}>
                  {adding ? 'Adding Tool…' : 'Add Tool'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
