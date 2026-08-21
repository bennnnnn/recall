# CLAUDE.md — Recall (Personal AI Chat)

A personal mobile AI chat app that remembers the user's preferences, projects, and context across chats. Mobile = Expo React Native. Backend = FastAPI. Models routed via LiteLLM. This file is the **engineering map** (rules, layers, catalog, seams). Product status lives in [FEATURES.md](./FEATURES.md). Math pipeline: [docs/math.md](./docs/math.md). Health review: [docs/CODEBASE_REVIEW_2026-08.md](./docs/CODEBASE_REVIEW_2026-08.md).

**This is not a week-one MVP.** Approximate size (app code, excluding generated/`node_modules`):

| Tree | Lines | Notes |
|------|-------|-------|
| `apps/api/app` | ~44k Python | ~83k with tests |
| `apps/mobile` | ~50k TS/TSX | ~62k with tests; vendor inlined separately |

Do not review or extend the app from the historical MVP screen list. Use **Domain catalog** and **Seams**.

## Golden Rules (read first)

1. **Never put provider API keys in the mobile app.** Keys live only in the backend `.env`. The app only ever talks to our API.
2. **Use product model aliases, never provider names**, in app/business code: `free-chat`, `smart-chat`, `max-chat`, `title-model`, `memory-model`. Alias → provider mapping lives in `services/model_catalog.py` (LiteLLM calls go through `gateways/litellm_gateway.py`).
3. **Never send full chat history to the model.** Build context from injected memory + the recent window (default hard cap 20 messages; token budget also trims) only.
4. **Topic generation, memory extraction, and other post-turn work are best-effort background jobs.** They must never raise into the chat request path or block streaming. Enqueue from `services/chat/post_turn.py` via `core/jobs.py`.
5. **No arbitrary code execution — one sandboxed exception.** Code in messages is rendered/highlighted only, with a single exception: **HTML/CSS/JS may be previewed in a sandboxed WebView** (and charts/diagrams rendered from model output). Never execute Python, shell, or any other language, and never run code anywhere except inside the isolated preview WebView (no app token is ever exposed to it). The preview WebView requires a dev build — it does not work in Expo Go.
6. **All LLM structured outputs are validated with Pydantic** before they touch the DB.
7. **Symbolic math runs server-side only (SymPy).** The mobile app renders verified results and structured `geometry` / `graph` fences — it never solves equations on-device. Pipeline map: [docs/math.md](./docs/math.md).

## Service Overview

**What it does:** authenticated users chat with LLMs; the app persists chats, auto-generates titles, injects structured personal memory, and layers productivity (todos, Learning, calendar/Gmail) plus rich rendering.

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

**Rich rendering:** markdown, tables, math, callouts, code highlighting, sandboxed HTML/CSS/JS preview, charts (Vega), Mermaid, geometry/graph SVG, chemistry (SMILES). Fence identity lives in `apps/mobile/lib/fenceRegistry.ts`.

**Owned tool loop, on by default:** `gateways/mcp/` (sympy, calendar, image-gen, web-search) plus `services/tool_loop.py`. `mcp_tool_loop_enabled` defaults to `true`. The legacy one-shot `mcp_tools_enabled` pre-stream round stays **off**. Heuristic SymPy + web-search inject still run. See `docs/math.md` and `FEATURES.md` §16.

**Not in scope (v1):** execution of non-web code or execution outside the sandboxed preview WebView; multi-user/teams; duplex full-voice; arbitrary user MCP servers. A **web client sharing this same API** is planned later. Attachment RAG is shipped.

## Architecture

Monorepo:

```
recall/
  apps/
    mobile/        # Expo React Native (~50k TS) — screens, hooks, rich render, lib/api
    api/           # FastAPI (~44k py) — HTTP/WS + worker
  docs/            # math.md, PRODUCTION.md, QA_MATRIX.md, CODEBASE_REVIEW_2026-08.md
  CLAUDE.md
  FEATURES.md
```

Backend layers (`apps/api/app/`) — keep layers thin and one-directional (`routers/` → `services/` → `gateways/` + `repositories/`):

