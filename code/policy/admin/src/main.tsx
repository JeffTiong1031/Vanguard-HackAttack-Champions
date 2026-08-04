import { render } from 'preact';
import { useEffect, useState } from 'preact/hooks';
import { api, UnauthorisedError, type Session } from './api';
import { Login } from './screens/Login';
import { Signup } from './screens/Signup';
import { Tools } from './screens/Tools';
import { Departments } from './screens/Departments';
import { Requests } from './screens/Requests';
import { Reviews } from './screens/Reviews';
import { AiUsage } from './screens/AiUsage';
import { InsiderRisk } from './screens/InsiderRisk';
import { Tokens } from './screens/Tokens';
import { DeptTools } from './screens/DeptTools';
import {
  LayersIcon, ShieldIcon, InboxIcon, BarIcon, KeyIcon, GavelIcon,
  PanelLeftIcon, ChevronRightIcon, ChevronLeftIcon
} from './icons';
import './style.css';

const SESSION_KEY = 'vg_admin_session';

interface NavItem {
  id: string;
  label: string;
  category: string;
  icon: typeof ShieldIcon;
  component: preact.ComponentChildren;
}

function loadSession(): Session | null {
  try { return JSON.parse(localStorage.getItem(SESSION_KEY) ?? 'null'); } catch { return null; }
}

function useScrollReveal(activeId: string) {
  useEffect(() => {
    let lastScrollY = window.scrollY;
    let isScrollingUp = false;

    const updateDirectionClasses = () => {
      const currentScrollY = window.scrollY;
      if (Math.abs(currentScrollY - lastScrollY) < 2) return;
      isScrollingUp = currentScrollY < lastScrollY;
      lastScrollY = currentScrollY;

      const hiddenTargets = document.querySelectorAll('.reveal-target:not(.reveal-in)');
      hiddenTargets.forEach((el) => {
        if (isScrollingUp) {
          el.classList.add('from-top');
          el.classList.remove('from-bottom');
        } else {
          el.classList.add('from-bottom');
          el.classList.remove('from-top');
        }
      });
    };

    window.addEventListener('scroll', updateDirectionClasses, { passive: true });

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const el = entry.target as HTMLElement;
          if (entry.isIntersecting) {
            if (isScrollingUp) {
              el.classList.add('from-top');
              el.classList.remove('from-bottom');
            } else {
              el.classList.add('from-bottom');
              el.classList.remove('from-top');
            }
            requestAnimationFrame(() => {
              el.classList.add('reveal-in');
            });
          }
        });
      },
      { threshold: 0.05, rootMargin: '0px 0px -20px 0px' }
    );

    // Instant scroll to top on page navigation
    window.scrollTo({ top: 0 });

    // Mark elements in initial viewport as visible immediately to avoid flash
    const targets = document.querySelectorAll(
      '.panel, .stat-card, .table-wrap, .bars-group'
    );
    targets.forEach((el) => {
      const rect = el.getBoundingClientRect();
      if (rect.top < window.innerHeight) {
        el.classList.add('reveal-in');
      } else {
        el.classList.add('reveal-target', 'from-bottom');
        observer.observe(el);
      }
    });

    return () => {
      window.removeEventListener('scroll', updateDirectionClasses);
      observer.disconnect();
    };
  }, [activeId]);
}

function App() {
  const [session, setSession] = useState<Session | null>(loadSession);
  const [view, setView] = useState<'login' | 'signup'>('login');
  const [checking, setChecking] = useState(() => !!loadSession());

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
    try { await api.post('/v1/admin/logout'); } catch { /* clear locally */ }
    localStorage.removeItem(SESSION_KEY);
    setSession(null);
  }

  if (checking) return <div class="login-wrap"><p class="empty">Authenticating security session…</p></div>;
  if (!session) {
    return view === 'signup'
      ? <Signup onBack={() => setView('login')} />
      : <Login onDone={handleLogin} onCreate={() => setView('signup')} />;
  }
  return <Dashboard session={session} onLogout={logout} />;
}

