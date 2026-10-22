# Scaling the API

What it takes to run more than one `app` machine and more than one `worker` on Fly
(`fly.toml`), what already works across machines, what is per machine on purpose, and
the changes to make, in order, when traffic needs them. Load limits and their defaults
are in [PRODUCTION.md](./PRODUCTION.md#load-and-abuse-limits); where code lives is
[ARCHITECTURE.md](./ARCHITECTURE.md).

Today: one `app` machine (shared CPU, 1 GB, one uvicorn process, one event loop) and one
`worker` (512 MB). Both talk to the same Neon Postgres (through its `-pooler` host),
Upstash Redis and R2. Scale out by adding machines (`fly scale count app=N worker=M`),
not uvicorn `--workers`: every per-process item below would multiply inside one machine
(three more SymPy processes per uvicorn worker, a socket cap per process, one more
signal hook) and the 1 GB budget is sized for one.

## Already safe on N app machines and M workers

Everything a turn or a request must agree on across machines lives in Redis or Postgres.

| What | Where it lives | Notes |
|---|---|---|
| Sign-in and every request's token check | JWT + Redis (`revoked:jti:`, `revoked:sid:`, `revoked_since:`, read with the user's `usergen:` in one MGET) | `core/access_tokens.py`; account delete revokes every session first, so a cached user row elsewhere is never served to a deleted account |
| Rate limits: REST, sign-in, chat messages (30/min across WS and SSE), WS connect and handshake, voice, scan reads, link previews | Redis counters (`core/rate_limit.py`, `core/rest_rate_limit.py`, `core/chat_rate_limit.py`) | Fail closed when Redis is down. Per-IP limits need `TRUST_X_FORWARDED_FOR=true` behind Fly |
| Daily tokens, image, voice, search and live-talk allowances, Tavily budget | Redis (`services/quota/`) | One budget per user whichever machine serves the turn |
| Global daily spend cap | Redis `spend_musd:<date>` (`core/spend_counter.py`) | Every machine adds to and reads the same counter |
| One turn per chat at a time | Redis lock `chatprep:{chat}` (TTL 30 s, refreshed every 10 s) | A second send on another machine gets `busy` |
| "Wait for the last reply to be saved" | Redis marker `chatfinal:{chat}` (`modules/chat/finalize_registry.py`) | Same machine awaits the task; another machine polls the marker (50 ms, up to 10 s) |
| Memory, home, link-preview, web-search, query-embedding and follow-up caches; model health | Redis, keyed by user or query, with TTLs | Where a write must invalidate one, it bumps a Redis generation key (`core/cache_generation.py`), so every machine sees it |
| Memory writes | Redis lock per user (`modules/memory/locks.py`) plus Postgres row locks (user row first) | A busy lock re-enqueues the job with a backoff |
| Background jobs | One Redis Stream `recall:jobs`, consumer group `workers` (`core/jobs/`) | Each worker has its own consumer name; entries are leased and reclaimed after 60 s idle; `jobdone:<key>` dedupe keeps a job from running twice; poison entries and timeouts go to the DLQ; the stream is bounded (`JOBS_STREAM_MAX_LEN`) |
| Periodic schedulers (push, reminder email, orphan reaper, billing reconcile) | Every worker runs every loop; a Redis lock per cycle lets one run it (`background/periodic.py`) | Adding workers adds lock attempts, not duplicate sends |
| Files | R2 presigned URLs | Production refuses local storage (`validate_production_settings`) |
| Deploys | Blue-green, then SIGINT: in-flight turns stop and save, locks release | Two workers overlap for a moment; leases, dedupe and scheduler locks cover it |

## Per machine on purpose, and what that means

| State | Where | Effect with N app machines |
|---|---|---|
| Last loaded user row, 5 min, checked against Redis | `core/user_cache.py` | Every committed write to a user row (plan change from the RevenueCat webhook, a settings or memory change, consent) stores a new `usergen:{user}`; every request and chat frame reads it with its token check and loads the row again when its copy is older. A write whose generation Redis refuses answers 503 (it is saved; its retry publishes); a missing key starts a fresh generation, never one an old copy was stored under. A SQL edit to `users` needs `DEL usergen:<id>` (PRODUCTION.md §2); otherwise, and after a machine dies between a commit and its publish, a copy can lag for up to 5 min. Consent is re-read from the row before a turn is refused. |
| A chat created here, 120 s | `repositories/chats.py` (`_chat_cache`) | The send right after "new chat" skips a query. If the chat is deleted through another machine, this machine still starts a turn for it for up to 120 s, which then fails when it saves. |
| Open chat sockets per user (5) | `modules/chat/ws_limits.py` | A user can hold 5 per machine, N×5 in all. The frame budget and idle timeout are per socket, so they are exact. |
| SymPy process pool (3 workers, 2 s slot wait) | `core/sympy_executor.py` | Capacity grows with machines (3 per machine); a maths turn that waits more than 2 s for a slot on its machine is answered unverified. |
| In-flight turns, their Stop, the finalize task that saves the reply, the post-turn enqueue, follow-up questions | `modules/chat/` background tasks (`core/background_tasks.py`) | A machine that dies without the stop signal (OOM, host loss) loses the replies it had not saved yet; its `chatprep` lock and `chatfinal` marker expire within 30 s. |
| Spend record and invalid-output counter after each model call | `gateways/llm_spend.py`, `gateways/structured_completion.py` | Written on a background task; lost only if the machine dies in that instant. |
| Outbound HTTP pools, Google request session, Apple signing keys (1 h), storage client | `gateways/` | Each machine warms its own; no shared state. |
| Pure-function LRU caches (maths and physics readers, routing) | `modules/*` | Inputs only; any machine computes the same answer. |
| Jobs a worker runs at once (`JOBS_WORKER_CONCURRENCY` 8) and per-type caps (`memory_history_scan` 3) | `core/jobs/worker.py`, `background/handlers.py` | Caps are per worker: M workers run 8×M jobs and 3×M history scans at once. |

