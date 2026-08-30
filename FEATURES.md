# Recall — Feature Coverage & Roadmap

A reference of what the app does **today** versus what is **deferred** to a future version.
Recall is a personal AI chat app: a snappy chatbot with clean formatted answers, multi-model
support, and long-term memory of the user. Mobile = Expo (React Native). Backend = FastAPI +
Neon Postgres + Upstash Redis + LiteLLM (OpenRouter).

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
- ✅ **Sessions** — JWT (HS256) access token (1h) + Redis-backed refresh token (30d), stored in
  secure storage; `POST /auth/refresh` and `POST /auth/logout` with access-token revocation.
- ✅ **Auto sign-out on 401** — refresh is attempted first; if it fails, the user is signed out.
- ✅ **Sign out** — revokes server tokens, clears local storage, and signs out of Google.
- ✅ **Sign in with Apple** — iOS only (hidden on Android); requires Apple capability on App ID.
- 🔜 Email/password, magic links, multi-device session management.

## 2. Conversations (chats)
- ✅ **New chat** — from the header `＋` and the drawer; created **lazily** on the first message
  (no empty "New chat" rows pile up).
- ✅ **Chat list** — grouped by **Today / Yesterday / Earlier**, newest first; refreshes when the
  drawer opens.
- ✅ **Open & load history** — full message history loads when a chat is opened.
- ✅ **Rename** — via the in-chat `⋯` menu (modal editor).
- ✅ **Delete** — via the in-chat `⋯` menu with a confirmation prompt (DB-level cascade removes its
  messages).
- ✅ **Search** — full-text search across chats and messages via the drawer search bar
  (backend `/search` with debounce + pagination).
- ✅ **Pin** — pin/unpin a chat (chat `⋯` menu + drawer long-press); pinned chats show in a
  **Pinned** section at the top of the drawer.
- ✅ **Share / Export** — share a conversation as a markdown transcript via the **native OS
  share sheet** (Messages, Mail, Files, …); export a chat as PDF from the in-chat `⋯` menu;
  export a learning topic as PDF. Chat `⋯` + drawer long-press (share/pin/archive/delete);
  no backend. This is **not** a
  ChatGPT-style public `chatgpt.com/share/…` URL — anyone with that kind of link could
  read the thread without signing in. Public web links are a separate privacy feature
  (not started; do not assume we have them).
- ✅ **Manage from the drawer** — long-press any chat for **Pin/Unpin · Share · Archive · Delete**.
- ✅ **Library** — drawer **Library** → paginated grid of the user’s verified attachments
  (generated images, uploaded images, and files). Tabs: All / Generated / Uploaded / Files.
  Search is a case-insensitive substring on filename, MIME type, and the **linked message
  body**. For generated images that includes the **previous user message** (the draw
  prompt) and the prompt stored on `original_filename`, not only the assistant
  `[Image: …]` marker. Tap an image to view, with **Open chat** when the attachment is
  still linked; tap a file to share (no in-library preview). Deleting a chat removes
  its attachments from Library (unlinked leftovers are hidden; missing files drop
  the row instead of showing a blank 404 tile). Opening Library warms the All page
  from the drawer tap (20s cache, same window as Memory); tab snapshots avoid a
  wrong-grid flash. Logout, chat delete, upload, and image-gen invalidate it.
- ✅ **Archive** — drawer long-press and in-chat `⋯` menu; archived chats show in a separate
  section and are excluded from the main list.
- ✅ **Multi-select** — drawer **Select** mode: tap rows to choose, then bulk **Archive** or
  **Delete** (with confirm).
