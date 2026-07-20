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
- ✅ **Share / Export** — share a conversation as a markdown transcript via the native share
  sheet; export an assistant reply as PDF (structured headings/lists/code); export a learning
  topic (vocab words or trivia facts) as PDF from the project screen.
  (chat `⋯` menu + drawer long-press); no backend needed.
- ✅ **Manage from the drawer** — long-press any chat for **Pin/Unpin · Share · Archive · Delete**.
- ⚠️ **Archive** — chats can be archived from the drawer (long-press); archived chats show in a
  separate section and are excluded from the main list. In-chat `⋯` archive is pending.
- ✅ **Multi-select** — drawer **Select** mode: tap rows to choose, then bulk **Archive** or
  **Delete** (with confirm).
- 🔜 Folders.
- ✅ **Swipe-to-delete** — swipe a chat row left in the drawer to reveal Delete (same confirm
  flow as the long-press menu).
- ✅ **Project-scoped chats** — chats created from a learning project carry `project_id` (see [§17](#17-projects-utility-workspaces)).

## 3. Messaging behaviour
- ✅ **Streaming** — token-by-token over WebSocket; the reply appears as it's generated.
- ✅ **Stop generation** — cancel mid-stream (send button becomes a stop button); the partial reply
  is kept.
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
- ✅ **Read aloud (TTS)** — speaker on assistant messages and vocab words prefers cloud
  `POST /speech/tts` when a **dev build** + token are available; falls back to on-device
  `expo-speech`. Unavailable in Expo Go (same native gate as voice input).
- 🔜 Reactions, read receipts; duplex full-voice mode (out of scope).

## 4. Formatting & rendering
- ✅ **Markdown** — headings, **bold**/*italic*, bullet & numbered lists, blockquotes, links,
  inline code, horizontal rules.
- ✅ **Code blocks** — dark card, language badge, copy button, horizontal scroll.
- ✅ **Syntax highlighting** — **Prism.js** token coloring for 40+ languages (comments, strings,
  numbers, keywords); heuristic fallback for unknown langs.
- ✅ **Tables** — styled (header shading, borders, cell padding).
- ✅ **Inline images** — Markdown `![alt](url)` images render (contained, rounded).
- ✅ **Image generation (Pro)** — Type an image request in the composer and send (e.g. "draw me a
  cat"); Pro users get daily-limited generations stored as chat attachments. No separate prompt
  sheet. Tap the result to view full-screen and save via the system share sheet.
- ✅ **Math / LaTeX** — inline `$...$` renders as native text (superscripts, √, fractions);
  display ` ```math` uses KaTeX (or MathJax for heavy expressions) in a WebView on a
  **dev build**, with native/`MathText` fallback in Expo Go. Server-side **SymPy**
  solves equations and samples graphs before the LLM explains (verified numbers /
  fences injected into the prompt; post-stream fence correction). See [docs/math.md](./docs/math.md).
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
- ✅ **Mermaid diagrams** — inline SVG render via sandboxed WebView (dev build); source toggle +
  copy + Mermaid Live link; Expo Go shows source + external editor hint.
- ✅ **PDF attachments** — uploaded PDFs show a file card + inline first-page preview (pdf.js in
  sandboxed WebView, dev build); tap opens full viewer with share/export.
- 🔜 **Collaborative cursors / shared docs** — multi-user editing not in scope for v1 personal app.

## 5. Models & routing
- ✅ **Multiple tiers** — **Flash** (`free-chat`) and **Pro** (`smart-chat`), plus **Max**
  (`max-chat`, OpenRouter) which appears once an OpenRouter key is configured.
- ✅ **Manual switching** — model picker in the composer + a default in Settings (respected).
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
- ✅ **Automatic extraction** — durable facts are extracted in the background on **turn 1 and
  every 3rd turn** (`memory_extract_every_n_turns`), not every turn.
- ✅ **Typed memories** — `profile` · `preference` · `project` · `fact` · `focus` (captures things
  like interests, what they're working on, name, job, country when mentioned).
- ✅ **Quality controls** — confidence threshold, de-duplication, priority ordering, capped count.
- ✅ **Prompt injection** — relevant memories are added to the system prompt.
- ✅ **Semantic recall** — when `semantic_memory_enabled` (default on), the user's latest message
  is embedded and the top matching memories are selected (cosine similarity on stored embeddings;
  falls back to priority ordering when embeddings are missing).
- ✅ **Memory screen** — view memories grouped by type, with confidence, and **delete** them.
  Storage is one consolidated row per type (`profile` / `preference` / …); deleting a single
  fact rewrites that section rather than removing a separate row per bullet.
- ✅ **Memory toggle** — turn learning on/off in Settings.
- ✅ **Structured profile fields** — name, age, country, and job are discrete account fields
  (editable in Settings → Profile) and injected into the chat system profile block.
- ✅ **Attachment RAG** — chunk + embed PDF/doc text into pgvector; retrieve top chunks into
  the system prompt on follow-up turns (capped; invalidated on attachment delete). Chat-history
  corpus RAG still deferred.

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
- 🔜 Response caching, prompt token budgeting UI.

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
- ✅ **Account** — shows name + email; profile picture from Google (initials fallback).
- ✅ **Structured profile** — name, age, country, and job editable in Settings → Profile;
  persisted on `users` and injected into the chat system prompt (see [§6](#6-memory-remembering-the-user)).
- ✅ **Default model** — Flash / Pro.
- ✅ **Response style** — short / balanced / detailed (changes the assistant's verbosity).
- ✅ **Memory** — on/off toggle + link to manage saved memories.
- ✅ **Usage** — today's token meter.
- ✅ **Sign out.**
- ✅ **Data export** — exports profile + chats + messages + memories + todos + learning projects
  (with items) as JSON via the native share sheet (`GET /auth/me/export`).
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
- 🔒 **"Recalled" chips** — backend may still stream `recalled` / memory hints; mobile must
  **not** render a recalled chip (explicitly rejected — see `.cursor/rules/chat-ux-bans.mdc`).
- ✅ **Polish** — light haptic taps on key actions (Android via the built-in API) + chip fade-in
  animation.
- ✅ **iOS haptics** — `expo-haptics` on real devices (graceful no-op on Android / Expo Go).
- ✅ **Screen transitions** — shared stack presets: iOS-native push + back gestures on nested
  stacks, fade for auth/onboarding, fade-from-bottom for drawer utility screens (memory, todos).
- ✅ **Shared Button / type / space / motion tokens** — primary CTAs via `components/Button`;
  `lib/type.ts`, `lib/space.ts`, `lib/motion.ts` for high-traffic roles (incremental migration).
- 🔜 Full typography/spacing ownership across every screen; compact chip/pill controls stay
  specialized (not the shared Button).

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
- ✅ **Dedicated worker process** — Fly `app` (`PROCESS_ROLE=api`) + `worker` (`python -m
  app.worker_main`); local/dev default `process_role=all` keeps a single process. Scale with
  `fly scale count app=1 worker=1`. Multi-instance worker fleets remain a later ops concern.
- 🔜 Sentry/observability polish, structured request logging.

## 14. Todos & suggestions
- ✅ **Todo lists** — named lists (topics) with a list-first UX: create a list title, then add items;
  drawer shows a single **Todos** entry (not per-list submenus).
- ✅ **Todos API** — create, check off, delete items; delete entire list by topic; optional `due_at`.
- ✅ **LLM todo sync** — background job extracts add / complete / uncheck / delete / delete_list /
  set_due / clear_due from chat; injects current lists + overdue summary into the system prompt.
- ✅ **Due dates** — `due_at` on items; mobile date/time picker; relative labels in prompts
  (overdue, due today, due in N days); user timezone synced from device (`users.timezone`).
- ✅ **Local due reminders** — schedules a device notification at due time; resyncs on login,
  foreground, and todo changes; tap opens Todos screen. Lead time configurable (5 / 10 / 15 / 30 /
  **60 min** before due).
- ✅ **Proactive suggestions** — follow-up prompt ideas generated in the background from recent
  activity (best-effort; regenerated periodically); inline chips under the latest assistant reply.
- 🔜 1-hour-early **email/push** nudges beyond the local lead picker (calendar-aware).

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
- ✅ **ICS invite parsing** — folded lines, `TZID` / all-day `VALUE=DATE`, location/description
  notes, cancelled events skipped (LLM fallback when no `.ics`).
- 🔜 Richer sender templates, proactive chat nudges for email suggestions.

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
  adapters once before streaming (legacy; skipped when the tool loop is on).
- ✅ **Full tool-calling loop** — when `MCP_TOOL_LOOP_ENABLED=true`, model-initiated LiteLLM
  `tools=` rounds (`web_search` / `sympy` / `calendar`) with Pydantic-validated args, bounded by
  `mcp_tool_loop_max_rounds` (default off).
- ✅ **Golden rules preserved** — product aliases in services; structured outputs validated with
  Pydantic before DB writes (already enforced for calendar proposals and email extraction).

### Phase 3 — Smarter behavior
- ✅ **Conflict detection** — todo due times vs calendar events (server-side helper).
- ✅ **Create calendar events (confirm flow)** — user asks to schedule → model emits
  `calendar_proposal` fence → backend stores Redis proposal + injects `proposal_id` → mobile
  **Add to Calendar** card → confirm creates the Google event (requires calendar **write** scope).
- ✅ **Proactive calendar nudges** — push scheduler warns before connected Google Calendar
  events (default **15 min** lead; Redis dedupe per event). Tap opens Reminders calendar view.

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
8. Full LiteLLM tool-calling loop ✅ (flag-gated)
9. Email auto-add for high-confidence types (optional, post-MVP) 🔜

---

## 17. Projects (utility workspaces)

Recall is evolving from chat-only into a **holistic AI utility app**. **Learning** topics are
user-created workspaces beside **Todos** — for English vocabulary, general knowledge quizzes,
courses, habits, and anything else that needs structure over time.

### v1 (shipped foundation)
- ✅ **`projects` table** — title, description, `kind` (`general` | `vocabulary` | `language` |
  `trivia` | `learning`), archive flag.
- ✅ **REST API** — `GET/POST /projects`, `GET/PATCH/DELETE /projects/{id}`.
- ✅ **Mobile** — drawer **Learning** link → list → create → detail screen.
- ✅ **Project kinds** — API + mobile support only **English vocabulary** (`language`, with
  `vocabulary` as a write alias) and **general knowledge** (`trivia`). Legacy kinds
  (`programming`, `math`, …) are rejected on create and hidden from list/detail.

### Phase 2 — Vocabulary (Learning English)
- ✅ **Decks / groups** — organize words by deck title on the detail screen.
- ✅ **Vocab items** — term, definition, example sentence, status (new / mastered), review tracking.
- ✅ **Mark as known** — progress per item; stats on project detail (learned / due / this week).
- ✅ **AI tutor + quiz** — scoped chats from Learning; model emits `vocab_quiz` blocks; mobile
  shows A–D choices (tap chips or type letter; fast-path answers, minimal context, no web search
  on quiz turns). Wrong answers update SM-2 via deterministic ledger (`quiz_attempts` / `quiz_correct`).
- ✅ **Tap-to-answer MCQ** — interactive choice chips on complete `vocab_quiz` messages.
- ✅ **Review queue** — project detail CTA opens a due-only spaced-repetition chat session.
- ✅ **Adaptive level hints** — suggests level up/down from mastery ratio + quiz accuracy.
- ✅ **Streak + inactive days** — home highlight and project hero show streak; push/email
  nudges show “inactive for N days” copy (streak count is not included in notification text).
- ✅ **Goal-aware learning nudges** — push/email prioritize finishing today's daily batch; trivia
  included alongside vocabulary.
- ✅ **Pronunciation** — play button per word tries `pronunciation_url` when set, then cloud TTS,
  then on-device `expo-speech`.
- ✅ **Spaced repetition scheduling** — SM-2 fields (`ease_factor`, `interval_days`, `due_at`)
  update on vocab status changes; due counts prefer `due_at` (falls back to 24h heuristic).
- ✅ **Deck browse on language detail** — browse words by deck on the language project detail screen.

### Phase 3 — Cross-linking
- ✅ **`project_id` on chats** — conversations started from a project carry `project_id`; prompt
  injection scopes to that one project (+ tutor hints) instead of all projects.
- ✅ **Link todos to projects** — optional `project_id` on todo items (API create/update,
  prompt annotation, mobile link + project filter).
- ✅ **Home starters** — active project highlight on home; tap opens project or starts scoped chat.

### Phase 4 — More project types
- ✅ **General knowledge (trivia)** — topic picker, difficulty tiers (easy/medium/hard), scoped
  quiz chat, daily goal, trivia nudges. Each answered question stores a `project_items` row
  (reads capped); retention/rollup for very large decks is deferred.
- 🔜 **Learning (generic)** — lesson notes, spaced repetition beyond vocab, richer AI tutor mode.

Chat + memory + todos + projects share one backend; the LLM orchestrates across them (no keys on
device).

---

## Deferred to upcoming version(s)
A consolidated list of what's intentionally **not** (or only partially) in this version.

### Already shipped (keep for audit trail)
- ✅ **Full MCP / multi-turn tool loop** — LiteLLM `tools=` rounds behind `MCP_TOOL_LOOP_ENABLED`
  (default off). See [§16 MCP & calendar](#16-mcp--calendar-planned).
- ✅ **Attachment RAG** — pgvector chunk + embed over uploaded PDF/docs; top-k into the prompt.
- ✅ **Camera math solver** — attach sheet “Solve math with camera” → vision → SymPy → LaTeX/steps.
- ✅ **Web search** — Tavily primary + DuckDuckGo fallback; sources on assistant messages
  (hidden on vocab quiz cards).
- ✅ **Structured profile fields** — name / age / country / job (Settings + prompt injection).
- ✅ **Vision + Pro image gen** — image attachments route to vision models; Pro image generation
  via composer sheet (daily cap).

### Later / not v1
- 🔜 **Persist assistant reply across hard WS/SSE disconnect** — today disconnect cancels +
  refunds quota; no finalize-on-disconnect recovery for a mid-stream answer.
- 🔜 **Per-chat distributed prepare lock** — same-socket busy rejection exists; two concurrent
  connections can still race `prepare_chat_turn`.
- 🔜 **Algebra `canonical_fence` rewrite** — geometry/graph fences are validated post-stream;
  common algebra blocks still rely on the model copying SymPy verbatim.
- 🔜 **Math WebView expand / fullscreen** — tall worked steps stay capped at 320px with no scroll.
- 🔜 **Full locale translation** — key-set parity is enforced; ~340 strings still English in
  non-en locales (hardcoded UI strings from Claude review wave 3 are now keyed).
- 🔜 **Full chat-history semantic RAG** — embed past chats (beyond keyword `/search` + memory
  embeddings + attachment RAG). Index in background; retrieve small top-k at turn start so chat
  stays snappy. Not started.
- 🔜 **Plugins / arbitrary user MCP servers** — owned server-side tools only today.
- 🔜 **Code execution** beyond sandboxed HTML/chart preview (by design).
- 🔜 **Collaborative cursors / shared docs** — real-time co-editing; personal app only today.
- 🔜 **Web client** — same API; see [Web client](#web-client-planned) below.
- 🔜 Folders, editing arbitrary older messages, user-tunable routing rules, family plans,
  response caching / prompt-budget UI, duplex full-voice mode (out of scope).
- ⚠️ **Production R2 + store polish** — attachment code is done; prod R2 secrets and App Store /
  Play billing polish still pending (see Pre-deployment TODO).

### Pre-deployment TODO (from the holistic review)

Action items still open before the first production deploy. Correctness follow-ups from the
Jul 2026 architecture review are mostly shipped (see below); these remain:

- ⚠️ **R2 storage credentials** — the `R2StorageGateway` is wired and tested, but attachments
  run on local fallback until `STORAGE_BACKEND=r2` + `R2_ACCOUNT_ID` / `R2_ACCESS_KEY_ID` /
  `R2_SECRET_ACCESS_KEY` / `R2_BUCKET` secrets are set. (Code done; creds pending.)
- ⚠️ **Production env secrets** — `validate_production_settings` enforces
  `OAUTH_TOKEN_ENCRYPTION_KEY`, `OPENROUTER_API_KEY`, `CORS_ORIGINS`,
  `REVENUECAT_WEBHOOK_AUTH` (plus DB/Redis/Google/JWT/dev-flags). `ENVIRONMENT` now
  **defaults to `production` (fail-closed)** — local `.env` / `.env.example` must set
  `ENVIRONMENT=development`.
- 🔜 **Mobile gate + on-device pass** — `pnpm typecheck && pnpm lint && pnpm test` must run
  locally (deps don't install in the CI/dev-container env). Then an iOS **and** Android
  dev-build pass for: Google Sign-In, HTML/chart preview WebView, push, RevenueCat, the new
  cross-platform deck Modal, autoscroll, and the markdown throttle.
- ✅ **FlashList migration** — `ConversationList` and `Todos` now use `FlashList`
  (v2, auto-measured). Chat drawer rows and the flat reminders/done lists are
  virtualized; the calendar day-view and `ListGroupsView` render in the header
  (bounded/structured, not row-virtualized). Verify scroll/layout on-device.
- ✅ **i18n extraction (reminders / share / urgent)** — keys wired in `todoReminders`,
  `homeUrgentTodos`, `share.ts`, and push channel names; translated in all 9 locales.
- 🔜 **Locale prose translations** — all 9 locales share identical key sets (**787** keys), but
  many non-English values are still English copy (~340 keys in Spanish as a proxy). Structural
  i18n is complete; human translation of remaining prose is deferred.
- 🔜 **Legal page bodies** — `/legal/privacy` and `/legal/terms` remain English-only
  markdown on the API (nav titles are localized). Locale-aware legal content is deferred.
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

Still open (non-blocking / larger effort):

- 🔜 Multi-file HTML preview (deliberately deferred — single self-contained ` ```html ` fence)
- 🔜 Broader RTL coverage beyond the initial WebView / mount-queue suite
- 🔜 Locale prose + legal page bodies (see Pre-deployment TODO)

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
| PDF / doc upload + server text extract into prompt | ✅ Shipped (no OCR for scanned PDFs) |
| PDF inline preview (pdf.js WebView, dev build) | ✅ Shipped |
| Audio in (Whisper STT → composer) | ✅ Shipped (dev build) |
| Audio out (read aloud) | ✅ Cloud TTS + device `expo-speech` fallback (dev build) |
| pgvector RAG over attachment corpora | ✅ Shipped (`attachment_rag`; flag on by default) |
| Camera math solver UX | ✅ Shipped (attach sheet → vision → SymPy) |
| Full chat-history corpus RAG | 🔜 Deferred |
| Full duplex voice mode | 🔒 Out of scope |

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
- 🔜 **Approach to decide later** — react-native-web (reuse this Expo codebase) vs. a separate web
  app (e.g. Next.js) sharing only the API + types. Same API either way.

---

## 28. Product catalog (PM reference)

Internal product snapshot for leadership, engineering, design, GTM, and App Store review.
**Status:** pre–public launch on `main`. Supersedes one-off chat summaries when they disagree.

### Mission
Recall is a **personal AI utility** — not a generic chatbot. It remembers who you are, helps you
act (todos, calendar, email), and supports **Learning** (English vocabulary + general knowledge
quizzes). One trusted assistant combining ChatGPT-grade conversation with durable memory and
everyday productivity. **Programming help lives in main chat** (code blocks, previews) — not as a
structured Learning topic type.

### Strategic pillars
| Pillar | Meaning |
|--------|---------|
| Chat that feels fast | Streaming, stop/regenerate, rich answers, reasoning visible |
| Memory that compounds | Facts learned across chats, injected when relevant |
| Utility beyond chat | Todos, Learning, integrations, home starters |
| Trust & control | Export, delete account, opt-in integrations, quota transparency |
| Monetize fairly | Free tier with limits; Pro for power users |

### Release plan
| Phase | Scope | Status |
|-------|--------|--------|
| MVP (mobile) | Chat + memory + todos + Learning + calendar/Gmail + attachments | ~95% code-complete |
| Launch readiness | Provisioning, store builds, landing page, OAuth verification, on-device QA, R2 secrets | ~70% ops |
| v1.1 | Web client (same API), locale prose, legal localization | Not started |
| Later | Full chat-history RAG, gamification, user MCP plugins, folders / family plans | Not started |

Notes already on `main` (not waiting on v2): Fly api/worker split ✅, attachment RAG ✅,
flag-gated LiteLLM tool loop ✅, structured profile ✅, drawer FTS search ✅.

### Learning (not “programming projects”)
| Shipped | Not done |
|---------|----------|
| English vocabulary (`language`) — decks, quiz, tutor, SM-2 | Curated trivia marketplace |
| General knowledge (`trivia`) — topics, scoped quiz chat | Certificates, GitHub linking |
| Project-scoped chats, home highlight, link todos to projects | In-app code runner (out of scope) |
| ~~Programming curriculum kind~~ **removed** — use main chat for code help | — |

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
| Presigned upload, magic-byte validation, daily image cap | Production R2 until creds set |
| Vision routing for images | Document OCR for scanned PDFs |
| PDF text extract + pgvector attachment RAG | Full chat-history corpus RAG |
| Camera math solver (vision extract → SymPy → LaTeX) | Virus scan / enterprise DLP |
| PDF inline preview in message bubble | — |

### Voice
| Shipped | Not done |
|---------|----------|
| Record → Whisper → composer (dev build), waveform UI, rate limits | Duplex full-voice mode (out of scope) |
| Device TTS + cloud TTS (`POST /speech/tts`, daily caps, device fallback) | — |

### Cost guards (recent)
| Guard | Free | Pro |
|-------|------|-----|
| Daily tokens | 100k | 500k |
| Speech transcriptions/day | 30 | 200 |
| Speech TTS (read aloud)/day | 20 | 100 |
| Tavily searches/day | 20 (then DDG only) | 150 |
| R1 / smart-chat quota weight | 3.5× token charge | Same |

### Integrations
| Shipped | Not done |
|---------|----------|
| Google Calendar read + write (confirm flow) | Google OAuth verification for Gmail prod |
| Gmail → suggested reminders | Outlook, Slack, user MCP servers |
| MCP gateway skeleton + LiteLLM tool loop (flag-gated) | Arbitrary user MCP servers |

### Launch blockers (honest)
1. Cost guards (speech, Tavily, R1 weight) ✅
2. Provision Neon, Redis, R2, Fly, EAS ⬜
3. Landing page + support URL ⬜
4. Google OAuth verification (Gmail) ⬜
5. On-device QA matrix (iOS + Android) ⬜
6. R2 production attachments ⬜

### Explicitly not v1
Multi-user teams, collaborative editing, arbitrary code execution (except sandboxed HTML/chart
preview WebView), web client, gamification (XP/badges beyond learning streaks), duplex voice
mode, arbitrary user MCP servers, multi-file HTML preview.

**Planned later (not blocking launch):** full chat-history semantic RAG; locale prose + legal
bodies; folders / family plans. Attachment RAG and the LiteLLM tool loop are already on `main`
(tool loop flag-gated, default off) — see deferred list above.
