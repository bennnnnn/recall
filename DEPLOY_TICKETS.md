# Recall — Public Deployment Runbook

Sequenced checklist from "code on main" to "live in the App Store / Play Store".
Code blockers are all resolved; what remains is provisioning, building, and QA.

> **Alembic head:** `0037` · **App/API version:** `1.0.0` / `0.1.0`
> Local gate: `./scripts/dev.sh check` (API: ruff + format + mypy + pytest ≥80%; mobile: typecheck + lint + jest).

---

## Code tickets — done (all on `main`)

| # | Ticket | Commit |
|---|--------|--------|
| 1 | Offline chat send gating (block + alert when offline) | `b1e21ed` |
| 2 | Background LLM call timeouts (60s, with fallback) | `64a5388` |
| 3 | Quota DB reconciliation (self-heal after Redis flush) | `73eaef0` |
| 4 | `custom_instructions` wired through profile + prompt + Settings UI | `431b37b` |
| 5 | Drop orphan `templates` table (migration `0037`) | `7c7517b` |
| 6 | Real mobile Sentry (`@sentry/react-native@8.16` + DSN env + plugin) | `8710879` |
| 7 | Job retry-before-DLQ (3×) + `list_dlq`/`replay_dlq` + admin router + CLI | `a5a1054` |
| 8 | Legal docs → hosted-only single source (`/legal/*`); in-app screens removed | `0097efe` |
| 9 | CI `docker-build` job (catch Dockerfile regressions on PRs) | `8cb5ed9` |
| 10 | Test isolation: per-test fake Redis for the REST rate limiter | `eaf93cf` |

Earlier batch (already on main): R2 prod gate, Fly Docker context + `.dockerignore`,
`expo-dev-client` dev-only + LAN `apiUrl` removed, EAS API URL guard, `GOOGLE_CLIENT_SECRET`
gate, LiteLLM stream timeout, global REST rate limit, hosted `/legal/*`, JWT refresh +
revocation, per-memory fact delete, SSE chat fallback, manual deploy workflow, prod-checklist script.

---

## Step 1 — Provision external services

- [ ] **Neon Postgres** (AWS us-east-2): create project, get `DATABASE_URL`.
      Enable extensions before migrating:
      `CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pg_trgm;`
- [ ] **Upstash Redis**: production instance → `REDIS_URL` (quota, jobs, rate limits, WS).
- [ ] **OpenRouter**: API key → `OPENROUTER_API_KEY` (all chat + embeddings route through it).
- [ ] **Cloudflare R2**: bucket + API token + CORS (for presigned uploads).
      → `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`.
- [ ] **Google Cloud**: OAuth consent screen; web client (API verify) + iOS + Android clients.
      Enable Calendar/Gmail scopes + redirect URIs if shipping integrations.
- [ ] **RevenueCat** (if monetizing): app-specific SDK keys + webhook auth secret.
      Webhook → `https://<api>/webhooks/revenuecat`.
- [ ] **Sentry** (optional but recommended): DSNs for backend + mobile.
- [ ] **Optional:** `TAVILY_API_KEY` (web search; DuckDuckGo fallback exists),
      `RESEND_API_KEY` + `EMAIL_FROM` (transactional email; mock in dev).

## Step 2 — Set Fly API secrets

`fly secrets set …` (all enforced at boot by `validate_production_settings`):

- [ ] `ENVIRONMENT=production`, `DEV_AUTH_ENABLED=false`, `MOCK_LLM_ENABLED=false`
- [ ] `JWT_SECRET` (≥32 chars), `DATABASE_URL`, `REDIS_URL`
- [ ] `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- [ ] `OPENROUTER_API_KEY`, `CORS_ORIGINS` (explicit list — not empty, not `*`)
- [ ] `REVENUECAT_WEBHOOK_AUTH` (+ `REVENUECAT_SECRET_KEY` if monetizing)
- [ ] `OAUTH_TOKEN_ENCRYPTION_KEY` (Fernet: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)
- [ ] **R2:** `STORAGE_BACKEND=r2`, `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`
- [ ] Optional: `SENTRY_DSN`, `CHAT_STREAM_TIMEOUT_SECONDS` (180), `BACKGROUND_LLM_TIMEOUT_SECONDS` (60), `REST_RATE_LIMIT_PER_MINUTE` (240)

## Step 3 — Migrate + deploy the API

- [ ] `cd apps/api && uv run alembic upgrade head` (head: `0037` — idempotent; safe to re-run)
- [ ] `fly deploy` from repo root (build context `apps/api`, Dockerfile migrates-then-starts)
- [ ] Verify `GET https://<api>/health/ready` → `{"status":"ok"}` (DB + Redis check)
- [ ] Smoke: `curl https://<api>/legal/privacy` and `/legal/terms` (hosted legal docs)

## Step 4 — EAS / store build

Set in **EAS dashboard → Secrets** (production + preview):

- [ ] `EXPO_PUBLIC_API_URL=https://<api>` (build fails without it — guarded in `app.config.ts`)
- [ ] `EXPO_PUBLIC_EAS_PROJECT_ID` (push; `npx eas init`)
- [ ] `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID`, `EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID`
- [ ] `EXPO_PUBLIC_DEV_AUTH_ENABLED=false`
- [ ] `EXPO_PUBLIC_REVENUECAT_IOS_API_KEY` / `EXPO_PUBLIC_REVENUECAT_ANDROID_API_KEY` (if monetizing)
- [ ] `EXPO_PUBLIC_SENTRY_DSN` (mobile crash reporting — needs the native build)

Build + submit:

- [ ] `eas build --profile production --platform all` (native build: Google Sign-In, WebView preview, push, RevenueCat, Sentry all require it — not Expo Go)
- [ ] App Store Connect + Play Console: signing creds, listing, **privacy URL** → `https://<api>/legal/privacy`, **terms URL** → `https://<api>/legal/terms`
- [ ] Submit for review

## Step 5 — QA (on-device, iOS + Android production builds)

- [ ] `./scripts/dev.sh check` green locally (mobile deps need your machine)
- [ ] `./scripts/prod-checklist.sh` (check gate + legal URL smoke if API running)
- [ ] Google Sign-In (iOS + Android)
- [ ] WebView HTML/JS + chart + Mermaid previews
- [ ] Push notifications (real device)
- [ ] RevenueCat purchase flow (if monetizing)
- [ ] Offline banner → send is blocked with alert → reconnect resumes
- [ ] Core chat: stream, stop, regenerate, edit, model picker, quota nudge
- [ ] Attachments upload/download against **real R2** (not local disk)
- [ ] Memory view + per-fact delete; Settings → Preferences (incl. Custom instructions)
- [ ] Legal links open hosted URLs from login + Settings → About

## Step 6 — Post-launch operations

- [ ] **DLQ replay** (if jobs fail in prod): `uv run python scripts/replay_dlq.py --list`
      then `scripts/replay_dlq.py` to re-enqueue; or dev-gated `GET/POST /admin/dlq[/*]`.
- [ ] Monitor Sentry (backend + mobile) and `GET /health/ready`.
- [ ] `JWT_SECRET` rotation: rotating invalidates all sessions (no graceful migration yet —
      refresh tokens are Redis-bound; document before doing it).

---

## Intentionally out of scope (v1)

- Tools/agents, non-web code execution, multi-user/teams
- SSE fallback for regenerate/edit (WebSocket-only today)
- In-app theme override beyond system/manual (no per-screen override)
- RTL layout (i18n ships 9 LTR locales)

See also `FEATURES.md` → Pre-deployment TODO and `CLAUDE.md` for architecture.
