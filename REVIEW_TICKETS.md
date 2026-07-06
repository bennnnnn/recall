# Recall — Code Review Tickets (Jul 2026)

Tickets from the full-app review. One branch + PR per ticket; finish green
(`./scripts/dev.sh check`) before merging each.

| # | Ticket | Area | Status |
|---|--------|------|--------|
| R1 | [Fix regenerate prompt order](#r1-fix-regenerate-prompt-order) | API | ✅ |
| R2 | [Move pre-turn todo sync off critical path](#r2-move-pre-turn-todo-sync-off-critical-path) | API | ⬜ |
| R3 | [Fix `chat=None` shadowing in prompt_builder](#r3-fix-chatnone-shadowing-in-prompt_builder) | API | ⬜ |
| R4 | [Wire SSE AbortController into stopGeneration](#r4-wire-sse-abortcontroller-into-stopgeneration) | Mobile | ⬜ |
| R5 | [Add CSP to math WebViews](#r5-add-csp-to-math-webviews) | Mobile | ⬜ |
| R6 | [Refresh documentation drift](#r6-refresh-documentation-drift) | Docs | ⬜ |
| R7 | [Align local gate with CI](#r7-align-local-gate-with-ci) | Infra | ⬜ |

---

## R1: Fix regenerate prompt order

**Problem:** `stream_regenerate_response` calls `build_stream_prompt_context` before
deleting the last assistant message. The model sees the reply it is meant to replace,
causing repetition or weak regeneration.

**Fix:** Delete (or exclude) the last assistant message before building the prompt.

**Files:** `apps/api/app/services/chat/stream.py`, tests in `test_chat.py`.

**Acceptance:** Test asserts regenerate prompt excludes the deleted assistant message.

---

## R2: Move pre-turn todo sync off critical path

**Problem:** `prepare_chat_turn` awaits `sync_todos_before_reply`, which calls the LLM
before streaming starts. Violates golden rule #4 (background jobs must not block chat).

**Fix:** Remove pre-turn LLM todo extraction; rely on post-turn `sync_todos_from_transcript`
(already enqueued). Keep any fast, non-LLM path if needed.

**Files:** `apps/api/app/services/chat/turn_prep.py`, `apps/api/app/services/todos.py`,
tests.

**Acceptance:** `prepare_chat_turn` no longer awaits LLM todo extraction; post-turn sync
unchanged; tests green.

---

## R3: Fix `chat=None` shadowing in prompt_builder

**Problem:** `build_prompt_messages` sets `chat = None` at the top, discarding the
`chat` argument callers pass to avoid an extra DB query.

**Fix:** Use the passed-in `chat` when provided; only fetch when `chat is None`.

**Files:** `apps/api/app/services/chat/prompt_builder.py`, tests.

**Acceptance:** Regression test: when `chat` is passed, `get_by_id` is not called.

---

## R4: Wire SSE AbortController into stopGeneration

**Problem:** `stopGeneration` only sends WebSocket `{ type: "cancel" }`. SSE fallback
(`lib/chatSse.ts`) supports `AbortSignal` but `useChat` never wires it. Users on SSE
cannot stop server-side generation.

**Fix:** Hold an `AbortController` ref in `useChat`; pass `signal` to SSE calls;
abort on `stopGeneration`.

**Files:** `apps/mobile/hooks/useChat.ts`, optional test in `lib/__tests__/`.

**Acceptance:** `stopGeneration` aborts in-flight SSE fetch; WS path unchanged.

---

## R5: Add CSP to math WebViews

**Problem:** `ChartBlock` and `HtmlPreviewModal` inject CSP via `previewSandbox`; math
HTML (`lib/mathHtml.ts`, `lib/katexRender.ts`) loads MathJax from CDN without the same
sandbox policy.

**Fix:** Apply `injectPreviewCsp` (or equivalent) to math WebView HTML builders.

**Files:** `apps/mobile/lib/mathHtml.ts`, `lib/katexRender.ts`, tests.

**Acceptance:** Test asserts math HTML includes the same CSP meta tag as chart preview.

---

## R6: Refresh documentation drift

**Problem:** Docs lag shipped code — Apple sign-in marked deferred in `FEATURES.md`,
`CLAUDE.md` "Later" list understates pgvector/RevenueCat/Sentry/worker, alembic head
stale in `README.md` / `DEPLOY_TICKETS.md`.

**Fix:** Update `FEATURES.md`, `CLAUDE.md`, `README.md`, `DEPLOY_TICKETS.md` to match
code (head `0041`, Apple ✅, etc.).

**Acceptance:** No factual contradictions between docs and code for listed items.

---

## R7: Align local gate with CI

**Problem:** CI runs `alembic upgrade head` before pytest; local `scripts/check.sh`
does not.

**Fix:** Run migrate when `DATABASE_URL` is set (or always with test DB URL in check).

**Files:** `scripts/check.sh`.

**Acceptance:** `./scripts/dev.sh check` runs migrate step when DB is available; skips
gracefully when not.
