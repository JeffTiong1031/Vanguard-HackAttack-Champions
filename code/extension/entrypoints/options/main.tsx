import { render } from 'preact';
import { useEffect, useState } from 'preact/hooks';
import {
  getApiBase,
  getDemoToken,
  setApiBase,
  setDemoToken,
} from '../../src/files/config';
import { getMode, setMode, optionsView, type Mode } from '../../src/mode/mode';
import { getPolicyBase, setPolicyBase } from '../../src/policy/config';
import type { PolicyRequest, PolicyResponse, AppealsResponse } from '../../src/policy/messages';
import { clearEnrolment } from '../../src/policy/store';
import { REVOKED_MESSAGE, takeRevokedNotice } from '../../src/policy/revoked';
import type { Enrolment, Policy } from '../../src/policy/types';
import type { AppealRow } from '../../src/policy/appeals';
import { SensitivityPanel } from '../../src/ui/sensitivity-panel';

export const TOKEN_RESPONSIBILITY =
  'Keep this code private — activity recorded under it is attributed to you.';

/** Enterprise is a commitment, not a toggle: leaving requires the admin to
 *  revoke. Honest limit — the extension can still be removed in Chrome. */
export function canSwitchToPersonal(enrolment: Enrolment | null): boolean {
  return enrolment === null;
}

function ask(msg: PolicyRequest): Promise<PolicyResponse> {
  return chrome.runtime.sendMessage(msg) as Promise<PolicyResponse>;
}

type OrganisationProps = {
  enrolment: Enrolment | null;
  setEnrolment: (e: Enrolment | null) => void;
  policy: Policy | null;
  setPolicy: (p: Policy | null) => void;
};

function Organisation({ enrolment, setEnrolment, policy, setPolicy }: OrganisationProps) {
  const [token, setToken] = useState('');
  const [base, setBase] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    void getPolicyBase().then(setBase);
  }, []);

  async function join() {
    setError('');
    await setPolicyBase(base);
    const r = await ask({ kind: 'policy-enrol', token: token.trim() });
    if (!r.ok) { setError(r.error); return; }
    setEnrolment(r.enrolment);
    setPolicy(r.policy);
    setToken('');
  }

  async function leave() {
    await clearEnrolment();
    setEnrolment(null);
    setPolicy(null);
  }

  if (enrolment) {
    const approved = policy?.tools.filter((t) => t.status === 'approved').length ?? 0;
    return (
      <section>
        <h2 style="font-size:16px">Organisation</h2>
        <p style="color:#15803d">
          Connected to <strong>{enrolment.org_name}</strong> · {enrolment.department} ·{' '}
          {approved} approved tools · policy v{policy?.version ?? '?'}
        </p>
        <button onClick={leave} style="padding:6px 12px;border:1px solid #cbd5e1;
                border-radius:6px;background:#fff;cursor:pointer">Disconnect</button>
      </section>
    );
  }

  return (
    <section>
      <h2 style="font-size:16px">Organisation</h2>
      <p style="color:#475569">
        Paste the enrolment token your admin gave you. Vanguard never collects your name,
        email, or prompt text. Your organisation may label your enrolment with your name
        for its own records.
      </p>
      <input
        value={base}
        onInput={(e) => setBase((e.target as HTMLInputElement).value)}
        placeholder="Policy service address"
        style="width:100%;padding:8px;border:1px solid #cbd5e1;border-radius:6px;margin-bottom:8px"
      />
      <p style="color:#64748b;font-size:12px;margin:0 0 4px">{TOKEN_RESPONSIBILITY}</p>
      <input
        value={token}
        onInput={(e) => setToken((e.target as HTMLInputElement).value)}
        placeholder="ENG-xxxxxxxxxxxx"
        style="width:100%;padding:8px;border:1px solid #cbd5e1;border-radius:6px"
      />
      <button onClick={join} style="margin-top:12px;padding:8px 14px;border:none;
              border-radius:6px;background:#e11d48;color:#fff;cursor:pointer">Connect</button>
      {error && <p style="color:#b91c1c">{error}</p>}
    </section>
  );
}

function FileService() {
  const [base, setBase] = useState('');
  const [token, setToken] = useState('');
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    void getApiBase().then(setBase);
    void getDemoToken().then(setToken);
  }, []);
  return (
    <section style="margin-top:32px">
      <h2 style="font-size:16px">File checking</h2>
      <p style="color:#475569">
        Address of the file-checking service. Use <code>http://localhost:8000</code> if you are
        running it yourself, or leave the default hosted address. For the hosted demo, also paste
        the access key your team lead sent you (it is not in the repo).
      </p>
      <label style="display:block;margin-bottom:4px;color:#334155">Service address</label>
      <input
        value={base}
        onInput={(e) => { setBase((e.target as HTMLInputElement).value); setSaved(false); }}
        style="width:100%;padding:8px;border:1px solid #cbd5e1;border-radius:6px;margin-bottom:12px"
      />
      <label style="display:block;margin-bottom:4px;color:#334155">Demo access key</label>
      <input
        type="password"
        value={token}
        autocomplete="off"
        onInput={(e) => { setToken((e.target as HTMLInputElement).value); setSaved(false); }}
        placeholder="Paste the key from your team lead"
        style="width:100%;padding:8px;border:1px solid #cbd5e1;border-radius:6px"
      />
      <button
        onClick={async () => {
          await setApiBase(base);
          await setDemoToken(token);
          setSaved(true);
        }}
        style="margin-top:12px;padding:8px 14px;border:none;border-radius:6px;
               background:#e11d48;color:#fff;cursor:pointer"
      >Save</button>
      {saved && <span style="margin-left:10px;color:#15803d">Saved</span>}
    </section>
  );
}

