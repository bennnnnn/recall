# Recall — Feature Coverage & Roadmap

A reference of what the app does **today** versus what is **deferred** to a future version.
Recall is a personal AI chat app: a snappy chatbot with clean formatted answers, multi-model
support, and long-term memory of the user. Mobile = Expo (React Native). Backend = FastAPI +
Neon Postgres + Upstash Redis + LiteLLM (DeepSeek).

**Legend**
- ✅ Implemented
- ⚠️ Partial / with caveats
- 🔜 Deferred (planned)

---

## 1. Authentication (sign up & sign in)
- ✅ **Google sign-in** — single "Continue with Google" button (requires native dev build + the
  Google config plugin / iOS URL scheme to be set).
- ✅ **Account creation** — automatic on first Google sign-in (no separate sign-up flow).
- ✅ **Dev login** — "Continue as Dev User" for Expo Go / local development (gated by
  `DEV_AUTH_ENABLED`, blocked in production).
- ✅ **Sessions** — JWT (HS256) access token, stored in secure storage, 7-day lifetime.
- ✅ **Auto sign-out on 401** — an expired/invalid token signs the user out globally.
- ✅ **Sign out** — clears the local token and the native Google session.
- 🔜 Email/password, Apple sign-in, magic links, multi-device session management, refresh tokens.

## 2. Conversations (chats)
- ✅ **New chat** — from the header `＋` and the drawer; created **lazily** on the first message
  (no empty "New chat" rows pile up).
- ✅ **Chat list** — grouped by **Today / Yesterday / Earlier**, newest first; refreshes when the
  drawer opens.
- ✅ **Open & load history** — full message history loads when a chat is opened.
- ✅ **Rename** — via the in-chat `⋯` menu (modal editor).
- ✅ **Delete** — via the in-chat `⋯` menu with a confirmation prompt (DB-level cascade removes its
  messages).
- ✅ **Search** — full-text search across all your chats and messages on a dedicated search
  screen (backend `/search`), plus the drawer's client-side title filter.
- ✅ **Pin** — pin/unpin a chat (chat `⋯` menu + drawer long-press); pinned chats show in a
  **Pinned** section at the top of the drawer.
- ✅ **Share / Export** — share a conversation as a markdown transcript via the native share sheet
  (chat `⋯` menu + drawer long-press); no backend needed.
- ✅ **Manage from the drawer** — long-press any chat for **Pin/Unpin · Share · Delete**.
- ✅ **Archive** — chats can be archived (chat `⋯` menu + drawer); archived chats show in a separate section and are excluded from the main list.
- 🔜 Folders, multi-select, and a true swipe-to-delete gesture (needs a gesture
  library + dev build).
