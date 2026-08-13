# Recall — Codebase Health Review (Aug 2026)

Scope: readiness to add incremental product features (chat / learning / lists / math polish)
over the coming days. Not a product review. No new features proposed.

Reviewed at `fix/mobile-math-no-gray-clip` (6 commits ahead of `main`).
Prior review (`REVIEW_TICKETS.md`, R1–R7) is fully closed and not re-litigated here.

---

## A. Verdict

**Yes — this codebase is in shape to add features next week.** It is materially healthier
than its own docs suggest. Layering is real and mostly one-directional, the job queue is
durable with a DLQ, there are 1,598 backend tests across 139 files and 140 mobile test
files, i18n is at exact 889-key parity across 9 locales *with a test enforcing it*, config
is fully centralised (zero `os.environ` reads outside `core/config.py`), there is no dead
feature flag, no commented-out code, and no silent `except: pass` anywhere in the API.
The rejected-UX bans are genuinely honoured — no recalled chip, no `ImageGenPromptSheet`,
no fallback chips, assistant bodies unfolded.

**The one biggest structural risk is the turn-resource lifecycle in
`services/chat/stream.py`.** Daily-quota reservation and the per-chat prepare lock are
acquired, transferred between entry points, and released/refunded by hand across three
public stream functions, coordinated by four ad-hoc ownership flags (`pre_reserved`,
`took_reservation_ownership`, `held_chatprep_lock`, `owns_lock`) and six separate
`refund_usage` call sites. Every exit path — including `BaseException` for WS cancel — has
to refund the right amount exactly once. It is correct today, and the comments show it was
made correct the hard way. But it is correct by vigilance, not by construction: the failure
mode is a silent daily-quota leak that no test will notice, and *any* new pre-stream step
that can raise, or any fourth turn entry point, has to re-derive the whole discipline. That
is the thing most likely to bite the next feature.

Everything else is ordinary drag: one genuinely missing seam (fence dispatch), one inverted
import (`core` → `background`), two files that outgrew their concern, and documentation that
describes a smaller app than the one that exists.

**Judgment call worth stating up front:** the `docs/` set is accurate and the `.cursor/rules`
set is excellent, but root `CLAUDE.md` is now actively misleading (C9). If you hand this repo
to a fresh agent next week, that file is the first thing it reads, and it will get the map
wrong. I would fix it before any structural work, because it is the cheapest item here and
it changes the quality of every subsequent agent's output.

---

## B. What's working (don't "fix" these)

- **Backend layering holds.** Routers are transport-only; business logic is in services;
  IO is in gateways/repositories. `services/{chat,todos,projects,home,web_search}` are
  proper packages, not dumping grounds.
- **`math_tools.py` is already registry-driven.** Despite 1,973 lines, it has an ordered
  `_INTENT_EXTRACTORS` tuple and a `kind → _verified_block_*` dict, with ordering rationale
  in comments and 9 dedicated test files. Adding a math intent is 4 edits in 1 file. **It
  does not need a registry and it does not need splitting** — leave it alone.
- **Heavy vendors are correctly lazy.** ~8.4MB of inlined Mermaid/MathJax/Vega/PDF/SMILES
  sits in `lib/vendor/`, but `LazyHeavyRich.tsx` async-splits all of it and there is not one
  static import. Already solved; don't re-solve.
- **One stream-payload handler on mobile.** `useChat.handleChatPayload` serves both WS and
  SSE; `chatSse.ts` routes through `lib/api/client.requestSse` rather than a bare `fetch`.
  The `lib/api` boundary is intact — `lib/api.ts` is a thin barrel over `lib/api/*`.
- **`useChat` / `useChatSend` is a defensible split**, not a lost-ownership problem:
  `useChat` owns the wire and turn state, `useChatSend` owns composer→send intent, and
  `app/index.tsx` composes them with zero direct API calls in 541 lines.
- **i18n is genuinely healthy** — flat 889-key `en.json`, 8 locales at exact parity, guarded
  by `lib/__tests__/i18n.test.ts`. No hardcoded `Alert.alert` or JSX copy found.
