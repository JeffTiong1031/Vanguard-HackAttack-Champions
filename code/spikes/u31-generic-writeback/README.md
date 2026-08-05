# U31 — generic composer write-back

**MEASUREMENT INSTRUMENT. Nothing here ships** (ADR 0012 · U26).

## Claim under test
A composer rewrite performed via the browser's own text-insertion path is
accepted by the site's editor framework — and when it is not, a read-back
check detects it.

## Run it
1. `chrome://extensions` → Developer mode → Load unpacked → this folder
2. Open a surface, **click into the composer**, type a word so it is focused
3. DevTools console: `await __vgU31()`
4. Copy the `[U31 CAPTURE]` JSON into `results/<host>.json`

## Reading a capture — the verdict is YOURS, not the probe's
| Field | Means |
|---|---|
| `composerFound: false` | rung 1 fails. Nothing else is meaningful |
| `composerKind: "last-focused"` | the element the operator actually focused before switching to DevTools — the reliable case |
| `composerKind` is `"active"`, `"contenteditable-query"`, or `"textarea-query"` | 🔴 **treat the reading as suspect.** No remembered focus was available, so the probe fell back to `document.activeElement` (likely DevTools itself) or queried the first matching element on the page — which can be a rename field, a sidebar editor, or a message-edit overlay, not the composer. **Re-run: click into the actual composer, then switch to DevTools and invoke `__vgU31()` without clicking anything else on the page in between** |
| `composerDescriptor` | tag / id / first CSS class / rounded width×height (px) of the measured element. Use it to sanity-check `composerKind` — a real composer is normally the widest, tallest text-entry element on the page; a 20×20px box is not it |
| `execCommandReturned: false` | the browser refused the insert outright |
| `stillConnected: false` | 🔴 the measured node was removed from the DOM during the two-frame wait — the framework replaced rather than mutated it. `readBack` and `matches` were read from a detached node and may be misleading |
| `matches: true` | text landed AND survived two frames. Only trust this if `stillConnected: true` |
| `matches: false` with `execCommandReturned: true` | 🔴 **the interesting case** — the editor reverted it. This is what read-back exists to catch |

⚠️ `matches: true` proves the text is in the DOM. It does **not** prove the
site would send it. Confirm by actually sending a marked message on at least
ChatGPT and Claude, and checking the sent message contains the marker.

---

## Results — measured 2026-08-05, Chrome on Windows

Captures: [`result/host.json`](result/host.json) (all eight concatenated in one file).

| Host | Editor (`firstClass`) | Composer found | Detection path | Insert accepted | Survived 2 frames | Node still attached | Marker in SENT message |
|---|---|---|---|---|---|---|---|
| chatgpt.com | ProseMirror | ✅ | `last-focused` | ✅ | ✅ | ✅ | ✅ **confirmed** |
| claude.ai | Tiptap | ✅ | `last-focused` | ✅ | ✅ | ✅ | ✅ **confirmed** |
| gemini.google.com | Quill (`ql-editor`) | ✅ | `last-focused` | ✅ | ✅ | ✅ | not tested |
| copilot.microsoft.com | plain `textarea` | ✅ | `last-focused` | ✅ | ✅ | ✅ | not tested |
| www.perplexity.ai | contenteditable `div#ask-input` | ✅ | `last-focused` | ✅ | ✅ | ✅ | not tested |
| chat.deepseek.com | plain `textarea` | ✅ | `last-focused` | ✅ | ✅ | ✅ | not tested |
| chat.mistral.ai | ProseMirror | ✅ | `last-focused` | ✅ | ✅ | ✅ | not tested |
| grok.com | Tiptap | ✅ | `last-focused` | ✅ | ✅ | ✅ | not tested |

**Measured:** **8/8** composers found · **8/8** inserts accepted and survived · **8/8** on the
reliable `last-focused` path, zero fallbacks · **2/2** send-through confirmations.

**Editor spread is the finding, not the count.** Four distinct technologies —
ProseMirror ×2, Tiptap ×2, Quill ×1, plain `textarea` ×2, one unidentified
contenteditable. The technique is not passing eight times; it is passing across
the main ways a chat composer is built, which is why a ninth surface is likely to
be one of these again.

### 🔴 What this run did NOT establish

- **The read-back check never fired.** Zero `matches: false` in eight runs. The
  detector is confirmed to report success correctly; its ability to **detect
  failure is untested**, because no surface gave it a failure to detect. Do not
  cite read-back as a proven safety net — it is an unexercised one.
- **`frameworkHint` was `null` on all eight**, including surfaces that are
  certainly React. The field only inspects `__react*` keys on the element itself
  and told us nothing. Ignore it; do not read meaning into the nulls.
- **Send-through was confirmed on 2 of 8.** The other six proved DOM insertion
  only. That is the weaker claim, and the gap is stated rather than assumed away.
- **One browser, one OS, one date.** These are properties of eight websites on
  2026-08-05 and they move on the D4 clock.