- ✅ **Project-scoped chats** — chats created from a learning project carry `project_id` (see [§17](#17-projects-utility-workspaces)).

## 3. Messaging behaviour
- ✅ **Streaming** — token-by-token over WebSocket; the reply appears as it's generated.
- ✅ **Stop generation** — cancel mid-stream (send button becomes a stop button); the partial reply
  is kept.
- ✅ **Regenerate** — re-run the last assistant reply.
- ✅ **Message folding** — long user messages *and* long replies collapse past ~320px with a fade +
  **Show more / Show less** (disabled while a reply is still streaming).
- ✅ **Copy** — copy a whole message, and a dedicated copy button per code block.
- ✅ **Like / dislike** — thumbs up/down persist per message (saved to the backend and restored on
  load); tapping the active rating clears it.
- ✅ **Per-message model** — the model used is recorded on each message.
- ✅ **Edit & resend** — edit the **last** user message (pencil under the bubble); drops the old
  reply, rewrites the message, and re-runs. (Last-message only, so it never rewrites summarized
  history.)
- ✅ **Web search** — when the user's question needs fresh facts, the backend runs Tavily (or
  DuckDuckGo fallback) and injects results; source links render under the reply (skipped on vocab
  quiz turns).
- 🔜 Edit any earlier message, message-level share, reactions, read receipts, voice input.

## 4. Formatting & rendering
- ✅ **Markdown** — headings, **bold**/*italic*, bullet & numbered lists, blockquotes, links,
  inline code, horizontal rules.
- ✅ **Code blocks** — dark card, language badge, copy button, horizontal scroll.
- ✅ **Syntax highlighting** — token coloring (comments, strings, numbers, keywords) via a
  dependency-free tokenizer; covers common languages with a monochrome fallback for the rest.
- ✅ **Tables** — styled (header shading, borders, cell padding).
- ✅ **Inline images** — Markdown `![alt](url)` images render (contained, rounded).
- ✅ **Math / LaTeX** — inline `$...$` and ` ```math` fences render as native text with
  superscripts (x², ±, √). Server-side **SymPy** solves equations and samples graphs before the
  LLM explains (verified numbers injected into the prompt).
- ✅ **Geometry diagrams** — ` ```geometry` JSON fences render labeled rectangles (diagonal, angle)
  via native SVG (`react-native-svg`; works in Expo Go).
- ✅ **Function graphs** — ` ```graph` JSON fences plot y=f(x) from server-computed point arrays
  via native SVG.
- ✅ **Charts** — `chart` / `vega` / `vega-lite` fences render inline via a sandboxed WebView
  (Vega; needs a dev build).
- ✅ **HTML/CSS/JS preview** — `html` fences get a sandboxed WebView preview ("run" → modal) plus
  "open in browser" (needs a dev build; see the code-execution policy below).
- ✅ **Rich blocks** — callouts (`> [!NOTE]`), key-value, comparison, step lists, and
  email/message/social "copy" cards.
- ⚠️ **Mermaid diagrams** — shows the diagram source with copy + "Open in Mermaid Live" (not yet
  rendered inline).
- 🔜 **Grammar-perfect highlighting** — current highlighter is heuristic; a full library
  (Shiki/Prism) would be more precise.

## 5. Models & routing
- ✅ **Multiple tiers** — **Flash** (`free-chat`) and **Pro** (`smart-chat`), plus **Max**
  (`max-chat`, OpenRouter) which appears once an OpenRouter key is configured.
- ✅ **Manual switching** — model picker in the composer + a default in Settings (respected).
- ✅ **Auto routing** — an **Auto** chip (composer + Settings) picks Flash vs Pro per message via a
  fast heuristic (length, code fences, reasoning keywords). No extra LLM call.
- ✅ **Multi-provider** — a **model catalog** (`services/model_catalog.py`) defines provider, model,
  key, base URL, and pricing per entry. DeepSeek is active; OpenRouter is wired and activates the
  moment its key is set. Adding a provider/model is a one-line catalog entry.
- ✅ **Model availability + cost** — `GET /models` reports each model's availability (key present)
  and price; the picker shows available models with a per-1M-token cost hint.
- 🔜 **Live latency/health checks** and **user-tunable routing rules** (need runtime metrics +
  a rules UI/storage).

## 6. Memory (remembering the user)
- ✅ **Automatic extraction** — durable facts are extracted in the background **every turn**.
- ✅ **Typed memories** — `profile` · `preference` · `project` · `fact` · `focus` (captures things
  like interests, what they're working on, name, job, country when mentioned).
- ✅ **Quality controls** — confidence threshold, de-duplication, priority ordering, capped count.
- ✅ **Prompt injection** — relevant memories are added to the system prompt.
- ✅ **Semantic recall** — when `semantic_memory_enabled` (default on), the user's latest message
  is embedded and the top matching memories are selected (cosine similarity on stored embeddings;
  falls back to priority ordering when embeddings are missing).
- ✅ **Memory screen** — view memories grouped by type, with confidence, and **delete** them.
- ✅ **Memory toggle** — turn learning on/off in Settings.
- 🔜 **Structured profile fields** — name/age/country/job as discrete fields (today they're
  free-text memories).
- 🔜 **Full RAG over chats/docs** — memory uses embeddings today; pgvector over attachments and
  chat history is not built yet.

## 7. Context management & performance
- ✅ **Token-budget window** — recent turns are kept verbatim up to a token budget
  (`context_token_budget`, with a hard message cap), never the whole transcript.
- ✅ **History compression** — turns that fall outside the token budget are folded into a rolling
  per-chat **summary** (batched, runs on the durable job queue), so long chats keep context
  without bloating the prompt.
- ✅ **Memory caching** — the assembled memory block is cached in Redis per user (with
  invalidation on new/deleted memories) instead of rebuilt every turn.
- ✅ **Provider context caching** — DeepSeek caches prompt prefixes automatically.
- ✅ **Snappy delivery** — async backend, streaming, virtualized message list; DB connection is
  released during the model stream.
- 🔜 Response caching, parallelized pre-stream reads, prompt token budgeting UI.

## 8. Titles / topics
- ✅ **Auto title** — a concise title is generated after the first exchange (cheap model).
- ✅ **Backfill** — missing titles are generated when a chat is opened.
- ✅ **Manual rename** — overrides the generated title.

## 9. Quotas & usage
- ✅ **Daily token limit** — enforced in Redis with atomic **reserve → adjust → refund** (can't be
  bypassed by parallel requests). Free tier default 30k/day; Pro tier 500k/day (`DAILY_TOKEN_LIMIT_PRO`).
- ✅ **Plan-aware enforcement** — quota service reads the user's subscription plan before reserving.
- ✅ **Usage meter** — today's tokens vs. daily limit shown in Settings.
- ✅ **Real token accounting** — uses the provider's reported usage when available.
- ✅ **Pro tier** — higher daily limit when entitled; see [§12 Monetization](#12-monetization).

## 10. Settings & profile
- ✅ **Account** — shows name + email.
- ✅ **Default model** — Flash / Pro.
- ✅ **Response style** — short / balanced / detailed (changes the assistant's verbosity).
- ✅ **Memory** — on/off toggle + link to manage saved memories.
- ✅ **Usage** — today's token meter.
- ✅ **Sign out.**
- ✅ **Edit name** — editable in Settings (Account → pencil → save).
- ✅ **Data export** — exports your full data (profile + chats + messages + memories) as JSON via the
  native share sheet (`GET /auth/me/export`).
- ✅ **Account deletion** — permanently deletes the account and all its data (`DELETE /auth/me`),
  then signs out.
- ✅ **Avatar** — shows the Google profile picture, falling back to the user's initials (no upload
  by design).
- ✅ **Language / i18n** — `react-i18next` with English, Spanish, French, Amharic, German, Italian, Portuguese, Russian, and Turkish.
- ⚠️ **Dark theme** — the chat screen follows the system light/dark scheme; the remaining screens
  are still light (theme rollout in progress).
- ✅ **Local todo reminders** — scheduled on-device notifications when a todo item is due (via
  `expo-notifications`; requires a dev build for full native support).
- ✅ **Remote push (MVP)** — Expo push tokens registered with the backend; learning-review and
  todo-due notifications (requires dev build + EAS project ID).
- 🔜 Email reminders, theming the remaining screens.

## 11. Navigation & UX
- ✅ **Drawer** — custom slide-in: search, New chat, chat history, profile + settings.
- ✅ **Chat screen** — composer with model picker, top-right `＋` (new) and `⋯` (Share / Rename /
  Pin / Delete).
- ✅ **States** — login, loading, empty chat ("How can I help?"), empty memory, drawer offline/retry.
- ✅ **Onboarding** — a first-run welcome screen (value props + "Get started"), shown once before
  the first sign-in.
- ✅ **"Recalled" chips** — when a reply used your memories, a subtle "✨ Recalled N memories" chip
  fades in above it (live replies only).
- ✅ **Polish** — light haptic taps on key actions (Android via the built-in API) + chip fade-in
  animation.
- ✅ **iOS haptics** — `expo-haptics` on real devices (graceful no-op on Android / Expo Go).
- 🔜 Richer screen transitions.

## 12. Monetization
- ✅ **Pro subscription (RevenueCat)** — mobile purchase flow via lazy-loaded `react-native-purchases`
  (dev/production builds only; skipped in Expo Go). Restore purchases supported.
- ✅ **Backend entitlement** — RevenueCat webhook + `POST /auth/me/sync-subscription`; `users.plan`
  drives quota limits and model access.
- ✅ **Upgrade sheet** — locked Pro models open an upgrade sheet with subscribe/restore when RevenueCat
  is configured.
- ✅ **Dev Pro toggle** — Settings → tap a locked model → **Enable Pro (dev only)** in the upgrade
  sheet (development builds only; calls a dev-only backend endpoint).
- 🔜 App Store / Play billing polish, promotional offers, family plans.

## 13. Platform, security & infrastructure
- ✅ **Backend** — FastAPI (async), WebSocket streaming, layered (routers → services →
  gateways/repositories).
- ✅ **Data** — Neon Postgres via SQLAlchemy + Alembic migrations; Upstash Redis for quota/cache.
- ✅ **Model gateway** — LiteLLM with product aliases mapped to providers; mock mode runs the whole
  app with no API keys.
- ✅ **Security** — Google ID-token verification (incl. `email_verified`), rate limiting on
  auth + WebSocket, production config guards (no dev auth / mock / weak secret in prod),
  locked-down CORS.
- ✅ **Ops** — `/health` liveness + `/health/ready` (DB + Redis) checks, graceful shutdown, DB
  connection pooling.
- ✅ **Quality** — CI (Postgres + Redis services, ruff, mypy, pytest with coverage gate).
- ✅ **Background jobs** — title / memory / compression are enqueued to a **durable Redis Stream**
  and processed by an in-process worker (consumer group). Jobs survive process restarts, and an
  entry left unacked by a crash is reclaimed on the next startup (at-least-once).
- 🔜 **Dedicated worker process** (for multi-instance / serverless), Sentry/observability,
  structured request logging.

## 14. Todos, templates & suggestions
- ✅ **Todo lists** — named lists (topics) with a list-first UX: create a list title, then add items;
  drawer shows a single **Todos** entry (not per-list submenus).
- ✅ **Todos API** — create, check off, delete items; delete entire list by topic; optional `due_at`.
- ✅ **LLM todo sync** — background job extracts add / complete / uncheck / delete / delete_list /
  set_due / clear_due from chat; injects current lists + overdue summary into the system prompt.
- ✅ **Due dates** — `due_at` on items; mobile date/time picker; relative labels in prompts
  (overdue, due today, due in N days); user timezone synced from device (`users.timezone`).
- ✅ **Local due reminders** — schedules a device notification at due time; resyncs on login,
  foreground, and todo changes; tap opens Todos screen.
- ✅ **Templates** — reusable starter prompts: built-in templates seeded on first run plus the
  user's own; start a chat from a template.
- ✅ **Proactive suggestions** — follow-up prompt ideas generated in the background from recent
  activity (best-effort; regenerated periodically).
- 🔜 Surfacing suggestions inline under replies, template-editing polish, 1-hour-early reminders,
  remote push / email nudges.

## 15. Code execution policy
- ⚠️ **Sandboxed HTML/CSS/JS preview only** — `html` fences can be previewed/run in an isolated
  WebView (no app token is exposed to it), and charts render via a sandboxed Vega WebView.
- 🔒 **No other code execution** — all other code (Python, shell, etc.) is rendered/highlighted
  only, and nothing runs outside the sandboxed preview WebView. (By design.)

## 16. MCP & calendar (planned)

Connect external context (starting with Google Calendar) so the assistant knows the user's schedule,
can align todos with meetings, and eventually act via tools — **all server-side** (no MCP secrets or
calendar tokens on the mobile app).

```
Mobile → Recall API → MCP / calendar gateway → Google Calendar
                    ↘ memory / todos / chat (existing)
```

### Phase 1 — Calendar connect (before full MCP)
- ✅ **Google Calendar OAuth** — separate opt-in from sign-in; scope `calendar.readonly`; refresh
  token stored server-side only.
- ✅ **`user_calendar_connections` table** — refresh token, granted scopes, primary calendar id.
- ✅ **`calendar_service.py`** — fetch events for a window (today → +60 days); Redis cache (~5 min)
  so every chat turn doesn't hit Google.
- ✅ **Prompt injection** — compact calendar block next to todos/memory (title, start/end, optional
  location; minimal PII).
- ✅ **Settings UI** — Connect / disconnect Google Calendar; shows connected email.
- ✅ **Reminders calendar UI** — Google events on the day view alongside in-app reminders (all
  **selected** calendars on the connected account, not primary only).

Unlocks: "What's on my calendar tomorrow?", conflict checks vs todo due dates, smarter scheduling
suggestions using existing `users.timezone` and `todo_items.due_at`.

### Phase 1b — Gmail → suggested reminders
- ✅ **Gmail OAuth** — opt-in from Settings (separate from Calendar); read-only inbox scope;
  refresh token server-side only.
- ✅ **`user_gmail_connections` table** — scopes, sync cursor, connected email.
- ✅ **`email_service.py`** — fetch recent mail, dedupe by message id, LLM extraction with Pydantic
  validation before DB writes.
- ✅ **Suggested reminders API** — list / dismiss / confirm → create in-app todo.
- ✅ **Suggested reminders UI** — Reminders screen "From email" section + chat nudge chip;
  confirm before add (no silent auto-add).
- ✅ **Background sync** — periodic Gmail sync job enqueued after connect.
- 🔜 Higher-confidence `.ics` parsing paths, richer sender templates, proactive chat nudges.

**Privacy & UX** (unchanged intent)
- Clear copy: what is read, how long it is kept, revoke = stop + delete tokens
- Minimal retention; user confirms every suggestion in v1

**Out of scope for v1** (unchanged)
- Reading mail from a **different** Google account than the one connected
- Google Tasks / Keep reminders
- Sending email or replying from Recall
- Full inbox UI in the app

### Phase 2 — MCP layer
- ✅ **MCP gateway skeleton** — `gateways/mcp/` with registry + adapters (`web_search`, `calendar`).
- ⚠️ **Pre-stream tool round** — when `MCP_TOOLS_ENABLED=true`, `chat_tools.py` invokes matching
  adapters once before streaming (web search query, calendar write hint). Not a full multi-turn
  LiteLLM `tools=` loop yet.
- 🔜 **Full tool-calling loop** — model-initiated tool rounds via LiteLLM; prerequisite for richer
  agents.
- 🔜 **Golden rules preserved** — product aliases in services; structured outputs validated with
  Pydantic before DB writes (already enforced for calendar proposals and email extraction).

### Phase 3 — Smarter behavior
- ✅ **Conflict detection** — todo due times vs calendar events (server-side helper).
- ✅ **Create calendar events (confirm flow)** — user asks to schedule → model emits
  `calendar_proposal` fence → backend stores Redis proposal + injects `proposal_id` → mobile
  **Add to Calendar** card → confirm creates the Google event (requires calendar **write** scope).
- 🔜 **Proactive nudges** — combine overdue todos + today's calendar in chat or push ("leave now —
  meeting in 15 min").

### Privacy & UX
- Opt-in connect; revoke clears tokens and stops injection.
- Minimal event data in prompts; no full attendee lists unless the user asks.
- v1 non-goals: arbitrary user-configured MCP servers, syncing every on-device calendar locally,
  running MCP on the phone.

### Suggested build order
1. Google Calendar read-only + prompt injection ✅
2. Settings "Connect calendar" ✅
3. Calendar events on Reminders calendar UI ✅
4. Calendar-aware chat answers (no MCP protocol yet) ✅
5. **Gmail read-only → suggested reminders** ✅
6. MCP gateway abstraction + pre-stream adapter round ⚠️
7. Write calendar events / confirm UX ✅
8. Full LiteLLM tool-calling loop 🔜
9. Email auto-add for high-confidence types (optional, post-MVP) 🔜

---

## 17. Projects (utility workspaces)

Recall is evolving from chat-only into a **holistic AI utility app**. **Projects** are
user-created workspaces beside **Todos** — for learning English, programming practice, courses,
habits, and anything else that needs structure over time.

### v1 (shipped foundation)
- ✅ **`projects` table** — title, description, `kind` (`general` | `vocabulary` | `programming` |
  `learning`), archive flag.
- ✅ **REST API** — `GET/POST /projects`, `GET/PATCH/DELETE /projects/{id}`.
- ✅ **Mobile** — drawer **Projects** link → list → create → detail screen.
- ✅ **Project kinds** — taxonomy hook for different toolkits per type (no modules yet).

### Phase 2 — Vocabulary (Learning English)
- ✅ **Decks / groups** — organize words by deck title; part-of-speech grouping on detail screen.
- ✅ **Vocab items** — term, definition, example sentence, status (new / mastered), review tracking.
- ✅ **Mark as known** — progress per item; stats on project detail (learned / due / this week).
- ✅ **AI tutor + quiz** — "Ask Recall" and "Quiz with Recall" launch scoped chats; model emits
  `vocab_quiz` blocks; mobile shows A–D choices with fast-path answers (minimal context, no web
  search on quiz turns).
- 🔜 **Pronunciation** — TTS play button per word (uses audio-out substrate).
- 🔜 **Spaced repetition scheduling** — due-for-review uses last_reviewed_at today; richer SM-2-style
  scheduling not built yet.

### Phase 3 — Cross-linking
- ✅ **`project_id` on chats** — conversations started from a project carry `project_id`; prompt
  injection scopes to that one project (+ tutor hints) instead of all projects.
- 🔜 **Link todos to projects** — due dates + project goals in one view.
- ✅ **Home starters** — active project highlight on home; tap opens project or starts scoped chat.

### Phase 4 — More project types
- ✅ **Programming** — language-specific curriculum seeded on create; journey lists + "Continue" /
  per-topic study prompts; push nudge to resume learning.
- 🔜 **Learning (generic)** — lesson notes, spaced repetition beyond vocab, richer AI tutor mode.

Chat + memory + todos + projects share one backend; the LLM orchestrates across them (no keys on
device).

---

## Deferred to upcoming version(s)
A consolidated list of what's intentionally **not** in this version:

- 🔜 **Full MCP / multi-turn tool loop** — pre-stream adapter round exists; LiteLLM `tools=` loop not
  built yet. See [§16 MCP & calendar](#16-mcp--calendar-planned).
- 🔜 **Plugins / arbitrary user MCP servers**
- 🔜 **Full RAG** (pgvector over attachments + chat corpora; memory embeddings exist today)
- 🔜 **Code execution** (beyond sandboxed HTML/chart preview)
- ⚠️ **File / image upload** — attachment substrate partially wired; not full vision/RAG pipeline
- 🔜 **Image input/output** (multimodal models end-to-end)
- 🔜 **Camera math solver** — snap a photo of a math problem → AI reads it, solves it, and renders
  the worked, step-by-step solution formatted to match the problem. Composite feature, built on:
  camera capture (`expo-camera` / image picker), **image input** via a **vision model or math OCR**,
  and **LaTeX rendering** for the formatted answer. (Depends on the image-input + Math/LaTeX items.)
- ✅ **Web search** — Tavily primary + DuckDuckGo fallback; injected into chat when heuristics match;
  sources shown on assistant messages (hidden on vocab quiz cards).
- 🔜 Inline Mermaid rendering, grammar-perfect (library) syntax highlighting, structured profile,
  dedicated worker process, multi-select, swipe-to-delete (gesture lib), editing arbitrary
  (older) messages, live model latency/health, user-tunable routing rules, email-only reminders,
  theming the remaining screens.

### Pre-deployment TODO (from the holistic review)

Action items still open before the first production deploy. The security/data-integrity
fixes from the review are shipped; these remain:

- ⚠️ **R2 storage credentials** — the `R2StorageGateway` is wired and tested, but attachments
  run on local fallback until `STORAGE_BACKEND=r2` + `R2_ACCOUNT_ID` / `R2_ACCESS_KEY_ID` /
  `R2_SECRET_ACCESS_KEY` / `R2_BUCKET` secrets are set. (Code done; creds pending.)
- ⚠️ **Production env secrets** — `validate_production_settings` now enforces
  `OAUTH_TOKEN_ENCRYPTION_KEY`, `OPENROUTER_API_KEY`, `CORS_ORIGINS`,
  `REVENUECAT_WEBHOOK_AUTH` (plus the existing DB/Redis/Google/JWT/dev-flags). The
  `OPENROUTER_API_KEY` also makes the `fallback-memory-model` actually resolve.
- 🔜 **Mobile gate + on-device pass** — `pnpm typecheck && pnpm lint && pnpm test` must run
  locally (deps don't install in the CI/dev-container env). Then an iOS **and** Android
  dev-build pass for: Google Sign-In, HTML/chart preview WebView, push, RevenueCat, the new
  cross-platform deck Modal, autoscroll, and the markdown throttle.
- ✅ **FlashList migration** — `ConversationList` and `Todos` now use `FlashList`
  (v2, auto-measured). Chat drawer rows and the flat reminders/done lists are
  virtualized; the calendar day-view and `ListGroupsView` render in the header
  (bounded/structured, not row-virtualized). Verify scroll/layout on-device.
- 🔜 **i18n migration** — the new UI keys are now in all 9 locale files (English
  placeholder values for the 8 non-EN locales — translate when ready). Hardcoded
  English still remains in: the legal pages (`privacy`/`terms`), `todoReminders`
  ("Reminder" title/body), `homeUrgentTodos` prompts/subtitles, and `share.ts`
  ("You"/"Recall"). Those strings need extracting to keys + translations.
- 🔜 **DB session scope in `_prepare_chat_turn`** — the session is held through web
  search/embeddings/calendar/Gmail/MCP prep, which can starve the Neon pool under concurrent
  streams. Load → close → external I/O → reopen for writes. (Non-trivial refactor; deferred
  as a follow-up, not a ship blocker for single-user MVP scale.)
- 🔜 **Background-job DLQ / WS per-message re-auth** — failed jobs are ACKed by design
  (poison-pill avoidance); a DLQ would make them visible/retryable. WS auth is checked once
  at connect (7-day JWT); per-message re-auth is overkill — a shorter JWT expiry is the
  better lever. Both deferred as judgment calls.

### Multimodal & attachments (planned)

Richer inputs/outputs, grouped because they share one prerequisite — an **attachments
substrate** — so it's built once and reused by all of them.

- 🔜 **Attachments substrate (build first)** — object storage on **S3** (or an
  S3-compatible store such as **Cloudflare R2** to avoid egress fees when the app
  re-downloads media), accessed via **presigned upload/download URLs** so the client
  talks to storage directly and provider/storage keys stay server-side. Adds an
  `attachments` table (owner, message link, storage key, content-type, size) — blobs
  never live in Postgres. Private bucket + short-lived signed URLs, per-user scoping,
  content-type/size validation.
- 🔜 **Image upload (vision)** — attach or take a photo; routed to a vision-capable
  catalog model (e.g. MiniMax M3 / other multimodal model). The message `content`
  becomes a parts array (text + image reference) instead of a plain string.
- 🔜 **File upload (PDF, docs, etc.)** — upload → extract text server-side → chunk →
  retrieve (pairs with the RAG / pgvector item) → answer; file shown as an attachment chip.
- 🔜 **Audio in (speech-to-text)** — record on device → transcribe (Whisper/STT) → feed
  the transcript as a normal text turn. Minimal impact on the chat core.
- 🔜 **Audio out (text-to-speech)** — "read aloud" the assistant's reply (TTS → play
  audio). Output-only.
- 🔒 **Out of scope: full voice mode** — real-time, full-duplex spoken conversation
  (low-latency streaming, barge-in) is its own project; deferred indefinitely.

Notes: multimodal routes through whichever catalog model supports the modality (DeepSeek
is text-only), so each capability activates per provider/model as they're added. Multimodal
calls cost more than text — likely gate behind a paid tier + the existing token quota.

### Web client (planned)

A future **web version that reuses this same API** — one backend, multiple clients.

- 🔜 **Shared API + types** — the web app consumes the same HTTP/WebSocket endpoints and
  request/response shapes; eventually extract the `lib/api.ts` types/client into a package both
  apps import. Bearer-token (JWT) auth already works cross-origin.
- 🔜 **Web-specific swaps** — `expo-secure-store` → httpOnly cookie / web storage; native Google
  Sign-In → web OAuth; the `react-native-webview` previews → a real `<iframe>` / native HTML.
  Keep rich-block rendering behind components so only the renderer differs per platform.
- 🔜 **Backend** — add the web origin(s) to `cors_origins` (CORS is locked down by env) and allow
  them on the WebSocket; no other backend change needed.
- 🔜 **Approach to decide later** — react-native-web (reuse this Expo codebase) vs. a separate web
  app (e.g. Next.js) sharing only the API + types. Same API either way.
