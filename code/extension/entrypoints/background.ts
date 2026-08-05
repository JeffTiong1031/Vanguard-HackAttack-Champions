// L2 / sensitivity leg (teammate's sensitivity-integration work).
import { buildRunRequest, type ScanRequest, type ScanResponse } from '../src/detection/l2/messages';
import { loadConfig, type SensitivityConfig } from '../src/detection/l2/sensitivity';
import { recordStatus } from '../src/detection/l2/status-store';
// Policy leg (Plan B governance integration).
import { enrol, refreshPolicy, sendAccessRequest, fetchNotifications } from '../src/policy/client';
import { queueEvent, flushNow } from '../src/policy/events';
import { isPolicyRequest, type PolicyRequest, type PolicyResponse, type AppealsResponse, type AllowanceResponse, type NotificationsResponse } from '../src/policy/messages';
import { getCachedPolicy, getEnrolment } from '../src/policy/store';
import { submitAppeal, fetchMyAppeals, grantPassIfAllowed } from '../src/policy/appeals';

// [verify] WXT output path for entrypoints/offscreen/index.html — confirmed by inspecting a real
// build (dist/chrome-mv3/); see .superpowers/sdd/task-3-report.md for the check.
const OFFSCREEN_URL = 'offscreen.html';

async function ensureOffscreen(): Promise<void> {
  const has = await chrome.offscreen.hasDocument?.();
  if (has) return;
  await chrome.offscreen.createDocument({
    url: OFFSCREEN_URL,
    reasons: [chrome.offscreen.Reason.WORKERS],
    justification: 'Run on-device NER inference in a WASM worker; no data leaves the device.',
  });
}

import { setupKeepAliveServer } from '../src/util/keepalive';

// 🔴 The service worker owns ALL configuration (ADR 0030). The offscreen document has no
// chrome.storage — measured 2026-07-20 — so it cannot read its own settings, and a read there
// throws in a way the old code reported as "feature off". Cached because scans run at
// keystroke rate; invalidated on change so the options page takes effect without a reload.
let cfgCache: SensitivityConfig | null = null;
async function config(): Promise<SensitivityConfig> {
  if (!cfgCache) cfgCache = await loadConfig();
  return cfgCache;
}

export default defineBackground(() => {
  console.info('[vanguard] background alive');
  setupKeepAliveServer();

  // First run: land the user on the Personal/Enterprise chooser in Options.
  chrome.runtime.onInstalled.addListener((details) => {
    if (details.reason === 'install') void chrome.runtime.openOptionsPage();
  });

  chrome.storage.onChanged.addListener(() => { cfgCache = null; });

  // ─── Proactive notification polling ────────────────────────────────────────
  // Poll every 30 seconds so the employee is notified as soon as a manager
  // reviews their prompt appeal — no need to open the ethics modal first.
  async function pollAndNotify(): Promise<void> {
    try {
      const notifs = await fetchNotifications();
      for (const notif of notifs.filter(n => n.status === 'unread')) {
        try {
          if (typeof chrome !== 'undefined' && chrome.notifications?.create) {
            chrome.notifications.create(`vg-notif-${notif.id}`, {
              type: 'basic',
              iconUrl: 'icon-128.png',
              title: notif.title,
              message: notif.message,
              priority: 2,
            });
          }
        } catch {
          // Notifications permission may not be granted; ignore silently.
        }
      }
    } catch {
      // Service may be offline; degrade gracefully.
    }
  }

  // Create a repeating alarm for notification polling.
  chrome.alarms.create('vg-notification-poll', { periodInMinutes: 0.5 });
  chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name === 'vg-notification-poll') void pollAndNotify();
  });
  // Also poll immediately on startup.
  void pollAndNotify();
  // ───────────────────────────────────────────────────────────────────────────


  chrome.runtime.onMessage.addListener((msg: ScanRequest, _s, sendResponse) => {
    if (msg?.kind !== 'l2-scan') return;
    (async () => {
      try {
        await ensureOffscreen();
        const res = (await chrome.runtime.sendMessage(
          buildRunRequest(msg, await config()),
        )) as ScanResponse;
        // The offscreen document cannot write storage either, so the SW records the engine
        // state for the options page on its behalf.
        if (res.ok) void recordStatus(res.sensitivity);
        sendResponse(res);
      } catch (e) {
        // Without this, a throw becomes an unhandled rejection and the content side only
        // sees a timeout → 'degraded'. Surface the real failure as an l2-result error.
        sendResponse({ kind: 'l2-result', id: msg.id, ok: false, error: String(e) } satisfies ScanResponse);
      }
    })();
    return true;
  });

  // Policy traffic lives HERE, not in the content script. A content script on
  // https://chatgpt.com cannot fetch http:// on a LAN address -- see
  // src/policy/client.ts and spec section 5.4.
  chrome.runtime.onMessage.addListener((msg: PolicyRequest, _s, sendResponse) => {
    if (!isPolicyRequest(msg)) return;
    (async () => {
      try {
        switch (msg.kind) {
          case 'policy-get': {
            const policy = await refreshPolicy();
            void flushNow();
            sendResponse({
              kind: 'policy-result', ok: true,
              policy, enrolment: await getEnrolment(),
            } satisfies PolicyResponse);
            return;
          }
          case 'policy-enrol': {
            const enrolment = await enrol(msg.token);
            sendResponse({
              kind: 'policy-result', ok: true,
              policy: await getCachedPolicy(), enrolment,
            } satisfies PolicyResponse);
            return;
          }
          case 'policy-request-access': {
            await sendAccessRequest(msg.llmId, msg.reason);
            sendResponse({
              kind: 'policy-result', ok: true,
              policy: await getCachedPolicy(), enrolment: await getEnrolment(),
            } satisfies PolicyResponse);
            return;
          }
          case 'policy-event': {
            queueEvent(msg.event);
            sendResponse({
              kind: 'policy-result', ok: true,
              policy: null, enrolment: null,
            } satisfies PolicyResponse);
            return;
          }
          case 'appeal-submit': {
            await submitAppeal({
              decisionType: msg.decisionType, category: msg.category,
              reason: msg.reason, disclosedText: msg.disclosedText, promptHash: msg.promptHash,
            });
            sendResponse({ kind: 'policy-result', ok: true, policy: null, enrolment: null } satisfies PolicyResponse);
            return;
          }
          case 'appeals-get': {
            sendResponse({ kind: 'appeals-result', ok: true, appeals: await fetchMyAppeals() } satisfies AppealsResponse);
            return;
          }
          case 'appeal-allowance-check': {
            sendResponse({ kind: 'allowance-result', ok: true, granted: await grantPassIfAllowed(msg.promptHash) } satisfies AllowanceResponse);
            return;
          }
          case 'notifications-get': {
            const notifs = await fetchNotifications();
            for (const notif of notifs.filter(n => n.status === 'unread')) {
              try {
                if (typeof chrome !== 'undefined' && chrome.notifications?.create) {
                  chrome.notifications.create(notif.id, {
                    type: 'basic',
                    iconUrl: 'icon-128.png',
                    title: notif.title,
                    message: notif.message,
                    priority: 2,
                  });
                }
              } catch {
                // Ignore if notifications permission not granted
              }
            }
            sendResponse({ kind: 'notifications-result', ok: true, notifications: notifs } satisfies NotificationsResponse);
            return;
          }
        }
      } catch (e) {
        sendResponse({
          kind: 'policy-result', ok: false, error: String(e instanceof Error ? e.message : e),
        } satisfies PolicyResponse);
      }
    })();
    return true;   // keep the message channel open for the async reply
  });
});
