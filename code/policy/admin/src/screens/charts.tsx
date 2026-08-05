import { scalePoints } from './chart-helpers';
import type { AlertRow } from '../api';
import type { JSX } from 'preact';

const SCHEME_COLORS: Record<string, string[]> = {
  crimson: ['#b91c1c', '#dc2626', '#ef4444'],
  cyan:    ['#0369a1', '#0284c7', '#38bdf8'],
  emerald: ['#047857', '#059669', '#10b981'],
  orange:  ['#c2410c', '#ea580c', '#f97316'],
  multi:   ['#b91c1c', '#c2410c', '#047857', '#0369a1', '#141413'],
};

export function StatCard({
  label,
  value,
  sub,
  icon: Icon,
  color = 'indigo',
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon: (props: JSX.SVGAttributes<SVGSVGElement>) => JSX.Element;
  color?: 'indigo' | 'emerald' | 'orange' | 'crimson' | 'cyan' | 'rose';
}) {
  const normColor = color === 'rose' ? 'crimson' : color;
  return (
    <div class={`stat-card stat-${normColor}`}>
      <div class={`stat-icon ${normColor}`}>
        <Icon />
      </div>
      <div class="stat-body">
        <div class="stat-label">{label}</div>
        <div class="stat-value">{value}</div>
        {sub && <div class="stat-sub">{sub}</div>}
      </div>
    </div>
  );
}

/** Horizontal bar list with custom color variants (crimson, cyan, emerald, orange) */
export function Bars({
  title,
  rows,
  variant = 'orange',
}: {
  title: string;
  rows: { label: string; value: number }[];
  variant?: 'crimson' | 'cyan' | 'emerald' | 'orange';
}) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <div class="bars-group">
      <h3>{title}</h3>
      {rows.length === 0 && <p class="empty">No data recorded yet.</p>}
      {rows.map((r) => {
        const percent = Math.round((r.value / max) * 100);
        return (
          <div class="bar-row" key={r.label}>
            <span class="lbl" title={r.label}>{r.label}</span>
            <span class="bar-track">
              <span class={`bar-fill ${variant}`} style={`width:${Math.max(4, percent)}%`} />
            </span>
            <span class="val">{r.value}</span>
          </div>
        );
      })}
    </div>
  );
}