```
app/
  main.py              # app factory, middleware, router registration
  worker_main.py       # Fly worker: jobs + schedulers (no public API)
  worker_health.py     # worker liveness probe
  exceptions.py        # shared domain exceptions
  routers/             # HTTP + WebSocket ONLY (no business logic)
  services/            # business logic (~27k)
    chat/              # turn prep, stream, post_turn (~4.5k)
    memory/ projects/ todos/ web_search/ home/
  gateways/            # external IO (LiteLLM, Google, storage, speech, search, …)
    mcp/               # tool adapters + registry (flag-gated at runtime)
  repositories/        # Neon access
  models/              # Pydantic + ORM
  background/          # job handlers + periodic schedulers
    handlers.py        # job-type → handler register (imported at startup)
  core/                # config, db, redis, jobs stream (no domain imports)
  content/             # static legal copy
  tests/               # ~39k
```

### Transaction ownership

- Services own multi-step database units. They call repository writes with
  `commit=False`, commit once after every write succeeds, and roll back the
  service-owned transaction on failure.
- Repository write functions keep `commit=True` only as a compatibility default
  for standalone single-operation callers. With `commit=False`, they may flush
  to materialize IDs or constraints but must not commit or roll back.
- Cache invalidation, job enqueue, and other external side effects happen after
  the owning service commits. Slow provider calls should run outside an open DB
  transaction; a workflow may therefore use separate short transaction phases
  (for example, memory text then embedding writes).
- A caller that explicitly passes `commit=False` to a composable service owns
  both the eventual commit and rollback. Do not add a generic unit-of-work layer
  unless repeated concrete workflows require more than these boundaries.

**Streaming:** WebSocket (`routers/ws.py`) preferred (stop-generation); SSE fallback (`routers/chat_stream.py`). Both share `chat/stream_events.py` for `done` / `error` payloads. A cancel message aborts the active LLM task.

**Clients & the API contract:** the backend is a client-agnostic HTTP/WebSocket API with stateless JWT (Bearer) auth, so a future **web client reuses the same API**. Keep `apps/mobile/lib/api.ts` the **barrel** over `lib/api/*.ts` (single network boundary). Rich-block rendering should stay swappable; only platform bits differ per client.

## Domain catalog

What exists in code today. Product caveats: FEATURES.md.

| Domain | API | Mobile |
|--------|-----|--------|
| Auth / account | `routers/auth.py`, `users.py`, `services/auth.py`, `profile.py`, `subscription.py` | `app/login.tsx`, `onboarding.tsx`, `lib/api/auth.ts`, `account.ts` |
| Chat + stream | `routers/ws.py`, `chat_stream.py`, `chats.py`; `services/chat/` | `app/index.tsx`, `hooks/useChat*.ts`, `components/chat/` |
| Memory | `routers/memories.py`, `services/memory/`, `background/memory_*.py` | `app/memory.tsx`, `hooks/useMemoryActions.ts` |
| Models / quota | `routers/models.py`, `model_catalog.py`, `quota.py`, `routing.py` | composer picker, `settings/models.tsx` |
| Search | `routers/search.py`, `services/search.py` | drawer search (`useDrawerSearch`) |
| Todos / reminders | `routers/todos.py`, `services/todos/` | `app/todos.tsx`, `components/todos/` |
| Learning projects | `routers/projects.py`, `services/projects/`, `vocab_quiz.py`, `daily_learning.py` | `app/projects/`, quiz chips |
| Home starters | `routers/home.py`, `services/home/` | home cards on chat empty / index |
| Attachments + RAG | `routers/attachments.py`, `attachment_*.py`, `background/attachment_*.py` | `lib/api/attachments.ts`, composer attach |
| Chat-history RAG | `chat_history_rag.py`, `message_chunks`, `background/message_indexing.py` | (prompt inject only; no extra UI) |
| Image gen (Pro) | `routers/images.py`, `image_generation.py`, `image_gen_intent.py` | composer send only (no prompt sheet) |
| Speech STT/TTS | `routers/speech.py`, `services/speech.py` | `useVoiceInput`, message speaker |
| Web search | `services/web_search/`, `gateways/web_search_*.py` | source chips under replies |
| Math (SymPy) | `math_tools/`, `math_service/`, `math_fence.py`, `sympy_executor.py` | `MathText` / `MathView` / `geometry` / `graph` |
| Calendar / Gmail | `routers/integrations.py`, `gmail_integrations.py`, `services/calendar.py`, `email.py` | `settings/integrations.tsx` |
| Push / email out | `push_notifications.py`, `transactional_email.py`, `background/*scheduler*` | notification settings |
| Billing | `routers/webhooks.py`, `gateways/revenuecat_gateway.py` | RevenueCat |
| Admin / legal / health | `routers/admin.py`, `legal.py`, `health.py` | `settings/about.tsx`, data-controls |
| Rich fences | prompt constants + post-stream fence rewrite | `lib/fenceRegistry.ts`, `components/rich/` |
| i18n | locale on user + prompt | `lib/i18n/*.json` (9 locales, key parity tested) |

