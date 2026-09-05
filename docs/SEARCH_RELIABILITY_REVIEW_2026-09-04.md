# Search reliability review — 2026-09-04

Scope: drawer search, backend matching and pagination, and opening a matching
conversation/message. This review does not certify the whole app as production-ready.

## Fixed behavior

- Account, drawer, and query changes invalidate previous requests immediately,
  including the debounce window and returning to the same query. Old result presses
  cannot navigate or cancel a newer highlight. Access-token refresh preserves search.
- First-page failures offer Retry. Pagination failures retain existing results and
  retry the failed offset. Requests cannot overlap within one search; aborts, focus
  frames, and debounce timers are cleaned up on close and unmount.
- Query bounds match the API's trimmed 2–200 Unicode code points. URL encoding accepts
  incomplete Unicode input. Duplicate result rows are merged by chat/message identity
  while pagination offsets count all rows consumed from the API.
- SQL substring matching escapes percent signs, underscores, and backslashes while
  retaining existing trigram fuzzy matching. Message hits require ownership of both
  the message and its chat; archived conversations remain excluded.
- Result order has deterministic tie-breakers. One SQL statement returns the page
  and its total from the same database snapshot, including an empty out-of-range page.
- Selecting a message pages toward it only in the destination conversation/account.
  It waits for initial history loading, avoids repeatedly retrying a failed history
  cursor, and uses the latest row index when scrolling. Existing Load earlier remains
  available for manual retry. Navigation, another result, or a title selection in the
  same chat cancels obsolete targets and highlight timers.

## Validation

All 2,394 mobile tests passed across 277 suites. The full local backend suite passed
3,370 tests with 85.67% coverage. Ruff, formatting, mypy, mobile TypeScript, and ESLint
passed; changed mobile files have no lint warnings. Existing unrelated lint warnings
remain. No web code changed.

Regressions cover account changes before React rerenders, A→B→A query races, retained
row callbacks, token refresh, pagination retry/deduplication, timer cleanup, same-chat
title selection, older-history loading, Unicode bounds, ownership mismatches, SQL
wildcard escaping, equal timestamps, and empty-page totals. Backend tests execute SQL
against isolated tables. The 49 real PostgreSQL tests, including nine new search
regressions, run in CI; final results are recorded in the PR.

Local backend tests used a sanitized environment with live services blocked. No
production database migrations or storage calls were made.

## Remaining release checks and limits

- Native iOS/Android QA remains: type rapidly, close/reopen search, switch accounts,
  interrupt connectivity during either page, and open an old message from results.
  Check keyboard focus, list layout, scrolling, and highlight visibility on devices.
- The existing offset API stops at offset 10,000. Ordering is deterministic for
  unchanged data; separate pages are separate database snapshots. Concurrent inserts
  or deletes can shift offsets, so rerun the query to refresh changing results.
- Chat-list pagination beyond 200 rows remains a separate deferred feature.
