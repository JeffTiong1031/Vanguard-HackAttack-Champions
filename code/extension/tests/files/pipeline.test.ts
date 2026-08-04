import { describe, expect, it, vi } from 'vitest';
import { FileStore } from '../../src/files/store';
import { processFile } from '../../src/files/pipeline';
import { ExtractError } from '../../src/files/api';

const coverage = { read: ['file text'], not_read: [], pages_total: null, pages_with_text: null };

describe('processFile', () => {
  it('walks held -> extracting -> scanning -> scanned', async () => {
    const store = new FileStore();
    const id = store.add(new File(['x'], 'a.txt'));
    const seen: string[] = [];
    store.subscribe(() => seen.push(store.get(id)!.status.kind));

    await processFile(store, id, {
      extract: async () => ({
        extract: 'Ahmad 880101-14-5566', chars: 20, truncated: false,
        format: 'txt' as const, coverage, warnings: [],
      }),
      scan: async () => ({
        state: 'DIRTY' as const, complete: true,
        findings: [{ cls: 'NRIC' as const, start: 6, end: 20, text: '880101-14-5566' }],
      }),
    });

    expect(seen).toEqual(['extracting', 'scanning', 'scanned']);
    expect(store.get(id)!.findings).toHaveLength(1);
  });

  it('initialises one pending decision per finding', async () => {
    const store = new FileStore();
    const id = store.add(new File(['x'], 'a.txt'));
    await processFile(store, id, {
      extract: async () => ({
        extract: 'Ahmad 880101-14-5566', chars: 20, truncated: false,
        format: 'txt' as const, coverage, warnings: [],
      }),
      scan: async () => ({
        state: 'DIRTY' as const, complete: true,
        findings: [{ cls: 'NRIC' as const, start: 6, end: 20, text: '880101-14-5566' }],
      }),
    });
    expect(store.get(id)!.decisions!.size).toBe(1);
    expect(store.allResolved()).toBe(false);
  });

  it('stores the API error message verbatim for the user to read', async () => {
    const store = new FileStore();
    const id = store.add(new File(['x'], 'a.pdf'));
    await processFile(store, id, {
      extract: async () => { throw new ExtractError('no_text_layer', 'This PDF looks like a scan…'); },
      scan: async () => ({ state: 'CLEAN' as const, complete: true, findings: [] }),
    });
    expect(store.get(id)!.status).toMatchObject({
      kind: 'error', code: 'no_text_layer', message: 'This PDF looks like a scan…',
    });
  });

  it('does NOT mark a file clean when the on-device engine degraded', async () => {
    // ADR 0013/0014: an incomplete scan is advisory, never CLEAN. A file that
    // was never really checked must not read as checked.
    const store = new FileStore();
    const id = store.add(new File(['x'], 'a.txt'));
    await processFile(store, id, {
      extract: async () => ({
        extract: 'text', chars: 4, truncated: false, format: 'txt' as const, coverage, warnings: [],
      }),
      scan: async () => ({ state: 'ADVISORY' as const, complete: false, findings: [] }),
    });
    expect(store.get(id)!.status).toMatchObject({ kind: 'error', code: 'parse_failed' });
    expect(store.get(id)!.status.message).toContain('could not be fully checked');
  });

  it('surfaces truncation and coverage to the store for the UI to render', async () => {
    const store = new FileStore();
    const id = store.add(new File(['x'], 'a.pdf'));
    await processFile(store, id, {
      extract: async () => ({
        extract: 'body', chars: 4, truncated: true, format: 'pdf' as const,
        coverage: { read: ['text layer'], not_read: ['4 pages with no text layer (no OCR)'], pages_total: 10, pages_with_text: 6 },
        warnings: ['4 of 10 pages had no readable text (likely scans) and were not checked.'],
      }),
      scan: async () => ({ state: 'CLEAN' as const, complete: true, findings: [] }),
    });
    expect(store.get(id)!.coverage!.not_read).toEqual(['4 pages with no text layer (no OCR)']);
    expect(store.get(id)!.truncated).toBe(true);
  });

  it('processes image file with OCR extract format', async () => {
    const store = new FileStore();
    const id = store.add(new File(['fake image bytes'], 'screenshot.png', { type: 'image/png' }));
    await processFile(store, id, {
      extract: async () => ({
        extract: 'Confidential NRIC 880101-14-5566', chars: 32, truncated: false, format: 'image' as const,
        coverage: { read: ['OCR text layer'], not_read: [], pages_total: 1, pages_with_text: 1 },
        warnings: [],
      }),
      scan: async () => ({
        state: 'DIRTY' as const, complete: true,
        findings: [{ cls: 'NRIC' as const, start: 18, end: 32, text: '880101-14-5566' }],
      }),
    });
    expect(store.get(id)!.status.kind).toBe('scanned');
    expect(store.get(id)!.findings).toHaveLength(1);
    expect(store.get(id)!.findings![0].cls).toBe('NRIC');
  });
});
