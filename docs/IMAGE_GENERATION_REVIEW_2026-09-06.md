# Recall — Image Generation (Pro) Code Review (Sep 2026)

Scope: **only** image-generation intent detection/interception in the chat turn,
the generation call + quota/cost control, and storage of the resulting image.
Modeled on `docs/STT_LIVE_TALK_REVIEW_2026-09-05.md`'s C1 finding (daily-cap
reservation at the wrong granularity, with a dead refund path). Not a review
of chat text, memory, Learning, or any other domain. Reviewed at `main`
(`cb245e81`, "Fix chat persistence, file/image fidelity, and OpenAI voice
reliability (#1181)").

---

## A. Verdict

**Unlike Live Talk, image generation gets the fundamental reservation unit
right, and the everyday refund paths are real and tested.** The daily cap is
reserved atomically with a single `INCR`-then-rollback
(`apps/api/app/services/quota.py:124-148`) immediately before the expensive
provider call, per request — not per session — so there is no
granularity mismatch and no TOCTOU gap: concurrent requests from the same user
across different chats race on one atomic Redis key
(`imggen:{user_id}:{date}`) and the loser always gets its slot back. The
common failure modes (oversized/invalid provider output, DB persist failure,
attachment-link failure) all refund correctly and are covered by tests with
explicit `incrby` assertions
(`apps/api/app/tests/test_routers_images.py:67-106,248-305`). The Pro gate is
enforced server-side at three independent call sites, not just hidden by
mobile UI, and provider-returned image URLs are fetched through the
SSRF-safe/DNS-pinned helper with a private-IP block — security work nobody
asked for in this scope but worth flagging as genuinely good.

**The one place this system reproduces Live Talk's exact bug class is
cancellation.** `generate_for_chat`'s cleanup only catches
`ImageGenerationError` and `Exception`
(`apps/api/app/services/image_generation.py:290,297`) — never
`BaseException` — so an `asyncio.CancelledError` delivered while the 120s
provider call, a storage write, or the DB commit is in flight skips both the
quota refund and the storage-object rollback. This is not a hypothetical: the
same turn's own async-generator chain is cancellable end-to-end by design —
WS "Stop" calls `producer.cancel()` (`apps/api/app/routers/ws.py:204,217`) and
SSE disconnect-polling does the same
(`apps/api/app/routers/chat_stream.py:124-127`) — and *both* of image
generation's in-chat-turn entry points (`_try_image_gen_for_turn` at
`apps/api/app/services/chat/stream_entry.py:37-107`, invoked from inside
`stream_chat_response`'s cancellable body at line 199, and the owned
tool-loop's `ImageGenAdapter.invoke` at
`apps/api/app/services/mcp/image_gen_adapter.py:102`, invoked from the same
cancellable turn) sit directly on that call chain. The codebase has already
fixed this exact bug class twice elsewhere (`turn_resources.py:94`,
`sympy_executor.py:155`, `attachment_reuse.py:56`, and a dedicated regression
test at `test_stream_quota.py:100-150` whose docstring literally says
*"Hard cancel (CancelledError) must refund — except Exception would miss
it"*) — it just wasn't applied to `image_generation.py`. See **F1**.

**The second Live-Talk-shaped gap is real and directly transferable:** the
global per-day OpenRouter spend kill-switch that gates production boot
(`daily_global_spend_usd`, required `> 0` — `apps/api/app/core/config.py:427`)
is wired to text chat and nowhere else, exactly as C3 found for voice. Image
generation is a second, independent LLM/provider cost path with zero calls to
`record_global_spend` / `global_spend_exceeded`. See **F2**.

Everything else is smaller: there is no per-user total-storage cap or expiry
for generated images (only a small daily *count* cap — F3), no rate limit
layered on top of the daily cap the way speech endpoints have one (F4), and
the intent-detection heuristic is hand-duplicated in TypeScript and Python
with no parity test (F5, informational — the backend gate is authoritative
regardless of client-side drift).

---

## B. What's working (don't "fix" these)

- **Reservation unit and timing are correct — the exact thing Live Talk got
  wrong.** `reserve_image_generation` → `_reserve_daily_slot`
  (`apps/api/app/services/quota.py:409-410,124-148`) is one atomic `INCR`
  per `generate_for_chat` call (one *image request*, not one *session*), and
  it happens at `apps/api/app/services/image_generation.py:153-155` — after
  ownership/storage checks but **before** the 120s provider call
  (`apps/api/app/gateways/image_gateway.py:18`). The `INCR`-then-rollback
  shape means a race between two concurrent requests from the same user
  cannot both pass: the loser's `new_total > limit` check fails and it gives
  its slot back inline, atomically, no separate compare-then-set window.
- **Refund symmetry is real for every *synchronous* failure branch and is
  tested, not just written.** Empty-prompt-after-reserve
  (`image_generation.py:161-164`), oversized/invalid provider output, failed
  content-type/signature validation, and any exception from storage/DB persist
  all refund via the `except ImageGenerationError` / `except Exception` blocks
  (`image_generation.py:290-302`) — and three of these are asserted with
  exact `incrby(-1)` calls, not just "no exception":
  `test_generate_image_quota_exhausted`, `test_generate_image_rejects_oversized_result`
  (asserts `incrby.await_count == 2` and the second call is `-1`), and
  `test_generate_image_deletes_storage_when_persist_fails` (same assertion,
  plus `gateway.delete_bytes.assert_awaited_once_with(storage_key)`) —
  `apps/api/app/tests/test_routers_images.py:44-106,248-305`.
- **Storage rollback on write-then-fail is real, not aspirational.**
  `_rollback_written_bytes` (`image_generation.py:53-64`) is called for both
  the generated-image key and every reference-image copy on any failure path,
  with the comment explaining exactly why: *"The orphan reaper only sees
  attachment rows. A write with no row... would leak the object forever
  without this rollback."* Covered by
  `test_image_reference_persistence_is_atomic_and_regeneration_reuses_input`
  (`apps/api/app/tests/services/test_image_reference_persistence.py:75-80`,
  asserting `gateway.delete_bytes.await_count == 2` on a link failure) and
  `test_generate_image_deletes_storage_when_persist_fails`.
- **The free-tier gate is enforced server-side at every reachable entry
  point, not just hidden by mobile UI.** `plan_service.is_pro(user)` is
  checked independently in the HTTP router path
  (`image_generation.py:134-135`, raising 403 — tested by
  `test_generate_image_requires_pro`), the pre-stream chat intercept
  (`stream_entry.py:50-51`, returning `False` to fall through to a normal
  turn rather than erroring), and the tool-loop adapter
  (`image_gen_adapter.py:90-94`, plus `_tools_for_user`
  (`apps/api/app/services/tool_loop.py:283-288`) omitting the tool from the
  model's toolset entirely for non-Pro users) — three independent layers, and
  even a hypothetical bypass of `is_pro` still hits `daily_image_generations`
  defaulting to `0` for free (`core/config.py:194`), which
  `_reserve_daily_slot`'s `if limit <= 0: return False`
  (`quota.py:136-137`) refuses unconditionally.
- **No double-generation within one turn.** The pre-stream intercept
  (`try_image_gen_for_turn`, `stream_entry.py:199-210`) runs and, on a match,
  `return`s before `prepare_chat_turn`/the tool loop is ever reached — so the
  tool-loop's own `generate_image` tool (`image_gen_adapter.py`) cannot also
  fire for the same message. Both paths independently gate on the *same*
  `extract_image_gen_prompt` (imported directly by
  `tool_loop.turn_needs_tool_loop`, `apps/api/app/services/tool_loop.py:261,277`),
  so there is no message that both paths would classify differently and race
  on.
- **Mobile mirrors the server-authoritative design correctly.** The composer
  send path (`apps/mobile/hooks/useChatSend.ts:298-327`) detects intent
  client-side and calls `POST /images/generate` directly instead of the
  normal WS/SSE chat send, with an explicit comment: *"Do not gate on client
  isPro... submitPrompt / the API [will] open upgrade or generate."*
  (`useChatSend.ts:299-300`) — i.e. the client deliberately does not trust
  its own Pro check and lets the 403 from the server drive the upgrade
  prompt (`apps/mobile/hooks/useImageGeneration.ts:229-232`).
- **Provider-returned image URLs are fetched SSRF-safely.** When OpenRouter
  returns a `url` instead of inline `b64_json`, the gateway resolves and pins
  the DNS lookup and fetches by IP with an explicit `Host` header
  (`apps/api/app/gateways/image_gateway.py`, exercised by
  `test_generate_image_openrouter_url_response_is_fetched_ssrf_safely` and
  `test_generate_image_openrouter_url_response_blocks_private_ip`,
  `apps/api/app/tests/services/test_image_generation.py:123-165,283-306`) —
  a real defense against a compromised/malicious provider response pointing
  at `169.254.169.254` or an internal host, not asked for by this scope but
  worth calling out.
- **Reference-image ownership and blast radius are bounded.**
  `load_reference_images` scopes the lookup by `user_id`
  (`image_generation.py:307-318`, `attachments_repo.get_by_ids(session, ids,
  user_id)`), rejects non-image content types, rejects oversized/invalid
  bytes, and caps the reference count at 2
  (`image_generation.py:311-313`) — tested by
  `test_reference_lookup_rejects_another_users_image_before_reading_storage`
  (`test_image_generation.py:108-120`), which explicitly asserts
  `gateway.read_bytes.assert_not_awaited()` for an unauthorized id.
- **Last-line-of-defense size check matches the rest of the attachment
  pipeline.** `image_generation.py:180-189` re-checks `MAX_ATTACHMENT_SIZE`
  on the generated bytes even though the gateway already enforces it,
  explicitly modeled on the same double-check every normal upload gets in
  `routers/attachments.py` — good defense-in-depth, not redundant dead code.

---

## C. Findings — ranked

### Cost control / quota correctness

---

**F1 — `generate_for_chat`'s quota refund and storage rollback are not
`BaseException`-safe, so a WS "Stop" / SSE disconnect during an in-flight
generation burns a daily image-gen slot (and can orphan a stored object)
with zero image produced — the exact bug class fixed elsewhere in this
codebase but missed here**
**Severity:** P1 · **Area:** image-gen / cost-control · **Effort:** S

**Evidence:**
- `generate_for_chat` reserves the daily slot at
  `apps/api/app/services/image_generation.py:153-155`, then runs the 120s
  provider call, storage writes, and DB commit inside a `try:` block
  (`image_generation.py:168-289`) whose only exception handlers are
  `except ImageGenerationError as exc:` (l.290) and `except Exception:`
  (l.297). Since Python 3.8, `asyncio.CancelledError` inherits from
  `BaseException`, **not** `Exception` — neither handler catches it, so its
  cleanup (`_rollback_written_bytes` for the generated image and every
  reference copy, plus `quota_service.refund_image_generation`) never runs
  on cancellation; the exception propagates un-cleaned-up.
- This is directly cancellable in production, not a theoretical corner case.
  Image generation has exactly two in-chat-turn entry points, and both sit on
  a cancellable `asyncio.Task`:
  1. The pre-stream intercept `_try_image_gen_for_turn`
     (`apps/api/app/services/chat/stream_entry.py:37-107`) is awaited at
     `stream_entry.py:199` from inside `stream_chat_response`'s body, itself
     inside `async with seams.turn_resources(...)`
     (`turn_resources.py:67-101`).
  2. The owned tool loop's `generate_image` tool,
     `ImageGenAdapter.invoke` → `generate_for_chat`
     (`apps/api/app/services/mcp/image_gen_adapter.py:102`), runs inside
     `run_tool_rounds` which is called from the same turn's `prepare_chat_turn`
     path — the identical cancellable `Task`.
  Both transports cancel that task on user action: WS "Stop" calls
  `producer.cancel()` (`apps/api/app/routers/ws.py:200-204`, and again on
  disconnect-drain at l.216-217), and SSE cancels identically on
  disconnect-poll (`apps/api/app/routers/chat_stream.py:110-132`,
  specifically `producer.cancel()` at l.127). `asyncio.Task.cancel()`
  delivers `CancelledError` into whatever the task is currently awaiting —
  including a nested `await generate_image(...)` three calls deep inside
  `generate_for_chat`'s `try:` block. The provider call alone has a 120s
  timeout window for this to land
  (`apps/api/app/gateways/image_gateway.py:18`).
- `turn_resources`'s own `except BaseException:` handler
  (`apps/api/app/services/chat/turn_resources.py:94-96`) *does* correctly
  catch this cancellation one level up and calls `resources.refund()` — but
  that method only refunds `res.reserved_tokens`, the **text-token** usage
  counter (`turn_resources.py:45-55`, `quota_service.refund_usage`). It has
  no knowledge of the `imggen:{user_id}:{date}` counter reserved deep inside
  `generate_for_chat` — that is a completely separate Redis key namespace
  (`quota.py:401-414` vs. `quota.py:224-266`) that nothing at the outer layer
  can refund on the caller's behalf.
- The codebase has fixed exactly this bug class multiple times elsewhere,
  which makes the gap here a miss, not an unknown pattern: `turn_resources.py:94`,
  `apps/api/app/services/sympy_executor.py:155`, and
  `apps/api/app/services/attachment_reuse.py:56` all use
  `except BaseException:` specifically for cleanup-on-cancel. There is a
  dedicated regression test, `test_stream_chat_response_refunds_on_cancelled_error`
  (`apps/api/app/tests/services/test_stream_quota.py:100-150`), whose
  docstring states the lesson explicitly: *"Hard cancel (CancelledError)
  must refund — except Exception would miss it."* That lesson was applied to
  the text-token path and never re-applied to `image_generation.py`'s own
  reservation.
- No test exercises this: `grep -rn "CancelledError" apps/api/app/tests/services/test_image_generation.py
  apps/api/app/tests/services/test_image_reference_persistence.py
  apps/api/app/tests/test_routers_images.py` returns nothing, and
  `test_stream_chat_response_refunds_on_cancelled_error` mocks
  `_try_image_gen_for_turn` to return `False` (l.124-126) — i.e. it
  deliberately routes around the image-gen path and never exercises a
  cancellation *while inside* `generate_for_chat`.

**Why it matters:** the daily image-generation cap is small by design (10/day
Pro, 0/day free — `core/config.py:194-195`), which makes each slot
proportionally expensive to lose. A user who taps Stop (a normal, expected
action — the mobile UI's own Stop button is live for the whole turn via
`streamActive = llmBusy || imageGen.generating`,
`apps/mobile/app/index.tsx:268`) at the wrong moment during a
server-triggered generation permanently loses one of ten daily slots for a
request that produced nothing, with no user-visible error and no way to get
it back (there is no `/images/refund` endpoint the way Live Talk at least
has a — separately broken — `/speech/live/refund`). If the cancellation lands
after `write_bytes` succeeds but before the attachment row is created in the
DB (`image_generation.py:201` vs. `213-224`), the object is also orphaned in
storage with no row for the orphan reaper to ever find, which is a small but
real permanent R2 cost leak once production storage is live (see F3). This
matters more, not less, because the primary mobile flow calls
`POST /images/generate` directly (bypassing WS/SSE entirely, so this
specific class of cancellation cannot happen there — see B, "Mobile mirrors
the server-authoritative design") — meaning the two *reachable* paths for
this bug are precisely the pre-stream intercept and the tool loop, i.e.
exactly the cases CLAUDE.md calls out as "may return without an LLM turn"
and the owned-by-default tool loop, both of which exist specifically to
cover clients (including a future web client) that don't do the mobile
app's own client-side detection.

**Recommended fix (smallest seam):** change both handlers in
`generate_for_chat` to `except (ImageGenerationError, Exception) as exc:` →
a single `except BaseException as exc:` that branches on
`isinstance(exc, ImageGenerationError)` only to decide the refund
403/429 exemption, otherwise always refunds and rolls back storage, then
re-raises — mirroring `turn_resources.py:94-96` and
`attachment_reuse.py:56-64` exactly. Add one test parametrized the same way
as `test_stream_chat_response_refunds_on_cancelled_error`, but patching
`generate_image` (or `gateway.write_bytes`) to raise
`asyncio.CancelledError` and asserting `quota_service.refund_image_generation`
is awaited and `gateway.delete_bytes` is awaited when a key was already
written.

**Do not:** change the reservation granularity or the daily limit — those
are correct today (see B); this is purely about making the *existing*
refund/rollback code reachable on cancellation, not changing when or how
much is reserved.

---

**F2 — The global per-day OpenRouter spend kill-switch is wired to text
chat only; image generation is a second uncovered provider-spend path**
**Severity:** P1 · **Area:** cost-control / api · **Effort:** S

**Evidence:** `record_global_spend` / `global_spend_exceeded`
(`apps/api/app/services/quota.py:482-505`) are called from exactly three
places, all text-chat: `apps/api/app/services/chat/stream_pipeline.py:117`,
`apps/api/app/services/chat/post_turn.py:251,287`, and
`apps/api/app/background/handlers.py:106-108`.
`grep -rn "global_spend" apps/api/app/routers/images.py
apps/api/app/services/image_generation.py apps/api/app/services/image_gen_intent.py
apps/api/app/services/mcp/image_gen_adapter.py apps/api/app/gateways/image_gateway.py`
returns nothing. Production boot requires `daily_global_spend_usd > 0`
specifically *because* it is meant to be a universal backstop
(`core/config.py:427-431`, error text: *"UTC-day OpenRouter spend
kill-switch"*), but image generation — a paid OpenRouter model call
(`_IMAGE_MODEL_ALIAS`, `image_generation.py:38,95-102`) exactly like a chat
completion — never checks or records against it.

**Why it matters:** per-user daily caps exist for image generation (10/day
Pro) exactly as they do for Live Talk (30 sessions/day Pro), and F1 shows
those per-user caps can already leak. The kill-switch exists specifically as
the second, defense-in-depth layer for when a per-feature cap is wrong,
bypassed, or leaking — and it does not cover image generation at all, same
as C3 found for voice. Unlike voice, image generation cost per call is
comparatively bounded (one request, one provider call, capped output size),
which is why this is P1 rather than P0 — but it is still a real, zero-effort
gap in the one global safety net the product explicitly requires in
production.

**Recommended fix:** call `global_spend_exceeded(redis, settings)` in
`generate_for_chat` right after the Pro/enabled checks and before
`reserve_image_generation` (returning the existing 429/`ImageGenerationError`
path with a "try again later" message), and call `record_global_spend` with
the model's known per-image cost after a successful generation — OpenRouter
image pricing is fixed per call/resolution, so no usage-telemetry parsing is
needed, unlike text tokens.

**Do not:** fold this into the same change as F1 — reservation-cancellation
safety and kill-switch wiring are independently valuable and separately
reviewable, matching the Live Talk review's own guidance on C1 vs. C3.

---

### Storage cost / abuse control

---

**F3 — No per-user total-storage cap or expiry for generated images; only a
small daily *count* cap bounds growth, and it bounds it forever, not per
period**
**Severity:** P2 · **Area:** image-gen / storage · **Effort:** S/M

**Evidence:** `daily_image_generations_pro = 10`
(`core/config.py:195`) and `MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024`
(`apps/api/app/core/attachment_limits.py:3`) bound *daily* growth to at most
100MB/user/day, but nothing bounds *total* growth over the lifetime of a Pro
subscription: `grep -rn "total.*size\|SUM(\|storage.*limit"
apps/api/app/repositories/attachments.py apps/api/app/services/image_generation.py`
returns nothing, and the only cleanup job,
`attachment_orphan_reaper.py`/`_handle_storage_sweep`
(`apps/api/app/background/handlers.py:265-294`), only removes *unconfirmed*
uploads after `attachment_orphan_grace_hours` (24h,
`core/config.py:108`) — confirmed generated images (`mark_verified` is
called unconditionally right after generation,
`image_generation.py:286`) are permanent until the user manually deletes
them from the Library. FEATURES.md documents this daily cap as the entire
control (`FEATURES.md:1030`: *"daily image cap"*) with no mention of a
total-storage ceiling.

**Why it matters:** at the current small daily cap this is a slow leak, not
an acute one — but it is unbounded in principle, and R2 production
credentials are explicitly ⚠️ pending (`FEATURES.md:832-834`), meaning this
cost exposure has not yet been paid for in production and would compound
silently once it is. A single long-lived Pro subscriber generating near the
daily cap indefinitely accumulates tens of GB/year with no automatic
retention policy — this is the storage-cost analogue of Live Talk's
uncapped-session-duration finding (C1): a per-request cap without a
lifetime/total ceiling.

**Recommended fix:** add either (a) a per-user total-bytes-for-generated-images
soft cap enforced at `generate_for_chat`'s reservation step (reusing the
`imggen` Redis namespace with a bytes-sum key, or a cheap
`SELECT SUM(size_bytes)` scoped by `source='generated'` — batched, not
per-request, to avoid a query on every generation), or (b) a retention
policy (e.g. auto-expire generated images older than N days unless saved to
a chat the user still has), whichever matches the product's actual storage
budget. This is a product decision, not purely a code fix — flag for
explicit sign-off rather than picking a number unilaterally.

**Do not:** touch the daily *count* cap or `MAX_ATTACHMENT_SIZE` — those are
correct and already tested; this is about the *lifetime* ceiling, which is
currently absent, not the per-day one, which is fine.

---

**F4 — No rate limit layered on top of the daily cap for `/images/generate`,
unlike the analogous speech endpoints**
**Severity:** P3 · **Area:** image-gen / api · **Effort:** S

**Evidence:** `routers/speech.py`'s `_reserve_tts_or_raise` and
`/speech/transcribe` both check a short-window rate limit *and* the daily
cap (`SPEECH_RATE_LIMIT_MESSAGE`, `SPEECH_TTS_RATE_LIMIT_MESSAGE`,
`quota.py:39-40`); `routers/speech_realtime.py`'s `_reserve_realtime_or_raise`
does the same (`LIVE_TALK_RATE_LIMIT_MESSAGE`, `quota.py:53`). `images.py`
and `generate_for_chat` have no equivalent —
`grep -rn "rate_limit\|allow_request" apps/api/app/routers/images.py`
returns nothing.

**Why it matters:** low practical severity today — the atomic daily-cap
reserve (`_reserve_daily_slot`) already prevents exceeding 10 requests/day
regardless of burst pattern, so this is not a quota-bypass. It is a minor
defense-in-depth gap: without a rate limit, a user (or a compromised/scripted
client) can fire all 10 of their daily requests as fast as the client can
issue them, each holding an outbound 120s HTTP connection to OpenRouter
concurrently, which is a modest self-inflicted-DoS-shaped risk the other
provider-cost endpoints in this codebase already guard against.

**Recommended fix:** reuse the same `allow_request_fail_closed`/rate-limit
helper the speech endpoints call, with a generous window (e.g. 1/10s) — this
is about smoothing bursts, not lowering the daily cap.

**Do not:** treat as urgent; bundle into whatever PR next touches
`images.py` rather than opening a dedicated change.

---

### Minor / informational

---

**F5 — Composer image-gen intent detection is hand-duplicated in TypeScript
and Python with no parity test between them**
**Severity:** P3 · **Area:** image-gen / drift-risk · **Effort:** S

**Evidence:** `apps/api/app/services/image_gen_intent.py:1` states in its own
docstring that it *"mirrors mobile imageGenIntent.ts"* — two independent,
hand-maintained token-matching implementations
(`apps/mobile/lib/imageGenIntent.ts`, 321 lines;
`apps/api/app/services/image_gen_intent.py`, 592 lines) with no shared
fixture or cross-language golden-file test asserting they classify the same
set of example messages identically.

**Why it matters:** low severity because the backend is authoritative
regardless of what the client detects (see B) — a drift only causes a
message to be handled by the *other* of the two paths (client-side direct
call vs. server-side in-chat intercept), not a security or quota bypass.
It is, however, the same "two independently-maintained lists already
drifted" shape flagged as C5 in `docs/CODEBASE_REVIEW_2026-08.md` for fence
dispatch, and it is worth naming now while the drift is still hypothetical
rather than after the two files have silently diverged.

**Recommended fix:** a small parametrized test fixture (a shared JSON list
of `{text, expected_subject}` cases) consumed by both
`apps/mobile/lib/__tests__/imageGenIntent.test.ts` and
`apps/api/app/tests/services/test_image_gen_intent.py`, asserting both
implementations agree on the same inputs. Not urgent enough to block on.

**Do not:** try to unify the two into one shared library across
Python/TypeScript — that is a much larger change for a modest drift-risk
payoff; a parity test is the right-sized fix.

---

## D. Test coverage gaps (scope item 6)

**Solid today:** free-tier gate (`test_generate_image_requires_pro`), quota
exhaustion (`test_generate_image_quota_exhausted`), refund-on-oversized-result
with exact `incrby` assertions (`test_generate_image_rejects_oversized_result`),
refund-on-persist-failure with storage rollback assertions
(`test_generate_image_deletes_storage_when_persist_fails`), reference-image
ownership rejection (`test_reference_lookup_rejects_another_users_image_before_reading_storage`),
atomic reference-copy persistence across regenerate/link-failure branches
(`test_image_reference_persistence_is_atomic_and_regeneration_reuses_input`,
3 parametrized cases), SSRF-safe URL-response fetch + private-IP block (2
tests), oversized-payload rejection on both provider response shapes (2
tests), content-type casing normalization, the model-callable adapter's
context-binding/non-Pro/success/error branches (`test_image_gen_adapter.py`,
4 tests), and the pre-stream intercept's mobile-mirrored intent matching
(`test_image_gen_intent.py`, plus the mobile `imageGenIntent.test.ts` /
`imageGenTurn.test.ts` suites) — all real coverage, not padding.

**Missing:**

| Gap | Evidence |
|---|---|
| No test for `CancelledError` during `generate_for_chat` (quota leak / no rollback) | `grep -rn "CancelledError" apps/api/app/tests/services/test_image_generation.py apps/api/app/tests/services/test_image_reference_persistence.py apps/api/app/tests/test_routers_images.py` → no matches; F1 |
| No test asserting `_try_image_gen_for_turn` or `ImageGenAdapter.invoke` propagate a cancellation with the outer turn's refund still correct | `test_stream_chat_response_refunds_on_cancelled_error` (`test_stream_quota.py:100-150`) explicitly mocks `_try_image_gen_for_turn` to return `False`, routing around the exact path F1 concerns |
| No test for the global spend kill-switch on the image-gen path | `grep -rn "global_spend" apps/api/app/tests/services/test_image_generation.py apps/api/app/tests/test_routers_images.py apps/api/app/tests/services/test_image_gen_adapter.py` → no matches; F2 |
| No test for concurrent same-user requests racing the daily cap | `_reserve_daily_slot`'s atomicity is unit-tested generically for other daily caps but there is no image-gen-specific concurrent-request test (defense-in-depth gap only, since the primitive itself is shared and tested elsewhere) |
| No test for the tool-loop adapter double-firing after the pre-stream intercept already handled the same message | Both paths call the same `extract_image_gen_prompt`, and the intercept `return`s before the tool loop is reached (verified by reading, see B) — but no regression test pins this invariant, so a future refactor could silently reorder them |

---

## E. Weak / unwanted / missing inventory

| Item | Status | Evidence | Recommend |
|---|---|---|---|
| Daily image-gen quota reservation granularity | Solid — per request, atomic, pre-provider-call | `quota.py:124-148,409-410`; `image_generation.py:153-155` | Keep as-is |
| Refund on synchronous failures (oversized/invalid/persist/link) | Solid — tested with exact `incrby` assertions | `image_generation.py:290-302`; `test_routers_images.py:44-106,248-305` | Keep as-is |
| Refund/rollback on `asyncio.CancelledError` (WS Stop / SSE disconnect mid-generation) | **Weak — dead on cancellation** | `image_generation.py:290,297` catch `Exception`, not `BaseException`; reachable via `stream_entry.py:199`, `image_gen_adapter.py:102`, `ws.py:204/217`, `chat_stream.py:127` | Fix (F1) |
| Global per-day spend kill-switch coverage | **Missing — image-gen not wired** | `record_global_spend`/`global_spend_exceeded` callers are all text-chat | Fix (F2) |
| Free-tier / non-Pro server-side gate | Solid — 3 independent layers | `image_generation.py:134-135`, `stream_entry.py:50-51`, `image_gen_adapter.py:90-94`, `tool_loop.py:283-288` | Keep as-is |
| No double-generation within one turn (intercept vs. tool loop) | Solid — intercept short-circuits first | `stream_entry.py:199-210` returns before `prepare_chat_turn`/tool loop | Keep as-is; add regression test (D) |
| Reference-image ownership + size/type validation | Solid | `image_generation.py:307-334`; `test_image_generation.py:108-120` | Keep as-is |
| Provider-returned URL fetch (SSRF) | Solid | `image_gateway.py`; `test_image_generation.py:123-165,283-306` | Keep as-is |
| Per-user total storage cap / expiry for generated images | **Missing — only a daily count cap exists** | no `SUM(size_bytes)` / storage-quota check anywhere; orphan reaper only covers unconfirmed uploads | Add (F3), product decision on the number |
| Rate limit on `/images/generate` (vs. daily cap alone) | Weak — no burst smoothing, unlike speech endpoints | `speech.py`/`speech_realtime.py` have both; `images.py` has neither | Add (F4), low urgency |
| TS/Python intent-detection parity | Weak — hand-duplicated, no cross-check test | `image_gen_intent.py:1` docstring; no shared fixture | Add parity test (F5), low urgency |
| Mobile composer-only send path (bypasses WS/SSE for the primary flow) | Solid — server-authoritative, doesn't trust client Pro check | `useChatSend.ts:298-327`; `useImageGeneration.ts:229-232` | Keep as-is |
| Last-line-of-defense size re-check on generated bytes | Solid — deliberate defense-in-depth, not dead code | `image_generation.py:180-189` | Keep as-is |

---

## F. Explicit non-goals of this review

Considered and intentionally not pursued further here:

- **Music generation (🔜 in FEATURES.md).** Not shipped; explicitly deferred
  in the product doc until image-gen's storage/cap path is confirmed as the
  template (`FEATURES.md:185-190`) — this review's F1/F3 findings are
  exactly the kind of thing that template should fix first.
- **Provider selection / model-catalog correctness for `image-gen-model`.**
  Out of scope; the alias→slug mapping (`model_catalog.py`) is shared
  infrastructure reviewed elsewhere, not image-gen-specific.
- **The mobile UI's optimistic-bubble/retry state machine
  (`useImageGeneration.ts`'s pending/failed/canceled rendering).** Read for
  context (confirmed it doesn't bypass server-side gating) but not reviewed
  for UX correctness — out of the stated cost-control/security scope.
- **Attachment RAG, Library/gallery browsing, or general attachment upload
  quota (`daily_image_limit` for *uploads*).** Distinct from generation;
  only touched insofar as `MAX_ATTACHMENT_SIZE` and the orphan reaper are
  shared with generated images.
- **Actual R2 production cost measurement.** FEATURES.md already discloses
  R2 credentials are pending (`FEATURES.md:832-834`); F3 is about the
  *absence of a ceiling* in the code, not a measurement of current spend.
