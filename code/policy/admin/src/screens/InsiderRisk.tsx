import { useEffect, useState } from 'preact/hooks';
import { api, UnauthorisedError, type AnalyticsSummary, type AlertRow, type Scope } from '../api';
import { ShieldIcon, AlertTriangleIcon, ActivityIcon, UsersIcon } from '../icons';
import { Bars, LineChart, AlertsTable, RangeSelector, StatCard } from './charts';

const WEIGHTS = 'Risk Weights: Ethics block = 5 · PII block = 3 · Warning = 1 · Unapproved visit = 1 · Access request = 0';

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

  if (!data) {
    return (
      <section class="panel">
        <p class="empty">{error || 'Calculating Risk Index & Threat Telemetry…'}</p>
      </section>
    );
  }

  const highAlertsCount = data.alerts_by_severity.find((s) => s.severity === 'high')?.count ?? 0;
  const topRiskyUser = data.top_employees[0] ? `${data.top_employees[0].name}` : 'None';

  const riskLine = [{ department: 'Risk Score', points: data.risk_timeline.map((r) => r.risk) }];
  const riskDates = data.risk_timeline.map((r) => r.date);
  const alertLines = [
    { department: 'High Severity', points: data.alerts_timeline.map((r) => r.high) },
    { department: 'Medium Severity', points: data.alerts_timeline.map((r) => r.medium) },
    { department: 'Low Severity', points: data.alerts_timeline.map((r) => r.low) },
  ];
  const alertDates = data.alerts_timeline.map((r) => r.date);

  return (
    <div>
      {/* Top KPI Stat Cards Grid */}
      <div class="kpi-grid">
        <StatCard
          label="High Severity Alerts"
          value={highAlertsCount.toLocaleString()}
          sub={`Critical policy violations (${days}d)`}
          icon={AlertTriangleIcon}
          color="crimson"
        />
        <StatCard
          label="Highest Risk Employee"
          value={topRiskyUser}
          sub={data.top_employees[0] ? `Risk Score: ${data.top_employees[0].risk}` : 'No risk flagged'}
          icon={UsersIcon}
          color="orange"
        />
        <StatCard
          label="Governance Telemetry"
          value={data.totals.events.toLocaleString()}
          sub="Analyzed policy events"
          icon={ActivityIcon}
          color="cyan"
        />
        <StatCard
          label="Monitored Audit Stream"
          value={alerts.length.toLocaleString()}
          sub="Recent security audit entries"
          icon={ShieldIcon}
          color="emerald"
        />
      </div>

      <div class="panel">
        <div class="panel-head">
          <span class="ico"><ShieldIcon /></span>
          <div>
            <h2>Insider Risk & Threat Score Matrix</h2>
            <p class="sub">Evaluation heuristic over AI prompt usage, ethical policy blocks, and PII redactions.</p>
          </div>
          <div style="margin-left:auto">
            <RangeSelector days={days} onChange={setDays} />
          </div>
        </div>

        <p class="hint">{WEIGHTS}</p>
        {error && <p class="error">{error}</p>}

        <div class="grid-2col" style="margin-top:20px">
          {/* Risk Score Timeline: Crimson Line Chart */}
          <LineChart
            title="Risk Score Timeline"
            series={riskLine}
            labels={riskDates}
            scheme="crimson"
          />
          {/* Alerts Timeline: Sky Blue / Cyan Line Chart */}
          <LineChart
            title="Alerts Timeline (by Severity)"
            series={alertLines}
            labels={alertDates}
            scheme="cyan"
          />
        </div>
      </div>

      <div class={scope === 'company' ? 'grid-main-side' : 'grid-2col'}>
        <div class="panel">
          <Bars
            title="Top Risky Employees"
            rows={data.top_employees.map((e) => ({ label: `${e.name} (${e.department})`, value: e.risk }))}
            variant="crimson"
          />
        </div>
        {scope === 'company' && (
          <div class="panel">
            <Bars
              title="Top Risky Departments"
              rows={data.top_departments.map((d) => ({ label: d.department, value: d.risk }))}
              variant="crimson"
            />
          </div>
        )}
        <div class="panel">
          <Bars
            title="Alert Breakdown by Severity"
            rows={data.alerts_by_severity.map((s) => ({ label: s.severity.toUpperCase(), value: s.count }))}
            variant="orange"
          />
        </div>
      </div>

      <div class="panel">
        <div class="panel-head">
          <span class="ico"><AlertTriangleIcon /></span>
          <div>
            <h2>Security Audit Stream & Violation Alerts</h2>
            <p class="sub">Detailed real-time security events captured by Vanguard governance policies.</p>
          </div>
          <span class="tag count">{alerts.length} events logged</span>
        </div>
        <AlertsTable rows={alerts} />
      </div>
    </div>
  );
}
