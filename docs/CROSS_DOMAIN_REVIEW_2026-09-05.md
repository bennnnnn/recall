# Recall — Cross-Domain Review: STT/Live Talk, Schedule, Push, Memory, Output Format (Sep 2026)

Staff-level review across five product-critical subsystems, run as five independent, read-only
deep-dives (one subagent per domain) and consolidated here. Each domain has its own full report
with file:line evidence:

| Domain | Full report | Top severity found |
|---|---|---|
| STT + Live Talk | [`STT_LIVE_TALK_REVIEW_2026-09-05.md`](./STT_LIVE_TALK_REVIEW_2026-09-05.md) | P0 ×2 |
| Schedule / Calendar / Gmail | [`SCHEDULE_CALENDAR_REVIEW_2026-09-05.md`](./SCHEDULE_CALENDAR_REVIEW_2026-09-05.md) | P1 ×2 |
| Push notifications | [`PUSH_NOTIFICATIONS_REVIEW_2026-09-05.md`](./PUSH_NOTIFICATIONS_REVIEW_2026-09-05.md) | P1 ×2 |
| Memory | [`MEMORY_ARCHITECTURE_REVIEW_2026-09-05.md`](./MEMORY_ARCHITECTURE_REVIEW_2026-09-05.md) | P1 ×1 |
| Output format / rich rendering | [`OUTPUT_FORMAT_REVIEW_2026-09-05.md`](./OUTPUT_FORMAT_REVIEW_2026-09-05.md) | P1 ×2 |

Each report also independently re-verified prior review docs (`docs/CODEBASE_REVIEW_2026-08.md`,
`docs/*_RELIABILITY_REVIEW_2026-09-04.md`) against current code rather than assuming they still
hold — all their headline fixes (C3/C4 memory split, C5/C7 fence registry, Schedule pagination
and conditional writes) were confirmed genuinely landed and correct. Findings below are net-new.

## Overall verdict

The core, oldest subsystems (chat loop, memory persistence, Schedule CRUD/delivery, fence
dispatch) are **correct by construction** — conditional writes, optimistic concurrency, lock
ordering, and registry-driven dispatch replaced hand-vigilance in exactly the places the Aug 2026
review flagged as weak, and the fixes hold up under a fresh, skeptical pass. The newer or
higher-surface-area subsystems (Live Talk's WebRTC session lifecycle, the production push
scheduler's two-session cycle, Gmail-sourced content crossing the prompt-injection trust
boundary, model-authored `places`/`vocab_quiz` fences) have not yet received the same treatment.
**Every P0/P1 finding below is a variant of one pattern: a boundary where either (a) a resource
reservation/trust decision is made once but the thing it's supposed to bound can silently exceed
it (quota, WebRTC session duration, dedupe claims, prompt trust), or (b) the code path that runs
in production is not the code path the tests exercise.**

## Top 10 findings, ranked across all domains

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

## Suggested sequencing (cross-domain, highest leverage first)

1. Fix Live Talk's quota unit (C1) and the chat-switch state bug (C2) — both P0, both cost/
   correctness, both isolated to `useLiveTalk.ts`/`speech_realtime.py`.
2. Fix the Gmail-reminder trust-framing bypass (Schedule F1) — narrow, one-file-ish, closes a live
   prompt-injection path.
3. Add the missing production push-cycle test (Push PN1) before touching anything else in that
   file — this is a test-only PR that makes every subsequent push fix verifiable.
4. Fix mobile push-registration failure visibility (Push PN7) and OAuth error typing (Schedule
   F2) — both are "users silently get nothing" bugs, independently shippable.
5. Add the memory "forget" delete path (Memory M1) and the `places`/`vocab_quiz` validation gaps
   (Output O1/O2) — three independent, narrow Pydantic-hardening fixes.
6. Wire the global spend kill-switch to voice (STT/Live Talk C3) and move calendar/learning push
   dedupe claims to post-send (Push PN3).
7. Everything else in the five reports' own "P2/P3" sections and sequencing notes.

## Explicit non-goals of this cross-domain pass

- No code was changed by any of the five reviews; this is a pure audit.
- Did not re-review the chat loop, jobs architecture, or i18n — covered by
  `docs/CODEBASE_REVIEW_2026-08.md` and not revisited unless a domain review touched them.
- Did not attempt on-device validation of Live Talk barge-in/echo/interruption timing — all five
  reports are static code reviews; where device validation is claimed pending in FEATURES.md, the
  reports confirm that disclosure is accurate rather than trying to close it.
