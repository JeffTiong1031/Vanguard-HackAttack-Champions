import { capabilitiesFor, getMode } from '../src/mode/mode';
import { POLICY_CONFIG } from '../src/policy/config';
import { toolForHost } from '../src/policy/lookup';
import type { PolicyRequest, PolicyResponse } from '../src/policy/messages';
import type { Enrolment, GovernanceEvent, Policy } from '../src/policy/types';
import { hideWarnBanner, showWarnBanner, updateWarnBanner } from '../src/ui/warn-banner';
import { setupKeepAliveClient } from '../src/util/keepalive';

/** Every registry host. Keep in step with code/policy/app/seed.py's REGISTRY. */
const REGISTRY_MATCHES = [
  'https://*/*',
  'http://*/*',
];


function ask<T = PolicyResponse>(msg: PolicyRequest): Promise<T> {
  return chrome.runtime.sendMessage(msg) as Promise<T>;
}

function emit(event: GovernanceEvent): void {
  void ask({ kind: 'policy-event', event });
}

export default defineContentScript({
  matches: REGISTRY_MATCHES,
  runAt: 'document_idle',
  world: 'ISOLATED',
  async main() {
    if (location.hostname === 'localhost' && location.port === '8001') return;
    if (location.hostname === 'www.google.com') return;

    const caps = capabilitiesFor((await getMode()) ?? 'personal');
    if (!caps.toolPolicy) return;   // Personal: no warn banner, no polling, no events

    // Enterprise only, and deliberately after the gate above: the keep-alive
    // port exists to hold the worker up for policy polling, which Personal
    // mode never does.
    setupKeepAliveClient();

    let shownFor: string | null = null;   // llm_id the banner is currently up for
    let reportedVisit = false;

    async function tick(): Promise<void> {
      let response: PolicyResponse;
      let reqResponse: any;
      try {
        [response, reqResponse] = await Promise.all([
          ask<PolicyResponse>({ kind: 'policy-get' }),
          ask<any>({ kind: 'policy-requests-get' })
        ]);
      } catch {
        return;   // worker restarting; the next tick picks it up
      }
      if (!response?.ok) return;

      const policy: Policy | null = response.policy;
      const enrolment: Enrolment | null = response.enrolment;
      if (!policy || !enrolment) return;   // not enrolled: never warn

      const tool = toolForHost(policy, location.hostname);
      const toolId = tool ? tool.llm_id : `tool_${location.hostname.toLowerCase().replace(/[^a-z0-9]/g, '_')}`;
      const toolName = tool ? tool.display_name : location.hostname;

      let requestStatus = 'none';
      let adminNote = '';
      if (reqResponse?.ok && reqResponse.requests) {
        const myReq = reqResponse.requests.find((r: any) => r.llm_id === toolId);
        if (myReq) {
          requestStatus = myReq.status;
          adminNote = myReq.admin_note || '';
        }
      }

      if (requestStatus === 'blocked') {
        if (!document.querySelector('[data-vanguard-ui="warn-banner"]')) {
          showWarnBanner({
            toolName, orgName: enrolment.org_name,
            onDismiss: () => { shownFor = null; },
            onRequest: async () => {},
          });
        }
        updateWarnBanner('blocked', adminNote);
        shownFor = toolId;
        return;
      }

      if (requestStatus === 'approved') {
        if (shownFor) { hideWarnBanner(); shownFor = null; }
        return;
      }

      // Only explicitly approved tools take/keep the banner down.
      // All other websites (unapproved or unlisted) display the banner.
      if (tool && tool.status === 'approved') {
        if (shownFor) { hideWarnBanner(); shownFor = null; }
        return;
      }

      if (requestStatus === 'pending') {
        if (!document.querySelector('[data-vanguard-ui="warn-banner"]')) {
          showWarnBanner({
            toolName, orgName: enrolment.org_name,
            onDismiss: () => { shownFor = null; },
            onRequest: async () => {},
          });
        }
        updateWarnBanner('sent');
        shownFor = toolId;
        return;
      }

      if (!reportedVisit) {
        reportedVisit = true;
        emit({ host: location.hostname, type: 'visit_unapproved', ts: new Date().toISOString() });
      }
      if (shownFor === toolId) return;

      shownFor = toolId;
      emit({ host: location.hostname, type: 'warn_shown', ts: new Date().toISOString() });
      showWarnBanner({
        toolName,
        orgName: enrolment.org_name,
        onDismiss: () => { shownFor = null; },
        onRequest: async (reason) => {
          await ask({ kind: 'policy-request-access', llmId: toolId, reason });
          emit({ host: location.hostname, type: 'request_sent', ts: new Date().toISOString() });
          updateWarnBanner('sent');
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
