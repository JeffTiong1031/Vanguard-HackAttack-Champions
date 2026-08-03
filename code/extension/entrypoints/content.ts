import { pickAdapter } from '../src/adapters/registry';
import { recordFindings, recordIgnore } from '../src/audit/audit';
import type { GovernanceEvent } from '../src/policy/types';
import type { PolicyRequest, AllowanceResponse } from '../src/policy/messages';

/** Fire-and-forget. A governance event must never delay the gate, and a policy
 *  service that is down must never stop someone sending a prompt (ADR 0014). */
function emitGovernance(event: GovernanceEvent): void {
  void (chrome.runtime.sendMessage({ kind: 'policy-event', event } satisfies PolicyRequest)
    .catch(() => undefined));
}

import { sha256Hex } from '../src/detection/hash';
import { scanInto } from '../src/detection/scan';
import { checkEthics } from '../src/detection/ethics';
import { showEthicsModal, showReviewApprovedModal } from '../src/ui/ethics-modal';
import { VerdictCache } from '../src/detection/verdict-cache';
import { attachFiles } from '../src/files/attach';
import { buildCleanedFile } from '../src/files/cleaned';
import { installFileCapture } from '../src/files/capture';
import { CLIENT_LIMITS } from '../src/files/config';
import { defaultDeps, processFile } from '../src/files/pipeline';
import { FileStore } from '../src/files/store';
import { ApprovalStore } from '../src/gate/approval-token';
import { installGate } from '../src/gate/gate';
import { SessionNumbering } from '../src/mask/placeholder';
import { createComposerHints } from '../src/ui/composer-hints';
import { clearChips, renderChips, showRedactionFailure } from '../src/ui/file-chip';
import {
  hideModal,
  hideOversizedDialog,
  hideProtectionDegraded,
  showModal,
  showOversizedDialog,
  showProtectionDegraded,
} from '../src/ui/mount';
import { debounce } from '../src/util/debounce';

const COLD_HASH = '\0cold';
// First-run weight download (quantized mBERT NER) routinely exceeds a few seconds on a
// cold cache. 4s caused lasting "protection degraded" with no CSP error — the race lost
// to the download, then every follow-up scan also timed out until a lucky fast hit.
// (estimate) team-test value; U6-b still measures the real curve later.
const L2_TIMEOUT_MS = 120_000;

import { setupKeepAliveClient } from '../src/util/keepalive';

