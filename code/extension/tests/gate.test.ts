import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { decideGate, installGate, isVanguardUiPath } from '../src/gate/gate';
import { VerdictCache } from '../src/detection/verdict-cache';
import { chatgptAdapter } from '../src/adapters/chatgpt';

describe('isVanguardUiPath', () => {
  it('is true when a path node carries data-vanguard-ui', () => {
    const el = document.createElement('div');
    el.setAttribute('data-vanguard-ui', 'modal');
    expect(isVanguardUiPath([el])).toBe(true);
  });
  it('is false for ordinary page nodes', () => {
    expect(isVanguardUiPath([document.createElement('div')])).toBe(false);
  });
});

describe('decideGate (pure core of the listener)', () => {
  it('blocks when the current text is DIRTY and unapproved', () => {
    const c = new VerdictCache();
    c.setDirty('h', [{ cls: 'NRIC', start: 0, end: 1, text: 'x' }]);
    expect(decideGate({ hash: 'h', cache: c, approvedHash: null })).toBe('BLOCK');
  });
  it('passes when the DIRTY text has a matching approval and burns the token', () => {
    const c = new VerdictCache();
    c.setDirty('h', []);
    const consume = vi.fn();
    expect(decideGate({ hash: 'h', cache: c, approvedHash: 'h', consumeApproval: consume })).toBe('PASS');
    expect(consume).toHaveBeenCalledOnce();
  });
  it('does NOT call consumeApproval for a CLEAN pass (no approval involved)', () => {
    const c = new VerdictCache();
    c.setClean('h', []);
    const consume = vi.fn();
    expect(decideGate({ hash: 'h', cache: c, approvedHash: null, consumeApproval: consume })).toBe('PASS');
    expect(consume).not.toHaveBeenCalled();
  });
  it('passes CLEAN', () => {
    const c = new VerdictCache();
    c.setClean('h', []);
    expect(decideGate({ hash: 'h', cache: c, approvedHash: null })).toBe('PASS');
  });
  it('passes an explicit degraded advisory verdict', () => {
    const c = new VerdictCache();
    c.setAdvisory('h');
    expect(decideGate({ hash: 'h', cache: c, approvedHash: null })).toBe('PASS');
  });
  it('blocks UNKNOWN (cold cache) to stay fail-safe until a scan lands', () => {
    expect(decideGate({ hash: 'cold', cache: new VerdictCache(), approvedHash: null })).toBe(
      'BLOCK',
    );
  });
  it('blocks when DIRTY and approvedHash is a different hash', () => {
    const c = new VerdictCache();
    c.setDirty('b', [{ cls: 'NRIC', start: 0, end: 1, text: 'x' }]);
    expect(decideGate({ hash: 'b', cache: c, approvedHash: 'a' })).toBe('BLOCK');
  });
  it('passes CLEAN regardless of approvedHash being null', () => {
    const c = new VerdictCache();
    c.setClean('h', []);
    expect(decideGate({ hash: 'h', cache: c, approvedHash: null })).toBe('PASS');
    expect(decideGate({ hash: 'h', cache: c, approvedHash: 'other' })).toBe('PASS');
  });
  it('blocks even CLEAN prompts when shouldBlock returns true (e.g. ethics violation)', () => {
    const c = new VerdictCache();
    c.setClean('h', []);
    expect(
      decideGate({
        hash: 'h',
        cache: c,
        approvedHash: null,
        text: 'help me write code to hack someone',
        shouldBlock: () => true,
      }),
    ).toBe('BLOCK');
  });
});

