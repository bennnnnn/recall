# Recall — Billing / Subscription (RevenueCat) Review (Sep 2026)

Scope: the RevenueCat webhook handler, the REST gateway, how `user.plan` (free/pro) is
derived and kept in sync, and how Pro-gated features actually check that plan value.
Explicitly out of scope: the internal business logic of the gated features themselves
(Live Talk, image generation) — only their plan checks were verified.

Reviewed at `cursor/cross-domain-review-2026-09-05`. Primary files:
`apps/api/app/routers/webhooks.py`, `apps/api/app/services/revenuecat_webhook.py`,
`apps/api/app/services/subscription.py`, `apps/api/app/gateways/revenuecat_gateway.py`,
`apps/api/app/services/plan.py`, `apps/api/app/services/quota.py`,
`apps/api/app/routers/speech_realtime.py`, `apps/mobile/lib/purchases.ts`,
`apps/mobile/hooks/useBootstrapSync.ts`, `apps/mobile/components/UpgradeSheet.tsx`.

---

## A. Verdict

**The plan-sync core is unusually mature for a personal app's billing plumbing** — better
than most first builds ever get, and the git history (`e7e8e2c5`, `977a68a9`, `3e1cf71d`,
`b28d0264`, `9853734f`) shows a real sequence of hardening passes against exactly the bug
classes this review was asked to check: atomic dedup claim, per-user serialization, a
durable Postgres watermark against out-of-order redelivery, and a deliberate decision *not*
to downgrade on `BILLING_ISSUE`. The auth check is constant-time, runs before any body
parse, and fails closed (503) rather than open when misconfigured. Upgrades are never
trusted from the webhook payload — every `_PRO_EVENTS` / `TRANSFER` dispatch re-fetches the
subscriber's actual entitlement from RevenueCat's REST API before writing `plan="pro"`, so
an authenticated-but-forged payload cannot grant Pro to an arbitrary `app_user_id` on its
own say-so. There is no test gap here that matters: `test_routers.py` alone has ~35
dedicated webhook tests covering auth, dedup, staleness, transfer, and cancellation timing.

**But there is one finding that undermines all of that hardening, and it is the cheapest
possible fix in this report.** The webhook endpoint returns `204 No Content`
(`routers/webhooks.py:80`). RevenueCat's own docs are explicit: *"Your server should return
a 200 status code. Any other status code will be considered a failure by our backend."*
Every single successful delivery is currently reported to RevenueCat as a failure, which
queues up to 5 retries over 155 minutes and — because the endpoint never returns exactly
200 — permanently marks every event "failed" in RevenueCat's dashboard. The retries are
harmless today only because the rest of the pipeline happens to be idempotent by accident
of good design, not because anything currently in this endpoint or its tests notices the
mismatch. This is a one-line fix (F1) and it should ship before anything else here.

**The second finding is a genuine correctness gap, not a defensive nice-to-have.** RevenueCat
sends the *same* `CANCELLATION` event type for a voluntary auto-renew-off **and** for a
refund (`cancel_reason=CUSTOMER_SUPPORT`), and explicitly warns that a refund does not
necessarily flip the subscription's auto-renewal off — `expiration_at_ms` can still be a
real future date. `_cancellation_should_downgrade`
(`apps/api/app/services/revenuecat_webhook.py:112-119`) only ever looks at
`expiration_at_ms`; it never reads `cancel_reason`. A refunded user keeps Pro until the
store's next natural renewal/expiration point, even though Recall no longer has their
money. Every other upgrade-relevant code path in this same module (the six `_PRO_EVENTS`,
and `TRANSFER`) re-verifies against RevenueCat's REST API before trusting the payload;
`CANCELLATION` is the one branch that was deliberately hand-rolled to "keep Pro through the
paid period" (commit `3e1cf71d`) and that hand-rolled heuristic is exactly what breaks on
refunds.

**Third, and lower severity but directly the thing this review was asked to check:** there
is no backend reconciliation job. RevenueCat's own webhook docs recommend polling
`GET /subscribers/{id}` as the durable sync mechanism and treating webhooks as the trigger,
not the only source of truth. Recall does the opposite — webhooks (plus the RevenueCat SDK's
client-side `customerInfoUpdateListener`) are the *only* mechanism. If a webhook delivery is
lost (RevenueCat gives up after 155 minutes with no server-side retry queue on their end —
see F1) and the affected user does not reopen the app on the device that has Purchases
configured, `user.plan` in Postgres simply never corrects itself. There is no scheduled job
among the 15 modules in `apps/api/app/background/` that re-checks any Pro user's live
entitlement.

