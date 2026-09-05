# Recall — Push Notification System Review (Sep 2026)

Scope: the push-notification **delivery mechanism** only — token lifecycle
(register/rebind/prune), the Expo send path, the cross-feature scheduler that
fans reminders/calendar/learning/email-suggestion pushes through it, retries,
idempotency, security, and mobile registration/permission/settings. The
recurrence/scheduling *business logic* for Schedule/todos is out of scope and
not re-litigated here.

Reviewed at `main` (`a6d0773e`, 30 commits of visible push-specific history).

---

## A. Verdict

**The send path itself is genuinely solid.** One funnel
(`_append_outbound` → `dispatch_expo` → `_finalize_push_deliveries` in
`apps/api/app/services/notifications/push.py`) is shared cleanly by all four
producers (todo reminders, email suggestions, learning nudges, calendar
nudges) — there is no per-feature copy of "call Expo" anywhere. Expo's
100-message batch cap is honored with per-chunk failure isolation
(`apps/api/app/gateways/expo_push_gateway.py:88-167`), `DeviceNotRegistered`
is correctly distinguished from `InvalidCredentials` so a misconfigured APNs/
FCM credential can't mass-delete every user's token (a real bug this codebase
already had and fixed, per the `_INVALID_TOKEN_ERRORS` comment), and the
receipt API is polled but explicitly kept out of the delivery-marking
decision — a common naive mistake this team already avoided on purpose (see
the module docstring). Cross-user token rebinding requires a matching
install `device_id`, is tested for all three branches, and the residual risk
is honestly written down in `FEATURES.md`, not hidden.

