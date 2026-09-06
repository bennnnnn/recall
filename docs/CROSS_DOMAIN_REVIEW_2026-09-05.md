# Recall — Cross-Domain Review: STT/Live Talk, Schedule, Push, Memory, Output Format, Billing, Image Gen, Tool Loop, Cancellation Safety, Background Jobs, Model Routing/Quota, Mobile Offline Resilience, Account Lifecycle/Email (Sep 2026)

Staff-level review across thirteen product-critical subsystems, run as thirteen independent,
read-only deep-dives (one subagent per domain, across four rounds) and consolidated here. Each
domain has its own full report with file:line evidence:

**Round 1 (2026-09-05):**

| Domain | Full report | Top severity found |
|---|---|---|
| STT + Live Talk | [`STT_LIVE_TALK_REVIEW_2026-09-05.md`](./STT_LIVE_TALK_REVIEW_2026-09-05.md) | P0 ×2 |
| Schedule / Calendar / Gmail | [`SCHEDULE_CALENDAR_REVIEW_2026-09-05.md`](./SCHEDULE_CALENDAR_REVIEW_2026-09-05.md) | P1 ×2 |
| Push notifications | [`PUSH_NOTIFICATIONS_REVIEW_2026-09-05.md`](./PUSH_NOTIFICATIONS_REVIEW_2026-09-05.md) | P1 ×2 |
| Memory | [`MEMORY_ARCHITECTURE_REVIEW_2026-09-05.md`](./MEMORY_ARCHITECTURE_REVIEW_2026-09-05.md) | P1 ×1 |
| Output format / rich rendering | [`OUTPUT_FORMAT_REVIEW_2026-09-05.md`](./OUTPUT_FORMAT_REVIEW_2026-09-05.md) | P1 ×2 |

**Round 2 (2026-09-06)** — picked based on round 1's finding that cost-control/security gaps
cluster at newer, higher-surface-area subsystems; targeted the highest-risk areas with zero prior
review (money and security):

| Domain | Full report | Top severity found |
|---|---|---|
| Billing / RevenueCat | [`BILLING_REVENUECAT_REVIEW_2026-09-06.md`](./BILLING_REVENUECAT_REVIEW_2026-09-06.md) | P0 ×1 |
| Image generation (Pro) | [`IMAGE_GENERATION_REVIEW_2026-09-06.md`](./IMAGE_GENERATION_REVIEW_2026-09-06.md) | P1 ×2 |
| MCP tool loop + web search | [`MCP_TOOL_LOOP_SECURITY_REVIEW_2026-09-06.md`](./MCP_TOOL_LOOP_SECURITY_REVIEW_2026-09-06.md) | High ×1 |

**Round 3 (2026-09-06)** — round 2 surfaced a cancellation-safety bug class independently in two
different domains (Live Talk, image gen); round 3 both closes that pattern out with a dedicated
sweep and covers the two remaining structural subsystems (job/worker infra, model routing + core
quota) that every other domain sits on top of:

| Domain | Full report | Top severity found |
|---|---|---|
| Cross-cutting cancellation-safety sweep | [`CANCELLATION_SAFETY_SWEEP_2026-09-06.md`](./CANCELLATION_SAFETY_SWEEP_2026-09-06.md) | P2 ×1 (new) |
| Background jobs / worker infra | [`BACKGROUND_JOBS_INFRA_REVIEW_2026-09-06.md`](./BACKGROUND_JOBS_INFRA_REVIEW_2026-09-06.md) | P0 ×1 |
| Model routing + core quota | [`MODEL_ROUTING_QUOTA_REVIEW_2026-09-06.md`](./MODEL_ROUTING_QUOTA_REVIEW_2026-09-06.md) | P1 ×2 |

**Round 4 (2026-09-06)** — mobile-only (no web client exists yet, per explicit product scoping);
targeted the two largest remaining unreviewed surfaces: client-side network/state resilience, and
the account-deletion/GDPR/email lifecycle that sits underneath every other feature:

| Domain | Full report | Top severity found |
|---|---|---|
| Mobile network/offline resilience + drafts | [`MOBILE_OFFLINE_RESILIENCE_REVIEW_2026-09-06.md`](./MOBILE_OFFLINE_RESILIENCE_REVIEW_2026-09-06.md) | P0 ×1 |
| Account lifecycle + transactional email | [`ACCOUNT_LIFECYCLE_EMAIL_REVIEW_2026-09-06.md`](./ACCOUNT_LIFECYCLE_EMAIL_REVIEW_2026-09-06.md) | P1 ×3 |

