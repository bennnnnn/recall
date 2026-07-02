# Pre-launch tickets (from deployment readiness review)

Code tickets only — ops items (Fly secrets, R2 creds, EAS signing, on-device QA) stay in `FEATURES.md`.

| # | Ticket | Status |
|---|--------|--------|
| 1 | Offline banner clears when link reconnects (ignore stale `isInternetReachable`) | done (#29) |
| 2 | Templates UI — browse built-in/user templates, start chat from template | done (#30) |
| 3 | Production gate: require R2 storage config (not ephemeral local disk) | done (#31) |
| 4 | Fly Docker build context + `.dockerignore` | done (#32) |
| 5 | Mobile prod build: conditional `expo-dev-client`, remove hardcoded LAN `apiUrl` | done (#33) |
| 6 | Production gate: require `GOOGLE_CLIENT_SECRET` | done (#34) |
| 7 | LiteLLM chat stream timeout (hung provider) | done (#34) |
| 8 | Global REST rate limiting (beyond auth/WS/link-preview) | done (#34) |

Deferred (judgment / needs external accounts): Sentry, JWT refresh/logout, job DLQ, per-memory delete UI, hosted privacy URLs.
