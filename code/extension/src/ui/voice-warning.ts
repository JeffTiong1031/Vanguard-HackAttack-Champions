export const VOICE_DATA_LEAK_WARNING =
  'Warning: This action might result in a data leak. Do you want to continue?';

const VOICE_START_LABEL =
  /\b(?:dictate|start dictation|start voice(?: mode)?|voice mode|use (?:the )?microphone)\b/i;
const VOICE_STOP_LABEL = /\b(?:stop|end|cancel|pause)\b/i;

function controlLabel(control: Element): string {
  return [
    control.getAttribute('aria-label'),
    control.getAttribute('title'),
    control.getAttribute('data-testid'),
    control.textContent,
  ].filter(Boolean).join(' ');
}

/** Detect provider controls that begin microphone capture, without matching a
 * control that stops an already-running voice session. */
function findVoiceStartControl(path: EventTarget[]): HTMLElement | null {
  const controls = new Set<HTMLElement>();

  for (const node of path) {
    if (!(node instanceof Element)) continue;
    const control = node.closest('button, [role="button"], input[type="button"]');
    if (control instanceof HTMLElement) controls.add(control);
  }

  return [...controls].find((control) => {
    const label = controlLabel(control);
    return VOICE_START_LABEL.test(label) && !VOICE_STOP_LABEL.test(label);
  }) ?? null;
}

export function isVoiceStartControl(path: EventTarget[]): boolean {
  return findVoiceStartControl(path) !== null;
}

type OpenDropdown = { host: HTMLElement; close: () => void };

function showVoiceDropdown(control: HTMLElement, onContinue: () => void): OpenDropdown {
  const host = document.createElement('div');
  host.setAttribute('data-vanguard-ui', 'voice-warning');
  const root = host.attachShadow({ mode: 'open' });
  const rect = control.getBoundingClientRect();
  const width = 320;
  const left = Math.max(12, Math.min(rect.right - width, window.innerWidth - width - 12));
  const top = Math.min(rect.bottom + 8, window.innerHeight - 160);

  host.style.cssText = [
    'position:fixed',
    `left:${left}px`,
    `top:${Math.max(12, top)}px`,
    'z-index:2147483647',
  ].join(';');

  root.innerHTML = `
    <style>
      :host { all: initial; }
      .dropdown {
        box-sizing: border-box; width: ${width}px; padding: 14px;
        border: 1px solid #f59e0b; border-radius: 10px; background: #fffbeb;
        color: #451a03; box-shadow: 0 12px 32px rgba(15, 23, 42, .22);
        font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif;
      }
      .title { margin: 0 0 5px; font-weight: 700; color: #92400e; }
      .message { margin: 0; }
      .actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px; }
      button {
        border: 1px solid #d97706; border-radius: 7px; padding: 7px 12px;
        background: white; color: #78350f; cursor: pointer; font: 600 13px system-ui;
      }
      button.continue { border-color: #b45309; background: #b45309; color: white; }
      button:focus-visible { outline: 2px solid #2563eb; outline-offset: 2px; }
    </style>
    <div class="dropdown" role="alertdialog" aria-labelledby="title" aria-describedby="message">
      <p class="title" id="title">Voice data-leak warning</p>
      <p class="message" id="message">${VOICE_DATA_LEAK_WARNING}</p>
      <div class="actions">
        <button type="button" class="cancel">Cancel</button>
        <button type="button" class="continue">Continue</button>
      </div>
    </div>
  `;

  const close = () => host.remove();
  root.querySelector<HTMLButtonElement>('.cancel')!.addEventListener('click', close);
  root.querySelector<HTMLButtonElement>('.continue')!.addEventListener('click', () => {
    close();
    onContinue();
  });
  (document.body || document.documentElement).append(host);
  root.querySelector<HTMLButtonElement>('.continue')!.focus();
  return { host, close };
}

export function installVoiceWarning(): () => void {
  const bypassOnce = new WeakSet<HTMLElement>();
  let open: OpenDropdown | null = null;

  const handler = (event: MouseEvent) => {
    if (event.eventPhase !== Event.CAPTURING_PHASE) return;
    const path = event.composedPath();

    if (open && !path.includes(open.host)) {
      open.close();
      open = null;
    }

    const control = findVoiceStartControl(path);
    if (!control) return;
    if (bypassOnce.has(control)) {
      bypassOnce.delete(control);
      return;
    }

    event.preventDefault();
    event.stopImmediatePropagation();
    open?.close();
    open = showVoiceDropdown(control, () => {
      open = null;
      bypassOnce.add(control);
      control.click();
    });
  };

  window.addEventListener('click', handler, { capture: true });
  return () => {
    window.removeEventListener('click', handler, { capture: true });
    open?.close();
    open = null;
  };
}
