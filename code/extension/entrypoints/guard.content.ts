import { capabilitiesFor, getMode } from '../src/mode/mode';
import { POLICY_CONFIG } from '../src/policy/config';
import { toolForHost } from '../src/policy/lookup';
import type { PolicyRequest, PolicyResponse } from '../src/policy/messages';
import type { Enrolment, GovernanceEvent, Policy } from '../src/policy/types';
import { hideWarnBanner, showWarnBanner } from '../src/ui/warn-banner';
import { setupKeepAliveClient } from '../src/util/keepalive';

/** Every registry host. Keep in step with code/policy/app/seed.py's REGISTRY. */
const REGISTRY_MATCHES = [
  'https://chatgpt.com/*',
  'https://claude.ai/*',
  'https://gemini.google.com/*',
  'https://copilot.microsoft.com/*',
  'https://www.perplexity.ai/*',
  'https://chat.deepseek.com/*',
  'https://chat.mistral.ai/*',
  'https://grok.com/*',
];

function ask(msg: PolicyRequest): Promise<PolicyResponse> {
  return chrome.runtime.sendMessage(msg) as Promise<PolicyResponse>;
}

function emit(event: GovernanceEvent): void {
  void ask({ kind: 'policy-event', event });
}

export default defineContentScript({
  matches: REGISTRY_MATCHES,
  runAt: 'document_idle',
  world: 'ISOLATED',
  async main() {
    const caps = capabilitiesFor((await getMode()) ?? 'personal');
    if (!caps.toolPolicy) return;   // Personal: no warn banner, no polling, no events

    // Enterprise only, and deliberately after the gate above: the keep-alive
    // port exists to hold the worker up for policy polling, which Personal
    // mode never does.
    setupKeepAliveClient();

    let shownFor: string | null = null;   // llm_id the banner is currently up for
    let dismissed = false;                // per page load; a reload warns again
    let reportedVisit = false;

    async function tick(): Promise<void> {
      let response: PolicyResponse;
      try {
        response = await ask({ kind: 'policy-get' });
      } catch {
        return;   // worker restarting; the next tick picks it up
      }
      if (!response?.ok) return;

      const policy: Policy | null = response.policy;
      const enrolment: Enrolment | null = response.enrolment;
      if (!policy || !enrolment) return;   // not enrolled: never warn

      const tool = toolForHost(policy, location.hostname);

      // Approved, or not a governed tool at all -> take the banner down. This is
      // the demo's pivot: the admin approves and the banner clears itself.
      if (!tool || tool.status === 'approved') {
        if (shownFor) { hideWarnBanner(); shownFor = null; }
        return;
      }

      if (!reportedVisit) {
        reportedVisit = true;
        emit({ host: location.hostname, type: 'visit_unapproved', ts: new Date().toISOString() });
      }
      if (dismissed || shownFor === tool.llm_id) return;

      shownFor = tool.llm_id;
      emit({ host: location.hostname, type: 'warn_shown', ts: new Date().toISOString() });
      showWarnBanner({
        toolName: tool.display_name,
        orgName: enrolment.org_name,
        onDismiss: () => { dismissed = true; shownFor = null; },
        onRequest: async (reason) => {
          await ask({ kind: 'policy-request-access', llmId: tool.llm_id, reason });
          emit({ host: location.hostname, type: 'request_sent', ts: new Date().toISOString() });
        },
      });
    }

    void tick();
    setInterval(() => { void tick(); }, POLICY_CONFIG.pollMs);
    // A tab returning to the foreground should not wait out the interval.
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') void tick();
    });
  },
});
