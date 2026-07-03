# Recall — Public Deployment Runbook

Sequenced checklist from "code on main" to "live in the App Store / Play Store".
Code blockers are all resolved; what remains is provisioning, building, and QA.

> **Alembic head:** `0038` · **App/API version:** `1.0.0` / `0.1.0`
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

- [ ] `cd apps/api && uv run alembic upgrade head` (head: `0038` — idempotent; safe to re-run)
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
- [ ] Sign in with Apple (iOS only — not shown on Android)
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

## Appendix A — RevenueCat setup (Pro subscriptions)

Use a **new RevenueCat project** named **Recall**. Do not reuse old projects (e.g. Africana).

**Billing site:** [https://app.revenuecat.com](https://app.revenuecat.com)

### Naming (Recall vs other products)

| Name | Can you use "Recall"? |
|------|------------------------|
| RevenueCat project label | Yes — dashboard label only |
| App Store display name | Yes — many apps share "Recall"; bundle ID must be unique |
| Bundle ID | **`com.recall.app`** (already in `app.json`) |
| Entitlement ID | **`pro`** — hard-coded in app; do not rename |
| Anthropic Claude "memory/recall" features | Not a product trademark blocker |
| [recall.it](https://www.recall.it/) AI knowledge app | Same category — consider a distinct App Store subtitle |

### Step-by-step

1. **New project:** RevenueCat dropdown → **+ New project** → name **`Recall`**.
2. **Add iOS app:** **Apps → + New → Apple App Store**
   - App name: `Recall`
   - Bundle ID: **`com.recall.app`**
3. **Entitlement:** **Product catalog → Entitlements → + New**
   - Identifier: **`pro`**
4. **App Store Connect subscription** (before RevenueCat products):
   - [appstoreconnect.apple.com](https://appstoreconnect.apple.com) → your app
   - **Subscriptions** → group e.g. `Recall Pro`
   - Product ID e.g. **`recall_pro_monthly`** (monthly)
5. **RevenueCat product:** **Product catalog → Products → + New**
   - Link `recall_pro_monthly` → entitlement **`pro`**
6. **Offering:** **Product catalog → Offerings**
   - Create `default`, mark **Current**
   - Add **Monthly** package → `recall_pro_monthly`
7. **API keys** (Recall project → **API keys**):

   | Key | Env var |
   |-----|---------|
   | iOS public SDK (`appl_…`) | `EXPO_PUBLIC_REVENUECAT_IOS_API_KEY` |
   | Android public SDK (`goog_…`) | `EXPO_PUBLIC_REVENUECAT_ANDROID_API_KEY` |
   | Secret API (`sk_…`) | `REVENUECAT_SECRET_KEY` (API only) |

   Generate webhook secret: `openssl rand -hex 32` → `REVENUECAT_WEBHOOK_AUTH`

8. **Webhook** (after API deployed):
   - URL: `https://<api>/webhooks/revenuecat`
   - Authorization header = `REVENUECAT_WEBHOOK_AUTH`
9. **Store credentials in RevenueCat:**
   - iOS: App Store Connect API key (`.p8`)
   - Android: Google Play service account JSON
10. **Test:** dev/production build only — **not Expo Go**. Sandbox Apple/Google test accounts.

### Checklist

- [ ] New RevenueCat project **Recall** (not Africana)
- [ ] iOS app `com.recall.app` + entitlement **`pro`**
- [ ] App Store subscription product created
- [ ] Current offering with monthly package
- [ ] SDK keys → mobile EAS secrets
- [ ] Secret key + webhook auth → Fly secrets
- [ ] Webhook URL live after deploy

---

## Appendix B — Sign in with Apple (iOS only)

The app shows **Sign in with Apple on iOS only** — hidden on Android. Google Sign-In remains on both platforms (dev/production builds).

### Apple Developer + App Store Connect

1. [developer.apple.com](https://developer.apple.com) → **Certificates, Identifiers & Profiles**
2. **Identifiers → App IDs** → confirm **`com.recall.app`**
3. Enable capability: **Sign In with Apple**
4. App Store Connect → app → ensure same bundle ID

No extra mobile env vars — native sign-in uses the bundle ID as audience.

### Backend

| Setting | Default | Notes |
|---------|---------|-------|
| `APPLE_CLIENT_ID` | `com.recall.app` | Must match iOS bundle ID |

Migration **`0038`** adds `users.apple_sub` and makes `google_sub` nullable.

Endpoint: `POST /auth/apple` with `{ "id_token": "…", "name": "…" }`.

### Testing

- **iOS Simulator / device:** works in Expo Go and dev builds (simulator needs Apple ID signed in)
- **Android:** Apple button not shown
- **Google:** still requires dev build (`pnpm expo run:ios` / `run:android`)

### App Store review note

If you offer Google Sign-In on iOS, Apple requires you to also offer Sign in with Apple — now implemented.

### Checklist

- [ ] Sign In with Apple enabled on App ID `com.recall.app`
- [ ] Run migration `0038` on production DB
- [ ] Rebuild iOS app after pulling Apple auth changes
- [ ] QA: Apple login, Google login (dev build), account persists across relaunch

---

## Intentionally out of scope (v1)

- Tools/agents, non-web code execution, multi-user/teams
- SSE fallback for regenerate/edit (WebSocket-only today)
- In-app theme override beyond system/manual (no per-screen override)
- RTL layout (i18n ships 9 LTR locales)

See also `FEATURES.md` → Pre-deployment TODO and `CLAUDE.md` for architecture.
