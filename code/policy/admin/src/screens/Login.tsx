import { useState } from 'preact/hooks';
import { api, UnauthorisedError, NetworkError, type LoginResult, type Session, type Scope } from '../api';
import { LayersIcon } from '../icons';

export function Login({ onDone, onCreate }: { onDone: (s: Session) => void; onCreate: () => void }) {
  const [role, setRole] = useState<Scope>('company');
  const [secret, setSecret] = useState('');
  const [error, setError] = useState('');

  async function submit(e: Event) {
    e.preventDefault();
    setError('');
    try {
      const r = await api.post<LoginResult>('/v1/admin/login', { role, secret });
      onDone({
        role: r.role, org_id: r.org_id, org_name: r.org_name,
        department_id: r.department_id, department: r.department,
      });
    } catch (err) {
      if (err instanceof UnauthorisedError) setError('That secret was not recognised for this role.');
      else if (err instanceof NetworkError) setError(err.message);
      else if (err instanceof Error) setError(`Service error: ${err.message}`);
      else setError('An unexpected error occurred.');
    }
  }

  return (
    <div class="login-wrap">
      <form class="login-card" onSubmit={submit}>
        <div class="brand">
          <span class="brand-mark"><LayersIcon /></span>
          <div>
            <div class="brand-name">Vanguard</div>
            <div class="brand-sub">AI Governance</div>
          </div>
        </div>
        <h1 class="login-title">Sign in</h1>
        <p class="login-caption">Choose your role, then paste your access secret.</p>

        {/* The unselected button must be `btn-ghost`, not `''`: an empty class
            falls through to the default `button` rule, which is the same indigo
            gradient as `.btn-primary` — making both look selected. */}
        <div class="role-toggle" style="display:flex;gap:8px;margin-bottom:12px">
          <button type="button" aria-pressed={role === 'company'}
            class={role === 'company' ? 'btn-primary role-on' : 'btn-ghost'}
            style="flex:1" onClick={() => setRole('company')}>Company Admin</button>
          <button type="button" aria-pressed={role === 'department'}
            class={role === 'department' ? 'btn-primary role-on' : 'btn-ghost'}
            style="flex:1" onClick={() => setRole('department')}>Department Admin</button>
        </div>

        <label>Access secret<input type="password" value={secret}
          placeholder="Paste the secret you were given"
          onInput={(e) => setSecret((e.target as HTMLInputElement).value)} /></label>
        <button type="submit">Sign in</button>
        {error && <p class="error">{error}</p>}
        <p class="login-caption" style="margin-top:12px">
          New company? <a href="#" onClick={(e) => { e.preventDefault(); onCreate(); }}>Create one</a>.
        </p>
      </form>
    </div>
  );
}