- **`stream_events.py` and `finalize_registry.py` are good seams** that already exist.
  Extend them (C6); don't rebuild them.

---

## C. Findings — ranked

### Architecture

---

**C1 — Turn quota/lock lifecycle is hand-managed across three entry points**
**Severity:** P0 · **Area:** chat-loop · **Effort:** M

**Evidence:** `apps/api/app/services/chat/stream.py`
- `stream_chat_response` (l.248–392): flags `took_reservation_ownership` (l.277),
  `owns_lock` (l.278); refunds at l.316, l.361, l.391; lock release at l.387.
- `stream_regenerate_response` (l.395–551): own acquire (l.415), reserve (l.477),
  refund (l.505), release (l.551).
- `stream_edit_response` (l.554–677): own acquire (l.580), reserve (l.600), refund (l.652),
  then *delegates into* `stream_chat_response` passing `pre_reserved=reserved` (l.668) and
  `held_chatprep_lock=(lock_key, lock_token)` (l.673) — which is the sole reason the two
  ownership flags exist.
- `stream_and_finalize` refunds again at l.1041.

**Why it blocks scale / plug-out:** the reservation is a *transferable resource* modelled as
two optional parameters plus two booleans. Adding a fourth entry point, or inserting any new
fallible pre-stream step (a new tool round, a new attachment path), means re-deriving which
of the six refund sites applies. `except BaseException` is load-bearing on two of them — the
comment at l.358 exists because 3.12 `CancelledError` already caused a leak once. The bug
class is a silent quota leak; nothing fails loudly, so tests won't catch a regression.

**Recommended fix (smallest seam):** one async context manager in a new
`services/chat/turn_resources.py` that owns acquire → refund-on-error → release:

```python
async with turn_resources(redis, settings, user=user, chat_id=chat_id, ...) as res:
    ...  # res.reserved_tokens; refund + release happen on any exit
```

Give it a `transfer()` (or accept an already-open `res`) so `stream_edit_response` hands its
reservation down instead of passing `pre_reserved` + `held_chatprep_lock`. Delete all four
ownership flags. No behaviour change — this is a pure move of existing refund/release calls
into `__aenter__`/`__aexit__`.

**Do not:** change *when* quota is reserved or how much (`weighted_reserve_tokens`,
`vision_reserve_tokens` stay untouched); don't fold the three public entry points into one
parametrised function — three named turn kinds is the readable shape; don't drop
`asyncio.shield` semantics in `stream_events.await_finalize_commit`.

---

**C2 — `core/jobs.py` imports `background/` and `services/` (inverted layer); the job
registry exists but nothing outside uses it**
**Severity:** P1 · **Area:** jobs · **Effort:** S

**Evidence:** `apps/api/app/core/jobs.py:24-38` imports nine `app.background.*` modules plus
`app.services.transactional_email`. `register(job_type, handler)` is public (l.100) but the
only callers are inside `jobs.py` itself (l.~330-331); the ten `_handle_*` thunks live in
`jobs.py` (l.198–340). Confirmed: `grep` finds zero external `jobs.register(` callers.

**Why it blocks scale / plug-out:** `core/` is the lowest layer and now depends on the
highest, so importing anything from `core.jobs` drags ten background modules (and their
transitive service imports) into the graph. Adding a best-effort job means editing
`core/jobs.py` in three places (import, `_handle_x`, `register`) — the file every other job
also edits, so parallel feature branches collide there. Deleting a job means the same.

**Recommended fix:** move each `_handle_*` into the background module it already calls, and
have those modules call `jobs.register(...)` at import. Keep one explicit
`app/background/__init__.py` (or `register_all()`) that the worker lifespan imports once, so
registration order stays deterministic and greppable. `core/jobs.py` keeps the stream,
retry, DLQ, and metrics machinery and loses all domain imports.

