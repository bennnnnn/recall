# Recall — Account Lifecycle & Transactional Email Review (Sep 2026)

Scope: account deletion / GDPR purge (`services/account_lifecycle.py`), GDPR data
export (`services/export_service.py`), transactional email content + dispatch
(`services/notifications/transactional_email.py`, `gateways/email_gateway.py`),
the `/auth/me` (export/delete) router surface, the background job handlers that
touch these paths (`background/handlers.py`), and the mobile delete-account /
export UI and session teardown (`hooks/useDataControls.ts`,
`app/settings/data-controls.tsx`, `lib/signOutCleanup.ts`, `contexts/AuthContext.tsx`).

This is round 4 of the cross-domain review series. Round 1–3 findings
(`docs/CROSS_DOMAIN_REVIEW_2026-09-05.md`) are not re-litigated. Per the task
brief, `docs/BACKGROUND_JOBS_INFRA_REVIEW_2026-09-06.md` **J4** (transactional
email in-process-retry double-send) and **J5** (spend-cap skip extends dedupe
permanently) are treated as already-known and are only referenced where a new
finding here is directly adjacent to them.

---

## A. Verdict

**Account deletion is architecturally sound and unusually well-tested for the
data it was designed to cover — every Postgres-owned table that holds user
content is genuinely purged, either by an explicit delete in
`users_repo.delete_user` or by a real `ON DELETE CASCADE` constraint verified
against the actual Alembic migration DDL (not just the SQLAlchemy model
annotation, which can silently drift from the DB). Redis session revocation
is real security, not token deletion theater: a `revoked_since` key
invalidates every access token issued before the delete, and the WS layer
re-verifies on every chargeable frame specifically so a live session on
another device is cut off mid-conversation, not just at natural JWT
expiry — this is a rare degree of care and is explicitly comment-documented
as such (`routers/ws.py:474-490`).**

**The two real gaps are elsewhere: (1) the transactional-email job handler
silently converts *any* send failure into a recorded job success — a
distinct, more consequential bug than the already-known J4/J5, not a
duplicate of them — and (2) the two "GDPR-adjacent" features that sit next to
account deletion, data export and billing cleanup, are each incomplete in a
concrete, evidence-backed way: the export silently omits several tables
(including one containing verbatim Gmail content), and account deletion never
touches the RevenueCat subscription, so a deleted Pro user keeps being billed
by the App/Play Store indefinitely with no in-app disclosure.**

Every background job type that could plausibly run concurrently with account
deletion (memory, todos, projects, topic, transactional_email, attachment_index,
message_index, gmail_sync) was traced to its actual row-lookup code, not just
its handler wrapper, and each one degrades safely — no crash, no data
resurrection, no write to an orphaned `user_id` — when the row it's scoped to
is already gone. Re-signup with the same Google/Apple identity or email was
traced end-to-end and is clean: a hard-deleted row releases the
`google_sub`/`apple_sub`/`email` uniqueness immediately, so the next sign-in
creates a genuinely fresh account with a new random UUID, and both the
Redis-side session state and the mobile-side local caches/RevenueCat identity
are torn down in a way that cannot leak into the new account.

---

## B. What's working (don't "fix" these)

- **DB-level cascade was independently re-verified against the actual
  migration DDL, not just the ORM annotation.** `users_repo.delete_user`
  (`repositories/users.py:83-113`) explicitly deletes 13 tables before the
  user row, and its own docstring claims some of those FKs (`todos`,
  `projects`, `project_items`, `suggestions`, `messages`, `memories`) have no
  `ON DELETE CASCADE` — but migration `0052_user_owned_cascades.py` added real
  DB-level `CASCADE` to all eight of those FKs, so the docstring is now stale
  (harmless: the explicit deletes are redundant-but-safe, not wrong). Every
  other user-owned table not in that explicit list —
  `attachment_chunks`/`message_chunks`/`product_events`/`quiz_miss_events`/
  `learning_practice_events` — was checked against its own migration
  (`0047_attachment_chunks.py`, `0064_message_chunks.py`,
  `0068_product_events.py`, `0056_quiz_miss_events.py`,
  `0079_learning_practice.py`) and each one really does declare
  `ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE")` at the
  DB level. **Every table that stores user content is covered; nothing was
  found orphaned in Postgres.**
- **pgvector embeddings have no separate index to sweep.** Memory, attachment,
  and chat-history embeddings live as a `Vector` column directly on
  `memories` / `attachment_chunks` / `message_chunks`
  (`models/orm/memory.py:53`, `models/orm/attachments.py:69,85,116`) — the
  same cascade above covers them. There is no separate vector store with its
  own retention/deletion contract to forget.
