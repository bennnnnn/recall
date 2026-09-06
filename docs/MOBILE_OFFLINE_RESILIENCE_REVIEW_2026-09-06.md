# Recall — Mobile Network/Offline Resilience & Chat Draft Persistence Review (Sep 2026)

Scope: mobile-only (no web client exists yet). How the app detects connectivity
(`hooks/useNetworkStatus.ts`, `lib/networkProbe.ts`), what happens when a send is attempted
offline or fails mid-flight (`lib/offlineSendFeedback.ts`, `hooks/useChatSend.ts`,
`hooks/useChat.ts`), what happens to a partial reply on a mid-stream disconnect
(`lib/chatPartialStream.ts`, `lib/chat/chatMessageMerge.ts`, `hooks/useChatRouteLoader.ts`), and
per-chat/per-account composer draft isolation (`lib/chat/composerThreadDraft.ts`,
`contexts/ComposerDraftContext.tsx`, `hooks/useChatDraftWarmup.ts`, `hooks/useDraftChat.ts`).
Round 4 of the cross-domain series; round 1–3 findings (`docs/CROSS_DOMAIN_REVIEW_2026-09-05.md`)
are not re-litigated except where directly load-bearing (the server-side hard-disconnect
finalize/refund fix from that series turns out to be exactly the safety net this review's top
finding shows mobile cannot see).

Reviewed at `cursor/cross-domain-review-2026-09-05`. One finding (F1) is reproduced with a
standalone script outside the test suite, matching the bar set by the cancellation-safety and
background-jobs reviews; the rest are traced through the full call chain with file:line evidence
and, where a test exists, read closely to check whether it exercises the real production shape.

---

## A. Verdict

**The single most severe issue in this area is a cross-account privacy leak, not a lost-message
bug.** `ComposerDraftProvider` (`contexts/ComposerDraftContext.tsx`) is mounted once, as the
parent of the `if (!token) return <Redirect href="/login" />` check in `app/index.tsx`, so it is
**never unmounted across sign-out → sign-in** — confirmed by reading the actual render tree, not
inferred. `lib/signOutCleanup.ts`'s `clearSignedOutAccount` clears eleven other per-account
caches (attachments, todos, reminders, message cache, memory/gallery/integration/usage caches,
RevenueCat) but never touches composer draft state. Because the New Chat composer slot is a
single shared key (`COMPOSER_NEW_THREAD_KEY = "new"`) used by *every* account, and because
`switchThread`'s same-key guard skips restoring text whenever the outgoing and incoming thread
key are identical, an account that lands back on New Chat after any sign-in (the default
post-login destination — `login.tsx:77` unconditionally redirects to `/`) inherits whatever
unsent text the *previous* account left in the box. **This is reproduced in this review with a
standalone script (§C, F1) that models the exact algorithm and shows Account B's composer
displaying Account A's un-sent draft verbatim.**

**The second and third findings are both instances of the same architectural seam**: `useChat`
owns the wire (confirmed correct and intentional by the Aug 2026 review), `useChatSend` owns
composer intent, and — as that review noted approvingly — there is no "send split across N hooks
with no owner" problem for the *happy* path. But the boundary between them has a real gap for the
*unhappy* path: once `useChatSend.handleSend` calls `sendMessage()`, it fully relinquishes the
optimistic user bubble and the cleared composer text to `useChat`, trusting either a normal
`done`/`error` event or an explicit server-side `rejectedSend` (`busy` / `attachment_rejected`) to
close the loop. **A genuine client-side network failure — the WebSocket handshake timing out and
the SSE fallback's `fetch` throwing, or a mid-stream disconnect while the app stays
foregrounded — is not one of those closed loops.** Neither `useChat`'s `disconnect()` handler nor
`sendViaSse`'s catch block ever touches the user's optimistic bubble; only the assistant
`"streaming"` placeholder is reconciled. The result: a message that never reached the server
settles into what looks like an ordinary, permanently-sent bubble, with its text already gone
from the composer and no retry affordance — and, for the mid-stream case, the *only* visible
recovery action (Regenerate) actively discards a correct, already-persisted answer (the server's
own hard-disconnect finalize path, confirmed still in place per `FEATURES.md:102-107` and
`services/chat/stream_entry.py`) and pays for a brand-new LLM call to produce a possibly-different
one.

**Everything upstream of these two gaps is solid.** The offline-*before*-send path (banner +
toast + preserved draft), the WS/SSE transport fallback and its 1.5s WS timeout, the explicit
server-rejection retry queue (`rejectedSend`), the app-backgrounding-mid-stream foreground
recovery path, and the connectivity probe's three-state classification (`online` /
`api_unreachable` / `no_internet`) are all correctly designed and, in most cases, already
defended by a version/session-guard idiom this codebase uses consistently elsewhere. The gaps are
narrow, precisely located, and — like round 3's `except Exception`/`except BaseException`
finding — instances of a *pattern already solved correctly elsewhere in this exact codebase*
(`lib/pendingComposerAttachment.ts` already session-guards its module-level state the way
`ComposerDraftContext` should) not solved consistently everywhere it's needed.