**Do not:** switch to decorator-based auto-discovery or import-side-effect scanning — the
explicit list is the point; don't touch `_MAX_ATTEMPTS`/DLQ/dedupe semantics; keep
`enqueue_welcome_email` / `enqueue_purchase_receipt` where routers already import them.

---

**C3 — `app/memory.tsx` holds API mutations and optimistic rollback inline in JSX**
**Severity:** P1 · **Area:** mobile · **Effort:** S

**Evidence:** `apps/mobile/app/memory.tsx` (558 lines) calls `api.updateMemory` (l.250),
`api.deleteMemorySection` (l.346), `api.deleteMemoryFact` (l.381) directly inside `Alert`
callbacks nested ~6 levels into the render tree, each with its own snapshot/rollback and
error alert (l.338–390). There is no `hooks/useMemory*.ts`.

**Why it blocks scale / plug-out:** violates the stated mobile rule (screens dumb, logic in
hooks) in the one screen most likely to gain features (memory editing/consolidation UI).
The optimistic-rollback pattern is untestable where it currently sits, and the rollback
comment at l.383 documents a real server-interaction subtlety that deserves a test.

**Recommended fix:** extract `hooks/useMemoryActions.ts` mirroring the existing
`hooks/useTodosActions.ts` (363 lines, same shape, already the house pattern). Screen keeps
`Alert` confirm UX; the hook owns snapshot → call → rollback/reload. Add unit tests for the
404-means-reload branch.

**Do not:** redesign the memory screen UI or change the section/fact data model; keep the
`load({ silent: true, force: true })` reload-on-404 behaviour exactly as-is.

---

**C4 — `services/memory.py` mixes five concerns in 961 lines**
**Severity:** P1 · **Area:** api · **Effort:** M

**Evidence:** `apps/api/app/services/memory.py` contains text normalisation (l.45–82),
consolidation policy (l.82–204), prompt selection (l.204–248), semantic search + embedding
cache (l.248–511), Redis block cache + generation keys (l.521–716), write locking
(l.716–790), and CRUD (l.790–961). Nine call sites across routers, services, and background
import it, several importing single leaf helpers (`home/memory_starters.py:22`).

**Why it blocks scale / plug-out:** memory is named in `CLAUDE.md` as a 90%-coverage
critical service, and it's the module most likely to change when learning/memory features
land. Today a change to caching sits in the same file as sentence-splitting, so unrelated
feature branches conflict, and the import surface makes it impossible to depend on just the
pure text helpers.

**Recommended fix:** split into `services/memory/` mirroring `services/todos/`:
`text.py` (normalise/stamp/split/sensitive), `consolidation.py`, `selection.py`,
`semantic.py`, `cache.py`, `locks.py`, `crud.py`, with `__init__.py` re-exporting the
current public names so no call site changes in the same PR.

**Do not:** change memory selection/ranking behaviour or cache TTLs while moving; keep the
`__init__` re-export shim so this lands as a pure move with zero diff at call sites; don't
merge this with C3 — separate PRs.

---

### Plug-in gaps

---

**C5 — Fence dispatch has no registry: five files, four independently-maintained lang lists,
already drifted**
**Severity:** P0 · **Area:** rich-render · **Effort:** M

**Evidence:** adding or removing one fence type touches, by hand:
1. `lib/richBlocks.ts` — `STRUCTURED_LANGS` set (l.44–76) + any parser
2. `components/rich/RichFence.tsx` — `renderRichFence` if-chain (~15 branches) *and*
   `renderCopyStyleBlock`
3. `components/markdown/markdownFenceRender.tsx` — pre-dispatch with its **own** lists
   (`isMathDiagramLang`, `isFakeImageGenFence`) and order-sensitive precedence
4. `lib/copyBlock.ts` — `isAnswerLang` (l.313), the code-block exclusion list (l.320–334),
   the copy-block list (l.365–370)
5. `lib/fallbackFence.ts` — `classifyFallbackFence`, a second parallel classifier for the
   crash path

