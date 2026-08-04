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
 *  so lines are comparable. Axis labels are HTML (not <text>): the SVG stretches
 *  with `preserveAspectRatio="none"`, which would distort any text drawn inside
 *  it, so the y ticks sit in a column beside the plot and the x ticks below. */
export function LineChart({
  title, series, labels = [], height = 140,
}: {
  title: string;
  series: { department: string; points: number[] }[];
  labels?: string[];
  height?: number;
}) {
  const width = 640;
  const globalMax = Math.max(1, ...series.flatMap((s) => s.points));
  const hasData = series.some((s) => s.points.length > 0);
  const yTicks = [globalMax, Math.round(globalMax / 2), 0];
  const fmtDate = (d: string) => (d && d.length >= 10 ? d.slice(5) : d); // ISO -> MM-DD
  const xTicks =
    labels.length === 0
      ? []
      : labels.length <= 3
        ? labels.map(fmtDate)
        : [labels[0], labels[Math.floor((labels.length - 1) / 2)], labels[labels.length - 1]].map(fmtDate);

  return (
    <div class="bars-group">
      <h3>{title}</h3>
      {!hasData && <p class="empty">No data yet.</p>}
      {hasData && (
        <>
          <div style="display:flex;gap:8px">
            <div style="display:flex;flex-direction:column;justify-content:space-between;height:160px;padding:2px 0;min-width:30px;font-size:11px;color:#94a3b8;text-align:right;font-variant-numeric:tabular-nums">
              {yTicks.map((t, i) => <span key={i}>{t}</span>)}
            </div>
            <div style="flex:1;min-width:0">
              <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none"
                   style="width:100%;height:160px;background:#f8fafc;border-radius:6px;display:block">
                {[0.25, 0.5, 0.75].map((f) => (
                  <line x1="0" y1={(height * f).toFixed(1)} x2={width} y2={(height * f).toFixed(1)}
                        stroke="#e2e8f0" stroke-width="1" vector-effect="non-scaling-stroke" />
                ))}
                {series.map((s, i) => {
                  const pts = scalePoints(s.points, width, height, globalMax);
                  const d = pts.map((p, j) => `${j === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
                  return <path d={d} fill="none" stroke={COLORS[i % COLORS.length]} stroke-width="2"
                               vector-effect="non-scaling-stroke" />;
                })}
              </svg>
              {xTicks.length > 0 && (
                <div style="display:flex;justify-content:space-between;margin-top:4px;font-size:11px;color:#94a3b8;font-variant-numeric:tabular-nums">
                  {xTicks.map((t, i) => <span key={i}>{t}</span>)}
                </div>
              )}
            </div>
          </div>
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
  // Sticky header needs an opaque background so scrolled rows don't show through.
  const stickyTh = 'position:sticky;top:0;background:var(--panel);padding-top:10px;z-index:1';
  return (
    <div style="max-height:320px;overflow-y:auto;border:1px solid var(--line-soft);border-radius:8px">
    <table>
      <thead><tr>
        <th style={stickyTh}>Time</th><th style={stickyTh}>Department</th><th style={stickyTh}>Employee</th>
        <th style={stickyTh}>Tool</th><th style={stickyTh}>Type</th><th style={stickyTh}>Action</th>
        <th style={stickyTh}>Severity</th>
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
    </div>
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
