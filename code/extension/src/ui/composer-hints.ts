import type { Finding } from '../detection/l1/types';
import type { SessionNumbering } from '../mask/placeholder';
import {
  applyOneFinding,
  findingKey,
  locateInDom,
  placeHintPopover,
  pruneDismissed,
  rangeFromOffsets,
  recommendationFor,
  visibleHints,
  whyFor,
} from './hint-logic';

const STYLE = `
:host { all: initial; }
.layer { position: fixed; inset: 0; pointer-events: none; z-index: 2147483646; }
.mark {
  position: absolute;
  pointer-events: auto;
  height: 3.5px;
  background: #e11d48;
  border-radius: 2px;
  opacity: 0;
  animation: vgFade 120ms ease-out forwards;
  cursor: pointer;
  box-shadow: 0 0 0 3px rgba(225, 29, 72, 0.18);
}
.mark:hover, .mark[data-active="1"] { background: #be123c; height: 4px; box-shadow: 0 0 0 4px rgba(225, 29, 72, 0.28); }
@keyframes vgFade { from { opacity: 0; } to { opacity: 1; } }
.popover {
  position: absolute;
  pointer-events: auto;
  width: 300px;
  max-width: calc(100vw - 16px);
  box-sizing: border-box;
  background: #fff;
  color: #0f172a;
  border: 1px solid #fecdd3;
  border-radius: 10px;
  box-shadow: 0 12px 32px rgba(225, 29, 72, 0.18);
  padding: 12px 14px;
  font: 13px/1.4 "Segoe UI", system-ui, -apple-system, sans-serif;
  animation: vgPop 200ms cubic-bezier(0.34, 1.56, 0.64, 1);
  z-index: 1;
}
@keyframes vgPop {
  from { opacity: 0; transform: translateY(4px) scale(0.96); }
  to { opacity: 1; transform: none; }
}
.cls {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #e11d48;
  text-transform: uppercase;
  margin-bottom: 6px;
}
.why { margin: 0 0 8px; color: #0f172a; }
.rec {
  font-family: ui-monospace, Consolas, monospace;
  font-size: 13px;
  background: #f1f5f9;
  padding: 8px 10px;
  border-radius: 6px;
  margin-bottom: 12px;
}
.actions { display: flex; gap: 8px; }
button {
  flex: 1;
  border-radius: 6px;
  padding: 8px 12px;
  font: 600 13px "Segoe UI", system-ui, sans-serif;
  cursor: pointer;
}
button.primary {
  border: none;
  background: #e11d48;
  color: #fff;
}
button.secondary {
  border: 1px solid #fecdd3;
  background: transparent;
  color: #9f1239;
}
`;

export type ComposerHintsDeps = {
  numbering: SessionNumbering;
  /** Called after Accept rewrites the composer text. */
  onRewrite: (rewritten: string) => void;
};

export type ComposerHints = {
  attach: (composer: HTMLElement | null) => void;
  update: (text: string) => void;
  clear: () => void;
  destroy: () => void;
};

