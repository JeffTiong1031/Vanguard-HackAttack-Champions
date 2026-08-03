// @vitest-environment jsdom
import { describe, it, expect } from 'vitest';
import { pickAdapter } from '../src/adapters/registry';
import { chatgptAdapter } from '../src/adapters/chatgpt';
import { claudeAdapter } from '../src/adapters/claude';

describe('adapter registry', () => {
  it('routes chatgpt.com', () => expect(pickAdapter('chatgpt.com')?.host).toBe('chatgpt.com'));
  it('routes claude.ai', () => expect(pickAdapter('claude.ai')?.host).toBe('claude.ai'));
  it('returns null off-surface', () => expect(pickAdapter('example.com')).toBeNull());
});

describe('adapter shape', () => {
  const methods = ['getComposer', 'readText', 'writeText', 'isSendControl', 'onPaste', 'fileInputs'] as const;

  it('chatgptAdapter exposes the expected host and methods', () => {
    expect(chatgptAdapter.host).toBe('chatgpt.com');
    for (const m of methods) {
      expect(typeof chatgptAdapter[m]).toBe('function');
    }
  });

  it('claudeAdapter exposes the expected host and methods', () => {
    expect(claudeAdapter.host).toBe('claude.ai');
    for (const m of methods) {
      expect(typeof claudeAdapter[m]).toBe('function');
    }
  });
});

describe('prompt edit support', () => {
  it('detects textarea in event path for chatgptAdapter', () => {
    const textarea = document.createElement('textarea');
    textarea.value = 'edited text containing NRIC 000203-06-0283';
    expect(chatgptAdapter.getComposer([textarea])).toBe(textarea);
    expect(chatgptAdapter.readText([textarea])).toBe('edited text containing NRIC 000203-06-0283');
  });

  it('matches Save & Submit and edit buttons in chatgptAdapter', () => {
    const saveBtn = document.createElement('button');
    saveBtn.textContent = 'Save & Submit';
    expect(chatgptAdapter.isSendControl([saveBtn])).toBe(true);

    const sendBtn = document.createElement('button');
    sendBtn.textContent = 'Send';
    expect(chatgptAdapter.isSendControl([sendBtn])).toBe(true);
  });

  it('reads the edit field associated with Save & Submit instead of the main composer', () => {
    document.body.innerHTML = `
      <div id="prompt-textarea" contenteditable="true">main composer text</div>
      <form id="edit-form">
        <textarea>edited prompt with 000203-06-0283</textarea>
        <button type="button">Save &amp; Submit</button>
      </form>
    `;
    const form = document.querySelector<HTMLElement>('#edit-form')!;
    const button = form.querySelector<HTMLButtonElement>('button')!;

    expect(chatgptAdapter.readText([button, form, document.body])).toBe(
      'edited prompt with 000203-06-0283',
    );
  });

  it('recognises a nested plaintext-only editor used by an edit form', () => {
    document.body.innerHTML = `
      <form id="edit-form">
        <div contenteditable="plaintext-only" role="textbox"><p>NRIC 000203-06-0283</p></div>
        <button type="submit"></button>
      </form>
    `;
    const editor = document.querySelector<HTMLElement>('[role="textbox"]')!;
    const paragraph = editor.querySelector<HTMLElement>('p')!;

    expect(chatgptAdapter.readText([paragraph, editor])).toBe('NRIC 000203-06-0283');
  });

  it('writes reviewed text back to the old-message edit field, not the main composer', () => {
    document.body.innerHTML = `
      <div id="prompt-textarea" contenteditable="true">new message draft</div>
      <form><textarea>old sensitive message</textarea></form>
    `;
    const main = document.querySelector<HTMLElement>('#prompt-textarea')!;
    const edit = document.querySelector<HTMLTextAreaElement>('textarea')!;

    chatgptAdapter.writeText('old PERSON_1 message', edit);

    expect(edit.value).toBe('old PERSON_1 message');
    expect(main.textContent).toBe('new message draft');
  });

  it('detects textarea in event path for claudeAdapter', () => {
    const textarea = document.createElement('textarea');
    textarea.value = 'claude edited prompt';
    expect(claudeAdapter.getComposer([textarea])).toBe(textarea);
    expect(claudeAdapter.readText([textarea])).toBe('claude edited prompt');
  });

  it('matches edit submit buttons in claudeAdapter', () => {
    const btn = document.createElement('button');
    btn.setAttribute('aria-label', 'Save and submit prompt');
    expect(claudeAdapter.isSendControl([btn])).toBe(true);
  });

  it('reads Claude edit text from the submit button wrapper', () => {
    document.body.innerHTML = `
      <div class="ProseMirror" contenteditable="true">main composer text</div>
      <section id="edit-wrapper">
        <textarea>edited claude prompt with alice@example.com</textarea>
        <button aria-label="Save and submit prompt"></button>
      </section>
    `;
    const wrapper = document.querySelector<HTMLElement>('#edit-wrapper')!;
    const button = wrapper.querySelector<HTMLButtonElement>('button')!;

    expect(claudeAdapter.readText([button, wrapper, document.body])).toBe(
      'edited claude prompt with alice@example.com',
    );
  });
});
