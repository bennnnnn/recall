# Recall

Personal AI mobile chat with persistent memory.

**Docs:** [CLAUDE.md](./CLAUDE.md) — engineering map. Product: [FEATURES.md](./FEATURES.md). Security: [SECURITY.md](./SECURITY.md).

**Layout:**

- `apps/api/` — FastAPI backend
- `apps/mobile/` — Expo React Native app
- `apps/web/` — Vite slice 1 (login + chat SSE)

**Scripts:** `./scripts/dev.sh` (api, watch-errors, mobile, migrate, setup, check)

Cursor rules live in `.cursor/rules/`. Subject pipelines: [docs/math.md](./docs/math.md), [docs/physics.md](./docs/physics.md), [docs/chemistry.md](./docs/chemistry.md). Launch: [docs/PRODUCTION.md](./docs/PRODUCTION.md), [docs/QA_MATRIX.md](./docs/QA_MATRIX.md), [docs/ROLLBACK.md](./docs/ROLLBACK.md).

## Where an error lives

- A wrong verified answer starts in `apps/api/app/modules/math/`, `modules/physics/`, or `modules/chemistry/`, and in that subject's doc above.
- Stream, stop, or a turn that never finishes starts in `apps/api/app/services/chat/`. `routers/ws.py` and `routers/chat_stream.py` call it.
- A screen that already has a feature folder starts in `apps/mobile/features/<name>/`.
- Chat UI, until that move lands, starts in `apps/mobile/hooks/useChat*.ts`, `components/chat/`, and `lib/chat/`. `app/index.tsx` stays a route.

## Cursor Cloud specific instructions

- System Python on the base image can be 3.12.3, which segfaults while compiling API tests. Use `uv run` from `apps/api` (uv installs CPython 3.12.4+). Do not run the suite on the system interpreter.
- Local Postgres is `postgresql+asyncpg://postgres:dev@127.0.0.1:5432/recall` with the `vector` extension (`postgresql-16-pgvector`). Redis is `redis://127.0.0.1:6379`. Start both with `sudo service postgresql start` and `sudo service redis-server start`, then `./scripts/dev.sh migrate`.
- `apps/api/.env` enables `DEV_AUTH_ENABLED` and `MOCK_LLM_ENABLED`, so chat works without OpenRouter. The web client at http://127.0.0.1:5173 signs in with **Continue (dev)**. API health is http://127.0.0.1:8000/health.
- iOS Simulator and Android emulators are not available here. Check mobile with `pnpm typecheck`, `pnpm lint`, and `pnpm test` in `apps/mobile`. Use `apps/web` (`./scripts/dev.sh web`) for the browser UI.
- Install and boot helpers: `.cursor/cloud-agent-install.sh` (deps only) and `.cursor/cloud-agent-start.sh` (Postgres, Redis, migrate, API, web).