export function createComposerHints(deps: ComposerHintsDeps): ComposerHints {
  let host: HTMLElement | null = null;
  let shadow: ShadowRoot | null = null;
  let layer: HTMLElement | null = null;
  let composer: HTMLElement | null = null;
  let dismissed = new Set<string>();
  let lastText = '';
  let openKey: string | null = null;
  let hideTimer: ReturnType<typeof setTimeout> | null = null;

  const ensureHost = () => {
    if (host) return;
    host = document.createElement('div');
    host.setAttribute('data-vanguard-ui', 'hints');
    host.style.cssText = 'position:fixed;inset:0;z-index:2147483646;pointer-events:none';
    shadow = host.attachShadow({ mode: 'closed' });
    const style = document.createElement('style');
    style.textContent = STYLE;
    layer = document.createElement('div');
    layer.className = 'layer';
    shadow.append(style, layer);
    (document.body || document.documentElement).appendChild(host);
  };

  const clearMarks = () => {
    if (!layer) return;
    layer.replaceChildren();
    openKey = null;
  };

  const hidePopoverSoon = () => {
    if (hideTimer) clearTimeout(hideTimer);
    hideTimer = setTimeout(() => {
      openKey = null;
      paint();
    }, 180);
  };

  const cancelHide = () => {
    if (hideTimer) {
      clearTimeout(hideTimer);
      hideTimer = null;
    }
  };

  const showPopover = (finding: Finding, anchor: DOMRect) => {
    if (!layer || !shadow) return;
    cancelHide();
    openKey = findingKey(finding);
    const existing = layer.querySelector('.popover');
    existing?.remove();

    const pop = document.createElement('div');
    pop.className = 'popover';
    pop.setAttribute('role', 'dialog');
    pop.setAttribute('aria-label', 'Privacy tip');

    const cls = document.createElement('div');
    cls.className = 'cls';
    cls.textContent = finding.cls;

    const why = document.createElement('p');
    why.className = 'why';
    why.textContent = whyFor(finding.cls);

    const rec = document.createElement('div');
    rec.className = 'rec';
    rec.textContent = `Recommend: ${recommendationFor(finding, deps.numbering)}`;

    const actions = document.createElement('div');
    actions.className = 'actions';

    const accept = document.createElement('button');
    accept.type = 'button';
    accept.className = 'primary';
    accept.textContent = 'Accept';
    accept.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      const rewritten = applyOneFinding(lastText, finding, deps.numbering);
      dismissed.delete(findingKey(finding));
      openKey = null;
      deps.onRewrite(rewritten);
    });

    const dismiss = document.createElement('button');
    dismiss.type = 'button';
    dismiss.className = 'secondary';
    dismiss.textContent = 'Dismiss';
    dismiss.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      dismissed.add(findingKey(finding));
      openKey = null;
      paint();
    });

    actions.append(accept, dismiss);
    pop.append(cls, why, rec, actions);

    pop.addEventListener('mouseenter', cancelHide);
    pop.addEventListener('mouseleave', hidePopoverSoon);

    // It must be in the shadow tree before it has a measurable rendered size.
    // Keep it invisible for that first layout so users never see it jump from
    // below the composer to its final (usually above) position.
    pop.style.visibility = 'hidden';
    layer.appendChild(pop);
    const measured = pop.getBoundingClientRect();
    const position = placeHintPopover(
      anchor,
      { width: measured.width || 300, height: measured.height || 180 },
      window.innerWidth,
      window.innerHeight,
    );
    pop.style.top = `${position.top}px`;
    pop.style.left = `${position.left}px`;
    pop.setAttribute('data-placement', position.placement);
    pop.style.visibility = 'visible';

    for (const mark of layer.querySelectorAll('.mark')) {
      mark.setAttribute('data-active', mark.getAttribute('data-key') === openKey ? '1' : '0');
    }
  };

  const paint = () => {
    if (!composer || !layer) {
      clearMarks();
      return;
    }
    ensureHost();
    dismissed = pruneDismissed(lastText, dismissed);
    const findings = visibleHints(lastText, dismissed);
    const content = composer.textContent ?? '';

    const keepPopover = openKey && findings.some((f) => findingKey(f) === openKey);
    layer.replaceChildren();
    if (!keepPopover) openKey = null;

    for (const finding of findings) {
      const loc = locateInDom(content, finding);
      if (!loc) continue;
      const range = rangeFromOffsets(composer, loc.start, loc.end);
      if (!range) continue;
      let rects: DOMRectList | DOMRect[];
      try {
        rects = range.getClientRects();
      } catch {
        continue;
      }
      const key = findingKey(finding);
      for (let i = 0; i < rects.length; i++) {
        const r = rects[i]!;
        if (r.width < 1 || r.height < 1) continue;
        const mark = document.createElement('div');
        mark.className = 'mark';
        mark.setAttribute('data-key', key);
        mark.setAttribute('data-active', openKey === key ? '1' : '0');
        mark.style.left = `${r.left}px`;
        mark.style.top = `${r.bottom - 1}px`;
        mark.style.width = `${r.width}px`;
        mark.title = whyFor(finding.cls);
        mark.addEventListener('mouseenter', () => showPopover(finding, r));
        mark.addEventListener('mouseleave', hidePopoverSoon);
        layer!.appendChild(mark);
      }
    }

    if (openKey) {
      const still = findings.find((f) => findingKey(f) === openKey);
      if (still) {
        const loc = locateInDom(content, still);
        if (loc) {
          const range = rangeFromOffsets(composer, loc.start, loc.end);
          const r = range?.getBoundingClientRect();
          if (r && r.width > 0) showPopover(still, r);
        }
      }
    }
  };

  const onScrollOrResize = () => paint();

  return {
    attach(next) {
      if (composer === next) return;
      composer = next;
      ensureHost();
      window.addEventListener('scroll', onScrollOrResize, true);
      window.addEventListener('resize', onScrollOrResize);
      paint();
    },
    update(text) {
      lastText = text;
      paint();
    },
    clear() {
      lastText = '';
      dismissed.clear();
      clearMarks();
    },
    destroy() {
      window.removeEventListener('scroll', onScrollOrResize, true);
      window.removeEventListener('resize', onScrollOrResize);
      if (hideTimer) clearTimeout(hideTimer);
      host?.remove();
      host = null;
      shadow = null;
      layer = null;
      composer = null;
    },
  };
}
