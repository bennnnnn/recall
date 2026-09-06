# Recall — Background Job / Worker Infrastructure Review (Sep 2026)

Scope: the durable Redis-Stream job queue (`core/jobs.py`), handler registration
(`background/handlers.py`), the periodic scheduler framework (`background/periodic.py`),
every scheduler built on it, and the worker process entrypoint
(`worker_main.py`, `worker_health.py`, `process_bootstrap.py`) — retry, DLQ, dedup,
crash-safety, and whether individual handlers correctly participate in an
at-least-once queue. Individual jobs' own business logic (memory extraction quality,
Gmail sync correctness, etc.) is out of scope; they have their own domain reviews.

Reviewed at `cursor/cross-domain-review-2026-09-05` (working tree matches `main` for
every file in scope — verified via `git log` below). Builds on and verifies two prior
findings: `docs/CODEBASE_REVIEW_2026-08.md` **C2** (inverted `core/jobs.py` imports)
and `docs/PUSH_NOTIFICATIONS_REVIEW_2026-09-05.md` **PN1/PN2** (tests exercise the
wrong push-cycle function).

---

## A. Verdict

**C2 is fully fixed, cleanly, and by the exact mechanism the prior review
recommended.** `core/jobs.py` today has zero `app.background` / `app.services`
imports; the ten `_handle_*` bodies live in `background/handlers.py` next to the
modules they call, `register_all()` is the single explicit entrypoint, and both
`main.py` and `worker_main.py` (via `process_bootstrap`) call it once before the
consumer starts. This landed in commit `2d87f83d` (Aug 13), one editorial pass
before the code in this review, and nothing since has regressed it — `core/jobs.py`
is layer-clean today. This is genuinely closed; stop tracking it as an open finding.

**The PN1 "tests exercise the wrong code path" pattern does not generalize beyond
push.** Of the four periodic schedulers, three (`gmail_periodic_sync.py`,
`email_reminder_scheduler.py`, `attachment_orphan_reaper.py`) either test their exact
production entrypoint directly (`gmail_periodic_sync` — the best example in the
codebase: its tests call `run_gmail_periodic_cycle` itself, through a mocked Redis
lock, exercising the real acquire/refresh path) or delegate to a single-session
service function that *is* the same function under test (`email_reminder_scheduler`,
`attachment_orphan_reaper` — their scheduler wrapper is a one-line pass-through, so
there is no differently-shaped duplicate for a test to accidentally hit). Push remains
the one outlier, and it remains unfixed: `push_scheduler.py`'s two-session
`_push_cycle` still has exactly one test (a lock-TTL constant assertion), and
`services/notifications/push.py`'s `run_push_cycle` is still the same
test-only single-session artifact PN1 described, still never called by
`push_scheduler.py`. PN1/PN2/PN3 are unchanged from the Sep 5 review — verified
against the same commit (`a6d0773e`) the push review cites.

**The queue's headline claim — "at-least-once… a crash mid-processing leaves the
entry in the consumer group's pending list — reclaimed via XAUTOCLAIM"
(`core/jobs.py:1-8`) — is false for any job enqueued with a `dedupe_key`, which is
most of them.** This review reproduced, outside the test suite, a crash sequence
that causes a deduped job to be **silently and permanently dropped** rather than
redelivered: the dedupe claim's "short" TTL (`_JOB_DONE_CLAIM_TTL_SECONDS = 300`
seconds) is actually *five times longer* than the reclaim idle window
(`_CLAIM_IDLE_MS = 60_000` milliseconds = 60 seconds) it was explicitly designed to
expire before (`core/jobs.py:45-49`'s own comment states the opposite of what the
constants do). A worker that claims a deduped job and then dies before finishing it
leaves a stream entry that the *next* reclaim (30–90s later, well inside the 300s
claim) will pick up, see as "already claimed," skip — and then **ack anyway**,
permanently removing it from the pending list with no DLQ entry, no retry, and no
signal beyond an `INFO`-level log line indistinguishable from the benign
duplicate-enqueue case. This is demonstrated in this review (§C, finding **J1**) with
a runnable reproduction against the project's own `fakeredis`-backed test
infrastructure, and it touches nearly every job type in the system — `memory`,
`memory_consolidate`, `todos`, `projects`, `topic`, `compress`, `suggestions`,
`attachment_index`, `message_index`, `transactional_email`, `storage_sweep`, and
`language_path` are all enqueued with a `dedupe_key` (`services/chat/post_turn.py:341-436`,
`core/jobs.py:156-187`, `services/account_lifecycle.py:109`,
`services/learning/path.py:193`). Only jobs enqueued *without* one (e.g. `gmail_sync`)
are immune.

**A second, related bug compounds the first: `_process_one_entry`'s final `xack`
runs unconditionally, even on `asyncio.CancelledError`.** This review reproduced two
concrete, opposite-but-connected failure modes across the project's two real
deployment shapes: in the production two-process Fly split, the standalone
`worker` process's tiny health-check `uvicorn` server installs a process-wide
`SIGTERM` handler for its own lifetime and re-raises the signal with default
disposition once *it* finishes shutting down — which kills the whole process via the
OS **before** `worker_main.py`'s own `finally` block (which calls
`process_bootstrap.shutdown_process` → `jobs.stop_worker()`) ever runs. That
particular accident is *harmless* for the queue (a raw kill leaves entries correctly
pending for reclaim) but means the deliberately-written, unit-tested graceful-shutdown
code is dead in production, and scheduler locks are never explicitly released on
deploy. In the other deployment shape this codebase actually uses —
`PROCESS_ROLE=all` under a real ASGI server, which is `core/config.py`'s **default**
and is exactly what `scripts/dev.sh api` runs locally — `SIGTERM` *does* correctly
reach FastAPI's lifespan shutdown, which *does* call `jobs.stop_worker()`, which
cancels the consumer task mid-job — and `_process_one_entry`'s `finally: xack` fires
on that cancellation regardless of whether the handler finished, **falsely
acknowledging and permanently dropping whatever job was in flight**, again with no
DLQ entry. These two bugs currently offset each other by accident (production's
signal-handling bug means the ack-on-cancel bug is unreachable there) — which means
fixing either one in isolation would make the other's blast radius worse, not
better.