- **Object storage has two independent, genuinely redundant backstops, not
  one claimed one.** `purge_attachments_for_user`
  (`services/attachment_lifecycle.py:115-141`) best-effort deletes bytes then
  rows, and any byte-delete failure is pushed into a Redis `SET`
  (`enqueue_failed_storage_deletes`, `:66-74`) that the orphan reaper retries
  on every cycle **independently of whether the DB row still exists**
  (`retry_pending_storage_deletes`, `:77-100`, called from
  `reap_orphan_attachments:160`). Separately, `delete_account` enqueues a
  `storage_sweep` job that does a hard `DELETE`-by-prefix on `{user_id}/`
  (`account_lifecycle.py:105-110` → `attachment_lifecycle.sweep_user_storage`,
  `:202-215`) as a second, row-independent sweep. These are two genuinely
  different mechanisms (per-key retry set vs. per-user prefix sweep), not the
  same safety net counted twice.
- **Session revocation is real, immediate, and covers live sockets, not just
  new requests.** `purge_user_sessions` (`services/tokens.py:112-127`) sets a
  `revoked_since:{user_id}` key with a bounded TTL
  (`_revoke_all_refresh_tokens:86-109`); every access-token check
  (`verify_access_token:252-271`) rejects any token issued before that
  timestamp — closing the "still has a live JWT that hasn't naturally
  expired yet" window immediately, not at the token's own `exp`. The chat
  WebSocket explicitly re-verifies on **every chargeable frame** specifically
  so this reaches an open socket, with a comment naming account deletion as
  the reason (`routers/ws.py:474-490`): *"Re-check access on every chargeable
  frame so logout / account delete / refresh-reuse revoke… actually closes
  open sockets — handshake-only verify would leave them live."* This directly
  answers "is a live session on another device cut off during/after
  deletion" — yes, within one WS frame, by design, and the design explicitly
  names this exact scenario.
- **Google/Calendar/Gmail integration tokens are genuinely revoked at
  Google, not just deleted locally.**
  `revoke_all_google_tokens_for_user` (`services/google_integrations.py:137-153`)
  decrypts each stored refresh token and calls
  `google_oauth_revoke.revoke_refresh_token` — a real outbound call to
  Google's revoke endpoint — before the connection rows are deleted. Runs
  before attachment purge and the final user delete, in the correct order to
  still have the row to revoke.
- **Retry-safe, idempotent delete endpoint.** `DELETE /auth/me` purges
  sessions as its *first* step (`account_lifecycle.py:73-87`), so a client
  retry after a dropped response (network drop after the server actually
  finished) gets a 401 (token now revoked, `deps.py:37-53`), and the mobile
  client explicitly treats 401/404 on this specific call as "deletion already
  happened" (`lib/accountDelete.ts:1-8`) rather than surfacing a spurious
  error — a genuinely thought-through retry contract, not an accident.
- **Re-signup after deletion is clean end-to-end, traced through both
  identity providers.** `login_with_google`/`login_with_apple`
  (`services/auth.py:31-90, 91-153`) look up by `google_sub`/`apple_sub`, then
  by `email` — both are fully released by the hard delete (`session.delete(user)`,
  `repositories/users.py:112`), so the next login takes the `user is None`
  branch and calls `users_repo.create` with a **new random UUID**
  (`default=uuid.uuid4`, `models/orm/user.py:43`). No unique-constraint
  collision, no stale row to accidentally match. `is_new_user=True` correctly
  re-triggers the welcome-email enqueue (`services/auth.py:184-185`).
- **Redis-side per-user state cannot leak across a delete→resignup cycle,
  because every key that matters is either purged or keyed by a UUID that
  will never recur.** `purge_user_sessions` clears the live refresh-token set;
  quota/usage counters (`services/quota.py:109-110,139-141`) are
  `INCRBY`+`EXPIRE`'d with a bounded daily TTL — even if untouched, they
  age out on their own — and since the new account gets a fresh UUID, no
  quota/session/lock key computed as `f"...:{user_id}"` can ever collide with
  a pre-deletion key.
