import { render } from 'preact';
import { useEffect, useState } from 'preact/hooks';
import { api, UnauthorisedError, type Session, type Scope } from './api';
import { Login } from './screens/Login';
import { Signup } from './screens/Signup';
import { Tools } from './screens/Tools';
import { Departments } from './screens/Departments';
import { Requests } from './screens/Requests';
import { Reviews } from './screens/Reviews';
import { Usage } from './screens/Usage';
import { Tokens } from './screens/Tokens';
import { DeptTools } from './screens/DeptTools';
import { LayersIcon, ShieldIcon, InboxIcon, BarIcon, KeyIcon, GavelIcon } from './icons';
import './style.css';

const SESSION_KEY = 'vg_admin_session';

type TabDef = [string, string, typeof ShieldIcon, preact.ComponentChildren];

function loadSession(): Session | null {
  try { return JSON.parse(localStorage.getItem(SESSION_KEY) ?? 'null'); } catch { return null; }
}

function App() {
  const [session, setSession] = useState<Session | null>(loadSession);
  const [view, setView] = useState<'login' | 'signup'>('login');
  const [checking, setChecking] = useState(() => !!loadSession());

  // Verify a cached session with a role-appropriate authenticated call. A 401
  // means it expired -> drop it. Any other failure leaves it alone (the backend
  // may simply be down); the user retries with a reload. Timeout so a hung
  // request degrades the same way a rejection does.
  useEffect(() => {
    const cached = loadSession();
    if (!cached) return;
    const probe = cached.role === 'company' ? '/v1/admin/departments' : '/v1/dept/requests';
    const timeout = new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error('session check timed out')), 5000));
    Promise.race([api.get(probe), timeout])
      .then(() => { setSession(cached); setChecking(false); })
      .catch((err) => {
        if (err instanceof UnauthorisedError) localStorage.removeItem(SESSION_KEY);
        setChecking(false);
      });
  }, []);

  // A 401 anywhere bounces to login (screens don't catch UnauthorisedError).
  useEffect(() => {
    function onRejection(event: PromiseRejectionEvent) {
      if (event.reason instanceof UnauthorisedError) {
        event.preventDefault();
        localStorage.removeItem(SESSION_KEY);
        setSession(null);
      }
    }
    window.addEventListener('unhandledrejection', onRejection);
    return () => window.removeEventListener('unhandledrejection', onRejection);
  }, []);

  function handleLogin(s: Session) {
    localStorage.setItem(SESSION_KEY, JSON.stringify(s));
    setSession(s);
    setView('login');
  }

  async function logout() {
    try { await api.post('/v1/admin/logout'); } catch { /* clear locally regardless */ }
    localStorage.removeItem(SESSION_KEY);
    setSession(null);
  }

  if (checking) return <div class="login-wrap"><p class="empty">Checking session…</p></div>;
  if (!session) {
    return view === 'signup'
      ? <Signup onBack={() => setView('login')} />
      : <Login onDone={handleLogin} onCreate={() => setView('signup')} />;
  }
  return <Dashboard session={session} onLogout={logout} />;
}

function Dashboard({ session, onLogout }: { session: Session; onLogout: () => void }) {
  const isCompany = session.role === 'company';
  const tabs: TabDef[] = isCompany
    ? [
        ['departments', 'Departments', KeyIcon, <Departments />],
        ['tools', 'Tools', ShieldIcon, <Tools />],
        ['requests', 'Requests', InboxIcon, <Requests scope="company" />],
        ['reviews', 'Reviews', GavelIcon, <Reviews scope="company" />],
        ['usage', 'Usage', BarIcon, <Usage scope="company" />],
      ]
    : [
        ['requests', 'Requests', InboxIcon, <Requests scope="department" />],
        ['reviews', 'Reviews', GavelIcon, <Reviews scope="department" />],
        ['tokens', 'Employee Tokens', KeyIcon, <Tokens />],
        ['tools', 'Tools', ShieldIcon, <DeptTools />],
        ['usage', 'Usage', BarIcon, <Usage scope="department" />],
      ];
  const [active, setActive] = useState(tabs[0][0]);

  return (
    <div class="app">
      <header class="topbar">
        <div class="brand">
          <span class="brand-mark"><LayersIcon /></span>
          <div>
            <div class="brand-name">Vanguard</div>
            <div class="brand-sub">{isCompany ? 'Company Admin' : 'Department Admin'}</div>
          </div>
        </div>
        <div class="topbar-right">
          <span class="chip"><span class="dot" style="background:#4f46e5"></span> <strong>{session.org_name}</strong></span>
          {!isCompany && <span class="chip"><strong>{session.department}</strong></span>}
          <button class="btn-sm" onClick={onLogout}>Sign out</button>
        </div>
      </header>

      <nav class="tabs">
        {tabs.map(([id, label, Icon]) => (
          <button key={id} class={active === id ? 'active' : ''} onClick={() => setActive(id)}>
            <Icon /> {label}
          </button>
        ))}
      </nav>

      <main>{tabs.find((t) => t[0] === active)![3]}</main>
    </div>
  );
}

render(<App />, document.getElementById('root')!);
