import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const manifest = JSON.parse(
  readFileSync(resolve(__dirname, '../dist/chrome-mv3/manifest.json'), 'utf8'),
) as { host_permissions: string[]; permissions: string[] };

describe('manifest host_permissions', () => {
  // 🔴 A missing host permission does not raise. The fetch is blocked inside the offscreen
  // document, the model load never completes, every entity stays masked, and the user sees
  // "still blocked" — identical to the classifier disagreeing with them. That symptom had
  // three different causes in one session (no timeout, wrong bundle layout, missing
  // permission), so the invariant is pinned here rather than left to be rediscovered.

  it('covers both loopback spellings for every local port', () => {
    // 8765 (the local sensitivity model server) is retired — the classifier now loads from a
    // public hash-pinned repo (ADR 0029). The invariant is unchanged and still binds the Slice 2
    // backend on 8000: localhost and 127.0.0.1 are different origins for permission matching.
    const ports = [8000];
    for (const port of ports) {
      for (const host of ['localhost', '127.0.0.1']) {
        expect(
          manifest.host_permissions,
          `${host}:${port} — localhost and 127.0.0.1 are different origins for matching`,
        ).toContain(`http://${host}:${port}/*`);
      }
    }
  });

  it('still covers the two provider surfaces', () => {
    expect(manifest.host_permissions).toContain('https://chatgpt.com/*');
    expect(manifest.host_permissions).toContain('https://claude.ai/*');
  });

  it('does not request <all_urls> (ADR 0017 §6.2)', () => {
    expect(manifest.host_permissions).not.toContain('<all_urls>');
    expect(manifest.host_permissions.some((p) => p.includes('*://*/'))).toBe(false);
  });

  it('keeps permissions minimal — no webRequest', () => {
    expect(manifest.permissions).not.toContain('webRequest');
    expect(manifest.permissions).toEqual(
      expect.arrayContaining(['storage', 'offscreen', 'alarms', 'notifications']),
    );
  });
});

describe('offscreen model loading', () => {
  const offscreen = readFileSync(resolve(__dirname, '../entrypoints/offscreen/main.ts'), 'utf8');

  it('pins dtype explicitly for the sensitivity classifier', () => {
    // 🔴 transformers.js selects the FILE by dtype, and the default is per-device: cpu -> fp32,
    // wasm -> q8. Leaving it default in the browser asks for onnx/model_quantized.onnx, which
    // this bundle does not contain and must not — int8 of this model is degenerate
    // (always-KEEP). The result is a 404, a failed load, and every entity staying masked, which
    // is indistinguishable from the classifier disagreeing. Fourth cause of that one symptom.
    const call = offscreen.match(/pipeline<'text-classification'>\([\s\S]*?\)\;/)?.[0] ?? '';
    expect(call, 'sensitivity pipeline call not found').not.toBe('');
    expect(call, 'dtype must be explicit — wasm defaults to q8').toContain("dtype: 'fp32'");
  });

  it('keeps the NER on its pinned quantized dtype', () => {
    // The NER genuinely ships q8 and its file is pinned in models.manifest.json; only the
    // classifier needs fp32. Guard against a well-meaning sweep changing both.
    expect(offscreen).toContain("dtype: 'q8'");
  });
});

describe('the local model server is gone (ADR 0029)', () => {
  it('requests no permission for the retired :8765 model server', () => {
    expect(JSON.stringify(manifest.host_permissions)).not.toContain('8765');
  });

  it('needs no permission for the model host — remote weights already load without one', () => {
    expect(JSON.stringify(manifest.host_permissions)).not.toContain('huggingface');
  });
});