Everything else asked for in scope — the entry-point-only Live Talk plan check, the
mid-quota-window plan re-read, idempotent redelivery of `RENEWAL`/`EXPIRATION` — is solid
and is written up under "What's working" rather than as a finding.

---

## B. What's working (don't "fix" these)

- **Auth runs before any body work, and is constant-time.** `_verify_auth`
  (`routers/webhooks.py:40-60`) is called with only the `Authorization` header, before
  `await request.body()` (`routers/webhooks.py:89-91`). Comparison is
  `hmac.compare_digest` (`_secrets_match`, `routers/webhooks.py:31-37`), guarded by an
  ASCII check so a non-ASCII header 401s instead of leaking timing or 500ing the
  rate-limit-exempt route (`test_verify_auth_non_ascii_header_is_401`).
  Missing/wrong secret → `401`; missing secret *and* no explicit
  `DEV_ALLOW_UNAUTHED_WEBHOOKS` opt-in → `503` (fail closed, never fail open —
  `test_revenuecat_webhook_503_when_no_auth_and_no_dev_opt_in`).
- **Production cannot boot without the secret.** `validate_production_settings`
  (`core/config.py:432-434`) requires `REVENUECAT_WEBHOOK_AUTH` non-empty whenever
  `environment != "development"`, called from `process_bootstrap.initialize_process` in the
  FastAPI `lifespan` (`main.py:40-42`) — a missing secret fails app startup, not just one
  request. Because `_verify_auth`'s dev bypass only triggers when the secret string is
  empty (`routers/webhooks.py:40-47`), `DEV_ALLOW_UNAUTHED_WEBHOOKS=true` is inert in any
  environment where the secret is actually configured — the two guards can't be
  independently misconfigured into a hole.
- **An authenticated payload still can't self-grant Pro.** Every `_PRO_EVENTS` dispatch and
  `TRANSFER` re-fetches the subscriber from RevenueCat's REST API
  (`subscription.resolve_plan_from_revenuecat`, `revenuecat_webhook.py:174,182`) and never
  trusts the webhook body's own entitlement claims — `resolve_plan_from_revenuecat` "Never
  defaults to `pro`" (`subscription.py:61-62`) and returns `None` (deferring, not
  free-defaulting) when the secret is missing or the fetch fails
  (`resolve_plan_from_revenuecat`, `subscription.py:60-71`). Downgrades (`CANCELLATION` when
  due, `EXPIRATION`) are the one place the webhook is trusted directly — the correct
  asymmetry, since revoking access on a forged-but-authenticated payload is the safe
  failure direction.
- **Idempotency is layered, not single-point.** Three independent mechanisms, each
  covering a different failure mode: (1) a Redis `SET NX` in-flight claim
  (`_try_claim`, `revenuecat_webhook.py:138-146`) with a 120s TTL so a crash mid-processing
  self-heals instead of wedging the event forever; (2) a 24h Redis done-marker
  (`_already_processed`, l.134-136) for cheap replay-skip; (3) a **durable Postgres**
  per-user watermark (`users.rc_last_event_at_ms`, migration `0060`) that rejects
  out-of-order events regardless of whether the Redis keys have expired
  (`is_stale_rc_event`, `subscription.py:18-31`, checked at `revenuecat_webhook.py:272-287`).
  Even past the 24h Redis TTL, the DB watermark is still the actual source of truth for
  ordering. On top of all three, the terminal state-write itself is idempotent by
  construction: `apply_plan_for_app_user_id` returns `False` (no-op, no duplicate receipt
  email) when `user.plan == plan` already (`subscription.py:102-105`), so even a fully
  expired dedup key redelivers into a harmless no-op for `RENEWAL`/`EXPIRATION` unless the
  plan has genuinely changed. `test_revenuecat_webhook_dedups_replay_by_event_id`,
  `test_revenuecat_webhook_newer_expiration_still_applies_after_purchase`,
  `test_revenuecat_webhook_ignores_stale_expiration_after_purchase` all exercise this.