**The two things that would actually bite in production are both invisible
today because nothing tests the code path production runs.** First,
`background/push_scheduler.py`'s `_push_cycle` — the two-session
collect-then-dispatch-then-finalize function that is the *only* entry point
the worker ever calls — has exactly one test in the whole repo, and it
asserts a lock-TTL constant, not behavior. Every one of the ~15 `run_push_cycle`
tests in `test_push_notifications.py` exercises a single-session helper of
the same name that is a test-only artifact: production never calls it. That
is precisely the shape of the bug this project already shipped once (Redis
receipt/finalize split silently no-op'ing across sessions, fixed in #1017) —
and the fix landed in the code the tests exercise, not the code that runs.
Second, the calendar and learning nudge producers claim their Redis dedupe
key *before* the message is ever handed to Expo, and only release it on a
confirmed failure later in the same cycle. A worker crash between those two
points — the exact crash this codebase already treats as a first-class
concern in `stream.py`'s turn-resource lifecycle — doesn't duplicate the
notification (todos/suggestions/learning would); it **silently drops it**
until the dedupe key's TTL expires, which for a calendar nudge is routinely
after the meeting already happened.

**On mobile, the registration path is fire-and-forget in a way that actively
lies to the settings toggle.** `registerRemotePushToken` swallows every
failure — a rejected cross-user rebind (403), a missing EAS project id, an
Expo Go/Android environment, a network blip — and `settings/notifications.tsx`
calls `updateUser({ push_notifications_enabled: true })` regardless of whether
a token was ever actually registered. The user sees the toggle turn on and
gets nothing. This is the one finding in this review with a plausible path to
"why didn't I get reminded," and it has no test covering the failure branch.

Everything else — dedupe of duplicate tokens per device, multi-device
fan-out, the `push_notifications_enabled` flag gating every SQL query
directly (not relying on token absence), local/remote reminder
non-double-firing, Expo Go/web no-op safety — is either already correct or
already has a regression test guarding it.

---

## B. What's working (don't "fix" these)

- **One send funnel, no per-feature duplication.** `process_todo_reminders`,
  `process_email_suggestions`, `process_learning_nudges`, and
  `process_calendar_nudges` (`apps/api/app/services/notifications/push.py:238-506`)
  all terminate in the same `_append_outbound` → `collect_push_outbound` →
  `dispatch_expo` → `finalize_push_deliveries` pipeline
  (`push.py:581-653`). Item 5 in the review brief ("is the seam actually
  shared cleanly") — yes, cleanly, verified by reading all four producers.
- **Expo batching + per-chunk isolation is correct and tested.**
  `MAX_MESSAGES_PER_REQUEST = 100` (`expo_push_gateway.py:88`), chunked in
  `send_push_messages` (`:159-167`), with a transport failure on one chunk
  leaving only that chunk's messages unmarked
  (`test_send_push_messages_one_chunk_failure_does_not_affect_others`,
  `test_send_push_messages_chunks_over_100_messages`).
- **`InvalidCredentials` vs `DeviceNotRegistered` is deliberately
  distinguished** (`expo_push_gateway.py:16-21, 78-85, 127-134`) — a
  documented BUG FIX so a broken APNs/FCM credential (which would return the
  same error for every token) can't be mistaken for a fleet of dead devices
  and wipe every user's push token on the next cycle. Tested
  (`test_send_push_messages_survives_invalid_credentials_but_prunes_dead_device`).
- **Receipt polling is correctly kept off the delivery-marking critical
  path.** The module docstring (`push.py:1-9`) states the rule explicitly:
  ticket `status: ok` marks delivered; receipts are deferred
  (`RECEIPT_MIN_AGE_SECONDS = 15 * 60`) and used only to prune dead tokens.
  This is the right call — a slow/missing receipt never blocks marking or
  causes a resend.
- **Cross-user token rebind hardening does what `FEATURES.md` claims.**
  `push_tokens.upsert` (`apps/api/app/repositories/push_tokens.py:45-102`)
  requires a matching `device_id` to move an existing token to a different
  user (`:71-92`), all three branches are tested
  (`test_upsert_rejects_cross_user_rebind_without_device_id`,
  `..._with_mismatched_device`, `..._allows_..._with_matching_device`), and
  the residual risk ("attacker with both the token and the install id can
  still rebind") is written down in `FEATURES.md:756-760` rather than
  implied to be solved. Verified: this is exactly the risk the code has.
- **`push_notifications_enabled` gates every query directly, not token
  presence.** All four producers filter
  `User.push_notifications_enabled.is_(True)` in SQL
  (`push.py:254, 320, 387, 452`) — a stale/lingering `PushToken` row from a
  failed client-side unregister can never cause a send, because the flag is
  checked before tokens are even looked up.
- **Local vs. remote reminder double-fire is handled.**
  `shouldSyncLocalTodoReminders` (`apps/mobile/lib/todos/todoReminderPush.ts:19-23`)
  skips on-device scheduling while server push is on, and
  `PushNotificationBootstrap` cancels any matching local reminder the moment
  a remote push for the same todo arrives (`PushNotificationBootstrap.tsx:60-69`).
- **Expo Go / web are correctly no-op, not crashed.** `resolveExpoPushToken`
  (`pushNotifications.ts:52-61`) wraps `getExpoPushTokenAsync` in a catch-all
  that returns `null` — which is exactly what's needed, since Expo throws
  from that call on Android in Expo Go (SDK 53+ removed remote push there).
  Web is separately short-circuited (`Platform.OS === "web"` in both
  `registerRemotePushToken` and `PushNotificationBootstrap`), with a
  regression test for the specific crash this used to cause
  (`PushNotificationBootstrap.test.tsx` "BUG FIX regression: does not call
  the native-only response APIs on web").
- **Per-row failure isolation in every producer loop.** Each of the four
  `process_*` functions wraps its per-user (or per-todo) body in
  `try/except Exception: logger.exception(...); continue`
  (`push.py:277-301, 345-370, 412-428, 468-504`), each with a "BUG FIX (was
  cycle-fatal)" comment — this is a real, previously-shipped bug that is now
  guarded and tested (`test_process_learning_nudges_isolates_one_user_failure`).
- **Scheduler lock ownership is correct.** `acquire_lock`/`release_lock`/
  `refresh_lock` (`apps/api/app/core/redis_lock.py`) use a random token +
  Lua compare-and-delete/compare-and-expire, so a slow holder that outlives
  its TTL cannot have its lock stolen-then-released by a second instance.
  `LOCK_TTL_SECONDS` (600s) is asserted `> INTERVAL_SECONDS` (60s)
  (`test_push_scheduler.py`), matching the documented "hold longer than one
  interval" convention in `background/periodic.py:42-44`.
- **Multi-device fan-out and per-device dedupe both work.**
  `push_repo.list_for_users` returns every token for a user across devices;
  `_append_outbound` dedupes by exact token string within one call
  (`push.py:216-220`, tested by `test_append_outbound_dedupes_duplicate_tokens`);
  and a calendar dedupe key is only released if *every* device's send failed
  (`test_finalize_keeps_calendar_dedupe_when_any_device_succeeds`).
- **Cascade delete on account deletion.** `PushToken.user_id` is
  `ForeignKey("users.id", ondelete="CASCADE")`
  (`apps/api/app/models/orm/integrations.py:107-109`) — no orphaned tokens
  survive account deletion.
- **Payload content is minimal.** Bodies are todo content (the user's own
  text, truncated to 240 chars), sanitized/truncated email-suggestion
  titles (`_sanitize_email_suggestion_body`, `push.py:119-127`, cap 120
  chars, control-char stripped), and templated calendar/learning strings.
  Nothing pulls raw memory or LLM output into a push body.

---

## C. Findings — ranked

### Delivery reliability & test coverage

---

**PN1 — The production push-cycle body has one test, and it isn't a
behavior test; every `run_push_cycle` test exercises code production never
calls**
**Severity:** P1 · **Area:** api / tests · **Effort:** M

**Evidence:**
- Production worker path: `worker_main.py` → `process_bootstrap.start_worker_runtime`
  (`process_bootstrap.py:41-47`) → `push_scheduler.start_push_scheduler` →
  `run_locked_cycle` → **`push_scheduler._push_cycle`**
  (`apps/api/app/background/push_scheduler.py:27-56`). This is a
  two-session function: session A collects outbound and is released
  (`:31-34`) *before* the Expo network call (`:36-38`), then session B prunes
  invalid tokens, enqueues receipts, and finalizes (`:40-52`).
- `apps/api/app/tests/test_push_scheduler.py` is 7 lines and asserts
  `LOCK_TTL_SECONDS > INTERVAL_SECONDS`. It does not call `_push_cycle` or
  `run_push_cycle(settings)` at all.
- `apps/api/app/services/notifications/push.py:638-653` defines a
  **different** `run_push_cycle(session, redis, settings)` — a
  single-session helper, whose own docstring says "Single-session helper for
  tests; production uses collect → dispatch → finalize." Confirmed by
  `grep`: every call site of `push_service.run_push_cycle` is inside
  `test_push_notifications.py` (13 call sites); `background/push_scheduler.py`
  never imports or calls it.
- The ~13 tests that look like scheduler-behavior coverage
  (`test_run_push_cycle_marks_todo_sent_only_after_expo_ok`,
  `test_run_push_cycle_does_not_mark_todo_when_expo_fails`,
  `test_run_push_cycle_enqueues_receipt_tickets`, etc.) all call this
  test-only single-session function.

**Why it matters:** this project already shipped the exact bug class this
gap would hide. Commit `e3553906` ("Mark push deliveries on the finalize
session…") fixed a real production incident where "accepted Expo tickets
never flushed `notification_sent_at` across the two-session collect/finalize
split, so the same suggestion re-pushed every minute" — a bug that existed
*specifically* because production uses two sessions and the tests didn't.
The fix (now `_mark_todo_after_successful_push` using
`update_schedule_if_current`, `push.py:509-527`) is good and is exercised by
`run_push_cycle` tests — but `run_push_cycle` is not what runs the fix in
production. If a future change to `_push_cycle`'s session boundaries,
pruning order, or exception handling reintroduces a cross-session bug (e.g.,
someone "simplifies" it back to one session, or moves the invalid-token
prune before `finalize_push_deliveries` runs on a *different* session than
the one that loaded the rows), no test in the suite will catch it. This is
the single highest-leverage gap in the whole review because it is exactly
where the last real incident happened.

**Recommended fix:** add `apps/api/app/tests/test_push_scheduler.py` cases
that call `push_scheduler._push_cycle` directly (or `run_push_cycle(settings)`
through `run_locked_cycle`) with a fake Redis + two real/mocked
`SessionLocal` context managers, asserting: (a) the session used for
`collect_push_outbound` is closed before `dispatch_expo` is awaited (a mock
that raises if `session.execute` is called after `__aexit__`), (b) a todo
marked delivered in the collect session is actually flushed via the
finalize session, (c) invalid-token pruning and `finalize_push_deliveries`
both happen even when the collect session already returned an empty list
(early-return path, `_push_cycle:33-34`, currently untested).

**Do not:** rename or merge the two `run_push_cycle` functions in the same
PR — that's a separate, riskier cleanup (see PN2). Land the test first
against the current shape.

---

**PN2 — Two functions named `run_push_cycle` with different session
lifecycles is a standing trap for the next contributor**
**Severity:** P2 · **Area:** api · **Effort:** S

**Evidence:** `push_notifications.run_push_cycle` (single-session, test-only
per its own docstring, `push.py:638-653`) and
`push_scheduler.run_push_cycle` (`push_scheduler.py:58-66`, production,
delegates to `_push_cycle` via the lock) are different functions with the
same name, imported under the same module alias in different files. Nothing
stops a future change from calling the wrong one, or from "fixing" a bug in
`_push_cycle` by copying logic from `run_push_cycle` (the two-session vs.
one-session distinction is exactly the kind of detail that gets lost in a
copy-paste).

**Why it matters:** this is the direct cause of PN1 — a reviewer or a
future agent grepping for `run_push_cycle` tests will reasonably (and
wrongly) conclude the scheduler cycle is well tested.

**Recommended fix:** rename the test-only helper to something that cannot
be confused with the production entry point, e.g. `run_push_cycle_single_session`,
and add a one-line docstring cross-reference from `_push_cycle` back to it
("mirrors `push_notifications.run_push_cycle_single_session` but split
across two DB sessions — keep both in sync"). Do this after PN1's test lands,
so the rename doesn't also silently drop coverage.

**Do not:** delete the single-session helper — it's a legitimate,
reasonably ergonomic way to unit-test the four producers' combined output
without wiring two session mocks per test.

---

**PN3 — Calendar and learning nudges claim their Redis dedupe key before
Expo confirms the send; a crash in between silently drops the notification**
**Severity:** P2 · **Area:** api · **Effort:** M

**Evidence:**
- Calendar: `process_calendar_nudges` claims the per-event key *before*
  building the outbound message and *before* any Expo call:
  `claimed = await redis.set(dedupe_key, "1", nx=True, ex=ttl)`
  (`push.py:480`), then appends to `messages` (`:488-501`). The key is only
  released later, in `_finalize_push_deliveries`, and only if the send is
  recorded as failed (`:547-549, 573-575`).
- Learning: identical shape — `claim_learning_candidates` does the SETNX
  (`apps/api/app/services/learning/nudges.py:53`) *before* `collect_learning_nudge_picks`
  even loads stats or builds a message; the unclaim also only happens in
  `_finalize_push_deliveries` on a recorded failure, or inline when no
  sendable nudge exists (`nudges.py:145-147` — a different, non-crash case).
- Compare to todo reminders and email suggestions, which have **no**
  pre-claim at all — they rely purely on `TodoItem.notification_sent_at` /
  `SuggestedReminder.notification_sent_at` being `NULL`, set only *after* a
  confirmed Expo `ok` ticket. That design can duplicate a send on a crash
  (self-healing: the DB row is unaffected until it's actually marked) but
  can never lose one.
- `nudge_ttl_seconds` (`apps/api/app/services/calendar_nudges.py:62-66`) is
  `max(300, remaining + 3600)` — for an event 15 minutes out, that's a
  ~65-minute claim. If the worker dies between the `redis.set` at `push.py:480`
  and `dispatch_expo` actually reaching Expo (process kill, OOM, redeploy —
  the same class of failure `docs/CODEBASE_REVIEW_2026-08.md`'s C1 finding
  treats as a first-class concern for chat quota), the claim survives the
  crash and blocks every subsequent tick from re-claiming it. The meeting
  nudge is gone, silently, for up to an hour — almost always past the point
  where it's useful.
- Learning's day-key claim TTL is `86_400` (`nudges.py:53`) — a crash in the
  same window loses that user's learning nudge for the *entire day*, not
  just one tick.
- No test in `test_push_notifications.py` exercises "claimed, then process
  dies before dispatch" for either producer; the only failure-path tests
  are for a *recorded* Expo failure (`test_finalize_keeps_calendar_dedupe_when_any_device_succeeds`
  and its inverse), which correctly assumes finalize gets to run.

**Why it matters:** this is the opposite failure mode from the
already-fixed #1017 bug (that one duplicated forever; this one can silently
drop once, per crash, per in-flight event) — but it's invisible today
because nothing simulates the crash. Given the worker process already
restarts on deploys and can be OOM-killed (there's a dedicated
`worker_health.py` liveness probe specifically because this happens), this
is not a hypothetical.

**Recommended fix:** move the claim to *after* a confirmed `ok` ticket
(inside `_finalize_push_deliveries`, alongside where `learning_success` /
`dedupe_success` are already tracked) instead of before collection. Since
one worker instance runs one cycle at a time under the scheduler lock, and a
healthy cycle completes well within the 60s interval, claiming post-send
still prevents duplicate sends on every *healthy* subsequent tick — it just
stops being able to lose the notification on a crash, matching the
todo/email design. The cost is accepting the same "possible duplicate,
never lost" tradeoff already made for the other two producers, which is the
right tradeoff for a personal reminder app.

**Do not:** try to make the claim itself crash-safe with a Redis
transaction spanning the Expo HTTP call — Redis can't participate in that
kind of distributed transaction usefully here, and the point of collecting
under a short-lived DB session (`push_scheduler.py:29-30`) is specifically
to *not* hold anything open across the network call.

---

### Security / observability

---

**PN4 — Rejected cross-user token rebind attempts are invisible; only
successful rebinds are logged**
**Severity:** P2 · **Area:** api · **Effort:** S

**Evidence:** `_report_rebind` (`apps/api/app/repositories/push_tokens.py:22-42`)
logs a warning and adds a Sentry breadcrumb, but it is called **only** from
the success path (`:92`, after the device_id check passed). The two reject
branches — missing `device_id` (`:75-78`) and mismatched `device_id`
(`:79-81`) — raise `PushTokenBindError` with no logging, no metric, and no
Sentry signal of any kind before the router turns it into a plain 403
(`apps/api/app/routers/users.py:28-32`).

**Why it matters:** a rejected rebind is the more security-relevant event of
the two — it's what an actual token-theft attempt looks like (someone else's
Expo token, wrong or no `device_id`). Today there's no way to notice a
pattern of these (e.g., repeated 403s from one IP or user) because nothing
is ever recorded. Contrast with how carefully this codebase instruments
*other* security-adjacent paths (RevenueCat webhook claims, WS handshake
rate limiting) — this one is a blind spot.

**Recommended fix:** add a `logger.warning` + Sentry breadcrumb (mirroring
`_report_rebind`'s shape) in both reject branches before raising
`PushTokenBindError`, tagged distinctly (e.g. `push.token.rebind_rejected`)
so it's easy to alert on a spike separately from the accepted-rebind signal.

**Do not:** log the raw Expo token or `device_id` values at `warning`
level in production — hash or truncate them the way `delete_by_token`
already does (`push.py:647`, `token[:20]`).

---

**PN5 — First-time token claims have zero possession proof; only re-binds
of an *existing* row are guarded**
**Severity:** P3 · **Area:** api · **Effort:** S (fix is a doc/backlog note, not urgent code)

**Evidence:** `push_tokens.upsert` (`push_tokens.py:45-102`) only checks
`device_id` when a row for that `expo_push_token` **already exists**
(`row is None` branch at `:58-65` skips the check entirely — any
authenticated user can claim a brand-new token string with no proof at
all). The "re-bind hardening" in `FEATURES.md:756-760` explicitly scopes
itself to *moving* an existing token, and says so.

**Why it matters:** if an attacker ever learns another user's Expo push
token *before* that user's device first registers it with this backend
(e.g., leaked via a different app's logs, a shared CI fixture, or a
misconfigured analytics pipeline), they can pre-register it under their own
account. The real device's own later registration attempt then hits the
cross-user branch and needs a `device_id` match against the attacker's
fabricated value — which it will never have — permanently blocking the
legitimate user from getting push at all (via 403) until an operator
manually clears the row. This is a token-squatting DoS, not a
data-exposure risk (the attacker doesn't get the victim's chat content), and
it requires an unusual pre-condition (learning the token before its owner
ever registers it), so P3 is appropriate. It is a different, additional gap
from the residual risk `FEATURES.md` already documents.

**Recommended fix:** no urgent code change. Add one line to `FEATURES.md`'s
existing "Push-token re-bind hardening" bullet noting the first-claim gap
explicitly, so it's tracked rather than implicitly assumed covered by the
existing wording. If it's ever worth closing, an admin/support tool to
force-clear a `PushToken` row by token prefix is cheaper than adding
attestation.

**Do not:** add device attestation (App Attest / Play Integrity) to close
this — `FEATURES.md` already correctly defers "full device attestation" as
disproportionate for a personal reminders app.

---

**PN6 — `push_tokens.upsert`'s select-then-insert has no protection against
a concurrent double-insert of the same new token, and it's untested against
a real database**
**Severity:** P3 · **Area:** api / tests · **Effort:** S

**Evidence:** `upsert` selects for the token (`:54-56`), and on a miss,
constructs and `session.add`s a new `PushToken` then commits (`:58-65, 100`)
with no `try/except` around the insert. `expo_push_token` has a DB-level
`UniqueConstraint` (`apps/api/app/models/orm/integrations.py:102`). Two
concurrent first-time registrations of the same token (e.g., the mobile
app's mount-time call in `attachPushForegroundSync` racing a near-simultaneous
`AppState` "active" transition on a cold launch) would both pass the
`scalar_one_or_none() is None` check before either commits, and the second
`session.commit()` would raise an unhandled `IntegrityError`, surfacing as
an unhandled 500 (harmless to the user — mobile's call is wrapped in a
swallow-all `try/except`, see PN7 — but a 500 nonetheless, and un-instrumented).
Separately: every existing test for `upsert` — in
`tests/repositories/test_push_tokens.py` (only `list_for_users` is covered),
`tests/repositories/test_connections.py:68-98`, and
`tests/services/test_push_notifications.py:1035-1120` — uses a mocked
`AsyncMock` session. There is no `test_push_tokens_db.py`, even though
sibling repository `todo_schedules.py` (same domain, same "conditional write"
shape) has `test_todo_schedules_db.py`.

**Why it matters:** this is low-probability (mobile's own registration
call-sites are already gated to avoid double-firing in the common case) but
completely unverified — a real concurrent-insert scenario would currently
be caught by production error monitoring, not by CI.

**Recommended fix:** either add a `try/except IntegrityError` around the
insert branch that falls back to re-selecting and treating it as the
"already exists" case, or (simpler, given Postgres) switch the insert to an
`INSERT ... ON CONFLICT (expo_push_token) DO NOTHING` + re-select, matching
the `ON CONFLICT` pattern already used elsewhere in this codebase (e.g.
`repositories/usage.py`'s `add_tokens`). Add one `test_push_tokens_db.py`
covering: concurrent-equivalent double insert, the unique constraint firing,
and the three existing mocked rebind-branch tests re-verified against a real
session.

**Do not:** add application-level locking (e.g., a Redis lock per token) —
that's disproportionate for a rare race the database already resolves via
its own constraint; the fix is just handling the constraint gracefully.

---

### Mobile registration / permission / settings

---

**PN7 — The push toggle reports success even when no token was ever
registered — every registration failure mode is silently swallowed**
**Severity:** P1 · **Area:** mobile · **Effort:** M

**Evidence:**
- `registerRemotePushToken` (`apps/mobile/lib/pushNotifications.ts:71-93`)
  returns `void` and has exactly one `try/catch` (`:83-92`), around only the
  final `api.registerPushToken` call — and it swallows unconditionally
  (`catch { /* best-effort */ }`, no logging at all, not even a `console.warn`).
  Every earlier early-return (`resolveExpoPushToken()` returning `null` at
  `:81` — which happens on Android Expo Go, a missing EAS `projectId`
  (`:53-54, :40-50`), or a network failure fetching the token from Expo's
  servers) also silently produces "no token was registered," with **no
  distinguishable signal** from "not applicable right now."
- `settings/notifications.tsx`'s `togglePush` (`:104-124`) calls
  `await registerRemotePushToken(token, true);` and then, unconditionally
  (no return-value check, because there is no return value to check):
  `await updateUser({ push_notifications_enabled: true });` (`:120-121`).
- The only failure path the settings screen *can* observe is OS permission
  denial (`if (!granted) { Alert.alert(...) }`, `:116-117`) — checked
  **before** `registerRemotePushToken` is even called, so it never sees a
  post-permission registration failure (403 rebind rejection, missing
  `projectId`, Expo/network error).
- `apps/mobile/app/__tests__/notifications.test.tsx` has tests for the
  permission-denied Alert path but none for "permission granted,
  registration itself failed" — confirming this branch is genuinely
  untested, not just under-evidenced.

**Why it matters:** every one of these concrete, real scenarios ends in the
same silent state — toggle shows ON, `user.push_notifications_enabled` is
`true` server-side, and the device receives nothing:
1. Cross-user rebind 403 (PN's own hardening feature, working as designed,
   but with zero user-visible feedback — see PN4's server-side blind spot
   too).
2. Android + Expo Go (documented as requiring a dev build in `FEATURES.md`,
   but the settings screen doesn't know or say that).
3. A dev/preview build missing `extra.eas.projectId`.
4. A transient network failure on `POST /users/push-token` (the *server*
   accepted the permission and the user thinks it worked; the token simply
   never reached the DB).

  This is the one finding in the whole review with a direct, plausible path
to "I turned reminders on and never got one," which is the core product
promise of this feature.

**Recommended fix:** make `registerRemotePushToken` return a discriminated
result (`{ ok: true } | { ok: false; reason: "permission" | "no_token" | "network" | "rejected" }`)
instead of `void`, log the failure reason (at minimum `console.warn`, ideally
`trackProductEvent`, mirroring the existing `push_permission` event), and
have `togglePush` only call `updateUser({ push_notifications_enabled: true })`
on a real `ok: true`, showing the existing `push_blocked_title`/`_message`
Alert (or a new "couldn't register this device" copy) otherwise. Do the same
audit for the `AppState`-driven re-sync path in `attachPushForegroundSync` —
it doesn't need an Alert (the app is backgrounded), but it should at least
log so a support engineer debugging "no pushes" has something to grep for.

**Do not:** turn this into a blocking foreground retry loop or a persistent
banner — this is a personal reminders app, not a messaging app; a clear,
one-time failure signal at toggle-time is enough. Don't change the
Expo-Go/no-EAS-project no-op behavior itself (PN's "what's working" list) —
only the *visibility* of that state needs to change.

---

**PN8 — Denied permission triggers a native re-request call and a duplicate
analytics event on every single foreground transition**
**Severity:** P3 · **Area:** mobile · **Effort:** S

**Evidence:** `ensureNotificationPermission` (`pushNotifications.ts:18-28`)
calls `Notifications.getPermissionsAsync()`, and whenever the result isn't
`"granted"` (including a firm `"denied"` with `canAskAgain: false`), it
unconditionally calls `Notifications.requestPermissionsAsync()` again
(`:23`) and fires `trackProductEvent(..., "push_permission", { status: ... })`
(`:24-26`). `attachPushForegroundSync`'s `AppState` listener
(`pushNotifications.ts:127-135`) calls `registerRemotePushToken` — and
therefore `ensureNotificationPermission` — on *every* foreground transition
while `push_notifications_enabled` is true, regardless of whether permission
was already denied last time.

**Why it matters:** iOS/Android both suppress the actual OS re-prompt UI
once a user has denied and the app has no more prompts left, so this isn't
a UX bug the user sees — but it does mean a user who has push denied and
simply uses the app normally (backgrounding/foregrounding many times a day)
generates a fresh `push_permission: denied` analytics event and a wasted
native round-trip on every single resume, forever.

**Recommended fix:** have `ensureNotificationPermission` check
`canAskAgain` from `getPermissionsAsync()`'s result and short-circuit to
`false` without calling `requestPermissionsAsync()` (or firing the
analytics event) when it's already `false`.

**Do not:** cache "denied" locally to skip checking `getPermissionsAsync()`
itself — the user can still flip the OS setting back on outside the app, and
`getPermissionsAsync()` is the correct source of truth for that.

---

**PN9 — `PushTokenIn` validates only length, not Expo's token shape**
**Severity:** P3 · **Area:** api · **Effort:** S

**Evidence:** `PushTokenIn.expo_push_token` is `Field(min_length=8, max_length=512)`
(`apps/api/app/models/schemas/integrations.py:141`) — any 8–512 character
string is accepted and stored. Real Expo tokens are always shaped like
`ExponentPushToken[...]` or `ExpoPushToken[...]`.

**Why it matters:** low severity — Expo's own API will reject a malformed
`to` value at send time (caught by the existing broad `except Exception` in
`_send_chunk`), so this can't cause a crash or a leak. It just means garbage
tokens can sit in the table indefinitely (never pruned by the
`DeviceNotRegistered` path, since Expo would presumably return a different
error class for a malformed value that isn't currently classified) and
count against nothing but noise.

**Recommended fix:** add a `pattern` constraint
(`r"^Expo(nent)?PushToken\[.+\]$"`) to `PushTokenIn.expo_push_token`.

**Do not:** validate token shape in the mobile client instead of (or as well
as) the server — the server is the trust boundary; client-side validation
is UX-only and easy to bypass.

---

## D. Weak / unwanted / missing inventory

| Item | Status | Evidence | Recommend |
|---|---|---|---|
| Production `_push_cycle` behavior | Missing test coverage | `push_scheduler.py:27-56`; only test is `test_push_scheduler.py`'s 7-line lock-TTL assertion | Add direct tests (PN1) |
| `run_push_cycle` naming collision | Weak (confusable, caused PN1) | `push.py:638` vs `push_scheduler.py:58` | Rename test helper (PN2) |
| Calendar/learning dedupe claim ordering | Weak (claim before confirmed send) | `push.py:480`; `learning/nudges.py:53` | Move claim to post-success (PN3) |
| Rejected rebind observability | Missing | `push_tokens.py:75-81` (no log) vs `:92` (logged) | Log both branches (PN4) |
| First-claim token possession proof | Missing (documented gap, narrower one) | `push_tokens.py:58-65` | Note explicitly in FEATURES.md (PN5) |
| `upsert` insert-race handling | Missing; untested against real DB | `push_tokens.py:58-65, 100`; no `test_push_tokens_db.py` | `ON CONFLICT` + real-DB test (PN6) |
| Mobile registration failure visibility | Weak (silently swallowed everywhere) | `pushNotifications.ts:71-93`; `notifications.tsx:104-124` | Return + surface a result (PN7) |
| Denied-permission foreground re-request | Weak (harmless but wasteful) | `pushNotifications.ts:18-28, 127-135` | Respect `canAskAgain` (PN8) |
| Push token shape validation | Missing (cosmetic) | `models/schemas/integrations.py:141` | Add `pattern` (PN9) |
| Shared send funnel (4 producers → 1 pipeline) | Solid | `push.py:238-653` | Keep as-is |
| Expo 100-message batching + per-chunk isolation | Solid, tested | `expo_push_gateway.py:88-167` | Keep as-is |
| `InvalidCredentials` vs `DeviceNotRegistered` | Solid, tested | `expo_push_gateway.py:16-21, 78-85` | Keep as-is |
| Receipt-vs-ticket delivery semantics | Solid, documented | `push.py:1-9, 156-201` | Keep as-is |
| Cross-user rebind `device_id` hardening | Solid, tested, honestly documented | `push_tokens.py:71-92`; `FEATURES.md:756-760` | Keep as-is |
| `push_notifications_enabled` SQL-level gating | Solid | `push.py:254, 320, 387, 452` | Keep as-is |
| Local/remote reminder double-fire prevention | Solid | `todoReminderPush.ts:19-23`; `PushNotificationBootstrap.tsx:60-69` | Keep as-is |
| Expo Go / web no-op safety | Solid, one regression test already | `pushNotifications.ts:52-61`; `PushNotificationBootstrap.test.tsx` | Keep as-is |
| Scheduler lock correctness | Solid | `core/redis_lock.py`; `background/periodic.py:42-53` | Keep as-is |
| Payload content minimality | Solid | `push.py:119-127, 221-235` | Keep as-is |

---

## E. Suggested sequencing

One concern per change, each independently shippable:

1. **`test(api): cover the production two-session push cycle`** — PN1.
   Highest leverage, zero behavior change, closes the exact blind spot that
   let the last real incident (#1017) ship untested.
2. **`fix(mobile): surface push-registration failures to the settings
   toggle`** — PN7. Second because it's the one finding with a direct path
   to a bad user-facing outcome ("reminders silently don't arrive").
3. **`fix(api): claim calendar/learning dedupe keys after a confirmed send,
   not before`** — PN3. Depends on nothing above; do it once PN1's test
   scaffolding exists so the fix has a regression test alongside it.
4. **`chore(api): rename the test-only run_push_cycle helper`** — PN2. Do
   after PN1 lands so the rename doesn't touch in-flight test additions.
5. **`fix(api): log rejected cross-user push-token rebinds`** — PN4. Small,
   independent, no behavior change to the accept/reject decision itself.
6. **`fix(api): handle concurrent first-time token inserts; add
   test_push_tokens_db.py`** — PN6.
7. **`chore`: FEATURES.md note (PN5) + `pattern` validation on
   `PushTokenIn` (PN9) + `canAskAgain` short-circuit (PN8)** — batch these
   three together; each is a one-line change with no interaction between
   them.

---

## F. Explicit non-goals

Considered and deliberately not raised as findings:

- **Adding device attestation (App Attest / Play Integrity).** `FEATURES.md`
  already correctly defers this as disproportionate for a personal
  reminders app; PN5 only asks for the existing gap to be written down more
  precisely, not closed with attestation.
- **Rate-limiting/backoff tuned specifically to Expo's `429`/5xx responses.**
  The current behavior — a failed chunk's messages stay unmarked and retry
  on the next 60s scheduler tick — is a reasonable, if implicit, backoff for
  a personal-reminder cadence. Not worth a dedicated retry/backoff layer
  unless Expo-side throttling is observed in practice.
- **Unifying the WS/SSE-style "one shared payload builder" pattern from
  `docs/CODEBASE_REVIEW_2026-08.md`'s C6 finding onto push messages.** Push
  already has exactly one message-building seam (`_append_outbound`); there
  is nothing to consolidate.
- **Splitting `services/notifications/push.py` into a package.** At 654
  lines with four clearly-separated producer functions plus one shared
  finalize/dispatch tail, this is comparable to (and smaller than) the
  `math_tools.py` case the prior review explicitly declined to split — it
  isn't a dumping ground, and splitting it would scatter the one thing that
  makes it reviewable: seeing all four producers' shared tail in one file.
- **Migrating `apps/api/app/services/push_notifications.py`'s compatibility
  shim away.** It's a deliberate `sys.modules[__name__] = _impl` alias to
  the packaged `services/notifications/push` module, presumably to avoid a
  call-site churn PR. Cosmetic; not a correctness or security concern.
