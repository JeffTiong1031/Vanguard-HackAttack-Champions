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
            <div class="brand-sub">Governance Console</div>
          </div>
        </div>

        {!secret ? (
          <form onSubmit={submit}>
            <h1 class="login-title">Provision New Organization</h1>
            <p class="login-caption">Generate your root Company Admin master secret key. Store it securely.</p>
            <label>
              Organization / Company Name
              <input
                value={name}
                placeholder="e.g. Vanguard Security Corp"
                onInput={(e) => setName((e.target as HTMLInputElement).value)}
              />
            </label>
            <button type="submit" class="btn-primary" disabled={busy || !name.trim()}>Generate Master Secret</button>
            {error && <p class="error">{error}</p>}
            <p class="login-caption" style="margin-top:18px">
              <a href="#" onClick={(e) => { e.preventDefault(); onBack(); }} style="color:var(--primary);font-weight:700">← Back to Authentication</a>
            </p>
          </form>
        ) : (
          <div>
            <h1 class="login-title">Organization Provisioned</h1>
            <div class="mint-result">
              <strong>Save this Master Company Secret immediately (shown only once):</strong><br />
              Use this key under <em>Company Admin</em> to sign in.
              <code>{secret}</code>
            </div>
            <button class="btn-primary" style="width:100%;margin-top:16px" onClick={onBack}>I&apos;ve Saved My Secret — Continue to Sign In</button>
          </div>
        )}
      </div>
    </div>
  );
}
