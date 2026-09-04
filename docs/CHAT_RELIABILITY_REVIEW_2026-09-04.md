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

## Local verification

- Mobile: 2,079 tests passed in 258 suites; TypeScript and ESLint passed. Existing warnings elsewhere remain.
- Backend: 3,272 tests passed; coverage 85.47%, above the unchanged 80% threshold. Ruff, format, and mypy passed.
- Web: TypeScript and ESLint passed.
- Regression cases were reproduced before their fixes. Existing React test harness lint failures were corrected without disabling rules. A live-DNS test now uses a deterministic resolver fixture.

The 26 real-PostgreSQL tests require CI validation: the local sandbox prevents PostgreSQL shared-memory initialization. Device checks and CI results must be recorded before treating this feature as release-verified. This review does not certify other features or the production deployment.
