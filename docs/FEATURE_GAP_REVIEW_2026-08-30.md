# Recall — Feature gap review (30 Aug 2026)

Reviewed at `origin/main` (`7f47da6c`, live talk #1092 squash-merged). Product + security
pass against shipped code, not FEATURES.md as gospel. Prior architecture review
(`docs/CODEBASE_REVIEW_2026-08.md`) is not re-litigated: `turn_resources`, fence registry,
and CLAUDE.md map updates look closed.

**Merge hygiene this session:** working tree was already clean; stash empty. #1092
squash-merged after API CI green. Leftover squash heads (`fix/algebra-compact-roots`,
`fix/durable-local-attachments`, `fix/live-talk-interrupt`) pruned. No open PRs.

**Severity:** P0 = user-visible break or exploitable quota/auth hole you can hit without
trying. P1 = real product or security gap users or a motivated client will hit. P2 = debt,
overclaim, or a second door.

This is a findings report. It does not implement fixes.

---

## Highest-priority board

| Pri | Area | Gap |
|-----|------|-----|
| P1 | Web search | Default MCP tool loop never attaches source chips; snippets are unwrapped |
| P1 | Web search | Model can skip search on “needs search” turns; extra `web_search` calls each burn a Tavily slot |
| P1 | Streaming | New chat / leave **SSE** cancels the LLM (WS drains). Partial persist still runs |
| P1 | Live talk | Client abort (`CancelledError`) skips refund/`finally`; pending TTL 90s then the slot sticks |
| P1 | Learning | Lesson misses never PATCH `was_correct: false`; one later correct tap masters the word |
| P1 | Schedule | Recurring reminders need the app open (`server_todo_push_enabled` default false) |
| P1 | Notifications | “Push off” does not cancel local Schedule alerts |
| P1 | Memory | File/OCR excerpts go into the memory extract transcript (todos already strip these) |
| P1 | TTS | `lead`/`rest` follow-up is unbound to the lead text — other rest text can ride unbilled |
| P1 | HTML Run | `PREVIEW_CSP_LIVE` allows full http(s) script + `fetch` for model HTML |
| P1 | Web client | Access + refresh tokens in `sessionStorage` |
| P1 | Templates | SMS/social cards do not strip `[Name]` placeholders; web has no draft cards |

No classic P0 IDOR or “keys in the mobile app” found on this pass.

---

## 1. Web search (industry-standard search)

Default: `mcp_tool_loop_enabled=True`. Heuristic inject (`build_search_augmentation`) **returns
empty** when the tool loop is on (`apps/api/app/services/web_search/augment.py`). Live search
is a non-streaming `web_search` tool round (`tool_loop.py`, up to 30s) then a second stream.

### Gaps

**P1 — Source chips never attach on the default path.**
`enrich_final_content` only sets `search_sources` / ````sources`` if `ctx.search_sources`
is filled (`stream_pipeline.py`). `WebSearchAdapter.invoke` returns plain text; it never
writes hits onto the turn context. FEATURES “source links under the reply” is true only
when the tool loop is **off**.

**P1 — Prompt injection wrapper skipped.**
Heuristic path: `wrap_untrusted("web search", block)`. Tool path: raw title/url/snippet
as `role: tool` (`web_search_adapter.py`, `tool_loop.py`). Poisoned snippets are the case
`prompt_safety.py` was written for.

**P1 — Search is optional for the model.**
`turn_needs_tool_loop` only *offers* the tool. If the model answers without calling
`web_search`, there are no live results and no sources. The old heuristic path forced Tavily.

**P1 — One Tavily budget per `run_cached_search`, not per turn.**
Several `web_search` tool calls in one round each create a new `_TurnTavilyBudget`. Free
20/day can drain faster than FEATURES implies.

**P2 — Classifier unused on the default path.**
`classify_web_search` only runs in `build_search_augmentation`. The tool gate is the sync
`needs_web_search` heuristic.

**P2 — Redis down on Tavily reserve fails the turn** instead of DDG-only. FEATURES says
cap → “then DDG only.” DDG itself is uncapped (abuse = latency, not Tavily $).

**P2 — Global search cache** keyed by query hash, not `user_id`. Fine for public results;
still cross-user reuse of identical queries.

### Checked — no material gap

- Tavily key only on the backend; mobile has no search keys.
- Server does not fetch result URLs (no SSRF on hits). Chip open uses `openAllowedUrl`
  (blocks `javascript:` / `data:`).
- Quiz letter answers skip `needs_web_search`; mobile hides chips on quiz fences.
- When Tavily is reserved and fails or is capped, DDG runs if fallback is on.
- Per-user Tavily Redis key includes `user_id`.

**What good looks like:** Treat MCP `web_search` like the heuristic path — structured hits,
`wrap_untrusted`, `ctx.search_sources`, one Tavily budget per turn — or stop short-circuiting
heuristic inject (as FEATURES still claims).

---

## 2. Learning

Catalog FK / `MissingGreenlet` look **fixed** (`ensure_catalog_rows`, snapshot `user_id`
before `expire_all`). Chat A–D grading is intentionally stubbed (`minimal_quiz=False`).

**P1 — Lesson wrong answers never hit the miss ledger.**
`useLessonSession.finishWord` only PATCH `{ status: "mastered" }`. Wrong taps are haptic /
local. Backend `update_item` supports `was_correct` + `QuizMissEvent`. Failed-today / SM-2
misses ignore in-lesson fails; one later correct tap masters the word.

**P1 — Path seed still runs on `GET /projects/{id}`.**
`get_project_detail` can `seed_language_path` + `expire_all()` on a read. Reliability
footgun (timeouts) even though the FK crash is gone.

**P2 — SM-2 fields are written; there is no due-queue / self-rate UI.** FEATURES already
marks this incomplete; still a hole if users expect Anki-like review.

**P2 — Residual ````vocab_quiz`` prompt/UI** while chat quizzes are disabled. Old fences
can show chips with no ledger effect.

**P2 — Catalog is en/es only.** Fine if documented as a hard limit.

---

## 3. Library

`~/.recall/attachments`, `message_id IS NOT NULL` on gallery list, client drop of 404
thumbs, path-under-base, `get_by_id(..., user_id)` — the reboot-404 class of bug looks
fixed.

**P2 — List skips missing local blobs without deleting the row.** `/file` can drop; list
`continue`s. Neon can keep forever-hidden orphans.

**P2 — Thumbs are uncached** (`/file?w=` resizes every time). A large grid can bump the
REST 240/min limit.

**P2 — Orphan grace is 24h** of billed storage after unlink / failed R2 delete.

---

## 4. Schedule

Repeat picker in one sheet; chat extract skips undated adds; no project filter chips on
the Schedule UI (banned UX honoured).

**P1 — Lists banned in UI; API still creates undated items.**
`ListItemCreate.due_at` is optional; `create_todo` allows `due_at is None`;
`DELETE /todos/topic/{topic}` still deletes undated rows. Any client can recreate Lists.

**P1 — Recurring fire depends on app open.**
`server_todo_push_enabled` defaults **false**. Local notification is one-shot; next
occurrence is scheduled when Schedule/todos refresh. FEATURES “repeats fire a device push”
overclaims reliability.

**P2 — ````reminder`` fence has no per-reply create cap** (extract path caps at 12).
**P2 — `project_id` still accepted on the todo API** (mobile does not show it).

---

## 5. Notifications

Gmail re-push `session.get` on finalize looks **largely fixed**. Email reminders opt-in
default off. Gmail send is not implemented (readonly).

**P1 — Settings “push off” does not mute local Schedule alerts.**
`togglePush(false)` unregisters Expo tokens only. `cancelAllTodoReminders` runs on
logout, not on mute. Local `syncTodoReminders` keeps firing.

**P1 — Same recurrence hole as Schedule** for delivery.

**P2 — Gmail suggestion push body = extracted title** (LLM/ICS over inbox). Hostile
subject → lock-screen text. Prompt inject is wrapped; push is not.

**P2 — Finalize fallback** `todo_row if todo_row is not None else todo` can still touch a
detached ORM row if `session.get` misses.

**P2 — One global push switch** for learning + calendar + email suggestions.

---

## 6. TTS (read aloud)

Keys stay on the backend. Empty Whisper is `""` (not 502). Lead/rest JSON starts the
first sentence before the rest. Catalog aliases (`speech-tts-model` / fast Kokoro).

**P1 — Unbilled `rest` after any `lead`.**
Follow-up Redis value is `clips:remaining_chars` keyed only by `user_id`
(`_tts_followup_key`). It is **not** bound to the lead text. For 120s a client can
synthesize different rest text unbilled (up to remaining chars).

**P1 — Expo Go / no-mic builds kill read-aloud.**
`loadSpeech()` and cloud TTS are gated on `canUseVoiceInput()`. Mic permission incorrectly
disables speaker. FEATURES “device fallback” is also unwired: `preferCloud` is never
passed; cloud 502 → “unavailable” with working `expo-speech`.

**P2 — FEATURES markets `/speech/tts/stream`; mobile uses buffered JSON lead/rest.**
Comment in `pronunciation.ts`: raw PCM was static on device. Stream endpoint is
server-ready, client-orphaned.

**P2 — TTS 502 copy does not distinguish “API down” vs “speech model failed.”**

---

## 7. STS / live talk

SSE WAV clips, parallel Whisper, persist user+assistant, `chat_id` scoped with
`get_by_id(..., user_id)`, mute = mic not pause — the 20s JSON + ignored-transcript
bugs look fixed.

**P1 — Abort before first audio does not refund.**
`body_iter` refunds in `except Exception`. Client abort is `CancelledError` /
`GeneratorExit`. Mobile never calls `/live/refund`. Pending flag TTL is **90s**; after
that `refund_live_talk_if_pending` is a no-op and the daily slot sticks. Abort after
audio can skip `clear_pending` + persist (charged, no chat rows).

**P1 — Non-wav/mp3 fallback echoes the user.**
`live_talk_stream.py`: unsupported container → Whisper + TTS of the **same** transcript
as “assistant.” A bad Android “.wav” becomes a paid echo.

**P2 — Dead `/live/turn|refund|commit`.** Speak reserves itself. Dual-reserve if an old
client still calls turn+speak.

Not full duplex (deferred, honest). Overlay still covers the thread until close.

---

## 8. Streaming

WS: Stop = cancel; New chat disconnect **drains** and finalizes. `turn_resources` owns
quota refund. Connect timeout 1.5s → SSE latch. Banned chips are not copied onto
`Message`.

**P1 — New chat on SSE cancels generation.**
`useChat` `useEffect([chatId])` always `sseAbortRef.abort()`. SSE `watch_disconnect`
cancels the producer (`chat_stream.py`) — opposite of WS drain. `persist_finalize_if_pending`
saves a **truncated** assistant. After a proxy forces SSE, New chat violates the product
rule.

**P1 — Inflight stream registry is WS-only** (`ws.py`, not `chat_stream.py`). GET
`/messages` cannot wait on an SSE producer the same way.

**P2 — chatId effect zeroes streaming UI** on every switch (OK if the server finishes;
harmful when SSE truncates).

---

## 9. Routing

Auto heuristic, physics-homework cues, `_pick_strongest_from_pool` when smart is missing,
fallback by **tier proximity** then price — the “Auto threw away smart-chat for cheapest”
bug looks **fixed**. App code uses aliases; provider slugs stay in the catalog.

**P2 — Multiple smart models: pick cheapest smart, not strongest.**
**P2 — Cue lists are finite** (bare “physics” stays fast by design).
**P2 — Unknown override alias silently falls back.**

---

## 10. Templates (email, message, social, translation)

Email placeholder stripping works (`emailDraftSanitize.ts` + `parseEmailDraft`). Prompt
bans `[Manager's Email]` and says Recall cannot send. Cards: `EmailCard`, `MessagePreview`,
`SocialPostCard`. Gmail/SMS send are correctly **not** implemented.

**P1 — Only email is sanitized.** SMS/social copy `text` raw. `[Name]` survives Copy.

**P1 — Web slice has no draft cards.** Unknown fences become `<pre>`. Copy UX is mobile-only.

**P2 — No translate fence/card.** “Translate this” is ordinary chat. UI i18n (~350 English
leftovers in non-en locales) is a separate 🔜 item — don’t conflate.

**P2 — LinkedIn/caption asks rely on FORMAT_CONTRACT;** email-style “draft immediately”
is gated on email/SMS cues.

---

## 11. Tables

Mobile: GFM, swallowed-fence unwrap, horizontal pan, freeze-first column. HOWTO hint
blocks N-week plans as grids. Web DOMPurify **does** allow `table` tags (old “tables
vanished” bug is fixed).

**P1 — Web has no `normalizeMarkdownTables` / swallowed-fence split.** Loose pipes or a
table inside ````python`` still vanish or land in `<pre>` on web.

**P2 — HOWTO gate is English-heavy;** odd phrasing still becomes a clipped grid.
**P2 — Web tables CSS-scroll only** (no frozen first column).

---

## 12. Attachments

Magic-byte confirm, 10 MiB cap, plain `[Image:]`/`[File:]` in bubbles, RAG wrapped,
orphan reaper + pending R2 deletes, IDOR via `user_id`. Vision vs text-layer vs OCR-on-index
matches FEATURES.

**P1 — Textish MIME skips magic.** `text/plain` / json / csv / md accept any bytes
(`bytes_match_claimed`). Polyglot payloads can be stored and served with that type.

**P1 — GDPR residual:** failed R2 deletes live in Redis; account delete drops DB rows.
Bytes can outlive the row if Redis/reaper fails. Need a bucket lifecycle / prefix sweep.

**P2 — Attachment RAG is chat-scoped** (correct vs FEATURES 🔜 user-wide). Users still
expect Library files to answer in a **new** chat.

---

## 13. Math scanner

Camera → exact `MATH_CAMERA_PROMPT` → vision JSON → SymPy for a **subset** of kinds
(`docs/math.md` is more honest than FEATURES “vision → SymPy”). Keypad is shipped.
Freehand/diagrams are banned in the extract prompt; only the first image is used.

**P1 — Unsupported / handwritten / multi-problem falls through to an unverified LLM
with no “couldn’t verify” chip.** FEATURES slightly oversells a homework camera.

**P2 — Caption edit after scan can drop the OCR gate** (exact prompt or math keyword).
**P2 — Dev-build camera is not called out next to the FEATURES camera line.**

---

## 14. Memory

Typed sections, confidence, merge gates, first-party wrap, Memory screen edit/delete,
semantic recall for fact/focus/project. Transcript cap ~4k head+tail.

**P1 — Attachment/OCR text is in the extract transcript.**
`enqueue_post_turn_jobs` uses `User: {ctx.user_message_content}` with **no**
`strip_untrusted_blocks` / `text_before_attachment_markers` (todos **do** strip).
FEATURES “only user-stated facts” is false for PDF dumps.

**P1 — Sensitive memories are stored and shown on Memory, then excluded from chat inject**
(`exclude_sensitive=True`, health/legal/finance/relationship). “It forgot my allergy”
is the product outcome. Undocumented.

**P1 — Extract prompt still “rewrite the full section.”** Consolidation merges; extract
can drop facts under the anchor floor.

**P2 — Assistant lines are in the extract transcript** despite “User line only.”

---

## 15. RAG

Attachment RAG: chat-scoped, first turn = inline excerpt, OCR on the index job, wrapped.
History RAG: user-wide `message_chunks`, excludes recent message ids, never full
transcript, wrapped as “past conversations.” Golden Rule 3 holds.

**P1 — Same-turn “summarize page 3” misses chunks** until the index job finishes. No
“still indexing” UX.

**P1 — No filename/page on injected chunks.** FEATURES 🔜 citations is honest; users
still cannot tell which file a claim came from.

**P2 — Cross-chat history RAG can surprise** (“why did that other chat show up?”).
Label exists in the wrap text; no “this chat only” control.

**P2 — History RAG skipped on slim/casual turns.**

---

## 16. Rest of catalog

### Auth / quotas — no new P0

JWT HS256 + jti revoke + refresh rotation; production refuses weak `JWT_SECRET`,
`DEV_AUTH`, empty CORS `*`, missing RC webhook secret. REST/chat/auth rate limits
fail-closed. Quota Redis miss → `RedisUnavailableError` (fail-closed, not free chat).

### Image gen

Composer-only (no prompt sheet). Pro + daily cap + chat ownership. MCP `generate_image`
is Pro-gated. Stop/cancel path exists.

### MCP / tools

Default **on**. Calendar MCP is conflicts-only; create is `calendar_proposal` + confirm.
Gmail is readonly. SymPy sandboxed.

**P2 — `turn_needs_tool_loop` is true for calendar-create**, which pays a useless
non-streaming round. `.cursor/rules/recall-api.mdc` still says the loop defaults off
(CLAUDE.md / FEATURES / config say on).

### Calendar / Gmail

Confirm-before-create; proposals keyed by `user_id`. No send-mail API. Nudges wrapped
as untrusted in the prompt.

### HTML preview

Default `PREVIEW_CSP`: `connect-src 'none'`, no eval. Charts: `unsafe-eval` **only** on
the Vega document (tested).

**P1 — HTML Run (`PREVIEW_CSP_LIVE`)** allows `script-src` / `connect-src` http(s). Model
HTML can load remote JS and `fetch`. App JWT is not in the WebView (not token theft);
still a sandbox hole for anything painted in the preview. `originWhitelist={["*"]}`.

### Web client (slice 1)

Login + SSE chat + GFM. **P1 sessionStorage tokens** (refresh stealable via XSS). No
document CSP. Rich fences / Memory / Learning / attach deferred (honest).

### Billing

Webhook HMAC compare; prod requires secret; unsigned → 503 unless explicit
`DEV_ALLOW_UNAUTHED_WEBHOOKS`.

**P1 — `INITIAL_PURCHASE` / `RENEWAL` / `PRODUCT_CHANGE` stamp `plan=pro` without an
entitlement re-fetch** (TRANSFER does `resolve_plan_from_revenuecat`). Fine for a single
Pro SKU; wrong-product mapping is the extra gap.

**P1 — Idempotency skipped when `event_id` is absent.**

### i18n

Key-set parity enforced (~959). ~350 non-en values still English. Legal pages English-only.
Launch debt, not a security hole.

### Banned UX

No recalled-memory chip, no assistant Show more/less, no Schedule project chips, no
image-gen sheet, no Lists row in the drawer. API undated todos are the leftover door
(§4).

---

## What is actually in good shape (checked)

- Provider keys not in the mobile app.
- Attachment / chat / todo / project / live-talk `chat_id` reads scoped by `user_id`.
- Gmail cannot send; calendar write is confirm-gated.
- STT empty audio is not a 502.
- Live talk transcripts persist when the SSE `done` path runs.
- Routing strongest-in-pool when Auto wants smart and the free pool has none.
- Production boot guards (JWT, CORS, RC, OpenRouter, spend kill-switch).
- Chart `unsafe-eval` does not leak onto user-HTML CSP.

---

## Suggested order if you act on this

1. Web search: wrap + source chips + one Tavily budget on the MCP path (or restore heuristic inject).
2. SSE leave = drain (parity with WS); live-talk `finally` refund/persist on abort.
3. Lesson miss ledger; Schedule API require `due_at`; push-off cancels local reminders.
4. Strip attachments from the memory extract transcript; bind TTS `rest` to the lead hash.
5. HTML Run allowlist or lock; web httpOnly refresh before real web users; RC entitlement check.

Do not treat FEATURES 🔜 rows (full duplex, user-wide file RAG, locale prose, music gen,
claim citations) as bugs — those are already deferred honestly.