---

## B. What's working (don't "fix" these)

- **Pre-send offline detection is correct and has a clear, non-blocking UI.** `useNetworkStatus`
  (`hooks/useNetworkStatus.ts:21-84`) drives a persistent `OfflineBanner`
  (`components/OfflineBanner.tsx:14-31`, gated on `status !== "online"`) plus a per-tap toast
  (`lib/offlineSendFeedback.ts:5-11`, wired from `useChatSend.ts:270-278`). The draft is never
  touched — `handleSend` returns before `setInput("")` runs — so a user who is genuinely offline
  when they tap Send never loses their text, sees a clear banner, and gets haptic + toast
  feedback. This is exactly the "clear, correct UI state" the review asked whether this codebase
  has, and it does, for this specific case.
- **The three-state connectivity classifier is a real captive-portal-aware design, not just an
  `isConnected` check.** `resolveConnectivity` (`lib/networkProbe.ts:57-75`) races the app's own
  `/health` against a public `generate_204` target and picks `online` only if the API itself
  answers, `api_unreachable` if the API is down but the internet isn't, `no_internet` otherwise
  (`classifyConnectivity`, `:47-51`). `/health` is deliberately decoupled from Postgres/Redis on
  the server (`routers/health.py:10-13`, docstring: *"Do not couple this to Redis or Postgres"*),
  and the API's Fly machine runs with `auto_stop_machines = false` / `min_machines_running = 1`
  (`fly.toml:29-31`) — so the "Neon cold-start looks like `api_unreachable`" failure mode this
  review specifically went looking for (Q4) **does not exist**: traced fully, not a finding.
- **The offline poll loop is race-free and correctly bounded.** `useNetworkStatus`'s degraded-state
  polling effect (`:61-81`) guards against overlap with a `probeInFlight` flag, clears its interval
  and sets `cancelled` on unmount/status change, and every `NetInfo`/`AppState` subscription in the
  file is unsubscribed in the effect's cleanup (`:52-56`). No leak, no unbounded retry loop.
- **App-backgrounded-mid-stream recovery is a real, tested mechanism**, distinct from the
  foreground gap this review flags below: `useChatRouteLoader`'s `AppState` listener
  (`hooks/useChatRouteLoader.ts:276-334`) sets `wasStreamingWhenBackgroundedRef` when the app is
  backgrounded while streaming, then forces a TTL-bypassing silent refetch
  (`shouldForceForegroundChatRecovery`, `lib/chat/chatForegroundRefetch.ts:43-47`) on return to
  foreground — specifically so a truncated local bubble left by a backgrounding-killed socket gets
  replaced with the server's authoritative content.
- **Explicit server-side rejections have a real, tested recovery queue.** `rejectedSend` /
  `retryRejectedSend` (`hooks/useChat.ts:367-425, 839-864`) correctly distinguishes `busy` (retry
  the same content) from `attachment_rejected` (restore text + attachment, dropping the rejected
  reference id), queues per-chat, and survives navigation until explicitly retried or dropped. This
  is the *right* shape for send-failure recovery — the gap (F2 below) is that it only fires for
  explicit server rejections, never for a client-side network failure.
- **Fast-navigation races around chat loading are well-guarded.** Every async loader in
  `useChatRouteLoader.ts` and `useChatSend.ts` checks a `(session, version)` pair before applying
  its result (`isCurrent()` / `isCurrentView()`), and `hooks/__tests__/useChatRouteLoader.test.tsx`'s
  "chat history navigation races" suite exercises exactly the "navigate away and back before the
  request resolves" shape for both older-page pagination and the initial load — this review did
  not find a gap here (see §D, "considered, not a finding").
- **`lib/pendingComposerAttachment.ts` is the sibling implementation that gets session-scoping
  right**: `takeQueuedComposerAttachment` (`:13-19`) explicitly discards a queued Library pick if
  `queued.session !== getSessionGeneration()`. This is the exact guard `ComposerDraftContext` is
  missing (F1) — proof the pattern is known and used elsewhere in this file's own neighborhood, not
  a novel ask.
- **Per-thread draft isolation is correct *within* a signed-in session.** `takeThreadDraft` /
  `adoptNewComposerThread` / `stashFailedSendDraft` (`lib/chat/composerThreadDraft.ts:12-64`) are
  pure, well-tested (`lib/__tests__/composerThreadDraft.test.ts`), and correctly handle the "New
  Chat gets a real id mid-create" and "a rejected send must not clobber a newer draft" cases. The
  round-1 Live-Talk-style chat-switch leak (C2: switching chats while state from the old chat is
  still in flight) does **not** recur here for same-account chat-to-chat switches — see §D.

---

## C. Findings — ranked

### Privacy / cross-account isolation

---

**F1 — Composer draft text is never cleared on sign-out: the next account to sign in on the same
device inherits the previous account's unsent New Chat draft**
**Severity:** P0 · **Area:** mobile-privacy · **Effort:** S

