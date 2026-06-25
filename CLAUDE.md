# CLAUDE.md — Recall (Personal AI Chat)

A personal mobile AI chat app that remembers the user's preferences, projects, and context across chats. Mobile = Expo React Native. Backend = FastAPI. Models routed via LiteLLM. This file tells you how this codebase works and the rules to follow.

## Golden Rules (read first)

1. **Never put provider API keys in the mobile app.** Keys live only in the backend `.env`. The app only ever talks to our API.
2. **Use product model aliases, never provider names**, in app/business code: `free-chat`, `smart-chat`, `title-model`, `memory-model`. Only `gateways/litellm_gateway.py` maps aliases → real providers.
3. **Never send full chat history to the model.** Build context from injected memory + the recent window (~10–20 messages) only.
4. **Topic generation and memory extraction are best-effort background jobs.** They must never raise into the chat request path or block streaming.
5. **No code execution.** Code in messages is rendered/highlighted only — never run user code or shell.
6. **All LLM structured outputs are validated with Pydantic** before they touch the DB.

## Service Overview

**What it does:** authenticated users chat with cheap LLMs; the app persists chats, auto-generates a topic/title, and maintains structured personal memory that is injected into future prompts.

**Domain concepts:**

- **user** — Google-authenticated person; editable profile + preferences.
- **chat** — a conversation; has an auto-generated title.
- **message** — one turn (`user` | `assistant` | `system`).
- **memory** — a structured fact about the user, typed: `profile` | `preference` | `project` | `fact` | `focus`.
- **model alias** — product-level model name mapped to a provider by the gateway.
- **quota** — per-user daily token budget (free tier 30k/day).

**Not in scope (v1):** tools/agents, code execution, web app, multi-user/teams.

## Architecture

Monorepo:

```
recall/
  apps/
    mobile/        # Expo React Native (TypeScript)
    api/           # FastAPI (Python)
  CLAUDE.md
```

Backend layers (`apps/api/app/`) — keep layers thin and one-directional (routers → services → gateways/repositories):

```
app/
  main.py            # app factory, middleware, router registration
  routers/           # HTTP + WebSocket endpoints ONLY (no business logic)
  services/          # business logic: chat, memory, topic, quota, auth
  gateways/          # external calls: litellm_gateway.py, google_auth.py
  repositories/      # DB access (Neon): users, chats, messages, memories, usage
  models/            # Pydantic schemas (API I/O) + structured-output schemas
  background/        # async jobs: topic_generation.py, memory_extraction.py
  core/              # config (pydantic-settings), db, redis, logging
  tests/
```

**The chat loop** (where new chat code belongs → `services/chat.py`):

1. Verify session → 2. Check daily quota (Redis) → 3. Load memory + recent window (Neon) → 4. Stream via LiteLLM → 5. Persist messages → 6. Background topic (first turn only) → 7. Background memory extraction → 8. Update usage.

**Streaming:** WebSocket endpoint (`routers/ws.py`) preferred (supports stop-generation); a cancel message aborts the active LLM task.

**Mobile** (`apps/mobile/`): Expo Router screens (Login, Chat, History, Memory, Settings); API client in `lib/api.ts`; secure token storage; FlashList for messages; markdown + code highlighting in the message renderer.

## Build / Run Commands

**Backend** (uses uv):

```bash
cd apps/api
uv sync
uv run uvicorn app.main:app --reload --port 8000
uv run alembic upgrade head
```

**Mobile** (uses pnpm):

```bash
cd apps/mobile
pnpm install
pnpm expo start          # dev; press i / a for iOS / Android
```

**Gotchas:**

- Run the backend on port 8000 and point the app's `EXPO_PUBLIC_API_URL` at it (use your machine's LAN IP on a physical device, not localhost).
- Native Google Sign-In requires a dev build (`pnpm expo run:ios` / `run:android`), not Expo Go. Use dev auth in Expo Go.

## Testing

**Backend:**

```bash
cd apps/api
uv run pytest
uv run pytest app/tests/services/test_chat.py
uv run pytest -k memory
```

**Mobile:**

```bash
cd apps/mobile
pnpm test
pnpm typecheck
pnpm lint
```

**Coverage requirements**

- Backend minimum 80%; critical services (quota, auth, memory) target 90%+.
- `uv run pytest --cov=app --cov-report=term-missing --cov-fail-under=80`
- Do not skip tests to pass coverage. If a path is hard to cover, mock the external call.

## Unit Test Patterns

- Framework: pytest + pytest-asyncio. Async tests for all IO paths.
- Table-driven via `@pytest.mark.parametrize`.
- Mock all external calls — tests must make zero real network calls.
- Naming: `test_<unit>_<behavior>`.

```python
@pytest.mark.parametrize(
    "used, requested, allowed",
    [(0, 1000, True), (29_000, 2000, False), (30_000, 1, False)],
)
async def test_quota_enforced(fake_redis, used, requested, allowed):
    ...
```

**Mobile:** React Native Testing Library; mock `lib/api.ts`; assert on rendered text/markdown.

## Local Dev Setup

**Required services:** Neon Postgres + Upstash Redis (no Docker required).

**Env** (`apps/api/.env`):

```
DATABASE_URL=postgresql+asyncpg://...neon...
REDIS_URL=rediss://...upstash...
GOOGLE_CLIENT_ID=...
DEEPSEEK_API_KEY=...
JWT_SECRET=...
```

**Mobile** (`apps/mobile/.env`): `EXPO_PUBLIC_API_URL=http://<lan-ip>:8000`

**Dev placeholders:** `DEV_AUTH_ENABLED=true`, `MOCK_LLM_ENABLED=true` (when no API keys).

**Ports:** API 8000, Expo 8081. Health check: `GET /health` → `{"status":"ok"}`.

## Code Conventions

**Python:** async/await for all IO; full type hints; Pydantic v2; config via pydantic-settings; ruff for format/lint.

**TypeScript / Mobile:** functional components + hooks; all network via `lib/api.ts`; tokens in expo-secure-store.

## Key Dependencies (external services)

Neon · Upstash Redis · LiteLLM · Google OAuth · Sentry

Later: pgvector, RevenueCat, LiteLLM Proxy.

## Milestones (MVP week)

| Day | Deliverable |
|-----|-------------|
| 1 | Expo app + Google login + basic chat screen |
| 2 | FastAPI + LiteLLM streaming response |
| 3 | Persist + load chat history (Neon) |
| 4 | Markdown/code highlighting, model picker, stop/regenerate |
| 5 | Topic generation + daily token quota (Redis) |
| 6 | Memory extraction + injection |
| 7 | Settings, memory view/delete, polish |
