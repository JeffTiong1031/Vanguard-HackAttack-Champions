// [verify all selectors against live chatgpt.com DOM]
import type { SurfaceAdapter } from './types';
const COMPOSER = ['#prompt-textarea', 'div[contenteditable="true"]'];
const SEND = ['button[data-testid="send-button"]', 'button[aria-label*="Send" i]'];
const EDITOR = 'textarea, input[type="text"], [contenteditable]:not([contenteditable="false"]), [role="textbox"]';

export const chatgptAdapter: SurfaceAdapter = {
  host: 'chatgpt.com',
  getComposer(path) {
    if (path) {
      for (const node of path) {
        if (node instanceof HTMLElement) {
          if (node.matches(EDITOR)) return node;
          // A click on "Save & Submit" originates on the button, not the edit
          // field. Its composed path still includes the local edit form/wrapper,
          // so resolve the field from that wrapper before falling back to the
          // page's new-message composer.
          if (node.tagName !== 'BODY' && node.tagName !== 'HTML') {
            const nested = node.querySelector<HTMLElement>(EDITOR);
            if (nested) return nested;
          }
        }
      }
    }
    const active = document.activeElement;
    if (active instanceof HTMLElement && active.matches(EDITOR)) {
      return active;
    }
    for (const s of COMPOSER) {
      const el = document.querySelector<HTMLElement>(s);
      if (el) return el;
    }
    return null;
  },
  readText(path) {
    const el = this.getComposer(path);
    if (!el) return null;
    if (el instanceof HTMLTextAreaElement || el instanceof HTMLInputElement) return el.value;
    return el.innerText ?? el.textContent ?? null;
  },
  writeText(text, target) {
    const el = target ?? this.getComposer();
    if (!el) return;
    el.focus();
    if (el instanceof HTMLTextAreaElement || el instanceof HTMLInputElement) {
      el.value = text;
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    } else {
      el.textContent = text;
      el.dispatchEvent(new InputEvent('input', { bubbles: true }));
      const r = document.createRange(); r.selectNodeContents(el); r.collapse(false);
      const sel = getSelection(); sel?.removeAllRanges(); sel?.addRange(r);
    }
  },
  isSendControl(path) {
    return path.some((n) => {
      if (!(n instanceof Element)) return false;
      if (SEND.some((s) => n.matches?.(s) || n.closest?.(s))) return true;
      if (n.tagName === 'BUTTON') {
        const text = n.textContent?.trim().toLowerCase() ?? '';
        const label = n.getAttribute('aria-label')?.toLowerCase() ?? '';
        const testid = n.getAttribute('data-testid')?.toLowerCase() ?? '';
        if (text === 'send' || text === 'save & submit' || text === 'save and submit' || text === 'save') return true;
        if (label.includes('send') || label.includes('submit') || label.includes('save')) return true;
        if (testid.includes('send') || testid.includes('submit')) return true;
      }
      return false;
    });
  },
  onPaste(cb) {
    document.addEventListener('paste', (e) => {
      const t = e.clipboardData?.getData('text'); if (t) cb(t);
    }, true);
  },
  fileInputs() { return [...document.querySelectorAll<HTMLInputElement>('input[type="file"]')]; },
};
