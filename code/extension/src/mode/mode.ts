/**
 * Extension mode: Personal (local-only protection) vs Enterprise (org-governed).
 * One pure capabilities function is the single source of truth for every
 * mode-dependent seam, so no call site hard-codes a string comparison.
 */
export type Mode = 'personal' | 'enterprise';

export type ModeCapabilities = {
  reporting: boolean;   // send governance events to the policy server
  ethics: boolean;      // ethics detection + block + appeals
  files: boolean;       // file capture / cloud extract-redact
  toolPolicy: boolean;  // warn banner + enrolment/org surface
};

export function capabilitiesFor(mode: Mode): ModeCapabilities {
  const on = mode === 'enterprise';
  return { reporting: on, ethics: on, files: on, toolPolicy: on };
}

const KEY = 'vg_mode';

export async function getMode(): Promise<Mode | null> {
  const v = (await chrome.storage.local.get(KEY))[KEY] as Mode | undefined;
  return v === 'personal' || v === 'enterprise' ? v : null;
}

export async function setMode(mode: Mode): Promise<void> {
  await chrome.storage.local.set({ [KEY]: mode });
}

export function optionsView(mode: Mode | null): 'picker' | 'personal' | 'enterprise' {
  return mode ?? 'picker';
}
