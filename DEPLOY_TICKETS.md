# Pre-launch tickets (from deployment readiness review)

Code tickets only — ops items (Fly secrets, R2 creds, EAS signing, on-device QA) stay in `FEATURES.md`.

| # | Ticket | Status |
|---|--------|--------|
| 1 | Offline banner clears when link reconnects (ignore stale `isInternetReachable`) | done (#29) |
| 2 | Templates UI — browse built-in/user templates, start chat from template | done (#30) |
| 3 | Production gate: require R2 storage config (not ephemeral local disk) | in progress |
| 4 | Fly Docker build context + `.dockerignore` | pending |
| 5 | Mobile prod build: conditional `expo-dev-client`, remove hardcoded LAN `apiUrl` | pending |
| 6 | Production gate: require `GOOGLE_CLIENT_SECRET` | pending |
| 7 | LiteLLM chat stream timeout (hung provider) | pending |
| 8 | Global REST rate limiting (beyond auth/WS/link-preview) | pending |

Deferred (judgment / needs external accounts): Sentry, JWT refresh/logout, job DLQ, per-memory delete UI, hosted privacy URLs.