**Evidence:**

- `app/index.tsx:627-635`: `HomeScreen` renders `<ComposerDraftProvider><ChatScreen /></ComposerDraftProvider>`
  unconditionally. The `if (!token) return <Redirect href="/login" />` early return
  (`app/index.tsx:588`) lives *inside* `ChatScreen`, i.e. strictly below
  `ComposerDraftProvider` in the tree — so signing out never unmounts the provider, and its
  `useState`/`useRef` state (`contexts/ComposerDraftContext.tsx:38-42`: `input`, `draftsRef`,
  `threadKeyRef`) survives the entire sign-out → sign-in cycle untouched.
- `app/login.tsx:77`: `if (token) return <Redirect href="/" />` — every successful sign-in lands on
  `/` with no `chatId` param, i.e. `composerThreadKey(undefined) === COMPOSER_NEW_THREAD_KEY`
  (`lib/chat/composerThreadDraft.ts:4-10`) for literally every account, every time. The New Chat
  slot is not an edge case here — it is the universal post-login landing state.
- `lib/signOutCleanup.ts:1-24`, `clearSignedOutAccount`: clears attachment file cache, todo
  reminders, reminder-lead prefs, cached chat messages, memory/gallery/integration-status/
  suggested-reminders/chat-list/usage caches, and signs out of RevenueCat and Google — eleven
  distinct per-account caches — with **zero** reference to `ComposerDraftContext`, `draftsRef`, or
  composer `input` anywhere in the file (grep-confirmed).
- `contexts/ComposerDraftContext.tsx:48-59`, `switchThread`: `if (fromKey === nextKey) return;`
  runs *before* `setInput` is ever called. `hooks/useChatSend.ts:187-201`'s `useLayoutEffect` does
  call `switchThread(composerThread)` on every session change (there is explicit `accountChanged`
  handling right below it for `pendingAttachment`/`sendPhase`/sheets — the author clearly intended
  to reset per-account composer state here), but because `fromKey` (`getThreadKey()`, still `"new"`
  from the previous account) equals `nextKey` (`"new"` again for the new account), the early return
  fires and `setInput` is **never invoked** — the reset that was clearly intended for this exact
  moment silently no-ops for the one piece of state (the typed text) that matters most.
