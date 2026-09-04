# Chat management reliability review — 2026-09-04

Scope: rename, pin/unpin, archive/unarchive, delete, bulk actions, drawer consistency,
and reopening saved conversations. This review does not certify the whole app as
production-ready.

## Fixed behavior

- Generated titles use an atomic conditional database update. A manual rename wins
  against a delayed topic job. Short manual titles such as `AI` and `Chat` remain
  visible in API responses, the drawer, and the open chat.
- Pinned chats sort before the existing list limit, with stable ordering for ties.
  Archive always clears the database pin, even when another request pinned the
  chat after it was read. Pinning an archived chat returns a conflict.
- Header, drawer, and bulk actions share a per-chat mutation lock. Results stay in
  the account that started the action; header updates also stay in their original
  view. Confirmed deletion uses the registered new-chat action immediately.
- Bulk operations wait for every request to settle. Successful deletions remain
  deleted; only failed rows are restored. Archive rollback restores pins and the
  original activity group. Selection can retry failed items and includes archived
  chats; Archive is unavailable when every selected chat is already archived.
- Drawer cache reads cannot overwrite edits or restore a confirmed deletion.
  Account changes hide old rows immediately; normal access-token refresh preserves
  the current list and conversation. Pin/archive changes move rows into the right
  section and update the open chat's metadata.
- Title polling ignores stale account/view callbacks and manual-title changes,
  deduplicates concurrent polls, and clears its timers on unmount. Old title
  responses cannot overwrite a renamed conversation.
- History loading rejects stale pagination callbacks and responses after deletion
  or account changes. A confirmed 404 clears cached history and leaves the missing
  chat; temporary service failures retain the cached transcript.
- Disk history writes, patches, and deletes are ordered. Clearing a chat or signing
  out invalidates pending cache work, so an older write cannot recreate deleted
  history. Patching one message preserves the page's server-fetch timestamp.

## Validation

Regressions exercise delayed network responses, account changes before React
rerenders, repeated actions, navigation away and back, optimistic rollback, bulk
partial failure, cache invalidation, and concurrent title/pin/archive database
updates. Backend regressions execute SQL against isolated in-memory tables; the
PostgreSQL equivalents run in CI.

The full local backend suite passed 3,352 tests with 85.69% coverage. The 40 real
PostgreSQL tests were collected locally and are delegated to CI's isolated database.
Ruff, formatting, mypy, mobile TypeScript and ESLint, and web TypeScript and ESLint
passed. All 2,333 mobile tests passed across 272 suites. Final CI
results are recorded in the PR.
Local API validation used a sanitized environment with live services blocked; no
production database migrations or storage calls were made.

## Remaining release checks and deferred work

- Verify the final branch on native iOS and Android: header and drawer actions,
  multi-select partial failure, navigating during requests, background/foreground
  recovery, and account switching. Automated tests do not replace this device QA.
- Chat-list pagination beyond the current 200-row limit remains deferred; pinned
  rows now take priority within that existing limit.
- Search needs its own review. Existing search state can survive account changes
  while the drawer stays open; pagination validates query text rather than request
  identity, and query changes have a debounce window before invalidation. Search
  code is unchanged in this feature.