- **Mobile-side teardown on delete is more thorough than plain sign-out, and
  explicitly guards the RevenueCat cross-account leak.**
  `clearSignedOutAccount` (`lib/signOutCleanup.ts:1-24`) cancels scheduled
  local todo-reminder notifications, clears every list/cache (chat messages,
  memories, gallery, integrations, suggested reminders, chat list, usage), and
  calls `signOutRevenueCat()` (`lib/purchases.ts:100-111`, comment: *"log out
  RevenueCat so the next user doesn't inherit the prior user's entitlements /
  customer info"*) — this is precisely the mitigation that keeps the
  backend-side RevenueCat leftover (finding **E3** below) from being
  exploitable as a same-device entitlement leak between two different
  accounts.
- **No parameter-tampering path exists for delete or export.** `GET
  /auth/me/export` and `DELETE /auth/me` (`routers/auth.py:314-338`) both take
  their target exclusively from `Depends(get_current_user)` — neither route
  accepts a user id, account id, or any other identifier from the request
  that could be swapped to target someone else's data. `routers/admin.py` was
  checked for a parallel admin-side path and has none (its only destructive
  action is DLQ replay, unrelated to user data).
- **PII does not leak into logs on email failure.** `email_gateway.send_email`
  logs only a domain-only recipient label (`_recipient_log_label`,
  `gateways/email_gateway.py:27-32`) on both the mock-path and the real
  failure path; this is asserted by an existing test
  (`test_gateway_failure_log_omits_full_recipient`,
  `tests/services/test_transactional_email.py:200-224`), not just implied by
  the code.
- **HTML-escaping and header-injection hardening are real and tested**, not
  just claimed in a comment: `_esc`/`_strip_header_chars`
  (`transactional_email.py:454-475`) are exercised by
  `test_build_todo_reminder_escapes_html_but_not_text`,
  `test_build_receipt_escapes_html_fields`, and
  `test_build_todo_reminder_strips_newlines_from_subject`
  (`tests/services/test_transactional_email.py:64-90,140-154`) with payloads
  that would actually break an unescaped/unstripped template.
- **`todo_reminder`/`learning_nudge` (the two email types that go through the
  periodic scheduler, not the job queue) already handle "send failed" the
  way welcome/receipt should.** `process_todo_reminder_emails`
  (`services/notifications/reminder_email.py:93-113`) only calls
  `mark_email_sent_if_current` when `send_todo_reminder` returns `True`,
  leaving a failed send's DB marker untouched so the **next scheduler cycle
  retries it** — this is exactly the fix finding **E1** below recommends for
  welcome/receipt, already shipped for the other two email types.

---

## C. Findings — ranked

### Transactional email

---

**E1 — The job-queue transactional-email handler discards the gateway's
success/failure return value: any send failure (not just J4's narrow
ambiguous-timeout case) is recorded as job success, permanently, with zero
retry and zero DLQ entry**
**Severity:** P1 · **Area:** transactional-email / jobs-infra boundary · **Effort:** S

**Evidence:**

- `background/handlers.py:225-250`, `_handle_transactional_email`: calls
  `await transactional_email_service.send_welcome(settings, user)` (`:238`) or
  `send_purchase_receipt(...)` (`:239-247`) and **does not inspect the
  returned bool** — the function returns `None` either way, so the caller
  (`_dispatch` inside `_process_one_entry`) sees a normal return in both the
  success and the failure case.
- `gateways/email_gateway.py:35-88`, `send_email`: by explicit design (its own
  docstring, `:6-8`: *"Sending is best-effort: a failure is logged and never
  raised into the caller"*) **every** failure mode — disabled flag, empty
  recipient, not configured, `httpx` timeout/connection error, and any
  non-2xx via `response.raise_for_status()` — is caught internally
  (`except Exception:` at `:86-88`) and converted to `return False`. No code
  path in this function ever raises.
- `core/jobs.py:300-308`, `_process_one_entry`'s retry loop: `await
  _dispatch(settings, fields)` (`:303`) is followed unconditionally by
  `await _extend_dedupe(redis, dedupe_key)` then `break` (`:307-308`) **unless
  an exception propagates**. Since `send_welcome`/`send_purchase_receipt`
  never raise on a real send failure, this is exactly the "success" branch
  every time, regardless of what Resend actually returned. The dedupe key
  (`welcome:{user_id}` / `receipt:{uid}:{event_type}:{product_id}`) is
  extended to the full 24h "done" TTL (`_JOB_DONE_TTL_SECONDS`, per the
  background-jobs review's own citation of this mechanism), and the entry is
  `xack`'d in the `finally` block (`:328-334`) — permanently removed from the
  pending list.
- **No test exercises the failure path at this layer.** Both existing tests
  for this handler (`test_handle_transactional_email_welcome_dispatches`,
  `test_handle_transactional_email_receipt_dispatches`,
  `tests/services/test_transactional_email.py:353-416`) patch `send_welcome`
  / `send_purchase_receipt` with `AsyncMock(return_value=True)` and assert
  only that the mock was awaited — there is no test asserting what
  `_handle_transactional_email` does when the mock returns `False`. Given the
  code literally never checks the return value, that test would currently
  pass trivially either way, which is itself a coverage gap that let this
  ship.
- **Contrast with the two email types that don't have this bug**:
  `process_todo_reminder_emails` (`services/notifications/reminder_email.py:103-107`)
  and `process_learning_nudge_emails` (`:144-148`) both check `ok` and only
  commit/count on `True` — proving the codebase already knows the correct
  pattern, it just wasn't applied to the job-queue path.

**Why it matters:** this is not a duplicate of J4 (in-process retry causing a
*double* send on an ambiguous provider timeout — a narrow race). This is the
much more common, opposite-direction case: **any** definite send failure —
Resend down for a minute, a bad API key, a rate limit, a malformed recipient
— results in the welcome or Pro-receipt email being sent exactly once,
failing, and being recorded as a **successful** job completion. The queue's
own `_MAX_ATTEMPTS=3` retry-then-DLQ safety net (real and tested for every
other handler, per the background-jobs review) never engages for
transactional email at all, because the gateway's "never raise, always
best-effort" design — correct for protecting the synchronous chat/auth path
from an email failure — is reused unchanged as the job handler's return
value, and the job handler ignores it. The only trace of the failure is a
single `logger.exception` line in the gateway with no job-id, no
user-facing signal, and no operator alert. A user who signs up during a
Resend outage silently never gets a welcome email and there is no
after-the-fact way to know that happened, let alone retry it — the dedupe key
now blocks even a manual re-enqueue attempt for 24h.

**Recommended fix:** make `_handle_transactional_email` treat a `False`
return as a retryable failure — e.g. `if not sent: raise
TransientEmailSendError(...)` — so the existing, already-tested `_MAX_ATTEMPTS`
retry-then-DLQ mechanism actually applies to this handler like every other
one. This is a one-line-per-branch change in `background/handlers.py`; no
change to the gateway (which should keep its "never raise" contract for its
*other* caller, the chat/auth path) or to `core/jobs.py` is needed. Add a test
that patches `send_welcome`/`send_purchase_receipt` to return `False` and
asserts the handler raises (so the job queue retries) rather than returning
cleanly.

**Do not:** make `email_gateway.send_email` raise on failure — it is also
called from paths that must never let an email failure break the
request/chat flow (auth signup response, purchase-receipt trigger). The fix
belongs in the job handler that already knows it's running inside a
retry-capable queue, not in the shared gateway.

---

### Data export completeness (GDPR)

---

**E2 — The GDPR "export my data" feature is real and reasonably thorough, but
silently omits several user-owned tables — including one that stores
verbatim third-party (Gmail) content extracted about the user**
**Severity:** P1 · **Area:** compliance / export-service · **Effort:** S–M

**Evidence:**

- `services/export_service.py:20-30` imports exactly `Chat`,
  `LearningPracticeEvent`, `Memory`, `Message`, `ProductEvent`, `Project`,
  `ProjectItem`, `TodoItem`, `User` — confirmed by grep
  (`Suggestion\b|SuggestedReminder|UserCalendarConnection|UserGmailConnection|
  PushToken\b|UsageDaily` returns **zero matches** in this file) that none of
  the following user-owned tables are exported:
  - `suggested_reminders` (`models/orm/integrations.py:70-96`) — each row
    carries `source_snippet` and `source_sender`
    (`:87-88`), which is **a verbatim excerpt of the user's own Gmail
    message content** that the backend extracted and stored server-side.
    This is the most privacy-sensitive omission: a GDPR export request from
    a user whose Gmail is connected will not include this Gmail-derived
    personal data even though the backend clearly holds it.
  - `suggestions` (`models/orm/suggestions.py`) — proactive follow-up
    suggestions generated from the user's own recent activity.
  - `user_calendar_connections` / `user_gmail_connections`
    (`models/orm/integrations.py:26-46,49-66`) — connection metadata
    including the connected `google_email` and OAuth `scopes` (the
    `refresh_token` itself should stay excluded for security reasons, but the
    fact of the connection and which email/scopes are linked is exactly the
    kind of "what does this service know about me" fact a GDPR export exists
    to answer).
  - `push_tokens` (`models/orm/integrations.py:99-115`) — lower stakes (device
    push tokens, not content), but still personal/device data held about the
    user and not surfaced.
  - `usage_daily` (`models/orm/usage.py:22-35`) — token-usage stats; lower
    priority but also omitted.
- **This looks like an oversight, not an intentional scope boundary**, because
  the export *does* include tables added both before and after
  `suggested_reminders` chronologically: `product_events` (migration
  `0068`, newer than `suggested_reminders`'s `0024`) and
  `learning_practice_events` (migration `0079`, newer still) are both
  correctly wired into `_iter_export_json`
  (`export_service.py:432-445, 377-404`) with their own pagination limits —
  so newer tables *were* correctly retrofitted into the export at least
  twice, while an older one (`suggested_reminders`, predating both) was
  missed. This is the exact "does it silently miss subsystems added after
  the export feature was built" pattern the review brief asked about,
  just running in the opposite chronological direction from what you'd
  expect — the export was evidently revisited more than once and this table
  was skipped each time.
- No test asserts the export's *completeness* (i.e., that every user-owned
  ORM table has an exporter) — the existing test suite
  (`tests/test_account.py:227-677`) thoroughly asserts the *shape* of what
  is exported, but nothing fails when a new user-owned table ships without a
  corresponding export path, so this class of gap has no regression guard
  going forward either.

**Why it matters:** a user who exercises their GDPR Article 15/20 right to a
copy of their data, especially one who has connected Gmail (a feature that
explicitly reads and stores excerpts of their email), receives an export that
omits exactly that Gmail-derived content. This is a compliance gap with
concrete evidence, not a hypothetical — the code that would need to change is
small (each omitted table already has, or trivially needs, a
`list_for_user`-style repository function, mirroring the pattern every
already-exported table uses).

**Recommended fix:** add `suggested_reminders`, `suggestions`, and the
calendar/Gmail connection metadata (email + scopes, not the refresh token) as
additional sections in `_iter_export_json`, following the existing
page-and-yield pattern already used for todos/memories/practice-events.
`push_tokens` and `usage_daily` are lower priority but should be included for
genuine completeness. Add a test that enumerates every ORM model with a
`user_id` foreign key to `users.id` and asserts each one is referenced
somewhere in `export_service.py`, so a future new table cannot silently ship
without export coverage the way `suggested_reminders` did.

**Do not:** export `refresh_token` values from the calendar/Gmail connection
rows — those are credentials, not data-about-the-user in the GDPR sense, and
exporting them would hand the user (or anyone who intercepts the export file)
a live OAuth grant rather than information about what the service knows.

---

### Billing / subscription state on deletion

---

**E3 — Account deletion never touches the RevenueCat subscription: a deleted
Pro user keeps being billed by the App/Play Store indefinitely, with no
in-app disclosure, and the RevenueCat subscriber record (keyed by the
now-deleted internal user id) is orphaned with an active entitlement forever**
**Severity:** P1 (billing/product, capped by real store-level limits — see
"Do not") · **Area:** account-lifecycle / billing · **Effort:** S (disclosure) –
not fixable purely server-side for the underlying store subscription

**Evidence:**

- `services/account_lifecycle.py:73-110`, `delete_account`: purges sessions,
  revokes Google tokens, purges attachments, hard-deletes the user row, and
  enqueues `storage_sweep`. **Nothing in this function reads or calls
  anything under `services/subscription.py`, `gateways/revenuecat_gateway.py`,
  or any RevenueCat-related code path.**
- `services/subscription.py:20,36,79,94` confirm `app_user_id` passed to
  RevenueCat **is** `str(user.id)` — the app's own internal UUID is the
  RevenueCat subscriber id. Once that row is hard-deleted, the RevenueCat
  subscriber record for that exact id still exists on RevenueCat's side with
  whatever entitlement state it had at the moment of deletion — our backend
  has no record of it anymore to reconcile against, and never asked
  RevenueCat to do anything about it.
- `gateways/revenuecat_gateway.py` exposes exactly two functions —
  `fetch_subscriber` and `entitlement_active` — **no delete/cancel-subscriber
  call exists anywhere in this codebase** to even attempt to unlink or flag
  the orphaned subscriber record.
- Mobile confirmation copy discloses nothing about subscription state:
  `lib/i18n/en.json:290-291`, `delete.message`: *"This permanently deletes
  your account and all data. This action cannot be undone."* —
  `settings.delete_desc` (`:552`): *"Permanently removes your account and all
  data."* Neither string, nor any other string found in the delete-account
  flow (`app/settings/data-controls.tsx:54-66`,
  `hooks/useDataControls.ts:25-42`), mentions that an active subscription
  purchased through the App Store or Play Store is **not** cancelled by this
  action and must be cancelled separately in the store's own subscription
  settings — which is the actual, unavoidable mechanic for iOS/Android IAP
  (only the store, or the user directly, can stop the recurring charge; a
  backend cannot cancel a store subscription via RevenueCat's webhook-facing
  API).
- The mobile-side mitigation that *does* exist (`signOutRevenueCat()`,
  `lib/purchases.ts:100-111`, called from `clearSignedOutAccount`,
  `lib/signOutCleanup.ts:17`) prevents the **cross-account leak on the same
  device** (the next login correctly re-identifies with a fresh
  `app_user_id`) — but it does nothing for the **already-existing store
  subscription** tied to the old account, which keeps auto-renewing and
  billing the user's Apple/Google account regardless of what the app does
  locally.

**Why it matters:** this is the same "leftover secondary-store state" category
the review brief asked about explicitly (Q1: "RevenueCat subscription
state — is anything left behind indefinitely?") and the answer is yes, on
both sides: RevenueCat's own subscriber record for the deleted user, and —
materially worse for the actual user — the real, recurring Apple/Google
billing subscription. Apps that ship in-app account deletion (an App Store
Review Guideline 5.1.1(v) requirement this app already correctly implements)
are expected to make the interaction between account deletion and
subscription cancellation clear to the user; silently deleting the account
while the subscription (and the charges) continue is a foreseeable source of
support tickets and, in the worst case, a user reasonably believing "delete
account" means "stop being charged."

**Recommended fix:** at minimum, add an explicit line to the delete
confirmation copy for Pro users specifically (gate on `user.plan == "pro"`)
telling them their subscription is not cancelled by this action and pointing
to the store's subscription-management screen (iOS: Settings → \[name\] →
Subscriptions; Android: Play Store → Payments & subscriptions) — this is a
copy-only, low-effort fix available today. Separately, consider whether
RevenueCat's REST API offers anything actionable for the orphaned subscriber
record itself (e.g., tagging it or, for the subset of purchases routed
through Google Play, RevenueCat's real-time developer notification /ăexpire
integration may support a programmatic cancel — verify against current
RevenueCat docs before assuming it's possible) so it isn't purely a "tell the
user" fix.

**Do not:** assume this is fixable purely on the backend. For Apple in
particular, no third-party backend (including through RevenueCat) can cancel
an already-active App Store auto-renewable subscription on the user's
behalf — that capability does not exist in StoreKit's server-to-server API
surface. The realistic fix is disclosure + (where the store allows it)
best-effort RevenueCat-side cleanup, not "cancel the subscription
automatically," and the report should not be read as claiming the latter is
achievable.

---

### Email deliverability observability

---

**E4 — No bounce/complaint webhook handling exists for the email provider at
all: a hard-bounced or spam-complained recipient is invisible to the operator
indefinitely**
**Severity:** P2 · **Area:** transactional-email / observability · **Effort:** M

**Evidence:**

- `routers/webhooks.py:1-123` defines exactly one webhook route,
  `/webhooks/revenuecat`. Grepping the whole router tree for
  `resend|bounce|complaint|webhook` (case-insensitive) returns only that same
  file and the RevenueCat-specific service — there is no Resend webhook
  endpoint anywhere in `apps/api/app/routers/`.
- `core/config.py:205-214` has settings for `resend_api_key`,
  `resend_api_url`, and `email_from`, but no `resend_webhook_secret` or
  equivalent — confirming this isn't a partially-wired feature with a config
  flag sitting unused, it simply doesn't exist.
- The only signal a send failure produces anywhere in the system is
  `logger.exception("Transactional email send failed to=%s subject=%r", ...)`
  (`gateways/email_gateway.py:87`) — a log line with a redacted (domain-only)
  recipient and no persistent record, no Sentry breadcrumb, no admin-visible
  counter.

**Why it matters:** Resend (like every transactional email provider) will
hard-bounce permanently-invalid addresses and receive spam complaints from
recipients, and surfaces both via webhooks. Without consuming them, this app
has no way to know a user's email is undeliverable (so it will keep
"successfully" enqueuing sends to a dead address forever, compounded by
finding **E1** always marking those as job-success) and no way to detect a
complaint that could put the sending domain's reputation at risk. This is
lower-urgency than E1/E2/E3 because the app is not yet operating at a volume
where deliverability reputation is likely to be actively damaged, but it's a
real, growing-pain gap worth planning for before volume increases.

**Recommended fix:** add a `/webhooks/resend` route (mirroring the
authentication-then-size-cap-then-parse shape already established by
`/webhooks/revenuecat`) that consumes Resend's `email.bounced` /
`email.complained` events and, at minimum, logs them with enough context to
act on, and at best sets a per-user "email undeliverable" flag that the
welcome/receipt/reminder senders check before attempting a send.

**Do not:** block on this before E1 — a bounce/complaint handler is much less
valuable while every definite send failure (E1) is already being silently
swallowed with no operator visibility at all; fix the retry/DLQ gap first so
this handler has something meaningful to correlate against.

---

### Minor / lower-confidence items

---

**E5 — `delete_account`'s steps commit independently rather than atomically;
a process crash between the attachment-purge commit and the final
`delete_user` commit leaves a "half-deleted" account with no automatic
resume**
**Severity:** P3 (narrow window, self-healing via retry) · **Area:**
account-lifecycle · **Effort:** S–M

**Evidence:**

- `account_lifecycle.py:102-104`: `purge_attachments_for_user` is called,
  then `users_repo.delete_user` is called as a **separate** step.
  `attachments_repo.delete_rows` (`repositories/attachments.py:309-324`)
  defaults to `commit=True` and `purge_attachments_for_user`
  (`attachment_lifecycle.py:141`) calls it without overriding that default —
  so the attachment-row deletion is committed to Postgres **before**
  `delete_user`'s own bulk-delete-then-commit runs.
- If the process crashes (OOM-kill, deploy) between those two commits, the
  attachment rows and bytes are gone, but the user row, chats, messages,
  memories, todos, and connections are all still present and committed
  (nothing in that half rolled back, because it was never in the same
  transaction as the crash point).
- This is self-healing, not a permanent orphan: session purge is the *first*
  step of `delete_account` (`:80`), so by the time this crash window could
  occur the user's app session is already revoked, but their Google/Apple
  **sign-in** identity (a separate token from the calendar/Gmail integration
  tokens revoked in step 2) still matches the still-existing row — so the
  user can sign back in, land on their (now attachment-less) account, and
  either keep using it or tap "Delete account" again to finish the job
  cleanly (the second attempt's explicit deletes are idempotent against rows
  that are already gone).

**Why it matters:** for the narrow window where this can happen (a real
process crash exactly between two specific commits inside one request), the
practical consequence is bounded (recoverable by the user's own next login or
retry, no permanent data leak, no security exposure) — this is meaningfully
less severe than the background jobs review's J1/J3 crash-safety findings,
which affect a durable queue with no equivalent "the user notices and
retries" recovery path. Flagged here because the review brief asked to trace
what happens to data across a crash mid-deletion, and this is a real,
if narrow, answer.

**Recommended fix:** either wrap `purge_attachments_for_user` and
`delete_user` in one caller-owned transaction (pass `commit=False` through
both and commit once at the end of `delete_account`), or explicitly document
that deletion is a multi-phase, retry-safe operation by design and rely on
the user-facing retry path already described above. Given the low probability
and bounded blast radius, this is a "nice to have if touching this file for
another reason" fix, not an urgent one.

**Do not:** treat this as equivalent in urgency to J1/J3 — those affect a
background queue with no user-visible failure signal and no natural retry
trigger; this affects a synchronous request where the client already gets an
error and a retry button on failure.

---

**E6 — No one-click unsubscribe link / `List-Unsubscribe` header on the two
opt-in bulk email types (`todo_reminder`, `learning_nudge`)**
**Severity:** P3 (deliverability best-practice, not currently a compliance
blocker) · **Area:** transactional-email · **Effort:** S

**Evidence:**

- `_TEMPLATES["todo_reminder"]` / `_TEMPLATES["learning_nudge"]`
  (`transactional_email.py:413-439`) contain no unsubscribe link or
  `List-Unsubscribe` header, and `email_gateway.send_email`
  (`gateways/email_gateway.py:67-73`) never sets one on the outbound Resend
  payload.
- Both email types are already gated behind an opt-in, user-controlled
  setting (`User.email_reminders_enabled`, default `False`,
  `models/orm/user.py:60-62`), checked at the query level
  (`reminder_email.py:63,126`) — so there is a working, discoverable way for
  a user to stop these emails; it's an in-app Settings toggle rather than a
  link embedded in the email itself.

**Why it matters:** this is a real gap against current best practice (Gmail
and Yahoo's 2024 bulk-sender requirements expect one-click unsubscribe /
`List-Unsubscribe` headers for senders crossing their volume threshold), but
it is not currently a compliance blocker given the existing opt-in gate, and
the app is unlikely to be near the volume where a mailbox provider would
enforce this. Included as a forward-looking note, not a ranked urgent finding.

**Recommended fix:** add a `List-Unsubscribe` / `List-Unsubscribe-Post` header
(pointing at a simple, unauthenticated-by-token link that flips
`email_reminders_enabled` off) when volume or provider requirements make it
worth the small implementation cost. Low priority today.

---

## D. Answers to the review's explicit questions

1. **Is account deletion complete, or does it leave orphaned data in any
   secondary store?** Complete for Postgres (every content table, verified
   against real migration DDL) and for object storage (two independent
   backstops). Redis is either explicitly purged (sessions) or self-expiring
   (quota/usage, TTL-bound) and cannot collide across a delete→resignup cycle
   because the new account gets a fresh UUID. The one real "left behind
   indefinitely" store is **RevenueCat / the underlying store subscription**
   (finding **E3**) — not covered by anything in `delete_account`, and not
   coverable purely server-side for the store-level charge itself.

2. **Is there a race between deletion-in-progress and a still-logged-in
   session / concurrent background job?** Traced every plausible background
   job type (memory, todos, projects, topic, transactional_email,
   attachment_index, message_index, gmail_sync) to its actual row-lookup
   code, not just the handler wrapper: each one either loads a user/chat/
   attachment/connection row first and cleanly no-ops when it's gone
   (memory, topic, transactional_email, attachment_index, message_index,
   gmail_sync), or catches the resulting FK-violation exception and logs
   without re-raising or partially applying (todos, projects). None
   resurrect deleted data or write under an orphaned `user_id`. For a live
   session on another device, the WS layer explicitly re-verifies on every
   chargeable frame for exactly this reason (see "what's working"). **This
   is a swept-and-clean result, not a finding** — closest adjacent note: the
   `storage_sweep` job that finishes the R2 cleanup is itself one of the
   dedupe-keyed job types the background-jobs review's **J1** already flags
   as at risk of silent, permanent drop on a worker crash — and unlike most
   of J1's other affected job types (memory/todos/topic, which are
   best-effort enrichment), a dropped `storage_sweep` has no other recovery
   path at all (no admin re-trigger endpoint exists), so it's worth
   prioritizing J1's fix with this specific consequence in mind. This is a
   consequence of the already-documented J1, not a new finding.

3. **Does delete + re-signup with the same identity behave correctly?** Yes,
   traced through both Google and Apple sign-in and the dev-auth path: hard
   delete releases the `google_sub`/`apple_sub`/`email` uniqueness
   immediately, the next login takes the "new user" branch with a fresh
   random UUID, and nothing keyed by the old UUID (memories, quota, session
   state, RevenueCat identity on the same device) can attach to the new
   account. **Swept and clean.**

4. **Transactional email — anything beyond J4?** Yes — finding **E1**, which
   is a distinct, more consequential bug than J4 (guaranteed silent
   single-attempt-only on *any* failure, vs. J4's narrow double-send-on-
   ambiguous-timeout). No wrong-language email bug was found (locale
   fallback to `en` is deliberate and tested); no broken unsubscribe link was
   found because none exist for `welcome`/`receipt` (correctly, they're
   non-opt-out transactional mail) and the two opt-in types are gated by a
   working in-app toggle rather than an email-embedded link (**E6**, minor);
   no PII leak into logs was found (redacted recipient label, tested).

5. **Is there a GDPR export feature, and is it complete?** Yes, a real one
   exists (`GET /auth/me/export`, streamed, paginated, presigned attachment
   URLs) — but it is not complete: finding **E2** identifies five omitted
   user-owned tables, most importantly `suggested_reminders`, which stores
   verbatim Gmail content extracted about the user.

6. **Can a user trigger deletion/export of another user's data via parameter
   tampering?** No path found. Both endpoints resolve their target
   exclusively from the authenticated session (`Depends(get_current_user)`);
   neither accepts a user/account identifier from the request. The admin
   router has no parallel user-data-scoped endpoint either. **Swept and
   clean.**

---

## E. Explicit non-goals of this review

- **Re-litigating round 1–3 findings**, or J4/J5 from the background-jobs
  review — referenced only where directly adjacent (J1's consequence for
  `storage_sweep`, noted under Q2 above).
- **Auditing Resend's own infrastructure or SLAs.** This review covers what
  this codebase does with the provider's responses/failures, not whether
  Resend itself is a good choice of provider.
- **Determining whether RevenueCat's API can programmatically cancel an
  Apple/Google store subscription today.** Finding E3's recommended fix
  explicitly defers this to a documentation check against RevenueCat's
  current API rather than asserting an answer either way — Apple in
  particular is known not to support this via any third-party backend, but
  Play Store specifics were not verified against current RevenueCat/Google
  Play Developer API docs as part of this pass.
- **The mobile export file's on-device lifecycle after sharing.**
  `shareAccountExport` (`lib/exportData.ts:21-31`) writes the full export to
  the app's sandboxed cache directory before invoking the OS share sheet and
  does not delete it afterward — noted here for completeness but not raised
  as a ranked finding: the cache directory is app-sandboxed on both iOS and
  Android, so this requires physical/jailbroken device access to exploit,
  a materially different and much lower-likelihood threat model than any
  finding above.
- **Full attack-surface review of the Resend/RevenueCat gateways' own HTTP
  clients** (TLS config, timeout tuning beyond what's already
  present) — out of scope; this review focused on the account-lifecycle and
  email-correctness call chains, not generic HTTP-client hardening.
- **On-device/manual verification of the delete-account UI flow or a live
  Resend send.** All findings are from reading the actual code and tests and
  tracing real call chains (including cross-checking ORM `ondelete=` claims
  against the literal migration SQL rather than trusting the model
  annotation) — no live network calls, DB, or Resend/RevenueCat account were
  exercised as part of this review.
