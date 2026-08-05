import { setMode } from '../mode/mode';
import { clearEnrolment } from './store';

export const REVOKED_MESSAGE =
  "You're no longer connected to an organisation. Vanguard is now protecting " +
  'you personally — upgrade for personal plan features.';

const K_NOTICE = 'vg_revoked_notice';

/** The server said this enrolment is revoked.
 *
 *  Drops to Personal rather than blocking. ADR 0014: a control that bricks
 *  the browser gets uninstalled, and then it protects nobody. The user keeps
 *  local protection and stops reporting — which is what "out of the org"
 *  actually means.
 */
export async function handleRevoked(): Promise<void> {
  await clearEnrolment();
  await setMode('personal');
  await chrome.storage.local.set({ [K_NOTICE]: true });
}

export async function takeRevokedNotice(): Promise<boolean> {
  const seen = (await chrome.storage.local.get(K_NOTICE))[K_NOTICE] === true;
  if (seen) await chrome.storage.local.set({ [K_NOTICE]: false });
  return seen;
}