function MyReviews() {
  const [rows, setRows] = useState<AppealRow[]>([]);
  useEffect(() => {
    const load = () => (chrome.runtime.sendMessage({ kind: 'appeals-get' }) as Promise<AppealsResponse>)
      .then((r) => { if (r?.ok) setRows(r.appeals); }).catch(() => {});
    void load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);
  if (rows.length === 0) return null;
  return (
    <section style="margin-top:28px;border-top:1px solid #e2e8f0;padding-top:20px">
      <h1 style="font-size:18px">My reviews</h1>
      <p style="color:#475569">Decisions you asked a person to review.</p>
      {rows.map((r) => (
        <div key={r.id} style="display:flex;gap:10px;align-items:center;margin:8px 0;font-size:14px">
          <span style="width:190px">{r.decision_type} · {r.category}</span>
          <strong style={r.status === 'overturned' ? 'color:#15803d' : r.status === 'upheld' ? 'color:#b91c1c' : 'color:#64748b'}>
            {r.status}
          </strong>
          {r.admin_note && <span style="color:#475569">— {r.admin_note}</span>}
        </div>
      ))}
    </section>
  );
}

function ModePicker({ onChoose }: { onChoose: (m: Mode) => void }) {
  const card = 'flex:1;border:1px solid #e2e8f0;border-radius:10px;padding:20px;cursor:pointer;text-align:left;background:#fff';
  return (
    <section>
      <h2 style="font-size:16px">Choose how Vanguard runs</h2>
      <div style="display:flex;gap:16px;margin-top:12px">
        <button style={card} onClick={() => onChoose('personal')}>
          <strong style="display:block;font-size:15px;margin-bottom:6px">Personal</strong>
          <span style="color:#475569;font-size:13px">
            Protect your own sensitive data on this device. Nothing is sent anywhere.
          </span>
        </button>
        <button style={card} onClick={() => onChoose('enterprise')}>
          <strong style="display:block;font-size:15px;margin-bottom:6px">Enterprise</strong>
          <span style="color:#475569;font-size:13px">
            Connect to your organisation's policy, approvals, and file checking.
          </span>
        </button>
      </div>
    </section>
  );
}

function PersonalPanel({ onSwitch }: { onSwitch: () => void }) {
  return (
    <section>
      <h2 style="font-size:16px">Personal mode</h2>
      <p style="color:#475569">
        Vanguard protects sensitive data locally on ChatGPT and Claude. Nothing leaves this device —
        no organisation, no reporting, no file uploads.
      </p>
      <button onClick={onSwitch} style="padding:6px 12px;border:1px solid #cbd5e1;
              border-radius:6px;background:#fff;cursor:pointer">Switch to Enterprise</button>
    </section>
  );
}

function Options() {
  const [mode, setModeState] = useState<Mode | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [enrolment, setEnrolment] = useState<Enrolment | null>(null);
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [revokedNotice, setRevokedNotice] = useState(false);

  useEffect(() => { void getMode().then((m) => { setModeState(m); setLoaded(true); }); }, []);
  useEffect(() => {
    void ask({ kind: 'policy-get' }).then((r) => {
      if (r.ok) { setEnrolment(r.enrolment); setPolicy(r.policy); }
    });
  }, []);
  useEffect(() => { void takeRevokedNotice().then(setRevokedNotice); }, []);

  async function choose(m: Mode) { await setMode(m); setModeState(m); }
  async function toPersonal() {
    if (!canSwitchToPersonal(enrolment)) return; // belt-and-braces: the button is disabled too
    await clearEnrolment();            // disconnect + stop reporting
    await setMode('personal');
    setModeState('personal');
  }

  const view = loaded ? optionsView(mode) : null;
  const canLeave = canSwitchToPersonal(enrolment);

  return (
    <div style="font:14px/1.5 system-ui, sans-serif; max-width:560px">
      <h1 style="font-size:18px">Vanguard</h1>
      {revokedNotice && (
        <p style="background:#fef3c7;color:#92400e;padding:10px 12px;border-radius:6px;margin-bottom:16px">
          {REVOKED_MESSAGE}
        </p>
      )}
      {view === null && <p style="color:#64748b">Loading…</p>}
      {view === 'picker' && <ModePicker onChoose={choose} />}
      {view === 'personal' && <PersonalPanel onSwitch={() => void choose('enterprise')} />}
      {view === 'enterprise' && (
        <>
          <Organisation
            enrolment={enrolment}
            setEnrolment={setEnrolment}
            policy={policy}
            setPolicy={setPolicy}
          />
          <FileService />
          <MyReviews />
          <section style="margin-top:32px;border-top:1px solid #e2e8f0;padding-top:16px">
            <button
              onClick={() => void toPersonal()}
              disabled={!canLeave}
              style={`padding:6px 12px;border:1px solid #cbd5e1;border-radius:6px;background:#fff;
                      cursor:${canLeave ? 'pointer' : 'not-allowed'};opacity:${canLeave ? '1' : '0.6'}`}
            >Switch to Personal</button>
            <p style="color:#94a3b8;font-size:12px;margin-top:6px">
              {canLeave
                ? 'Switching disconnects from your organisation and stops all reporting.'
                : 'Ask your admin to revoke your enrolment first. (You can still remove Vanguard from Chrome.)'}
            </p>
          </section>
        </>
      )}
    </div>
  );
}

// Guarded rather than `!`-asserted: importing this module's named exports
// (tests, other entrypoints) must not crash just because there is no #root
// in that environment's document.
const root = document.getElementById('root');
if (root) {
  render(
    <>
      <Options />
      <SensitivityPanel />
    </>,
    root,
  );
}
