# AI tool lists — proposal for founder approval

**Status: PROPOSAL. Nothing here ships until the founder approves the names.**
Written 2026-08-06 at the founder's instruction: *"you propose a starter list, keep the
current eight first, then add ~12 more you can defend. I'll review/edit before it ships —
I want to approve the names, not invent the first draft."*

Binding constraint, restated by the founder in the same instruction: **no `<all_urls>`.**
Every host below is an explicit entry.

---

## 1. The two lists are different things, and the difference is what makes this scale

This is the part worth agreeing on before the names, because it decides how much work each
future addition costs.

| | **Protection list** | **Awareness list** |
|---|---|---|
| What we do | Full Slice 1 / Slice 2 protection: scan, mask, modal, rewrite the composer | Recognise the host as an AI tool. Warn (Personal) or block prompts (Enterprise, if unapproved) |
| What it costs to add one | **A measurement.** Someone must run the U31 probe on the surface and get a PASS | **One line.** A hostname and a display name |
| What it needs to be true | The generic write-back technique works on that site's composer | Only that the site is an AI chat tool |
| If we are wrong | We claim protection we do not deliver — the worst failure for a compliance buyer | We warn about something harmless, or miss a tool. Recoverable |

**The promotion path is the point:** a new tool enters **awareness** the day we hear about
it, at the cost of one line. It graduates to **protection** only when the U31 probe has
actually been run against it and passed. That keeps the protection claim honest and makes
adding tools cheap — which is the scaling property the founder asked for.

> 🔴 **The failure this structure prevents.** Without the split, the pressure is to add a
> host to the protection list because it *should* work — four editor frameworks passed, so
> the fifth probably will. U31 measured **8 of 8**, and that is evidence about eight
> websites on one date, not a law. A tool on the protection list that silently fails
> write-back is a control that appears to work and does not. That is doc 00 §6's worst case.

---

## 2. Protection list

### 2.1 The current eight — keep, unchanged, first

These are seeded today in [`code/policy/app/seed.py`](../../code/policy/app/seed.py) lines
13–20, and they are **exactly the eight U31 measured**. Every one has a PASS on the
generic write-back technique.

| # | Host | Name | Editor measured | Send-through confirmed |
|---|---|---|---|---|
| 1 | `chatgpt.com` | ChatGPT | ProseMirror | ✅ |
| 2 | `claude.ai` | Claude | Tiptap | ✅ |
| 3 | `gemini.google.com` | Google Gemini | Quill | not tested |
| 4 | `copilot.microsoft.com` | Microsoft Copilot | plain `textarea` | not tested |
| 5 | `www.perplexity.ai` | Perplexity | contenteditable `div#ask-input` | not tested |
| 6 | `chat.deepseek.com` | DeepSeek | plain `textarea` | not tested |
| 7 | `chat.mistral.ai` | Le Chat (Mistral) | ProseMirror | not tested |
| 8 | `grok.com` | Grok | Tiptap | not tested |

⚠️ **Carry the narrowing with the list, always.** Six of the eight proved *DOM insertion*
only. Send-through — that the site actually transmits the rewritten text — was confirmed on
**ChatGPT and Claude only**. See [`code/spikes/u31-generic-writeback/README.md`](../../code/spikes/u31-generic-writeback/README.md).

### 2.2 The twelve I propose adding — and why each

**None of these has been probed yet.** They are candidates for the protection list, which
means each needs a U31 run before it actually goes in. I am proposing *which twelve are
worth the probe*, not asserting they will pass.

**Group A — developer consoles. The highest-value paste targets in the estate.**

| Host | Name | Why it earns a slot |
|---|---|---|
| `aistudio.google.com` | Google AI Studio | Developers paste **production data** here to test prompts. Higher leak value per event than any consumer chat surface. |
| `platform.openai.com` | OpenAI Playground | Same argument. Also the surface where someone pastes a customer record to "see what the model does with it". |
| `console.anthropic.com` | Anthropic Console | Same class. Listed for symmetry — excluding it while listing OpenAI's would be a coverage gap a buyer notices. |
| `notebooklm.google.com` | NotebookLM | **Document-centric by design.** The whole product is "upload your documents". This is Slice 2's threat model, not Slice 1's. |

**Group B — the wedge's language. EN/BM/ZH is decision #4; these are ZH-first tools.**

| Host | Name | Why it earns a slot |
|---|---|---|
| `chat.qwen.ai` ⚠️ | Qwen (Alibaba) | Real ZH/SEA usage. Alibaba has a Malaysian cloud presence, so this is a plausible tool in a Malaysian enterprise. |
| `www.doubao.com` ⚠️ | Doubao (ByteDance) | Large ZH consumer base. |
| `kimi.moonshot.cn` ⚠️ | Kimi (Moonshot) | Long-context ZH tool — long context means **large pastes**, which is exactly U6-b's critical path. |
| `chatglm.cn` ⚠️ | ChatGLM (Zhipu) | Rounds out the ZH set. |