Each report also independently re-verified prior review docs (`docs/CODEBASE_REVIEW_2026-08.md`,
`docs/*_RELIABILITY_REVIEW_2026-09-04.md`, and each other's companion reports) against current
code rather than assuming they still hold — all their headline fixes (C3/C4 memory split, C5/C7
fence registry, Schedule pagination and conditional writes, C1 turn-quota lifecycle, C2 inverted
`core/jobs.py` imports, the server-side hard-disconnect finalize path) were confirmed genuinely
landed and correct. Findings below are net-new.

## Overall verdict

The core, oldest subsystems (chat loop, memory persistence, Schedule CRUD/delivery, fence
dispatch, RevenueCat's plan-sync core, the sympy execution sandbox, the tool loop's one-round
cap, the turn-quota reserve/refund lifecycle, the Redis-Stream job queue's retry/DLQ/concurrency
mechanics, and the model catalog/routing/plan-gating layer) are **correct by construction** —
conditional writes, optimistic concurrency, lock ordering, registry-driven dispatch, atomic
`INCRBY`-based reservation, and hard architectural caps replaced hand-vigilance in exactly the
places the Aug 2026 review flagged as weak, and the fixes hold up under a fresh, skeptical pass
across all eleven domains now reviewed. The newer or higher-surface-area subsystems (Live Talk's
WebRTC session lifecycle, the production push scheduler's two-session cycle, Gmail-sourced
content crossing the prompt-injection trust boundary, model-authored `places`/`vocab_quiz`
fences, the RevenueCat webhook's own success status code, `except Exception` vs `BaseException`
cancellation handling, calendar-tool untrusted-content wrapping, the job queue's crash-safety
timing constants, and per-request LLM fallback-retry accounting) have not yet received the same
treatment. **Every P0/P1/High finding below is a variant of one of four patterns:**

1. **A resource reservation/trust decision is made once but the thing it's supposed to bound can
   silently exceed it** — quota granularity (Live Talk sessions, image-gen cancellation),
   dedupe claims (push, and now the job queue's own dedupe-claim-vs-reclaim timing), prompt trust
   (Gmail reminders, calendar tool results), tool-call/search fan-out (MCP tool loop).
2. **The code path that runs in production is not the code path the tests exercise** — the push
   scheduler's two-session cycle, the webhook's `204` vs. RevenueCat's documented `200` contract.
   Round 3 confirmed this pattern does **not** generalize to the other three periodic schedulers
   (gmail/email-reminder/attachment-reaper all test their real entrypoint) — it stays a
   push-specific, already-tracked issue, not a systemic one.
3. **A fix already exists elsewhere in the codebase for this exact bug class but wasn't
   consistently re-applied** — `except BaseException` for cancel-safety exists in
   `turn_resources.py`/`sympy_executor.py`/`attachment_reuse.py` but not `image_generation.py`
   or (round 3's own new finding) the detached `finalize_stream_turn_db` background task;
   `wrap_untrusted` exists for web-search/Gmail/calendar-prompt-injection but not the calendar
   MCP tool; the global spend kill-switch exists for text chat but not voice, image-gen, or the
   tool-loop's own classifier call.
4. **Two independently-correct pieces of shutdown/lifecycle code interact badly, or a documented
   self-heal mechanism was never wired in** — new in round 3: the worker process's health-check
   server accidentally swallows `SIGTERM` before the app's own graceful shutdown runs (harmless
   only by accident), the job consumer's unconditional `xack` would falsely acknowledge in-flight
   work if that shutdown path were "fixed" in isolation, and the quota system's own documented
   Redis/DB drift healer (`heal_usage_drift`, shipped in PR #854 as fix H1) is fully implemented
   but has zero call sites.

## Top 10 findings, ranked across all domains (round 1)

1. **[STT/Live Talk] C1 (P0)** — Live Talk's 30-turns/day Pro cap is reserved once per WebRTC
   *session*, not per turn, and the session has no duration limit — a single session covers
   unbounded audio-minutes of real, billed OpenAI Realtime usage. The one refund path for a
   failed connection has had its mobile caller deleted, so a flaky handshake burns a slot with
   zero audio exchanged. **Direct, uncapped dollar-cost exposure**, not just a fairness bug.
2. **[STT/Live Talk] C2 (P0)** — Switching chats from the drawer while Live Talk is open doesn't
   close the session; the next spoken turn renders into the newly opened chat but persists to the
   chat that was left. A real state-machine bug with no guard and no test.
3. **[Schedule] F1 (P1, security)** — A Gmail-derived reminder loses its untrusted-content framing
   the instant it's confirmed and is re-injected into every future system prompt with a **more**
   trusting preamble than it had pre-confirmation. One phishing email + one user confirm-tap =
   persistent prompt-injection surface until the reminder is deleted.
4. **[Push] PN1 (P1)** — The production two-session push-delivery cycle (`_push_cycle`, the
   worker's sole entry point) has one trivial test; all ~15 "cycle" tests exercise a same-named
   single-session helper production never calls. This is exactly the blind spot behind a
   previously-shipped incident (#1017, duplicate sends).
5. **[Push] PN7 (P1)** — Mobile push registration swallows every failure mode (rejected rebind,
   Expo Go, missing EAS project id, network error); the settings toggle shows "on" regardless.
   Direct path to "I turned reminders on and never got one."
6. **[Memory] M1 (P1, privacy)** — Explicit "forget X" can never fully clear a memory section
   through the automated extraction pipeline: the schema forbids an empty summary, a partial-parse
   fallback silently drops the attempt, and the anti-hallucination guard that correctly protects
   against *accidental* erasure also blocks *deliberate, user-requested* erasure. Silent, on the
   one operation users most expect to work.
7. **[Output format] O1 (P1)** — The `places` fence is model-authored on the normal path (contrary
   to its own registry annotation) and, unlike its sibling `sources` fence, is never
   schema-validated before being shown or persisted — a live gap in golden rule #6.
8. **[Output format] O2 (P1)** — `vocab_quiz`, a fully model-authored JSON fence, is parsed with
   hand-rolled `dict.get()` into a plain dataclass and drives real SM-2 grading DB writes with no
   Pydantic validation anywhere in the path.
9. **[Schedule] F2 (P1)** — Google OAuth refresh failures aren't typed by cause; a permanently
   revoked grant is indistinguishable from a transient blip forever. No auto-disconnect, and
   Settings shows "Connected" based on row presence, not health — background jobs retry a
   dead grant every 60s indefinitely.
10. **[STT/Live Talk] C3 (P1)** — The global per-day spend kill-switch that protects text chat
    from runaway OpenRouter cost was never wired to voice (STT/TTS/Live Talk) spend — the second
    independent backstop that should catch runaway voice cost (after #1's broken cap) doesn't
    cover voice at all.

## Top findings, round 2 (Billing, Image Gen, Tool Loop)

1. **[Billing] F1 (P0)** — The RevenueCat webhook returns `204`; RevenueCat's own docs say only
   exactly `200` counts as success. **Every single successful delivery today is recorded as a
   failure** and retried up to 5 times over 155 minutes — harmless so far only by luck, because
   the plan-sync pipeline happens to be idempotent by design, not because anything notices the
   mismatch. Cheapest fix in either round (one status-code line) with the highest blast-radius
   potential (it affects every purchase/renewal/cancellation event, permanently, until fixed).
2. **[Tool loop] F1 (High)** — The calendar MCP tool returns externally-sourced event titles
   (which can originate from other people via shared calendars/invites) to the model **unwrapped**
   — every sibling untrusted-content path in this codebase (web search, Gmail, the main calendar
   prompt-injection path) calls `wrap_untrusted`; this one adapter skips it. The tool loop's
   hard one-round cap (a genuinely excellent, tested architectural property — see "what's
   working") limits the blast radius to the visible reply text, but that's still exactly the kind
   of injected-instruction surface `wrap_untrusted` exists to neutralize.
3. **[Billing] F2 (P1)** — `CANCELLATION`'s downgrade-timing heuristic checks only
   `expiration_at_ms`, never `cancel_reason` — a store-issued **refund**
   (`cancel_reason=CUSTOMER_SUPPORT`) is indistinguishable from a voluntary auto-renew-off, so a
   refunded user keeps Pro until the (unrelated, still-nominally-active) subscription period
   naturally ends. Real revenue-correctness gap, not defensive theater.
4. **[Image gen] F1 (P1)** — Same cancellation-safety gap found in Live Talk (round 1), confirmed
   independently in a second subsystem: `generate_for_chat` catches `Exception`, not
   `BaseException`, so a WS Stop/SSE disconnect mid-generation skips both the quota refund and
   storage rollback — burning one of only 10 daily Pro image slots for zero output. This is now a
   *pattern*, not an isolated bug — worth a codebase-wide sweep for this exact class (see
   "cross-cutting pattern" below).
5. **[Image gen] F2 / [Billing implicit] — global spend kill-switch gap, third occurrence** —
   image generation is a second feature (after Live Talk in round 1) where
   `record_global_spend`/`global_spend_exceeded` was never wired in. Combined with the tool
   loop's F4 (the web-search classifier call is also uncounted), this kill-switch has now been
   found missing on **four** separate cost paths across two review rounds.
6. **[Tool loop] F3/F4 (Medium)** — the per-turn Tavily budget reservation is 1-per-turn by
   design (correct for the app-controlled search fan-out) but has no cap on how many *real*
   searches a model can trigger via multiple `web_search` tool calls in one round; separately, the
   web-search-need classifier LLM call runs before the spend kill-switch check and is never
   counted in any usage/cost accounting at all.
7. **[Billing] F3 (P2)** — No backend reconciliation/polling job exists to re-verify a Pro user's
   entitlement against RevenueCat's REST API as a backstop — contrary to RevenueCat's own
   recommended architecture — so a lost webhook (compounded by F1's retry-exhaustion risk) has no
   server-side self-healing path if the user never reopens the app.
8. **[Tool loop] F2 (Medium)** — no cap on the number of tool calls processed in a single round,
   nor an aggregate timeout around executing them (each individual tool has its own timeout, but
   the sum is unbounded and calls run sequentially while holding the per-chat prepare lock).

## Top findings, round 3 (Cancellation Sweep, Background Jobs, Model Routing/Quota)

1. **[Background jobs] J1 (P0)** — The job queue's "short" dedupe-claim TTL (300s) is five times
   *longer* than the reclaim idle window (60s) it's documented to expire before — the two
   governing constants are backwards relative to each other. A worker that crashes mid-handler on
   any deduped job (which is nearly every job type: memory, todos, projects, topic, compress,
   suggestions, indexing, transactional email, storage sweep) gets silently and **permanently**
   dropped on the very next reclaim, with no DLQ trace — reproduced directly against the
   project's own `fakeredis` test infra, not inferred. This falsifies the module's own headline
   "at-least-once" claim for the majority of job types in the system.
2. **[Background jobs] J3 (P1)** — `_process_one_entry`'s final `xack` fires unconditionally,
   including on `asyncio.CancelledError` — wherever `jobs.stop_worker()` genuinely cancels the
   consumer mid-job (confirmed to happen in the `PROCESS_ROLE=all` mode this codebase's own local
   dev uses by default), an in-flight job is falsely acked and lost, with the same silent-loss
   signature as J1.
3. **[Background jobs] J2 (P1)** — The standalone worker process's own health-check `uvicorn`
   subserver swallows `SIGTERM` and re-raises it with default disposition, killing the process
   *before* the deliberately-written, unit-tested graceful-shutdown code (`process_bootstrap`)
   ever runs on a real Fly deploy — reproduced directly. Currently harmless for job loss only by
   accident (a raw kill leaves entries safely pending), but it means J2 and J3 must be fixed
   **together**: fixing J2 alone would newly expose every production worker deploy to J3's
   false-ack bug, trading a (harmless) lock-release delay for (real) silent job loss.
4. **[Cancellation sweep] S1 (P2, new)** — A third independent instance of the round-1/round-2
   `except Exception` vs. `BaseException` pattern, found by a dedicated sweep: the detached
   background task that commits a chat turn's DB row and refunds its token-quota reservation
   (`finalize_stream_turn_db`) only refunds from `except Exception:`, and is demonstrably
   cancelled by the app's own graceful-shutdown drain on every deploy — not by ordinary WS/SSE
   cancellation, which this sweep verified is correctly shielded away from it. Same fix shape as
   the three already-shipped instances (widen one `except` clause).
5. **[Model routing/quota] Q1 (P1)** — The LiteLLM gateway's multi-alias fallback retry (used to
   route around a provider returning an empty/whitespace-only reply — the code's own comment
   calls this "a common flaky provider quirk," i.e. not rare) shares one `usage` dict across
   attempts with no reset, so a discarded attempt's provider-reported tokens are never
   un-counted — the user is billed against their daily cap for both the invisible failed attempt
   and the delivered reply, every time the retry fires.
6. **[Model routing/quota] Q2 (P1)** — The exact self-heal for Redis/DB quota drift shipped in
   PR #854 as fix H1 (`heal_usage_drift`) is fully implemented, documented, and referenced by
   name in a log message ("heal_usage_drift on next turn will correct the drift") — but has zero
   call sites anywhere in the app. A Redis blip during post-commit quota reconciliation now
   silently under-counts a user's daily usage for the rest of the UTC day with no recovery path,
   the direct under-charging counterpart to Q1's over-charging.
7. **[Background jobs] J4/J5 (P2)** — Two narrower idempotency gaps in the same subsystem:
   transactional email (welcome/receipt) has no handler-level "already sent" guard, so an
   in-process retry after an ambiguous provider timeout can double-send; and a temporary
   global-spend-cap skip extends the same 24h dedupe claim used for genuine duplicate
   suppression, silently and permanently no-oping seven job types for every turn processed during
   a cost-spike window, even after the cap clears.
8. **[Model routing/quota] Q3 (P2)** — Fallback failure/health-sample attribution always blames
   the original primary model alias, even when a later fallback in the same chain is what
   actually failed — this quietly undermines the model-health-based fallback exclusion (M6 from
   PR #854) by penalizing the innocent primary while a genuinely-unhealthy fallback keeps getting
   selected.

**Confirmed fixed / confirmed not-a-finding in round 3** (recorded because each looked like a
plausible new finding before tracing the full call chain): the Aug 2026 review's **C2** (inverted
`core/jobs.py` layer dependency) is genuinely, cleanly fixed (commit `2d87f83d`) and unregressed;
the push review's **PN1** "tests exercise the wrong code path" pattern was checked against all
three other periodic schedulers and does **not** recur — it remains a push-only, already-tracked
issue; and the Aug 2026 review's **C1** (turn quota/lock lifecycle) is genuinely closed, including
the removal of the third entry point (`stream_edit_response`) that C1 originally flagged, which no
longer exists because message-edit was independently banned as a UX pattern.

## Top findings, round 4 (Mobile Offline Resilience, Account Lifecycle/Email)

1. **[Mobile offline] F1 (P0, privacy)** — Composer draft text is never cleared on sign-out:
   `ComposerDraftProvider` sits above the auth redirect in the component tree, so it's never
   unmounted across a sign-out → sign-in cycle, and the eleven-cache `clearSignedOutAccount` sweep
   never touches it. Because every sign-in lands on the shared "New Chat" draft slot, the next
   account to sign in on the same device inherits whatever unsent text the previous account left
   in the box — **reproduced with a standalone script showing Account B's composer displaying
   Account A's un-sent draft verbatim.** A straightforward, always-reproducible, high-confidence
   privacy bug on the default post-login path, not an edge case.
2. **[Account lifecycle] E3 (P1, billing/product)** — Account deletion never touches the
   RevenueCat subscription: a deleted Pro user's App/Play Store subscription keeps auto-renewing
   and billing them indefinitely, with zero in-app disclosure that "delete account" does not mean
   "stop being charged." Not purely fixable server-side (no third-party backend can cancel an
   active Apple auto-renewable subscription), but the missing disclosure is a same-day copy fix.
3. **[Account lifecycle] E2 (P1, compliance)** — The GDPR data-export feature silently omits five
   user-owned tables, most importantly `suggested_reminders`, which stores **verbatim excerpts of
   the user's own Gmail content** extracted server-side. A user who exports their data after
   connecting Gmail does not receive the Gmail-derived personal data the backend demonstrably
   holds about them.
4. **[Account lifecycle] E1 (P1, jobs/email)** — The job-queue transactional-email handler
   discards the email gateway's success/failure return value entirely, so **any** definite send
   failure (provider outage, bad API key, rate limit) — not just round 3's narrow J4
   ambiguous-timeout double-send case — is recorded as a successful job with zero retry and zero
   DLQ entry. A user who signs up during a provider outage silently never gets a welcome email,
   with no way to detect or recover it after the fact; the codebase already has the correct
   pattern next door (the two periodic-scheduler email types check their send result correctly)
   but it wasn't applied to the job-queue path.
5. **[Mobile offline] F2/F3 (P1)** — Two related mobile-chat-resilience gaps: a message that fails
   to send due to a genuine client-side network failure (not a server rejection) settles into a
   permanent, unmarked, unretryable "sent" bubble with the composer text already gone (F2); and a
   network drop mid-stream while the app stays foregrounded has no automatic recovery, leaving
   Regenerate as the only visible action — which discards a correct, already-persisted answer
   (per round 3's confirmed server-side hard-disconnect finalize fix) and burns a redundant LLM
   call (F3).
6. **[Account lifecycle] E4/E5/E6 (P2/P3)** — No bounce/complaint webhook exists for the email
   provider at all (invisible deliverability risk as volume grows); `delete_account`'s steps
   commit independently rather than atomically (narrow, self-healing crash window); no
   `List-Unsubscribe` header on the two opt-in bulk email types (forward-looking best-practice
   gap, not a current compliance blocker).

**Confirmed fixed / confirmed not-a-finding in round 4** (recorded because each looked like a
plausible new finding before tracing fully): account deletion's Postgres-level cascade coverage
was independently re-verified against actual migration DDL (not just ORM annotations) and is
**complete** — every user-content table is covered; session revocation is real and immediate,
explicitly re-verified on every chargeable WebSocket frame specifically to cut off live sessions
on deletion; re-signup with the same Google/Apple identity or email after deletion is clean
end-to-end with no stale-row collision; no parameter-tampering path exists for delete or export;
and the round-1 Live-Talk-style chat-switch state leak (C2) does **not** recur for same-account
chat-to-chat draft switching — only the cross-*account* case (F1 above) is broken.

### Cross-cutting pattern worth calling out explicitly

**The `except Exception` (not `BaseException`) cancellation-safety gap has now been found in
three separate subsystems by three different subagents** (Live Talk's `/speech/live/session` flow
in round 1, image generation's `generate_for_chat` in round 2, and — via round 3's dedicated
sweep — the detached `finalize_stream_turn_db` background task that commits every chat turn),
against a codebase that has already fixed this exact bug class correctly, three separate times,
elsewhere (`turn_resources.py`, `sympy_executor.py`, `attachment_reuse.py`, with a dedicated
regression test whose docstring states the lesson explicitly: *"Hard cancel (CancelledError) must
refund — except Exception would miss it"*). Round 3's sweep was the fourth, cheap, high-leverage
review this doc's previous revision called for, and it closed the loop: it found exactly one new
genuine instance (not more), confirmed several look-alikes are either already safe or not
currently reachable from any real cancellation source in this codebase's Starlette/uvicorn stack,
and concluded — correctly, based on only four data points with meaningfully different per-site
cleanup logic — that a shared `@refund_on_cancel` abstraction would be premature. **This pattern
should now be treated as closed as a class**, with the understanding that any *future* reservation
site should default to `except BaseException` from the start rather than needing its own
dedicated review to catch the same mistake a fifth time.

**Two more patterns crossed the round-3/round-4 boundary and are now confirmed 3-for-3 across
independent domains, on top of the cancellation-safety pattern above:**

- **"A fix or helper for exactly this problem already exists elsewhere in this file/codebase but
  was never wired in."** Round 3's Q2 (`heal_usage_drift`, fully implemented, zero call sites) now
  has a direct sibling in round 4: `findLastLocalUserMessageId` (mobile offline F2) is a tested
  helper — the exact lookup a send-failure recovery path needs — with zero call sites in
  production code. Both are the same shape: the engineer who'd need to write this code already
  wrote it, scoped correctly, and then the wiring-in step didn't happen. Worth a lightweight
  "grep for unused-but-tested exports" pass as a cheap way to find more of these before they're
  independently rediscovered a third time.
- **"The handler/caller silently treats a definite failure as success because the callee's
  contract is 'never raise.'"** This is the shared root cause of round 4's E1 (transactional email:
  the gateway's correct, intentional "never raise" contract for its *synchronous* caller is reused
  unchanged as a job-queue return value the handler never checks) and is structurally the same
  mistake as the fallback-retry accounting bug in round 3 (Q1: a retry mechanism built for one
  failure mode silently mis-accounts a different one it wasn't checked against). Both are now
  fixed with the same shape of change: make the *caller* that has retry/accounting responsibility
  actually inspect what it's calling, rather than trusting a shared, differently-scoped contract.
- **"Tests exercise a call shape production never uses"** (PN1, background-jobs J6) recurred a
  third time in round 4: 24 of ~26 `sendMessage` calls in `useChat.test.tsx` use an options shape
  production never sends (`skipUserBubble` omitted), so the disconnect/error tests that look like
  they cover "what happens to the user's message on failure" actually exercise a dead branch. This
  review series has now found this exact bug class in four independent subsystems (push, jobs,
  and twice more here) — it may be worth a dedicated, cheap sweep (grep every test file for the
  production call's actual option shape vs. what the test passes) rather than continuing to find
  one instance per domain review.

## Second-tier findings worth scheduling soon (P2, selected)

- **[Push] PN3** — Calendar/learning push dedupe claims their Redis key *before* Expo confirms
  the send; a worker crash in between silently drops the notification (opposite failure mode from
  #4's duplicate-send bug — this one loses, not repeats).
- **[Output format] O3/O4** — A follow-up "output-routing review" reintroduced three new
  hand-written fence-lang lists one layer below the registry the Aug review just fixed, and the
  registry's own recommended round-trip render test was never written — a new fence with no wired
  renderer would pass every existing test today.
- **[Memory] M2** — The non-semantic memory-selection fallback (used on any embedding-provider
  hiccup, not just an outage) silently omits `project`/`fact`/`focus` types from the prompt, logged
  only at debug level.
- **[Schedule] F5** — A dead mobile recurrence module re-implements and re-breaks the exact
  400-iteration catch-up cap bug the backend already fixed — an attractive nuisance waiting to be
  wired back in by a future contributor.
- **[STT/Live Talk] C5** — Live Talk has no `AppState`/backgrounding handling at all — unlike
  every other async feature in the mobile app, it doesn't flush or close on background/interrupt.

## What's already solid across all five domains (do not re-litigate)

- Memory: optimistic-concurrency background writes, self-healing embedding staleness, documented
  off-by-one fix, prompt-injection framing on injected memory, cross-user isolation. The Aug 2026
  C3/C4 findings are both genuinely fixed.
- Output format: the fence registry (`fenceRegistry.ts`) is a real single source of truth now;
  CSP is consistently applied across every WebView path; `sources`/geometry/graph/reminder/
  calendar fences are all correctly Pydantic-gated.
- Schedule: recurrence math, conditional schedule writes, and the `services/todos/` package
  structure are correct by construction, not by vigilance.
- Push: the four-producer → one-funnel send path, Expo batching/chunk isolation,
  `DeviceNotRegistered` vs `InvalidCredentials` handling, and cross-user token rebind hardening
  are all solid and tested.
- STT/Live Talk: no provider API key ever reaches the client; every session/tool key is
  user-scoped; the no-speech gate is real and layered; FEATURES.md's own hedges about Live Talk
  validation gaps are honest, not spin.
- Billing: the RevenueCat plan-sync core is unusually mature — constant-time, fail-closed webhook
  auth; every upgrade path re-verifies entitlement against RevenueCat's REST API rather than
  trusting the payload; three-layer idempotency (Redis claim, Redis done-marker, durable Postgres
  watermark); `BILLING_ISSUE`/`SUBSCRIPTION_PAUSED` correctly no-op; downgrades propagate on the
  very next request with no plan caching.
- Image generation: the daily-cap reservation is atomic and correctly per-request (not
  per-session, unlike Live Talk); refund symmetry on every synchronous failure path is real and
  tested with exact assertions; the Pro gate is enforced server-side at three independent layers;
  provider-returned image URLs are fetched through an SSRF-safe, DNS-pinned helper.
- MCP tool loop: hard-capped to exactly one round of tool execution, verified by reading the code
  (not just the misleading config name) and tested; calendar writes are cleanly separated into a
  human-confirmed, non-tool-loop flow; cross-user authorization holds on every adapter; the
  classic `sympify`/`parse_expr` RCE gadget is closed on both the heuristic and tool-callable
  paths with an explicit allowlist and a parametrized regression test against real exploit
  payloads.
- Background jobs: C2 (inverted `core/jobs.py` imports) is fully and cleanly fixed; DLQ
  inspect/replay is real and has both a dev-gated admin route and a standalone ops script;
  retry-to-DLQ bounding, bounded worker concurrency, the token-based Redis scheduler lock, and
  queue-depth Sentry alerting are all solid and genuinely tested (assertions on actual behavior,
  not just that a code path was hit); three of four periodic schedulers test their real production
  entrypoint directly.
- Model routing/quota: C1 (turn quota/lock lifecycle) is fully closed; the reserve → top-up →
  reconcile-against-provider-usage pipeline is a genuinely good design, not just a claimed one;
  atomic `INCRBY`-based reservation/rollback is race-free and tested; overshoot is capped so one
  turn's real usage can't corrupt the next turn's remaining-quota check; the model catalog is
  current against live OpenRouter listings; per-message model overrides are correctly plan-gated
  end-to-end, and no provider API key or raw provider error ever reaches the client.
- Mobile offline resilience: pre-send offline detection has a correct, non-blocking UI (banner +
  toast + preserved draft); the three-state connectivity probe correctly distinguishes API-down
  from no-internet and has no Neon-cold-start false positive (the API never scales to zero); the
  app-backgrounded-mid-stream recovery mechanism and the explicit server-rejection retry queue are
  both real and tested; same-account chat-switch draft isolation is correct — only the
  cross-*account* case (F1) leaks.
- Account lifecycle: Postgres-level deletion cascade coverage is complete, independently
  re-verified against real migration DDL rather than trusted from ORM annotations; session
  revocation is immediate and explicitly reaches live WebSocket connections, not just new
  requests; Google/Gmail/Calendar OAuth tokens are genuinely revoked at Google on deletion, not
  just deleted locally; object storage has two independent, non-redundant cleanup backstops;
  re-signup after deletion with the same identity is clean end-to-end; HTML-escaping and
  header-injection hardening in email templates is real and tested; no parameter-tampering path
  exists for delete or export.

## Suggested sequencing (cross-domain, highest leverage first)

1. **Fix the RevenueCat webhook status code** (Billing F1) — literally one line, zero behavior
   risk, and it's the single highest blast-radius item across all three rounds (every billing
   event, permanently, until fixed). Ship this first regardless of what else is in flight.
2. **Fix the job queue's crash-safety bugs together, in the order round 3 specifies** (Background
   Jobs J1 then J3, then J2) — J1's unconditional-ack-on-skip fix and J3's
   don't-ack-on-`CancelledError` fix must land before J2's `SIGTERM`-ownership fix, because fixing
   J2 alone first would newly expose every production worker deploy to J3's false-ack bug. This is
   the second-highest blast-radius item in the whole series: it affects nearly every background job
   type, silently, on every crash or deploy.
3. Fix Live Talk's quota unit (STT/Live Talk C1) and the chat-switch state bug (C2) — both P0,
   both cost/correctness, both isolated to `useLiveTalk.ts`/`speech_realtime.py`.
4. Fix the Gmail-reminder trust-framing bypass (Schedule F1) and the calendar-MCP-tool wrapping
   gap (Tool Loop F1) together — both are the same root cause (`wrap_untrusted` not applied
   consistently to externally-sourced content) in two different features; worth one PR review
   pass even though they're separate files.
5. Ship the cross-cutting `except Exception` → `except BaseException` cancellation-safety fixes as
   one batch: image-gen F1, and round 3's new S1 (`finalize_stream_turn_db`) — the dedicated sweep
   (round 3) already did the work of confirming these are the only two outstanding instances and
   that everything else either doesn't need it or isn't reachable; this pattern is now closed as a
   class, treat it as a small, final cleanup PR rather than an open-ended search.
6. Fix the two model-routing/quota accounting bugs together (Model Routing Q1 double-charge, Q2
   dead-code drift-heal) — same subsystem, same PR review pass, opposite-direction bugs
   (over-charge vs. under-charge) that are each individually small.
7. Add the missing production push-cycle test (Push PN1) before touching anything else in that
   file — this is a test-only PR that makes every subsequent push fix verifiable.
8. Fix mobile push-registration failure visibility (Push PN7), OAuth error typing (Schedule F2),
   and RevenueCat's refund-vs-cancel distinction (Billing F2) — all three are "users/revenue
   silently get nothing" bugs, independently shippable.
9. Add the memory "forget" delete path (Memory M1) and the `places`/`vocab_quiz` validation gaps
   (Output O1/O2) — three independent, narrow Pydantic-hardening fixes.
10. Consolidate the global-spend-kill-switch gap into one PR covering all four now-known-missing
    call sites (STT/Live Talk C3, Image Gen F2, Tool Loop F4's classifier call, plus a grep for
    any others) rather than fixing them one review at a time.
11. Add a RevenueCat reconciliation/polling backstop (Billing F3), move calendar/learning push
    dedupe claims to post-send (Push PN3), and pick up the smaller round-3/round-4 items
    (Background Jobs J4/J5 transactional-email idempotency and spend-cap-vs-dedupe interaction;
    Model Routing Q3 fallback-failure attribution; Account Lifecycle E4/E5/E6).
12. Fix the two mobile send-failure/mid-stream recovery gaps (Mobile Offline F2, F3) together —
    same architectural seam (`useChat`'s failure-path ownership of the optimistic user bubble),
    same PR review pass, and F3's fix reuses the exact forced-refetch mechanism the
    already-working backgrounding path (F3's "what's working" citation) provides for free.
13. Fix the GDPR export completeness gap (Account Lifecycle E2) and add the Pro-subscription
    deletion disclosure copy (E3) — both are compliance/trust-facing, both are small, targeted
    changes with no architecture risk.
14. Everything else in the thirteen reports' own "P2/P3/Medium/Low" sections and sequencing notes.

## What to review next (candidates, not yet covered)

All five previously-listed highest-value candidates from round 3 — the cancellation-safety sweep,
background jobs/worker infra, model routing/core quota, mobile offline resilience, and account
lifecycle/email — are now complete and folded into the findings above. Given the product
explicitly has no web client to review right now, remaining candidates are narrower:

- **Auth/session refresh (mobile Bearer-token flows)** — the Sep 4 `AUTH_SESSION_REVIEW` describes
  a large, thorough rewrite (atomic credential storage, session-generation guards, revocation
  precision) that predates this series; round 4 leaned on and re-verified pieces of it (session
  revocation on deletion) but a fresh, dedicated pass has not been done. Likely lower marginal
  value than it would have been before round 4, given how much of it round 4 already exercised.
- **i18n / localization correctness** — explicitly out of scope for every round so far; only
  covered historically by `docs/CODEBASE_REVIEW_2026-08.md`. Round 4 noted the locale-fallback
  behavior for transactional email is deliberate and tested, but did not review UI-string
  localization broadly.
- **Onboarding flow correctness** (`apps/mobile/app/onboarding.tsx`) beyond the auth/session and
  account-lifecycle pieces already covered — first-run UX, permission-request sequencing, and
  whether onboarding state itself has the same kind of session-scoping gap round 4 found in
  composer drafts.
- **The "tests exercise the wrong code path" and "helper/fix exists but never wired in" sweeps**
  called out above as now-confirmed 3-for-3 and 2-for-2 patterns respectively — not new domains,
  but per the cancellation-safety sweep's precedent, a dedicated cheap grep-based pass for either
  pattern could plausibly find more instances at lower cost than another full-domain review.

## Explicit non-goals of this cross-domain pass

- No code was changed by any of the thirteen reviews; this is a pure audit. Round 4's mobile
  offline review used a standalone reproduction script (outside the repo) to verify F1; nothing in
  the repository itself was modified.
- Did not re-review the chat loop's core LLM streaming logic, i18n, admin surfaces, or a web
  client — the first is covered by `docs/CODEBASE_REVIEW_2026-08.md` and the turn-quota lifecycle
  sub-piece was re-verified in round 3 (Model Routing Q-series); i18n and admin surfaces remain
  open candidates above; **no web client exists for this product today**, so it is explicitly
  excluded rather than deferred.
- Did not attempt on-device validation of Live Talk barge-in/echo/interruption timing, nor of the
  job-queue/worker-shutdown reproductions — round 3's crash-safety and `SIGTERM`-handling findings
  were reproduced with standalone scripts modeling the real code's shape and reading the installed
  `uvicorn`/`starlette` source, not by triggering an actual Fly deploy or OOM-kill; where device
  validation is claimed pending in FEATURES.md, the reports confirm that disclosure is accurate
  rather than trying to close it.
- Did not add HMAC webhook signature verification for RevenueCat (offered as a stronger
  alternative to the current constant-time shared-secret check) — not a demonstrated
  vulnerability, flagged as a future option only.
- Did not build a shared cancellation-safety abstraction (e.g. a `@refund_on_cancel` decorator) —
  round 3's sweep explicitly recommends against this with only four data points in hand; revisit
  if a fifth instance of the same call-site shape turns up.
- Did not propose an offline send queue or a WebSocket/SSE heartbeat protocol for mobile (round
  4's F2/F3 fixes are about correctly surfacing/recovering from an already-failed or
  already-finished turn, not about preventing disconnects or adding a durable outbox) — both are
  larger product/protocol decisions explicitly out of scope for a code-correctness review.
- Did not determine whether RevenueCat's API can programmatically cancel an Apple/Google store
  subscription on account deletion (Account Lifecycle E3) — Apple is known not to support this via
  any third-party backend; Play Store specifics were not verified against current docs, and the
  recommended fix is disclosure-first, not an assumed programmatic cancel.
