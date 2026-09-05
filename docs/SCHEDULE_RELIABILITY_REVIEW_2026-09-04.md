# Schedule reliability review — 2026-09-04

Scope: creating, completing, rescheduling and deleting dated reminders; Schedule's
calendar/suggestion views; badge state and local notifications; recurrence and delayed
server push persistence. Calendar/Gmail synchronization and extraction remain separate
features. This pass does not add undated lists or Learning-project linking.

## Fixed behavior

- Reminder creation omits the unsupported project field so the API accepts normal saves.
  Failed saves preserve the draft. Row actions roll back only their own changes, use the
  latest row, and remain exclusive across screen visits. A returned creation cannot
  duplicate the same row already observed by a list refresh.
- Account and focus ownership invalidate old dialogs and callbacks. Ordinary token
  refresh preserves the active draft. Android uses separate date and time dialogs and
  commits only a complete selection; cancellation and stale native callbacks cannot save
  partial dates. iOS retains its combined picker.
- The list loads every page before treating it as authoritative. Failed refreshes keep
  existing rows with Retry. Account changes reject old reads and setters; list/mutation
  coordination prevents older reads from undoing active changes.
- Calendar and suggestion failures retain useful rows and expose Retry. Opening a
  highlighted reminder selects its day once, allowing later manual navigation. Suggestion
  writes and cache recovery stay within their account across screen visits; stale reads
  cannot restore successfully dismissed suggestions or refill a disconnected cache.
- The provider owns local reminder synchronization after list and preference changes.
  Native writes run in order, and newer full-list intent supersedes older scheduling.
  Sign-out and cancellation wait for in-flight native work; background refresh does not
  prompt for notification permission. Seen/dismissed state is serialized and uses the
  configured reminder lead time.
- The API rejects null values for required fields and blank reminder text. Rescheduling
  resets delivery markers only when the final due date changes, including weekday
  snapping and chat/bulk edits. Equal timestamps have deterministic pagination order.
- Push delivery finalization updates only the unchanged occurrence that was sent. An
  early recurring delivery advances from that occurrence, preventing repeated sends in
  the lead window. Push-enabled reads leave undelivered occurrences for the worker;
  push-off reads catch up local recurrence without overwriting concurrent edits.
  Long catch-up spans no longer stop after 400 occurrences; timezone/DST behavior and
  the existing monthly clamping policy are preserved.

## Validation

Regression tests exercise the actual mobile hooks, provider, cache and request body,
with controlled delays for account changes, navigation, overlapping writes, failed
requests and native callbacks. Backend tests use local SQL for CRUD/chat/delivery
integration and PostgreSQL cases for conditional writes and ownership. Native services
and external providers are replaced by fixtures.

All 2,540 mobile tests passed across 290 suites. TypeScript and ESLint passed; changed
mobile files have no lint warnings, with 146 existing warnings elsewhere. The full
local API suite passed 3,415 tests with 85.88% coverage. Ruff, formatting and mypy passed. The 71 PostgreSQL tests, including nine new Schedule persistence cases,
run against CI's isolated database. Final CI results are recorded in the PR.
Local backend tests use a sanitized environment with live services blocked. No schema
migration or web code change is required.

## Remaining release checks

- Exercise iOS and Android dev builds: create, fail/retry, complete, delete, edit due
  dates, navigate away during saves, switch accounts, and choose/cancel both Android
  dialogs. Verify accessibility and keyboard layout on actual devices.
- Verify local alerts and server pushes under real OS permission states, foreground and
  background transitions, lead-time changes, timezones and recurring occurrences.
  Automated tests cannot establish native delivery behavior on a particular device.
- Review this PR after its prerequisite feature PRs. This feature pass does not certify
  the entire app as production-ready or error-free.