**The drift is already measurable.** Comparing the lists programmatically:
`sources`, `copy`, `message`, `reply`, `sms`, `text` appear in `copyBlock.ts` but not in
`STRUCTURED_LANGS`; 18 langs including `chart`, `mermaid`, `vega`, `steps`, `compare` are in
`STRUCTURED_LANGS` but absent from `copyBlock`'s lists. Concretely: the backend *emits* a
` ```sources ` fence (`services/web_search/formatting.py:289`) and strips it again (l.272);
mobile's only knowledge of `sources` is one line in `copyBlock.ts`. If the server-side strip
is ever missed, that fence falls all the way through to the terminal
`<CodeBlock lang="sources">` and the user sees raw JSON. Separately, `vocab_quiz` is a
fully parallel fence path (`lib/parseVocabQuiz.ts`, 503 lines + `lib/vocabQuizFormat.ts`)
that never enters this dispatch at all.

**Why it blocks scale / plug-out:** "one more rich fence" is the single most likely shape of
next week's work, and it is currently a 5-file change with an implicit precedence contract
spread across two if-chains. Deleting a fence is worse — nothing tells you which of the five
lists still mentions it.

**Recommended fix:** one `lib/fenceRegistry.ts` — an ordered array of
`{ id, langs, match?, render, copyBehaviour, fallback }` entries. `isStructuredFenceLang`,
`renderRichFence`, `classifyFallbackFence`, and `copyBlock`'s lists all derive from it. The
existing `renderFenceInner` precedence (answer → latex → clock → rich → math-meta → copy →
code) becomes explicit registry order rather than statement order. Add a test asserting
every registered id round-trips through render, copy, and fallback.

**Do not:** touch what any fence *renders* — this is dispatch only, zero visual diff; don't
fold `vocab_quiz` into the registry in the same PR (its quiz-state coupling is separate work
and `lessons.mdc` documents rejected quiz UX); don't remove the mistagged-`json` geometry/
graph detection (`detectJsonRichFenceKind`) — model instruction-drift is real and that
fallback is load-bearing; don't change the content-derived `math:` React keys, which exist
to stop WebView remount flicker.

---

**C6 — Stream event envelope is built inline in both transports**
**Severity:** P1 · **Area:** shared-contract · **Effort:** S

**Evidence:** `services/chat/stream_events.py` owns only `done` (`build_done_payload`) and
`error` (`error_payload_for_exception`). The other five events are constructed by hand in
each transport: `start`, `token`, `status`, `reasoning`, and `stream_end` — with the
`resolved_model` / `fallback_used` conditional block duplicated verbatim at
`routers/ws.py:111-116` and `routers/chat_stream.py:~137-143`.

**Why it blocks scale / plug-out:** adding one stream event (or one field on `stream_end`)
is a 2-router + 2-client change with nothing enforcing agreement, and the docs commit to a
web client reusing this exact protocol. The seam already exists and is half-populated —
this is finishing it, not building it.

**Recommended fix:** move `build_start_event`, `build_token_event`, `build_status_event`,
`build_reasoning_event`, `build_stream_end_payload` into `stream_events.py`; both routers
call them. Add one test asserting WS and SSE emit the same event-type set and identical
`stream_end` keys for the same result dict (closes C10).

**Do not:** unify the two transports themselves — WS cancel and SSE disconnect-polling are
legitimately different mechanics and must stay separate; don't change wire field names
(mobile `chatSocketReduce.ts` parses them).

---

### Dead / unwanted

---

**C7 — `contextSummarized` is dead plumbing for a banned chip**
**Severity:** P2 · **Area:** mobile · **Effort:** S

**Evidence:** declared at `lib/assistantMessageContent.ts:44`, **never destructured or read**
in `deriveAssistantMessageContent` (l.121–134) and absent from its output type. Still
threaded through `lib/chatSocketReduce.ts:17,61` → message type →
`hooks/useAssistantMessageContent.ts:77` (plus l.89 in the `useMemo` deps) → asserted in
`lib/__tests__/assistantMessageContent.test.ts:29`.

**Why it blocks scale / plug-out:** `chat-ux-bans.mdc §4` bans surfacing
`context_summarized`, and `lessons.mdc` records it flashing a raw i18n key in chat. The
render path is gone but the wiring survives, which is precisely the "second entry point that
can pop the old thing back" the ban rule warns about. It also adds a no-op `useMemo`
dependency.

**Recommended fix:** delete the field from `assistantMessageContent.ts`,
`useAssistantMessageContent.ts` (including the dep array), and the test fixture. Keep it in
`chatSocketReduce.ts` types only if the wire payload genuinely still carries it — the
backend is allowed to send it for logging.

**Do not:** remove `context_summarized` from `stream_events._DONE_PAYLOAD_KEYS` on the
backend — the ban explicitly permits the server to keep sending it.

---

**C8 — Chat SSE endpoints duplicate a 3-line rate-limit preamble and a ~40-line body**
**Severity:** P2 · **Area:** api · **Effort:** S

**Evidence:** `routers/chat_stream.py` — the identical
`if not await allow_chat_message(redis, user.id): raise HTTPException(429, ...)` block plus
`cancel_event = asyncio.Event()` appears three times (`stream_message_sse`,
`stream_regenerate_sse`, `stream_edit_sse`), each wrapping a near-identical `generate()`
that differs only in which `chat_service.*` function it closes over and which body fields
it forwards.

**Why it blocks scale / plug-out:** a fourth streaming entry point copies the preamble a
fourth time, and a change to chat rate limiting has to be made in three places (four with
`ws.py`'s `_ws_rate_limit`).

**Recommended fix:** a FastAPI dependency `Depends(require_chat_rate_limit)` returning the
redis handle, and a small local helper that builds the `generate()` closure from a
`stream_factory`. Purely mechanical.

**Do not:** merge the three routes into one polymorphic endpoint — distinct paths are the
contract the mobile client and any future web client bind to.

---

### Missing docs / tests

---

**C9 — Root `CLAUDE.md` describes a substantially smaller app than the one that exists**
**Severity:** P1 · **Area:** shared-contract · **Effort:** S

**Evidence:** verified contradictions against the tree:
- *"Not in scope (v1): tools/agents"* — but `services/tool_loop.py`, `services/chat_tools.py`,
  and `gateways/mcp/{registry,base,sympy_adapter,calendar_adapter,image_gen_adapter}.py`
  exist, with `mcp_tools_enabled` / `mcp_tool_loop_enabled` flags and a documented tool-loop
  path in `docs/math.md`. `FEATURES.md:333` correctly marks this ⚠️ partial — so the two
  root docs contradict each other.
- *"Later: … full attachment RAG"* — but `services/attachment_rag.py`,
  `repositories/attachment_chunks.py`, and `attachment_rag_enabled: bool = True` (default on)
  all exist.
- The **Service Overview** domain list (user/chat/message/memory/model alias/quota/todo/
  suggestion/search) omits project, attachment, calendar, gmail, reminder, subscription.
- The **directory tree** omits `app/content/`, `app/worker_main.py`, `app/worker_health.py`,
  `app/exceptions.py`, and every service subpackage (`chat/turn_prep`, `home`, `projects`,
  `todos`, `web_search`, `gateways/mcp`).
- The **chat loop** is described in 8 steps; the real path adds image-gen interception,
  chatprep locking, finalize-registry waiting, tool loop, and math pre-solve.

**Why it blocks scale / plug-out:** this is the first file every agent and every future
contributor reads, and `recall.mdc` (`alwaysApply: true`) points at it. An agent that trusts
it will put MCP work in the wrong place, or refuse RAG work as out of scope. Cheapest,
highest-leverage item in this review.

**Recommended fix:** refresh Service Overview, the directory tree, the chat-loop steps, and
the in-scope/non-goals lists to match code. Keep the Golden Rules verbatim — they are
accurate and load-bearing. State the MCP tool loop as flag-gated-off-by-default rather than
"not in scope", matching `FEATURES.md`.

**Do not:** weaken or reword the six golden rules; don't promote any ⚠️ FEATURES item to ✅
as part of this — documentation accuracy only.

---

**C10 — No test asserts WS and SSE speak the same protocol**
**Severity:** P2 · **Area:** tests · **Effort:** S

**Evidence:** the duplicated `stream_end` construction in C6 has no cross-transport
assertion. Test suites cover each transport independently.

**Recommended fix:** fold into C6 — one parametrised test over both transports asserting
identical event-type sets and `stream_end`/`done` key sets from the same result dict.

**Do not:** spin this up as its own PR; it is the acceptance test for C6.

---

## D. Weak / unwanted / missing inventory

| Item | Status | Evidence | Recommend |
|---|---|---|---|
| Turn quota/lock lifecycle | Weak (correct by vigilance) | `services/chat/stream.py` — 6 refund sites, 4 ownership flags | Keep & harden (C1) |
| Fence dispatch | Missing seam; lists already drifted | 5 files, 4 lang lists; `sources` known to 1 of 5 | Keep & harden (C5) |
| ` ```sources ` fence | Weak (no client renderer; relies on server strip) | emitted `web_search/formatting.py:289`, stripped l.272; mobile: `copyBlock.ts:328` only | Keep & harden via C5 registry + honest fallback |
| `vocab_quiz` fence | Weak (parallel dispatch path) | `lib/parseVocabQuiz.ts` (503 l.), never enters `RichFence` | Defer — note in FEATURES; don't fold into C5 |
| `contextSummarized` plumbing | Unwanted (banned-chip residue) | `assistantMessageContent.ts:44` declared, never read | Delete (C7) |
| `core/jobs.py` domain imports | Weak (inverted layer) | `core/jobs.py:24-38` | Keep & harden (C2) |
| `services/memory.py` | Weak (5 concerns, 961 l.) | see C4 | Keep & harden (C4) |
| `app/memory.tsx` mutations | Weak (logic in screen) | l.250, 346, 381 | Keep & harden (C3) |
| SSE endpoint triplication | Weak (copy-paste) | `chat_stream.py` ×3 | Keep & harden (C8) |
| Root `CLAUDE.md` | Missing-gap (contradicts code + FEATURES) | see C9 | Keep & harden (C9) |
| MCP tool loop | Missing-gap (⚠️ in FEATURES, "not in scope" in CLAUDE.md) | `tool_loop.py`, `gateways/mcp/`, flags default `false` | Defer to FEATURES; fix the doc claim (C9) |
| Attachment RAG | Missing-gap (shipped, doc says "Later") | `attachment_rag.py`, flag default `true` | Defer to FEATURES; fix the doc claim (C9) |
| `lib/vendor/` 8.4MB in-repo | Acceptable | lazy-split, zero static imports | Keep as-is — do not touch |
| `math_tools.py` 1,973 l. | Acceptable | registry-driven, 9 test files | Keep as-is — do not split |
| R2 storage credentials | Missing-gap (infra, not code) | `FEATURES.md:477` ⚠️ | Defer — deployment task, out of scope here |