**Everything else in the queue mechanics is genuinely solid**, and the test suite for
it (`test_jobs.py`, 39+ cases) is thorough: retry-then-succeed vs. retry-to-DLQ,
bounded concurrency, DLQ list/replay round-trip (with a real ops script,
`scripts/replay_dlq.py`), Sentry-backed queue-depth alerting, and the Redis lock
(`core/redis_lock.py`) used by every scheduler is a correct token-based
compare-and-delete/compare-and-expire, immune to the classic "TTL expired, second
holder's lock stolen-then-released by the first" race. The bugs found here are
narrow, precisely-located, and specific to the crash/redeploy boundary — not evidence
of a broadly unreliable system.

---

## B. What's working (don't "fix" these)

- **C2 is closed for real.** `core/jobs.py:1-190` (queue mechanics) has zero
  `app.background` / `app.services` imports; `background/handlers.py:1-14`'s own
  docstring states the invariant and `register_all()` (`handlers.py:280-294`) is the
  single, explicit, greppable registration list both `main.py` (lifespan) and
  `worker_main.py` → `process_bootstrap.start_worker_runtime` (`process_bootstrap.py:41-43`)
  call before the consumer starts. Landed in `2d87f83d`, verified unregressed.
- **DLQ is real, inspectable, and replayable — not a graveyard.** `list_dlq` /
  `replay_dlq` (`core/jobs.py:562-616`) back a dev-only admin router
  (`routers/admin.py:59-90`, gated by `dev_auth_enabled` + an explicit
  `ADMIN_USER_IDS` allowlist) *and* a standalone production ops script
  (`scripts/replay_dlq.py`) that does the same thing directly against
  `REDIS_URL` — a real, documented, two-tier recovery path
  (`docs/ROLLBACK.md:63`). Replay correctly carries the original `dedupe_key`
  forward (`core/jobs.py:602-604`), and dedupe is released before a job reaches
  the DLQ (`core/jobs.py:311-312, 326-327`), so a replayed job isn't immediately
  re-skipped as a duplicate.
- **Retry-then-DLQ is correctly bounded and tested.** `_MAX_ATTEMPTS = 3` with
  linear backoff (`core/jobs.py:66-67, 315-322`); `test_process_entries_failed_job_goes_to_dlq`
  and `test_process_entries_retries_then_succeeds_without_dlq`
  (`tests/test_jobs.py:372-410`) both assert the attempt count and the presence/absence
  of a DLQ write precisely.
- **Bounded concurrency is real and race-tested**, not just claimed:
  `_process_entries` (`core/jobs.py:337-363`) uses a semaphore sized from
  `jobs_worker_concurrency`, and `test_process_entries_runs_batch_concurrently` /
  `test_process_entries_parallel_drain_faster_than_serial` (`tests/test_jobs.py:414-463`)
  assert actual overlap and wall-clock speedup, not just that the code path was hit.
- **The Redis lock underlying every scheduler is correct.** `core/redis_lock.py:17-55`
  is SET-NX-EX to acquire, then Lua compare-and-delete/compare-and-expire to
  release/refresh — a slow holder that outlives its TTL cannot have its lock stolen
  by instance B and then deleted out from under B by instance A's late cleanup. Two
  Fly instances racing the same scheduler tick cannot both run it: the loser's
  `acquire_lock` simply returns `None` and that tick no-ops
  (`background/periodic.py:56-77`).
- **`gmail_periodic_sync.py` is the best-tested scheduler in the file, and it is
  testing the real thing.** `tests/background/test_gmail_periodic_sync.py` calls
  `gmail_periodic_sync.run_gmail_periodic_cycle` — the exact function
  `start_gmail_periodic_scheduler` schedules — through a mocked Redis lock, and
  separately asserts per-user failure isolation, concurrency bounding, and that
  disabling the flag skips the DB query entirely. This is the template the other
  three schedulers should be held to, not an exception.
- **Two of three handler examples spot-checked here are naturally idempotent by
  design, not just by dedupe luck.** `compress_chat_history`
  (`services/chat/compaction.py:25-46`) takes its own per-chat Redis lock *and*
  recomputes the compaction split from current DB state every call, so redelivery
  safely no-ops or recomputes correctly. Memory extraction
  (`services/memory/extraction_workflow.py:53-93`) loads `existing_sections` and asks
  the LLM to *revise* them rather than append, so a redelivered extraction merges
  into the same state rather than duplicating facts.
- **Queue-depth observability exists and is tested**, not just aspirational:
  `report_queue_metrics` (`core/jobs.py:527-559`) breadcrumbs every call and fires a
  Sentry warning above `_DLQ_ALERT_THRESHOLD` / `_PENDING_ALERT_THRESHOLD`, covered by
  `tests/test_jobs.py:558-658` for both thresholds and the no-sentry-installed
  fallback.
- **The worker health probe (`worker_health.py`) checks the right two things** —
  `jobs.is_worker_alive()` (task exists, not done, heartbeat fresh within
  `_HEARTBEAT_STALE_THRESHOLD_S`) *and* a live Redis ping — so Fly can tell a stuck
  event loop (blocked handler, deadlocked consumer) from a merely-quiet one, which a
  simple "is the process running" check cannot do.

---

## C. Findings — ranked

### Crash-safety / at-least-once semantics

---

**J1 — Dedupe-claim TTL (300s) is five times *longer* than the reclaim idle window
it's supposed to expire before (60s): a worker that crashes mid-handler on a
deduped job causes that job to be silently and permanently dropped, not retried**
**Severity:** P0 · **Area:** jobs-infra · **Effort:** S

**Evidence:**

