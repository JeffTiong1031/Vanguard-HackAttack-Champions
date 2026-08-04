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
            <div class="brand-sub">Governance Console</div>
          </div>
        </div>
        <h1 class="login-title">Console Authentication</h1>
        <p class="login-caption">Select your administrative role and enter your security secret key.</p>

        <div class="role-toggle">
          <button type="button" aria-pressed={role === 'company'}
            class={role === 'company' ? 'btn-primary role-on' : 'btn-ghost'}
            onClick={() => setRole('company')}>Company Admin</button>
          <button type="button" aria-pressed={role === 'department'}
            class={role === 'department' ? 'btn-primary role-on' : 'btn-ghost'}
            onClick={() => setRole('department')}>Department Admin</button>
        </div>

        <label>
          Access Secret Key
          <input
            type="password"
            value={secret}
            placeholder="Paste your assigned secret key…"
            onInput={(e) => setSecret((e.target as HTMLInputElement).value)}
          />
        </label>
        
        <button type="submit" class="btn-primary">Authenticate & Access Console</button>
        
        {error && <p class="error">{error}</p>}
        
        <p class="login-caption" style="margin-top:18px">
          Need to register a new organization? <a href="#" onClick={(e) => { e.preventDefault(); onCreate(); }} style="color:var(--primary);font-weight:700">Provision Organization</a>.
        </p>
      </form>
    </div>
  );
}