## Resource budgets per process

- **Postgres connections.** Every process has one SQLAlchemy pool of `DB_POOL_SIZE` 20 +
  `DB_MAX_OVERFLOW` 10 = up to 30 (`core/db.py`), the worker included, which needs far
  fewer (8 jobs plus four schedulers). (N + M) × 30 client connections must fit Neon's
  pooler; the real limit is the compute's server pool (about 0.9 × its `max_connections`),
  which queues transactions beyond it. Set a smaller `DB_POOL_SIZE` on the worker (inline in
  its `fly.toml` process command, as `PROCESS_ROLE` is) before adding many.
- **Redis connections.** Two clients per process (`core/redis.py`: request path, and the
  jobs consumer with a longer socket timeout), each with redis-py's default unbounded
  pool: a burst opens a connection per concurrent command. Upstash limits concurrent
  connections per plan and bills per command.
- **Redis commands per request.** An authenticated REST request costs the rate-limit
  pipeline (INCR + EXPIRE) and one MGET for the token check. A finished chat turn
  enqueues up to seven jobs, each an XADD plus the soft trim (XPENDING, XTRIM).
- **CPU.** One event loop per machine on a shared CPU. SymPy runs in its own processes and
  document parsing on threads, but prompt building, the maths/physics/chemistry readers
  and the finalize passes run on the loop. Measure before moving any of it.
- **Memory.** About 270–400 MB for the API plus 90–150 MB per SymPy worker
  (PRODUCTION.md); hence 1 GB per `app` machine.

## Changes for scaling out, most useful first

Each is a change of behavior or of resource use, so none is made yet. The seam is where it
plugs in.

1. **Decide how Fly counts WebSockets** (owner, PRODUCTION.md §4): with
   `[http_service.concurrency] type = "requests"`, 200 open chat sockets may fill a machine.
   Seam: `fly.toml`. Do this first; it decides when a second `app` machine is needed.
2. **Bound and trim Redis use.** Give both clients a `max_connections` (a blocking pool) sized
   to Upstash's limit ÷ machines; trim the jobs stream from the worker on a timer instead of
   on every enqueue (`core/jobs/queue.enqueue`). Seams: `core/redis.py`,
   `core/jobs/queue.py`.
3. **Size the Postgres pool per role** (smaller on workers) and per Neon compute, so
   (N + M) × pool stays under the server pool. Seam: `DB_POOL_SIZE` / `DB_MAX_OVERFLOW`
   (`core/settings/infrastructure.py`), set per process group.
4. **Invalidate the per-machine chat cache** once a chat deleted through another machine
   must stop at once: check a Redis generation per chat on read, as `core/user_cache.py`
   does for user rows (the `core/cache_generation.py` pattern). Seam:
   `repositories/chats.py` (`peek_recent_chat` / `forget_chat`).
5. **Count chat sockets per user in Redis** if N×5 is too many: an expiring counter or set
   per user, refreshed while the socket lives. Seam: `modules/chat/ws_limits.py`
   (`user_socket_slot`).
6. **Make the account-delete sweep independent of total size.** `purge_user_redis_keys`
   SCANs the whole keyspace and `purge_user_jobs` walks both job streams on every delete.
   Keep a per-user index of keys (or put the user id in a fixed prefix) and let the stream
   bound age job payloads out. Seams: `modules/account/lifecycle.py`,
   `core/jobs/admin.py`.
7. **Shard the billing reconcile.** It checks every paid user one by one (a RevenueCat call
   plus a 0.2 s gap: at most 18,000 users an hour, about half that with the call's own
   latency), so past that it no longer finishes within its hour. Split by user-id range
   across workers, or check only users without a recent webhook. Seam: `background/billing_reconcile_scheduler.py`.
8. **Separate job classes if one starves another.** All job types share one stream and
   worker slots; `max_running` limits a slow type per worker. A second stream (or a second
   consumer group) for slow jobs would keep titles and memory quick under a burst. Seams:
   `core/jobs/queue.py` (`JOBS_STREAM`, `register`), `core/jobs/worker.py`.
9. **Move CPU off the event loop when measurements say so**: the readers and finalize
   passes are text processing over the reply, so a process pool like SymPy's could take them. Seams:
   `core/sympy_executor.py` (the bounded, injectable pool), `modules/chat/finalize_passes.py`.
   A remote SymPy service would implement `BoundedSympyExecutor` and plug in through
   `set_sympy_executor`.
10. **Save replies durably** if losing an unsaved reply on a machine crash matters: hand the
    finalize to a job instead of an in-process task. Seams: `modules/chat/stream_pipeline.py`,
    `core/jobs/`.
11. **Raise the orphan reaper batch** if uploads outpace it: it removes up to
    `ATTACHMENT_ORPHAN_REAP_LIMIT` (100) rows an hour. Seam:
    `core/settings/attachments.py`.

Provider limits (OpenRouter, Tavily, Expo, Resend, RevenueCat) are per API key and do not
grow with machines; raise them with the provider.
