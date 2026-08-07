/**
 * The unapproved-tool banner.
 *
 * 🔴 It WARNS. It does not block. Spec section 7: "which tool you use is
 * advisory, what you ask it to do is blocking." The case study's own finding is
 * that outright bans push usage out of sight, and a blocked page sends the
 * employee to their phone, where we see nothing at all.
 */
import { explain } from '../detection/explanations';

const HOST_ATTR = 'data-vanguard-ui';

export type WarnBannerOptions = {
  toolName: string;
  orgName: string;
  onRequest: (reason: string) => Promise<void>;
  onDismiss: () => void;
};

export function hideWarnBanner(): void {
  updateBannerState = null;
  document.querySelector(`[${HOST_ATTR}="warn-banner"]`)?.remove();
}

let updateBannerState: ((mode: 'warn' | 'sent' | 'blocked', adminNote?: string) => void) | null = null;

export function updateWarnBanner(mode: 'warn' | 'sent' | 'blocked', adminNote?: string): void {
  updateBannerState?.(mode, adminNote);
}

export function showWarnBanner(options: WarnBannerOptions): void {
  hideWarnBanner();

  const host = document.createElement('div');
  host.setAttribute(HOST_ATTR, 'warn-banner');
  const root = host.attachShadow({ mode: 'open' });

  const style = document.createElement('style');
  style.textContent = `
    .backdrop {
      position: fixed; top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0, 0, 0, 0.75);
      backdrop-filter: blur(8px);
      z-index: 2147483646;
      display: flex; align-items: center; justify-content: center;
    }
    .modal {
      background: rgba(255, 255, 255, 0.95);
      border-radius: 16px;
      padding: 32px;
      max-width: 480px;
      width: 90%;
      box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5);
      font: 15px/1.5 system-ui, sans-serif;
      color: #1f2937;
      text-align: center;
    }
    .header { font-size: 20px; font-weight: 600; color: #b45309; margin-bottom: 12px; line-height: 1.3; }
    .desc { color: #4b5563; margin-bottom: 24px; font-size: 14px; }
    .note { 
      color: #991b1b; font-weight: 500; font-size: 14px; margin-bottom: 24px; 
      padding: 12px 16px; background: #fee2e2; border-radius: 8px; border: 1px solid #fca5a5;
    }
    .appeal-section { display: flex; flex-direction: column; gap: 16px; text-align: left; }
    .appeal-label { font-size: 14px; font-weight: 600; color: #374151; }
    textarea { 
      width: 100%; box-sizing: border-box; padding: 12px; border-radius: 8px; 
      border: 1px solid #d1d5db; font-size: 14px; resize: vertical; min-height: 80px;
      background: white; font-family: inherit;
    }
    textarea:focus { outline: none; border-color: #b45309; box-shadow: 0 0 0 3px rgba(180, 83, 9, 0.2); }
    textarea:disabled { background: #f3f4f6; color: #9ca3af; cursor: not-allowed; }
    button { 
      padding: 12px 24px; border: none; border-radius: 8px; background: #b45309; 
      color: white; font-weight: 600; font-size: 15px; cursor: pointer; transition: all 0.2s; 
    }
    button:hover:not(:disabled) { background: #92400e; transform: translateY(-1px); }
    button:disabled { background: #d1d5db; color: #6b7280; cursor: not-allowed; transform: none; }
  `;

  const backdrop = document.createElement('div');
  backdrop.className = 'backdrop';

  const modal = document.createElement('div');
  modal.className = 'modal';
  backdrop.append(modal);

  let currentReason = '';

  const render = (mode: 'warn' | 'sent' | 'blocked', adminNote?: string) => {
    modal.innerHTML = '';

    const header = document.createElement('div');
    header.className = 'header';
    header.textContent = `Vanguard is not supported in this website. Use it at your own risk.`;
    modal.append(header);

    const desc = document.createElement('div');
    desc.className = 'desc';
    desc.textContent = `(${options.toolName} is not approved at ${options.orgName}.)`;
    modal.append(desc);

    if (mode === 'blocked' && adminNote) {
      const note = document.createElement('div');
      note.className = 'note';
      note.innerHTML = `<strong>Request Rejected:</strong> ${adminNote}`;
      modal.append(note);
    }

    const appealSection = document.createElement('div');
    appealSection.className = 'appeal-section';

    const label = document.createElement('div');
    label.className = 'appeal-label';
    label.textContent = 'Request Approval';
    appealSection.append(label);

    const textarea = document.createElement('textarea');
    textarea.placeholder = 'Please explain your business need for this tool...';
    textarea.value = currentReason;
    if (mode === 'sent') textarea.disabled = true;
    textarea.addEventListener('input', (e) => {
      currentReason = (e.target as HTMLTextAreaElement).value;
    });
    appealSection.append(textarea);

    const btn = document.createElement('button');
    btn.textContent = mode === 'sent' ? 'Request Sent' : 'Submit Appeal';
    if (mode === 'sent') btn.disabled = true;
    
    btn.addEventListener('click', () => {
      if (!currentReason.trim()) return;
      btn.textContent = 'Sending...';
      btn.disabled = true;
      textarea.disabled = true;
      void options.onRequest(currentReason).then(() => render('sent'));
    });
    
    appealSection.append(btn);
    modal.append(appealSection);
  };

  updateBannerState = render;

  render('warn');
  root.append(style, backdrop);
  document.documentElement.append(host);
}