- **Reproduced standalone** (no repo code modified; the algorithm is copied verbatim from the two
  files above into an isolated script, matching the bar set by round 3's `SIGTERM`/ack-on-cancel
  reproductions):

  ```
  Account A composer shows: "Account A secret draft: my SSN is 123-45-6789"
  Account B composer shows: "Account A secret draft: my SSN is 123-45-6789"
  REPRODUCED: Account B sees Account A's unsent draft text.
  ```

  The script (`/tmp/repro_draft_leak.mjs` during this review, not committed) instantiates the same
  `takeThreadDraft`/`switchThread` shape, types a draft as "Account A," simulates the sign-out (no
  clear call — matching `clearSignedOutAccount`'s real omission) and sign-in as "Account B" landing
  on the same `"new"` thread key, and shows the leaked text verbatim.
- **Contrast with the sibling that gets this right:** `lib/pendingComposerAttachment.ts:13-15`
  explicitly discards a queued attachment when `queued.session !== getSessionGeneration()`. The
  session-scoping idiom this bug needs already exists in the same directory, applied to a
  *different* piece of composer state, one file away.

**Why it matters:** Recall explicitly supports multiple accounts signing in and out on the same
device (this is the review's own stated framing, and `clearSignedOutAccount`'s eleven-cache sweep
confirms the product treats account switching as a first-class, security-sensitive event). A
composer draft is free-form text the user has *not yet chosen to send* — by definition the
category of content most likely to contain something the user reconsidered, or something sensitive
typed and abandoned (a health question, a financial detail, a message about another person). On a
shared or handed-down device, the very next person to sign in sees it, unprompted, before typing
anything themselves. This is a straightforward, high-confidence, always-reproducible privacy bug,
not a theoretical one — it fires on the default path (New Chat) taken by every sign-in.

**Recommended fix:** give `ComposerDraftContext` the same session-scoping idiom
`pendingComposerAttachment.ts` already uses. Concretely, add a `resetForNewSession()` method to
`ComposerDraftApi` that clears `draftsRef.current`, resets `threadKeyRef.current` to
`COMPOSER_NEW_THREAD_KEY`, and calls `setInput("")` unconditionally (bypassing `switchThread`'s
same-key guard) — then call it from `useChatSend.ts`'s existing `accountChanged` branch
(`:190-201`), which already has the session-transition detected and already resets every other
piece of per-account composer state right next to where this fix belongs. Symmetrically, call the
same reset (or an equivalent) from `AuthContext.signOut` / `clearSignedOutAccount` so the leak is
closed the instant the outgoing account signs out, not merely papered over the instant the next
account signs in (defense in depth: the two call sites are cheap and independent).

**Do not:** persist composer drafts to disk as a "fix" for anything else in this area (see F2/F3)
without first ensuring the persisted store is itself session-scoped and wiped on sign-out — adding
durable storage on top of the current unscoped in-memory design would turn this from a same-device,
same-session leak into a leak that survives an app restart too.

---

### Send-failure / mid-stream disconnect recovery

---

**F2 — A message that fails to send due to a genuine client-side network failure (not a server
rejection) settles into a permanent, unmarked, unretryable "sent" bubble; the composer text is
already gone and cannot be recovered**
**Severity:** P1 · **Area:** mobile-chat-resilience · **Effort:** M

**Evidence:**

- `hooks/useChatSend.ts:350-361`: on Send, `handleSend` immediately clears the composer
  (`setInput("")`, `:346`) and inserts an optimistic user bubble with id `local-${Date.now()}`
  directly into `messages`. It then calls `sendMessage(pending.text, pending)` with
  `skipUserBubble: true` (`lib/chat/chatSendLogic.ts:67,81` — `buildPendingSendAfterCreate` always
  sets this) and does **not** await or inspect the result — `sendMessage`'s type is `(text, opts) =>
  void` (`hooks/useChatSend.ts:52-66`).
- `hooks/useChat.ts:723-834`, `dispatchSend`: for a genuine network failure, the sequence is
  `ensureConnected()` (never rejects — `connect()`'s executor always calls `resolve()`, even on
  handshake timeout, `:479-486`) → WS not open within 1.5s (`WS_CONNECT_TIMEOUT_MS`,
  `lib/chatWsConnect.ts:7`) → falls back to `sendViaSse` (`:805-811`), which performs the actual
  network I/O via `requestSse`/`fetch` (`lib/chatSse.ts:38-94`, `lib/api/client.ts:157-201`).
- `hooks/useChat.ts:644-656`, `sendViaSse`'s catch block: on a thrown fetch error (real network
  failure, not an abort), it clears `streaming`/`finalizing`, calls `preservePartialStream()` or
  `clearStreamingBubble()` (both operate **only** on the message with `id === "streaming"`, i.e.
  the assistant placeholder), and calls `reportError(t("chat.error_unreachable"))`. **No code path
  in this function ever filters, marks, or removes the user's `local-...` message.** The same is
  true of the WS-path equivalent, `disconnect()` (`:504-553`): it reconciles or removes the
  `"streaming"` assistant bubble and nothing else.
- `lib/chatMessageLogic.ts:9-17`, `findLastLocalUserMessageId`: a helper that finds "the latest
  optimistic user message" — exactly the lookup a failure-recovery path would need to locate and
  mark/remove the stranded bubble — is defined, unit-tested
  (`lib/__tests__/chatMessageLogic.test.ts:25-35`), and **has zero call sites anywhere in
  production code** (grep-confirmed across `apps/mobile`, excluding its own definition and test).
  This is the same "a fix/mechanism exists but was never wired in" shape round 3 found for
  `heal_usage_drift` (Model Routing Q2) — a different subsystem, same pattern.
- **Compounding: the hook's own unit tests exercise a message-ownership shape production never
  uses.** Every real caller of `sendMessage` passes `skipUserBubble: true`
  (`hooks/useChatSend.ts:241-252, 455-464`, both via `buildPendingSendAfterCreate`, which
  hard-codes `skipUserBubble: true` at `lib/chat/chatSendLogic.ts:67`) — grep-confirmed, this is
  the *only* production call shape. Yet 24 of the ~26 `sendMessage(...)` calls in
  `hooks/__tests__/useChat.test.tsx` (including the disconnect-focused
  `"preserves partial content on a socket error followed by close"` test, `:130-140`) call it with
  no options or without `skipUserBubble: true`, which exercises `dispatchSend`'s *own* internal
  bubble-insertion branch (`hooks/useChat.ts:741-758`, `if (!options?.skipUserBubble)`) — a branch
  that is **dead in production**. Only one test (`:443-444`, an attachment-specific case) uses the
  real shape. This means the suite's disconnect/error tests give the appearance of covering "what
  happens to the user's message on a socket failure" while actually testing a code path real users
  never hit — the same "tests exercise the wrong code path" class flagged in the Push and
  Background Jobs reviews, recurring here in a third subsystem. It does not, by itself, hide a
  *different* bug: this review confirmed that neither shape's user bubble is ever cleaned up on
  failure, so the mismatch doesn't mask a "the real path is fine" false negative — but it does mean
  a future regression in the real path could land with every one of these tests still green.

**Why it matters:** a network blip that lands during the ~1.5s WS-timeout-to-SSE-fallback window,
or any time during the SSE fetch itself, is not a rare event on a cellular connection (elevator,
tunnel, wifi↔cellular handoff, weak signal). When it happens: the user's typed text is already gone
from the composer (cleared optimistically at send time), the message they typed never reached the
server, and the bubble that represents it sits in the transcript indistinguishable from a
successfully delivered message — no error glyph, no retry button, no "tap to resend." The only
visible signal is a transient toast (`chat.error_unreachable`) that says nothing about *which*
message failed. The existing `rejectedSend`/`retryRejectedSend` machinery
(`hooks/useChat.ts:367-425, 839-864`) was clearly built to solve exactly this class of problem —
it is well-designed and well-tested — but it only activates for explicit server-side rejection
codes (`busy`, `attachment_rejected`), never for a client-side connection failure that never
reached the server at all.

**Recommended fix:** in both `sendViaSse`'s catch block and `disconnect()`'s no-content branch,
call `findLastLocalUserMessageId(messagesRef.current)` (now that it has a real caller) to locate
the stranded optimistic bubble and either (a) remove it and restore its text into the composer —
mirroring `useChatSend.ts`'s existing `restoreDraft()` pattern, which already does exactly this for
the pre-send failure cases (attachment upload, chat creation) — by exposing a callback `useChat`
can invoke, or (b) mark it with a `sendFailed: true` flag (parallel to the existing
`generationStopped` flag) and render a small inline "Failed to send · Retry" affordance on that
specific bubble, wired to resend just that message's content. Option (a) is the smaller change and
matches the codebase's existing "keep the draft, no queue yet" philosophy
(`lib/offlineSendFeedback.ts:1-4`); option (b) is more correct long-term (it also naturally covers
"the request may have actually reached the server, we just didn't hear back" ambiguity, which (a)
does not). Either way, wire `findLastLocalUserMessageId` up — a tested helper with no caller is a
strong signal this was already scoped and simply not finished.

**Do not:** try to solve this by increasing `WS_CONNECT_TIMEOUT_MS` or adding automatic silent
retries inside `dispatchSend`/`sendViaSse` — a blind retry on an ambiguous failure (request may or
may not have reached the server) risks duplicate sends, the opposite failure mode this review was
also asked to check for. Surface the failure and let the user decide, the same way `rejectedSend`
already does for server-side rejections.

---

**F3 — No automatic recovery when the network drops mid-stream while the app stays in the
foreground; the only visible affordance (Regenerate) discards a correct, already-persisted answer
and burns a duplicate LLM call**
**Severity:** P1 · **Area:** mobile-chat-resilience · **Effort:** M

**Evidence:**

- `hooks/useChat.ts:504-553`, `disconnect()` (fires on `ws.onclose`/`ws.onerror`): when there is
  partial content, it commits the streaming bubble in place as `streamed-${Date.now()}` with
  `generationStopped: true` (`:537-547`) — a purely local id, never reconciled against the server's
  real message id, because reconciliation only happens if the server's `done` event later arrives
  **over the same socket** (`lib/chatSocketReduce.ts:117-144`, `mergeDoneIntoMessages`'s
  `stoppedStreamedId` branch) — and a closed socket will never deliver that event. The SSE
  equivalent (`hooks/useChat.ts:644-656`) has the identical shape.
- The only mechanisms that ever silently re-fetch the authoritative server content for the open
  chat are: (1) the app-backgrounding recovery path (`hooks/useChatRouteLoader.ts:276-334`,
  requires an actual `background`/`inactive` → `active` `AppState` transition — see "what's
  working"), and (2) leaving the chat and returning, which re-runs the full non-silent load effect
  (`hooks/useChatRouteLoader.ts:340-441`, keyed on `routeChatId` changing). **Neither fires when the
  network drops mid-stream and the app simply stays open on the same chat** — the ordinary shape of
  a brief connectivity blip that doesn't coincide with backgrounding.
- `lib/chat/chatForegroundRefetch.ts:25-27`, `shouldSilentRefetchChatOnFocus`: hard-coded to always
  return `false`, by design (comment: *"Back from Lists / Learning / Reminders must not reload the
  thread"*) — this is a deliberate, documented choice for a different scenario (avoiding UI churn
  on tab-focus), but it also means there is no focus-based fallback for this case either.
  `app/index.tsx` has no pull-to-refresh on the message list (grep-confirmed: no `onRefresh` /
  `RefreshControl` in the chat screen).
- `components/MessageBubble.tsx:451-453`: a `generationStopped` message shows only a static
  `"Generation stopped."` footer — no "reload the full reply" action.
  `components/MessageBubble.tsx:498` (`onRegenerate={isLastAssistant ? onRegenerate : undefined}`)
  shows the Regenerate button for the last assistant message unconditionally, **not gated on
  whether that message is actually incomplete** — a user has no way to distinguish "this really was
  cut off, regenerating is reasonable" from "this looks cut off locally but the server actually
  finished it fine."
- `apps/api/app/services/chat/stream_entry.py:317-334`, `stream_regenerate_response`: fetches
  `messages_repo.get_last(session, chat_id)` — the real, currently-persisted last row — and, if it
  is an assistant message, treats it as `regenerate_backup` and replaces it with a fresh generation.
  Per this series' own round 3 finding (S1, now fixed) and `FEATURES.md:102-107` ("Hard WS/SSE
  disconnect with tokens already streamed also finalizes"), the server's hard-disconnect path
  **does** persist the full, correct answer that was generated up to that point — so `get_last`
  returns the *correct, complete* answer in exactly the scenario this finding describes. Tapping
  Regenerate therefore discards a real, already-paid-for answer and generates a new one in its
  place, purely because the mobile client never learned the first one had, in fact, succeeded.
- No test in `hooks/__tests__/useChat.test.tsx` or `hooks/__tests__/useChatRouteLoader.test.tsx`
  covers "WS/SSE fails while the app stays foregrounded, then the network recovers" — the closest
  test, `"preserves partial content on a socket error followed by close"`
  (`useChat.test.tsx:130-140`), only asserts the local partial is kept; it does not assert (because
  there is nothing to assert) that anything later reconciles it against the server.

**Why it matters:** this is the mobile-side counterpart to the server-side safety net this review
series already confirmed exists (round 3's cancellation-safety work). The backend correctly
finalizes and persists the true answer on a hard disconnect — but that correctness is invisible to
the user whenever the disconnect happens without a backgrounding event, which is the common case
for a short cellular blip. The user is left staring at a truncated reply with exactly one
actionable button, and that button's effect is to throw away the real answer and spend a second LLM
call (and, per the quota system reviewed in round 3, real per-user daily token budget) to produce a
possibly-different one — at the worst possible moment (right after their connection just glitched).

**Recommended fix:** the smallest correct fix is architectural, not a new subsystem: extend the
same signal `disconnect()`/`sendViaSse`'s catch already computes (`hadContent` / a caught network
error with tokens already streamed) to trigger a `silentRefetchChat` call for the current chat,
exactly the way the `AppState` background→foreground handler already does via
`shouldForceForegroundChatRecovery`'s `force: true` path — i.e., treat "the socket died with
content already streamed" as its own trigger for the *existing* forced-refetch mechanism, not just
a distinct code path with different consequences depending on the timing of an unrelated OS event.
Once wired, that refetch will pull the server's already-finalized real answer (or, if the server
turn is still finishing, retry again shortly) and replace the local `streamed-...` placeholder
before the user ever needs to consider Regenerate. As a smaller, purely-defensive complement, gate
the Regenerate button's copy/confirmation on `generationStopped` (e.g. a brief "this may already be
complete — refreshing…" state while the silent refetch is in flight) rather than presenting it as
an unconditional, no-cost action.

**Do not:** try to solve this by keeping the WebSocket "alive" longer (increasing timeouts, adding
raw reconnect-and-resume at the protocol level) — there is no way to resume a specific in-flight
turn once its connection is gone (the server has no notion of "reattach to turn X"), and the
correct answer already exists safely in the database; the fix is entirely about *retrieving* it,
not about preventing the disconnect in the first place.

---

### State-machine hygiene (minor)

---

**F4 — `wasStreamingWhenBackgroundedRef` is only reset inside the branch it enables, so a
foreground event that fails the recovery gate (still streaming / still loading) leaves a stale
`true` that force-bypasses the freshness cache on a later, unrelated foreground event**
**Severity:** P3 · **Area:** mobile-chat-resilience · **Effort:** S

**Evidence:**

- `hooks/useChatRouteLoader.ts:276-334`: on `background`/`inactive`, `wasStreamingWhenBackgroundedRef.current`
  is set `true` if streaming or image-generating (`:280-283`). On the next `active` transition, the
  reset to `false` (`:314`) only happens **after** the early-return guard
  (`!openChatId || !shouldRefetchChatOnForeground(...)`, `:298-310`) has already passed. If that
  gate fails — e.g. the app is foregrounded while the turn is *still* streaming
  (`streamingRef.current` still `true`, a real possibility since backgrounding doesn't
  synchronously kill the socket) or while `chatLoading` is `true` — the function returns at
  `:309-310` and the flag is never cleared.
- Consequence: the next time the app backgrounds/foregrounds for any unrelated reason (even much
  later, with no streaming involved at all), `shouldForceForegroundChatRecovery`
  (`lib/chat/chatForegroundRefetch.ts:43-47`) will still see `wasStreamingWhenBackgrounded: true`
  and force a TTL-bypassing refetch that wasn't warranted.

**Why it matters:** this is a stale-flag bug, not a data-loss bug — the consequence is a spurious
extra `GET /chats/{id}` + `GET .../messages` round-trip on some later, unrelated foreground event,
not corruption or a UI-visible symptom. Low severity, but it is exactly the "missing cleanup on an
early-return branch" shape the review was asked to check for, and it is a two-line fix.

**Recommended fix:** reset `wasStreamingWhenBackgroundedRef.current = false` unconditionally at the
top of the `active` branch, before the `shouldRefetchChatOnForeground` gate is evaluated, and pass
the already-read value into the gate/force computation as a local rather than reading the ref
twice.

**Do not:** treat this as urgent or bundle it with F1–F3 — it's an isolated, low-blast-radius
cleanup, independently shippable.

---

## D. Swept and clean / considered, not a finding

Recorded because each looked like a plausible candidate before being traced through fully:

- **"Neon cold-start looks like `api_unreachable`" (Q4 false-positive candidate).** Traced fully:
  `/health` is deliberately decoupled from Postgres/Redis (`routers/health.py:10-13`), and the
  API's Fly machine is configured with `min_machines_running = 1` / `auto_stop_machines = false`
  (`fly.toml:29-31`), so there is no scale-to-zero wake delay on the endpoint the probe hits. Not
  reachable in this codebase's actual deployment config.
- **`generate_204`'s target being blocked in some regions (e.g. behind the Great Firewall) causing
  a mislabeled banner.** Traced: `classifyConnectivity` (`lib/networkProbe.ts:47-51`) already
  returns `online` whenever the API itself is reachable, regardless of the public-reachability
  result — the public check only disambiguates the *label* (`api_unreachable` vs `no_internet`)
  when the API is *also* down, and both labels correctly gate `isOffline` identically
  (`useNetworkStatus.ts:83`). Worst case is a cosmetic wording difference on an already-broken
  connection, not a functional gap. Not worth a fix on its own.
- **Same-account chat-to-chat draft leakage (the round-1 Live-Talk C2 pattern, re-checked here).**
  `takeThreadDraft`/`adoptNewComposerThread` (`lib/chat/composerThreadDraft.ts:12-40`) key
  correctly off real, server-issued chat UUIDs for every existing chat, and
  `useChatSend.ts:187-201`'s effect correctly detects `composerThread` changes and saves/restores
  per-key text via `switchThread` on every route change. The only shared/colliding key in the whole
  scheme is the single `"new"` sentinel — which is *intentionally* shared within one account (it is
  the documented "New Chat slot," `FEATURES.md:108-110`) and only becomes a bug when it is also,
  unintentionally, shared *across accounts* (F1). Normal same-account chat switching does not leak.
- **Draft-warmup / fast-navigation races (Q5).** Every async operation that could race a fast
  "type → navigate away → navigate back" sequence (`prepareDraftChat` in `useChatSend.ts:411-454`,
  the full chat load effect in `useChatRouteLoader.ts:340-441`, older-page pagination) is guarded by
  a `(session, version)` pair checked via `isCurrentView()`/`isCurrent()` before any state mutation,
  and `hooks/__tests__/useChatRouteLoader.test.tsx`'s "chat history navigation races" suite
  specifically exercises this shape and passes. `useChatDraftWarmup` itself
  (`hooks/useChatDraftWarmup.ts:13-24`) is a thin, idempotent `connect()` call gated by
  `shouldWarmDraftSocket` (`lib/chatDraftLogic.ts:66-78`) with no state of its own to race.
- **Indefinite silent hang on a fully "black-holed" connection (packets stop flowing in both
  directions with no FIN/RST — common on cellular NAT after several minutes idle) with no
  application-level heartbeat.** Confirmed there is no ping/pong or inactivity timeout on either
  transport (`hooks/useChat.ts`, `lib/chatSse.ts`) beyond the 30s *connection-setup* timeout that is
  explicitly cleared once headers/handshake complete (`lib/api/client.ts:195-200`, matching the
  auth-session review's documented fix for "Stop disconnected after headers"). This means a
  worst-case dead connection can leave `streaming: true` indefinitely with no automatic recovery —
  but the existing Stop button (`stopGeneration`, `hooks/useChat.ts:928-980`) already recovers the
  UI unconditionally and client-side regardless of whether the cancel frame reaches a dead server,
  so this degrades to "the user must notice and tap Stop" rather than a true dead end. Noted as a
  minor, pre-existing UX gap (no auto-detection), not logged as a numbered finding given the
  existing manual escape hatch and the added complexity a heartbeat protocol would introduce for a
  rare failure mode.
- **`ComposerDraftProvider`'s `draftsRef` Map growing unboundedly across many distinct chats
  visited in one app session.** Real, but bounded by the number of distinct chats a user opens
  before an app restart (each entry is one short string), never persisted to disk, and reset on
  every cold start. Not worth a numbered finding on its own; if F1's fix adds a `resetForNewSession`
  path, consider pruning entries for chats no longer in the drawer list at the same time, but this
  is optional hygiene, not a correctness issue.

---

## E. Weak / unwanted / missing inventory

| Item | Status | Evidence | Recommend |
|---|---|---|---|
| Composer draft session-scoping | **Missing** | `ComposerDraftContext.tsx` has no session/account awareness; `signOutCleanup.ts` never references it | Fix urgently (F1) |
| Optimistic user bubble on send-time network failure | **Broken** (silently stranded, unmarked, text lost) | `useChat.ts:644-656, 504-553`; `findLastLocalUserMessageId` dead code | Fix (F2) |
| `useChat.test.tsx` `sendMessage` call shape vs. production | **Mismatched** (tests a dead branch) | `useChat.ts:741-758` vs. `useChatSend.ts:241-252,455-464` | Add tests using `skipUserBubble: true` alongside the F2 fix |
| Foreground mid-stream disconnect recovery | **Missing** | `chatForegroundRefetch.ts:25-27` (focus refetch off by design), no network-triggered refetch | Fix (F3) |
| `wasStreamingWhenBackgroundedRef` reset-on-early-return | **Weak** (stale flag) | `useChatRouteLoader.ts:298-314` | Fix (F4) |
| Pre-send offline UX (banner/toast/preserved draft) | **Solid** | `useNetworkStatus.ts`, `offlineSendFeedback.ts`, `useChatSend.ts:270-278` | Keep as-is |
| Three-state connectivity probe (`online`/`api_unreachable`/`no_internet`) | **Solid** | `networkProbe.ts:47-75`; `fly.toml:29-31`; `routers/health.py:10-13` | Keep as-is |
| App-backgrounded-mid-stream recovery | **Solid, tested** | `useChatRouteLoader.ts:276-334` | Keep as-is (feeds F3's fix) |
| Explicit server-rejection retry queue (`rejectedSend`) | **Solid, tested** | `useChat.ts:367-425,839-864` | Keep as-is; extend pattern to cover F2 |
| Same-account chat-switch draft isolation | **Solid** | `composerThreadDraft.ts`; `useChatSend.ts:187-201` | Keep as-is |
| Fast-navigation race guards (`isCurrentView`/`isCurrent`) | **Solid, tested** | `useChatRouteLoader.test.tsx` "chat history navigation races" | Keep as-is |
| `pendingComposerAttachment.ts` session-guard | **Solid** | `:13-15` | Model for F1's fix |
| Listener/timer cleanup (`useNetworkStatus`, `useChatRouteLoader`) | **Solid** | `useNetworkStatus.ts:52-56,77-80`; `todoSyncTimersRef` cleanup | Keep as-is |
| Application-level stream heartbeat / inactivity auto-recovery | **Absent, low priority** | No ping/pong on WS or SSE; Stop is a manual escape hatch | Optional future hardening, not urgent |
| `draftsRef` Map pruning | **Absent, cosmetic** | Never deleted from; bounded by session length | Optional, bundle with F1 if convenient |

---

## F. Sequenced fix plan

One concern per PR, matching this codebase's own execution discipline.

1. **`fix(mobile): reset composer draft state on account change`** — F1. Highest priority: a
   privacy leak with a two-call-site, low-risk fix (add `resetForNewSession()` to
   `ComposerDraftApi`, call it from `useChatSend.ts`'s existing `accountChanged` branch and from
   `AuthContext.signOut`/`clearSignedOutAccount` for defense in depth).
2. **`fix(mobile): recover the optimistic user bubble on a send-time network failure`** — F2. Wire
   `findLastLocalUserMessageId` into `sendViaSse`'s catch and `disconnect()`'s no-content path;
   restore the composer text (or mark the bubble failed with a retry action). Add tests using the
   real `skipUserBubble: true` production shape.
3. **`fix(mobile): silently refetch the chat when the socket dies mid-stream while foregrounded`**
   — F3. Reuse the existing forced-refetch mechanism the backgrounding path already has; gate
   Regenerate's presentation on whether a refetch is in flight.
4. **`fix(mobile): reset wasStreamingWhenBackgroundedRef unconditionally on foreground`** — F4.
   Small, independent, no dependency on 1–3.

---

## G. Explicit non-goals

- **No code was changed by this review; this is a pure audit.** The standalone reproduction script
  for F1 was written to `/tmp` for verification only and is not part of the repository.
- **Did not re-review the server-side chat-loop, quota, or cancellation-safety mechanics** — those
  are round 3's scope (`CANCELLATION_SAFETY_SWEEP_2026-09-06.md`,
  `MODEL_ROUTING_QUOTA_REVIEW_2026-09-06.md`); this review only relies on their confirmed
  conclusion (hard-disconnect finalize + refund is correct) as load-bearing context for F3.
- **Did not build or propose an offline send queue** (e.g. persisting unsent messages to retry
  automatically once connectivity returns). The current "keep the draft, no queue yet" design
  (`lib/offlineSendFeedback.ts:1-4`) is a documented, deliberate product choice for the
  before-send case; F2's fix is about correctly recovering from an *in-flight* failure, not about
  adding a durable outbox for the pre-send case, which is a larger product decision out of this
  review's scope.
- **Did not propose adding a WebSocket/SSE heartbeat protocol.** Noted in §D as a low-priority gap
  with an existing manual mitigation (Stop); a heartbeat is a meaningfully larger change (new
  server + client protocol surface) than this review's other findings and was not asked for.
- **Did not review the web client** — none exists yet, per the task framing; `lib/api.ts`'s
  barrel-boundary design is noted only where it's directly relevant to a finding's fix.
- **Did not re-litigate i18n, admin surfaces, or any of the eleven previously-reviewed domains**
  listed in `CROSS_DOMAIN_REVIEW_2026-09-05.md` except where their prior conclusions are directly
  load-bearing for a finding here (F3's reliance on the round-3-confirmed hard-disconnect finalize
  path).
