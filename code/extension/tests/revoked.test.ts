import { describe, it, expect, beforeEach } from 'vitest';

const store = new Map<string, unknown>();
(globalThis as any).chrome = {
  storage: { local: {
    get: async (k: string) => ({ [k]: store.get(k) }),
    set: async (o: Record<string, unknown>) => { for (const k in o) store.set(k, o[k]); },
    remove: async (keys: string[]) => { for (const k of keys) store.delete(k); },
  } },
};

import { handleRevoked, REVOKED_MESSAGE } from '../src/policy/revoked';
import { getMode } from '../src/mode/mode';

describe('handleRevoked', () => {
  beforeEach(() => {
    store.clear();
    store.set('vg_mode', 'enterprise');
    store.set('vg_enrolment', { org_name: 'Acme', pseudo_id: 'p1' });
    store.set('vg_policy', { version: 3, tools: [] });
  });

  it('forces Personal mode', async () => {
    await handleRevoked();
    expect(await getMode()).toBe('personal');
  });

  it('clears the enrolment and the cached policy', async () => {
    await handleRevoked();
    expect(store.get('vg_enrolment')).toBeUndefined();
    expect(store.get('vg_policy')).toBeUndefined();
  });

  it('raises the notice flag so the user is told once', async () => {
    await handleRevoked();
    expect(store.get('vg_revoked_notice')).toBe(true);
  });

  it('names the personal plan in the message', () => {
    expect(REVOKED_MESSAGE).toContain('no longer connected');
    expect(REVOKED_MESSAGE).toContain('protecting you personally');
  });
});
