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
