// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { showEthicsModal, hideEthicsModal } from '../src/ui/ethics-modal';

function root(): ShadowRoot {
  return document.querySelector('[data-vanguard-ui="ethics-modal"]')!.shadowRoot!;
}

beforeEach(() => { document.body.innerHTML = ''; hideEthicsModal(); });

describe('ethics modal', () => {
  it('shows the plain-language why and the on-device note', () => {
    showEthicsModal({ label: 'Covert monitoring', category: 'covert_surveillance', orgName: 'Acme', onEdit: () => {}, onRequestReview: () => {} });
    const t = root().textContent!;
    expect(t.toLowerCase()).toContain('monitor');
    expect(t).toContain('on your device');
  });

  it('submits a review with the typed reason and no disclosed text by default', () => {
    const onRequestReview = vi.fn();
    showEthicsModal({ label: 'x', category: 'covert_surveillance', orgName: 'Acme', onEdit: () => {}, onRequestReview });
    root().querySelector<HTMLButtonElement>('[data-act="open-review"]')!.click();
    const reason = root().querySelector<HTMLTextAreaElement>('[data-act="reason"]')!;
    reason.value = 'defence not attack';
    reason.dispatchEvent(new Event('input'));
    root().querySelector<HTMLButtonElement>('[data-act="send-review"]')!.click();
    expect(onRequestReview).toHaveBeenCalledWith('defence not attack', undefined);
  });

  it('includes the prompt only when the opt-in box is ticked', () => {
    const onRequestReview = vi.fn();
    showEthicsModal({ label: 'x', category: 'covert_surveillance', orgName: 'Acme', promptText: 'the prompt', onEdit: () => {}, onRequestReview });
    root().querySelector<HTMLButtonElement>('[data-act="open-review"]')!.click();
    const reason = root().querySelector<HTMLTextAreaElement>('[data-act="reason"]')!;
    reason.value = 'r'; reason.dispatchEvent(new Event('input'));
    root().querySelector<HTMLInputElement>('[data-act="opt-in"]')!.click();
    root().querySelector<HTMLButtonElement>('[data-act="send-review"]')!.click();
    expect(onRequestReview).toHaveBeenCalledWith('r', 'the prompt');
  });

  it('renders My Reviews right panel with recent reviews, status, and reason', () => {
    showEthicsModal({
      label: 'Covert monitoring',
      category: 'covert_surveillance',
      orgName: 'Acme',
      reviews: [
        { category: 'covert_surveillance', status: 'pending', reason: 'defensive audit', admin_note: null },
        { category: 'exploit_code', status: 'approved', reason: 'security lab test', admin_note: 'Approved for security team' },
      ],
      onEdit: () => {},
      onRequestReview: () => {},
    });
    const t = root().textContent!;
    expect(t).toContain('My Reviews');
    expect(t).toContain('In Review');
    expect(t).toContain('Approved');
    expect(t).toContain('defensive audit');
    expect(t).toContain('Approved for security team');
  });
});
