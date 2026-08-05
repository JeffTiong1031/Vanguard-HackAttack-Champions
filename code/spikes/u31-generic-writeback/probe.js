// U31 MEASUREMENT INSTRUMENT — records observations, decides nothing.
// Ledger #10/#11: verdict strings in an analyser are where wrong answers come
// from. This file writes no verdict. A human reads the capture.

const MARKER = 'VG_U31_' + Math.random().toString(36).slice(2, 8);

function findComposer() {
  const active = document.activeElement;
  if (active instanceof HTMLTextAreaElement) return { el: active, kind: 'textarea' };
  if (active instanceof HTMLElement && active.isContentEditable) {
    return { el: active, kind: 'contenteditable' };
  }
  const ce = document.querySelector('[contenteditable="true"]');
  if (ce instanceof HTMLElement) return { el: ce, kind: 'contenteditable-query' };
  const ta = document.querySelector('textarea');
  if (ta instanceof HTMLTextAreaElement) return { el: ta, kind: 'textarea-query' };
  return null;
}

function readText(el) {
  return el instanceof HTMLTextAreaElement ? el.value : el.innerText;
}

// The technique under test: ask the browser to insert text through its own
// editing pipeline, so the site's framework sees a normal edit.
function genericWrite(el, text) {
  el.focus();
  document.execCommand('selectAll', false, undefined);
  return document.execCommand('insertText', false, text);
}

async function probe() {
  const found = findComposer();
  const capture = {
    marker: MARKER,
    host: location.hostname,
    at: new Date().toISOString(),
    composerFound: !!found,
    composerKind: found ? found.kind : null,
    before: null, execCommandReturned: null, readBack: null, matches: null,
    frameworkHint: Object.keys(found?.el ?? {}).filter((k) => k.startsWith('__react')).join(',') || null,
  };

  if (found) {
    capture.before = readText(found.el);
    capture.execCommandReturned = genericWrite(found.el, MARKER);
    // Two frames: a controlled editor reverts on its next render, and that
    // revert is precisely the signal we are here to observe.
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    capture.readBack = readText(found.el);
    capture.matches = capture.readBack.includes(MARKER);
  }

  console.log('[U31 CAPTURE]', JSON.stringify(capture, null, 2));
  return capture;
}

window.__vgU31 = probe;
console.log('[U31] loaded. Click into the composer, then run: await __vgU31()');
