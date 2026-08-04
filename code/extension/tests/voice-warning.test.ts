// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  installVoiceWarning,
  isVoiceStartControl,
  VOICE_DATA_LEAK_WARNING,
} from '../src/ui/voice-warning';

afterEach(() => {
  document.body.innerHTML = '';
});

describe('voice data-leak warning', () => {
  it.each(['Dictate', 'Start voice', 'Start voice mode', 'Use microphone'])(
    'recognises the %s control',
    (label) => {
      const button = document.createElement('button');
      button.setAttribute('aria-label', label);
      const icon = document.createElement('span');
      button.append(icon);
      expect(isVoiceStartControl([icon, button, document.body])).toBe(true);
    },
  );

  it('does not warn for stop voice or unrelated controls', () => {
    const stop = document.createElement('button');
    stop.setAttribute('aria-label', 'Stop voice mode');
    const send = document.createElement('button');
    send.setAttribute('aria-label', 'Send message');
    expect(isVoiceStartControl([stop])).toBe(false);
    expect(isVoiceStartControl([send])).toBe(false);
  });

  it('shows the required warning in a dropdown and cancels voice', () => {
    const remove = installVoiceWarning();
    const providerClick = vi.fn();
    const button = document.createElement('button');
    button.setAttribute('aria-label', 'Dictate');
    button.addEventListener('click', providerClick);
    document.body.append(button);

    const allowed = button.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));

    expect(allowed).toBe(false);
    expect(providerClick).not.toHaveBeenCalled();
    const host = document.querySelector<HTMLElement>('[data-vanguard-ui="voice-warning"]')!;
    expect(host.shadowRoot?.textContent).toContain(VOICE_DATA_LEAK_WARNING);

    host.shadowRoot?.querySelector<HTMLButtonElement>('.cancel')?.click();
    expect(document.querySelector('[data-vanguard-ui="voice-warning"]')).toBeNull();
    expect(providerClick).not.toHaveBeenCalled();
    remove();
  });

  it('continues the original voice action once when Continue is selected', () => {
    const remove = installVoiceWarning();
    const providerClick = vi.fn();
    const button = document.createElement('button');
    button.setAttribute('title', 'Start voice');
    button.addEventListener('click', providerClick);
    document.body.append(button);

    button.click();
    const host = document.querySelector<HTMLElement>('[data-vanguard-ui="voice-warning"]')!;
    host.shadowRoot?.querySelector<HTMLButtonElement>('.continue')?.click();

    expect(providerClick).toHaveBeenCalledOnce();
    expect(document.querySelector('[data-vanguard-ui="voice-warning"]')).toBeNull();
    remove();
  });
});
