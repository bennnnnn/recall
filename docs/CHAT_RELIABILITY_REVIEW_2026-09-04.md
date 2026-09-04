# Text chat reliability review — September 4, 2026

Scope: send, stream, stop, regenerate, persist, reopen, and paginate a text conversation.

## Corrected failure cases

- A connection callback or prepared send from an earlier view could interrupt or write into the current chat. Callbacks now carry a view identity, including navigation away and back to the same chat.
- Stop during a handshake or regeneration preparation could still dispatch the request. Pending attempts now respect cancellation; late stopped-stream frames cannot finish a newer turn.
- WebSocket authentication rejection could discard the attempted message before it was persisted. An explicit rejection before generation safely replays that request through the existing HTTP token-refresh flow.
- Interrupted SSE could end without a terminal event and leave the composer busy. Truncated streams now report failure and keep partial content marked incomplete.
- Stopping regeneration before replacement tokens could remove the original answer locally. The UI now retains the server's last committed answer.
- Opening cached history could indefinitely hide newer turns. Cached content appears immediately and is revalidated before sending.
- Older-message responses could populate another chat or duplicate a page. Pagination is single-flight, deduplicated, and tied to the requesting view.
- A foreground refresh could drop the current partial reply when an earlier assistant existed. Reconciliation now considers the latest turn.
- A fast follow-up could read history before the previous assistant committed. History and routing now wait for that save; a slow save returns a retriable busy error.
- Failed regeneration could delete original attachment bytes despite a database rollback. Storage cleanup now follows a successful commit.
- A post-commit refresh failure could misreport a saved reply and refund quota. The redundant refresh was removed.
- Failed background title scheduling could prevent saved history from opening. This remains best-effort.
- Malformed WebSocket frames or a pre-authentication disconnect could escape their lifecycle handlers. The stream producer remains owned and ordinary disconnects are handled.
- Ambiguous follow-ups such as “again” and “refresh” were intercepted as requests for the local time regardless of the conversation. Both the backend shortcut and mobile renderer had this defect. Only explicit time questions now take the instant-clock path; contextual follow-ups use ordinary chat generation and render the returned answer.

## PR feedback: rejected follow-up recovery

The [P1 review comment](https://github.com/bennnnnn/recall/pull/1185#discussion_r3938085217) correctly identified a gap: the strict finalize timeout rejects a follow-up before saving it, but the client left its optimistic user bubble in the transcript and offered Stop. Both transports can emit `start` before this rejection, so `start` is not evidence of persistence.

Explicit busy rejections now retain the original send payload in a queue for that chat, remove its unsaved optimistic bubble, and offer Retry. Retry submits the rejected content, model, attachment IDs and location context as a new send; it does not regenerate an earlier saved message. New composer text remains untouched, later rejected sends do not replace earlier ones, and reopening a chat within the mounted screen recovers its queued sends. Stop, account changes and stale callbacks cannot replay them. Generic errors and network failures are not treated as proof that a send was unsaved.

This recovery queue lasts for the mounted chat screen and signed-in session; it is not a durable offline outbox across a full app restart. Updated validation results are recorded on PR #1185.

The follow-up passed independent review and local backend validation: 3,298 tests with 85.55% coverage, full Ruff/format/mypy, and web TypeScript/lint. All 2,175 mobile tests across 263 suites passed, including 17 new transport, error recovery and UI regressions. Mobile TypeScript and lint also passed with no warnings in changed files.

## Local verification

- Mobile: 2,087 tests passed in 258 suites; TypeScript and ESLint passed. Existing warnings elsewhere remain.
- Backend: 3,281 tests passed; coverage 85.49%, above the unchanged 80% threshold. Ruff, format, and mypy passed.
- Web: TypeScript and ESLint passed.
- Regression cases were reproduced before their fixes. Existing React test harness lint failures were corrected without disabling rules. Generated `.expo` bundler files are excluded from source linting, matching their existing Git exclusion. A live-DNS test now uses a deterministic resolver fixture.

## CI verification

On commit `e4f847d0`, [PR #1185](https://github.com/bennnnnn/recall/pull/1185) passed Mobile CI, API CI, the production Docker image build, and CodeQL for Python, JavaScript/TypeScript, and Actions. API CI passed all 3,298 tests, including the 26 real-PostgreSQL tests unavailable locally, with 85.80% coverage. The local sandbox prevents PostgreSQL shared-memory initialization, so migrations and those database tests were run against CI's isolated PostgreSQL service.

The subsequent clock-shortcut correction adds nine backend and eight mobile regressions. Final revision checks are recorded on the linked PR; the local and device results here include that correction.

The separate automatic Advanced Security review could not start because GitHub's Copilot service returned “The requested model is not supported.” This did not affect the passing CodeQL analyses or application checks.

## Device verification and remaining scope

The iPhone 17 Pro Max simulator loaded the patched JavaScript from the source checkout and exercised local development sign-in, a synthetic text send, a completed answer, leaving/reopening the conversation, regeneration cancellation, and a successful send after Stop. A fresh conversation confirmed that “Again” retained the pineapple topic without an unrelated clock. Regeneration completed, and reopening first displayed cached history then revalidated to the newly saved regenerated answer with the composer enabled.

Reloading the Expo development session returned to sign-in and showed an `expo-notifications` registration/keychain warning. These observations are deferred to native startup/authentication review in `FEATURES.md`; they do not establish how a release build behaves. Existing lint warnings elsewhere remain. This review covers the core mobile text-chat lifecycle, not every feature, platform, dependency vulnerability, or the production deployment.