- `core/jobs.py:36`: `_CLAIM_IDLE_MS = 60_000` — the `min_idle_time` (milliseconds,
  confirmed against the `redis-py` `xautoclaim` signature) below which an entry is
  *not yet* eligible for reclaim by a peer.
- `core/jobs.py:45-49`, verbatim: *"Short enough that a crashed worker's claim
  expires before the reclaim picks up the entry (reclaim idle is `_CLAIM_IDLE_MS`);
  long enough to cover a normal handler run…"* followed immediately by
  `_JOB_DONE_CLAIM_TTL_SECONDS = 300` — i.e. **300 seconds**, which is *five times
  longer* than the 60-second idle window the comment says it must expire before, not
  shorter. The top-of-file comment (`core/jobs.py:37-42`) independently describes the
  same constant as "a few multiples of the reclaim idle window," which is the
  opposite requirement from "expires before the reclaim picks up the entry" — the two
  comments contradict each other, and the shipped value matches the wrong one.
- `core/jobs.py:379-397`, `_reclaim_pending_jobs`: called on worker startup
  (`core/jobs.py:419`) and every 30 seconds from the live loop
  (`_RECLAIM_INTERVAL_S = 30.0`, `core/jobs.py:428, 435-437`) — so a crashed worker's
  entry becomes visible to `XAUTOCLAIM` at 60s idle and is reclaimed on the very next
  30s tick (60–90s after the crash), 210–240 seconds *before* the 300s dedupe claim
  would naturally expire.
- **Reproduced directly against this repository's own queue code and `fakeredis`
  fixture** (the same one `tests/conftest.py:12-16` provides): a job is delivered,
  its dedupe key is claimed (`_claim_dedupe`, `core/jobs.py:234-255`) exactly as
  `_process_one_entry` would before calling the handler, and the "worker" then
  crashes (no handler call, no `xack`) — precisely modelling a Fly OOM-kill or hard
  redeploy mid-handler. A subsequent `XAUTOCLAIM` (simulating the next reclaim tick)
  correctly transfers the entry, but `_process_entries` on the reclaimed copy calls
  `_claim_dedupe` again, finds the key still set (240s of its 300s TTL remaining),
  returns `False`, logs `"Skipping already-processed job"` (`core/jobs.py:294-298`),
  and the `finally` block **still runs `redis.xack`** (`core/jobs.py:328-334`),
  permanently removing the entry from the pending list. Handler call count after
  reclaim: **0**. The job never ran, and it is now unreachable — not pending, not in
  the DLQ, not retryable.
- **This is not a narrow edge case.** Every per-turn background job is enqueued with
  a `dedupe_key`: `todos` (`services/chat/post_turn.py:349`), `projects` (`:372`),
  `topic` (`:385`), `compress` (`:398`), `suggestions` (`:406`), `attachment_index`
  (`:417`), `message_index` (`:434`), plus `memory` / `memory_consolidate` (lock-retry
  stems, `background/handlers.py:93`), `welcome` / `receipt` emails
  (`core/jobs.py:161, 186`), `storage_sweep` (`services/account_lifecycle.py:109`),
  and `language_path` (`services/learning/path.py:193`). Only jobs enqueued without a
  key (e.g. `gmail_sync`, `services/google_integrations.py:316`) are unaffected.
- **No test exercises this interaction.** `tests/test_jobs.py:757-778`
  (`test_process_entries_claims_with_short_ttl_then_extends_on_success`) only covers
  the *happy* path — claim, dispatch, extend. Nothing asserts what happens when a
  *second* delivery of the same `dedupe_key` arrives while the first claim is still
  alive but the job never actually ran.

**Why it matters:** the module docstring's central promise — *"a crash mid-processing
leaves the entry in the consumer group's pending list — reclaimed via XAUTOCLAIM…
At-least-once"* (`core/jobs.py:1-8`) — is false for the majority of job types in this
system, in exactly the scenario (worker crash mid-handler) the mechanism was written
to survive. Because the loss is silent (an `INFO` log line identical in shape to the
legitimate duplicate-enqueue-skip case, no DLQ entry, no Sentry signal, no metric),
an operator has no way to notice that a user's memory extraction, todo sync, project
sync, chat-history compression, suggestion generation, attachment/message indexing,
welcome email, or GDPR storage sweep silently never ran after a deploy or an
OOM-kill. This is precisely the "worker process already restarts on deploys and can
be OOM-killed" scenario `worker_health.py`'s own docstring says is a first-class
concern — the crash-safety design exists, it just has the two governing timers
backwards.

**Recommended fix (smallest correct change):** two independent, complementary fixes,
either alone closes the data-loss path:

1. Fix the constant relationship so the short claim genuinely expires *before* the
   next reclaim can see it: either lower `_JOB_DONE_CLAIM_TTL_SECONDS` below
   `_CLAIM_IDLE_MS` (e.g. 45s, leaving margin under the 60s idle threshold — but note
   this then risks the *other* stated constraint, "long enough to cover a normal
   handler run," for slow LLM/Gmail-batch handlers that can legitimately exceed 45s),
   or raise `_CLAIM_IDLE_MS` well above any realistic handler runtime and only then
   pick a claim TTL comfortably below *that*. Given LLM-backed handlers
   (`memory`, `topic`, `todos`, `projects`, `gmail_sync`) can legitimately run well
   past 60s, raising `_CLAIM_IDLE_MS` (e.g. to 180–240s) and setting
   `_JOB_DONE_CLAIM_TTL_SECONDS` a safe margin below it is the more robust half.
2. **More surgical and independent of the TTL tuning above:** stop acking on the
   "already claimed, skip" branch (`core/jobs.py:293-299`) the same way an
   exhausted-retry DLQ write does. An entry skipped because its dedupe key is *still
   claimed but not yet extended to the full TTL* is exactly the ambiguous state where
   you cannot tell "still legitimately running elsewhere" from "crashed, orphaned
   claim" — leaving it **unacked** costs nothing (it will simply be re-offered by the
   next reclaim once idle again) and guarantees the short TTL eventually gets a real
   chance to expire and trigger a genuine retry, rather than the entry being deleted
   from the pending list the first time anyone checks. Only ack when the claim was
   released (permanent failure, `core/jobs.py:326-327`) or successfully extended to
   the full TTL (`core/jobs.py:307`).
