# Recall — Cancellation-Safety Sweep (Sep 2026)

Scope: **only** the specific bug class already found twice in this audit series —
a quota/rate-limit/Redis reservation made, then slow I/O awaited, with
cleanup/refund/rollback gated by `except Exception` (or narrower) instead of
`except BaseException`, on a code path that is *actually* reachable from
`asyncio.CancelledError`. Not a general chat-loop or cost-control review;
those exist already (`docs/STT_LIVE_TALK_REVIEW_2026-09-05.md`,
`docs/IMAGE_GENERATION_REVIEW_2026-09-06.md`). Reviewed read-only at
the current `apps/api` tree.

---

## Verdict

**One genuine new instance**, beyond the two already known (Live Talk's C1,
image-generation's F1): `apps/api/app/services/chat/post_turn.py`'s
`finalize_stream_turn_db` refunds the reserved text-token quota only from an
`except Exception:` block, and that function runs as a **detached background
task** that is demonstrably cancellable — not by WS "Stop" or SSE disconnect
(both are correctly shielded away from it, see evidence below), but by the
app's own shutdown path, `drain_background_tasks` (`apps/api/app/core/background_tasks.py:34`),
which calls `task.cancel()` on any such task still running 10 seconds into a
graceful shutdown. This is real, wired production code (`apps/api/app/main.py:47`
→ every Fly deploy), not a hypothetical.

Everything else that fits the surface pattern — a reservation followed by
slow I/O guarded by a narrow `except` — turned out, on tracing the actual
call chain, to be either (a) already `BaseException`-safe, (b) protected by an
exception-type-agnostic `try/finally`, (c) not a metered/refundable resource
at all (a one-shot claim-then-consume token, by design), or (d) not reachable
from any cancellation source that exists in this codebase's current
Starlette/uvicorn stack. Section 3 lists everything checked, including the
negative results, since several of those were the most likely-looking
candidates on first read and are worth recording as "considered, not a
finding" rather than silently omitted.

---

## 1. New finding

---

**S1 — `finalize_stream_turn_db`'s token-quota refund is not `BaseException`-safe against the shutdown-triggered cancellation of its own detached background task**
**Severity:** P2 · **Area:** chat finalize / cost-control · **Effort:** S

**Evidence:**

- The reservation: `stream_entry.py`/`turn_resources.py` reserve
  `ctx.reserved_tokens` for the turn up front. While the turn is *streaming*,
  `turn_resources()`'s own `except BaseException:` (`apps/api/app/services/chat/turn_resources.py:94-96`)
  correctly refunds this reservation on any cancellation of the streaming
  body — this is the already-fixed, correct pattern the other two reports
  point to.
- But once the token stream finishes, `stream_and_finalize`
  (`apps/api/app/services/chat/stream_pipeline.py:388-393`) hands the actual
  DB commit off to a **new, detached** task:
  ```
  finalize_db_task = seams.create_background_task(
      seams.finalize_stream_turn_db(redis, ctx, assistant_text, usage, result),
      name="finalize_stream_turn_db",
  )
  ```
  This call happens *inside* the async generator that `turn_resources()`
  wraps, but the task itself is fire-and-forget (`create_background_task`,
  `apps/api/app/core/background_tasks.py:15-23`) — it is not awaited before
  the generator returns. By the time the WS/SSE caller's
  `async with seams.turn_resources(...)` block exits (the stream is done,
  the client already got `done`), that context manager exits **normally**
  (no exception), so its `except BaseException` never runs for anything that
  happens to `finalize_db_task` afterward. The two lifecycles are already
  decoupled at this point — confirmed by tracing, not assumed.
- `finalize_stream_turn_db` (`apps/api/app/services/chat/post_turn.py:86-264`)
  does its DB writes (message insert, usage row, commit) inside a `try:`
  (lines 147-253) whose only handler is `except Exception:` (line 254), which
  refunds via `quota_service.refund_usage(redis, str(ctx.user_id), ctx.reserved_tokens)`
  (line 257) before re-raising. `asyncio.CancelledError` is a `BaseException`,
  not an `Exception` — it skips this handler entirely. The function's
  `finally:` (lines 261-264) still runs and clears the pending-finalize
  marker, but it does **not** refund; the refund call only lives inside the
  `except Exception` block.
- This is genuinely reachable, and by a mechanism this review verified
  directly rather than assumed: `drain_background_tasks`
  (`apps/api/app/core/background_tasks.py:26-37`) is called from
  `process_bootstrap.shutdown_process` (`apps/api/app/process_bootstrap.py:65`,
  `timeout_seconds=10.0`), which is wired into the real FastAPI lifespan
  shutdown handler (`apps/api/app/main.py:39-47`, `await process_bootstrap.shutdown_process(...)`
  after `yield`) — i.e. it runs on every graceful shutdown (Fly deploy/restart),
  not just in tests. `drain_background_tasks` awaits all in-flight background
  tasks for up to 10s, then explicitly does `task.cancel()` on any that are
  still running (line 34) — a test pins this exact behavior:
  `test_drain_background_tasks_cancels_on_timeout`
  (`apps/api/app/tests/core/test_background_tasks.py:28-37`).
  `asyncio.Task.cancel()` delivers `CancelledError` into whatever
  `finalize_stream_turn_db` is currently awaiting — most plausibly
  `await session.commit()` (`post_turn.py:213`) or one of the writes just
  before it, under DB contention or connection-pool pressure at exactly the
  moment a deploy lands.
- I specifically checked whether the two other cancellation sources in this
  codebase (WS `producer.cancel()`, SSE disconnect-cancel) can reach this
  same task and confirmed they cannot: `wait_for_pending_finalize`
  (`apps/api/app/services/chat/finalize_registry.py:103-124`), the only other
  code that touches this task, waits on it via
  `_await_bounded`/`asyncio.wait_for(asyncio.shield(task), ...)`
  (`finalize_registry.py:56-58`) — `asyncio.shield` deliberately means a
  *waiter's* own cancellation cannot propagate into the shielded
  `finalize_db_task`. So the only demonstrated cancellation source for this
  specific task is the shutdown drain, not ordinary user action.

**Why it matters:** if the cancellation lands before `await session.commit()`
completes (lines 147-213), the DB transaction correctly rolls back (no
half-written message/usage row — `async with SessionLocal()`'s own
`__aexit__` handles that regardless of exception type), but the Redis-side
token reservation taken at the start of the turn is never given back. The
user already saw the full reply stream to their screen (WS/SSE already sent
`done` before this background task even started), so from their perspective
nothing looks wrong, but their daily quota counter is short by
`ctx.reserved_tokens` for a turn whose actual usage was never reconciled via
`adjust_usage` either. This is bounded and self-healing — it is a single
user's single turn, on a Redis key with a UTC-midnight TTL — but it is a
real instance of exactly the pattern C1/F1 describe, on the one code path in
`post_turn.py` that was not audited by either of those two reports (both
were feature-specific; neither one looked at what happens to the *shared*
finalize task's own cancellation safety).

**Recommended fix (smallest seam):** change `finalize_stream_turn_db`'s
outer handler from `except Exception:` to `except BaseException:`, mirroring
`turn_resources.py:94-96` exactly — the refund and `raise` already do the
right thing; only the exception type needs widening. No behavior change is
needed for the two nested `except Exception:` blocks around `adjust_usage`
(lines 239-248) and `record_global_spend` (lines 250-253): those already run
strictly *after* `committed = True`, so a cancellation there should not
refund (the reply is already persisted) — that half of the function is
correctly scoped as-is. Add one test parametrized the same way as
`test_stream_chat_response_refunds_on_cancelled_error`
(`apps/api/app/tests/services/test_stream_quota.py:100-150`), but patching
something inside the pre-commit block (e.g. `usage_repo.add_tokens` or
`session.commit`) to raise `asyncio.CancelledError`, asserting
`quota_service.refund_usage` is awaited with `ctx.reserved_tokens`.

**Do not:** widen the two *inner* `except Exception:` blocks (adjust_usage
retry loop, record_global_spend) to `BaseException` — those intentionally
swallow-and-log because the reply is already committed at that point;
turning them into hard failures would raise into `run_jobs_after_db`'s own
`except Exception` (`stream_pipeline.py:403`) for no benefit and would not
change what needs refunding.

---

## 2. Related but distinct — not instances of this bug class

Two adjacent patterns matched the surface shape (reserve → slow I/O → narrow
`except`) closely enough to warrant tracing all the way through, and both
turned out to have a **different root cause** than an exception-type
mismatch — recorded here rather than silently dropped, per the brief.

- **Tavily search budget has no refund path at all, by design — not a
  mismatch, an absence.** `_search_with_cache`
  (`apps/api/app/services/web_search/search_cache.py:162-247`) reserves the
  turn's one Tavily slot at line 224 (`budget.skip_tavily(cache_redis)`),
  immediately before the network call at line 226
  (`web_search_gateway.search_web`). Its `finally:` (line 242) only releases
  the *cache* lock, not the Tavily reservation. `quota.py` has no
  `refund_tavily_search` function at all (`grep -n "tavily" apps/api/app/services/quota.py`
  → `tavily_search_limit_for_user` and `reserve_tavily_search` only, no
  refund). This means a Tavily slot is spent even on a **synchronous**
  provider error, not just on cancellation — the bug class in scope is
  specifically about the *gap between* a working refund-on-Exception and a
  missing refund-on-Cancel; this code has no refund-on-anything, which is a
  deliberate "use it or lose it" cost-control choice already implicit in the
  daily-cap sizing, not a latent bug to fix under this sweep. `_TurnTavilyBudget.skip_tavily`
  (`search_cache.py:51-90`) does explicitly re-raise `asyncio.CancelledError`
  (line 80-81) rather than swallowing it, so it is not making the situation
  worse either.
- **Calendar event confirmation deliberately burns the proposal on any
  failure, including cancellation — an intentional duplicate-prevention
  trade-off, not a metered resource leak.** `confirm_create_event`
  (`apps/api/app/services/calendar.py:436-499`) does
  `claimed = await redis.getdel(_proposal_key(...))` (line 463) — an atomic
  claim-and-delete — *before* `google_calendar_gateway.create_event` (line
  472), with an explicit comment explaining why: a retry after a failed
  cleanup must not find the proposal again and create a duplicate event. If
  `create_event` is cancelled, the proposal is gone and cannot be reused,
  but a calendar proposal is a one-time UX affordance, not a billed/limited
  quota unit — there is nothing to "refund" in the sense C1/F1 mean. Also,
  tracing the call graph confirms this endpoint is only reachable from
  `apps/api/app/routers/integrations.py`, a plain HTTP endpoint outside the
  WS/SSE cancellable task tree entirely (see §3's last item for why that
  matters) — so even setting the design question aside, cancellation cannot
  reach this code today.

---

## 3. Swept and clean

Everything below was traced from a real cancellation source down to the
relevant `except`/cleanup code, not just pattern-matched.

**Already fixed correctly (cited by the two prior reports, re-verified here, not re-detailed):**

- `apps/api/app/services/chat/turn_resources.py:94-96` — `except BaseException:` → `resources.refund()` for the turn's text-token reservation, on the streaming body's cancellation. Re-verified as still exactly this shape.
- `apps/api/app/services/sympy_executor.py:155` — `except BaseException:` → kills the subprocess pool before re-raising. Re-verified as still exactly this shape.
- `apps/api/app/services/attachment_reuse.py:56-67` — **verified complete, not partial**: `ensure_unlinked_copies` wraps the whole copy-bytes + insert-clone + commit sequence in `except BaseException:`, which rolls back the session and deletes every storage key written so far (`created_keys`) before re-raising. Confirmed this is called from `apps/api/app/services/chat/turn_prep/attachments.py:139-141`, inside the same cancellable turn-prep path — so the fix is not just present, it is on the path that needed it.

**Newly checked in this sweep and confirmed safe:**

- `apps/api/app/routers/speech.py:346-349` — `synthesize_speech`'s `/speech/tts` handler explicitly catches `asyncio.CancelledError` (separately from `except HTTPException` and `except Exception`) and refunds `speech_tts` quota before re-raising. Correct.
- `apps/api/app/routers/speech.py:369-394` — `stream_speech`'s `/speech/tts/stream` generator (`body_iter`) uses `try/finally` (line 382), which is exception-type-agnostic by construction — it refunds whenever no audio chunk was ever produced, regardless of whether the abort surfaces as `CancelledError`, `GeneratorExit` (StreamingResponse abandoning the iterator), or anything else. This is the pattern the `lessons.mdc` entry "Live talk abort skipped refund... Settle in finally" documents; correctly generalized here.
- `apps/api/app/services/chat/finalize_registry.py:56-58` — `_await_bounded` wraps every wait in `asyncio.shield`, so a *waiter's* cancellation (e.g. a second request racing the same chat) cannot propagate into the task being waited on. This is precisely the guard that rules out WS/SSE cancellation as a source for finding S1 above — checked, not assumed.
- `apps/api/app/services/memory/` locking (referenced in the prior conversation's notes) — write locks are released in `try/finally` with a bounded TTL as a second line of defense; re-confirmed this session by reading the acquire/release pairing.
- `apps/api/app/services/calendar.py:436-499` (`confirm_create_event`'s lock release, line 491-499) and `apps/api/app/services/calendar.py:502-527` (`materialize_calendar_proposals`) — the former's *lock* (not the proposal claim, see §2) is released in `finally`; the latter only writes new proposals to Redis and never claims/consumes anything before a slow call, so there is nothing to leak.
- `apps/api/app/services/mcp/calendar_adapter.py` (`CalendarAdapter.invoke`, lines 135-159) — read-only Google Calendar conflict check; no reservation of any kind.
- `apps/api/app/services/chat/turn_prep/integrations.py:150-219` — calendar/Gmail prompt-context loads are read-only fetches gathered with `asyncio.gather` (line 204); none of the gathered coroutines claims a resource that a sibling's failure could strand.
- `apps/api/app/services/attachment_rag.py` and `apps/api/app/services/attachment_content.py` — chunking/embedding calls (`_embed_pieces`, `attachment_rag.py:73-84`) have no metered reservation to leak; a cancelled embed call just means fewer chunks got embedded, retried by the background indexing job's own retry count (`AttachmentIndexError`, `attachment_rag.py:87-93`), which is a different, already-understood failure mode, not this bug class.
- `apps/api/app/services/tool_loop.py:373-391` — the tool-loop's own `complete_with_tools` call is guarded by `except ModelUnavailableError` / `except Exception`, which do *not* catch `CancelledError` — but this loop does not hold any reservation of its own at this point (the only in-loop reservation is image generation, already F1, and the Tavily budget, already §2); a bare `CancelledError` here is expected and correctly meant to propagate uncaught, up to `turn_resources`'s outer `except BaseException`.
- **Verified, not assumed: plain (non-WS/SSE) HTTP endpoints that reserve-then-`except Exception` are not currently reachable from `asyncio.CancelledError` in this codebase's stack, so their narrow `except` is not (yet) a live instance of this bug class.** This was the single largest source of false-positive-looking candidates in this sweep and deserves the same rigor as a real finding:
  - `apps/api/app/routers/speech.py:397-475` (`transcribe_speech`, `/speech/transcribe`)
  - `apps/api/app/routers/speech_realtime.py:137-172` (`create_realtime_session`, `/speech/live/session`) and its gateway call `apps/api/app/gateways/openai_speech_gateway.py:95-144` (`except Exception:` at line 142)
  - `apps/api/app/services/attachment_upload.py:45-101` (`create_presigned_upload`)
  - `apps/api/app/routers/images.py:12-35` (`generate_image`'s direct, non-chat-turn call to `generate_for_chat` — the image-generation review's own F1 text already notes this specific entry point "bypasses WS/SSE entirely, so this specific class of cancellation cannot happen there")

  All four reserve a quota slot, then await slow I/O (a provider call or a
  DB/storage write), guarded only by `except Exception`/`except HTTPException`
  — matching the surface pattern exactly. The reason none of them is a
  finding here: I verified, by reading the installed Starlette
  (`starlette==1.3.1`) `BaseHTTPMiddleware` implementation
  (`.venv/lib/python3.13/site-packages/starlette/middleware/base.py`) and
  uvicorn's HTTP protocol (`.venv/.../uvicorn/protocols/http/h11_impl.py`),
  that this stack does **not** auto-cancel a plain request handler's task on
  client disconnect. `connection_lost` only sets a `disconnected` flag
  (`h11_impl.py`, `self.cycle.disconnected = True`); `BaseHTTPMiddleware`'s
  `receive_or_disconnect` races `wrapped_receive` against
  `response_sent.wait()` inside its own *nested* task group, and cancelling
  that inner race does not touch the outer task running `self.app(...)` —
  it only resolves a value the app would see if it explicitly called
  `receive()`, which none of these four handlers do. None of them streams a
  response either (all return a single JSON body), so there is no
  `StreamingResponse` body-iterator abandonment path (the mechanism that
  *does* legitimately protect `stream_speech`, above, via `finally`). A
  client that closes the connection mid-request to any of these four
  endpoints today gets silently ignored server-side until the handler
  finishes on its own — there is no live cancellation-injection mechanism
  for them at all, so the `except Exception` gap, while real, does not
  currently qualify under this sweep's criterion (d). This is worth
  revisiting only if one of these is ever wrapped in an explicit
  disconnect-watch task (the way `ws.py`/`chat_stream.py` are) or a
  `asyncio.wait_for`/`asyncio.timeout` is added around the slow call —
  neither exists today.

---

## 4. Consolidated recommendation

**Fix S1 with the same site-local `except BaseException:` pattern used at
`turn_resources.py:94`, `sympy_executor.py:155`, and `attachment_reuse.py:56`
— do not build a shared abstraction yet.** Three data points now exist of
this exact shape being fixed correctly with a one-line change
(`except Exception:` → `except BaseException:` plus, where needed,
narrowing what's re-raised), and this sweep found exactly one more genuine
instance, in a codebase of ~44k backend lines with dozens of reservation
sites. A `@refund_on_cancel` decorator or context-manager helper would need
to know, per call site, *what* to refund and *what condition* exempts a
refund (e.g. `turn_resources`'s "only refund if not already refunded and
`reserved_tokens > 0`", image-gen's "don't refund on a 403/429 that already
means no charge happened," S1's "only refund pre-commit, not post-commit")
— that's meaningfully different shaped cleanup at each site, not a
parameterizable single operation. Building the abstraction now would mean
guessing its shape from four samples, and the two the sample most resembles
(`turn_resources.py`, `attachment_reuse.py`) are already written, tested,
and shipped in the site-local style — retrofitting them into a new helper
purely for symmetry is churn with no bug-fixing value. Revisit a shared
helper if a *fifth* instance turns up with the same call-site shape as an
existing one (not just the same category of bug); until then, the fix is:
find the reservation, find its cleanup, widen that one `except` clause,
add a `CancelledError` test modeled on `test_stream_chat_response_refunds_on_cancelled_error`
or `test_drain_background_tasks_cancels_on_timeout`, ship it in its own
commit per `execution.mdc`.
