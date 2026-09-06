# Recall — STT & Live Talk Code Review (Sep 2026)

Scope: **only** speech-to-text voice input (composer dictation) and Live Talk
(WebRTC speech-to-speech via OpenAI Realtime). Not a review of chat text, memory,
schedule, or any other domain. Reviewed at `main` (052eab2e, "Codex/expo go
startup (#1187)").

---

## A. Verdict

**The security posture is genuinely solid; the cost-control and turn-lifecycle
posture is not.** The OpenAI API key never reaches the client, the Realtime
credential is a short-lived server-minted `ek_` secret, every Redis-backed
session/tool key is scoped by `user.id`, and the no-speech gate, rate limits,
and daily caps are all real, tested, server-side checks
(`apps/api/app/services/transcript_validation.py`, `apps/api/app/services/quota.py`).
Composer dictation (`useVoiceInput`) is a clean, well-isolated hook with
real thread-affinity guards against stale transcripts landing in the wrong chat.

**The single biggest problem is that Live Talk's daily cap is enforced at the
wrong granularity.** The code's own comment says *"One slot = one user utterance
that is sent as a chat turn"* (`apps/api/app/services/quota.py:418-419`), and
FEATURES.md advertises **"30 turns/day."** But the reservation actually happens
once per `POST /speech/live/session` call — i.e. once per WebRTC connection —
and a single WebRTC session can carry an unbounded number of spoken turns for
an unbounded duration (no client or server timer ever closes it). Compounding
this, the one refund path that exists for a failed connection
(`POST /speech/live/refund`) has had its only mobile caller deleted
(commit `d799231a`, "Remove leftover batch Live Talk now that WebRTC is the
only path"), so a WebRTC handshake that fails *after* a successful mint burns
a daily slot permanently with zero speech ever exchanged. This is a real
dollar-cost exposure given OpenAI Realtime audio billing, not just a UX nit —
see **C1**.

**The second biggest problem is a genuine turn-lifecycle/state bug, not just a
cost issue:** switching chats from the drawer while Live Talk is open does not
close the Live Talk session (`LiveTalkOverlay` deliberately keeps the header
tappable for exactly this). The hook's `chatId` binding is captured once at
`open()` and never re-synced, so a spoken turn started after switching chats
gets its live bubbles painted into the *newly opened* chat's message list but
persisted server-side to the *old* chat — see **C2**.

Everything else is smaller: the global per-day spend kill-switch that protects
text chat from runaway OpenRouter cost was never wired to voice spend (C3), one
FEATURES.md claim ("Voice input... Not available in Expo Go") is now stale as
of the very last commit touching this area (C4), Live Talk has no
app-background/interruption handling at all (C5), and the mint-failure refund
path — the only surviving one — has zero test coverage (see §D).

---

## B. What's working (don't "fix" these)

- **No provider key ever reaches the client.** `openai_speech_gateway.create_realtime_client_secret`
  (`apps/api/app/gateways/openai_speech_gateway.py:95-144`) is the only place the
  permanent `OPENAI_API_KEY` is used; mobile receives only a short-lived `ek_`
  client secret and does the SDP exchange directly against OpenAI
  (`apps/mobile/lib/realtimeVoice.ts:283-289, 695-702`). This matches golden
  rule 1 exactly.
- **Every session/tool key is scoped by `user_id`.** `_realtime_session_key`
  (`apps/api/app/services/live_talk.py:46-47`) and the live-tool cache key
  (`apps/api/app/services/live_talk_tools.py:26-28`) both embed `user.id`, so
  `/speech/live/persist` and `/speech/live/tool` cannot be pointed at another
  user's `call_id` — verified against `test_persist_requires_issued_realtime_session`
  and the parametrized ownership test in
  `apps/api/app/tests/test_speech_realtime.py:145-165, 330-365`.
- **The no-speech gate is real and layered.** Client-side, `useVoiceInput`
  requires `VOICE_MIN_SPEECH_SAMPLES = 2` metering samples above threshold
  before it will even upload (`apps/mobile/hooks/useVoiceInput.ts:29,117-126`).
  Server-side, `sanitize_transcript` drops classic Whisper silence
  hallucinations ("thank you for watching" etc.) only on clips too small to be
  real speech (`apps/api/app/services/transcript_validation.py:39-48`), with
  three focused unit tests. This is exactly the kind of narrow, linear-scan
  gate the security-alert-pitfalls skill asks for — no regex, no ReDoS surface.
- **Legacy-client versioning is handled deliberately, not accidentally.**
  Stale builds calling the removed batch endpoints get explicit `410 Gone`
  (`/speech/live/turn`, `/speech/live/commit`, `/speech/live/speak` —
  `apps/api/app/routers/speech.py:491-531`) or `426 Upgrade Required` for the
  removed server-proxied SDP path (`/speech/live/webrtc` —
  `apps/api/app/routers/speech_realtime.py:175-188`), all with tests
  (`test_speech_live_turn_gone`, `test_legacy_webrtc_endpoint_requires_current_mobile_bundle`).
  This is a good pattern other seams in the codebase could reuse.
- **`useVoiceInput` and `useLiveTalk` are cleanly separated, not entangled.**
  They are two independent hooks instantiated side-by-side in
  `apps/mobile/app/index.tsx:345-382` with no shared refs or state; the only
  coupling is `ChatComposer`'s `onSend` calling `liveTalkSession?.onYield()`
  (`apps/mobile/components/chat/ChatScreenBody.tsx:241-244`), which is the
  documented, intentional "typing yields voice mode" behavior.
- **Voice-input thread affinity is actually correct.** `voiceCaptureThreadRef`
  is snapshotted at record-start and checked against the *current* composer
  thread before a transcript is ever inserted, so navigating to a different
  chat mid-recording cannot leak a transcript into the wrong composer
  (`apps/mobile/app/index.tsx:336,347-363`); recording is also cancelled on
  route change (`useLayoutEffect` at `apps/mobile/app/index.tsx:354-356`).
  **Live Talk has no equivalent guard — see C2.**
- **Search-source reuse, not duplication.** Live Talk's `web_search` tool
  results are appended as the exact same ` ```sources ` fence the text-chat
  pipeline emits (`apps/api/app/routers/speech_realtime.py:223-228`), so the
  mobile source chips under a reply work unmodified for spoken turns. Good
  reuse of an existing seam instead of a second rendering path.
- **Tavily budget is shared, not duplicated.** The Live Talk `web_search` tool
  binds into the same per-user Tavily daily-search budget as text chat via
  `bind_search_quota_context` (`apps/api/app/services/live_talk_tools.py:79`,
  `apps/api/app/services/mcp/web_search_adapter.py:27-44`) — it does not have
  its own uncapped search allowance.
- **Backend persistence/memory-context test coverage is genuinely good.**
  `apps/api/app/tests/services/test_live_talk.py` (9 tests) exercises
  writing both roles, the follow-up-persist-without-user-row path, memory
  load failure degrading gracefully to an empty block, and the missing-chat
  404 path — this is real coverage of the persistence seam, not padding.
- **FEATURES.md's own hedges about Live Talk are honest, not spin.** The
  claims "physical-device barge-in implemented, live validation pending" and
  "iOS Simulator retains half-duplex" (FEATURES.md:146-147, 932) both check
  out against the code: `barge_in` is wired to `interrupt_response` end-to-end
  (`apps/api/app/gateways/openai_speech_gateway.py:53-54` →
  `apps/mobile/lib/realtimeVoice.ts:311`), gated by
  `webRtcMicConstraints()`/`isIosSimulator()`
  (`apps/mobile/lib/realtimeVoice.ts:101-130`), and the only test evidence is
  mocked WebRTC events (`apps/mobile/lib/__tests__/realtimeVoiceSession.test.ts`)
  — there is no device-validation artifact in the repo, which is exactly what
  the doc discloses.

---

## C. Findings — ranked

### Cost control / quota correctness

---

**C1 — Live Talk's daily cap is spent per WebRTC session, not per spoken turn, and the one refund path for a failed connection is unreachable from the client**
**Severity:** P0 · **Area:** live-talk / cost-control · **Effort:** M

**Evidence:**
- The comment documenting the intended model: *"One slot = one user utterance
  that is sent as a chat turn. Pending key lets the client refund if STT/send
  fails before the model starts."* (`apps/api/app/services/quota.py:418-419`).
  FEATURES.md agrees: **"Live talk turns/day | 0 (Pro only) | 30"**
  (FEATURES.md:1050) and *"Pro: 30 turns/day"* (FEATURES.md:148).
- The reservation actually happens exactly once, inside
  `_reserve_realtime_or_raise` (`apps/api/app/routers/speech_realtime.py:100-134`),
  called once from `create_realtime_session`
  (`apps/api/app/routers/speech_realtime.py:137-172`) — i.e. once per
  `POST /speech/live/session` call.
- Mobile calls `/speech/live/session` exactly once per `open()`
  (`apps/mobile/hooks/useLiveTalk.ts:371-381` →
  `apps/mobile/lib/realtimeVoice.ts:283-289`), and the resulting WebRTC
  connection (`apps/mobile/lib/realtimeVoice.ts:256-767`) stays open across an
  arbitrary number of `speech_started` → `response_done` cycles — each one a
  full conversational turn persisted separately via
  `persistRealtimeLiveTalkTurn` (`apps/mobile/hooks/useLiveTalk.ts:162-222`) —
  until the user taps close. Nothing re-reserves a slot per turn, and nothing
  bounds session duration: the OpenAI credential's `expires_at` is logged
  (`apps/mobile/lib/realtimeVoice.ts:699`) but never enforced to end or renew
  the session.
- The moment the mint succeeds, the pending flag that would allow a refund is
  cleared immediately — *before* the client has even attempted the WebRTC
  handshake: `await quota_service.clear_live_talk_pending(redis, user.id)`
  (`apps/api/app/routers/speech_realtime.py:166`), right after
  `issue_realtime_session` (line 165) and before `RealtimeSessionOut` is
  returned. The *only* place `refund_live_talk_if_pending` fires is the
  mint-failure branch two lines above it (line 159), when
  `create_realtime_client_secret` itself returns `None`.
- `POST /speech/live/refund` (`apps/api/app/routers/speech.py:500-513`) is the
  only other caller of `refund_live_talk_if_pending`, and it has **no mobile
  caller at all**. `apps/mobile/lib/api/speech.ts` has no `refund`/`refundLiveTalkTurn`
  function. `git log -p -- apps/mobile/lib/api/speech.ts` shows
  `refundLiveTalkTurn` existed from the original PR (#914) through the last
  batch-era commit and was deleted in `d799231a` ("Remove leftover batch Live
  Talk now that WebRTC is the only path"), which kept the backend route as a
  compatibility stub for "stale builds" but never re-wired a caller for the
  new WebRTC flow. `useLiveTalk.open()`'s catch block
  (`apps/mobile/hooks/useLiveTalk.ts:383-389`) and `close()`
  (`apps/mobile/hooks/useLiveTalk.ts:316-335`) both have every fact needed to
  call it (they know the attempt failed / the user never spoke) and neither
  does.

**Why it matters:** the effective daily allowance is not "30 turns" — it is
"30 WebRTC connections, each of unbounded duration." A Pro user who opens Live
Talk once and talks for 20 minutes across dozens of exchanges spends exactly 1
of their 30 slots; a user on a flaky network who gets an ICE/DTLS failure
right after a successful mint (a common WebRTC failure mode, and the app's own
`CONNECTION_TIMEOUT_MS = 10_000` in `realtimeVoice.ts:48` acknowledges this
happens) loses a slot with zero audio ever exchanged, and cannot get it back.
OpenAI Realtime audio is billed per minute of audio, not per message, so this
is a real, uncapped cost multiplier on top of the "30 turns/day" the product
believes it is charging Pro users for — not merely a fairness/UX issue.

**Recommended fix (smallest seam):**
1. Re-instate a `refundLiveTalkTurn`/`liveTalkRefund` call in
   `apps/mobile/lib/api/speech.ts`, and call it from `useLiveTalk`'s `open()`
   catch block whenever the WebRTC handshake fails or times out after a
   successful mint, and from `close()` when a session ends having produced
   zero turns (`captureCurrentTurn()` returns nothing).
2. Move `clear_live_talk_pending` to fire only after the *first* accepted
   utterance is confirmed (e.g. on the first `/speech/live/persist` or a new
   lightweight "session started speaking" ping), not immediately after mint,
   so the existing pending-refund window actually covers the WebRTC handshake.
3. Add a server-enforced or client-enforced maximum session duration (e.g.
   close and require a fresh `/speech/live/session` call after N minutes),
   so one reservation cannot cover unbounded audio-minutes. Decide deliberately
   whether the product wants "N sessions/day" or "N turns/day" — pick one and
   make the code, the comment in `quota.py`, and FEATURES.md agree.

**Do not:** change the free-tier gate (0 for free, Pro-only) or the `30`
number itself without a product decision — this finding is about the unit the
cap is denominated in, not the number.

---

**C2 — Switching chats from the drawer while Live Talk is open does not close the session; the next turn is displayed in the wrong chat and persisted to a different one**
**Severity:** P0 · **Area:** live-talk / mobile state machine · **Effort:** S

**Evidence:**
- `LiveTalkOverlay` deliberately reserves `headerInset` "so ChatHeader
  (hamburger / ⋮) stays tappable" (`apps/mobile/components/chat/LiveTalkOverlay.tsx:27-30,90-93`),
  and FEATURES.md documents this as intentional: *"The chat header (drawer /
  ⋮) stays available."* (FEATURES.md:156). The drawer can therefore be opened
  and a different chat selected while a Live Talk WebRTC session is actively
  listening.
- `useLiveTalk.open()` captures the chat id **once**, into `turnChatIdRef.current`
  (`apps/mobile/hooks/useLiveTalk.ts:362`), and nothing in the hook watches
  `chatId`/`routeChatId` afterward to update it or close the session. The
  hook's only teardown effect runs on unmount only —
  `useEffect(() => { ...; return () => closeRef.current(); }, [])` with an
  **empty dependency array** (`apps/mobile/hooks/useLiveTalk.ts:426-435`).
- `useChatRouteLoader`'s route-change effect, which fires on every
  `routeChatId` change from the drawer, unconditionally does
  `setMessages([])` and loads the newly selected chat's messages into that
  same shared array (`apps/mobile/hooks/useChatRouteLoader.ts:340-441`,
  specifically lines 375 and 392). It has no knowledge of, and does not
  touch, `useLiveTalk`'s internal refs.
- `grep -rn "liveTalk" apps/mobile/components/drawer apps/mobile/contexts/DrawerContext.tsx`
  returns zero matches — no drawer code path closes or even reads Live Talk
  state when a chat is selected.
- The only place `liveTalk.close()`/`yieldToComposer` is ever invoked outside
  the explicit close button and hardware back button is `ChatComposer`'s
  `onSend` (`apps/mobile/components/chat/ChatScreenBody.tsx:241-244`) — i.e.
  only when the user types and sends text, never on a chat switch.

**Why it matters:** after a drawer chat switch, the Live Talk overlay stays
visible on top of the newly opened chat (its `visible` state is independent of
`routeChatId`), the mic keeps listening, and the *next* spoken turn's live
bubbles are painted via `applyEvent`/`setMessages` into the *new* chat's
message array (`apps/mobile/hooks/useLiveTalk.ts:138-144`) while
`finishTurn`'s persist call still sends `chatId: completed.chatId` —
`turnChatIdRef.current`, the *old* chat
(`apps/mobile/hooks/useLiveTalk.ts:146-160,169-190`). The user sees a voice
exchange appear in the chat they just switched to, but the backend saves it
under the chat they left; the next reload of either chat silently disagrees
with what was on screen a moment earlier. This is exactly the "state machine
bug in the live-talk turn lifecycle" class of issue called out in scope, and
it is currently unguarded and untested (no test references `liveTalk` in
`apps/mobile/hooks/__tests__/useChatRouteLoader.test.tsx`).

**Recommended fix:** close the Live Talk session (call the same path as the
existing close button) as soon as `routeChatId` changes away from the chat the
session was opened against — a small `useEffect` in `useLiveTalk` keyed on
`chatId`/`routeChatId`, mirroring the pattern `useVoiceInput` already uses for
composer dictation (`apps/mobile/app/index.tsx:354-356`). Flush any in-flight
turn to the *original* chat before tearing down, exactly as `close()` already
does for the explicit-close case.

**Do not:** block the drawer/header from opening while Live Talk is visible —
that access is an intentional, documented feature; the fix is to close the
*session*, not to hide the *header*.

---

**C3 — The global per-day spend kill-switch protects text chat but was never wired to voice (STT/TTS/Live Talk) spend**
**Severity:** P1 · **Area:** cost-control / api · **Effort:** S

**Evidence:** `record_global_spend` and `global_spend_exceeded`
(`apps/api/app/services/quota.py:468-509`, comment: *"we do not burn money
while the meter is blind"*) are called from exactly three places:
`apps/api/app/services/chat/stream_pipeline.py:117`,
`apps/api/app/services/chat/post_turn.py:251,287`, and
`apps/api/app/background/handlers.py:108` — all text-chat/OpenRouter paths.
`grep -rn "global_spend" apps/api/app/routers/speech.py apps/api/app/routers/speech_realtime.py apps/api/app/services/speech.py apps/api/app/services/live_talk.py apps/api/app/gateways/openai_speech_gateway.py`
returns nothing.

**Why it matters:** per-user daily caps exist for speech (30/200 transcriptions,
30 live-talk sessions for Pro — see C1 for why that number under-counts real
cost) but the backstop that exists specifically because per-feature caps can
be wrong or bypassed does not cover voice at all. Given C1's finding that a
Live Talk "session" can run for an unbounded duration, this is the second
independent layer that should have caught runaway voice spend and does not.

**Recommended fix:** call `global_spend_exceeded` in
`_reserve_realtime_or_raise` and `_reserve_tts_or_raise`/`/speech/transcribe`
before minting/transcribing, and call `record_global_spend` with an estimated
cost after each successful realtime session close, TTS synthesis, and
transcription (OpenAI per-minute/per-character pricing is known up front, so
an estimate is straightforward even without exact usage telemetry from the
Realtime API).

**Do not:** fold this into the same PR as C1 — the reservation-granularity fix
and the kill-switch wiring are independently valuable and separately
reviewable.

---

### Reliability / lifecycle gaps

---

**C5 — Live Talk has no app-background, phone-call-interruption, or route-change handling; a suspended app cannot flush or close an in-flight session**
**Severity:** P1 · **Area:** live-talk / mobile reliability · **Effort:** S/M

**Evidence:** `grep -rln "AppState" apps/mobile --include=*.ts --include=*.tsx`
lists 11 files (`useNetworkStatus.ts`, `useTodosList.ts`,
`useChatRouteLoader.ts`, `useUsage.ts`, `useLessonAudio.ts`,
`ProjectsContext.tsx`, `ModelsContext.tsx`, `HomeContext.tsx`,
`chatForegroundRefetch.ts`, `pushNotifications.ts`, `gmailAutoSync.ts`) — none
of them is `useLiveTalk.ts` or `realtimeVoice.ts`, and neither of those files
imports `AppState`. Text chat has an explicit, tested pattern for exactly this
class of problem — *"Backgrounding mid-stream kills the socket; onclose
commits a truncated bubble... pull the server's full reply without requiring
the user to leave the chat"* (`apps/mobile/hooks/useChatRouteLoader.ts:293-296`)
— and Live Talk has no analogue. The only lifecycle hooks Live Talk has are
Android hardware-back (`apps/mobile/hooks/useLiveTalk.ts:416-424`) and an
unmount-only cleanup (`apps/mobile/hooks/useLiveTalk.ts:426-435`).

**Why it matters:** if the app is backgrounded (or a phone call/other app
interruption takes over the audio session) while Live Talk is open, there is
no code path that mutes/pauses capture, flushes an in-flight turn before the
process may be suspended, or closes the WebRTC peer and releases the reserved
slot. Depending on OS behavior this either leaves an active (billed) Realtime
session running with no UI, or the connection is torn down by the OS with an
in-flight turn silently lost (no `response_done` ever arrives to trigger
`finalizeCurrentTurn`). This is squarely one of the reliability scenarios
named in scope ("background/foreground transitions, phone call interruption,
headphone route changes") and none of it has explicit handling in this repo —
whatever behavior exists today is entirely whatever `react-native-webrtc`'s
native defaults happen to do, which this review cannot verify without a
physical-device test (consistent with FEATURES.md's own disclosure that
device validation is pending).

**Recommended fix:** add an `AppState` listener in `useLiveTalk` mirroring
`useChatRouteLoader`'s: on `background`/`inactive`, flush the current turn
(`flushPendingTurn()` already exists and is safe to call early) and close the
session; do not silently rely on the OS to do this. If product wants Live Talk
to *survive* brief backgrounding (e.g. a quick notification-shade peek),
that's a legitimate design choice, but it should be a decision, not an
absence.

**Do not:** try to solve headphone-route-change or CallKit interruption
recovery in the same change — flushing/closing on background is the
minimum-safe first step; full interruption *resume* is a larger, separate
feature decision.

---

**C6 — Live Talk's error mapping has no case for microphone-permission-denied; the user sees a generic "unavailable" message with no path to Settings, unlike composer dictation**
**Severity:** P2 · **Area:** live-talk / mobile UX · **Effort:** S

**Evidence:** `useVoiceInput.startRecording` explicitly requests permission
and shows a dedicated alert on denial:
`Alert.alert(t("chat.voice_permission_title"), t("chat.voice_permission_body"))`
(`apps/mobile/hooks/useVoiceInput.ts:84-88`). Live Talk instead calls
`webrtc.mediaDevices.getUserMedia(...)` directly
(`apps/mobile/lib/realtimeVoice.ts:268-276`) with no explicit permission
request step, and `liveTalkErrorGate` — the sole place errors from `open()`
are translated into user-facing copy — only special-cases
`webrtc_unavailable` and HTTP `status` 403/429/503/404
(`apps/mobile/lib/liveTalkLogic.ts:83-96`); anything else, including a
`getUserMedia` permission rejection, falls through to the generic
`"unavailable"` gate and `chat.live_talk_unavailable_body` copy
(`apps/mobile/hooks/useLiveTalk.ts:100-117`).

**Why it matters:** a user who previously denied microphone access gets the
same message for "Live Talk is broken on this device" and "you denied mic
permission, go to Settings" — the second case has an obvious, actionable fix
that the first doesn't, and the composer already models the right UX for it a
few files away.

**Recommended fix:** detect the native permission-denied error (typically
`NotAllowedError`/a specific `getUserMedia` rejection) in `createRealtimeVoiceSession`
or `liveTalkErrorGate`, and map it to a distinct gate with copy that opens
Settings, matching `useVoiceInput`'s existing pattern.

**Do not:** add a pre-flight permission *request* dialog before `getUserMedia`
— that would be a second confirmation step the product has deliberately
avoided elsewhere (composer-only image gen, no prompt sheets); improve the
*denial* message, not the happy path.

---

### Documentation / FEATURES.md divergence

---

**C4 — FEATURES.md still claims Voice input (STT) is "Not available in Expo Go"; the most recent commit touching this exact code made it available**
**Severity:** P2 · **Area:** docs · **Effort:** S

**Evidence:** FEATURES.md:141-143: *"Voice input (STT) — mic in the composer
records on-device (`expo-audio`, **dev build**)... Not available in Expo Go."*
`apps/mobile/lib/expoRuntime.ts:40-42`'s `canUseVoiceInput()` unconditionally
returns `true`, with the comment *"Dictation uses expo-audio, which is
included in Expo Go."* `git show 052eab2e -- apps/mobile/lib/expoRuntime.ts`
(the tip commit reachable from this review, "Codex/expo go startup (#1187)")
shows this was changed *from* `return !isExpoGo();` *to* `return true;` in
this repo's most recent commit touching the file, with the commit message
*"Keep dictation and Live Talk usable in Expo Go without a WebRTC crash.
expo-audio is in Expo Go so the composer mic can show."* That same commit did
not touch `FEATURES.md` (`git show 052eab2e --stat` has no `FEATURES.md`
entry; `git log -1 -- FEATURES.md` resolves to an earlier commit, `50f790db`).

**Why it matters:** this is precisely the "verify claims against the actual
code" check the review scope asked for, and it fails — a reader of
FEATURES.md today would incorrectly tell a user or plan a QA pass around STT
requiring a dev build, when the shipped code now intentionally allows it in
Expo Go. (Live Talk itself is unaffected — WebRTC is still gated separately
and still correctly requires a dev build, per the same commit's message and
`isRealtimeVoiceAvailable()` — apps/mobile/lib/realtimeVoice.ts:92-94.)

**Recommended fix:** update FEATURES.md:141-143 to drop the "Not available in
Expo Go" clause for STT specifically (keep it for Live Talk, where it's still
accurate), matching the intent of commit `052eab2e`.

**Do not:** change any gating code as part of a docs fix — this is a one-line
FEATURES.md correction.

---

### Minor

---

**C8 — Two independent feature flags (`speech_live_talk_enabled`, `speech_realtime_voice_enabled`) always gate the same feature together; the quota-reservation preamble is duplicated across two router files**
**Severity:** P2 · **Area:** api / minor architecture · **Effort:** S

**Evidence:** every check in `routers/speech_realtime.py` tests both flags
together — `if not settings.speech_live_talk_enabled or not settings.speech_realtime_voice_enabled`
(`apps/api/app/routers/speech_realtime.py:101,197,265`) — there is no code
path where they differ. Separately, `_reserve_tts_or_raise`
(`apps/api/app/routers/speech.py:68-89`) and `_reserve_realtime_or_raise`
(`apps/api/app/routers/speech_realtime.py:100-134`) both hand-roll the same
"rate-limit check, then daily-cap reserve, then raise 429" shape; a third,
inline copy of the same shape lives in `/speech/transcribe`
(`apps/api/app/routers/speech.py:445-465`).

**Why it matters:** low risk today (three call sites, all correct), but it's
the same "copy-paste preamble" pattern flagged as C8 in the prior
`docs/CODEBASE_REVIEW_2026-08.md` for chat SSE — a fourth speech endpoint
would copy it a fourth time.

**Recommended fix:** collapse the two flags to one if there's truly no reason
to ship Realtime independently of "Live Talk enabled," and factor the
rate-limit-then-reserve preamble into one small helper
(`reserve_or_raise(redis, key, rate_limit, daily_limit, message)`) shared by
all three call sites.

**Do not:** treat this as urgent — fold it into any future PR that already
touches these files rather than opening a dedicated one.

---

## D. Test coverage gaps (scope item 5)

**Solid today:** transcription provider failure → 502
(`test_speech_transcribe_provider_failure_is_502`), daily cap
(`test_speech_transcribe_daily_cap`), rate limit
(`test_speech_transcribe_rate_limit`), oversized-payload rejection
(`test_speech_transcribe_6mb_is_413_before_quota`), TTS cancellation refund
(`test_speech_tts_cancelled_refunds`), the no-speech gate
(`test_sanitize_drops_watching_hallucination_on_tiny_clip`), Live Talk
persistence + memory-context loading including the missing-chat 404 and
memory-load-failure paths (`apps/api/app/tests/services/test_live_talk.py`,
9 tests), and tool-call session/plan/allowlist enforcement
(`test_voice_tools_enforce_session_ownership_plan_and_read_only_allowlist`,
5 parametrized cases) — all in `apps/api/app/tests/`.

**Missing:**

| Gap | Evidence |
|---|---|
| `POST /speech/live/session` has no test for quota-exceeded (429) | `_session_mint_patches` in `apps/api/app/tests/test_speech_realtime.py:116-142` unconditionally patches `reserve_live_talk` to `AsyncMock(return_value=True)`; no test flips it to `False` |
| `POST /speech/live/session` has no test for free-plan (403), missing-key (503), or mint-failure (502 + refund) | `grep -c "403\|503\|502" apps/api/app/tests/test_speech_realtime.py` → the only status codes exercised for this route are 200; the mint-failure branch that is C1's *only* surviving refund path (`speech_realtime.py:158-161`) has zero test coverage |
| No test for a WebRTC connection dropping *after* it reached `connected` | `apps/mobile/lib/__tests__/realtimeVoiceSession.test.ts` and `realtimeVoice.test.ts` cover the connect-time-unavailable and mocked in-session event paths, but neither fires `pc.onconnectionstatechange` → `"failed"` once already connected (`apps/mobile/lib/realtimeVoice.ts:439-445`) |
| No hook-level test for `useLiveTalk.ts` or `useVoiceInput.ts` at all | `find apps/mobile -iname "*useLiveTalk*" -o -iname "*useVoiceInput*"` returns only the source files; the pure-logic modules they call (`liveTalkLogic.ts`, `liveTalkEvents.ts`, `liveTalkSfx.ts`) are well tested, but the stateful turn machine in the hook itself (flush-on-new-utterance, close-mid-turn, error-path alerting) is not exercised by any test |
| No test for the C2 drawer-chat-switch scenario | `grep -rn "liveTalk" apps/mobile/hooks/__tests__/*.test.*` → no matches; the bug in C2 has no regression test because the interaction was never modeled |
| Multipart `/speech/transcribe` size check can be bypassed by omitting `Content-Length` | `_reject_oversized_speech_body` (`apps/api/app/routers/speech.py:224-238`) is only invoked with the header value before `await request.form()` parses the full body (`apps/api/app/routers/speech.py:426-429`); no test sends a multipart body with no `Content-Length` header to confirm behavior under that condition |

---

## E. Weak / unwanted / missing inventory

| Item | Status | Evidence | Recommend |
|---|---|---|---|
| Live Talk quota granularity | Weak (wrong unit) | `quota.py:418-419` comment vs. one reservation per `/speech/live/session` call | Fix (C1) |
| Live Talk refund path | Weak (dead from client) | `speech.ts` has no refund caller; deleted in `d799231a` | Fix (C1) |
| Live Talk session duration | Missing (unbounded) | no timer anywhere in `realtimeVoice.ts`/`useLiveTalk.ts` | Fix (C1) |
| Drawer chat-switch vs. open Live Talk session | Missing (unguarded) | no `liveTalk` reference in drawer code or `useChatRouteLoader` | Fix (C2) |
| Global spend kill-switch coverage | Missing-gap (voice excluded) | `record_global_spend`/`global_spend_exceeded` callers are all text-chat | Fix (C3) |
| FEATURES.md STT/Expo-Go claim | Stale | contradicted by `052eab2e` | Fix (C4) |
| Live Talk AppState/backgrounding handling | Missing | `grep -rln AppState` excludes `useLiveTalk.ts`/`realtimeVoice.ts` | Add (C5) |
| Live Talk mic-permission-denied UX | Weak (generic message) | `liveTalkErrorGate` has no case for it; `useVoiceInput` does | Add (C6) |
| `speech_live_talk_enabled` / `speech_realtime_voice_enabled` | Weak (redundant flags) | always checked together, `speech_realtime.py:101,197,265` | Collapse (C8) |
| Rate-limit + daily-reserve preamble | Weak (copy-pasted 3×) | `speech.py:68-89,445-465`, `speech_realtime.py:100-134` | Factor out (C8) |
| No provider key on mobile | Solid | `openai_speech_gateway.py` is the sole key user | Keep as-is |
| Per-user session/tool key scoping | Solid | `live_talk.py:46-47`, `live_talk_tools.py:26-28` | Keep as-is |
| No-speech gate (client + server) | Solid | `useVoiceInput.ts:29,117-126`, `transcript_validation.py:39-48` | Keep as-is |
| Legacy-client 410/426 stubs | Solid | `speech.py:491-531`, `speech_realtime.py:175-188` | Keep as-is |
| `useVoiceInput`/`useLiveTalk` separation | Solid | independent hooks, no shared state | Keep as-is |
| Voice-input thread affinity | Solid | `voiceCaptureThreadRef` guard, `index.tsx:336,347-363` | Keep as-is |
| Backend Live Talk persistence tests | Solid | `test_live_talk.py`, 9 tests incl. memory-failure and 404 paths | Keep as-is |
| Tavily budget sharing for the voice `web_search` tool | Solid | `bind_search_quota_context` reused, not duplicated | Keep as-is |

---

## F. Explicit non-goals of this review

Considered and intentionally not pursued further here:

- **TTS/read-aloud-specific logic** (the lead/rest follow-up Lua script, voice
  selection, `expo-speech` fallback) — out of the stated scope (STT + Live
  Talk only); only touched where it shares a router file or quota helper with
  in-scope code.
- **Actual device testing of barge-in, echo cancellation, or interruption
  timing.** This is a static code review; FEATURES.md already discloses this
  gap accurately (see "What's working"), and nothing found here contradicts
  that disclosure.
- **Chat-loop, memory, todos, or any other domain** — reviewed only insofar as
  Live Talk calls into them (`get_memory_block`, `todos_service`, job
  enqueueing) to confirm it reuses those seams correctly rather than
  duplicating them, which it does.
