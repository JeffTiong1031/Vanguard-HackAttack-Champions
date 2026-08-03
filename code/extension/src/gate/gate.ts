import type { VerdictCache } from '../detection/verdict-cache';

export function decideGate(a: { hash: string; cache: VerdictCache; approvedHash: string | null }): 'PASS' | 'BLOCK' {
  if (a.approvedHash === a.hash) return 'PASS';
  const v = a.cache.getSync(a.hash);
  if (!v) return 'BLOCK';               // cold cache -> modal resolves it
  return v.state === 'CLEAN' || v.state === 'ADVISORY' ? 'PASS' : 'BLOCK';
}

export type GateDeps = {
  cache: VerdictCache;
  getComposerText: (path: EventTarget[]) => string | null;
  isSendIntent: (e: Event, path: EventTarget[]) => boolean;
  hashOf: (text: string) => string;          // sync hash lookup memoized by the scanner
  approvedHash: () => string | null;
  /**
   * When true, block even on a CLEAN prompt. Held files were intercepted at
   * attach and the provider never received them — Send must hand them off
   * (reattach) first. Covers scanning, review, AND clean-checked files.
   */
  hasHeldFiles?: () => boolean;
  onBlocked: (text: string) => void;
};

/** True when the event originated inside our shadow UI (modal, hints popover). */
export function isVanguardUiPath(path: EventTarget[]): boolean {
  return path.some(
    (node) => node instanceof Element && node.hasAttribute('data-vanguard-ui'),
  );
}

/** True when focus is inside our UI (walks open shadow → host). */
export function isVanguardUiFocused(): boolean {
  const ae = document.activeElement;
  if (!(ae instanceof Element)) return false;
  let node: Node | null = ae;
  while (node) {
    if (node instanceof Element && node.hasAttribute('data-vanguard-ui')) return true;
    if (node instanceof ShadowRoot) {
      node = node.host;
      continue;
    }
    node = node.parentNode;
  }
  return false;
}

export function installGate(deps: GateDeps): void {
  const handler = (e: Event) => {
    if (e.eventPhase !== Event.CAPTURING_PHASE) return;
    if (e instanceof KeyboardEvent && e.isComposing) return; // U12-b: IME commit, not a send
    const path = e.composedPath();
    // Enter in Ignore / hint Accept must not be treated as Send (Claude live bug).
    // Keys typing into Ignore were landing in the composer because focus stayed on-page;
    // path + activeElement both needed (shadow retargeting).
    if (isVanguardUiPath(path) || isVanguardUiFocused()) return;
    if (!deps.isSendIntent(e, path)) return;
    const text = deps.getComposerText(path);
    if (text == null) return;
    // Files first: a clean prompt + clean file used to PASS the gate and send
    // with nothing attached (provider never got the intercept). Handoff lives
    // in onBlocked — including the no-modal path for all-clean files.
    if (deps.hasHeldFiles?.()) {
      e.stopImmediatePropagation();
      e.preventDefault();
      deps.onBlocked(text);
      return;
    }
    const decision = decideGate({ hash: deps.hashOf(text), cache: deps.cache, approvedHash: deps.approvedHash() });
    if (decision === 'BLOCK') {
      e.stopImmediatePropagation();
      e.preventDefault();
      deps.onBlocked(text);
    }
  };
  window.addEventListener('keydown', handler, { capture: true });
  window.addEventListener('click', handler, { capture: true });
  // Provider edit UIs may submit a form programmatically after their button
  // handler. Guard the cancellable submit event too, so DOM/button-label drift
  // cannot bypass the same text-hash decision.
  window.addEventListener('submit', handler, { capture: true });
}
