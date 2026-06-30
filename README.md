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
```bash
./scripts/dev.sh mobile
```

On a physical device, set `EXPO_PUBLIC_API_URL=http://<your-lan-ip>:8000` in `apps/mobile/.env`.

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

## Remote

https://github.com/bennnnnn/recall