> 🔴 **Weakest group, and I would rather say so than pad it.** These four are defensible on
> the wedge — decision #4 puts the beachhead on EN/BM/ZH, and a protection list with no
> ZH-first tools in it is a wedge we do not actually serve. But my confidence in the
> **hostnames** is lower than for Groups A and C (see §4), and I do not know how many
> Malaysian enterprises actually have these open. **This group is the one to cut first if
> you want fewer than twelve.**

**Group C — general-purpose surfaces with real reach.**

| Host | Name | Why it earns a slot |
|---|---|---|
| `poe.com` | Poe (Quora) | A **multi-model aggregator** — one host fronting many models. Unusually high coverage per entry. |
| `www.meta.ai` | Meta AI | Consumer reach; increasingly present on managed devices. |
| `you.com` | You.com | AI search with a chat composer. |
| `huggingface.co` ⚠️ | HuggingChat | Open-model chat. ⚠️ The chat lives at a **path** (`/chat`), not its own host — so a host-level entry over-matches the whole of Hugging Face, which is mostly not a chat tool. **This one may need path handling or should be dropped.** |

---

## 3. Awareness list

**Recommendation: seed awareness with all twenty protection candidates plus the tools
below.** Awareness costs one line and no measurement, so the list should be *wider* than
the protection list by design — that asymmetry is the whole reason for the split.

| Host | Name | Why awareness and not protection |
|---|---|---|
| `character.ai` | Character.AI | Consumer roleplay. Low enterprise-leak value, but an admin who sees it wants to know. |
| `phind.com` | Phind | Developer search. Composer shape unverified. |
| `www.blackbox.ai` ⚠️ | Blackbox AI | Code-focused; heavy paste behaviour. |
| `bolt.new` | Bolt | Codegen — people paste config and secrets into these. |
| `v0.app` ⚠️ | v0 (Vercel) | Same class. |
| `lovable.dev` | Lovable | Same class. |
| `replit.com` | Replit (AI) | Agent features; broad host, so **awareness only** is the right level. |
| `copilot.cloud.microsoft` ⚠️ | Microsoft 365 Copilot | 🔴 **Deliberately awareness-only.** It is embedded inside Office surfaces rather than being a chat page, so the composer model does not apply. Also, per doc 00 §2.4, Microsoft is *"the existential competitor"* — claiming to protect their surface is a claim to inspect. |
| `github.com` | GitHub Copilot Chat | ⚠️ Broad host, mostly not an AI tool. Same over-match problem as Hugging Face. **May not be worth including at all** — flagged rather than quietly added. |

---

## 4. 🔴 What I am NOT certain of — read this before approving

**Every hostname marked ⚠️ above is from memory and has not been verified.** The package's
standing rule is *a gap over a fabrication*, and a hostname asserted from memory is exactly
the kind of plausible-looking detail that does not get checked — CLAUDE.md §9's lesson.
Several of these products have **renamed or moved domains**, and some run several at once:

- Qwen has appeared under `tongyi.aliyun.com`, `qwen.ai` and `chat.qwen.ai` at various points.
- Kimi has used both `kimi.moonshot.cn` and `www.kimi.com`.
- Zhipu has used both `chatglm.cn` and `chat.z.ai`.
- v0 moved from `v0.dev` to `v0.app`.

**A wrong hostname is not a harmless typo here.** It is an entry that silently never
matches — the tool is neither protected nor warned about, and nothing in the product
reports the miss. It fails open and quiet.

**So the sequence I recommend:**

1. **You approve the NAMES** (which products belong on which list) — that is the judgement
   only you can make, and it does not depend on any hostname being right.
2. **I verify every hostname** by actually visiting each surface, before a single one is
   written into `seed.py` or the manifest. Not from memory.
3. **The protection list additionally waits on a U31 probe run per host.** Approval puts a
   tool on the *candidate* list; a PASS puts it on the *protection* list.

**Nothing here is blocking.** This is Piece 4 work and Pieces 2 and 3 come first — there is
time to do steps 2 and 3 properly.

---

## 5. The two decisions I need from you

1. **The names** — cut, add, or reorder. Group B (the ZH tools) is my least confident and
   the first place to cut if twelve is too many.
2. **The two over-matching hosts** — `huggingface.co` and `github.com` are mostly *not* AI
   tools, so a host-level entry warns on far more than it should. Options: add path
   matching (real work), accept the over-warning, or drop them. **My recommendation: drop
   both from the starter lists** and revisit if the Ignore-rate data says people are
   actually using them.
