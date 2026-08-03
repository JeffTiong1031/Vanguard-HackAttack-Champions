import { useEffect, useState } from 'preact/hooks';
import { api, UnauthorisedError, type AnalyticsSummary, type Scope } from '../api';
import { BarIcon } from '../icons';
import { Bars, LineChart, RangeSelector } from './charts';
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

  if (!data) return <section class="panel"><p class="empty">{error || 'Loading…'}</p></section>;
  const trend = pivotTrend(data.usage_trend);

  return (
    <section class="panel">
      <div class="panel-head">
        <span class="ico"><BarIcon /></span>
        <div>
          <h2>AI Usage</h2>
          <p class="sub">Governance events — class, count, host, never prompt text.</p>
        </div>
        <span class="tag">{data.totals.events} events · {data.totals.active_employees} people</span>
      </div>
      <RangeSelector days={days} onChange={setDays} />
      {error && <p class="error">{error}</p>}
      <LineChart title="Usage trend by department" series={trend.series} />
      <Bars title="Top apps / domains" rows={data.top_apps.map((a) => ({ label: a.host, value: a.events }))} />
      <Bars title="Top employees" rows={data.top_employees.map((e) => ({ label: `${e.name} · ${e.department}`, value: e.events }))} />
    </section>
  );
}