3. Add a regression test that models exactly this review's reproduction: claim,
   simulate a crash (no dispatch, no ack), reclaim via `XAUTOCLAIM` with
   `min_idle_time=0`, and assert the job either reruns or stays pending — never both
   skipped *and* acked.

**Do not:** remove the dedupe-claim mechanism to "solve" this by making everything
retry freely — legitimate duplicate-enqueue suppression (the `welcome:{user_id}` /
`todosync:{chat_id}:{turn_key}` cases) is real and correctly designed; the bug is in
the *timing relationship* between two constants and the *unconditional ack* on the
skip branch, not in the existence of dedupe.

---

**J2 — The standalone worker process's `SIGTERM` is consumed by its own health-check
`uvicorn` subserver and re-raised with default disposition, killing the process
*before* the deliberately-written graceful shutdown code ever runs**
**Severity:** P1 · **Area:** worker-lifecycle · **Effort:** S–M

**Evidence:**

- `fly.toml:22-24`: production runs the worker as
  `sh -c 'PROCESS_ROLE=worker exec /opt/venv/bin/python -m app.worker_main'`, with an
  explicit comment that `exec` is used "so uvicorn/worker is PID 1 and receives
  SIGTERM cleanly" (`fly.toml:22`) — stating the intent this finding disproves.
  `worker_health_port` defaults to `8001` (`core/config.py:168`), i.e. the health
  server is on by default in this exact deployment.
- `worker_main.py:18-51`: `_run_worker` starts the health check `uvicorn.Server` as a
  background task (`asyncio.create_task(health_server.serve())`, `:33`) while the
  *outer* coroutine blocks forever on `await asyncio.Event().wait()` (`:37`) — an
  `Event` that nothing in this file or `process_bootstrap.py` ever calls `.set()` on.
  The graceful-shutdown code (health server stop, `process_bootstrap.shutdown_process`
  → `stop_worker_runtime` → `jobs.stop_worker()`, scheduler stops, `engine.dispose()`,
  `redis.aclose()`) lives entirely in the `finally` block after that `wait()`
  (`:38-51`).
- `uvicorn.Server.serve()` wraps its whole run in `capture_signals()`
  (confirmed by reading the installed `uvicorn` package in this environment), which
  installs a process-wide `signal.signal(SIGTERM, self.handle_exit)` for the duration
  of `serve()` — i.e., for the lifetime of the *health-check* server, which is the
  lifetime of the whole worker process. On receiving `SIGTERM`, `handle_exit` sets
  `self.should_exit = True` on the health server; once that server's own `_serve()`
  loop notices and finishes shutting down (closing its tiny HTTP listener),
  `capture_signals()`'s `finally` **restores the original signal handler and then
  calls `signal.raise_signal(SIGTERM)`** — re-delivering the signal with default
  disposition now active, which terminates the whole OS process immediately.
- **Reproduced directly**: a minimal script matching `_run_worker`'s exact shape
  (health-check `uvicorn.Server` as a background task, outer coroutine blocked on
  `asyncio.Event().wait()` forever) was sent `SIGTERM` after startup. Across 5
  repeated runs, the process exited with code `-15` (killed by `SIGTERM`) **every
  time**, and the `finally` block's own print statements — modelling
  `process_bootstrap.shutdown_process` — **never executed**. A bare `uvicorn` app (no
  wrapping outer coroutine) shows the expected "Shutting down / Application shutdown
  complete / Finished server process" sequence before the same re-raise-and-exit,
  confirming the health server's *own* shutdown genuinely runs — it is specifically
  the *outer* worker coroutine's cleanup that never gets scheduled before the process
  dies.
- No test in the suite exercises real OS-signal-based shutdown of `worker_main.py`;
  `tests/test_process_bootstrap.py` calls `process_bootstrap.start_worker_runtime` /
  `shutdown_process` directly as plain async functions (fully mocked collaborators),
  which is correct for unit-testing that module in isolation but gives no signal
  about whether the *entrypoint* (`worker_main.py`) ever actually invokes them on a
  real deploy.

**Why it matters:** the intent stated in `fly.toml`'s own comment — worker receives
`SIGTERM` cleanly — is false for the standalone worker process as currently wired.
Practical consequences: (1) `stop_worker_runtime()`'s explicit lock releases for the
push/gmail/email-reminder/attachment-reaper schedulers (`process_bootstrap.py:50-55`)
never run on an ordinary deploy, so whichever scheduler(s) happen to hold their Redis
lock at kill time leave it to expire naturally — up to `lock_ttl_hold_across_ticks`
(600s for push/email) or `lock_ttl_yield_next_tick` (up to 870s for the 900s gmail
scan interval) of "reminders/nudges paused" after every worker deploy, not because
anything crashed but because the graceful path that would have released the lock
immediately never runs; (2) `engine.dispose()` / `get_redis_client().aclose()`
(`process_bootstrap.py:68-69`) never execute, leaving connection cleanup entirely to
server-side idle timeouts; (3) the unit-tested graceful-shutdown code path in
`process_bootstrap.py` has, as far as this review can determine, never actually run
against a real Fly deploy of the worker — the tests give real confidence in the
*function*, and false confidence that the *function is reached*.

The accidental silver lining: because the process dies via a raw, uncatchable signal
rather than Python-level task cancellation, in-flight job entries are *not*
falsely acked (no Python code runs at all after the re-raise) — they correctly stay
pending for the next worker's startup reclaim. This is not a case for leaving it
alone, though: see J3, which shows that "fixing" this signal-swallowing bug in
isolation, without also fixing the unconditional-ack-on-cancel bug, would trade a
lock-release delay for silent job loss on every single deploy.

