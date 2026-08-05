// U31 MEASUREMENT INSTRUMENT — records observations, decides nothing.
// Ledger #10/#11: verdict strings in an analyser are where wrong answers come
// from. This file writes no verdict. A human reads the capture.

const MARKER = 'VG_U31_' + Math.random().toString(36).slice(2, 8);

// Fix round 1, finding 1: invoking __vgU31() requires clicking into DevTools,
// which moves focus off the composer before probe() runs — so
// document.activeElement at call time is usually DevTools, not the composer.
// Remember the last text input actually focused on the page, before that
// happened, and prefer it over activeElement.
let lastFocused = null;
function isTextInput(el) {
  if (!(el instanceof HTMLElement)) return false;
  if (el instanceof HTMLTextAreaElement) return true;
  if (el instanceof HTMLInputElement && el.type === 'text') return true;
  return el.isContentEditable;
}
window.addEventListener('focusin', (e) => {
  if (isTextInput(e.target)) lastFocused = e.target;
}, true);

function findComposer() {
  if (lastFocused instanceof HTMLElement && lastFocused.isConnected) {
    return { el: lastFocused, kind: 'last-focused' };
  }
  const active = document.activeElement;
  if (active instanceof HTMLTextAreaElement) return { el: active, kind: 'active' };
  if (active instanceof HTMLElement && active.isContentEditable) {
    return { el: active, kind: 'active' };
  }
  const ce = document.querySelector('[contenteditable="true"]');
  if (ce instanceof HTMLElement) return { el: ce, kind: 'contenteditable-query' };
  const ta = document.querySelector('textarea');
  if (ta instanceof HTMLTextAreaElement) return { el: ta, kind: 'textarea-query' };
  return null;
}

function readText(el) {
  if (el instanceof HTMLTextAreaElement || el instanceof HTMLInputElement) return el.value;
  return el.innerText;
}

// Fix round 1, finding 3: nothing recorded which element was measured, so a
// wrong-element reading was unfalsifiable from the capture alone.
function describeElement(el) {
  const rect = el.getBoundingClientRect();
  return {
    tag: el.tagName.toLowerCase(),
    id: el.id || null,
    firstClass: el.classList.length ? el.classList[0] : null,
    width: Math.round(rect.width),
    height: Math.round(rect.height),
  };
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
    composerDescriptor: found ? describeElement(found.el) : null,
    before: null, execCommandReturned: null, readBack: null, matches: null,
    stillConnected: null,
    frameworkHint: Object.keys(found?.el ?? {}).filter((k) => k.startsWith('__react')).join(',') || null,
  };

  if (found) {
    capture.before = readText(found.el);
    capture.execCommandReturned = genericWrite(found.el, MARKER);
    // Two frames: a controlled editor reverts on its next render, and that
    // revert is precisely the signal we are here to observe.
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    // Fix round 1, finding 2: if the framework reverts by unmounting and
    // replacing the composer node rather than mutating it, the read-back
    // below happens on a detached node and can yield a misleading value.
    capture.stillConnected = found.el.isConnected;
    capture.readBack = readText(found.el);
    capture.matches = capture.readBack.includes(MARKER);
  }

  console.log('[U31 CAPTURE]', JSON.stringify(capture, null, 2));
  return capture;
}

window.__vgU31 = probe;
console.log('[U31] loaded. Click into the composer, then run: await __vgU31()');
