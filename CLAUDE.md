# CLAUDE.md — Recall (Personal AI Chat)

A personal mobile AI chat app that remembers the user's preferences, projects, and context across chats. Mobile = Expo React Native. Backend = FastAPI. Models routed via LiteLLM. This file tells you how this codebase works and the rules to follow.

## Golden Rules (read first)

1. **Never put provider API keys in the mobile app.** Keys live only in the backend `.env`. The app only ever talks to our API.
2. **Use product model aliases, never provider names**, in app/business code: `free-chat`, `smart-chat`, `title-model`, `memory-model`. Alias → provider mapping lives in `services/model_catalog.py` (LiteLLM calls go through `gateways/litellm_gateway.py`).
3. **Never send full chat history to the model.** Build context from injected memory + the recent window (default hard cap 20 messages; token budget also trims) only.
4. **Topic generation and memory extraction are best-effort background jobs.** They must never raise into the chat request path or block streaming.
5. **No arbitrary code execution — one sandboxed exception.** Code in messages is rendered/highlighted only, with a single exception: **HTML/CSS/JS may be previewed in a sandboxed WebView** (and charts/diagrams rendered from model output). Never execute Python, shell, or any other language, and never run code anywhere except inside the isolated preview WebView (no app token is ever exposed to it). The preview WebView requires a dev build — it does not work in Expo Go.
6. **All LLM structured outputs are validated with Pydantic** before they touch the DB.
7. **Symbolic math runs server-side only (SymPy).** The mobile app renders verified results and structured `geometry` / `graph` fences — it never solves equations on-device. Pipeline map: [docs/math.md](./docs/math.md).

## Service Overview

**What it does:** authenticated users chat with cheap LLMs; the app persists chats, auto-generates a topic/title, and maintains structured personal memory that is injected into future prompts.

**Domain concepts:**

- **user** — Google or Apple sign-in; editable profile + preferences; `plan` (`free` | `pro`) is driven by RevenueCat.
- **chat** — a conversation; has an auto-generated title.
- **message** — one turn (`user` | `assistant` | `system`).
- **memory** — a structured fact about the user, typed: `profile` | `preference` | `project` | `fact` | `focus`.
- **model alias** — product-level model name mapped to a provider by the gateway.
- **quota** — per-user daily token budget (free tier 100k/day).
- **todo** — a lightweight task the user tracks; optionally linked to a chat.
- **suggestion** — a proactive follow-up prompt generated from the user's recent activity (best-effort background job).
- **search** — full-text lookup across the user's chats and messages.
- **project** — a utility workspace (Learning/vocabulary today) with `project_items` and quiz progress (`quiz_miss_events`, SM-2 scheduling).
- **attachment** — an uploaded image/file (R2 in production) with extracted text chunked into `attachment_chunks` for retrieval.
- **integration** — a connected Google account: `user_calendar_connections` and `user_gmail_connections`, feeding calendar context and `suggested_reminders`.
- **push token** — a registered Expo device token for reminder/nudge notifications.

**Rich rendering:** the message renderer also supports markdown, tables, math, callouts, code highlighting, and sandboxed previews — HTML/CSS/JS via WebView, charts (Vega), Mermaid (source + external editor), geometry/graph SVG, and chemistry (SMILES).

**Flag-gated, off by default:** the MCP tool layer. `gateways/mcp/` (sympy, calendar, image-gen, web-search adapters) plus `services/tool_loop.py` and `services/chat_tools.py` are implemented and tested, but `MCP_TOOLS_ENABLED` and `MCP_TOOL_LOOP_ENABLED` both default to `false`. Treat this path as optional until intentionally enabled — see `docs/math.md` and `FEATURES.md` §16.

**Not in scope (v1):** execution of non-web code (Python/shell/etc.), execution outside the sandboxed preview WebView, multi-user/teams. (A **web client sharing this same API** is planned for a later version — see FEATURES.md.)

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
  worker_main.py     # separate worker process entrypoint (Fly api/worker split)
  worker_health.py   # worker liveness probe
  exceptions.py      # shared domain exceptions (ChatServiceError, QuotaExceededError, …)
  routers/           # HTTP + WebSocket endpoints ONLY (no business logic)
  services/          # business logic; subpackages: chat/ (+ chat/turn_prep/),
                     #   todos/, projects/, home/, web_search/
  gateways/          # external calls: litellm_gateway.py, google_auth.py, mcp/ adapters
  repositories/      # DB access (Neon): users, chats, messages, memories, usage, …
  models/            # Pydantic schemas (API I/O), orm.py, structured-output schemas
  background/        # async job bodies: topic_generation.py, memory_extraction.py, …
  core/              # config (pydantic-settings), db, redis, jobs.py (queue), logging
  content/           # static content (legal copy)
  tests/
