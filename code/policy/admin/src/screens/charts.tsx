import { scalePoints } from './chart-helpers';
import type { AlertRow } from '../api';

const COLORS = ['#4f46e5', '#e11d48', '#059669', '#d97706', '#0891b2', '#7c3aed', '#db2777'];

/** Horizontal bar list — the console's existing style (moved out of Usage). */
export function Bars({ title, rows }: { title: string; rows: { label: string; value: number }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <div class="bars-group">
      <h3>{title}</h3>
      {rows.length === 0 && <p class="empty">No data yet.</p>}
      {rows.map((r) => (
        <div class="bar-row" key={r.label}>
          <span class="lbl">{r.label}</span>
          <span class="bar-track">
            <span class="bar-fill" style={`width:${Math.max(4, (r.value / max) * 100)}%`} />
          </span>
          <span class="val">{r.value}</span>
        </div>
      ))}
    </div>
  );
}

/** Multi-series inline-SVG line chart. All series share one y-scale (global max)
 *  so lines are comparable. */
export function LineChart({
  title, series, height = 140,
}: { title: string; series: { department: string; points: number[] }[]; height?: number }) {
  const width = 640;
  const globalMax = Math.max(1, ...series.flatMap((s) => s.points));
  const hasData = series.some((s) => s.points.length > 0);
  return (
    <div class="bars-group">
      <h3>{title}</h3>
      {!hasData && <p class="empty">No data yet.</p>}
      {hasData && (
        <>
          <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none"
               style="width:100%;height:160px;background:#f8fafc;border-radius:6px">
            {series.map((s, i) => {
              const pts = scalePoints(s.points, width, height, globalMax);
              const d = pts.map((p, j) => `${j === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
              return <path d={d} fill="none" stroke={COLORS[i % COLORS.length]} stroke-width="2" />;
            })}
          </svg>
          <div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:8px;font-size:12px;color:#475569">
            {series.map((s, i) => (
              <span style="display:inline-flex;align-items:center;gap:4px">
                <i style={`width:10px;height:10px;border-radius:2px;background:${COLORS[i % COLORS.length]}`} />
                {s.department}
              </span>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

const SEV_CLASS: Record<string, string> = { high: 'blocked', medium: 'revoked', low: 'active' };

export function AlertsTable({ rows }: { rows: AlertRow[] }) {
  if (rows.length === 0) return <p class="empty">No alerts in this window.</p>;
  return (
    <table>
      <thead><tr>
        <th>Time</th><th>Department</th><th>Employee</th><th>Tool</th>
        <th>Type</th><th>Action</th><th>Severity</th>
      </tr></thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>
            <td><code>{new Date(r.ts).toLocaleString()}</code></td>
            <td>{r.department}</td>
            <td><span class="name">{r.name}</span></td>
            <td><code>{r.host}</code></td>
            <td>{r.type}{r.category ? ` · ${r.category}` : ''}</td>
            <td>{r.action}</td>
            <td><span class={`pill ${SEV_CLASS[r.severity] ?? 'active'}`}>{r.severity}</span></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function RangeSelector({ days, onChange }: { days: number; onChange: (d: number) => void }) {
  return (
    <div style="display:flex;gap:8px;margin-bottom:12px">
      {[7, 30].map((d) => (
        <button class={days === d ? 'btn-primary btn-sm' : 'btn-sm'} onClick={() => onChange(d)}>
          Last {d} days
        </button>
      ))}
    </div>
  );
}