export default defineContentScript({
  matches: ['https://chatgpt.com/*', 'https://claude.ai/*'],
  runAt: 'document_start',
  world: 'ISOLATED',
  main() {
    setupKeepAliveClient();

    const adapter = pickAdapter(location.hostname);
    if (!adapter) return;

    const cache = new VerdictCache();
    const approvals = new ApprovalStore();
    const numbering = new SessionNumbering();
    const hashes = new Map<string, string>();
    const files = new FileStore();

    files.subscribe(() => renderChips(files.list(), (id) => files.remove(id)));

    const scanText = (text: string) =>
      scanInto(new VerdictCache(), text, { l2TimeoutMs: CLIENT_LIMITS.fileScanTimeoutMs, purpose: 'file' });

    installFileCapture({
      onFiles: (picked) => {
        for (const file of picked) {
          // Oversize: never enter the FileStore / "Not checked" chip path.
          // Ask immediately; Proceed re-attaches unchecked, Decline drops it.
          // Either way Send later only reviews the prompt (and any other held files).
          if (file.size > CLIENT_LIMITS.maxUploadBytes) {
            showOversizedDialog({
              fileName: file.name,
              sizeBytes: file.size,
              onProceed: () => {
                hideOversizedDialog();
                const input = adapter.fileInputs()[0];
                if (input) attachFiles(input, [file]);
                else {
                  showRedactionFailure(
                    "Vanguard couldn't attach this file to the page. Please reload the tab and try again.",
                  );
                }
                void recordIgnore(
                  [{ cls: 'PERSON', start: 0, end: 0, text: '' }],
                  'file_unchecked:too_large: user trusted and attached without scan',
                );
              },
              onDecline: () => {
                hideOversizedDialog();
              },
            });
            continue;
          }

          const id = files.add(file);
          // Scan starts at ATTACH, not at Send. By the time the user finishes
          // typing, the File pane is usually already populated -- the
          // progressive UI is a consequence of the interception, not extra work.
          void processFile(files, id, defaultDeps(scanText));
        }
      },
    });

    const hints = createComposerHints({
      numbering,
      onRewrite: (rewritten) => {
        adapter.writeText(rewritten);
        approvals.invalidate();
        const text = adapter.readText() ?? rewritten;
        hints.update(text);
        void scan(text);
      },
    });

    const scan = async (text: string) => {
      const verdict = await scanInto(cache, text, { l2TimeoutMs: L2_TIMEOUT_MS, purpose: 'chat' });
      hashes.set(text, await sha256Hex(text));
      if (verdict.complete) hideProtectionDegraded();
      else showProtectionDegraded();
      if (verdict.state === 'DIRTY') await recordFindings(verdict.findings);
    };
    const debouncedScan = debounce((text: string) => void scan(text), 250);
    // The page can contain two editors at once while an old message is being
    // edited. Keep the exact editor that caused the blocked send so review,
    // masking, and focus never jump to the new-message composer.
    let blockedComposer: HTMLElement | null = null;

    installGate({
      cache,
      getComposerText: (path) => {
        blockedComposer = adapter.getComposer(path);
        return blockedComposer ? adapter.readText([blockedComposer]) : null;
      },
      isSendIntent: (event, path) =>
        (event instanceof KeyboardEvent && event.key === 'Enter' && !event.shiftKey)
        || event.type === 'submit'
        || adapter.isSendControl(path),
      hashOf: (text) => hashes.get(text) ?? COLD_HASH,
      approvedHash: () => approvals.currentHash(),
      hasHeldFiles: () => files.hasHeld(),
      onBlocked: async (text) => {
        if (cache.getSync(hashes.get(text) ?? '') == null) await scan(text);
        const verdict = cache.getSync(hashes.get(text) ?? '');
        const promptDirty = verdict?.state === 'DIRTY';

        // Ethics is checked FIRST and blocks outright. A prompt asking for a
        // covert-surveillance script is not made acceptable by masking a name,
        // so the PII path below must not be able to wave it through.
        const ethics = checkEthics(text);
        if (ethics) {
          const promptHash = hashes.get(text) ?? await sha256Hex(text);
          // One-time pass: an overturned appeal for THIS exact prompt lets it
          // through once. Checked here so the block is bypassed before the modal.
          const passGranted = await chrome.runtime.sendMessage({ kind: 'appeal-allowance-check', promptHash })
            .then((r: AllowanceResponse) => (r?.ok ? r.granted : false))
            .catch(() => false);

          if (!passGranted) {
            emitGovernance({
              host: location.hostname,
              type: 'ethics_block',
              category: ethics.category,
              ts: new Date().toISOString(),
            });
            showEthicsModal({
              label: ethics.label,
              category: ethics.category,
              orgName: 'your organisation',
              promptText: text,
              onEdit: () => (blockedComposer ?? adapter.getComposer())?.focus(),
              onRequestReview: (reason, disclosedText) => {
                void chrome.runtime.sendMessage({
                  kind: 'appeal-submit', decisionType: 'ethics',
                  category: ethics.category, reason, disclosedText, promptHash,
                }).catch(() => undefined);
              },
            });
            return;
          }

          // Pass granted. If the prompt is PII-clean, approve this exact prompt so
          // the next Send goes through (once); if it also has PII, fall through to
          // the PII path so masking still happens -- an ethics overturn must not
          // wave PII the admin never reviewed past the gate.
          if (!promptDirty) {
            approvals.approve(promptHash, 60_000);
            hashes.set(text, promptHash);
            showReviewApprovedModal(() => (blockedComposer ?? adapter.getComposer())?.focus());
            return;
          }
        }

        // Always open review when we hold a file — including the all-clean
        // case. Silent re-attach felt like "nothing happened" and skipped the
        // same Proceed confirmation dirty files get. Attach only on Proceed.
        if (!promptDirty && !files.hasHeld()) return;

        // I3: the CLASS of each finding and a count. Never the matched text.
        for (const finding of promptDirty ? verdict!.findings : []) {
          emitGovernance({
            host: location.hostname,
            type: 'pii_block',
            category: finding.cls,
            ts: new Date().toISOString(),
          });
        }

        showModal({
          text,
          findings: promptDirty ? verdict!.findings : [],
          numbering,
          files: files.list(),
          onAcknowledgeFileError: (id, reason) => {
            const held = files.get(id);
            if (!held || held.status.kind !== 'error') return;
            files.update(id, {
              status: { ...held.status, kind: 'error_acknowledged', reason },
            });
            // I3: the class and the reason, never the file bytes or its name.
            void recordIgnore(
              [{ cls: 'PERSON', start: 0, end: 0, text: '' }],
              `file_unchecked:${held.status.code}: ${reason}`,
            );
          },
          onProceed: async ({ finalText, ignored, files: fileResults }) => {
            for (const row of ignored) {
              await recordIgnore([row.finding], row.reason);
            }

            for (const result of fileResults) {
              const held = files.get(result.id);
              if (!held) continue;
              for (const row of result.ignored) await recordIgnore([row.finding], row.reason);
              if (held.findings?.length) await recordFindings(held.findings);
            }

            // Redaction is a network round trip now (Task 5B), so this can
            // FAIL. It must not fail into "attach the original" (a leak) or
            // into "attach a .txt" (a surprise edit in a format nobody asked
            // for). It fails into "nothing is attached and you are told".
            const outgoing: File[] = [];
            try {
              for (const result of fileResults) {
                const held = files.get(result.id);
                if (!held) continue;
                outgoing.push(
                  await buildCleanedFile(held, result.decisions, numbering),
                );
              }
            } catch (err) {
              const message =
                err instanceof Error
                  ? err.message
                  : 'Your files could not be prepared, so nothing was attached.';
              showRedactionFailure(message);
              return; // modal stays open; the user retries, removes the file, or edits
            }

            const input = adapter.fileInputs()[0];
            if (outgoing.length > 0 && input) attachFiles(input, outgoing);
            if (outgoing.length > 0 && !input) {
              // The provider's file input vanished (D4). Do NOT proceed as if
              // the attachment landed -- ADR 0014 degrades to advisory, and an
              // attachment silently dropped is worse than a visible failure.
              showRedactionFailure(
                "Vanguard couldn't attach the cleaned file to this page. Please reload " +
                  'the tab and attach it again.',
              );
              return;
            }

            adapter.writeText(finalText, blockedComposer);
            const approvedText = adapter.readText(blockedComposer ? [blockedComposer] : undefined) ?? finalText;
            const hash = await sha256Hex(approvedText);
            approvals.approve(hash, 60_000);
            hashes.set(approvedText, hash);
            void scan(approvedText);
            hints.update(approvedText);
            hideModal();
            // Files are handed off. Nothing readable outlives the send.
            files.clear();
            clearChips();
          },
        });
      },
    });

    let boundComposer: HTMLElement | null = null;
    const onInput = (e?: Event) => {
      approvals.invalidate();
      const path = e ? e.composedPath() : undefined;
      const text = adapter.readText(path);
      if (text) {
        // L1 hints: sync, no L2 (ADR 0024). Gate scan stays debounced.
        hints.update(text);
        debouncedScan(text);
      } else {
        hints.clear();
      }
    };
    document.addEventListener('input', (e) => onInput(e), { capture: true });
    const bindComposer = () => {
      const composer = adapter.getComposer();
      if (composer === boundComposer) return;
      boundComposer?.removeEventListener('input', onInput);
      boundComposer = composer;
      hints.attach(composer);
      boundComposer?.addEventListener('input', onInput);
      const text = adapter.readText();
      if (text) hints.update(text);
      else hints.clear();
    };
    bindComposer();
    new MutationObserver(bindComposer).observe(document, { childList: true, subtree: true });

    adapter.onPaste((text) => {
      hints.update(text);
      void scan(text);
    });
  },
});