- **A failed attempt does not burn the dedup key.** The done-marker is set only *after*
  `_dispatch_event` succeeds (`revenuecat_webhook.py:304-305`, inside the `try`, guarded by
  `finally` releasing the subscriber lock regardless) — `subscription_service.
  apply_plan_for_app_user_id` raising mid-processing leaves the event unmarked so
  RevenueCat's own retry can complete it
  (`test_revenuecat_webhook_failed_processing_does_not_burn_dedup_key`,
  `test_revenuecat_webhook_transfer_failure_does_not_dedup`).
- **`BILLING_ISSUE` and `SUBSCRIPTION_PAUSED` correctly do nothing.** Neither is in
  `_PRO_EVENTS`, `_FREE_EVENTS`, or specially handled in `_dispatch_event`
  (`revenuecat_webhook.py:149-207`), so both fall through as no-ops — this is exactly what
  RevenueCat's docs instruct ("Don't revoke access on `BILLING_ISSUE`" / "revoke only on the
  `EXPIRATION` that follows `SUBSCRIPTION_PAUSED`"), and it's a real regression test
  (`test_revenuecat_webhook_billing_issue_does_not_downgrade`, commit `b28d0264`).
- **Downgrade is not "next login only."** `quota.py`'s plan-dependent limits
  (`_plan_limit`, l.56-57; `live_talk_limit_for_user`, l.424-425; and every other
  `_plan_limit(user, ...)` call) read `user.plan` fresh from the row loaded for *this*
  request — there is no per-session cache of plan on the backend. A webhook-driven
  downgrade is visible on the very next HTTP/WS request after it commits, not at next
  login.
- **Live Talk's plan check is correctly entry-point-only, and that's the right call, not a
  gap.** `_reserve_realtime_or_raise` checks `plan_service.is_pro(user)` once, when minting
  the ephemeral OpenAI Realtime session (`speech_realtime.py:100-107`). After that, media
  flows directly between the mobile client and OpenAI over WebRTC — the backend is not in
  the audio path and has nothing to re-check mid-call. The session token itself is
  short-lived (`RealtimeSessionOut.expires_at`); a plan flip mid-call cannot extend Pro
  access beyond that token's natural expiry, and the `/speech/live/tool` and
  `/speech/live/persist` follow-ups either re-check `is_pro` (`speech_realtime.py:267`) or
  only persist a turn that already happened, so there's no privileged action left ungated.
- **`resolve_plan_from_revenuecat` degrades safely on gateway failure.** `fetch_subscriber`
  catches every exception, reports it (`revenuecat_gateway.py:34-51`), and returns `None`;
  callers treat `None` as "defer" (return `False`, don't dedupe, let RevenueCat retry) —
  never as "assume free" or "assume pro" (`test_revenuecat_webhook_pro_event_defers_when_
  entitlement_unresolved`, `test_handle_revenuecat_transfer_does_not_downgrade_when_fetch_
  fails`).
- **TRANSFER resolves the target's plan from the API before writing anything, and upgrades
  before downgrading.** `handle_revenuecat_transfer` (`subscription.py:111-154`) fetches the
  new `app_user_id`'s plan first, bails without touching the DB if that fetch fails, then
  upgrades the target and only *then* downgrades the `transferred_from` sources — so a
  failed target-plan sync can retry without having already stranded the old id on `free`
  (commit `9853734f`, `test_handle_revenuecat_transfer_downgrades_old_and_syncs_new`).
- **Test coverage on the plumbing itself is genuinely good.** `test_routers.py` has ~35
  webhook-focused tests (auth 401/503/oversized-body, sandbox-in-prod, dedup by `event_id`
  and by payload hash, in-flight `SubscriberBusyError`, stale-by-timestamp, transfer
  success/failure/malformed, cancellation future-vs-past expiry, billing-issue no-op,
  expiration always-downgrades) plus `test_subscription.py`'s unit coverage of
  `apply_plan_for_app_user_id`, the watermark, and transfer. This is not a "missing tests"
  finding.

---

## C. Findings — ranked

---

**F1 — The webhook endpoint returns `204`; RevenueCat's backend only accepts exactly `200`
as success, so every delivery is recorded as a failure and gets retried**
**Severity:** P0 · **Area:** webhook contract · **Effort:** S

**Evidence:**
`apps/api/app/routers/webhooks.py:80`:
```python
@router.post("/webhooks/revenuecat", status_code=status.HTTP_204_NO_CONTENT)
async def revenuecat_webhook(...) -> None:
```
RevenueCat's webhook docs (https://www.revenuecat.com/docs/integrations/webhooks, verified
live, September 2026): *"Your server should return a 200 status code. Any other status code
will be considered a failure by our backend. RevenueCat will retry later (up to 5 times)
with an increasing delay (5, 10, 20, 40, and 80 minutes). After 5 retries, we will stop
sending notifications."* The RevenueCat dashboard's "failed events" filter is literally
defined as "events not responded to with a 200 status code" (RevenueCat community answer,
`wes_clark`, RevenueCat staff). No test in this repo asserts the response status code of a
successful webhook call — every `test_revenuecat_webhook_*` test checks `r.status_code ==
204` as if that were the contract to preserve, which is exactly backwards.