function Dashboard({ session, onLogout }: { session: Session; onLogout: () => void }) {
  const isCompany = session.role === 'company';
  const [collapsed, setCollapsed] = useState(false);

  const navItems: NavItem[] = isCompany
    ? [
        { id: 'risk', label: 'Insider Risk', category: 'Dashboards', icon: ShieldIcon, component: <InsiderRisk scope="company" /> },
        { id: 'usage', label: 'AI Usage & Telemetry', category: 'Dashboards', icon: BarIcon, component: <AiUsage scope="company" /> },
        { id: 'requests', label: 'Access Requests', category: 'Security & Access', icon: InboxIcon, component: <Requests scope="company" /> },
        { id: 'reviews', label: 'Prompt Audits & Appeals', category: 'Security & Access', icon: GavelIcon, component: <Reviews scope="company" /> },
        { id: 'tools', label: 'Tools Policy Matrix', category: 'Security & Access', icon: ShieldIcon, component: <Tools /> },
        { id: 'departments', label: 'Departments & Secrets', category: 'Management', icon: KeyIcon, component: <Departments /> },
      ]
    : [
        { id: 'risk', label: 'Insider Risk', category: 'Dashboards', icon: ShieldIcon, component: <InsiderRisk scope="department" /> },
        { id: 'usage', label: 'AI Usage & Telemetry', category: 'Dashboards', icon: BarIcon, component: <AiUsage scope="department" /> },
        { id: 'requests', label: 'Access Requests', category: 'Security & Access', icon: InboxIcon, component: <Requests scope="department" /> },
        { id: 'reviews', label: 'Prompt Audits & Appeals', category: 'Security & Access', icon: GavelIcon, component: <Reviews scope="department" /> },
        { id: 'tools', label: 'Department Tools', category: 'Security & Access', icon: ShieldIcon, component: <DeptTools /> },
        { id: 'tokens', label: 'Employee Tokens', category: 'Management', icon: KeyIcon, component: <Tokens /> },
      ];

  const [activeId, setActiveId] = useState(navItems[0].id);
  const activeItem = navItems.find((n) => n.id === activeId) ?? navItems[0];

  // Enable directional real-time scroll reveal animations
  useScrollReveal(activeId);

  // Group items by category
  const categories = Array.from(new Set(navItems.map((i) => i.category)));

  return (
    <div class="app-shell">
      {/* Collapsible Left Sidebar */}
      <aside class={`sidebar ${collapsed ? 'collapsed' : ''}`}>
        <div class="sidebar-head">
          {!collapsed ? (
            <>
              <div class="sidebar-brand">
                <span class="sidebar-brand-icon"><LayersIcon /></span>
                <span class="sidebar-brand-text">Vanguard</span>
              </div>
              <button
                class="toggle-btn"
                onClick={() => setCollapsed(true)}
                title="Collapse Sidebar"
                aria-label="Collapse Sidebar"
              >
                <ChevronLeftIcon />
              </button>
            </>
          ) : (
            <button
              class="sidebar-brand-icon collapsed-toggle-btn"
              onClick={() => setCollapsed(false)}
              title="Expand Sidebar"
              aria-label="Expand Sidebar"
            >
              <ChevronRightIcon />
            </button>
          )}
        </div>

        <nav class="sidebar-nav">
          {categories.map((cat) => (
            <div class="nav-group" key={cat}>
              <div class="nav-section-title">{cat}</div>
              {navItems
                .filter((item) => item.category === cat)
                .map((item) => {
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.id}
                      class={`nav-item ${activeId === item.id ? 'active' : ''}`}
                      onClick={() => setActiveId(item.id)}
                      title={item.label}
                    >
                      <Icon />
                      <span class="nav-item-text">{item.label}</span>
                    </button>
                  );
                })}
            </div>
          ))}
        </nav>
      </aside>

      {/* Main Content Area */}
      <div class="main-wrap">
        {/* Upper Header Bar */}
        <header class="topbar">
          <div class="breadcrumbs">
            <span class="crumb-root">{activeItem.category}</span>
            <span class="sep"><ChevronRightIcon style="width:14px;height:14px" /></span>
            <span class="crumb-active">{activeItem.label}</span>
          </div>

          <div class="topbar-right">
            <span class="chip live"><span class="dot"></span> <strong>Live Guard</strong></span>
            <span class="chip">Org: <strong>{session.org_name}</strong></span>
            {!isCompany && <span class="chip">Dept: <strong>{session.department}</strong></span>}
            <button class="btn-signout" onClick={onLogout}>Sign Out</button>
          </div>
        </header>

        {/* Content Canvas with Page View Transition Animation */}
        <main class="main-content">
          <div key={activeId} class="page-transition-wrap">
            {activeItem.component}
          </div>
        </main>
      </div>
    </div>
  );
}

render(<App />, document.getElementById('root')!);