**Recommended fix:** don't run the health-check server's own `uvicorn.Server.serve()`
with its default signal capture inside a process that has its own top-level shutdown
sequence to run. Concretely: construct the health-check `uvicorn.Config` /
`Server` and call `server.serve()` with signal handling disabled for that server
(uvicorn does not expose this as a config flag directly, so the practical fix is to
install this project's *own* `signal.signal(SIGTERM, ...)` / `add_signal_handler`
at the top of `worker_main.main()` before creating the health server, and have the
`Event` in `_run_worker` be `.set()` from that handler) — so the outer
`_run_worker`'s `finally` block runs deterministically, once, on `SIGTERM`, before
the health server's own signal machinery (if any is left) gets a chance to act. Add
an integration-style test that actually sends `SIGTERM` to a subprocess running
`worker_main.main()` (mirroring this review's reproduction) and asserts the process
exits after running `shutdown_process`'s side effects (e.g. a marker file or a
mock-recorded call visible from outside the subprocess) — not just that the
*function* behaves correctly when called directly.

**Do not:** attempt to fix this by removing the health-check server or setting
`worker_health_port=0` in production — Fly's worker liveness check
(`fly.toml:79-87`) depends on it, and a stuck-but-not-crashed worker (blocked event
loop, deadlocked consumer) is a real failure mode `worker_health.py`'s own docstring
calls out; the fix is in signal ownership, not in removing observability.

---

**J3 — `_process_one_entry`'s final `xack` is unconditional, including on
`asyncio.CancelledError`: wherever `jobs.stop_worker()` genuinely cancels the
consumer mid-job, the in-flight job is falsely acked and permanently dropped**
**Severity:** P1 · **Area:** jobs-infra · **Effort:** S

**Evidence:**

- `core/jobs.py:277-334`, `_process_one_entry`: the dedupe-claim, dispatch, and retry
  logic is wrapped in one `try`, with a single `finally: await redis.xack(...)`
  (`:328-334`) that runs **regardless of how the `try` block exited** — success,
  `JobDiscardError`, exhausted retries, *or* the task being cancelled out from under
  it.
- `core/jobs.py:492-502`, `stop_worker`: cancels `_worker_task`
  (`_worker_task.cancel()`, `:496`) and awaits it — this is the exact mechanism
  `process_bootstrap.stop_worker_runtime` (`process_bootstrap.py:51`) invokes on every
  graceful shutdown, and `main.py`'s FastAPI `lifespan` calls
  `process_bootstrap.shutdown_process(stop_worker=role in ("all", "worker"))`
  (`main.py:47`) on every ASGI shutdown when `PROCESS_ROLE` is `all` or `worker`.
  `process_role` **defaults to `"all"`** (`core/config.py:161`), and this is exactly
  what `scripts/dev.sh api` runs (`uv run uvicorn app.main:app --reload …`, no
  `PROCESS_ROLE` override) — i.e. this is the codebase's own local-dev and
  single-process deployment shape, not a hypothetical.