/** Multi-series inline-SVG line chart with customizable color schemes and area gradient fills */
export function LineChart({
  title,
  series,
  labels = [],
  height = 140,
  scheme = 'multi',
}: {
  title: string;
  series: { department: string; points: number[] }[];
  labels?: string[];
  height?: number;
  scheme?: 'crimson' | 'cyan' | 'multi';
}) {
  const width = 640;
  const colors = SCHEME_COLORS[scheme] ?? SCHEME_COLORS.multi;
  const globalMax = Math.max(1, ...series.flatMap((s) => s.points));
  const hasData = series.some((s) => s.points.length > 0);
  const yTicks = [globalMax, Math.round(globalMax / 2), 0];
  const fmtDate = (d: string) => {
    if (!d) return '';
    if (d.length >= 13) {
      const datePart = d.slice(5, 10);
      const hourPart = d.slice(11, 13);
      return `${datePart} ${hourPart}:00`;
    }
    if (d.length >= 10) return d.slice(5, 10);
    return d;
  };
  const xTicks =
    labels.length === 0
      ? []
      : labels.length <= 4
        ? labels.map(fmtDate)
        : [labels[0], labels[Math.floor((labels.length - 1) / 3)], labels[Math.floor((2 * (labels.length - 1)) / 3)], labels[labels.length - 1]].map(fmtDate);

  const chartId = title.replace(/[^a-z0-9]/gi, '-').toLowerCase();
  const pad = 12;

  return (
    <div class="bars-group">
      <h3>{title}</h3>
      {!hasData && <p class="empty">No telemetry data recorded in this range.</p>}
      {hasData && (
        <>
          <div style="display:flex;gap:12px;align-items:flex-start">
            <div style="display:flex;flex-direction:column;justify-content:space-between;height:165px;padding:4px 0;min-width:32px;font-size:11px;font-weight:700;color:var(--ink-4);text-align:right;font-variant-numeric:tabular-nums">
              {yTicks.map((t, i) => <span key={i}>{t}</span>)}
            </div>
            <div style="flex:1;min-width:0">
              <div style="position:relative">
                <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none"
                     style="width:100%;height:165px;background:var(--panel);border:1px solid var(--line);border-radius:var(--r-lg);display:block">
                  <defs>
                    {series.map((_, i) => {
                      const color = colors[i % colors.length];
                      return (
                        <linearGradient id={`grad-${chartId}-${i}`} x1="0" y1="0" x2="0" y2="1" key={i}>
                          <stop offset="0%" stop-color={color} stop-opacity="0.25" />
                          <stop offset="100%" stop-color={color} stop-opacity="0.0" />
                        </linearGradient>
                      );
                    })}
                  </defs>
                  {[0.2, 0.5, 0.8].map((f) => (
                    <line key={f} x1="0" y1={(height * f).toFixed(1)} x2={width} y2={(height * f).toFixed(1)}
                          stroke="var(--line-soft)" stroke-width="1" stroke-dasharray="4 4" vector-effect="non-scaling-stroke" />
                  ))}
                  {series.map((s, i) => {
                    const pts = scalePoints(s.points, width, height, globalMax, pad);
                    if (pts.length === 0) return null;
                    const color = colors[i % colors.length];

                    let lineD = '';
                    let areaD = '';

                    if (pts.length === 1) {
                      const p = pts[0];
                      lineD = `M 0,${p.y.toFixed(1)} L ${width},${p.y.toFixed(1)}`;
                      areaD = `${lineD} L ${width},${height} L 0,${height} Z`;
                    } else {
                      lineD = pts.map((p, j) => `${j === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
                      areaD = `${lineD} L${pts[pts.length - 1].x.toFixed(1)},${height} L${pts[0].x.toFixed(1)},${height} Z`;
                    }

                    return (
                      <g key={s.department}>
                        <path d={areaD} fill={`url(#grad-${chartId}-${i})`} />
                        <path d={lineD} fill="none" stroke={color} stroke-width="2.5"
                              vector-effect="non-scaling-stroke" stroke-linejoin="round" stroke-linecap="round" />
                      </g>
                    );
                  })}
                </svg>
                {series.map((s, i) => {
                  const pts = scalePoints(s.points, width, height, globalMax, pad);
                  const color = colors[i % colors.length];
                  return pts.map((p, idx) => (
                    <span
                      key={`${s.department}-${idx}`}
                      style={{
                        position: 'absolute',
                        left: `${((p.x / width) * 100).toFixed(2)}%`,
                        top: `${((p.y / height) * 100).toFixed(2)}%`,
                        width: '10px',
                        height: '10px',
                        borderRadius: '50%',
                        backgroundColor: color,
                        border: '2px solid #ffffff',
                        boxShadow: '0 1px 4px rgba(20,20,19,0.18)',
                        transform: 'translate(-50%, -50%)',
                        pointerEvents: 'none',
                      }}
                    />
                  ));
                })}
              </div>
              {xTicks.length > 0 && (
                <div style="display:flex;justify-content:space-between;margin-top:6px;font-size:11px;font-weight:700;color:var(--ink-4);font-variant-numeric:tabular-nums">
                  {xTicks.map((t, i) => <span key={i}>{t}</span>)}
                </div>
              )}
            </div>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:14px;margin-top:12px;font-size:12.5px;font-weight:600;color:var(--ink-2)">
            {series.map((s, i) => (
              <span key={s.department} style="display:inline-flex;align-items:center;gap:6px">
                <i style={`width:10px;height:10px;border-radius:50%;background:${colors[i % colors.length]};box-shadow:0 0 0 2px rgba(255,255,255,0.8)`} />
                {s.department}
              </span>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

const SEV_CLASS: Record<string, string> = { high: 'blocked', medium: 'pending', low: 'active' };

export function AlertsTable({ rows }: { rows: AlertRow[] }) {
  if (rows.length === 0) return <p class="empty">No prompt activity or alerts recorded in this window.</p>;
  return (
    <div class="table-wrap" style="max-height:360px;overflow-y:auto">
      <table>
        <thead>
          <tr>
            <th style="position:sticky;top:0;background:var(--panel-muted);z-index:1">Timestamp</th>
            <th style="position:sticky;top:0;background:var(--panel-muted);z-index:1">Department</th>
            <th style="position:sticky;top:0;background:var(--panel-muted);z-index:1">Employee</th>
            <th style="position:sticky;top:0;background:var(--panel-muted);z-index:1">Tool Host</th>
            <th style="position:sticky;top:0;background:var(--panel-muted);z-index:1">Event Category</th>
            <th style="position:sticky;top:0;background:var(--panel-muted);z-index:1">Policy Action</th>
            <th style="position:sticky;top:0;background:var(--panel-muted);z-index:1">Severity</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td><code>{new Date(r.ts).toLocaleString()}</code></td>
              <td><strong>{r.department}</strong></td>
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
  const options = [
    { days: 1, label: '24 Hours (Hourly)' },
    { days: 7, label: 'Last 7 days' },
    { days: 30, label: 'Last 30 days' },
  ];
  return (
    <div style="display:flex;gap:6px">
      {options.map((opt) => (
        <button
          key={opt.days}
          class={days === opt.days ? 'filter-btn active' : 'filter-btn'}
          onClick={() => onChange(opt.days)}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
