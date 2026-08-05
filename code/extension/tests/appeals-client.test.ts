// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { submitAppeal, grantPassIfAllowed } from '../src/policy/appeals';

function stubEnrolled() {
  const bag: Record<string, unknown> = {
    vg_enrolment: { org_id: 'o1', org_name: 'A', pseudo_id: 'p1', department: 'Eng' },
    vg_policy_base: 'http://localhost:8001',
  };
  vi.stubGlobal('chrome', {
    storage: { local: { get: async (k: string) => (k in bag ? { [k]: bag[k] } : {}) } },
  });
}

beforeEach(() => { stubEnrolled(); });

describe('submitAppeal', () => {
  it('sends class + reason and OMITS disclosed_text when not opted in', async () => {
    const fetchMock = vi.fn(async () => new Response('{"id":"a1","status":"pending"}', { status: 201 }));
    vi.stubGlobal('fetch', fetchMock);

    await submitAppeal({ decisionType: 'ethics', category: 'covert_surveillance', reason: 'defence' });

    const body = JSON.parse((fetchMock.mock.calls[0]![1] as RequestInit).body as string);
    expect(body).toEqual({
      pseudo_id: 'p1', decision_type: 'ethics', category: 'covert_surveillance', reason: 'defence',
    });
    // 🔴 the load-bearing privacy assertion
    expect('disclosed_text' in body).toBe(false);
  });

  it('includes disclosed_text only when provided', async () => {
    const fetchMock = vi.fn(async () => new Response('{"id":"a1","status":"pending"}', { status: 201 }));
    vi.stubGlobal('fetch', fetchMock);

    await submitAppeal({ decisionType: 'pii', category: 'NRIC', reason: 'product code', disclosedText: 'SKU 880101-14-5566' });

    const body = JSON.parse((fetchMock.mock.calls[0]![1] as RequestInit).body as string);
    expect(body.disclosed_text).toBe('SKU 880101-14-5566');
  });

  it('throws when not enrolled', async () => {
    vi.stubGlobal('chrome', { storage: { local: { get: async () => ({}) } } });
    vi.stubGlobal('fetch', vi.fn());
    await expect(submitAppeal({ decisionType: 'ethics', category: 'x', reason: 'y' })).rejects.toThrow(/enrol/i);
  });
});

describe('grantPassIfAllowed', () => {
  it('grants a pass when the prompt hash is in the approved scopes list', async () => {
    const urls: string[] = [];
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(String(url));
      return new Response('["hashA","hashB"]', { status: 200 });
    }));
    expect(await grantPassIfAllowed('hashA')).toBe(true);
    expect(urls.some((u) => u.includes('/approved-scopes'))).toBe(true);
    // No consume call — approval is persistent, not one-time-burn
    expect(urls.some((u) => u.includes('/consume'))).toBe(false);
  });

  it('does not grant a pass when the hash is not in the approved scopes list', async () => {
    const urls: string[] = [];
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(String(url));
      return new Response('["someOtherHash"]', { status: 200 });
    }));
    expect(await grantPassIfAllowed('hashA')).toBe(false);
    expect(urls.some((u) => u.includes('/consume'))).toBe(false);
  });
});