---

## E. Sequenced cleanup plan

One concern per PR. Each lands independently, gate green (`./scripts/dev.sh check`),
commit + push, then the next.

1. **`docs: correct CLAUDE.md architecture to match the code`** — C9.
   *First because it is ~1 hour, has zero regression risk, and every later PR (and every
   later agent) reads it.* **Done:** no factual contradiction between `CLAUDE.md`,
   `FEATURES.md`, and the tree for MCP, attachment RAG, service list, and directory layout.

2. **`fix(mobile): drop dead contextSummarized plumbing`** — C7.
   *Second because it is the smallest possible diff and closes a banned-UX re-entry point
   before anyone touches the message pipeline.* **Done:** field gone from
   `assistantMessageContent.ts`, `useAssistantMessageContent.ts` deps, and the test fixture;
   mobile gate green.

3. **`refactor(api): own turn quota + lock in one async context manager`** — C1.
   *Third — highest risk item, and it wants to land before any new pre-stream step is added,
   not after.* **Done:** `pre_reserved`, `held_chatprep_lock`, `took_reservation_ownership`,
   `owns_lock` deleted; all three entry points use `async with turn_resources(...)`; existing
   quota/refund tests pass unchanged plus a new test asserting exactly one refund on cancel,
   on prepare failure, and on mid-stream error.

