import { defineConfig } from 'wxt';

export default defineConfig({
  outDir: 'dist',
  manifest: {
    name: 'Vanguard (Slice 1)',
    description: 'On-device prompt-privacy gate for ChatGPT and Claude. Team test build.',
    version: '0.1.0',
    permissions: ['storage', 'offscreen', 'alarms', 'notifications'],
    host_permissions: [
      // --- AI tool registry. Keep in step with code/policy/app/seed.py. ---
      // A curated, finite list is the answer to "why not <all_urls>?": AI
      // surfaces are known and enumerable, and asking for the whole web would
      // fail the buyer's own security review (doc 02 section 6.4).
      'https://chatgpt.com/*',
      'https://claude.ai/*',
      'https://gemini.google.com/*',
      'https://copilot.microsoft.com/*',
      'https://www.perplexity.ai/*',
      'https://chat.deepseek.com/*',
      'https://chat.mistral.ai/*',
      'https://grok.com/*',

      // --- File-extract service (Slice 2, unchanged) ---
      'http://localhost:8000/*',
      // 🔴 `localhost` and `127.0.0.1` are DIFFERENT origins for host_permissions matching --
      // a rule for one does not cover the other. Both are listed, on both the Slice 2 backend
      // port and the local model server, because a missing permission fails as a blocked fetch
      // inside the offscreen document: the load simply never completes, and the user sees
      // "still blocked", which is indistinguishable from the classifier disagreeing.
      // Observed 2026-07-20, after two other causes with the identical symptom.
      'http://127.0.0.1:8000/*',
      // The sensitivity classifier loads from a public, hash-pinned Hugging Face repo (ADR 0029).
      // No host_permission is needed for it: the NER already fetches remote weights with none
      // listed. The local model server it replaced needed two entries here and a Python process.
      // Placeholder origin already set (Path A hosted demo backend, render.yaml's
      // `name: vanguard-extract`). Task 7 Step 4 substitutes the real subdomain here
      // only if the deployed Render service name ends up different from this placeholder.
      'https://vanguard-extract.onrender.com/*',

      // --- Policy service (Plan A) ---
      // 🔴 THREE origins, and all three must ship. host_permissions is baked at
      // build time, so the venue's address cannot be added on the day.
      //   1. localhost      -- development
      //   2. the LAN address -- two-laptop demo over a phone hotspot with a
      //      reserved IP. EDIT THIS to the reserved address before building.
      //   3. the tunnel      -- a named cloudflared tunnel. HTTPS, so it also
      //      sidesteps mixed content entirely; prefer it as the primary path.
      'http://localhost:8001/*',
      'http://192.168.1.50:8001/*',
      'https://vanguard-policy.example.com/*',
    ],
    // No webRequest (ADR 0017 §6.2). No <all_urls>. Two hosts only.
    // MV3 default *should* include wasm-unsafe-eval; live Chrome applied script-src 'self'
    // only and blocked ORT WASM (R1). Pin the extension_pages CSP explicitly.
    content_security_policy: {
      // wasm-unsafe-eval on script-src AND worker-src: ORT may compile WASM in a Worker.
      // Live error after kill-offscreen quoted script-src 'self' only → stale load; pin both.
      extension_pages:
        "script-src 'self' 'wasm-unsafe-eval'; object-src 'self'; worker-src 'self' 'wasm-unsafe-eval'",
    },
  },
});