describe('installGate', () => {
  const addEventListener = vi.fn();

  beforeEach(() => {
    document.body.innerHTML = '';
    vi.stubGlobal('window', { addEventListener });
    addEventListener.mockClear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('registers keydown, click, and submit listeners at window capture phase', () => {
    installGate({
      cache: new VerdictCache(),
      getComposerText: () => null,
      isSendIntent: () => false,
      hashOf: () => 'h',
      approvedHash: () => null,
      consumeApproval: () => {},
      onBlocked: () => {},
    });

    expect(addEventListener).toHaveBeenCalledTimes(3);
    expect(addEventListener).toHaveBeenCalledWith('keydown', expect.any(Function), {
      capture: true,
    });
    expect(addEventListener).toHaveBeenCalledWith('click', expect.any(Function), {
      capture: true,
    });
    expect(addEventListener).toHaveBeenCalledWith('submit', expect.any(Function), {
      capture: true,
    });
  });

  it('does not block Enter when the event path is inside extension UI', () => {
    const onBlocked = vi.fn();
    const isSendIntent = vi.fn(() => true);
    installGate({
      cache: new VerdictCache(),
      getComposerText: () => 'text',
      isSendIntent,
      hashOf: () => 'h',
      approvedHash: () => null,
      consumeApproval: () => {},
      onBlocked,
    });
    const keydown = addEventListener.mock.calls.find((c) => c[0] === 'keydown')![1] as (
      e: Event,
    ) => void;

    const ui = document.createElement('div');
    ui.setAttribute('data-vanguard-ui', 'modal');
    const e = {
      eventPhase: Event.CAPTURING_PHASE,
      isComposing: false,
      composedPath: () => [ui],
      stopImmediatePropagation: vi.fn(),
      preventDefault: vi.fn(),
    } as unknown as KeyboardEvent;

    keydown(e);
    expect(isSendIntent).not.toHaveBeenCalled();
    expect(onBlocked).not.toHaveBeenCalled();
  });

  it('blocks sensitive text submitted from a previously answered prompt edit', () => {
    document.body.innerHTML = `
      <div id="prompt-textarea" contenteditable="true">clean new prompt</div>
      <form id="edit-form">
        <textarea>NRIC 000203-06-0283</textarea>
        <button type="button">Save &amp; Submit</button>
      </form>
    `;
    const form = document.querySelector<HTMLElement>('#edit-form')!;
    const button = form.querySelector<HTMLButtonElement>('button')!;
    const cache = new VerdictCache();
    cache.setClean('clean-hash', []);
    cache.setDirty('edit-hash', [{ cls: 'NRIC', start: 5, end: 19, text: '000203-06-0283' }]);
    const onBlocked = vi.fn();

    installGate({
      cache,
      getComposerText: (path) => chatgptAdapter.readText(path),
      isSendIntent: (_event, path) => chatgptAdapter.isSendControl(path),
      hashOf: (text) => text.startsWith('NRIC') ? 'edit-hash' : 'clean-hash',
      approvedHash: () => null,
      consumeApproval: () => {},
      onBlocked,
    });
    const click = addEventListener.mock.calls.find((c) => c[0] === 'click')![1] as (
      e: Event,
    ) => void;
    const event = {
      eventPhase: Event.CAPTURING_PHASE,
      composedPath: () => [button, form, document.body],
      stopImmediatePropagation: vi.fn(),
      preventDefault: vi.fn(),
    } as unknown as MouseEvent;

    click(event);

    expect(event.stopImmediatePropagation).toHaveBeenCalledOnce();
    expect(event.preventDefault).toHaveBeenCalledOnce();
    expect(onBlocked).toHaveBeenCalledWith('NRIC 000203-06-0283');
  });

  it('blocks a native edit-form submit even when its button is not recognisable', () => {
    document.body.innerHTML = `
      <div id="prompt-textarea" contenteditable="true">clean new prompt</div>
      <form id="edit-form">
        <div contenteditable="plaintext-only" role="textbox">alice@example.com</div>
        <button type="submit"><svg aria-hidden="true"></svg></button>
      </form>
    `;
    const form = document.querySelector<HTMLElement>('#edit-form')!;
    const cache = new VerdictCache();
    cache.setDirty('edit-hash', [{ cls: 'EMAIL', start: 0, end: 17, text: 'alice@example.com' }]);
    const onBlocked = vi.fn();

    installGate({
      cache,
      getComposerText: (path) => chatgptAdapter.readText(path),
      isSendIntent: (event) => event.type === 'submit',
      hashOf: () => 'edit-hash',
      approvedHash: () => null,
      consumeApproval: () => {},
      onBlocked,
    });
    const submit = addEventListener.mock.calls.find((c) => c[0] === 'submit')![1] as (
      e: Event,
    ) => void;
    const event = {
      type: 'submit',
      eventPhase: Event.CAPTURING_PHASE,
      composedPath: () => [form, document.body],
      stopImmediatePropagation: vi.fn(),
      preventDefault: vi.fn(),
    } as unknown as SubmitEvent;

    submit(event);

    expect(event.preventDefault).toHaveBeenCalledOnce();
    expect(onBlocked).toHaveBeenCalledWith('alice@example.com');
  });

  it('reports the prompt when a clean send is allowed', () => {
    const cache = new VerdictCache();
    cache.setClean('clean-hash', []);
    const onAllowed = vi.fn();
    installGate({
      cache,
      getComposerText: () => 'ordinary prompt',
      isSendIntent: () => true,
      hashOf: () => 'clean-hash',
      approvedHash: () => null,
      consumeApproval: () => {},
      onBlocked: () => {},
      onAllowed,
    });
    const keydown = addEventListener.mock.calls.find((c) => c[0] === 'keydown')![1] as (
      e: Event,
    ) => void;
    keydown({
      eventPhase: Event.CAPTURING_PHASE,
      isComposing: false,
      composedPath: () => [document.body],
    } as unknown as KeyboardEvent);

    expect(onAllowed).toHaveBeenCalledWith('ordinary prompt');
  });

  it('burns the approval after first approved send so the same prompt cannot be re-sent', () => {
    const cache = new VerdictCache();
    cache.setDirty('approved-hash', [{ cls: 'NRIC', start: 0, end: 1, text: 'x' }]);
    let currentHash: string | null = 'approved-hash';
    const consumeApproval = vi.fn((hash: string) => {
      if (currentHash === hash) currentHash = null;
    });
    const onBlocked = vi.fn();
    const onAllowed = vi.fn();
    installGate({
      cache,
      getComposerText: () => 'dirty prompt',
      isSendIntent: () => true,
      hashOf: () => 'approved-hash',
      approvedHash: () => currentHash,
      consumeApproval,
      onBlocked,
      onAllowed,
    });
    const keydown = addEventListener.mock.calls.find((c) => c[0] === 'keydown')![1] as (
      e: Event,
    ) => void;
    const makeEvent = () => ({
      eventPhase: Event.CAPTURING_PHASE,
      isComposing: false,
      composedPath: () => [document.body],
      stopImmediatePropagation: vi.fn(),
      preventDefault: vi.fn(),
    } as unknown as KeyboardEvent);

    // First send: allowed (approval matches) and token is burned
    keydown(makeEvent());
    expect(onAllowed).toHaveBeenCalledOnce();
    expect(consumeApproval).toHaveBeenCalledOnce();

    // Second send: approval is gone, prompt is still DIRTY -> blocked
    keydown(makeEvent());
    expect(onBlocked).toHaveBeenCalledOnce();
  });
});