**Why it matters:** this doesn't cause an observable bug *today* only because
`apply_plan_for_app_user_id` is idempotent — the correct plan is already written on delivery
attempt 1, so attempts 2-6 (arriving up to 155 minutes later) reprocess into no-ops. But it
means: (1) every event in RevenueCat's dashboard shows as permanently failed, so there is no
way to use RevenueCat's own delivery-health view to notice a *real* regression; (2) up to 6x
redundant load on this endpoint (DB round-trip, Redis lock, REST fetch to RevenueCat) per
event, for 155 minutes, for literally every purchase/renewal/cancellation in the app; (3) if
RevenueCat's redelivery window (155 minutes total) elapses before a slow/rate-limited
`resolve_plan_from_revenuecat` REST fetch ever succeeds, RevenueCat gives up and there is no
way to replay the event — "we don't have the ability to replay failed events after the retry
period ends" (RevenueCat support, community forum) — so on a real transient RevenueCat REST
outage, the retry budget is being silently spent 6x faster than it needs to be, on 5 wasted
attempts that were never going to be acknowledged as successful in the first place.

**Recommended fix:** change the success path to `status_code=status.HTTP_200_OK` (a bare
`Response(status_code=200)` or `return {}` with the decorator's default). Update every
`assert r.status_code == 204` in `test_routers.py`'s ~30 webhook tests to `200`. Add one new
test asserting the literal status code is `200` (not just "2xx") so this can't silently
regress back to `204`/`201` in a future refactor.

**Do not:** change the `413`/`400`/`401`/`503`/`503(SubscriberBusyError)` error status codes
— those are correctly non-200 today and RevenueCat retrying an event that genuinely didn't
process (bad auth aside, which won't self-heal via retry) is the intended behavior for those
paths.

---

**F2 — `CANCELLATION` downgrade timing only looks at `expiration_at_ms`; it never reads
`cancel_reason`, so a store-issued refund does not revoke Pro until the (unrelated,
still-active) subscription period naturally ends**
**Severity:** P1 · **Area:** plan-sync correctness · **Effort:** S

**Evidence:** `apps/api/app/services/revenuecat_webhook.py:112-119`:
```python
def _cancellation_should_downgrade(payload: dict[str, Any]) -> bool:
    milliseconds = _int_field(payload, "expiration_at_ms")
    if milliseconds is None:
        return True
    try:
        return datetime.fromtimestamp(milliseconds / 1000.0, tz=UTC) <= datetime.now(tz=UTC)
    except (OverflowError, OSError, ValueError):
        return True
```
called from the `CANCELLATION` branch of `_dispatch_event` (`revenuecat_webhook.py:195-203`),
which never inspects the payload's `cancel_reason` field at all. RevenueCat's own
`CANCELLATION` event doc: *"A subscription or non-renewing purchase was canceled or
refunded... In the case of refunds, a subscription's auto-renewal setting may still be
active"* (RevenueCat "Event Types and Fields" docs, `cancel_reason` values table:
`CUSTOMER_SUPPORT` = *"Customer received a refund from Apple support... Note that this
doesn't mean that a subscription's autorenewal preference has been deactivated since
refunds can be given without canceling a subscription."*). RevenueCat's sample `CANCELLATION`
payload for a refund carries `"cancel_reason": "CUSTOMER_SUPPORT"` alongside a negative
`"price": -9.99` — with `expiration_at_ms` left pointing at whatever the (unaffected,
still-auto-renewing) subscription's real period end is. The existing test suite only
exercises `expiration_at_ms` in the far future/far past
(`test_revenuecat_webhook_cancellation_with_future_expiry_keeps_pro`,
`test_revenuecat_webhook_cancellation_with_past_expiry_downgrades`) — neither test sets
`cancel_reason`, so there is no coverage of the refund case at all.

**Why it matters:** commit `3e1cf71d` ("keep Pro through paid period on RevenueCat cancel")
correctly fixed the *voluntary* cancel case — a user who just turns off auto-renew keeps what
they paid for. But `CANCELLATION` is the same event type RevenueCat uses for refunds, and the
heuristic that fixed the voluntary case is precisely wrong for the refund case: a refunded
user has their money back but — under the current code — keeps Pro (higher quotas, Live
Talk, image generation) until whatever future `expiration_at_ms` the still-nominally-active
subscription carries. This is the one path in this module that never calls
`resolve_plan_from_revenuecat` at all, unlike every `_PRO_EVENTS` member and `TRANSFER` — it
is the one place trusting the raw webhook payload for something the underlying entitlement
state can directly answer.

**Recommended fix:** on `CANCELLATION`, check `cancel_reason` (add a `_string_field(payload,
"cancel_reason")` helper next to the existing `_string_field` accessors) — when it is
`"CUSTOMER_SUPPORT"` (a refund), downgrade immediately via `resolve_plan_from_revenuecat`
(re-fetch, don't just blind-set `free`, in case a separate active purchase already restored
access) rather than deferring on `expiration_at_ms`. For every other `cancel_reason`, keep the
existing period-end heuristic unchanged. This matches RevenueCat's own general
recommendation to call `GET /subscribers` after any webhook rather than hand-rolling
per-event-type logic, while preserving the specific "keep Pro through the paid period" fix
this codebase already earned for the voluntary case.

**Do not:** revert to unconditionally trusting `resolve_plan_from_revenuecat` on every
`CANCELLATION` (that was tried and reverted for exactly the reason `3e1cf71d` exists —
voluntary cancels must not strip a paid period). Scope this to the refund `cancel_reason`
only.

---

**F3 — No backend reconciliation job; `user.plan` has no fallback path when a webhook is
lost and the user never reopens the app on a Purchases-configured device**
**Severity:** P2 · **Area:** plan-sync robustness · **Effort:** M

**Evidence:** `apps/api/app/background/` has 15 modules (`attachment_indexing.py`,
`attachment_orphan_reaper.py`, `compaction.py`, `email_reminder_scheduler.py`,
`gmail_periodic_sync.py`, `gmail_sync.py`, `handlers.py`, `memory_consolidation.py`,
`memory_extraction.py`, `message_indexing.py`, `periodic.py`, `project_sync.py`,
`push_scheduler.py`, `suggestion_generation.py`, `todo_sync.py`, `topic_generation.py`) —
none references `subscription`, `revenuecat`, or `plan`. `sync_user_plan_from_revenuecat`
(`services/subscription.py:74-84`) has exactly one production caller:
`POST /auth/me/sync-subscription` (`routers/auth.py:298-311`), which is only ever invoked
from the mobile client — either the user tapping subscribe/restore in `UpgradeSheet.tsx`
(`syncAfterStore`, l.69-73), or the RevenueCat SDK's `customerInfoUpdateListener` firing on
this device (`useBootstrapSync.ts:109-149`), which the code's own comment describes as the
actual backstop: *"The webhook may fail or lag; this listener closes the gap without relying
on a manual sync."* That listener only fires on **this device**, on purchase/restore, or when
the RevenueCat SDK's own foreground refresh notices a change — it cannot fire for a user who
does not reopen the app.

**Why it matters:** RevenueCat's own webhook docs recommend exactly the opposite architecture
for durability: *"we recommend calling the `GET /subscribers` REST API endpoint after
receiving any webhook... has the added benefit of making your system more robust and
scalable"* — i.e., treat webhooks as a trigger and rely on polling/reconciliation as the
system of record, not the other way around. Recall's design instead makes the webhook (a
best-effort, at-least-once — but per F1, not even correctly acknowledged — delivery) the
*only* server-side path, backstopped only by a client listener that requires the specific
device to be foregrounded again. A user who cancels or gets refunded outside the app (App
Store/Play Store settings), then never reopens Recall, or opens it on a different device (RC
`appUserID` is the Recall UUID, but a fresh install without `configurePurchases` running,
or a future web client mentioned as planned in `CLAUDE.md`, has no RevenueCat SDK at all) has
no path back to `free` other than a dropped/exhausted webhook eventually resolving on its
own — which F1 shows is not even self-healing on RevenueCat's side after 155 minutes.

**Recommended fix:** add a low-frequency scheduler (the existing `background/periodic.py` +
`push_scheduler.py`-style pattern) that pages through users with `plan == "pro"` and a
`rc_last_event_at_ms` older than N hours, calls `resolve_plan_from_revenuecat` for each, and
applies via the existing `apply_plan_for_app_user_id` (already idempotent, already
watermark-guarded). Batch/rate-limit against RevenueCat's REST API; this does not need to run
more than once or twice a day. This closes the gap for exactly the population that matters —
users the webhook or the client listener never reached — without duplicating any dispatch
logic.

**Do not:** poll every user on every plan — only Pro users need re-verification (free users
have nothing to revoke); don't replace the webhook with polling — webhooks remain the fast
path, this is a backstop only, matching RevenueCat's own stated architecture.

---

**F4 — `REFUND_REVERSED` (access should be re-granted after a clawed-back refund) is not a
recognized event type and silently no-ops**
**Severity:** P3 · **Area:** plan-sync completeness · **Effort:** S

**Evidence:** `_PRO_EVENTS` / `_FREE_EVENTS` / `_ORDERED_EVENTS`
(`revenuecat_webhook.py:24-35`) and the `_dispatch_event` if-chain
(`revenuecat_webhook.py:149-207`) handle `TRANSFER`, the six `_PRO_EVENTS`, `CANCELLATION`,
and `EXPIRATION` — `REFUND_REVERSED` falls through to `_dispatch_event`'s final `return
False` with no action taken. RevenueCat's docs: *"`REFUND_REVERSED` — A refund was
reversed"* — the customer's access should be restored.

**Why it matters:** this is App Store-only, and rare (a support agent or Apple reversing a
previously issued refund). Because the event isn't marked `processed` (the `False` return
skips both the watermark advance and the done-marker), a well-timed later event for the same
user still resolves correctly, and the client-side `registerPlanChangeListener` backstop
(the same one flagged as insufficient in F3) will eventually pick up the re-instated
entitlement on next foreground. This is the same class of gap as F3, just for a rarer event —
worth fixing alongside F3's reconciliation job rather than as a special case.

**Recommended fix:** add `REFUND_REVERSED` to `_PRO_EVENTS` (it re-verifies via
`resolve_plan_from_revenuecat` exactly like the other members, so it can't blind-grant
`pro` — it will only apply `pro` if the subscriber's live entitlement is actually active
again).

**Do not:** treat this as urgent enough to block F1/F2 — it's the correct next line to add,
not a new mechanism.

---

**F5 — `TRANSFER`'s per-old-id downgrade is not lock-protected**
**Severity:** P3 · **Area:** concurrency · **Effort:** S

**Evidence:** `process_event` (`revenuecat_webhook.py:264-269`) takes the subscriber lock
only for the *new* `app_user_id` before dispatch. Inside `_dispatch_event`'s `TRANSFER`
branch, `handle_revenuecat_transfer` (`subscription.py:150-153`) downgrades each
`transferred_from` id via `apply_plan_for_app_user_id` with no lock held on that old id at
all.

**Why it matters:** if RevenueCat (rarely, but the docs describe "at least one delivery", not
"exactly one, in order") delivers a `RENEWAL` for the *old* id concurrently with the
`TRANSFER` that's downgrading it, the two writes race with no serialization between them —
last-write-wins on `users_repo.update`. The DB watermark (`is_stale_rc_event`) only rejects
strictly-older `event_timestamp_ms`; two events racing at the DB layer with no ordering
guarantee between separate connections aren't protected by it. This is a narrow, low-frequency
window (transfer + a same-instant event on the abandoned old id) and not something the
existing test suite exercises.

**Recommended fix:** acquire the same per-`app_user_id` lock (`_subscriber_lock_key`) for
each `transferred_from` id inside `handle_revenuecat_transfer`, or — simpler — have
`process_event` take locks for the full set of ids (`app_user_id` + all `transferred_from`)
before dispatch on `TRANSFER` specifically.

**Do not:** generalize this into a multi-key locking primitive for every event type — only
`TRANSFER` touches more than one `app_user_id` per event.

---

## D. Weak / unwanted / missing inventory

| Item | Status | Evidence | Recommend |
|---|---|---|---|
| Webhook success status code | **Wrong** (204, RC requires exactly 200) | `routers/webhooks.py:80` | Fix now (F1) |
| `CANCELLATION` refund handling | **Missing** (no `cancel_reason` check) | `revenuecat_webhook.py:112-119` | Fix now (F2) |
| Backend reconciliation / polling backstop | **Missing** | no `background/*` module references subscription | Add (F3) |
| `REFUND_REVERSED` event | **Missing** (silent no-op) | `revenuecat_webhook.py:149-207` | Add (F4) |
| `TRANSFER` old-id lock | **Weak** (unlocked concurrent write) | `subscription.py:150-153` | Harden (F5) |
| Webhook auth (constant-time, fail-closed, pre-parse) | **Solid** | `routers/webhooks.py:31-60,89-91` | Keep as-is |
| Upgrade-path REST re-verification | **Solid** | `revenuecat_webhook.py:174,182`; `subscription.py:60-71` | Keep as-is |
| Idempotency (3-layer: Redis claim, Redis done-marker, Postgres watermark) | **Solid** | `revenuecat_webhook.py:134-146,226-309`; `subscription.py:18-49` | Keep as-is |
| `BILLING_ISSUE` / `SUBSCRIPTION_PAUSED` no-op | **Solid** (matches RC guidance) | `revenuecat_webhook.py:24-35,149-207` | Keep as-is |
| Downgrade propagation timing (no plan cache) | **Solid** | `quota.py` reads `user.plan` per-request | Keep as-is |
| Live Talk entry-point-only plan check | **Solid** (nothing left to re-check mid-call) | `speech_realtime.py:100-134,256-274` | Keep as-is |
| Webhook test coverage | **Solid** (~35 tests) | `test_routers.py` webhook section | Keep as-is; add F1/F2 coverage |
| HMAC signature verification (`X-RevenueCat-Webhook-Signature`) | **Not used** (shared-secret `Authorization` only) | RC docs offer HMAC as "stronger verification"; not implemented here | Optional hardening, not a vulnerability — defer |

---

## E. Sequenced fix plan

1. **`fix(api): return 200 (not 204) from the RevenueCat webhook`** — F1.
   *First: one line, zero behavior risk, and it's the only finding that affects every single
   webhook delivery today.* Update the ~30 `assert r.status_code == 204` webhook tests to
   `200`; add one test pinning the literal code.

2. **`fix(api): revoke Pro immediately on a refunded CANCELLATION (cancel_reason=CUSTOMER_SUPPORT)`**
   — F2. *Second: real, evidenced revenue-correctness gap; small, isolated diff in
   `_dispatch_event`'s `CANCELLATION` branch.* Add a test with `cancel_reason:
   "CUSTOMER_SUPPORT"` and a far-future `expiration_at_ms` asserting immediate downgrade,
   alongside the existing voluntary-cancel tests (which must keep passing unchanged).

3. **`feat(api): periodic RevenueCat entitlement reconciliation for Pro users`** — F3.
   *Third: the only finding here that's genuinely new code (a scheduler), size it after the
   two one-line fixes land.*

4. **`fix(api): handle REFUND_REVERSED as a pro-verifying event`** — F4. One line in
   `_PRO_EVENTS`; fold into the same PR as F3 since both are "webhook completeness."

5. **`fix(api): lock transferred_from ids during RevenueCat TRANSFER downgrade`** — F5.
   Smallest, most isolated; last because it's the lowest-severity, narrowest-window item.

---

## F. Explicit non-goals

- **Rewriting the dedup/lock architecture.** The three-layer idempotency design (Redis
  claim → Redis done-marker → Postgres watermark) is sound and load-bearing; nothing here
  proposes touching it.
- **Adding HMAC signature verification.** RevenueCat offers it as a stronger alternative to
  the shared-secret `Authorization` header, but the current constant-time shared-secret
  check, combined with the REST re-verification on every upgrade path, is not a
  demonstrated vulnerability — it's the design `CLAUDE.md` already documents as intended.
  Worth a future look if the shared secret ever needs stronger replay protection, not a
  finding here.
- **Touching the Live Talk / image-generation business logic.** Their plan *checks* were
  verified and found correct (entry-point gates, no finding needed); their internal
  quota/session logic is explicitly out of scope per this review's brief.
- **Auto-disabling or alerting inside the app when RevenueCat marks an event "failed."**
  That's a symptom of F1, not a separate problem to solve — fixing F1 removes the false
  failures entirely.
