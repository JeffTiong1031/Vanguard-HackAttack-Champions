import { test, expect } from 'vitest';
import { pivotTrend, scalePoints } from './chart-helpers';

test('pivotTrend aligns departments to a shared sorted date axis and zero-fills gaps', () => {
  const { dates, series } = pivotTrend([
    { date: '2026-08-02', department: 'Eng', events: 3 },
    { date: '2026-08-01', department: 'Eng', events: 1 },
    { date: '2026-08-02', department: 'Sales', events: 5 },
  ]);
  expect(dates).toEqual(['2026-08-01', '2026-08-02']);
  const eng = series.find((s) => s.department === 'Eng')!;
  const sales = series.find((s) => s.department === 'Sales')!;
  expect(eng.points).toEqual([1, 3]);
  expect(sales.points).toEqual([0, 5]); // no event on 08-01 -> 0
});

test('scalePoints spreads x evenly and inverts y against the max', () => {
  const pts = scalePoints([0, 10], 100, 100, 10, 0); // pad 0, max 10
  expect(pts[0]).toEqual({ x: 0, y: 100 });   // value 0 -> bottom
  expect(pts[1]).toEqual({ x: 100, y: 0 });   // value 10 (=max) -> top
});

test('scalePoints centers a single point and never divides by zero', () => {
  const pts = scalePoints([5], 100, 100, 5, 0);
  expect(pts).toEqual([{ x: 50, y: 0 }]);
});
