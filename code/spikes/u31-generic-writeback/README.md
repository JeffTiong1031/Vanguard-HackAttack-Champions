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
| `execCommandReturned: false` | the browser refused the insert outright |
| `matches: true` | text landed AND survived two frames |
| `matches: false` with `execCommandReturned: true` | 🔴 **the interesting case** — the editor reverted it. This is what read-back exists to catch |

⚠️ `matches: true` proves the text is in the DOM. It does **not** prove the
site would send it. Confirm by actually sending a marked message on at least
ChatGPT and Claude, and checking the sent message contains the marker.
