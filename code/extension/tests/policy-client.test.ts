// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { enrol, refreshPolicy, sendAccessRequest } from '../src/policy/client';

const policy = {
  org_id: 'o1', org_name: 'Acme Corp', version: 1, tools: [], categories: [],
};

function mockStorage() {
  const bag: Record<string, unknown> = {};
  return {
    local: {
      get: async (k: string | string[]) => {
        const keys = Array.isArray(k) ? k : [k];
        return Object.fromEntries(keys.filter((x) => x in bag).map((x) => [x, bag[x]]));
      },
      set: async (o: Record<string, unknown>) => { Object.assign(bag, o); },
      remove: async (k: string | string[]) => {
        for (const x of Array.isArray(k) ? k : [k]) delete bag[x];
      },
    },
  };
}

beforeEach(() => {
  vi.stubGlobal('chrome', { storage: mockStorage() });
});

describe('enrol', () => {
  it('posts the token and persists what comes back', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({
      org_id: 'o1', org_name: 'Acme Corp', pseudo_id: 'p1',
      department: 'Engineering', policy,
    }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    const result = await enrol('ENG-abc');
    expect(result.department).toBe('Engineering');
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(String(url)).toContain('/v1/enroll');
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({ token: 'ENG-abc' });
  });

  it('throws a readable error on a bad token', async () => {
    vi.stubGlobal('fetch', async () => new Response('{}', { status: 401 }));
    await expect(enrol('nope')).rejects.toThrow(/not recognised/i);
  });
});

describe('refreshPolicy', () => {
  it('sends If-None-Match once an etag is known and keeps the cache on 304', async () => {
    const first = new Response(JSON.stringify(policy), {
      status: 200, headers: { etag: 'W/"o1-1"' },
    });
    // CORRECTED BY THE CONTROLLER (verified by execution in this repo's
    // vitest/jsdom): the plan wrote `new Response('', { status: 304 })`, which
    // THROWS "Response constructor: Invalid response status code 304" -- 304 is
    // a null-body status, so an empty-string body is still a body. `null` is
    // required. Use this line exactly as written.
    const second = new Response(null, { status: 304 });
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(first)
      .mockResolvedValueOnce(second);
    vi.stubGlobal('fetch', fetchMock);

    await chrome.storage.local.set({
      vg_enrolment: { org_id: 'o1', org_name: 'A', pseudo_id: 'p1', department: 'Eng' },
    });

    const a = await refreshPolicy();
    expect(a?.version).toBe(1);

    const b = await refreshPolicy();
    expect(b?.version).toBe(1); // unchanged, served from cache
    const headers = (fetchMock.mock.calls[1]![1] as RequestInit).headers as Record<string, string>;
    expect(headers['If-None-Match']).toBe('W/"o1-1"');
  });

  it('returns null when not enrolled instead of calling the network', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    expect(await refreshPolicy()).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('returns the cached policy when the network fails, so a dead service never blocks anyone', async () => {
    await chrome.storage.local.set({
      vg_enrolment: { org_id: 'o1', org_name: 'A', pseudo_id: 'p1', department: 'Eng' },
      vg_policy: policy,
    });
    vi.stubGlobal('fetch', async () => { throw new Error('offline'); });
    expect((await refreshPolicy())?.version).toBe(1);
  });

  it('returns the cached policy when the response is not OK, so a dead service never blocks anyone', async () => {
    await chrome.storage.local.set({
      vg_enrolment: { org_id: 'o1', org_name: 'A', pseudo_id: 'p1', department: 'Eng' },
      vg_policy: policy,
    });
    vi.stubGlobal('fetch', async () => new Response('{}', { status: 500 }));
    expect((await refreshPolicy())?.version).toBe(1);
  });

  it('sends department_id when the enrolment has one', async () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 304 }));
    vi.stubGlobal('fetch', fetchMock);
    await chrome.storage.local.set({
      vg_enrolment: {
        org_id: 'o1', org_name: 'A', pseudo_id: 'p1', department: 'Eng', department_id: 'dept1',
      },
    });

    await refreshPolicy();

    const url = String(fetchMock.mock.calls[0]![0]);
    expect(url).toContain('org_id=o1');
    expect(url).toContain('department_id=dept1');
  });
});

describe('sendAccessRequest', () => {
  it('includes the pseudo_id from storage, never a name', async () => {
    const fetchMock = vi.fn(async () => new Response('{"id":"r1"}', { status: 201 }));
    vi.stubGlobal('fetch', fetchMock);
    await chrome.storage.local.set({
      vg_enrolment: { org_id: 'o1', org_name: 'A', pseudo_id: 'p1', department: 'Eng' },
    });

    await sendAccessRequest('google', 'Translation QA');
    const body = JSON.parse((fetchMock.mock.calls[0]![1] as RequestInit).body as string);
    expect(body).toEqual({ pseudo_id: 'p1', llm_id: 'google', reason: 'Translation QA' });
  });

  it('throws when not enrolled', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    await expect(sendAccessRequest('google', 'Test')).rejects.toThrow('Not enrolled.');
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
