# Recall — Production Provisioning Checklist

Step-by-step guide to provision production infrastructure. Pair with [`README.md`](../README.md) §Production deployment and run [`scripts/verify-production.sh`](../scripts/verify-production.sh) after each stage.

---

## 1. Database (Neon Postgres + pgvector)

- [ ] Create Neon project (or Fly Postgres with pgvector)
- [ ] Enable `vector` extension: `CREATE EXTENSION IF NOT EXISTS vector;`
- [ ] Set `DATABASE_URL` as `postgresql+asyncpg://...?sslmode=require`
- [ ] Run migrations: `cd apps/api && uv run alembic upgrade head`
- [ ] Confirm head revision **0036** (`0036_builtin_template_title_unique`)

```bash
cd apps/api && uv run alembic current
# Expected: 0036 (head)
```

---

## 2. Redis (Upstash)

- [ ] Create Upstash Redis database
- [ ] Set `REDIS_URL=rediss://...` (TLS URL)
- [ ] Verify connectivity from Fly region (latency to Upstash region)

---

## 3. Object storage (Cloudflare R2)

Required for production attachments (`STORAGE_BACKEND=r2`).

- [ ] Create R2 bucket (e.g. `recall-attachments`)
- [ ] Create API token with R2 read/write on bucket
- [ ] Set secrets:
  - `STORAGE_BACKEND=r2`
  - `R2_ACCOUNT_ID`
  - `R2_ACCESS_KEY_ID`
  - `R2_SECRET_ACCESS_KEY`
  - `R2_BUCKET`
- [ ] Smoke-test: upload image in app → confirm object in R2 → download in chat

---

## 4. Fly.io API

- [ ] `fly launch` (or connect existing app to repo root; uses `apps/api/Dockerfile`)
- [ ] Scale processes: `fly scale count app=1 worker=1`
- [ ] Set **all** secrets (enforced by `validate_production_settings`):

| Secret | Required | Notes |
|--------|----------|-------|
| `ENVIRONMENT` | yes | `production` |
| `DEV_AUTH_ENABLED` | yes | `false` |
| `MOCK_LLM_ENABLED` | yes | `false` |
| `JWT_SECRET` | yes | ≥32 random chars |
| `DATABASE_URL` | yes | asyncpg URL |
| `REDIS_URL` | yes | `rediss://` |
| `GOOGLE_CLIENT_ID` | yes | |
| `GOOGLE_CLIENT_SECRET` | yes | Calendar/Gmail OAuth |
| `OPENROUTER_API_KEY` | yes | |
| `CORS_ORIGINS` | yes | Explicit origins, never `*` |
| `OAUTH_TOKEN_ENCRYPTION_KEY` | yes | Fernet key |
| `REVENUECAT_WEBHOOK_AUTH` | yes | If monetizing |
| `REVENUECAT_SECRET_KEY` | if monetizing | |
| `TAVILY_API_KEY` | if web search | |
| R2 vars | yes | See §3 |

```bash
# Generate Fernet key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Deploy
fly deploy

# Verify
curl -s https://<your-api>/health/ready
```

- [ ] Health monitor on `GET /health/ready` (DB + Redis)
- [ ] RevenueCat webhook → `https://<api>/webhooks/revenuecat` with `Authorization` header

---

## 5. Mobile (EAS)

- [ ] Configure EAS project ID in `apps/mobile/.env` / EAS secrets
- [ ] Set `EXPO_PUBLIC_API_URL=https://<api-host>`
- [ ] Set Google client IDs (iOS + web) in EAS secrets
- [ ] Set RevenueCat API keys per platform
- [ ] Build:
  ```bash
  cd apps/mobile
  eas build --platform ios --profile production
  eas build --platform android --profile production
  ```
- [ ] Submit to App Store / Play Console
- [ ] On-device QA per [`docs/QA_MATRIX.md`](QA_MATRIX.md)

---

## 6. Google OAuth verification

- [ ] OAuth consent screen published
- [ ] Gmail scope verified for production (Calendar may work in testing mode)
- [ ] Redirect URIs match Fly API + mobile bundle IDs

---

## 7. Landing & support

- [ ] Landing page live
- [ ] Support URL for store listings
- [ ] Privacy policy + terms URLs (served from API `/legal/*` or static site)

---

## 8. Observability (optional)

- [ ] `SENTRY_DSN` on API and mobile EAS secrets
- [ ] Fly metrics / external uptime on `/health/ready`
- [ ] Resend (`RESEND_API_KEY`) if transactional email enabled

---

## Verification commands

```bash
# Static checks (migration file, env template)
./scripts/qa-smoke.sh

# Against running local or deployed API
API_URL=https://your-api.fly.dev ./scripts/qa-smoke.sh --live

# Full provisioning report
./scripts/verify-production.sh
API_URL=https://your-api.fly.dev ./scripts/verify-production.sh --live
```

---

## Launch blockers (from FEATURES.md)

1. Cost guards (speech, Tavily, R1 weight) — done in code
2. Provision Neon, Redis, R2, Fly, EAS
3. Landing page + support URL
4. Google OAuth verification (Gmail)
5. On-device QA matrix (iOS + Android)
6. R2 production attachments end-to-end