**Routers registered in** `main.py`: health, legal, auth, admin, webhooks, users, home, link_preview, chats, chat_stream, memories, models, todos, projects, search, suggestions, attachments, integrations, gmail_integrations, speech, images, ws.

**Service packages:** `services/chat`, `memory`, `projects`, `todos`, `web_search`, `home`, plus top-level modules (math_*, speech, calendar, …). New chat-loop code belongs in `services/chat/`. New IO belongs in a gateway or repository, not a router.

## Seams (plug in / plug out)

Add or delete at these boundaries. If a change needs eight unrelated files, the seam is missing or being bypassed — say so, don’t silently sprawl.

| Concern | Seam | How to extend | How to remove |
|---------|------|----------------|---------------|
| HTTP/WS endpoint | `routers/` + `main.py` `include_router` | Thin router → service | Drop router registration + tests |
| External API | `gateways/` | One gateway module; mock in tests | Delete gateway; keep service behind a flag if needed |
| MCP / model tools | `gateways/mcp/` + `setup_mcp_adapters` | `register(Adapter)` implementing `ToolAdapter` | Unregister; `mcp_tool_loop_enabled` defaults **on** |
| Background job | `background/handlers.py` + `core/jobs.py` `register` | Add handler in `handlers.py`; enqueue from `post_turn.py` or a scheduler — never on the stream path | Unregister + stop enqueue |
| Feature flag | `core/config.py` `*_enabled` | One Settings field; gate service entry | Default false; then delete path |
| Model | `services/model_catalog.py` | Catalog entry + OpenRouter slug | Remove alias; don’t leave provider names in app code |
| Mobile network | `lib/api/<domain>.ts` re-exported from `lib/api.ts` | Add file + barrel spread | Delete API slice; no raw `fetch` in screens |
| Rich fence | `lib/fenceRegistry.ts` (`FENCES`) | Add a `FenceSpec`; one block component; wire render | Delete the spec + component |
| Chat UI behavior | `hooks/useChat*.ts` | Hook owns logic; screen stays thin | Don’t add a second composer intercept |
| i18n string | `lib/i18n/*.json` | Key in `en.json` + locales | Delete key from all locale files |
| Banned UX | `.cursor/rules/chat-ux-bans.mdc` | — | If replacing UX, **delete** the old path |

**Flags (defaults in `core/config.py`):** `mcp_tool_loop_enabled` (on), `mcp_tools_enabled` (off, legacy), `math_tools_enabled`, `web_search_enabled`, `attachments_enabled`, `attachment_rag_enabled`, `attachment_ocr_enabled` (on), `chat_history_rag_enabled` (on), `image_generation_enabled`, `speech_*_enabled`, `gmail_enabled`, `google_calendar_enabled`, `push_enabled`, `email_enabled`, `semantic_memory_enabled`, `history_compression_enabled`, `dev_auth_enabled`, `mock_llm_enabled`.

## The chat loop

New chat-loop code → `services/chat/`. Quota + per-chat prepare lock are owned by `async with turn_resources(...)` in `stream.py` (do not re-introduce hand-managed `owns_lock` / `pre_reserved` flags).

