import { describe, it, expect, beforeEach } from 'vitest';

// Map-backed chrome.storage.local shim (same pattern as tests/policy-client.test.ts).
const store = new Map<string, unknown>();
(globalThis as any).chrome = {
  storage: { local: {
    get: async (k: string) => ({ [k]: store.get(k) }),
    set: async (o: Record<string, unknown>) => { for (const k in o) store.set(k, o[k]); },
  } },
};

import { capabilitiesFor, getMode, setMode, optionsView } from '../src/mode/mode';

describe('capabilitiesFor', () => {
  it('personal disables every org capability', () => {
    expect(capabilitiesFor('personal')).toEqual(
      { reporting: false, ethics: false, files: false, toolPolicy: false });
  });
  it('enterprise enables every capability', () => {
    expect(capabilitiesFor('enterprise')).toEqual(
      { reporting: true, ethics: true, files: true, toolPolicy: true });
  });
});

describe('getMode/setMode', () => {
  beforeEach(() => store.clear());
  it('returns null when unset', async () => {
    expect(await getMode()).toBeNull();
  });
  it('round-trips a stored mode', async () => {
    await setMode('enterprise');
    expect(await getMode()).toBe('enterprise');
  });
});

describe('optionsView', () => {
  it('routes null to the picker', () => { expect(optionsView(null)).toBe('picker'); });
  it('routes personal to personal', () => { expect(optionsView('personal')).toBe('personal'); });
  it('routes enterprise to enterprise', () => { expect(optionsView('enterprise')).toBe('enterprise'); });
});
