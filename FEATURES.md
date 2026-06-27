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
- 🔜 Folders/projects, archive, multi-select, and a true swipe-to-delete gesture (needs a gesture
  library + dev build).

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
- 🔜 Edit any earlier message, message-level share, reactions, read receipts, voice input.

## 4. Formatting & rendering
- ✅ **Markdown** — headings, **bold**/*italic*, bullet & numbered lists, blockquotes, links,
  inline code, horizontal rules.
- ✅ **Code blocks** — dark card, language badge, copy button, horizontal scroll.
- ✅ **Syntax highlighting** — token coloring (comments, strings, numbers, keywords) via a
  dependency-free tokenizer; covers common languages with a monochrome fallback for the rest.
- ✅ **Tables** — styled (header shading, borders, cell padding).
- ✅ **Inline images** — Markdown `![alt](url)` images render (contained, rounded).
- ✅ **Math / LaTeX** — KaTeX rendering for inline and block math.
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
- ✅ **Memory screen** — view memories grouped by type, with confidence, and **delete** them.
- ✅ **Memory toggle** — turn learning on/off in Settings.
- 🔜 **Structured profile fields** — name/age/country/job as discrete fields (today they're
  free-text memories).
- 🔜 **Semantic / vector recall (RAG)** — current recall is load-all + filter, not embeddings.

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
  bypassed by parallel requests).
- ✅ **Usage meter** — today's tokens vs. daily limit shown in Settings.
- ✅ **Real token accounting** — uses the provider's reported usage when available.
- 🔜 **Pro tier / higher limits / subscriptions** — single free tier only today.

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
- ✅ **Language / i18n** — `react-i18next` with English, Spanish, French, and Amharic.
- ⚠️ **Dark theme** — the chat screen follows the system light/dark scheme; the remaining screens
  are still light (theme rollout in progress).
- 🔜 Notifications (push infra), theming the remaining screens.

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
- 🔜 Proper iOS haptics (needs `expo-haptics`), richer screen transitions.

## 12. Monetization
- 🔜 **Payments / Pro entitlement / RevenueCat** — designed but not built; no paid tier on the
  backend yet (note: "Pro" today is just the `smart-chat` model label, not a subscription).

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
- ✅ **Todos** — a lightweight task list (`/todos`): create, check off, delete; a todo can be
  linked to the chat it came from.
- ✅ **Templates** — reusable starter prompts: built-in templates seeded on first run plus the
  user's own; start a chat from a template.
- ✅ **Proactive suggestions** — follow-up prompt ideas generated in the background from recent
  activity (best-effort; regenerated periodically).
- 🔜 Surfacing suggestions inline under replies, template-editing polish, todo reminders.

## 15. Code execution policy
- ⚠️ **Sandboxed HTML/CSS/JS preview only** — `html` fences can be previewed/run in an isolated
  WebView (no app token is exposed to it), and charts render via a sandboxed Vega WebView.
- 🔒 **No other code execution** — all other code (Python, shell, etc.) is rendered/highlighted
  only, and nothing runs outside the sandboxed preview WebView. (By design.)

---

## Deferred to upcoming version(s)
A consolidated list of what's intentionally **not** in this version:

- 🔜 **MCP (Model Context Protocol)** support
- 🔜 **Plugins / tools** (a tool-calling loop — prerequisite for most of the below)
- 🔜 **RAG** (embeddings + vector search; needs pgvector)
- 🔜 **Code execution**
- 🔜 **File upload**
- 🔜 **Image input/output** (multimodal models)
- 🔜 **Camera math solver** — snap a photo of a math problem → AI reads it, solves it, and renders
  the worked, step-by-step solution formatted to match the problem. Composite feature, built on:
  camera capture (`expo-camera` / image picker), **image input** via a **vision model or math OCR**,
  and **LaTeX rendering** for the formatted answer. (Depends on the image-input + Math/LaTeX items.)
- 🔜 **Web search**
- 🔜 Inline Mermaid rendering, grammar-perfect (library) syntax highlighting, payments/Pro tier,
  structured profile, dedicated worker process, folders/projects, archive, multi-select,
  swipe-to-delete (gesture lib), editing arbitrary (older) messages, live model latency/health,
  user-tunable routing rules, notifications, theming the remaining screens, iOS haptics
  (expo-haptics).

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
