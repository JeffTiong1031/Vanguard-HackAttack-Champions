import { useState } from 'preact/hooks';
import { api, NetworkError } from '../api';
import { LayersIcon } from '../icons';

export function Signup({ onBack }: { onBack: () => void }) {
  const [name, setName] = useState('');
  const [secret, setSecret] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function submit(e: Event) {
    e.preventDefault();
    setBusy(true); setError('');
    try {
      const r = await api.post<{ org_id: string; secret: string }>('/v1/signup', { company_name: name });
      setSecret(r.secret);
    } catch (err) {
      if (err instanceof NetworkError) setError(err.message);
      else setError(err instanceof Error ? `Service error: ${err.message}` : 'Could not create the company.');
    } finally { setBusy(false); }
  }

  return (
    <div class="login-wrap">
      <div class="login-card">
        <div class="brand">
          <span class="brand-mark"><LayersIcon /></span>
          <div>
            <div class="brand-name">Vanguard</div>
            <div class="brand-sub">AI Governance</div>
          </div>
        </div>

        {!secret ? (
          <form onSubmit={submit}>
            <h1 class="login-title">Create a company</h1>
            <p class="login-caption">We generate your Company Admin secret. Save it — it is shown once.</p>
            <label>Company name<input value={name}
              placeholder="e.g. Acme Corp"
              onInput={(e) => setName((e.target as HTMLInputElement).value)} /></label>
            <button type="submit" disabled={busy || !name.trim()}>Create company</button>
            {error && <p class="error">{error}</p>}
            <p class="login-caption" style="margin-top:12px">
              <a href="#" onClick={(e) => { e.preventDefault(); onBack(); }}>Back to sign in</a>
            </p>
          </form>
        ) : (
          <div>
            <h1 class="login-title">Company created</h1>
            <div class="mint-result">
              <strong>Copy this Company Admin secret now — it will not be shown again.</strong><br />
              Sign in with the <em>Company Admin</em> role and paste it.
              <code>{secret}</code>
            </div>
            <button onClick={onBack}>I&apos;ve saved it — go to sign in</button>
          </div>
        )}
      </div>
    </div>
  );
}
