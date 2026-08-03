// @vitest-environment jsdom
import { describe, it, expect } from 'vitest';
import { SessionNumbering } from '../src/mask/placeholder';
import {
  applyOneFinding,
  findingKey,
  hintFindings,
  L1_HINT_CLASSES,
  locateInDom,
  placeHintPopover,
  pruneDismissed,
  visibleHints,
} from '../src/ui/hint-logic';

describe('placeHintPopover', () => {
  const size = { width: 300, height: 180 };

  it('places the dropdown below when there is room', () => {
    expect(placeHintPopover(
      { top: 100, bottom: 120, left: 200 }, size, 800, 600,
    )).toEqual({ top: 128, left: 200, placement: 'below' });
  });

  it('flips above a composer near the bottom of the viewport', () => {
    expect(placeHintPopover(
      { top: 540, bottom: 560, left: 200 }, size, 800, 600,
    )).toEqual({ top: 352, left: 200, placement: 'above' });
  });

  it('opens above a lower-half composer even when the dropdown could fit below', () => {
    expect(placeHintPopover(
      { top: 500, bottom: 520, left: 200 }, { width: 300, height: 100 }, 800, 800,
    )).toEqual({ top: 392, left: 200, placement: 'above' });
  });

  it('clamps the dropdown horizontally at browser zoom and narrow edges', () => {
    expect(placeHintPopover(
      { top: 100, bottom: 120, left: 590 }, size, 640, 600,
    )).toEqual({ top: 128, left: 332, placement: 'below' });
  });
});

describe('hintFindings', () => {
  it('underlines L1 identifiers and email, never invents PERSON', () => {
    const text = 'IC 890101-14-5555 and alice@example.com';
    const findings = hintFindings(text);
    expect(findings.map((f) => f.cls).sort()).toEqual(['EMAIL', 'NRIC']);
    for (const f of findings) expect(L1_HINT_CLASSES.has(f.cls)).toBe(true);
  });

  it('does not underline ordinary arithmetic', () => {
    expect(hintFindings('what is 1+1 and year 2024')).toEqual([]);
  });
});

describe('dismiss + accept', () => {
  it('hides a dismissed span until prune drops stale keys', () => {
    const text = 'mail alice@example.com please';
    const [email] = hintFindings(text);
    expect(email).toBeTruthy();
    const key = findingKey(email!);
    expect(visibleHints(text, new Set([key]))).toEqual([]);
    expect(pruneDismissed('mail bob@example.com please', new Set([key])).size).toBe(0);
  });

  it('Accept rewrites only that span', () => {
    const text = 'IC 890101-14-5555 and alice@example.com';
    const findings = hintFindings(text);
    const nric = findings.find((f) => f.cls === 'NRIC')!;
    const numbering = new SessionNumbering();
    const out = applyOneFinding(text, nric, numbering);
    expect(out).toContain('NRIC_1');
    expect(out).toContain('alice@example.com');
    expect(out).not.toContain('890101-14-5555');
  });
});

describe('locateInDom', () => {
  it('uses offsets when they match, else searches the literal', () => {
    const f = hintFindings('hi alice@example.com')[0]!;
    expect(locateInDom('hi alice@example.com', f)).toEqual({
      start: f.start,
      end: f.end,
    });
    expect(locateInDom('zzzalice@example.com', f)).toEqual({
      start: 3,
      end: 3 + f.text.length,
    });
  });
});
