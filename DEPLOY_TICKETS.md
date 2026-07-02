# Pre-launch tickets (from deployment readiness review)

## Code tickets — done

| # | Ticket | Status |
|---|--------|--------|
| 1 | Offline banner clears when link reconnects (ignore stale `isInternetReachable`) | done (#29) |
| 2 | Templates UI — browse built-in/user templates, start chat from template | done |
| 3 | Production gate: require R2 storage config (not ephemeral local disk) | done (#31) |
| 4 | Fly Docker build context + `.dockerignore` | done (#32, #35) |
| 5 | Mobile prod build: conditional `expo-dev-client`, remove hardcoded LAN `apiUrl` | done (#33, #36) |
| 6 | Production gate: require `GOOGLE_CLIENT_SECRET` | done (#34, #37) |
| 7 | LiteLLM chat stream timeout (hung provider) | done (#34, #38) |
| 8 | Global REST rate limiting (beyond auth/WS/link-preview) | done (#34, #39) |
| 9 | Hosted privacy/terms URLs (`GET /legal/privacy`, `/legal/terms`) | done |
| 10 | i18n cleanup — share, todo reminders, urgent todo copy | done |
| 11 | App Store ATS — `NSAllowsLocalNetworking` dev-only | done |
| 12 | Sentry (optional DSN) + request ID middleware | done |
| 13 | Prod checklist script (`scripts/prod-checklist.sh`) | done |

Follow-up PRs #35–#39: Docker README fix, EAS API URL gate, tests/docs for #6–#8.

---

## Remaining before public launch

### Ops — must do (no code)

**Fly API (`fly secrets set …`)**

- `ENVIRONMENT=production`, `DEV_AUTH_ENABLED=false`, `MOCK_LLM_ENABLED=false`
- `JWT_SECRET` (≥32 chars), `DATABASE_URL`, `REDIS_URL`
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `OPENROUTER_API_KEY`, `CORS_ORIGINS` (explicit list, not empty)
- `REVENUECAT_WEBHOOK_AUTH` (+ `REVENUECAT_SECRET_KEY` if monetizing)
- `OAUTH_TOKEN_ENCRYPTION_KEY` (Fernet)
- **R2:** `STORAGE_BACKEND=r2`, `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`
- Optional: `TAVILY_API_KEY` (web search), `RESEND_API_KEY` + `EMAIL_FROM` (transactional email), `SENTRY_DSN`, `CHAT_STREAM_TIMEOUT_SECONDS`, `REST_RATE_LIMIT_PER_MINUTE`

**Neon**

- Enable `vector` + `pg_trgm` (migrations 0027/0033/0009 assume them)
- Run `alembic upgrade head` (head: 0036)

**Upstash Redis**

- Production instance for quota, jobs, rate limits, WS fan-out

**Google Cloud**

- OAuth web client (API) + iOS/Android clients (mobile)
- OAuth consent screen + redirect URIs for Calendar/Gmail if using integrations

**Cloudflare R2**

- Create bucket, API token, CORS for presigned uploads

**EAS / store**

- `EXPO_PUBLIC_API_URL` in EAS secrets (production + preview)
- `EXPO_PUBLIC_EAS_PROJECT_ID`, Google iOS/web client IDs, RevenueCat keys
- Optional: `EXPO_PUBLIC_SENTRY_DSN` for mobile crash reporting
- `eas build --profile production` (iOS + Android)
- App Store Connect + Play Console: signing, listing, **hosted privacy policy URL** → `https://<api-host>/legal/privacy` (and `/legal/terms`)
- RevenueCat webhook → `https://<api>/webhooks/revenuecat`

**Deploy**

- `fly deploy` from repo root (build context `apps/api`)
- Monitor `GET /health/ready`

### QA — must do (manual)

- `./scripts/dev.sh check` green locally (mobile deps need your machine)
- `./scripts/prod-checklist.sh` (includes check gate + legal URL smoke if API is running)
- **On-device pass (iOS + Android dev/production builds):** Google Sign-In, WebView HTML/chart preview, push, RevenueCat, offline banner reconnect, core chat/regen/quota, templates sheet
- Verify attachments upload/download against **real R2** (not local disk)

### Recently shipped (post-launch hardening batch)

- **JWT refresh / logout / revocation** — 1h access tokens + 30d refresh (Redis); `POST /auth/refresh`, `POST /auth/logout`; mobile auto-refresh on 401
- **Job DLQ** — failed stream jobs copied to `recall:jobs:dlq` before ACK
- **Per-memory fact delete** — `DELETE /memories/{id}/facts/{index}` + mobile UI
- **DB session scope in `_prepare_chat_turn`** — attachment S3 + web search outside DB session
- **CI/deploy automation** — `.github/workflows/deploy.yml` (manual `workflow_dispatch`; Fly + optional EAS)
- **HTTP SSE chat fallback** — `POST /chats/{id}/messages/stream`; mobile falls back when WebSocket fails (send message only)

### Intentionally out of scope (v1)

- Tools/agents, non-web code execution, multi-user/teams
- SSE fallback for regenerate/edit (WebSocket-only today)

See also `FEATURES.md` → Pre-deployment TODO for overlapping detail.
