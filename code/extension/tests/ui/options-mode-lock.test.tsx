// @vitest-environment jsdom
// tests/ui/options-mode-lock.test.tsx
//
// Enterprise is a commitment, not a toggle: leaving is meant to require the
// admin to revoke, not a click on "Switch to Personal". These tests lock
// that gate and the responsibility copy shown above the token input.

import { describe, it, expect } from 'vitest';
import { canSwitchToPersonal, TOKEN_RESPONSIBILITY } from '../../entrypoints/options/main';

describe('canSwitchToPersonal', () => {
  it('is blocked while enrolled', () => {
    expect(canSwitchToPersonal({ org_name: 'Acme' } as any)).toBe(false);
  });
  it('is allowed once the enrolment is gone', () => {
    expect(canSwitchToPersonal(null)).toBe(true);
  });
});

describe('TOKEN_RESPONSIBILITY', () => {
  it('tells the user activity is attributed to them', () => {
    expect(TOKEN_RESPONSIBILITY).toContain('private');
    expect(TOKEN_RESPONSIBILITY).toContain('attributed to you');
  });
});
