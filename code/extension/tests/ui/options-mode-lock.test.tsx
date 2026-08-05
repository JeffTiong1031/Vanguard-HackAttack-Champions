// @vitest-environment jsdom
// tests/ui/options-mode-lock.test.tsx
//
// Enterprise is a commitment, not a toggle: leaving is meant to require the
// admin to revoke, not a click on "Switch to Personal" -- or on "Disconnect",
// which does the identical clearEnrolment() and was found ungated on first
// review. Both doors have to be locked by the same rule or the lock does
// nothing. These tests cover the pure predicate, the responsibility copy,
// and -- because wiring is exactly what the fix touches -- the real
// `disabled` attribute on both buttons as rendered.

import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/preact';
import { canSwitchToPersonal, TOKEN_RESPONSIBILITY, Options } from '../../entrypoints/options/main';

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

// The Enrolment shape carried by every "connected" branch below.
const ENROLMENT = {
  org_id: 'org_1',
  org_name: 'Acme',
  pseudo_id: 'p1',
  department: 'Engineering',
};

/** Stubs just enough of `chrome` for Options() (and the Organisation/
 *  MyReviews subtrees it mounts) to settle without a real background page. */
function stubChrome(enrolment: typeof ENROLMENT | null) {
  const storageData: Record<string, unknown> = {
    vg_mode: 'enterprise',
    vg_revoked_notice: false,
  };
  vi.stubGlobal('chrome', {
    storage: {
      local: {
        get: async (keys: string) => ({ [keys]: storageData[keys] }),
        set: async (items: Record<string, unknown>) => { Object.assign(storageData, items); },
      },
    },
    runtime: {
      sendMessage: async (msg: { kind: string }) => {
        if (msg.kind === 'policy-get') {
          return enrolment
            ? { kind: 'policy-result', ok: true, enrolment, policy: { org_id: 'org_1', org_name: 'Acme', version: 1, tools: [], categories: [] } }
            : { kind: 'policy-result', ok: true, enrolment: null, policy: null };
        }
        if (msg.kind === 'appeals-get') return { kind: 'appeals-result', ok: true, appeals: [] };
        return { kind: 'policy-result', ok: false, error: 'unhandled in test stub' };
      },
    },
  });
}

describe('Options() -- mode-switch gate wiring', () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it('disables both Switch to Personal and Disconnect while enrolled, with the same reason', async () => {
    stubChrome(ENROLMENT);
    render(<Options />);

    const switchBtn = (await screen.findByText('Switch to Personal')) as HTMLButtonElement;
    const disconnectBtn = (await screen.findByText('Disconnect')) as HTMLButtonElement;

    expect(switchBtn.disabled).toBe(true);
    expect(disconnectBtn.disabled).toBe(true);

    const reasons = await screen.findAllByText(/Ask your admin to revoke your enrolment first/);
    // Same rule, same wording, in both places -- not two differently-worded messages.
    expect(reasons).toHaveLength(2);
    for (const r of reasons) expect(r.textContent).toContain('You can still remove Vanguard from Chrome');
  });

  it('enables Switch to Personal once there is no enrolment (Disconnect is not rendered at all)', async () => {
    stubChrome(null);
    render(<Options />);

    const switchBtn = (await screen.findByText('Switch to Personal')) as HTMLButtonElement;
    expect(switchBtn.disabled).toBe(false);

    // Disconnect only exists in the "connected" branch of Organisation(); with
    // no enrolment that branch never renders, so there is nothing to disable.
    expect(screen.queryByText('Disconnect')).toBeNull();
  });
});