1. Auth + per-chat prepare lock; wait for the previous turn's pending finalize (`chat/finalize_registry.py`)
2. Check + reserve daily quota (Redis)
3. Image-generation intent interception (Pro; may return without an LLM turn)
4. `turn_prep/`: memory + recent window, attachments/RAG, chat-history RAG, calendar/Gmail, web search, project/quiz context, SymPy pre-solve
5. Owned MCP tool loop (`mcp_tool_loop_enabled`, default on)
6. Stream via LiteLLM (`gateways/litellm_gateway.py`)
7. Post-stream math fence correction (`math_fence.py`)
8. Persist assistant + usage in a finalize task
9. `enqueue_post_turn_jobs` — topic, memory, todos, projects, compress, suggestions, attachment_index, message_index (best-effort; must not raise into the stream)

Steps 6–8 are the only ones on the user's critical path. Everything in step 9 is a durable Redis-Stream job.

**Jobs registered in** `background/handlers.py`: `topic`, `memory`, `memory_consolidate`, `todos`, `projects`, `language_path`, `compress`, `suggestions`, `gmail_sync`, `transactional_email`, `attachment_index`, `message_index`.

**Worker** (`worker_main.py`): consumes that stream and runs schedulers (push, email reminders, Gmail periodic, attachment orphan reaper).

## Mobile map

Expo Router (`apps/mobile/app/`): Login, Onboarding, Chat (`index`), Memory, Todos/Lists, Learning (`projects/`), Settings (models, memory, preferences, integrations, learning, notifications, data-controls, about). **Chat history and search are the drawer** (`components/drawer/`, `ConversationList.tsx`), not standalone screens.

- Network: `lib/api.ts` barrel → `lib/api/{client,auth,chats,memories,todos,projects,integrations,attachments,images,account,discover,connectivity,types}.ts`
- Tokens: `expo-secure-store` only
- Chat logic: `hooks/useChat.ts` plus focused `useChatSend` / `useChatRegenerate` / … — screens stay thin
- Messages: FlashList; markdown + `components/rich/*` + `components/markdown/*`
- Fences: `lib/fenceRegistry.ts` is the lang/id table; `RichFence` renders
- i18n: `lib/i18n` (9 locales, key parity enforced by test)

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

**Required services:** Neon Postgres + Upstash Redis (no Docker required). Local API rate limits: Homebrew Redis (`redis://127.0.0.1:6379`) if Upstash free-tier max-requests is exhausted.

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

Neon · Upstash Redis · LiteLLM (OpenRouter) · Google OAuth · Apple Sign-In · Tavily (web search) · R2 (attachments) · Sentry · RevenueCat

**Database — Neon (serverless Postgres), chosen over Supabase:** we run our own backend, auth (Google/JWT/Apple), and object storage (R2 in production), so we only need a database — not a BaaS bundle (auth/storage/realtime) we wouldn't use. Neon's usage-based pricing + scale-to-zero is cheaper at our scale, branching helps CI/preview, it's plain Postgres (portable, good for the future web client), and `pgvector` runs in the **same DB** for memory embeddings, attachment RAG, and chat-history RAG.

**Shipped beyond the original MVP week:** Learning projects + quizzes, todos/reminders, Gmail/calendar, attachments + RAG, image gen, STT/TTS, web search, math/geometry/graph, rich fences, Pro/RevenueCat, push, Fly `api`/`worker` split, flag-gated MCP tool loop. Full catalog: FEATURES.md.

**Later:** web client, user MCP servers, LiteLLM Proxy. Not “missing from CLAUDE.md” — deferred on purpose. The owned tool loop is on by default (see Service Overview). Chat-history semantic RAG is shipped.

## Milestones (MVP week — complete)

The original week-one MVP is done. The table below is historical; current scope is in FEATURES.md and the catalog above.

| Day | Deliverable |
|-----|-------------|
| 1 | Expo app + Google login + basic chat screen |
| 2 | FastAPI + LiteLLM streaming response |
| 3 | Persist + load chat history (Neon) |
| 4 | Markdown/code highlighting, model picker, stop/regenerate |
| 5 | Topic generation + daily token quota (Redis) |
| 6 | Memory extraction + injection |
| 7 | Settings, memory view/delete, polish |
