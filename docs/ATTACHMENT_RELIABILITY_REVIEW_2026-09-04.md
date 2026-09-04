# Attachment reliability review — 2026-09-04

Scope: selecting, uploading, opening, retaining, reusing, indexing, and deleting chat attachments, including the mobile Library. This follows the text-chat and session reviews. It does not certify the whole application as error-free or production-ready.

## Corrected behavior

- Late picker results and Library downloads cannot attach a file to a different conversation or account. An upload that succeeds before later send preparation fails retains its attachment ID for recovery, while newer composer text or files remain intact.
- API uploads use the shared session and token-refresh policy with a bounded timeout. Signed storage uploads and external previews do not receive Recall's bearer token. Native files are read through Expo File APIs, and changed file sizes are rejected.
- Download cache filenames cannot collide on matching URL suffixes. Downloads share in-flight work, check whether cached files still exist, and reject results from a departed account. Logout removes tracked cache files. Fullscreen previews bind cached content to the current file.
- Library requests cannot replace a newer filter, refreshed page, or cleared account cache. A deleted row cannot return from an older request. Pagination failures preserve the current rows and expose Retry.
- Temporary R2 failures are distinguished from missing objects, so verification does not purge files during a storage outage. Failed blob deletions remain eligible for cleanup retries after database records are removed. Reaping rechecks whether a row became a verified Library file or was linked while cleanup was pending.
- Local upload retries accept identical bytes and reject changes to an already verified file. Confirming an unfinished local upload reports a conflict. Failed Library reuse rolls back clone records and cleans up copied bytes.
- Chat acceptance validates requested attachment ownership and upload completion. Linking the user message and every attachment occurs in one transaction; a concurrent reuse conflict rolls back the unsaved message.
- An explicit attachment rejection removes the unsaved optimistic bubble and retains the original text and local file for **Restore draft**. Restoration waits for an empty composer and discards the rejected server attachment ID. It cannot overwrite newer text/files, regenerate a saved turn, or replay an accepted send. Recovery is scoped to the chat and signed-in session while the screen remains mounted; it is not durable across a full app restart.
- Index jobs use both attachment and chat identity for deduplication. Before replacing chunks, the worker locks the owning chat and attachment and verifies the current association. Deleted files, deleted chats, and old jobs from a reused Library file cannot write stale chunks.
- Attachment deletion relies on the existing foreign-key cascade to remove chunks. Removing redundant chunk-first deletes keeps deletion and indexing in the same lock order and avoids a deadlock between them.

## Validation

The final local revision passes:

- API: 3,335 tests, 85.65% coverage, full Ruff lint/format and mypy (600 source files).
- Mobile: 2,253 tests across 266 suites, TypeScript, and ESLint. Changed files have no lint warnings; the full checkout reports 166 existing warnings.
- Web: TypeScript build and ESLint.
- Whitespace/diff validation.

The first full mobile run exposed one test's missing native-session mock after the cache gained an auth-session dependency. Adding that mock made the final complete suite pass. Focused regressions also reproduced the wrong-chat picker, skipped pagination boundary, stale cache, rejected-send, and storage failure paths before their fixes.

Tests use isolated fake service settings and mocked storage/provider calls. Local validation does not migrate or write the configured development database. The 38 real PostgreSQL/pgvector tests are collected locally and run in CI, including 12 attachment cases for chunk ownership, deletion cascades, Library reuse, and cleanup predicates. CI results are attached to the PR.

## Remaining release verification

This review did not complete an authenticated native walkthrough of the final attachment revision. The earlier installed simulator binary lacked Apple signing entitlements. A compatible native development build and iOS/Android device checks remain necessary for camera/photo/document picking, native sharing, Photos permissions, and account transitions.

The inspected local configuration uses the local storage fallback. Production R2 credentials and live upload/confirm/download/delete behavior were not verified in this review; automated R2 tests mock the storage service. No deployment or production migration was performed.
