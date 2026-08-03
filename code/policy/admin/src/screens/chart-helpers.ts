export type TrendSeries = { dates: string[]; series: { department: string; points: number[] }[] };

/** Turn flat [{date, department, events}] rows into one aligned series per
 *  department over a shared, sorted date axis (missing days -> 0). */
export function pivotTrend(rows: { date: string; department: string; events: number }[]): TrendSeries {
  const dates = [...new Set(rows.map((r) => r.date))].sort();
  const byDept = new Map<string, Map<string, number>>();
  for (const r of rows) {
    if (!byDept.has(r.department)) byDept.set(r.department, new Map());
    byDept.get(r.department)!.set(r.date, r.events);
  }
  const series = [...byDept.entries()].map(([department, m]) => ({
    department,
    points: dates.map((d) => m.get(d) ?? 0),
  }));
  return { dates, series };
}

/** Map values to SVG coordinates: x evenly spaced across width, y inverted
 *  against `max` (default = the series max, floored at 1). A single point is
 *  centered. `pad` insets both axes. */
export function scalePoints(
  values: number[], width: number, height: number,
  max: number = Math.max(1, ...values), pad = 4,
): { x: number; y: number }[] {
  const n = values.length;
  const m = Math.max(1, max);
  const innerW = Math.max(1, width - pad * 2);
  const innerH = Math.max(1, height - pad * 2);
  return values.map((v, i) => ({
    x: pad + (n <= 1 ? innerW / 2 : (i / (n - 1)) * innerW),
    y: pad + innerH - (v / m) * innerH,
  }));
}