4. **`refactor(mobile): one fence registry for render, copy, and fallback`** — C5.
   *Fourth: the biggest plug-in win, and the most likely next feature area. After C1 so two
   large diffs are never in flight together.* **Done:** `lib/fenceRegistry.ts` is the single
   source of fence ids/langs/precedence; `richBlocks`, `RichFence`, `markdownFenceRender`,
   `fallbackFence`, `copyBlock` derive from it; round-trip test per registered id; zero
   visual diff.

5. **`refactor(api): background jobs self-register; core stops importing background`** — C2.
   *Fifth: independent of 3–4, unblocks adding jobs without touching `core/`.* **Done:**
   `core/jobs.py` has no `app.background` / `app.services` imports; each background module
   registers its own handler; one explicit registration entrypoint; DLQ/retry tests unchanged.

6. **`refactor(mobile): extract useMemoryActions from the memory screen`** — C3.
   **Done:** `app/memory.tsx` has no `api.` calls; `hooks/useMemoryActions.ts` owns
   snapshot/rollback; tests cover the 404-reload branch.

7. **`refactor(api): move remaining stream events into stream_events.py`** — C6 + C10.
   **Done:** no event payload constructed inline in either router; cross-transport parity
   test green.

8. **`refactor(api): split services/memory.py into a package`** — C4.
   *Late because it is a large mechanical move that will conflict with anything else touching
   memory; do it when the queue ahead is clear.* **Done:** `services/memory/` package with
   `__init__` re-exports; zero call-site changes in the diff; coverage on memory holds ≥90%.