```

**The chat loop** (where new chat code belongs → `services/chat/`):

1. Verify session → 2. Acquire per-chat prepare lock; wait for the previous turn's
   pending finalize (`chat/finalize_registry.py`) → 3. Check + reserve daily quota (Redis) →
   4. Image-generation intent interception (Pro; returns without an LLM turn) →
   5. `turn_prep/`: load memory, recent window, attachments, calendar/Gmail, web search,
   and SymPy pre-solve → 6. Stream via LiteLLM (or the MCP tool loop when enabled) →
   7. Post-stream fence rewrite (`services/math_fence.py`) → 8. Persist messages + usage in a
   finalize task → 9. Enqueue best-effort jobs: topic (first turn), memory extraction, todo /
   project sync, compaction.

Steps 6–8 are the only ones on the user's critical path; everything in step 9 is a durable
Redis-Stream job (`core/jobs.py`) and must never raise into the stream.

**Streaming:** WebSocket endpoint (`routers/ws.py`) preferred (supports stop-generation);
a cancel message aborts the active LLM task. `routers/chat_stream.py` is the SSE fallback
(client disconnect cancels generation). Both transports share `chat/stream_events.py` for
the `done` / `error` payloads.

**Mobile** (`apps/mobile/`): Expo Router screens — Login, Onboarding, Chat (`index`), Memory,
Todos, Projects (list + detail), and Settings (`settings/*`: models, preferences, memory,
notifications, integrations, learning, data controls, about). Chat history and search live in
the drawer (`components/drawer/`, `ConversationList.tsx`), not on their own routes. API client
in `lib/api.ts` (a barrel over `lib/api/*`); secure token storage; FlashList for messages;
markdown + code highlighting + sandboxed HTML/chart previews in the message renderer;
i18n via `lib/i18n` (9 locales, key parity enforced by test).

**Clients & the API contract:** the backend is a client-agnostic HTTP/WebSocket API with stateless JWT (Bearer) auth, so a future **web client reuses the same API** (no rewrite). Keep `lib/api.ts` the single network boundary and rich-block rendering swappable; only platform bits differ per client (web: cookie/web-storage tokens instead of expo-secure-store, web OAuth instead of native Google Sign-In, `<iframe>` instead of `react-native-webview`). Web needs its origin added to `cors_origins`.

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
- The HTML/JS preview WebView (`react-native-webview`) is a **native module** — it only works in a dev build. After adding/updating it, rebuild the dev client (`pnpm expo run:ios` / `run:android`); in Expo Go the preview falls back to static HTML (scripts stripped) or "Open in browser".

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

> **Neon setup:** use a **direct Neon account** (neon.com), *not* the Vercel-managed integration — the backend is FastAPI (not on Vercel), so that integration adds no value and limits the console/CLI/feature access. Create the project in **AWS us-east-2** to keep the option of trying Neon Storage (S3-compatible object storage, currently private preview). Just point `DATABASE_URL` at it.

**Env** (`apps/api/.env`):

```
DATABASE_URL=postgresql+asyncpg://...neon...
REDIS_URL=rediss://...upstash...
GOOGLE_CLIENT_ID=...
OPENROUTER_API_KEY=...
JWT_SECRET=...
```

**Mobile** (`apps/mobile/.env`): `EXPO_PUBLIC_API_URL=http://<lan-ip>:8000`

**Dev placeholders:** `DEV_AUTH_ENABLED=true`, `MOCK_LLM_ENABLED=true` (when no API keys).

**Ports:** API 8000, Expo 8081. Health check: `GET /health` → `{"status":"ok"}`.

## Code Conventions

**Python:** async/await for all IO; full type hints; Pydantic v2; config via pydantic-settings; ruff for format/lint.

**TypeScript / Mobile:** functional components + hooks; all network via `lib/api.ts`; tokens in expo-secure-store.

## Key Dependencies (external services)

Neon · Upstash Redis · LiteLLM (OpenRouter) · Google OAuth · Apple Sign-In · Sentry · RevenueCat

**Database — Neon (serverless Postgres), chosen over Supabase:** we run our own backend, auth (Google/JWT/Apple), and object storage (R2 in production), so we only need a database — not a BaaS bundle (auth/storage/realtime) we wouldn't use. Neon's usage-based pricing + scale-to-zero is cheaper at our scale, branching helps CI/preview, it's plain Postgres (portable, good for the future web client), and `pgvector` runs in the **same DB** for memory embeddings.

**Shipped beyond MVP:** pgvector memory embeddings, RevenueCat Pro subscriptions, Sentry (backend + mobile), Fly `api`/`worker` process split, attachment RAG (`services/attachment_rag.py` + `attachment_chunks`, `ATTACHMENT_RAG_ENABLED` defaults on), Google Calendar + Gmail integrations, push notifications, transactional email, image generation, web search. See `FEATURES.md` for the full product catalog.

**Later:** LiteLLM Proxy (self-hosted routing), web client. The MCP tool layer is built but flag-gated off (see Service Overview).

## Milestones (MVP week — complete)

The original week-one MVP is done. The table below is historical; current scope is in `FEATURES.md`.

| Day | Deliverable |
|-----|-------------|
| 1 | Expo app + Google login + basic chat screen |
| 2 | FastAPI + LiteLLM streaming response |
| 3 | Persist + load chat history (Neon) |
| 4 | Markdown/code highlighting, model picker, stop/regenerate |
| 5 | Topic generation + daily token quota (Redis) |
| 6 | Memory extraction + injection |
| 7 | Settings, memory view/delete, polish |
