# Recall

Personal AI mobile chat with persistent memory.

**Docs:** [CLAUDE.md](./CLAUDE.md) — engineering map. Product: [FEATURES.md](./FEATURES.md). Security: [SECURITY.md](./SECURITY.md).

**Layout:**

- `apps/api/` — FastAPI backend
- `apps/mobile/` — Expo React Native app
- `apps/web/` — Vite slice 1 (login + chat SSE)

**Scripts:** `./scripts/dev.sh` (api, watch-errors, mobile, migrate, setup, check)

Cursor rules live in `.cursor/rules/`. Live subject maps: [docs/math.md](./docs/math.md), [docs/chemistry.md](./docs/chemistry.md), [docs/MEMORY_V2.md](./docs/MEMORY_V2.md). Launch: [docs/PRODUCTION.md](./docs/PRODUCTION.md), [docs/QA_MATRIX.md](./docs/QA_MATRIX.md), [docs/ROLLBACK.md](./docs/ROLLBACK.md).