- **Reproduced directly**: a minimal FastAPI app with a `lifespan` that starts a
  background task (mirroring the jobs worker) and, on shutdown, cancels and awaits
  it exactly as `jobs.stop_worker()` does, was run under real `uvicorn` and sent
  `SIGTERM`. The background task's `finally` block — modelling `_process_one_entry`'s
  ack — ran and "acked" **despite the simulated handler never completing**
  (`await asyncio.sleep(9999)` interrupted mid-await), confirming that on this
  deployment shape, `SIGTERM` *does* correctly reach the app's graceful shutdown
  (unlike J2's standalone-worker case), and that graceful shutdown *does* trigger the
  false-ack path in `_process_one_entry`.
- No test asserts what happens to an in-flight (not failed, not succeeded, actively
  running) job's ack state when the consumer task is cancelled; `tests/test_jobs.py`'s
  worker-loop test (`test_worker_loop_processes_then_cancels`,
  `:501-520`) cancels the *loop* only after the batch has already fully processed and
  acked — it does not model cancellation arriving *during* a handler.

**Why it matters:** for anyone running `PROCESS_ROLE=all` (the default, and what
local development uses) or any future single-process deployment, every graceful
shutdown — a normal `Ctrl-C`, a `SIGTERM` from a process manager, a rolling restart —
silently drops whatever job happens to be mid-handler at that moment, with the same
"no DLQ entry, no signal beyond an ambiguous log line" invisibility as J1. Combined
with J2: production's worker process currently avoids this bug only because its
`SIGTERM` handling is itself broken in a way that skips this code path entirely. That
is not a stable foundation — it means J2 and J3 must be fixed **together** (see the
sequencing in §E), not independently.

**Recommended fix:** in `_process_one_entry`, don't ack in the `finally` block when
the coroutine is unwinding due to `asyncio.CancelledError` — either catch it
explicitly and re-raise after skipping the `xack` call, or restructure so the `xack`
is only reached from the paths that already decided the entry is resolved (success,
discard-to-DLQ, exhausted-retry-to-DLQ), not from a bare `finally`. A cancelled
in-flight entry left unacked is exactly the safe, correct behavior — the next reclaim
picks it up once idle, same as a hard crash.

**Do not:** try to "drain" in-flight jobs to completion before allowing cancellation
as an alternative fix — that reintroduces the un-bounded-shutdown-time problem this
architecture elsewhere avoids (`drain_background_tasks(timeout_seconds=10.0)`,
`process_bootstrap.py:65`, is *already* a bounded-wait pattern for a different
category of tasks; don't special-case the jobs consumer to wait unboundedly instead).

---

### Idempotency / dedupe correctness

---

**J4 — In-process retry (`_MAX_ATTEMPTS=3`) re-invokes the handler without
re-checking work-already-done; handlers with no DB-level idempotency of their own
(e.g. transactional email) can double-send on an ambiguous provider error**
**Severity:** P2 · **Area:** jobs-infra / handlers · **Effort:** S

**Evidence:**

- `core/jobs.py:293-322`: `_claim_dedupe` is called **once** per delivery, before the
  `for attempt in range(1, _MAX_ATTEMPTS + 1)` loop. A transient failure inside that
  loop re-invokes `_dispatch` → the handler up to two more times, with no re-claim and
  no handler-level "did this already happen" check in between.
- `background/handlers.py:225-250`, `_handle_transactional_email`: calls
  `transactional_email_service.send_welcome` / `send_purchase_receipt`
  (`services/notifications/transactional_email.py:562-587`) — both are pure
  build-and-send functions with **no persisted "already sent" state**; they rely
  entirely on the job queue's dedupe key (`welcome:{user_id}`,
  `receipt:{uid}:{event_type}:{product_id}`) to prevent a duplicate *enqueue* from
  sending twice. That protection does not cover a **retry within the same delivery**:
  if `email_gateway.send_email` times out reading the provider's response after the
  email was actually accepted for delivery (a standard ambiguous-outcome failure mode
  for any HTTP-based send), `_process_one_entry`'s retry loop will call
  `send_welcome`/`send_purchase_receipt` again 2 and 4 seconds later
  (`_RETRY_BACKOFF_S * attempt`, `core/jobs.py:67, 322`), sending a second welcome or
  receipt email to the user.
- Contrast with `_handle_compress` (`services/chat/compaction.py:25-46`), which is
  naturally idempotent under retry because it recomputes from current DB state and
  holds its own lock, and `_handle_memory` (`services/memory/extraction_workflow.py:53-93`),
  which merges into existing sections rather than appending — neither of these would
  double-apply on an in-process retry the way `transactional_email` can.

**Why it matters:** this is a narrower, lower-probability version of the general
"at-least-once needs idempotent handlers" rule this review was asked to check, and
it's real: the queue's own retry mechanism, not just cross-delivery redelivery, is
enough to trigger a duplicate side effect for the one handler in this codebase that
sends user-facing, unrepeatable content (an email) with no idempotency of its own.

**Recommended fix:** give `send_welcome` / `send_purchase_receipt` (or their gateway)
a lightweight "already sent" check independent of the job queue — e.g. a
short-TTL Redis SETNX keyed identically to the job's own `dedupe_key`, claimed
*inside* the handler immediately before the actual send call, not just at the queue
layer. This makes the handler safe under retry *and* under redelivery, rather than
depending on the queue's dedupe semantics (which J1 shows can fail) to be the only
line of defense against a duplicate email.

**Do not:** add idempotency keys to every handler uniformly — `compress` and
`memory` are already safe by construction (see "What's working"), and `todos` /
`projects` sync's own idempotency is business logic out of this review's scope
(their LLM-driven action model is a separate, deeper question than infra
correctness).

---

**J5 — A temporary global-spend-cap skip permanently marks the job "done" via the
same dedupe key used for genuine duplicate suppression**
**Severity:** P2 (conditional — requires `daily_global_spend_usd` configured) ·
**Area:** jobs-infra · **Effort:** S

**Evidence:**

- `background/handlers.py:97-111`, `_spend_capped`: returns `True` (skip) when
  `settings.daily_global_spend_usd > 0` (opt-in; defaults to `0.0`,
  `core/config.py:220`) and the global daily spend cap is currently exceeded
  (`quota_service.global_spend_exceeded`). Explicitly documented as fail-closed and
  *temporary* — "background LLM jobs… intentionally bypass per-user token quota…
  The global $ cap is the guardrail" (`:98-104`).
- Seven handlers gate on this and simply `return` when capped, with **no exception
  raised**: `_handle_memory` (`:115-116`), `_handle_memory_consolidate` (`:145-146`),
  `_handle_todos` (`:167-168`), `_handle_projects` (`:178-179`), `_handle_compress`
  (`:200-201`), `_handle_suggestions` (`:208-209`), `_handle_attachment_index`
  (`:254-255`), `_handle_message_index` (`:260-261`).
- `core/jobs.py:300-308`: `_process_one_entry` treats any handler return with no
  exception as success — `await _dispatch(...)` completing normally is immediately
  followed by `await _extend_dedupe(redis, dedupe_key)`, extending the claim to the
  full `_JOB_DONE_TTL_SECONDS = 86_400` (24 hours), then `break`s to the `finally`
  block's `xack`. There is no branch that distinguishes "the handler did real work"
  from "the handler no-opped because of a transient global condition."
- These same seven job types are the ones enqueued with per-turn/per-chat/per-user
  `dedupe_key`s in `services/chat/post_turn.py` (see J1's evidence list) — one-shot
  keys with no independent retry path once marked done.

**Why it matters:** the spend cap is designed as a *temporary* circuit breaker for a
traffic/cost spike, but its interaction with the dedupe mechanism makes its effect
*permanent* for every turn processed during the trip window: once the cap clears,
none of the memory extraction, todo sync, project sync, history compression,
suggestion generation, or attachment/message indexing jobs that were silently
no-opped during the spike will ever run for those specific turns, because their
dedupe keys are now marked "done" for 24 hours. A cost-spike event — precisely the
moment many jobs are in flight simultaneously — is the worst time for this to
happen, and it is currently untested (`grep` finds no test asserting dedupe-key state
after a `_spend_capped` skip).

**Recommended fix:** when a handler no-ops due to `_spend_capped`, don't extend the
dedupe claim to the full 24h TTL — either raise a distinguishable
"retry-later" signal that `_process_one_entry` release the claim (or leaves the
short claim to expire naturally, same mechanism as J1's fix) so a later redelivery
or explicit re-enqueue can still do the real work, or (simpler, no queue-layer
change) have `_spend_capped`'s callers explicitly re-enqueue themselves with a
fresh short delay before returning, mirroring the existing
`_reenqueue_after_memory_lock` pattern (`background/handlers.py:68-94`) already used
for the analogous "temporarily can't run yet" case (memory write-lock contention).

**Do not:** remove the spend cap's fail-closed default or make it retry
indefinitely against an exceeded cap — the intent (never let background jobs bypass
the safety valve) is correct; only the "temporary skip masquerading as permanent
success" side effect needs fixing.

---

### Test coverage

---

**J6 — Confirms PN1: push is still the only scheduler with this gap. No other
scheduler has silently regressed to it.**
**Severity:** P2 (tracking / no new code risk) · **Area:** tests · **Effort:** —
(already tracked as PN1/PN2 in the push review; recorded here as a cross-scheduler
verification, not a new finding)

**Evidence — production entrypoint vs. what tests call, for all four schedulers:**

| Scheduler | Worker calls | Test calls | Same code path? |
|---|---|---|---|
| `push_scheduler.py` | `start_push_scheduler` → `run_push_cycle` → `run_locked_cycle` → **`_push_cycle`** (two-session collect/dispatch/finalize, `push_scheduler.py:27-56`) | `tests/test_push_scheduler.py` asserts `LOCK_TTL_SECONDS > INTERVAL_SECONDS` only (7 lines); the ~13 `run_push_cycle`-named tests in `tests/services/test_push_notifications.py` all call `push_notifications.run_push_cycle` — a different, single-session, test-only function (`services/notifications/push.py:638-653`) that `push_scheduler.py` never imports or calls | **No — PN1 confirmed still open, unchanged since Sep 5** |
| `gmail_periodic_sync.py` | `start_gmail_periodic_scheduler` → **`run_gmail_periodic_cycle`** → `run_locked_cycle` → `_gmail_cycle` | `tests/background/test_gmail_periodic_sync.py` calls `gmail_periodic_sync.run_gmail_periodic_cycle` directly, through a mocked Redis lock, 4 scenarios (concurrency, staleness skip, per-user failure isolation, disabled-flag skip) | **Yes — exact production entrypoint** |
| `email_reminder_scheduler.py` | `start_email_reminder_scheduler` → `run_email_reminder_cycle` → `run_locked_cycle` → `_email_cycle` → **`reminder_emails.run_email_reminder_cycle(session, redis, settings)`** (single session; the scheduler wrapper is a 4-line pass-through, `email_reminder_scheduler.py:31-36`) | `tests/services/test_reminder_emails.py` and `test_reminder_email_management.py` call `reminder_emails.run_email_reminder_cycle` directly — the *same* function the scheduler wrapper calls, not a differently-shaped duplicate | **Yes — same underlying function; only the trivial lock-acquisition wrapper itself is untested (low risk, see inventory)** |
| `attachment_orphan_reaper.py` | `start_orphan_reaper` → `run_orphan_reaper_cycle` → `run_locked_cycle` → `_reaper_cycle` → **`attachment_lifecycle.reap_orphan_attachments(settings)`** (owns its own session; wrapper is a 1-line pass-through, `attachment_orphan_reaper.py:19-20`) | `tests/services/test_attachment_lifecycle.py` — 8 tests calling `reap_orphan_attachments` directly, the same function the scheduler wrapper calls | **Yes — same underlying function; same trivial-wrapper caveat as above** |

**Why this ranking:** this table is the direct, exhaustive answer to "does the PN1
pattern exist in any other scheduler" — it does not. The other three schedulers are
either exemplary (`gmail_periodic_sync`, which tests the *actual* lock-guarded
entrypoint) or safe-by-construction (`email_reminder_scheduler` and
`attachment_orphan_reaper`, whose scheduler-level wrapper is too thin to have room
for a differently-shaped duplicate to hide behind — there is no second function with
the same name doing something different, which is precisely the shape PN2 flagged as
the root cause of PN1). Push remains the sole, already-tracked exception; no new
finding is warranted, but this review recorded the full comparison so the next
reviewer doesn't have to re-derive it.

**Recommended fix:** none beyond what `docs/PUSH_NOTIFICATIONS_REVIEW_2026-09-05.md`
already recommends (PN1: add direct `_push_cycle` tests; PN2: rename the test-only
`run_push_cycle`). Optionally, close the smaller residual gap noted in the table —
add one test per scheduler that calls the *module-level* `run_X_cycle` (not just the
inner service function) through a mocked Redis lock, matching `gmail_periodic_sync`'s
pattern, so lock-acquisition/skip-when-disabled behavior is verified at that level
too for email reminders and the orphan reaper.

**Do not:** treat this as urgent — the underlying business logic for these three
schedulers *is* under direct test; only the thin lock-wrapper glue is unverified,
and `periodic.py`'s `run_locked_cycle` itself is generic, shared, and implicitly
covered by `gmail_periodic_sync`'s tests exercising it end-to-end.

---

## D. Weak / unwanted / missing inventory

| Item | Status | Evidence | Recommend |
|---|---|---|---|
| C2 (`core/jobs.py` inverted imports) | **Fixed** | `2d87f83d`; `core/jobs.py` has zero `app.background`/`app.services` imports today | Keep as-is — closed, stop tracking |
| Dedupe-claim TTL vs. reclaim idle window | **Broken** (crash → silent permanent job loss) | `core/jobs.py:36,45-49`; reproduced in this review | Fix urgently (J1) |
| Worker process `SIGTERM` handling | **Broken** (graceful shutdown code is dead in production) | `worker_main.py:18-51`; `fly.toml:22`; reproduced in this review | Fix (J2), together with J3 |
| `_process_one_entry` ack-on-cancel | **Broken** (false-acks in-flight jobs on graceful shutdown in `process_role=all`) | `core/jobs.py:328-334`; reproduced in this review | Fix (J3), together with J2 |
| Transactional email idempotency | **Weak** (no handler-level guard; queue dedupe is the only defense, and only across deliveries, not within a retry) | `services/notifications/transactional_email.py:562-587`; `core/jobs.py:293-322` | Add handler-level guard (J4) |
| Spend-cap skip vs. dedupe TTL | **Weak** (temporary condition marked permanently done) | `background/handlers.py:97-111`, seven call sites | Don't extend dedupe on a capped no-op (J5) |
| Push scheduler test coverage | **Weak, already tracked** (PN1/PN2, unchanged) | `tests/test_push_scheduler.py` (7 lines); `push_scheduler.py:27-56` | See push review; no new action here |
| Gmail/email/reaper scheduler test coverage | **Solid** | see J6 table | Keep as-is; optional thin-wrapper test (low priority) |
| DLQ inspect/replay | **Solid** | `core/jobs.py:562-616`; `routers/admin.py`; `scripts/replay_dlq.py`; `docs/ROLLBACK.md:63` | Keep as-is |
| Retry-then-DLQ bounding | **Solid, tested** | `core/jobs.py:66-67,300-327`; `tests/test_jobs.py:372-410` | Keep as-is |
| Bounded worker concurrency | **Solid, tested** | `core/jobs.py:337-363`; `tests/test_jobs.py:414-463` | Keep as-is |
| Scheduler Redis lock (`redis_lock.py`) | **Solid** | token-based compare-and-delete/expire; PN review already verified for push, re-confirmed here for all schedulers via shared `periodic.py` | Keep as-is |
| Handler registration (`register_all`) | **Solid** | `background/handlers.py:280-294`; called once by both `main.py` and `worker_main.py` via `process_bootstrap` | Keep as-is |
| Queue-depth Sentry alerting | **Solid, tested** | `core/jobs.py:527-559`; `tests/test_jobs.py:558-658` | Keep as-is |
| `compress` / `memory` handler idempotency | **Solid by design** | `services/chat/compaction.py:25-46`; `services/memory/extraction_workflow.py:53-93` | Keep as-is |
| `core/jobs.py` module docstring | **Now inaccurate** | claims unconditional "At-least-once" (`:1-8`); J1/J3 show exceptions | Caveat or fix alongside J1/J3 |
| Worker health probe | **Solid** | `worker_health.py:1-43`; checks task-alive heartbeat + Redis ping, not just process-up | Keep as-is |
| `core/deps.py` → `app.services` import | **Weak, deliberately deferred** (same inversion class as C2, different concern) | noted explicitly in `2d87f83d`'s commit message as out of scope | Separate PR if ever prioritized; not this review's scope |

---

## E. Sequenced fix plan

One concern per PR, matching this codebase's own execution discipline.

1. **`fix(api): don't ack a job whose dedupe claim is still short-lived and unresolved`**
   — J1 (surgical half: unconditional-ack removal on the "already claimed" skip
   branch). Smallest, safest first step: it stops the silent permanent loss even
   before the TTL constants are retuned, because a mis-timed skip now just leaves the
   entry pending instead of destroying it.
2. **`fix(api): stop acking on asyncio.CancelledError in _process_one_entry`** — J3.
   Do this *with* or immediately after step 1 and *before* J2 — fixing J2 alone
   first would newly expose every graceful worker deploy to J3's false-ack, which is
   strictly worse than today's (accidental) safety.
3. **`fix(api): retune _CLAIM_IDLE_MS / _JOB_DONE_CLAIM_TTL_SECONDS so the short
   claim actually expires before the next reclaim`** — J1 (constant-tuning half).
   Land after 1–2 so there's a real regression test (from step 1) proving the
   crash-loss scenario is closed independent of the exact constants chosen.
4. **`fix(api): own SIGTERM in worker_main.py instead of letting the health-check
   server's signal capture swallow it`** — J2. Now safe to land, because steps 1–2
   mean the graceful shutdown path this restores will correctly leave in-flight jobs
   pending rather than falsely acking them.
5. **`fix(api): give transactional email its own send-idempotency guard`** — J4.
   Independent of 1–4; small, isolated.
6. **`fix(api): release (not extend) the dedupe claim on a spend-cap skip`** — J5.
   Independent; small.
7. **`test(api): add module-level lock-wrapper tests for email reminders and the
   attachment orphan reaper`** — J6's optional follow-up. Lowest priority; the
   underlying logic is already covered.

**Unchanged from the push review, still queued there, not duplicated here:** PN1
(direct `_push_cycle` tests), PN2 (rename the test-only `run_push_cycle`), PN3
(claim calendar/learning dedupe after a confirmed send, not before).

---

## F. Explicit non-goals

Considered and deliberately not raised as findings:

- **Re-litigating C2.** Fully fixed, verified against the actual commit
  (`2d87f83d`) and the current tree; this review only needed to confirm it, not
  redesign it further.
- **Re-litigating PN1/PN2/PN3.** Already fully specified in
  `docs/PUSH_NOTIFICATIONS_REVIEW_2026-09-05.md` with a sequencing plan; this review
  only needed to confirm the pattern doesn't recur elsewhere (J6) and did not find a
  reason to add to or change that plan.
- **Auditing `todos`/`projects` sync's own LLM-driven idempotency.** Whether
  re-running the same transcript through the todo/project extraction LLM prompt
  would create duplicate rows is business logic, not infra — explicitly out of this
  review's scope, and it already has the queue-level dedupe key protection that
  works correctly outside the J1 crash window.
- **`core/deps.py`'s `app.services` import inversion.** Same class of issue as C2,
  explicitly called out as deliberately deferred in the C2 fix commit's own message;
  a separate, smaller concern than the job queue and not part of this review's
  named scope.
- **Rewriting the dedupe/reclaim design from scratch** (e.g. moving to Redis
  Streams' built-in consumer-group semantics exclusively, dropping the separate
  dedupe-key layer entirely). The dedupe-key layer solves a real problem
  (`XAUTOCLAIM` alone doesn't prevent double-enqueue from a caller, only
  double-*delivery* of the same stream entry) — J1's fix is a timing/ack correction
  within the existing design, not a case for redesigning it.
- **Gmail/email/reaper scheduler wrapper tests.** Flagged as a minor, optional
  follow-up in J6, not a finding of its own — the actual business logic for all
  three is directly tested; only a thin, generic pass-through wrapper (already
  implicitly exercised via `gmail_periodic_sync`'s tests of the shared
  `run_locked_cycle`) lacks a scheduler-specific test.