- 🔜 Folders.
- ✅ **Project-scoped chats** — chats created from a learning project carry `project_id` (see [§17](#17-projects-utility-workspaces)).

## 3. Messaging behaviour
- ✅ **Streaming** — token-by-token over WebSocket; the reply appears as it's generated.
  Ordinary turns show typing dots only (no “loading memory / working on it” staircase).
  Status labels are reserved for real extra work: web search, files, calendar, inbox,
  math, and image gen. Turn start overlaps waiting for the previous reply to persist
  with user/quota load (regenerate still waits first so it does not miss that reply).
  Learning quiz lookback and attachment-chunk probes run only when they can apply;
  time/location answers skip a database checkout.
- ✅ **Stop generation** — cancel mid-stream (send button becomes a stop button); the partial reply
  is kept. Hard WS/SSE disconnect with tokens already streamed also finalizes (same as soft stop).
- ✅ **Regenerate** — re-run the last assistant reply.
- ✅ **Message folding** — long **user** messages collapse past ~320px with a fade +
  **Show more / Show less** (disabled while a reply is still streaming). Assistant replies do
  **not** fold (code blocks may still fold). Do not reintroduce assistant-body folding.
- ✅ **Copy** — copy a whole message, and a dedicated copy button per code block.
- ✅ **Like / dislike** — thumbs up/down persist per message (saved to the backend and restored on
  load); tapping the active rating clears it.
- ✅ **Per-message model** — the model used is recorded on each message.
- ✅ **Edit & resend** — edit a user message (pencil under the bubble); truncates forward from that
  turn, rewrites the message, and re-runs.
- ✅ **Web search** — when the user's question needs fresh facts, the backend runs Tavily (or
  DuckDuckGo fallback) and injects results; source links render under the reply (skipped on vocab
  quiz turns).
- ✅ **Voice input (STT)** — mic in the composer records on-device (`expo-audio`, **dev build**),
  transcribes via Whisper (OpenRouter), and injects the transcript as normal text. Daily caps
  (30 free / 200 Pro). Not available in Expo Go.
- ✅ **Live talk (Pro)** — waveform on the composer opens a **speech-to-speech** session
  (OpenAI GPT Audio via OpenRouter: audio in → spoken reply, **not Whisper**). Short pause
  ends your turn; the orb never shows “Transcribing…”. Not full duplex. Free is blocked
  (upgrade). Pro: **30 turns/day** (UTC). Composer mic STT remains Whisper.
- ✅ **Read aloud (TTS)** — speaker streams OpenRouter **Gemini 3.1 Flash TTS** PCM
  (`POST /speech/tts` lead then rest) and starts playback on the first sentence; **Kokoro 82M**
  is the cheap alternative (`speech-tts-fast-model`). Dev build required. JSON `POST /speech/tts`
  remains for non-streaming clients.
- 🔜 Reactions, read receipts; full duplex / interruptible live voice (later).

## 4. Formatting & rendering
- ✅ **Markdown** — headings, **bold**/*italic*, bullet & numbered lists, blockquotes, links,
  inline code, horizontal rules.
- ✅ **Code blocks** — dark card, language badge, copy button, horizontal scroll.
- ✅ **Syntax highlighting** — **Prism.js** token coloring for 40+ languages (comments, strings,
  numbers, keywords); heuristic fallback for unknown langs.
- ✅ **Tables** — styled (header shading, borders, cell padding).
- ✅ **Inline images** — Markdown `![alt](url)` images render (contained, rounded).
- ✅ **Image generation (Pro)** — Type an image request in the composer and send (e.g. "draw me a
  cat"); the user bubble keeps that wording (not rewritten to "Generate image: …"). Pro users
  get daily-limited generations stored as chat attachments. No separate prompt sheet. Stop
  mid-generation keeps the user message and shows canceled/failed + Retry. Tap the result to
  view full-screen and save via the system share sheet.
- 🔜 **Music generation** — same composer-send path as image gen (no prompt sheet): user asks
  to generate a track, we generate a clip, store it as an audio attachment, and show a **compact
  inline player** on the assistant message (play/pause + scrub + duration — not a full-screen
  Now Playing UI). Pro + daily cap. Catalog alias + gateway (provider TBD); reuse
  `expo-audio` / attachment URLs. Do not start until image-gen’s storage/cap path is the
  template. Not TTS / not humming into the mic.
- ✅ **Math / LaTeX** — inline `$...$` renders as native text (superscripts, √, fractions);
  display ` ```math` uses KaTeX (or MathJax for heavy expressions) in a WebView on a
  **dev build**, with native/`MathText` fallback in Expo Go. Tall WebViews offer **Expand** →
  fullscreen scroll. Server-side **SymPy** solves equations and samples graphs before the LLM
  explains (verified numbers injected into the prompt; Recall attaches geometry,
  graph, and algebra ` ```answer ` after the stream). The composer **math keypad** inserts
  LaTeX (Basics + 6-column numpad; Trig / Calc / Greek; Converter can **Insert** the live
  result into the draft). See [docs/math.md](./docs/math.md).
- ✅ **Geometry diagrams** — ` ```geometry` JSON fences render labeled shapes (rectangle, circle,
  triangle, trapezoid, sector, …) via native SVG (`react-native-svg`; works in Expo Go).
- ✅ **Function graphs** — ` ```graph` JSON fences plot y=f(x) from server-computed point arrays
  via native SVG.
- ✅ **Charts** — `chart` / `vega` / `vega-lite` fences render inline via a sandboxed WebView
  (Vega; needs a dev build).
- ✅ **HTML/CSS/JS preview** — `html` fences get a sandboxed WebView preview ("run" → modal) plus
  "open in browser" (needs a dev build; see the code-execution policy below).
- ✅ **Rich blocks** — callouts (`> [!NOTE]`), key-value, comparison, step lists, and
  email/message/social "copy" cards.
- ✅ **Fence ownership** — [fenceRegistry.ts](apps/mobile/lib/fenceRegistry.ts) marks each
  fence `model` / `server` / `legacy`. New turns: Markdown plus a small model-facing
  set (`copy` / drafts, `mermaid`, `chart`, `math`, chemistry source). Server attaches
  verified `answer` / `graph` / `geometry`, `sources`, and `places`. Layout fences
  (`steps`, `comparison`, `keyvalue`, `collapsible`, `quote`, `clock`, `callout`)
  still render for history; the prompt must not choose them. Calendar / reminder /
  settings / vocab-quiz control fences stay outside the registry.
- ✅ **Mermaid diagrams** — inline SVG render via sandboxed WebView (dev build); source toggle +
  copy + Mermaid Live link; Expo Go shows source + external editor hint.
- ✅ **PDF attachments** — uploaded PDFs show a file card + inline first-page preview (pdf.js in
  sandboxed WebView, dev build); tap opens full viewer with share/export.
- 🔜 **Collaborative cursors / shared docs** — multi-user editing not in scope for v1 personal app.

## 5. Models & routing
- ✅ **Multiple tiers** — **Flash** (`free-chat`) and **Pro** (`smart-chat`), plus named
  models in the picker (Llama, GPT 5.5, GLM, …). No OpenRouter-auto “Max” chip.
- ✅ **Manual switching** — model picker in the composer + a default in Settings (respected).
- ✅ **Chat settings from natural language** — small allowlist, confirm-then-write
  (calendar-proposal style): model (Flash / Pro / Auto, nicknames like “GPT” → GPT 5.5),
  tone (funny / professional / casual / soft), app language, and appearance
  (light / dark / system — applied on-device). Respects `enabled_models` + plan.
  No open settings tool. Daily learning goal still Settings-only.
- ✅ **Auto routing** — an **Auto** chip (composer + Settings) picks Flash vs Pro per message via a
  fast heuristic (length, code fences, reasoning keywords). No extra LLM call.
- ✅ **Multi-provider** — a **model catalog** (`services/model_catalog.py`) defines provider, model,
  key, base URL, and pricing per entry. All chat aliases route through **OpenRouter** via LiteLLM
  (`gateways/litellm_gateway.py`). Adding a model is a catalog entry + OpenRouter slug.
- ✅ **Model availability + cost** — `GET /models` reports each model's availability (key present)
  and price; the picker shows available models with a per-1M-token cost hint.
- ✅ **Live latency/health** — Redis rolling samples from stream outcomes; `GET /models` exposes
  `healthy`, `latency_p50_ms`, and sample count. Settings shows degraded / latency.
- 🔜 **User-tunable routing rules** (custom per-message heuristics beyond Auto + enabled set).

## 6. Memory (remembering the user)
- ✅ **Automatic extraction** — durable facts are extracted in the background every N
  turns (`memory_extract_every_n_turns=3` by default; always on turn 1).
- ✅ **Extraction hygiene** — only user-stated/confirmed facts; transcript capped ~4k
  (head+tail); memory wrapped as first-party notes (fence kept); account email injected
  only for email/draft/inbox intents.
- ✅ **Typed memories** — `profile` · `preference` · `project` · `fact` · `focus` (captures things
  like interests, what they're working on, name, job, country when mentioned).
- ✅ **Quality controls** — confidence threshold, de-duplication, priority ordering, capped count.
- ✅ **Prompt injection** — profile/preference always; fact/focus/project only when
  similarity clears `memory_min_similarity` (default 0.35), with a char budget.
- ✅ **Semantic recall** — when `semantic_memory_enabled` (default on), the user's latest message
  is embedded and the top matching memories are selected (cosine similarity on stored embeddings;
  falls back to priority ordering when embeddings are missing).
- ✅ **Memory screen** — view memories grouped by type, with confidence, and **edit / delete**
  them. Storage is one consolidated row per type (`profile` / `preference` / …); deleting a
  single fact rewrites that section rather than removing a separate row per bullet.
  `PATCH /memories/{id}` updates text, re-embeds, and invalidates caches.
- ✅ **Memory toggle** — turn learning on/off in Settings.
- ✅ **Structured profile fields** — name, age, country, and job are discrete account fields
  (editable in Settings → Profile) and injected into the chat system profile block.
- ✅ **Attachment RAG** — chunk + embed PDF/doc text into pgvector; retrieve top chunks
  into the system prompt on **later turns in the same chat** (`chat_id` on chunks — **not**
  a user-wide file library). Prepare uses the **text layer only**; scanned-PDF vision OCR
  runs on the **index job**, not the pre-stream path. First turn uses the inline
  text-layer excerpt. Invalidated on attachment delete. Flag: `attachment_rag_enabled`
  (default on).
- ✅ **Chat-history semantic RAG** — background `message_index` embeds past turns into
  `message_chunks` (pgvector). Turn start retrieves a small top-k, excluding the recent
  window. Golden Rule 3 still holds — never the full transcript. First index also
  backfills the user's recent 40 messages so older chats are searchable after one turn.

## 7. Context management & performance
- ✅ **Token-budget window** — recent turns are kept verbatim up to a token budget
  (`context_token_budget`, with a hard message cap), never the whole transcript.
- ✅ **History compression** — turns that fall outside the token budget are folded into a rolling
  per-chat **summary** (batched, runs on the durable job queue), so long chats keep context
  without bloating the prompt.
- ✅ **Memory caching** — the assembled memory block is cached in Redis per user (with
  invalidation on new/deleted memories) instead of rebuilt every turn.
- ✅ **Provider context caching** — OpenRouter/provider prompt-prefix caching when the upstream
  model supports it (transparent to the app).
- ✅ **Snappy delivery** — async backend, streaming, virtualized message list; DB connection is
  released during the model stream.
- ✅ **Parallelized pre-stream reads** — memory, todos, projects, recent titles, and attachment
  RAG gather on separate short-lived sessions so the prompt path stays concurrent without
  sharing one `AsyncSession`.
- ✅ **Slim casual turns** — coaching / chit-chat uses a compact format + math-safety hint (not
  the full visualization/math-solver pack) and skips calendar/gmail-nudge and web/math/chem
  prefetch unless the turn is rich or actually needs search, math, chemistry, or calendar/gmail.
- ✅ **Prompt token budgeting UI** — Settings → Models shows today's used / daily
  limit (input · output split) and the server prompt window
  (`context_token_budget`, last `recent_message_window` messages). The composer
  shows a local draft estimate when the text is large enough to matter.
- 🔜 Response caching.

## 8. Titles / topics
- ✅ **Auto title** — a concise title is generated after the first exchange (cheap model).
- ✅ **Backfill** — missing titles are generated when a chat is opened.
- ✅ **Manual rename** — overrides the generated title.

## 9. Quotas & usage
- ✅ **Daily token limit** — enforced in Redis with atomic **reserve → adjust → refund** (can't be
  bypassed by parallel requests). Free tier default **100k**/day; Pro tier **500k**/day
  (`DAILY_TOKEN_LIMIT` / `DAILY_TOKEN_LIMIT_PRO`).
- ✅ **Plan-aware enforcement** — quota service reads the user's subscription plan before reserving.
- ✅ **Usage meter** — today's tokens vs. daily limit shown in Settings.
- ✅ **Real token accounting** — uses the provider's reported usage when available.
- ✅ **Pro tier** — higher daily limit when entitled; see [§12 Monetization](#12-monetization).

## 10. Settings & profile
- ✅ **Account** — shows email and plan; profile picture from Google (initials fallback).
  Profile (name, age, country, job, plan) is a row under that header.
- ✅ **Settings chrome** — identity header, then App / Data & privacy on the home list, plus the
  same icon wells and one-line subtitles on nested screens. Choice rows expand
  inline (no picker sheet). Same destinations.
- ✅ **Structured profile** — name, age, country, and job editable in Settings → Profile;
  plan (Free / Pro) is shown there. Persisted on `users` and injected into the chat
  system prompt (see [§6](#6-memory-remembering-the-user)).
- ✅ **Default model** — Flash / Pro.
- ✅ **Response style** — short / balanced / detailed (changes the assistant's verbosity).
- ✅ **Memory** — on/off toggle + link to manage saved memories.
- ✅ **Usage** — today's token meter.
- ✅ **Sign out.**
- ✅ **Data export** — exports profile + chats + messages + memories + todos + learning projects
  (with items) as JSON via the native share sheet (`GET /auth/me/export`). Shows a progress
  screen while the archive builds.
- ✅ **Account deletion** — permanently deletes the account and all its data (`DELETE /auth/me`),
  then signs out.
- ✅ **Language / i18n** — `react-i18next` with English, Spanish, French, Amharic, German, Italian, Portuguese, Russian, and Turkish.
- ✅ **Dark / light theme** — screens use `useTheme()` with system or manual appearance in
  Preferences. Some older hardcoded English strings remain (see i18n backlog).
- ✅ **Local todo reminders** — scheduled on-device notifications when a todo item is due (via
  `expo-notifications`; requires a dev build for full native support).
- ✅ **Remote push (MVP)** — Expo push tokens registered with the backend; learning-review,
  todo-due, email-suggestion, and **calendar meeting** notifications (requires dev build + EAS
  project ID).
- ✅ **Email reminders** — opt-in todo-due + learning nudge emails (Resend); Settings
  toggle; worker scheduler only (welcome + Pro receipt unchanged).

## 11. Navigation & UX
- ✅ **Drawer** — custom slide-in: search, New chat, chat history, profile + settings.
- ✅ **Chat screen** — composer with model picker, top-right `＋` (new) and `⋯` (Share / Rename /
  Pin / Delete).
- ✅ **States** — login, loading, empty chat ("How can I help?"), empty memory, drawer offline/retry.
- ✅ **Onboarding** — a first-run welcome screen (value props + "Get started"), shown once before
  the first sign-in.
- ✅ **Polish** — light haptic taps on key actions (Android via the built-in API) + chip fade-in
  animation.
- ✅ **iOS haptics** — `expo-haptics` on real devices (graceful no-op on Android / Expo Go).
- ✅ **Screen transitions** — shared stack presets: iOS-native push + back gestures on nested
  stacks, fade for auth/onboarding, fade-from-bottom for drawer utility screens (memory, todos).
- ✅ **Shared Button / type / space / motion tokens** — primary CTAs via `components/Button`;
  `lib/type.ts`, `lib/space.ts`, `lib/motion.ts` for high-traffic roles (incremental migration).
- ✅ **Full typography/spacing ownership on screens** — `app/*` screens and settings
  chrome use `Type` / `Space` for body, caption, label, title, and display roles.
  Compact chip/pill controls stay specialized (not the shared Button). Login
  wordmark and 11px stat chips keep their one-off sizes.

## 12. Monetization
- ✅ **Pro subscription (RevenueCat)** — mobile purchase flow via lazy-loaded `react-native-purchases`
  (dev/production builds only; skipped in Expo Go). Restore purchases supported.
- ✅ **Backend entitlement** — RevenueCat webhook (Redis `SET NX` claim before process; done-marker
  after success) + `POST /auth/me/sync-subscription`; `users.plan`
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
- ✅ **Ops** — `/health` liveness + `/health/ready` (Postgres; Redis reported as
  `ok`/`degraded` without draining the fleet), graceful shutdown, DB
  connection pooling.
- ✅ **Quality** — CI (Postgres + Redis services, ruff, mypy, pytest with coverage gate).
- ✅ **Background jobs** — title / memory / compression are enqueued to a **durable Redis Stream**
  and processed by an in-process worker (consumer group). Jobs survive process restarts, and an
  entry left unacked by a crash is reclaimed on the next startup (at-least-once).
- ✅ **Dedicated worker process** — Fly `app` (`PROCESS_ROLE=api`) + `worker` (`python -m
  app.worker_main`); local/dev default `process_role=all` keeps a single process. Scale with
  `fly scale count app=1 worker=1`. Multi-instance worker fleets remain a later ops concern.
- ✅ **Sentry** — optional DSN init on API + mobile (no-op when unset).
- ✅ **Sentry / request logs** — `before_send` drops `WebSocketDisconnect` /
  `ClientDisconnect`, strips request bodies and auth headers, tags `request_id`.
  One structured access line per HTTP request (`event=http_request`; JSON in
  production). Health probes and CORS preflight are skipped. No bodies or query
  strings.

## 14. Schedule & suggestions
- ❌ **Lists** — removed. No shopping/packing checklists in the drawer or chat. Do not
  reintroduce a Lists row, list composer, or undated checklist UI. (Learning chapter
  `lists` are vocab word groups, not this feature.)
- ✅ **Schedule** — dated items (formerly Reminders) with optional repeat
  (`daily` / `weekdays` / `weekly` / `monthly`). Repeats fire a **device push**
  only (notification bar), not email. Chat can set `repeat` on the ` ```reminder `
  fence. Route `focus=reminders` still works; `focus=schedule` is an alias.
  `/todos?focus=list` redirects to Schedule.
- ✅ **Todos API** — create, check off, delete dated reminders; optional `due_at`.
  Chat extract skips undated adds.
- ✅ **LLM todo sync** — background job extracts add / complete / uncheck / delete /
  set_due from chat (dated items only); injects Schedule + overdue summary into the
  system prompt. “What time is my flight / meeting / …” loads Schedule (and Calendar) on
  the first turn.
- ✅ **Due dates** — `due_at` on items; mobile date/time picker on Reminders; relative
  labels in prompts (overdue, due today, due in N days); user timezone synced from
  device (`users.timezone`).
- ✅ **Local due reminders** — schedules a device notification at due time; resyncs on
  login, foreground, and todo changes; tap opens **Schedule** (`/todos?focus=reminders`).
  Lead time configurable (5 / 10 / 15 / 30 / **60 min** before due). A server todo-due
  push cancels the matching local scheduled alert so both do not fire.
- ✅ **Proactive suggestions** — follow-up prompt ideas generated in the background from recent
  activity (best-effort; regenerated periodically); inline chips under the latest assistant reply.
- 🔜 1-hour-early **email/push** nudges beyond the local lead picker (calendar-aware).
- 🔜 **Flight-aware reminders** — parse confirmation mail (airline, flight number, departure)
  into a suggested reminder (confirm before add, same as other Gmail suggestions). Later:
  live status (delayed / cancelled / gate) from a flight API when the user asks. Not v1.

## 15. Code execution policy
- ⚠️ **Sandboxed HTML/CSS/JS preview only** — `html` fences can be previewed/run in an isolated
  WebView (no app token is exposed to it), and charts render via a sandboxed Vega WebView.
- 🔒 **No other code execution** — all other code (Python, shell, etc.) is rendered/highlighted
  only, and nothing runs outside the sandboxed preview WebView. (By design.)

## 16. MCP & calendar

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
- ✅ **`services/calendar.py`** — fetch events for a window (**local midnight** → +60
  days, not `timeMin=now`); prompt inject uses 14 days; Redis cache (~5 min) so every
  chat turn doesn't hit Google. Morning meetings stay on the Reminders day view after
  they end.
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
- ✅ **`user_gmail_connections` table** — scopes, `last_sync_at`, connected email (7-day
  inbox query; not a Gmail History API cursor).
- ✅ **`services/email.py`** — fetch recent mail, dedupe by message id, LLM extraction with Pydantic
  validation before DB writes.
- ✅ **Suggested reminders API** — list / dismiss / confirm → create an in-app **dated**
  reminder (`due_at` required; undated extracts default to 18:00 local or now + 1 hour).
- ✅ **Suggested reminders UI** — Reminders screen "From email" section + chat nudge chip;
  confirm before add (no silent auto-add).
- ✅ **Background sync** — periodic Gmail sync job enqueued after connect.
- ✅ **ICS invite parsing** — folded lines, `TZID` / all-day `VALUE=DATE`, location/description
  notes, cancelled events skipped (LLM fallback when no `.ics`).
- ✅ **Sender templates + chat nudges** — known senders (Amazon / UPS / FedEx /
  USPS / DHL / OpenTable / Resy / Tock / Calendly) extract without the LLM when
  the subject looks like a delivery, reservation, or appointment. Suggestions
  store `source_sender`. Pending items inject into regular chat turns (not only
  inbox questions) and the composer chip refreshes on focus. Confirming from the
  chip syncs local due notifications. Flights stay a later item.
- 🔜 **Flight confirmations** — extract airline + flight number + departure into the
  suggested reminder (not a free-text “flight” title only). Live delay/cancel status is
  a later flight-API step, not inbox guessing.

**Privacy & UX** (unchanged intent)
- Clear copy: what is read, how long it is kept. Disconnecting Calendar or Gmail
  **revokes the Google grant** (they often share one refresh token) and **disconnects
  the sibling product**. Reconnect the remaining product to grant only its scopes.
- Minimal retention; user confirms every suggestion in v1

**Out of scope for v1** (unchanged)
- Reading mail from a **different** Google account than the one connected
- Google Tasks / Keep reminders
- Sending email or replying from Recall
- Full inbox UI in the app

### Phase 2 — MCP layer
- ✅ **MCP gateway skeleton** — `gateways/mcp/` with registry + adapters (`web_search`, `calendar`).
- ⚠️ **Pre-stream tool round** — when `MCP_TOOLS_ENABLED=true`, `chat_tools.py` invokes matching
  adapters once before streaming (legacy; skipped when the tool loop is on).
- ✅ **Full tool-calling loop** — **on by default**, but **not on every turn.**
  Ordinary chat streams immediately. Pre-stream `complete_with_tools` runs only
  when the turn still looks like web search (and heuristic search did not already
  fill sources), unsolved math, calendar create, or Pro image gen. If that round
  finishes without tools, the text is shown — the stream does not call the model
  a second time. Adapters: `web_search` / `sympy` / `calendar` / `image_gen`,
  Pydantic-validated args, bounded by `mcp_tool_loop_max_rounds`. The **calendar**
  adapter **conflict-checks Google Calendar** (`fetch_upcoming_events`, same as
  Reminders/chat) and may merge caller-supplied stubs (proposed times). It does
  **not** create Google events — create stays the `calendar_proposal` fence +
  confirm card. Heuristic SymPy + web-search inject still run so homework and
  first-turn search do not wait on a tool call. Legacy `mcp_tools_enabled` stays off.
- ✅ **Golden rules preserved** — product aliases in services; structured outputs validated with
  Pydantic before DB writes (already enforced for calendar proposals and email extraction).

### Phase 3 — Smarter behavior
- ✅ **Conflict detection** — server helper + row notes on existing reminders after events
  load. Add/edit sheets do not call `/conflicts`.
- ✅ **Create calendar events (confirm flow)** — user asks to schedule → model emits
  `calendar_proposal` fence → backend stores Redis proposal + injects `proposal_id` → mobile
  **Add to Calendar** card → confirm creates the Google event (requires calendar **write** scope).
- ✅ **Proactive calendar nudges** — push scheduler warns before connected Google Calendar
  events (default **15 min** lead; Redis dedupe per event). Tap opens Reminders calendar view.

### Privacy & UX
- Opt-in connect; disconnecting deletes Recall’s connection row and stops injection.
  If Calendar and Gmail share a refresh token, disconnect **revokes at Google** and
  **drops the sibling product** so it must reconnect with only its scopes.
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
8. Full LiteLLM tool-calling loop ✅ (on by default)
9. Email auto-add for high-confidence types (optional, post-MVP) 🔜

---

## 17. Projects (utility workspaces)

Recall is evolving from chat-only into a **holistic AI utility app**. **Learning** is
**English and Spanish vocabulary only** (one class per target language). Other UI locales
stay in the app; they are not Learning class types. Trivia / general-knowledge quizzes
were removed. Programming help lives in main chat.

### v1 (shipped foundation)
- ✅ **`projects` table** — title, description, `kind` (`language` only; `vocabulary` is a
  write alias), archive flag. DB CHECK rejects `general` / `trivia` / `learning` /
  `programming`.
- ✅ **REST API** — `GET/POST /projects`, `GET/PATCH/DELETE /projects/{id}`.
- ✅ **Mobile** — drawer **Learning** → list → create → **lesson map** (detail redirects
  there). Compact stats, PDF export, and delete live in Settings/Learning.
- ✅ **Project kinds** — create only offers `en` / `es`. Legacy kinds (`trivia`,
  `programming`, `math`, …) are rejected on create.

### Phase 2 — Vocabulary (language learning)
- ✅ **Decks / groups** — catalog chapters (domain → branch), not a user-editable deck UI.
- ✅ **Vocab items** — term, definition, example, IPA, part of speech, simple gloss,
  status (new / learning / mastered), SM-2 fields.
- ✅ **Mark as known** — progress per item; compact stats summary (learned / this week / streak)
  lives in Settings/Learning, not the main lesson flow.
- ✅ **AI tutor + quiz** — chat still sees Learning progress and can open a lesson via
  `learning_launch` / home suggestions. Study runs in the lesson window: **teach first**
  (word, IPA, POS, meaning, example), then the existing A–D **lesson choice cards**
  (gapped sentence, then meaning in that sentence). Continue is enabled after a correct
  tap; that last check marks the word `mastered` (already-mastered review pages without a
  PATCH). No per-word illustration. The next group stays locked until every word in the
  current chapter is mastered. Chat must not render A–D quiz chips, `vocab_card` study
  cards, or grade letter answers. Regular chat must not quiz in-bubble. Chat tutor prompts
  must not invent words.
- ✅ **Lesson A–D check after teaching** — restored `LessonQuizCards` (the old tappable
  A/B/C/D cards). Typed-answer lessons and chat MCQ chips are not the study path.
- ❌ **Chat A–D quiz UI / `vocab_quiz` as the lesson product** — removed. Hidden
  project-scoped chats no longer emit `vocab_quiz` / `vocab_card` for study. The lesson
  window reuses the old choice-card UI; it is not a new in-card “What does this mean?”
  quiz and it does not quiz before teaching.
- ❌ **SM-2 review UI / Settings deck browse** — **not shipped.** SM-2 fields
  (`ease_factor`, `interval_days`, `due_at`) are written on status changes.
  There is no due-queue of old mastered words across groups. Reopening a
  **completed** group on the map is a same-group review pass, not SM-2.
  Settings has PDF export, not a deck browser. `buildProjectReviewPrompt` is unused.
- ❌ **Class CEFR level** — unused. Vocab is the full catalog for everyone;
  Settings has daily goal + PDF + delete only. Chat extract `set_level` is a no-op.
- ✅ **Streak + inactive days** — home highlight and project hero show streak; push/email
  nudges show “inactive for N days” copy (streak count is not included in notification text).
- ✅ **Goal-aware learning nudges** — push/email prioritize finishing today's daily batch.
- ✅ **Pronunciation** — play button per word tries `pronunciation_url` when set, then cloud TTS,
  then on-device `expo-speech`.
- ✅ **Spaced repetition scheduling** — SM-2 fields (`ease_factor`, `interval_days`, `due_at`)
  update on vocab status changes. Due counts for the map are in-progress items, not a
  mastered-word review queue.
- ✅ **Ordered learning path** — language projects store `learning_path` chapter titles
  (decks). Create enqueues a `language_path` job that copies a curated catalog
  (`vocab_decks` / `vocab_entries`: domain → branch tree). English classes use
  conversation-grouped chapters (Greetings, Numbers and time, Feelings, …,
  Casual expressions last). Spanish
  keeps the Greetings / Family / Food / … tree. Older English Hotel/SAT rows stay
  in the catalog tables for existing `catalog_entry_id` links but are **not** on
  the English lesson map. **Every class sees its full path.** Create is a
  full-screen flow: **language**, then **daily goal** (5/10/15). Create opens the
  **lesson map** (not a tutor chat that invents words). Main chat gets a progress overview (class, daily
  counts, path checkmarks) and today’s lemmas when asked — not the full word dump.
  A project-linked tutor / quiz turn sees only the current `up_next` chapter’s
  ○ / ◐ words. The model must not invent or add words. Progress is derived
  (mastered/total; a chapter is complete when every word is mastered). English
  groups are one map row per theme (~16+ words). The lesson map is a vertical
  list (status icon, title, counts) — not letter-in-a-circle nodes. Tap an
  unlocked group to open the word page; a completed group opens as review.
  Opening a group starts a **daily sitting** (5/10/15 words — the class daily
  goal), not the full chapter. Map counts (15/43) are chapter progress; the
  word page shows “Today 1 of 10”.
  The main flow is
  Sidebar → My Learning list → Lesson map → Lesson page (no intermediate stats
  screen). Compact stats, PDF export, and delete live in Settings/Learning. A
  thin "today" progress line sits above the path tree. Locked chapters stay
  visible until the current one is complete. No generic `learning` kind, lesson
  notes, certificates, or marketplace.

### Phase 3 — Cross-linking
- ✅ **`project_id` on chats** — conversations started from a project carry `project_id`; prompt
  injection scopes to that one project (+ tutor hints) instead of all projects.
- ❌ **Link todos to Learning** — optional `project_id` may exist on todo rows in the API.
  Mobile must not show it (no “Linked to …”, no filter chips, no folder control). Schedule
  and Learning stay separate.
- ✅ **Home starters** — active project highlight on home; tap opens project or starts scoped chat.

### Phase 4 — More project types
- ❌ **General knowledge (trivia)** — removed. Learning is language vocabulary only.
- 🔜 **Learning (generic)** — lesson notes, spaced repetition beyond vocab, richer AI tutor mode.

Chat + memory + todos + projects share one backend; the LLM orchestrates across them (no keys on
device).

---

## Deferred to upcoming version(s)
A consolidated list of what's intentionally **not** (or only partially) in this version.

### Already shipped (keep for audit trail)
- ✅ **Full MCP / multi-turn tool loop** — LiteLLM `tools=` rounds; `MCP_TOOL_LOOP_ENABLED`
  defaults **on**. Heuristic math/search still run. See [§16](#16-mcp--calendar).
- ✅ **Attachment RAG** — pgvector chunk + embed over uploaded PDF/docs **in that chat**
  (`chat_id`); top-k into later turns. **Not** a per-user file library across chats.
  Text-layer extract on prepare; vision OCR on the index job only.
- ✅ **Camera math solver** — attach sheet “Solve math with camera” → vision → SymPy → LaTeX/steps.
- ✅ **Web search** — Tavily primary + DuckDuckGo fallback; sources on assistant messages
  (hidden on vocab quiz cards).
- ✅ **Structured profile fields** — name / age / country / job (Settings + prompt injection).
- ✅ **Vision + Pro image gen** — image attachments route to vision models; Pro image generation
  from the composer on send (daily cap; no separate prompt sheet).
- ✅ **Per-chat Redis prepare lock** — `chatprep:{chat_id}` around prepare + stream; concurrent
  turns get `ChatBusyError` / `code: "busy"` (#536).
- ✅ **Math WebView expand / fullscreen** — tall KaTeX/MathJax blocks offer Expand → full-screen
  modal (`MathFormulaWebView`; #537).
- ✅ **Algebra `canonical_fence` / ` ```answer ` rewrite** — SymPy attaches canonical answer
  fences; post-stream `validate_math_fences` rewrites drifted finals (#538).
- ✅ **Persist assistant reply on hard WS/SSE disconnect** — mid-stream `CancelledError` with
  tokens finalizes like soft stop (#539).
- ✅ **RevenueCat webhook atomic claim** — Redis `SET NX` claim before processing; done-marker
  after success (#535).

### Later / future (not the current coding backlog)
- ✅ **Push-token re-bind hardening** — cross-user Expo token moves require a matching
  install `device_id` (stable id persisted on device; Expo removed `installationId`).
  Mismatched device → 403; successful rebinds log + Sentry breadcrumb. Residual risk:
  attacker with both the Expo token and the install id can still rebind; full device
  attestation remains deferred.
- ✅ **Message id time-ordering (uuid7)** — new `messages.id` values use UUID v7
  (`app.core.ids.uuid7`) so `(created_at, id)` cursors stay time-stable; existing
  uuid4 rows are unchanged.
- 🔜 **Full locale translation** — key-set parity is enforced (**960** keys); ~350 strings still
  English in non-en locales (Claude review wave 3 strings are keyed; prose translation deferred).
- ✅ **Full chat-history semantic RAG** — `message_chunks` + `message_index` job + top-k
  at turn start (excludes the recent window). Same shape as attachment RAG.
- ✅ **Scanned-PDF OCR** — text-layer `pypdf` on **prepare** (no vision). Empty PDFs
  render pages (`pypdfium2`) and transcribe via `vision-chat` on the **index job**,
  then the same excerpt + attachment RAG path. Cap + timeout in `attachment_ocr_*`.
  Not a second extract pipeline.
- ✅ **Owned tool loop enabled** — `mcp_tool_loop_enabled` defaults true. Heuristic
  SymPy + web search kept. See [§29](#29-next-actions-product-decisions).
- 🔜 **Plugins / arbitrary user MCP servers** — owned server-side tools only today.
  Google Docs + GitHub (and similar) are later owned integrations, not user-hosted MCP.
- 🔜 **Code execution** beyond sandboxed HTML/chart preview — later, not now. Keep the
  sandboxed WebView exception until then.
- 🔜 **Collaborative cursors / shared docs** — real-time co-editing; personal app only today.
- 🔜 **Web client** — slice 1 shipped (login + chat stream); see [Web client](#web-client-planned) below.
- 🔜 **RenderDocument v2** — versioned ordered block schema, same document live and on
  history reload. Not started; P0 kept `message.content` plus a trailing sources fence.
- ⚠️ **Web output parity** — GFM tables, named source links, and human fallbacks for
  JSON rich fences are in slice 1. KaTeX, Mermaid, Vega, and sandboxed HTML remain later.
- 🔜 **Claim-level citations** and attachment filename / page / chunk identity in the
  answer contract (today: one source list, RAG chunks without user-facing file metadata).
- 🔜 **Six visual families** — restyle existing rich cards onto one document / artifact /
  result / visual / evidence / action shell.
- ✅ **Hide raw reasoning** from the assistant answer — status/waiting while the model
  works; CoT is not copied onto the bubble or kept as `reasoning_preview`. Do not
  reintroduce recalled-memory chips.
- ✅ **One molecule card** — adjacent `smiles`/`chemistry` + `molecule3d` collapse
  in the client to one card (2D default, optional 3D). Persist still stores both
  fences. Standalone `molecule3d` stays 3D-only. Web slice 1 skips the second
  “Chemical structure” label for that pair.
- 🔜 Folders, editing arbitrary older messages, user-tunable routing rules, family plans,
  response caching, full duplex / interruptible voice (later).
- 🔜 **Production R2 + store polish** — attachment *code* is done; prod R2 secrets and App Store /
  Play billing polish are **future owner ops**, not a product coding task.
- ✅ **Mobile UI systems (audit 2026-08)** — P0 contrast tokens, switch/chip labels, 44pt
  `IconButton` on named undersized controls, PDF/math pinch-zoom, AppSheet
  dialog/focus/pan, AuthScrollLayout, gallery filter wrap, drawer width cap,
  SheetFormHeader, Space/Radius/Type (deleted `layout.ts`), StrokeIcon→Icon,
  Reduce Motion helpers, in-tree ActionBanner overlay host, recoverable
  `Alert.alert` sweep, and unused UI file cleanup. Do not restyle or
  reintroduce banned UX.

**Not implemented (future — do not start now).** Remaining 🔜 / partial items in this file:

| Area | Still not built |
|------|-----------------|
| Auth | Email/password, magic links, multi-device session management |
| Chats | Folders; public unauthenticated share URLs; edit arbitrary older messages |
| Messaging | Reactions, read receipts; full duplex / interruptible voice; music generation (composer send + compact inline player) |
| Models | User-tunable routing rules; response-cache; NL daily-goal setting |
| Todos | 1-hour-early email/push nudges; flight-aware reminders (email parse + live status) |
| Learning | Generic `learning` kind; other target languages; certificates; **SM-2 review-queue UI**; Settings deck browse; typed-answer lesson path |
| Attachments | **User-wide attachment RAG** (chunks are per `chat_id`; later turns in that chat only) |
| Todos↔Learning | API may still have `project_id` on todos; mobile link/filter/“Linked to” UI is **removed** (banned) |
| Integrations | Google Docs, GitHub; user MCP servers; Gmail OAuth verification (prod) |
| Platform | Web client; code execution beyond HTML sandbox; virus scan |
| i18n | ~350 locale strings still English; legal privacy/terms bodies English-only |
| Polish | App Store / Play / family plans |
| Launch ops | Neon / Redis / R2 / Fly / EAS; landing page; on-device QA; prod R2 secrets |

### Future — owner ops (was “Pre-deployment TODO”)

Infra + store steps live in Lists → **Launch** (local Dev User) and
[`docs/PRODUCTION.md` § Owner actions](./docs/PRODUCTION.md#owner-actions-you--not-code).
**Future — not the current backlog.** Code cannot finish these.

- ⚠️ **R2 storage credentials** — the `R2StorageGateway` is wired and tested, but attachments
  run on local fallback until `STORAGE_BACKEND=r2` + `R2_ACCOUNT_ID` / `R2_ACCESS_KEY_ID` /
  `R2_SECRET_ACCESS_KEY` / `R2_BUCKET` secrets are set. (Code done; creds pending.)
- ⚠️ **Production env secrets** — `validate_production_settings` enforces
  `OAUTH_TOKEN_ENCRYPTION_KEY`, `OPENROUTER_API_KEY`, `CORS_ORIGINS`,
  `REVENUECAT_WEBHOOK_AUTH` (plus DB/Redis/Google/JWT/dev-flags). `ENVIRONMENT` now
  **defaults to `production` (fail-closed)** — local `.env` / `.env.example` must set
  `ENVIRONMENT=development`.
- 🔜 **Mobile gate + on-device pass** — **future.** `pnpm typecheck && pnpm lint && pnpm test`
  locally, then an iOS **and** Android dev-build pass (Google Sign-In, HTML/chart WebView,
  push, RevenueCat, deck Modal, autoscroll, markdown throttle).
- 🔜 **Frontend launch-readiness (audit, deferred)** — Pressable a11y coverage, `textTertiary`
  contrast, tablet readable-width, icon stroke unification, web KaTeX/Mermaid/Vega /
  httpOnly cookies / stream virtualization, QA matrix assistive-tech pass. Not the current
  backlog.
- ✅ **FlashList migration** — `ConversationList` and Schedule now use `FlashList`
  (v2, auto-measured). Chat drawer rows are virtualized; the calendar day-view
  renders in the header (bounded/structured, not row-virtualized). Verify
  scroll/layout on-device.
- ✅ **i18n extraction (reminders / share / urgent)** — keys wired in `todoReminders`,
  `homeUrgentTodos`, `share.ts`, and push channel names; translated in all 9 locales.
- 🔜 **Locale prose translations** — **future.** Key-set parity is enforced (**960** keys);
  ~350 non-en values are still English. Structural i18n is complete.
- 🔜 **Legal page bodies** — **future.** `/legal/privacy` and `/legal/terms` remain English-only
  markdown on the API (nav titles are localized).
- ✅ **DB session scope in `_prepare_chat_turn`** — attachment S3 reads and web-search
  augmentation run outside the DB session; calendar/Gmail still use a short session.
- ✅ **Background-job DLQ** — failed jobs (including unknown type / bad JSON) go to
  `recall:jobs:dlq` before ACK. Stream trim uses pending MINID so approximate maxlen
  cannot drop unacked entries.
- ✅ **JWT refresh / logout** — 1h access + refresh rotation; mobile auto-refresh on 401.
- ✅ **HTTP SSE chat fallback** — `POST /chats/{id}/messages/stream` when WebSocket fails.

### Architecture review follow-ups (Jul 2026)

Shipped after the Phase 1/2 code review (and follow-up PRs):

- ✅ Fail-closed `ENVIRONMENT` default (`production`); tests set `development` via conftest
- ✅ Job DLQ for unknown type / bad payload; pending-aware stream trim
- ✅ Remove dead `quota.can_spend`; bulk-delete suggested reminders; parallel attachment byte deletes
- ✅ `attachment_index` enqueued on the post-turn jobs path (not mid `prepare_chat_turn`)
- ✅ Token-based Redis locks for push / email / Gmail / orphan-reaper schedulers
- ✅ WS handshake IP rate limit before `accept()`; core `user_id` FKs `ON DELETE CASCADE`
- ✅ Alembic `transaction_per_migration` so future `CREATE INDEX CONCURRENTLY` can use
  `op.get_context().autocommit_block()`
- ✅ Enum-like CHECK constraints (`0053`) for memories, projects, users plan/tone, quiz mode, item status
- ✅ Mobile: in-chat delete syncs drawer + cache; mount chat-load `catch`; memoized contexts;
  removed unused `showContextSummarized`; bootstrap listener cleanup race; draft discard on
  background; a11y labels on key icon-only controls
- ✅ **Real-SQL repository tests** — `test_*_db.py` for chats / messages / memories / usage
- ✅ **RTL test infra** — `@testing-library/react-native` + WebView sandbox / mount-queue tests
  (expand coverage over time; foundation is in)
- ✅ **Deferred WebView mount queue** — `useDeferredWebViewMount` caps concurrent chart/math/Mermaid
  WebViews so multi-block messages stay smooth
- ✅ **Hung-worker heartbeat** — `is_worker_alive` tracks loop heartbeat, not only `task.done()`
- ✅ **Claude review waves (#533–#539)** — product/reliability fixes + deferred items: chatprep
  lock, math expand, algebra answer fences, hard-disconnect persist, RevenueCat SET NX
  (see [Already shipped](#already-shipped-keep-for-audit-trail))

Still open (non-blocking / larger effort):

- ✅ **Multi-file HTML preview** — same-reply ` ```html ` + ` ```css ` +
  ` ```javascript ` fences are inlined for the sandboxed Run preview (relative
  names only; leftover CSS/JS appended). Single self-contained ` ```html ` still
  works. No folders, no extra execution surface.
- 🔜 Broader RTL coverage beyond the initial WebView / mount-queue suite
- 🔜 Locale prose + legal page bodies (future; see owner-ops list above)

### Review audit follow-ups (PR #129, Jul 2026)

Shipped in the audit PR or follow-up commits: push ticket-vs-receipt semantics, 600s scheduler
lock, attachment byte verification on GET, graph `points: []` rejection, live model badge via
`stream_end` + `resolved_model`, day-planning quiz stats, instant project day-item cache.

Still open (non-blocking):

- ⚠️ **Android chat keyboard** — `softwareKeyboardLayoutMode: resize` is set for Reanimated's
  `useAnimatedKeyboard`; needs an **Android dev-client rebuild** and on-device composer smoke test
  (iOS confirmed smooth; Android unverified).
- ✅ **Memory consolidation (merge-not-replace)** — per-section LLM merge via
  `merge_memory_section`, with a deterministic exact-sentence dedupe pre-pass. Safety gates
  still skip merges that shrink below 50% (LLM path) or drop **≥20% of salient anchors**.

### Multimodal & attachments

Shared **attachments substrate** (presigned upload, `attachments` table, local or R2 storage,
magic-byte validation, daily caps). Blobs never live in Postgres.

| Capability | Status |
|------------|--------|
| Presigned upload + confirm + orphan reaper | ✅ Shipped (local default; R2 when `STORAGE_BACKEND=r2` + secrets) |
| Image upload → vision-chat routing (Gemini via OpenRouter) | ✅ Shipped |
| Pro image generation (composer send, daily cap) | ✅ Shipped |
| Library (drawer grid of generated + uploaded images and files) | ✅ Shipped |
| PDF / doc upload + server text extract into prompt | ✅ Text-layer PDFs / DOCX + scanned-PDF OCR (page render → vision) |
| PDF inline preview (pdf.js WebView, dev build) | ✅ Shipped |
| Audio in (Whisper STT → composer) | ✅ Shipped (dev build) |
| Live talk (speech-to-speech, Pro + daily cap) | ✅ Shipped (GPT Audio; not Whisper; not full duplex) |
| Audio out (read aloud) | ✅ Cloud TTS + device `expo-speech` fallback (dev build) |
| Music generation (composer send + compact inline player) | 🔜 Later (Pro + daily cap; not TTS) |
| pgvector RAG over **this chat’s** attachments | ✅ Shipped (`attachment_rag`; flag on by default; not a user-wide corpus) |
| Camera math solver UX | ✅ Shipped (attach sheet → vision → SymPy) |
| Full chat-history corpus RAG | ✅ Shipped (`message_chunks`; flag on by default) |
| Full duplex voice mode | 🔜 Later |

Notes: multimodal routes through whichever catalog model supports the modality (vision/image-gen
aliases on OpenRouter). Multimodal calls cost more than text — gated by plan + daily caps
(images, speech).

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
- ✅ **Approach decided** — separate Vite + React + TypeScript app at `apps/web` (not
  react-native-web of `apps/mobile`). Expo's FlashList/Reanimated/SecureStore/`expo-audio`/
  `react-native-webview` don't port to a browser without a multi-month effort.
- ✅ **Slice 1 shipped** — login (Google Identity Services + dev), chat list (create/open),
  chat view with SSE streaming (`start`/`token`/`status`/`stream_end`/`done`/`error`),
  stop (abort), regenerate, GFM markdown (including tables and images). Source links
  render under the reply; JSON rich fences (graph/chart/places/…) degrade to a short
  label instead of a code dump. Adjacent SMILES + molecule3d share one
  “Chemical structure” label (no 2D/3D viewer yet). No KaTeX/Mermaid/Vega/HTML iframe yet. Tokens in
  `sessionStorage` (tab-scoped); 401 → refresh → retry.
  CORS origin documented in `apps/api/.env.example`. Follows the mobile chat-ux-bans.
- 🔜 **Later slices** — rich fences (math/charts/Mermaid/sandboxed HTML preview), Memory/
  Learning/settings/attachments/image gen, `packages/api-types` extracted from
  `lib/api/types.ts`, httpOnly refresh cookie + CSRF, Apple Sign-In on web, prod deploy.

---

## 28. Product catalog (PM reference)

Internal product snapshot for leadership, engineering, design, GTM, and App Store review.
**Status:** pre–public launch on `main`. Supersedes one-off chat summaries when they disagree.

### Mission
Recall is a **personal AI utility** — not a generic chatbot. It remembers who you are, helps you
act (reminders, calendar, email), and supports **Learning** (English and Spanish
vocabulary). One trusted assistant combining ChatGPT-grade conversation with durable memory and
everyday productivity. **Programming help lives in main chat** (code blocks, previews) — not as a
structured Learning topic type.

### Strategic pillars
| Pillar | Meaning |
|--------|---------|
| Chat that feels fast | Streaming, stop/regenerate, rich answers, status while working |
| Memory that compounds | User facts + past-chat RAG — the namesake |
| Utility beyond chat | Schedule, Learning, integrations, home starters |
| Trust & control | Export, delete account, opt-in integrations, quota transparency |
| Monetize fairly | Free tier with limits; Pro for power users |

### Release plan
| Phase | Scope | Status |
|-------|--------|--------|
| MVP (mobile) | Chat + memory + Schedule + Learning + calendar/Gmail + attachments | ~95% code-complete |
| Launch readiness | Provisioning, store builds, landing page, OAuth verification, on-device QA, R2 secrets | 🔜 Future (owner ops) |
| v1.1 | Web client (same API), locale prose, legal localization | 🔜 Future |
| Next (product) | — | Done (tool loop, scanned-PDF OCR, chat-history RAG) |
| Later | Google Docs, GitHub, code execution, duplex voice, web client, folders / family plans | 🔜 Future |

Notes already on `main` (not waiting on v2): Fly api/worker split ✅, attachment RAG ✅,
chat-history RAG ✅, LiteLLM tool loop **on by default** (ordinary chat skips the pre-stream round) ✅, structured profile ✅,
drawer FTS search ✅.

### Learning (not “programming projects”)
| Shipped | Not done |
|---------|----------|
| Language (`language`) — en/es catalog tree, teach-then-A/D lesson cards, SM-2 fields | Other target languages; trivia |
| Domain → branch lesson map; create opens the map | Review queue, Settings deck browse, typed answers |
| Project-scoped chats, home highlight (Learning only) | In-app code runner (later) |
| ~~Programming curriculum kind~~ **removed** — use main chat for code help | ~~Hidden chat `vocab_quiz` as the lesson path~~ **removed** |

### Rich rendering (§4 summary)
| Capability | Status |
|------------|--------|
| Markdown, tables, math, geometry/graph SVG, charts, HTML sandbox | ✅ Shipped |
| Prism.js syntax highlighting | ✅ Shipped |
| Mermaid inline (WebView, dev build) | ✅ Shipped |
| PDF preview in chat | ✅ Shipped (tap card → viewer modal) |
| Collaborative cursors / shared docs | 🔜 Deferred (personal app; no multi-user) |

### Attachments & multimodal
| Shipped | Not done |
|---------|----------|
| Presigned upload, magic-byte validation, daily image cap | Production R2 secrets (future owner ops) |
| Vision routing for images + scanned-PDF OCR (**index job**, not prepare) | — |
| PDF text extract + pgvector RAG **per conversation** | User-wide attachment corpus |
| Chat-history corpus RAG (pgvector top-k, not full transcript) | — |
| Camera math solver (vision extract → SymPy → LaTeX) | Virus scan / enterprise DLP |
| PDF inline preview in message bubble | — |

### Voice
| Shipped | Not done |
|---------|----------|
| Record → Whisper → composer (dev build), waveform UI, rate limits | Full duplex / interruptible voice (later) |
| Live talk speech-to-speech (Pro, 30 turns/day) | — |
| Device TTS + streaming cloud TTS (`POST /speech/tts/stream`, daily caps) | — |

### Cost guards (recent)
| Guard | Free | Pro |
|-------|------|-----|
| Daily tokens | 100k | 500k |
| Speech transcriptions/day | 30 | 200 |
| Speech TTS (read aloud)/day | 20 | 100 |
| Live talk turns/day | 0 (Pro only) | 30 |
| Tavily searches/day | 20 (then DDG only) | 150 |
| R1 / smart-chat quota weight | 3.5× token charge | Same |

### Integrations
| Shipped | Not done |
|---------|----------|
| Google Calendar read + write (confirm flow) | Google OAuth verification for Gmail (future) |
| Gmail → suggested **dated** reminders (`last_sync_at`, 7-day query) | Gmail History API cursor; Google Docs, GitHub |
| MCP adapters + LiteLLM tool loop **on by default** (not every turn); calendar MCP conflicts vs Google | Calendar MCP creating Google events; user MCP servers |

### Future — launch ops (owner, not product code)
1. Cost guards (speech, Tavily, R1 weight) ✅
2. 🔜 Provision Neon, Redis, R2, Fly, EAS
3. 🔜 Landing page + support URL
4. 🔜 Google OAuth verification (Gmail)
5. 🔜 On-device QA matrix (iOS + Android)
6. 🔜 R2 production attachments

### Explicitly not v1
Multi-user teams, collaborative editing, video generation, public unauthenticated share URLs,
arbitrary user MCP servers, gamification (XP/badges beyond learning
streaks). **OpenRouter / product aliases are the intended model setup** — not a gap.

**Next (product):** none — tool loop, scanned-PDF OCR, and chat-history RAG are done.

**Future (not implementing now):** launch ops (provision, landing page, Gmail OAuth, on-device
QA, prod R2); Google Docs + GitHub; code execution (beyond the HTML sandbox); duplex voice;
web client; locale prose + legal bodies; folders / family plans; **user-wide attachment RAG**;
**SM-2 review-queue UI / Settings deck browse / typed-answer lessons**.

---

## 29. Next actions (product decisions)

Compiled from the ChatGPT-gap review. One concern per PR. Do not treat OpenRouter as a
weakness. No video generation. Native share is enough unless we later decide we want
**public unauthenticated URLs** (we do not have those today).

### Done (this product pass)

1. ✅ **Owned tool loop on** — `mcp_tool_loop_enabled` defaults true. Adapters:
   `web_search`, `calendar`, `sympy` (if math on), `image_gen` (if image gen on).
   The calendar adapter conflict-checks **Google Calendar** (plus optional caller
   stubs); it does not create on Google. Heuristic SymPy + first-turn web search
   still run. Add Docs/GitHub later as owned tools — not user MCP servers.
2. ✅ **Scanned-PDF OCR** — text-layer extract on prepare (no vision); empty PDFs
   render pages → `vision-chat` on the **index job** → same excerpt + chunk/embed
   RAG. No second pipeline.
3. ✅ **Chat-history semantic RAG** — `message_index` after finalize; top-k at turn
   start excluding the recent window. Golden Rule 3: never dump the full transcript.

### Future (not implementing now)

- Launch ops: provision Neon / Redis / R2 / Fly / EAS; landing page + support URL;
  Google OAuth verification (Gmail); on-device QA (iOS + Android); production R2 secrets.
- Google Docs, GitHub (owned integrations).
- **User-wide attachment RAG** — chunks stay per `chat_id`; later turns in that chat only.
- **SM-2 review-queue UI / Settings deck browse / typed-answer lesson path.**
- Full duplex / interruptible live voice.
- Code execution beyond the sandboxed HTML/chart WebView.
- Web client (same API).
- Locale prose + legal page bodies.
- Public share URLs only if we explicitly want unauthenticated read links.
- Folders, family plans, response-cache / prompt-budget UI, user-tunable routing.

### Not doing

- Video generation.
- Custom GPTs / arbitrary user MCP servers as the way to “make tools strong.”
- Calling rented models a product gap.