9. **`refactor(api): dedupe chat SSE rate-limit preamble`** — C8.
   **Done:** one `require_chat_rate_limit` dependency; three routes keep their paths and
   response shapes.

**Later (parked, not scheduled):** fold `vocab_quiz` into the fence registry; revisit
`lib/vendor/` if repo size becomes painful; R2 production credentials (deployment, not code).

---

## F. Explicit non-goals

Considered and rejected:

- **Splitting `math_tools.py` / touching the math pipeline.** It is 1,973 lines but already
  registry-driven with 9 test files and documented ordering rationale. `docs/math.md` says
  don't churn it; the evidence agrees. Nearly filed this as a missing-registry finding before
  reading the file — it isn't one.
- **Extracting `lib/vendor/` to a CDN or postinstall fetch.** Already lazy-split with zero
  static imports; `scripts/vendor-cdn.mjs` exists. In-repo blobs are the deliberate,
  offline-safe choice. No user-visible win.
- **Consolidating the 21 `useChat*` hooks.** Inspected for the "send split across N hooks with
  no owner" pathology; it isn't there. `useChat` owns the wire, `useChatSend` owns composer
  intent, `app/index.tsx` composes with no direct API calls.
- **Unifying WS and SSE transports.** Cancel-frame vs disconnect-polling are genuinely
  different; only the *payload builders* should be shared (C6).
- **A `services/` reorganisation** (~60 flat modules alongside 5 subpackages). Real, but
  cosmetic churn that would conflict with every in-flight branch and buys nothing for the
  next features. Split modules when they hurt (C4), not by category.
- **Any new product surface** — no folders, no web client, no agents, no voice, no auth
  changes. None proposed here.
- **Coverage/gate changes.** No test deleted, no threshold lowered, no `# type: ignore` or
  `# noqa` added by any item above.
- **Touching the in-flight math render work** on `fix/mobile-math-no-gray-clip`. Reviewed for
  context only; it is unrelated to every finding here and should merge on its own.
