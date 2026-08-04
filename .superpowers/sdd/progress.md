# Progress ledger — department-hierarchy-backend (Plan 1)

Base: 27da228 (branch transparency-redressal)
Mode: subagent-driven, per-user directive: no per-task report/review/brief.

- [x] Task 1: schema + migration
- [x] Task 2: session helpers + authz guards
- [x] Task 3: wire-model updates
- [x] Task 4: seed helpers
- [x] Task 5: signup route
- [x] Task 6: role/secret login + logout
- [x] Task 7: company departments routes
- [x] Task 8: company routes re-scope
- [x] Task 9: dept requests + override
- [x] Task 10: dept appeals
- [x] Task 11: dept employee tokens
- [x] Task 12: dept-aware policy/enroll/tools/usage
- [x] Task 13: main.py + seed script + DEMO-TOKENS.md
- [x] Task 14: end-to-end + isolation tests
- [x] Task 15: full suite green + README

Notes:
- Tasks 1-4 complete (a87babf..5f17121, tests green).
- FOLLOW-UP for final-green task: fix tests/test_db.py no-PII assertion to allow department_id (UUID FK, not PII); remove leftover seed_demo_org/session_org when Tasks 8/13 land.
- Tasks 5-8 complete (b867286..4bbfbbe). Local-only app/static mount makes unmatched POST 405 not 404; git-ignored, absent in CI.
- Tasks 9-12 complete (51e8518..59ab75a). Remaining red (owned by 13-15): test_db (department_id col), test_appeals (old model), test_admin oversight (405 vs 404 from local app/static mount).
- Tasks 13-15 complete (e0326dc..b0c2932). FULL SUITE: 110 passed, 0 failed. Plan 1 DONE.

# Progress ledger — department-hierarchy-console (Plan 2)
Base: b0c2932
- [x] Task 1: api.ts types
- [x] Task 2: Login role picker
- [x] Task 3: Signup screen
- [x] Task 4: app shell role routing
- [x] Task 5: Departments screen
- [x] Task 6: scope prop Requests/Reviews/Usage
- [x] Task 7: dept Tokens + DeptTools
- [x] Task 8: extension department_id poll (2ff6f80, 321 ext tests pass)
- [~] Task 9: HTTP flow verified live on current code; browser walk owed to user (restart stale server + reseed first)
- Console Tasks 1-7 complete (98da5c0..02d1820, tsc+build clean).
- Console+extension DONE. Live three-tier flow smoke test PASS.

# Progress ledger — personal-enterprise-mode-gate (Plan 3)
- [x] Task 1: mode module (pure + storage)
- [x] Task 2: content-script gating (4 seams + guard early-return)
- [x] Task 3: background onInstalled auto-open picker
- [x] Task 4: options picker/personal/switch
- [x] Task 5: popup mode framing
- [~] Task 6: manual acceptance — user-owned (load unpacked + browser walk)
- Mode-gate code DONE (787cdf7..a7b2f79). Extension suite 328 passed, build clean.

# Progress ledger — analytics (Plans 4a backend / 4b console)
Backend:
- [x] T1 name columns+migration
- [x] T2 name plumbing (mint/list/enrol)
- [x] T3 analytics_summary
- [x] T4 analytics_alerts
- [x] T5 company+dept routes
- [x] T6 seed + full green
Console: (base 571ef90)
- [x] T1 vitest setup (3276239, 1 passed)
- [x] T2 api types (a5de29c)
- [x] T3 chart-helpers (cf19b35, 3 passed)
- [x] T4 chart components (8b8059b)
- [x] T5 AiUsage (b8a3888)
- [x] T6 InsiderRisk (ecbef60)
- [x] T7 tabs wiring (eecab3c, tsc+build clean, Usage.tsx deleted)
- [x] T8 token name field (fa8e173)
- [x] T9 extension copy (2d2446b, 328 passed, dist committed)
- [~] T10 manual acceptance — code done; reseed+build run; browser walk user-owned
- Analytics BACKEND done (829ee8a..571ef90, 121 passed). test_db.py guardrail updated to allow admin-supplied name, still forbids email + pins exact column set (spec-approved).
- Analytics CONSOLE done (3276239..2d2446b). tsc clean, console build ✓, helper tests 3/3, ext suite 328 passed, dist committed.
- T10 automated half verified live on :8001 reseeded DB: company summary HTTP 200 (all 8 keys, named employees, risk/severity), alerts named+severity-tagged, dept scope isolated to own dept. DEMO-TOKENS.md regenerated (new secrets). Browser walk (visual chart render) user-owned.
