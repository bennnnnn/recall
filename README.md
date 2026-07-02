# Recall

Personal AI mobile chat that remembers who you are, what you prefer, and what you're working on.

**Stack:** Expo React Native · FastAPI · Neon Postgres · Upstash Redis · LiteLLM

## One-time setup (no Docker)

```bash
cd ~/Projects/recall
./scripts/dev.sh setup
```

### 1. Neon (Postgres)

1. Create a free project at [neon.tech](https://neon.tech)
2. Copy the connection string
3. Convert to async SQLAlchemy format in `apps/api/.env`:

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@ep-xxx.region.aws.neon.tech/neondb?sslmode=require
```

### 2. Upstash (Redis)

1. Create a free Redis database at [upstash.com](https://upstash.com)
2. Copy the **Redis URL** (starts with `rediss://`) into `apps/api/.env`:

```bash
REDIS_URL=rediss://default:xxx@xxx.upstash.io:6379
```

### 3. Migrate

```bash
./scripts/dev.sh migrate
```

## Start developing

**Backend:**
```bash
./scripts/dev.sh api          # http://localhost:8000/health
```

**Mobile:**

| Where you test | Start commands | `EXPO_PUBLIC_API_URL` |
|----------------|----------------|------------------------|
| **iOS Simulator (default here)** | `./scripts/dev.sh api` then `./scripts/dev.sh mobile-sim` | `http://127.0.0.1:8000` (set automatically) |
| Physical device + Expo Go | `./scripts/dev.sh api` then `./scripts/set-lan-ip.sh` then `./scripts/dev.sh mobile` | `http://<your-lan-ip>:8000` |

```bash
./scripts/dev.sh api          # backend → http://localhost:8000/health
./scripts/dev.sh mobile-sim   # iOS Simulator + Expo Go (not QR on a real phone)
./scripts/dev.sh mobile       # LAN + QR for a physical device on same Wi‑Fi
./scripts/dev.sh kill-metro   # stop Metro if ports are stuck
```

**Mobile app notes:** use **Continue as Dev User** in Expo Go (Google Sign-In needs a dev build). Theme: **Settings → Personalization → Appearance** (System / Light / Dark). After pulling mobile changes, restart Expo with `--clear` if the bundle looks stale.

On a physical device only, run `./scripts/set-lan-ip.sh` before Expo — do **not** use the LAN IP in the simulator (use `127.0.0.1` instead).

## Dev without Google or API keys

1. Start backend
2. In the app → **Continue as Dev User**
3. Mock LLM replies work until you add `OPENROUTER_API_KEY` ([openrouter.ai/keys](https://openrouter.ai/keys))

## Optional: Docker

Only if you want local Postgres/Redis instead of Neon/Upstash:

```bash
./scripts/dev.sh infra
# then set DATABASE_URL=postgresql+asyncpg://postgres:dev@localhost:5432/recall
# and REDIS_URL=redis://localhost:6379
```

The compose file uses `pgvector/pgvector:pg16` so migrations that need the
`vector` extension (0027/0033) run locally.

## Production deployment (Fly.io)

The API needs a long-running process (WebSockets + the in-process Redis-Stream
background worker), so deploy to a host that keeps the process alive — not a
serverless function platform. A Dockerfile + `fly.toml` are included.

1. **Provision:** `fly launch` (uses `apps/api/Dockerfile`), or point an
   existing Fly app at this directory. Provision a Fly Postgres cluster **with
   pgvector** (`fly pg create --image-ref flyio/postgres-flex:16` then
   `CREATE EXTENSION vector`), or keep using Neon.
2. **Set secrets** (`fly secrets set …`) — every one of these is enforced at
   startup by `validate_production_settings`:
   - `ENVIRONMENT=production`
   - `DEV_AUTH_ENABLED=false` · `MOCK_LLM_ENABLED=false`
   - `JWT_SECRET=` (≥32 random chars)
   - `DATABASE_URL=` · `REDIS_URL=`
   - `GOOGLE_CLIENT_ID=` · `GOOGLE_CLIENT_SECRET=`
   - `OPENROUTER_API_KEY=`
   - `CORS_ORIGINS=https://app.recall.app` (explicit; never `*` in prod)
   - `REVENUECAT_WEBHOOK_AUTH=` (and `REVENUECAT_SECRET_KEY=` if monetizing)
   - `OAUTH_TOKEN_ENCRYPTION_KEY=` (generate with
     `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)
   - `TAVILY_API_KEY=` (if web search is on)
3. **Migrate on deploy:** `fly deploy` runs `alembic upgrade head` first (see
   `fly.toml`). Confirm the head (`0036`) is applied.
4. **Health:** point your monitor at `GET /health/ready` (checks DB + Redis).
5. **RevenueCat:** set the webhook URL to `https://<api>/webhooks/revenuecat`
   with the `Authorization` header = your `REVENUECAT_WEBHOOK_AUTH`.

### Mobile production build

```bash
cd apps/mobile
# set EXPO_PUBLIC_API_URL=https://<api-host> in apps/mobile/.env (or EAS secrets)
eas build --platform ios --profile production
eas build --platform android --profile production
```

Native features require a dev/production build, **not** Expo Go: Google
Sign-In, the HTML/chart preview WebView, push notifications, and RevenueCat
purchases. Configure your EAS `projectId`.

## Remote

https://github.com/bennnnnn/recall
