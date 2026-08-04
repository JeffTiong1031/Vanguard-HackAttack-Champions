import { useEffect, useState } from 'preact/hooks';
import { api, UnauthorisedError, type AnalyticsSummary, type Scope } from '../api';
import { BarIcon, ActivityIcon, UsersIcon, SparklesIcon, TrendingUpIcon } from '../icons';
import { Bars, LineChart, RangeSelector, StatCard } from './charts';
import { pivotTrend } from './chart-helpers';

export function AiUsage({ scope }: { scope: Scope }) {
  const base = scope === 'company' ? '/v1/admin/analytics' : '/v1/dept/analytics';
  const [days, setDays] = useState(7);
  const [data, setData] = useState<AnalyticsSummary | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    async function load() {
      try { setData(await api.get<AnalyticsSummary>(`${base}/summary?days=${days}`)); setError(''); }
      catch (err) { if (err instanceof UnauthorisedError) throw err; setError(err instanceof Error ? err.message : 'Could not load usage.'); }
    }
    void load();
  }, [base, days]);

  if (!data) {
    return (
      <section class="panel">
        <p class="empty">{error || 'Fetching AI Usage Telemetry…'}</p>
      </section>
    );
  }

  const trend = pivotTrend(data.usage_trend);
  const topHost = data.top_apps[0]?.host ?? 'None';

  return (
    <div>
      {/* Top KPI Stat Cards Grid */}
      <div class="kpi-grid">
        <StatCard
          label="Total Governance Events"
          value={data.totals.events.toLocaleString()}
          sub={`Over last ${days} days`}
          icon={ActivityIcon}
          color="cyan"
        />
        <StatCard
          label="Active AI Users"
          value={data.totals.active_employees.toLocaleString()}
          sub="Employees interacting with AI"
          icon={UsersIcon}
          color="emerald"
        />
        <StatCard
          label="Top AI Application"
          value={topHost}
          sub="Most accessed tool domain"
          icon={SparklesIcon}
          color="orange"
        />
        <StatCard
          label="Analytics Scope"
          value={scope === 'company' ? 'Organization' : 'Department'}
          sub={`Last ${days} days telemetry`}
          icon={TrendingUpIcon}
          color="indigo"
        />
      </div>

      <div class="panel">
        <div class="panel-head">
          <span class="ico"><BarIcon /></span>
          <div>
            <h2>AI Usage & Telemetry Analytics</h2>
            <p class="sub">Governance events overview — host domains, prompt activity, policy triggers.</p>
          </div>
          <div style="margin-left:auto">
            <RangeSelector days={days} onChange={setDays} />
          </div>
        </div>

        {error && <p class="error">{error}</p>}

        <LineChart title="Daily AI Telemetry Events by Department" series={trend.series} labels={trend.dates} scheme="cyan" />
      </div>

      <div class="grid-2col">
        <div class="panel">
          <Bars title="Top Apps / Domains" rows={data.top_apps.map((a) => ({ label: a.host, value: a.events }))} variant="cyan" />
        </div>
        <div class="panel">
          <Bars title="Top Active Employees" rows={data.top_employees.map((e) => ({ label: `${e.name} (${e.department})`, value: e.events }))} variant="orange" />
        </div>
      </div>
    </div>
  );
}
