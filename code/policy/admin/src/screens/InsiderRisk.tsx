import { useEffect, useState } from 'preact/hooks';
import { api, UnauthorisedError, type AnalyticsSummary, type AlertRow, type Scope } from '../api';
import { ShieldIcon } from '../icons';
import { Bars, LineChart, AlertsTable, RangeSelector } from './charts';

const WEIGHTS = 'Risk weights: ethics block 5 · PII block 3 · warning 1 · unapproved visit 1 · access request 0';

export function InsiderRisk({ scope }: { scope: Scope }) {
  const base = scope === 'company' ? '/v1/admin/analytics' : '/v1/dept/analytics';
  const [days, setDays] = useState(7);
  const [data, setData] = useState<AnalyticsSummary | null>(null);
  const [alerts, setAlerts] = useState<AlertRow[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    async function load() {
      try {
        setData(await api.get<AnalyticsSummary>(`${base}/summary?days=${days}`));
        setAlerts(await api.get<AlertRow[]>(`${base}/alerts?limit=50`));
        setError('');
      } catch (err) { if (err instanceof UnauthorisedError) throw err; setError(err instanceof Error ? err.message : 'Could not load risk data.'); }
    }
    void load();
  }, [base, days]);

  if (!data) return <section class="panel"><p class="empty">{error || 'Loading…'}</p></section>;

  const riskLine = [{ department: 'Risk', points: data.risk_timeline.map((r) => r.risk) }];
  const alertLines = [
    { department: 'High', points: data.alerts_timeline.map((r) => r.high) },
    { department: 'Medium', points: data.alerts_timeline.map((r) => r.medium) },
    { department: 'Low', points: data.alerts_timeline.map((r) => r.low) },
  ];

  return (
    <section class="panel">
      <div class="panel-head">
        <span class="ico"><ShieldIcon /></span>
        <div>
          <h2>Insider Risk</h2>
          <p class="sub">A transparent heuristic over governance events. It ranks; it does not diagnose.</p>
        </div>
        <span class="tag">{data.totals.events} events</span>
      </div>
      <RangeSelector days={days} onChange={setDays} />
      <p class="hint">{WEIGHTS}</p>
      {error && <p class="error">{error}</p>}

      <LineChart title="Risk score timeline" series={riskLine} />
      <LineChart title="Alerts timeline (by severity)" series={alertLines} />
      <Bars title="Top risky employees"
            rows={data.top_employees.map((e) => ({ label: `${e.name} · ${e.department}`, value: e.risk }))} />
      {scope === 'company' && (
        <Bars title="Top risky departments"
              rows={data.top_departments.map((d) => ({ label: d.department, value: d.risk }))} />
      )}
      <Bars title="Alerts by severity"
            rows={data.alerts_by_severity.map((s) => ({ label: s.severity, value: s.count }))} />
      <h3 style="margin-top:20px">Review alerts</h3>
      <AlertsTable rows={alerts} />
    </section>
  );
}
