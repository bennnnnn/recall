# Recall — Cross-Domain Review: STT/Live Talk, Schedule, Push, Memory, Output Format, Billing, Image Gen, Tool Loop (Sep 2026)

Staff-level review across eight product-critical subsystems, run as eight independent, read-only
deep-dives (one subagent per domain, in two rounds) and consolidated here. Each domain has its own
full report with file:line evidence:

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

Each report also independently re-verified prior review docs (`docs/CODEBASE_REVIEW_2026-08.md`,
`docs/*_RELIABILITY_REVIEW_2026-09-04.md`, and each other's companion reports) against current
code rather than assuming they still hold — all their headline fixes (C3/C4 memory split, C5/C7
fence registry, Schedule pagination and conditional writes) were confirmed genuinely landed and
correct. Findings below are net-new.

## Overall verdict

The core, oldest subsystems (chat loop, memory persistence, Schedule CRUD/delivery, fence
dispatch, RevenueCat's plan-sync core, the sympy execution sandbox, the tool loop's one-round
cap) are **correct by construction** — conditional writes, optimistic concurrency, lock
ordering, registry-driven dispatch, and hard architectural caps replaced hand-vigilance in
exactly the places the Aug 2026 review flagged as weak, and the fixes hold up under a fresh,
skeptical pass across all eight domains. The newer or higher-surface-area subsystems (Live
Talk's WebRTC session lifecycle, the production push scheduler's two-session cycle, Gmail-sourced
content crossing the prompt-injection trust boundary, model-authored `places`/`vocab_quiz`
fences, the RevenueCat webhook's own success status code, `except Exception` vs `BaseException`
cancellation handling, calendar-tool untrusted-content wrapping) have not yet received the same
treatment. **Every P0/P1/High finding below is a variant of one of three patterns:**

1. **A resource reservation/trust decision is made once but the thing it's supposed to bound can
   silently exceed it** — quota granularity (Live Talk sessions, image-gen cancellation),
   dedupe claims (push), prompt trust (Gmail reminders, calendar tool results), tool-call/search
   fan-out (MCP tool loop).
2. **The code path that runs in production is not the code path the tests exercise** — the push
   scheduler's two-session cycle, the webhook's `204` vs. RevenueCat's documented `200` contract.
3. **A fix already exists elsewhere in the codebase for this exact bug class but wasn't
   consistently re-applied** — `except BaseException` for cancel-safety exists in
   `turn_resources.py`/`sympy_executor.py`/`attachment_reuse.py` but not `image_generation.py`;
   `wrap_untrusted` exists for web-search/Gmail/calendar-prompt-injection but not the calendar
   MCP tool; the global spend kill-switch exists for text chat but not voice, image-gen, or the
   tool-loop's own classifier call.

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

### Cross-cutting pattern worth calling out explicitly

**The `except Exception` (not `BaseException`) cancellation-safety gap has now been found twice,
independently, in two different subsystems reviewed by two different subagents** (Live Talk's
`/speech/live/session` flow in round 1, image generation's `generate_for_chat` in round 2) —
both against a codebase that has already fixed this exact bug class three times elsewhere
(`turn_resources.py`, `sympy_executor.py`, `attachment_reuse.py`, with a dedicated regression test
whose docstring states the lesson explicitly: *"Hard cancel (CancelledError) must refund — except
Exception would miss it"*). This strongly suggests a **fourth, cheap, high-leverage review**: grep
the entire backend for every `except Exception` block that sits between a quota/resource
reservation and its refund, on any code path reachable from a cancellable WS/SSE turn, and fix
them as one batch rather than one-at-a-time as each feature happens to get reviewed. This would
likely be higher-leverage than reviewing one more whole domain.

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

## Suggested sequencing (cross-domain, highest leverage first)

1. **Fix the RevenueCat webhook status code** (Billing F1) — literally one line, zero behavior
   risk, and it's the single highest blast-radius item in either round (every billing event,
   permanently, until fixed). Ship this first regardless of what else is in flight.
2. Fix Live Talk's quota unit (STT/Live Talk C1) and the chat-switch state bug (C2) — both P0,
   both cost/correctness, both isolated to `useLiveTalk.ts`/`speech_realtime.py`.
3. Fix the Gmail-reminder trust-framing bypass (Schedule F1) and the calendar-MCP-tool wrapping
   gap (Tool Loop F1) together — both are the same root cause (`wrap_untrusted` not applied
   consistently to externally-sourced content) in two different features; worth one PR review
   pass even though they're separate files.
4. Do the cross-cutting `except Exception` → `except BaseException` cancellation-safety sweep
   described above (round 2's cross-cutting pattern) — fixes image-gen F1 as part of a batch
   rather than a one-off, and pre-empts a third occurrence in whatever domain gets reviewed next.
5. Add the missing production push-cycle test (Push PN1) before touching anything else in that
   file — this is a test-only PR that makes every subsequent push fix verifiable.
6. Fix mobile push-registration failure visibility (Push PN7), OAuth error typing (Schedule F2),
   and RevenueCat's refund-vs-cancel distinction (Billing F2) — all three are "users/revenue
   silently get nothing" bugs, independently shippable.
7. Add the memory "forget" delete path (Memory M1) and the `places`/`vocab_quiz` validation gaps
   (Output O1/O2) — three independent, narrow Pydantic-hardening fixes.
8. Consolidate the global-spend-kill-switch gap into one PR covering all four now-known-missing
   call sites (STT/Live Talk C3, Image Gen F2, Tool Loop F4's classifier call, plus a grep for
   any others) rather than fixing them one review at a time.
9. Add a RevenueCat reconciliation/polling backstop (Billing F3) and move calendar/learning push
   dedupe claims to post-send (Push PN3).
10. Everything else in the eight reports' own "P2/P3/Medium/Low" sections and sequencing notes.

## What to review next (candidates, not yet covered)

- **Auth/session refresh, models/quota routing (fallback logic), `core/jobs.py`'s inverted-layer
  finding (C2 from the Aug 2026 review — check if it was ever fixed)** — moderate risk, some
  already reviewed recently (Sep 4 auth session review) so lower marginal value than the items
  below.
- **The `except Exception`-vs-`BaseException` cancellation sweep** described above — not a new
  domain, but the single highest-leverage next action given it's now a confirmed 2-for-2 pattern.
- **Admin/health/worker process infra** (`worker_health.py`, `process_bootstrap.py`) — not yet
  reviewed at all; lower urgency than money/security paths but worth a pass before any production
  scale-up.
- **Transactional email** (`transactional_email.py`) — lower stakes than push, likely quick.

## Explicit non-goals of this cross-domain pass

- No code was changed by any of the eight reviews; this is a pure audit.
- Did not re-review the chat loop, jobs architecture, or i18n — covered by
  `docs/CODEBASE_REVIEW_2026-08.md` and not revisited unless a domain review touched them.
- Did not attempt on-device validation of Live Talk barge-in/echo/interruption timing — all eight
  reports are static code reviews; where device validation is claimed pending in FEATURES.md, the
  reports confirm that disclosure is accurate rather than trying to close it.
- Did not add HMAC webhook signature verification for RevenueCat (offered as a stronger
  alternative to the current constant-time shared-secret check) — not a demonstrated
  vulnerability, flagged as a future option only.
