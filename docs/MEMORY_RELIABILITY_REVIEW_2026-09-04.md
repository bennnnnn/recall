# Memory management reliability review — 2026-09-04

Scope: viewing and refreshing saved memory, editing sections, deleting sections/facts,
the learning toggle, and background persistence where it intersects manual changes.
Extraction prompts, recall ranking, and unrelated product features are unchanged.

## Fixed behavior

- Memory cache and UI work belong to the signed-in account. Old reads cannot refill
  an invalidated cache, and delayed dialogs cannot act after navigation or an account
  change. Auth-context updates reset editors without relying on the route rerendering;
  ordinary token refresh preserves current edits.
- Independent section mutations update only their own rows. Same-section writes remain
  exclusive across screen remounts, and completions reconcile the current account's
  cache even after the initiating screen closes. In-flight reads replay intervening
  mutations; failed edits and deletions refresh authoritative data after older reads settle.
- Failed refreshes retain saved rows and show Retry. Settings counts track cache changes
  and returning from the memory screen. The learning toggle cannot issue overlapping
  writes after navigation; stale completions cannot clear another account's busy state
  or display errors there.
- Long fact lists now collapse correctly. The section card has its own component;
  pending actions expose their disabled/busy state. Editing strips the server's date
  stamp, so a maximum-length saved section can be edited again. Fact selectors preserve
  their full text, handle incomplete Unicode safely, and accept the full persisted length.
- Manual edits and fact deletions keep text, vectors, JSON embeddings, and content
  hashes aligned. Failed embedding generation clears stale vectors instead of leaving
  deleted facts searchable. Manual changes invalidate both memory and Home caches.
- Background extraction/consolidation saves only sections that still match its input
  snapshot. Deleted rows are not recreated; competing new sections are not overwritten.
  Its short write transaction checks and locks the current learning setting. Delayed
  embedding responses update only the same account's unchanged text. Account deletion
  takes locks in the same order as the new memory write transaction.

## Validation

Regression tests cover account changes before React rerenders, context-only updates,
blur/refocus and unmount/remount, concurrent actions, optimistic rollback, stale list
responses, long fact selectors, and retry after an offscreen failure. Database tests
exercise manual/background write conflicts, disabled learning, deleted rows, stale
embeddings, ownership, and account-deletion lock ordering.

All 2,456 mobile tests passed across 282 suites. The full local backend suite passed
3,393 tests with 85.82% coverage. Ruff, formatting, mypy, mobile TypeScript, and ESLint
passed; changed mobile files have no lint warnings. The 62 real PostgreSQL tests,
including 13 new conditional-memory-write cases, run against CI's isolated database.
Final CI results are recorded in the PR. Local backend tests use a sanitized
environment with live services blocked. No production migrations or provider/storage calls
were made. Existing unrelated lint warnings remain; no web code changed.

## Remaining release checks

- Verify native iOS and Android keyboard/editor layout, long sections, delete
  confirmations, refresh and retry, account switching, and navigation during writes.
- Confirm a saved edit/delete is reflected in later real conversations and the learning
  toggle under staging provider latency. Automated tests replace providers with fixtures.
- This feature review does not certify the entire app as production-ready or error-free.
