# D. Network and I/O efficiency — the phone (NETM)

Auditor: NETM agent. Code audited: `/home/user/recall-audit` at `d2ec42b0` (read-only).
Paths starting with `apps/` are repo-relative; every other path (`features/…`, `lib/…`, `hooks/…`,
`contexts/…`, `components/…`, `app/…`, `node_modules/…`) is under `apps/mobile/`.
"Common cold start" below means a signed-in user whose stored
access token is older than its 60-minute lifetime (`apps/api/app/core/settings/auth.py:21`),
which is most cold starts.

Important runtime fact checked before writing anything about timeouts or upload bodies: Expo SDK 57
replaces the global `fetch` with `expo/fetch` (`apps/mobile/node_modules/expo/src/winter/runtime.native.ts:40-53`,
opt-out `EXPO_PUBLIC_USE_RN_FETCH`, not set in this repo). On Android that client is built from
React Native's `OkHttpClientProvider` (`node_modules/expo/android/src/main/java/expo/modules/fetch/ExpoFetchModule.kt:26-31`),
whose connect/read/write timeouts are 0 = none (`node_modules/react-native/ReactAndroid/src/main/java/com/facebook/react/modules/network/OkHttpClientProvider.kt:49-54`).
On iOS each request gets `timeoutInterval = 0` (`node_modules/expo/ios/Fetch/ExpoURLSessionTask.swift:27`).
WebSockets use React Native's own module (Android read timeout disabled, no ping:
`node_modules/react-native/ReactAndroid/src/main/java/com/facebook/react/modules/websocket/WebSocketModule.kt:89-91`).

---

## 1. Start-up trace (common cold start, signed in, cached account)

Mount order: `app/_layout.tsx:128-149` → `AppearanceProvider` → `ActionFeedbackProvider` →
`AuthProvider` (children render as soon as the cached account is read) → `ModelsProvider` →
`TodosProvider` → `HomeProvider` → `NetworkProvider` → `PushNotificationBootstrap`,
`AiConsentRedirect`, `RootNavigator` → `app/index.tsx` → `features/chat/screens/ChatScreen.tsx`
(inside `DrawerShell`, which always mounts `components/ConversationList.tsx`).
All requests below leave within the first second or two, mostly concurrently.

| # | Request | Trigger (file:line) | Cache / dedupe | Needed at that moment? |
|---|---|---|---|---|
| 0 | SecureStore token + onboarded flag, `cached-user.json` (local) | `contexts/AuthContext.tsx:105-109` | local | yes |
| 1 | `POST /auth/refresh` | first authenticated request sees an expired JWT (`lib/api/client.ts:226-232`) | single-flight per session (`lib/api/client.ts:97-135`) | yes |
| 2 | `GET /auth/me` | `contexts/AuthContext.tsx:120` | cached display fields paint first | yes (preferences are not cached) |
| 3 | `GET /models` | `contexts/ModelsContext.tsx:121-123` (unconditional on mount) | disk catalog painted first (`:75-87`); in-flight join (`:91-94`) | partly: catalog is cached, live health is not |
| 4 | `GET /todos/page?limit=1000` (loops all pages) | `features/todos/hooks/useTodosList.ts:115` → `features/todos/api.ts:8-21` | per-session memory, 20 s | open rows yes; full completed history no (NETM-08) |
| 5 | `GET /home?client_timezone=…` | `features/home/context/HomeContext.tsx:93-105` (`force: true`) | `StaleResourceCache` in-flight join | **no** — the UI reads only `greeting`, which the phone already computes (NETM-02) |
| 6-9 | `GET /health` + `GET https://clients3.google.com/generate_204`, **twice** | `hooks/useNetworkStatus.ts:47` (`NetInfo.fetch().then`) and `:48` (`addEventListener` calls the handler immediately, `node_modules/@react-native-community/netinfo/src/internal/state.ts:110-119`) | `probeGen` drops the first result, both pairs are sent | one probe at most (NETM-01) |
| 10 | iOS: NetInfo's own `HEAD generate_204`, then every 60 s (5 s while unreachable) | NetInfo default config, never configured (`node_modules/@react-native-community/netinfo/src/internal/defaultConfiguration.ts:3-15`, `internetReachability.ts:105-127`) | — | no: duplicates rows 6-9 (NETM-01) |
| 11 | `POST /chats` (speculative empty "draft" chat) | `features/chat/hooks/useDraftChat.ts:76-84`, 125 ms after mount | per view | speculative (NETM-05) |
| 12 | WebSocket `/ws/chats/{draft}` + auth frame | `features/chat/hooks/useChatDraftWarmup.ts:17-23`, `useChatTransport.ts:104-110` | one per view | speculative (NETM-05) |
| 13 | `GET /chats/usage/today` (free users; paid users too until the server's user arrives with the refresh or `/me`, because the cached plan is forced to `"free"`, `lib/cachedUser.ts:79-85`) | `features/chat/hooks/useQuotaNudge.ts:44-60` | none (bypasses `lib/cache/usageCache.ts`) | free users only |
| 14 | `GET /chats/usage/today` again | the token refresh in row 1 changes `token`, a dependency of `useQuotaNudge.ts:60` | none | no (NETM-03) |
| 15 | `GET /chats` (≤200 active + ≤50 archived rows) | `hooks/useDrawerChatList.ts:120-132` (idle task while the drawer is closed) | `SessionResourceCache`, 20 s | reasonable prefetch (drawer, `getCachedChat`) |
| 16 | Expo push-token service (exp.host) + `POST /users/push-token` (DB upsert) | `hooks/useBootstrapSync.ts:63-91` → `lib/pushNotifications.ts:200-240` | "12 h fresh" is module memory, reset every process (`lib/pushNotifications.ts:181-191`) | no, on most launches (NETM-12) |
| 17 | `PATCH /auth/me {timezone}` | `hooks/useBootstrapSync.ts:25-42` | only when the device zone differs | yes when it differs |
| 18 | GPS fix + platform reverse geocode (+ `PATCH /auth/me {location}` if changed) | `hooks/useBootstrapSync.ts:44-61` → `lib/deviceLocation.ts:60-79` | none | once per launch defensible; re-runs hourly (NETM-03) |
| 19 | RevenueCat `configure` (SDK network) + listener | `hooks/useBootstrapSync.ts:103-146`, `lib/purchases.ts:94-107` | once per user per process | yes (see Open questions) |
| 20 | Sentry init (if DSN) | `app/_layout.tsx:121-126` | — | yes |

Not network: fonts are bundled (`app/_layout.tsx:101-115`), i18n JSON is bundled (`lib/i18n/*.json`),
appearance prefs are local. Cold start total: about 14-17 requests (plus a WebSocket), of which
rows 5, 6-9 (one pair), 10, 14 and usually 16 add nothing; 11-12 are speculative.

## 2. Opening a chat from the drawer (from the new-chat screen)

`components/ConversationList.tsx:153-164` `openChat` → `router.setParams({ chatId })` →
`features/chat/hooks/useChatRouteLoader.ts:332-441` and `useChat`/`useChatTransport`.

| # | Request | Trigger | Notes |
|---|---|---|---|
| 1 | `DELETE /chats/{draft}` | `useChatRouteLoader.ts:351-353` → `useDraftChat.ts:30-41` | throws away row 11 above |
| 2 | read `chat-pages/{id}.json` (disk), paint | `useChatRouteLoader.ts:386-407` | stale-while-revalidate |
| 3 | `GET /chats/{id}` | `useChatRouteLoader.ts:409-412` | skipped when the drawer list has the row (usual) |
| 4 | `GET /chats/{id}/messages?limit=40` | `useChatRouteLoader.ts:409-412` | **always**, even if fetched seconds ago (no freshness check on this path; the foreground path has one at `:225-246`) |
| 5 | close draft socket, open `/ws/chats/{id}` 100 ms later | `features/chat/hooks/useChat.ts:223-251` (detach), `useChatTransport.ts:104-110`, `features/chat/model/wsConnect.ts:13` | one handshake per chat view, used or not |
| 6 | `GET /attachments/{id}/url` per visible *file* attachment | `features/attachments/model/attachmentIndexStatus.ts:98-116` | shared poller, once per session per file, backoff; fine |
| 7 | `GET /attachments/{id}/file?w=…` per image | `components/ChatMessageImage.tsx:134-157`, expo-image `cachePolicy="memory-disk"` | server thumb at 2× layout width; fine |
| 8 | full PDF download per PDF card (page-1 preview) | `features/attachments/hooks/usePdfPreview.ts:57-75` | disk cache 7 days / 200 MB (`attachmentFileStore.ts:9-11`) |
| 9 | `GET /link-preview?url=` per allowed link | `components/LinkPreviewCard.tsx:26-41` → `lib/linkPreview.ts:17-33` | session Map for successes only (NETM-13) |
| 10 | `GET /chats/{id}` every 2 s, ≤8 times | `useChatRouteLoader.ts:421-423` → `useChatTitlePolling.ts:22-23,61-95` | only for an untitled chat |

**Switching A → B → A** repeats rows 3-5 on every switch: a 40-message page and a new
WebSocket handshake each time, even within seconds (the 20 s rule used on foreground is not used here).

**Returning from background** (≥5 min away, chat open). One `AppState` listener per concern, each
with its own staleness rule:

| Request | Listener | Staleness rule |
|---|---|---|
| `GET /health` + `GET generate_204` | `hooks/useNetworkStatus.ts:50-53` | none: every return (and every NetInfo event) |
| `GET /models` | `contexts/ModelsContext.tsx:125-137` | 5 min |
| `GET /home` | `features/home/context/HomeContext.tsx:116-123` | 20 s |
| `GET /todos/page` (full history) | `features/todos/hooks/useTodosList.ts:116-122` | 20 s |
| `GET /chats/{id}/messages?limit=40` (+ `GET /chats/{id}` if unlisted) | `features/chat/hooks/useChatRouteLoader.ts:268-326` | 20 s (disk `cached_at`) |
| new WebSocket + auth frame | `features/chat/hooks/useChatTransport.ts:120-135` | socket was released in background |
| push sync | `lib/pushNotifications.ts:234-239` | 12 h (local permission check only) |

If the app was away more than 60 minutes, `POST /auth/refresh` follows, and the token change re-runs
the token-keyed effects (NETM-03): `/home` (forced), `/models`, usage (free users), GPS + reverse geocode,
and a new draft chat. The reconnecting WebSocket was already built with the expired token (NETM-04).
Backgrounding (or an iOS `inactive` blip) with an untouched new chat costs
`GET /chats/{draft}/messages?limit=20` + `DELETE` + `DELETE` (NETM-05).
Typical return: 6-9 requests plus a WebSocket handshake.

---

## 3. Findings

### NETM-01 — Connectivity probe: fixed 1.5 s poll with no backoff or jitter, plus a probe on every foreground and NetInfo event, and two probing systems at once
- Severity: High
- Confidence: High
- Locations:
  - `apps/mobile/hooks/useNetworkStatus.ts:11` (`OFFLINE_POLL_MS = 1_500`), `:63-83` (degraded loop, `setInterval` at `:80`)
  - `apps/mobile/hooks/useNetworkStatus.ts:33-45` (every NetInfo event runs a probe), `:47-48` (two probes at start), `:50-53` (probe on every return to the app)
  - `apps/mobile/lib/networkProbe.ts:7,57-74` (each probe = our `/health` + Google's `generate_204`), `apps/mobile/lib/api/connectivity.ts:10-24`
  - NetInfo left at defaults (never `NetInfo.configure`d anywhere in `apps/mobile`): on iOS its own JS reachability check runs `HEAD https://clients3.google.com/generate_204` every 60 s, every 5 s while unreachable (`node_modules/@react-native-community/netinfo/src/internal/defaultConfiguration.ts:3-15`, `internetReachability.ts:105-127`; iOS native reports no `isInternetReachable`). On Android NetInfo emits on a cellular-generation change (LTE↔5G), `node_modules/@react-native-community/netinfo/android/src/main/java/com/reactnativecommunity/netinfo/ConnectivityReceiver.java:120-131`, and each emission runs our probe.
- Evidence:
  ```ts
  // hooks/useNetworkStatus.ts
  const OFFLINE_POLL_MS = 1_500;
  ...
  void NetInfo.fetch().then(onNetInfo);
  const unsubscribe = NetInfo.addEventListener(onNetInfo); // NetInfo calls the handler at once (state.ts:110-119)
  ...
  // While degraded, keep probing ... Each probe is two requests.
  void tick();
  const id = setInterval(() => void tick(), OFFLINE_POLL_MS);
  ```
  `git show d8e19b301` (2026-10-15, "Offline banner: stop probing while the app is in the background") measured
  "80 requests a minute" and only paused the loop in the background; the foreground interval, the lack of
  backoff/jitter and the stop condition (only `status === "online"`) are unchanged.
- Impact: while the API is slow (>3.5 s), down, or blocked for one user's network (captive portal, DNS,
  corporate firewall), every foregrounded phone sends `/health` about 40 times a minute plus the same to
  Google, indefinitely and in lockstep (no jitter). During an API incident with 5,000 phones in the
  foreground that is ~3,300 req/s of `/health` arriving exactly when the API is recovering (each one a TLS
  handshake and, if Fly counts it, a slot in `hard_limit = 200` per Machine, `fly.toml:73-75`). In steady
  state it still costs 2 requests per app return, per NetInfo event, and a duplicate pair at every cold start,
  plus iOS NetInfo's 60 requests an hour to Google per foregrounded user. Battery and data for users on
  networks that block our host are the worst case: 80 requests/min with the screen on.
- Fix: in `useNetworkStatus` keep the immediate probe on a NetInfo "link up" or a return to the app, then
  back off the degraded loop (1.5 s → 3 → 6 → … → 60 s, ±20% jitter), reset on a NetInfo change. Probe once at
  start (drop `NetInfo.fetch()` or ignore the listener's first callback). Skip the return-to-app probe when an
  API request succeeded in the last N seconds (record success in `lib/api/client.ts` `requestRaw`). Call
  `NetInfo.configure({ reachabilityShouldRun: () => false })` once (the app does its own probing and
  `lib/networkStatus.ts` only trusts `isConnected`). Seam: `hooks/useNetworkStatus.ts`, `lib/networkProbe.ts`.
- Effort: S
- Verify: extend `hooks/__tests__/useNetworkStatus.test.tsx` with fake timers: degraded for 10 min → probe
  count ≤ ~15 (today ≈ 400); one probe at mount; no probe on return within N s of a successful request.
  Production: `/health` request rate per active user before/after (Fly metrics).

### NETM-02 — `GET /home` is fetched at start, on every token refresh (forced), every return after 20 s and on chat focus, for a greeting the phone already computes
- Severity: Medium
- Confidence: High
- Locations:
  - `apps/mobile/features/home/context/HomeContext.tsx:93-105` (start and every `token` change: placeholder + `refresh({ force: true })`), `:109-112`, `:116-123` (every return to the app)
  - `apps/mobile/features/home/hooks/useHomeRefreshOnChatFocus.ts:13-27`
  - the only reader: `apps/mobile/features/home/components/HomeStarters.tsx:91,101,124` (`display.greeting`); the overdue row is computed locally from the to-do list at `:102-109` (`listHomeUrgentTodos(todos, …)`)
  - local greeting already exists: `apps/mobile/features/home/model/homeWelcome.ts:7-13` (`localGreeting`, translated)
  - server: `apps/api/app/modules/home/greeting.py:11-24` (English phrase + first name), `apps/api/app/modules/home/service.py:40-83` (also queries `list_due_soon` for `urgent_todos`, which no phone code reads)
- Evidence:
  ```tsx
  // HomeStarters.tsx
  const { screen } = useHome();
  const display = screen ?? instantHomePlaceholder();
  const urgent = listHomeUrgentTodos(todos, undefined, leadMinutes);   // local, not screen.urgent_todos
  <Text style={s.greeting}>{display.greeting}</Text>                  // the only field used
  ```
  A repo-wide search finds no other read of `screen.urgent_todos`, `.subtitle` or `.starters`. The starter
  chips were removed on 2026-10-04 (`git show 2cf7db33e`), leaving `/home` with nothing the phone needs.
- Impact: 1 request per cold start + 1 per return after 20 s + 1 per hourly token rotation, per user: roughly
  1-2 million requests a day at 100k DAU, each an authenticated API call plus a Redis read (and a DB query on
  a miss). Side effects: (a) the token-change branch first resets the screen to the placeholder, so the
  greeting flickers hourly; (b) the server greeting is English-only ("Good morning", "Hey there") and replaces
  the translated `localGreeting` once it lands, so a French user sees "Bonjour" turn into "Good morning, Sam"
  (i18n bug; route to the clarity/i18n owner).
- Fix: render `localGreeting(now)` + the first name from `useAuth().user` in `HomeStarters`, and delete the
  phone's `HomeProvider` fetch path (`HomeContext`, `useHomeRefreshOnChatFocus`, `homeApi`). Keep or retire
  `/home` on the server separately (web slice?).
- Effort: S
- Verify: start-up request capture (or a jest test around `app/_layout` providers with `lib/api` mocked)
  shows no `/home`; `HomeStarters` snapshot test per locale shows the translated greeting with the name.

### NETM-03 — Effects keyed on the bearer token re-run on every access-token rotation (hourly, and on most cold starts); the class was fixed twice case by case, seven instances remain
- Severity: Medium
- Confidence: High
- Locations (each effect lists `token` in its dependencies and does I/O):
  - `apps/mobile/contexts/ModelsContext.tsx:89-123` — `refresh` depends on `[token, userId]` (`:119`), and `useEffect(() => { void refresh(); }, [refresh])` (`:121-123`) refetches `GET /models` with no TTL (the 5-min TTL exists only in the AppState listener, `:125-137`)
  - `apps/mobile/features/home/context/HomeContext.tsx:93-105` — on every token change: `setScreen(instantHomePlaceholder())` + forced `/home` (see NETM-02)
  - `apps/mobile/features/chat/hooks/useQuotaNudge.ts:44-60` — `[token, isPaid, refreshKey]`, no dedupe: two `GET /chats/usage/today` at a common cold start, one more per rotation
  - `apps/mobile/hooks/useBootstrapSync.ts:44-61` — `[token, userId, location, locationEnabled, setUser]`: a GPS fix + platform reverse geocode (`lib/deviceLocation.ts:60-79`) every rotation; if the OS permission is not granted but `canAskAgain`, `lib/deviceLocation.ts:46-47` shows the system permission sheet from this background sync, against the project's own rule "Permission prompts belong to explicit user actions, never a background refresh" (`features/todos/model/todoReminders.ts:98`)
  - `apps/mobile/features/chat/hooks/useDraftChat.ts:43-84` — `prepareDraftChat` depends on `[token, chatId]` (`:70`); a rotation re-runs the prewarm effect (`:76-84`) and creates a draft chat when none exists (NETM-05)
  - `apps/mobile/features/attachments/components/AttachmentImageStage.tsx:257-281` (deps at `:281`) and `features/attachments/hooks/usePdfPreview.ts:57-75` — `token` in the deps of a download effect: a rotation aborts the in-flight full-size image/PDF download (last waiter cancels) and starts it again
  - (`useChatTransport.ts:82-110` also depends on `token` but reuses the old transport — that is NETM-04)
- Evidence: the rotation is real and hourly: `jwt_expire_minutes: int = 60` (`apps/api/app/core/settings/auth.py:21`);
  `lib/api/client.ts:226-232` refreshes proactively and `contexts/AuthContext.tsx:221-231` publishes the new
  token (and a new `user` object) to React. The team fixed two instances one at a time:
  `git show fce17eb0d` (push: "re-registered … on every hourly access token refresh") and `git show bde74a124`
  (RevenueCat: "Every hourly token refresh called Purchases.configure again"), whose fix is the pattern to copy:
  ```ts
  // hooks/useBootstrapSync.ts:104-108 (the fixed one)
  const tokenRef = useRef(token);
  tokenRef.current = token;
  const signedIn = Boolean(token);
  ```
  HomeContext even says "Access tokens rotate during a healthy session. Cache/dedupe by account, not bearer
  token" (`:34-36`) but its effect still depends on `token`.
- Impact: per active user-hour: +1 `/models`, +1 forced `/home` (with a visible reset of the home row), +1 usage
  GET (free plan), +1 GPS fix and reverse geocode (location users; the platform geocoders are rate-limited per
  app), and an aborted-and-restarted download if a viewer is open. At a common cold start the token refresh
  happens while the first wave is in flight, so most of these join; the usage GET (and, for paid users, a usage
  GET that should not happen at all because the cached plan is forced to `"free"`) does not.
- Fix (fix the class): keep the token out of effect dependencies; depend on account identity
  (`user.id` + session generation, or a `useAuthSession()` value that changes only on sign-in/out) and read the
  latest token from a ref at call time — `request()` already refreshes. Add a lint/test guard: a hook test that
  re-renders `AuthProvider` with a rotated token and asserts no new calls to the `lib/api` mock.
- Effort: S
- Verify: new test in `contexts/__tests__/` rendering the provider tree, rotating the token via
  `setTokenRefreshHandler`, and asserting zero additional `listModels`/`getHomeScreen`/`todayUsage`/
  `updateMe` calls and no `getCurrentPositionAsync` call.

### NETM-04 — The chat WebSocket keeps the token it was created with; an expired token makes the server say "Unauthorized" and the chat view stays on SSE
- Severity: Medium
- Confidence: High
- Locations:
  - `apps/mobile/features/chat/hooks/useChatTransport.ts:82-100` — a transport is built once per view with the render's `token` (`:86-89`) and reused (`if (!transport)`) after the token changes
  - `apps/mobile/features/chat/model/wsTransport.ts:113-151` — reconnects after an idle close (4408) or 1001/1012 send `this.options.token` (`:146-149`)
  - `apps/mobile/features/chat/hooks/useChatTransport.ts:120-135` — return to the app reconnects with the React `token`, which after >60 min away is expired (the proactive refresh lives only in `lib/api/client.ts:226-232`, which WebSockets bypass)
  - `apps/mobile/features/chat/model/wsTransport.ts:183-195` (`preferSse = true` on "Unauthorized"), `:114` (`connect()` is then a no-op for the rest of the view); `features/chat/hooks/useChatIncoming.ts:271-282` (replays the turn over SSE)
  - server: `apps/api/app/modules/chat/ws_api.py:234-275` (auth frame verified), `:388-403` ("Re-check access on every chargeable frame"), socket idle close 300 s (`apps/api/app/core/settings/edge.py:19`) so a busy chat keeps one socket for hours
- Evidence:
  ```ts
  // useChatTransport.ts
  let transport = wsTransportRef.current;
  if (!transport) {
    transport = new ChatWsTransport({ url: chatWebSocketUrl(chatId), token, ... });
  // wsTransport.ts — on "Unauthorized":
  this.preferSse = true;   // connect() returns early from now on
  ```
- Impact: two common paths. (1) Reopening the app more than an hour later onto an open chat: the reconnect
  sends the expired token, the server refuses it, and every send in that chat view goes over SSE until the user
  leaves the chat. (2) A conversation that outlives the token on one socket: the next turn's frame is refused,
  then replayed through SSE (an extra round trip plus a refresh on that turn's time-to-first-token), and SSE
  again for the rest of the view. Each is a wasted authenticated handshake/frame, and SSE loses the WebSocket
  stop path (`cancel` with `shown_chars`, `wsTransport.ts:219-223`), which CLAUDE.md names as the reason
  WebSocket is preferred.
- Fix: before `transport.connect()` and before `beginTurn`, run the same expiry check as `requestRaw`
  (`accessTokenNeedsRefresh` → shared `refreshAccessToken`, exported from `lib/api/client.ts` as a
  `freshAccessToken()` helper) and pass the fresh token per connect (make `options.token` a getter). On an
  "Unauthorized" auth reply, refresh once and retry the WebSocket instead of latching SSE. Seam:
  `features/chat/model/wsTransport.ts` + `lib/api/client.ts`.
- Effort: S
- Verify: `features/chat/model/__tests__/chatWsTransport.test.ts`: a transport created with token A, idle-closed
  (4408), reconnects with token B after rotation; an expired token triggers one refresh and a WebSocket retry,
  not `preferSse`. Production: share of turns sent over SSE (`chat_ttft.transport`) should drop.

### NETM-05 — Speculative work on *view*, not on *intent*: every new-chat view creates a server chat and a WebSocket; leaving, backgrounding or an iOS `inactive` blip deletes it with three requests, and every chat view holds an idle socket
- Severity: Medium
- Confidence: High (mechanism); Medium (fleet cost, depends on how Fly counts sockets)
- Locations:
  - create: `apps/mobile/features/chat/hooks/useDraftChat.ts:7,76-84` (125 ms after the screen mounts) → `:43-70` (`POST /chats`, `:55-57`); socket: `features/chat/hooks/useChatDraftWarmup.ts:17-23`, `features/chat/model/draftLogic.ts:66-78`
  - eager socket for every chat view: `apps/mobile/features/chat/hooks/useChatTransport.ts:102-110`, `features/chat/model/wsConnect.ts:13` (100 ms debounce)
  - discard on background **or `inactive`**: `apps/mobile/features/chat/hooks/useChatRouteLoader.ts:272-283` calls both `discardEmptyChat(draftId)` (`useDraftChat.ts:24-28` → `features/chat/api.ts:63-78`: `GET /chats/{id}/messages?limit=20`, then `DELETE`) and `clearDraftChat()` (`useDraftChat.ts:30-41`: a second `DELETE` of the same id)
  - discard on opening another chat / New chat: `useChatRouteLoader.ts:341-353`, `:160-186`
  - not re-created on return: the prewarm effect (`useDraftChat.ts:76-84`) depends on `[token, chatId, prepareDraftChat]`, none of which changes when the draft is cleared, so the next send pays a serial `POST /chats` (`features/chat/hooks/useEnsureChatId.ts:32-37`) — until a token rotation re-creates one (NETM-03)
  - server context: empty chats are hidden from lists (`apps/api/app/repositories/chats.py:83,101`) and no job deletes them, so a draft whose DELETE never left (app killed, offline) stays in the table; WebSocket limits `apps/api/app/modules/chat/ws_api.py:53-54` (30 handshakes/user/min, 60 unauthenticated handshakes/IP/min), idle close 300 s (`apps/api/app/core/settings/edge.py:19`); `fly.toml:73-75` (`type = "requests"`, `hard_limit = 200`) and `docs/PRODUCTION.md:205-213` ("Whether Fly's proxy counts each open chat WebSocket as one in-flight request for its whole life … was not confirmed")
- Evidence:
  ```ts
  // useChatRouteLoader.ts:272-282
  if (state === "background" || state === "inactive") {
    ...
    if (messages.length === 0 && chatId == null) {
      discardEmptyChat(draftId);   // GET ?limit=20 + DELETE
      clearDraftChat();            // DELETE again (same id, still in draftChatIdRef)
    }
  ```
  The prewarm was added on purpose for time-to-first-token (`git show 49a3dee1c`, 2026-09-10, "Prewarm new chats before the first send").
- Impact: the most common session ("open the app, glance, leave") costs `POST /chats` (DB insert) + a
  WebSocket handshake (two Redis rate-limit checks + token verification) + `GET` of up to 20 messages +
  2 × `DELETE` (DB delete), for zero user value; iOS fires `inactive` for Control Center, the app switcher,
  system permission alerts and incoming calls, so the draft is also thrown away mid-session and the
  prewarm it paid for is lost. Every chat view (including just reading history) holds a socket until the user
  leaves, backgrounds or idles 5 minutes, so the socket count tracks "people looking at a chat", not
  "turns in flight": if Fly counts sockets against `hard_limit = 200`, idle prewarm sockets decide the
  machine count. Users behind one NAT (a school using the tutoring features) share the 60/min per-IP
  handshake budget, and view-time handshakes spend it.
- Fix: prewarm on intent, not on mount: create the draft and open the socket on composer focus / first
  keystroke / attach (the user still types for seconds, which hides the round trip). Replace the
  create/delete churn with one reusable empty draft per account (server: `POST /chats` returns the user's
  existing empty chat if any — idempotent), or let the first WebSocket/SSE message create the chat. If a delete
  is still needed: one call, a server-side conditional delete (`DELETE /chats/{id}?if_empty=1`) instead of
  downloading 20 messages, and only on `background`, not `inactive`. Seams: `features/chat/hooks/useDraftChat.ts`,
  `useChatTransport.ts`, `apps/api/app/modules/chat/api.py`.
- Effort: M
- Verify: `features/chat/hooks/__tests__/useDraftChat.test.tsx` + `useChatRouteLoader.test.tsx`: mount →
  background with no typing → zero `createChat`/`deleteChat`/`deleteChatIfEmpty` calls; `inactive` never
  deletes. Production: `POST /chats` count ÷ chats that received a message (today ≫ 1), and open-socket count
  per Machine vs turns in flight.

### NETM-06 — After a turn the phone polls for data the stream could carry, including three full to-do list reads that cannot find a change with the default settings
- Severity: Medium
- Confidence: High
- Locations:
  - usage after **every** turn (free plan): `apps/mobile/features/chat/hooks/useChatScreenError.ts:92-99` bumps `refreshKey` when a stream ends → `features/chat/hooks/useQuotaNudge.ts:44-60` (`GET /chats/usage/today`); the `done` event carries no usage (`apps/api/app/modules/chat/stream_events.py:157-173`)
  - to-dos: `apps/mobile/features/chat/model/chatEvents.ts:79-80,111-119` (`todos_changed` → refresh now, at 2.5 s and at 7 s), `features/chat/screens/ChatScreen.tsx:74-76` (`force: true`, so the 20 s freshness is bypassed), each read is the full history (NETM-08). Server defaults: `reminder_proposals_enabled = True` (`apps/api/app/core/settings/chat.py:22`) ⇒ `materialize_reminder_fences(confirm=True)` writes nothing and returns 0 rows (`apps/api/app/modules/todos/reminder_fences.py:97-113`) and the background `todos` job is skipped (`apps/api/app/modules/chat/post_turn.py:128-134`); `todos_changed` then comes only from the transcript heuristic (`apps/api/app/modules/chat/finalize_reminders.py:64-68`)
  - title: `apps/mobile/features/chat/hooks/useChatTitlePolling.ts:22-23,61-95` (`GET /chats/{id}` every 2 s, up to 8)
  - dropped turn: `apps/mobile/features/chat/model/turnReconcile.ts:10-14,56-88` with `features/chat/hooks/useDroppedTurnReconcile.ts:41-42` (a full 40-message page every 2 s, up to 15 times, to learn whether one new row exists)
- Evidence:
  ```ts
  // chatEvents.ts
  /** Background Schedule extraction can finish after `done`, so the to-do list refreshes again. */
  const TODO_RESYNC_DELAYS_MS = [2_500, 7_000] as const;
  ...
  if (payload.todos_changed) {
    ctx.onTodosSyncRef.current?.();
    for (const delay of TODO_RESYNC_DELAYS_MS) { ...setTimeout(() => ctx.onTodosSyncRef.current?.(), delay) }
  ```
  The "background Schedule extraction" those delays wait for is the `todos` post-turn job, which is off while
  reminder proposals are on (the default). ES-35 said these waits would be "removed by ES-24's
  `todos_changed`" (`docs/ENGINEERING_STANDARDS_TICKETS.md:946`); they were only renamed (a straggler).
- Impact: free users (the majority) add one authenticated GET to every chat turn; a reminder-flavoured turn adds
  three full to-do downloads although, with proposals on, nothing on the server changed (the tap on the card
  does its own refresh, `features/todos/hooks/useReminderProposal.ts:27-30`). Dropped-turn polling after a
  deploy (every socket gets 1012 at once, `features/chat/model/wsTransport.ts:27-34`) makes every phone that
  was mid-turn download 40-message pages every 2 s in lockstep.
- Fix: put the quota numbers the nudge needs (`used_tokens`, `daily_limit`) in `DoneEvent` and update the nudge
  from the event (keep one GET at mount). Fire the to-do refresh once, and only when the server says rows were
  written (send `todos_changed` only for `created > 0`, or a new `todos_written` count); delete
  `TODO_RESYNC_DELAYS_MS` while proposals are on. Poll dropped turns with `limit=4` and fetch the 40-message page
  once when the reply is found; add ±25% jitter to the 2 s interval. Seam: `apps/api/app/modules/chat/stream_events.py`
  (`DoneEvent`) + `features/chat/model/chatEvents.ts`.
- Effort: S
- Verify: `features/chat/hooks/__tests__/useChatIncoming.test.tsx`: a `done` with `todos_changed` produces one
  `listTodos` call; `useChatScreenError.test.tsx`: a turn end updates the nudge without `todayUsage`.
  Production: requests per chat turn (today: 1 WebSocket frame + 1-4 GETs + 2 analytics POSTs).

### NETM-07 — Product analytics: one POST per event, two per chat turn, every turn, although the endpoint takes 20 per batch
- Severity: Medium
- Confidence: High
- Locations:
  - `apps/mobile/features/chat/model/latency.ts:63-87` (`markChatFirstToken`: `chat_ttft` after the first token) and `features/chat/model/turnOutcome.ts:72-82` (`chat_turn_outcome` after done) → `features/chat/model/latencyReporter.ts:32-65`
  - `apps/mobile/lib/productAnalytics.ts:18-41` (same one-event pattern for paywall/purchase/push events)
  - "sampling" is just "not in dev": `features/chat/model/latency.ts:13-17`, `features/chat/model/turnOutcome.ts:40-43`
  - each send also reads SecureStore (`latencyReporter.ts:38`, `getToken()` → `lib/auth.ts:104-107`) and the installation id
  - server batch contract: `apps/api/app/models/schemas/analytics.py:39-42` (`events: list[...] = Field(min_length=1, max_length=20)`); every POST is `get_current_user` + insert + commit (`apps/api/app/modules/analytics/api.py:13-24`)
- Evidence:
  ```ts
  // latencyReporter.ts
  const token = await getToken();
  ...
  await analyticsApi.recordProductEvents(token, [ { name, properties, ... } ]);   // always a 1-element batch
  ```
- Impact: a chat turn over the WebSocket is one frame; telemetry adds two separate HTTPS requests, each an
  auth lookup and a database commit — at 100k DAU × 20 turns/day that is ~4M requests and commits a day,
  likely more than the chat traffic itself in request count. The `chat_ttft` POST also competes with the reply
  stream on a weak radio.
- Fix: a small in-memory queue in `lib/productAnalytics.ts` (one seam for all events): flush on turn end, when
  20 events are queued, after 30 s, and on `AppState` background; send `chat_ttft` and `chat_turn_outcome` for
  a sample (e.g. 10-20%, the buckets are already coarse). Pass the token from the caller instead of reading
  SecureStore per event.
- Effort: S
- Verify: unit test of the queue (two turns → one POST with four events); production: `/analytics/events`
  request rate per chat turn drops from 2 to ≤0.2.

### NETM-08 — Whole resources are re-downloaded on every trigger, with no conditional request or delta; the to-do list is the user's entire history
- Severity: Medium
- Confidence: High
- Locations:
  - `apps/mobile/features/todos/api.ts:4,8-21` (`listTodos` walks every `/todos/page?limit=1000` page); server returns every row, completed ones included (`apps/api/app/modules/todos/repository.py:72-84`, no `checked` filter) and nothing ever deletes completed rows (no job in `apps/api/app/background/`)
  - triggers of a full read: start (`features/todos/hooks/useTodosList.ts:115`), every return after 20 s (`:116-122`), after every create/toggle/edit/delete (`features/todos/hooks/useTodosActions.ts:74-76`, called at `:100` and `:148`; a burst of taps coalesces into one read, but the PATCH/POST response already holds the row), after a reminder-card confirm (`features/todos/hooks/useReminderProposal.ts:27-30`, ignoring the `items` the server returns, `apps/api/app/modules/todos/api.py:99-113`), and three per reminder-flavoured turn (NETM-06)
  - chat page on open: `features/chat/hooks/useChatRouteLoader.ts:408-412` always reads `GET /chats/{id}/messages?limit=40`, although the same hook skips a read made <20 s ago on the foreground path (`:225-246`) and records the time it needs (`:419`)
  - no `ETag`, `If-None-Match`, `If-Modified-Since` or `since=` anywhere in `apps/mobile` or `apps/api/app` (repo-wide search); see Open questions for response compression
- Evidence:
  ```ts
  // features/todos/api.ts
  const TODO_PAGE_SIZE = 1000;
  ...
  for (;;) {
    const page = await request<TodoPage>(`/todos/page?limit=${TODO_PAGE_SIZE}${suffix}`, token, options);
    page.items.forEach((row) => rows.set(row.id, row));
    if (page.next_cursor === null) return [...rows.values()];
  ```
  ```ts
  // useTodosActions.ts:74-76
  const reconcile = useCallback(() => {
    if (isSameOwner()) void refresh({ silent: true, force: true, afterPending: true });
  ```
- Impact: the to-do payload grows without bound (a `TodoOut` is ~300 B of JSON; a heavy user with 1,500 rows
  downloads ~450 KB in two pages) and is re-read on every app return, every checkbox tap and every reminder
  turn; each read is a full index scan of the user's rows server-side. Chat switching re-downloads a page that
  was just painted from disk. Unchanged data still costs full bodies because nothing is conditional.
- Fix: (1) To-dos: load open rows plus recently completed ones (e.g. 30 days) and page older completed rows
  when the Completed view asks; add `updated_since` (rows have `updated_at`) or an `ETag` on `/todos/page`;
  apply the mutation/confirm responses instead of a forced full reconcile (keep a reconcile only for recurring
  rows the server advances). (2) Chat open: reuse the 20 s rule (`shouldSkipSilentChatRefetch`) on the route
  path. (3) Add weak `ETag`s to `/todos/page`, `/chats`, `/chats/{id}/messages` (server) and send
  `If-None-Match` from `lib/api/client.ts` `request` for GETs (one seam). (4) Fix the class behind the
  foreground fan-out: the six `AppState` "active" listeners (`hooks/useNetworkStatus.ts:50-53`,
  `contexts/ModelsContext.tsx:125-137`, `features/home/context/HomeContext.tsx:116-123`,
  `features/todos/hooks/useTodosList.ts:116-122`, `features/chat/hooks/useChatRouteLoader.ts:268-326`,
  `lib/pushNotifications.ts:234-239`) each pick their own staleness (none / 20 s / 5 min / 12 h); one
  foreground coordinator with per-resource TTLs (minutes, not 20 s, for to-dos and the open chat, which
  the socket and push already keep current) would make a 30-second app switch cost nothing.
- Effort: M
- Verify: `features/todos/hooks/__tests__` — a toggle produces one PATCH and no `listTodos`; an A→B→A switch
  within 20 s produces one `listMessages` for A. Production: bytes per active user per day on `/todos/page`.

### NETM-09 — Request deadlines end when headers arrive; bodies, SSE streams and WebSockets have no idle deadline (Android has no transport timeout at all), and a stalled token refresh wedges every API call
- Severity: Medium
- Confidence: Medium (code paths certain; how often bodies stall in the field is unmeasured)
- Locations:
  - `apps/mobile/lib/api/client.ts:202-261` — the 30 s timer (`:213`) is cleared in `finally` (`:259`) when headers arrive; `request()` then reads the body with no deadline (`:178-179`). Same in `fetchWithTimeout` (`:82-95`): the refresh body `await response.json()` (`:116`) runs after its 15 s timer was cleared
  - `apps/mobile/lib/api/client.ts:97-135` single-flight refresh, awaited by every authenticated request (`:228`, `:245`, `:280`, `:288`) without racing the request's own timeout/abort signal
  - `apps/mobile/features/chat/model/sse.ts:79-91` — SSE body read loop, no idle deadline
  - `apps/mobile/features/chat/model/wsTransport.ts:179-181` — the first turn event clears the only deadline; no ping/idle check afterwards
  - transports: Android `expo/fetch` = RN OkHttp with connect/read/write timeouts 0 (`node_modules/expo/android/src/main/java/expo/modules/fetch/ExpoFetchModule.kt:26-31`, `node_modules/react-native/ReactAndroid/src/main/java/com/facebook/react/modules/network/OkHttpClientProvider.kt:49-54`); RN WebSocket read timeout disabled (`node_modules/react-native/ReactAndroid/src/main/java/com/facebook/react/modules/websocket/WebSocketModule.kt:89-91`); iOS sets `request.timeoutInterval = 0` (`node_modules/expo/ios/Fetch/ExpoURLSessionTask.swift:27`)
- Evidence:
  ```ts
  // lib/api/client.ts (requestRaw)
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  ...
  } finally {
    if (!streamingBodyReturned) externalSignal?.removeEventListener("abort", onExternalAbort);
    clearTimeout(timeout);          // runs as soon as headers arrive
  }
  // request(): the body is read afterwards, unguarded
  const data = response.status === 204 ? undefined : await response.json();
  ```
- Impact: on a half-open connection (network switch, captive portal re-login, NAT timeout) after headers:
  opening a chat keeps `chatLoading` true, and `features/chat/model/sendGuards.ts:21-25` silently blocks Send in
  that chat; a reply keeps its typing indicator until the user taps Stop (`features/chat/hooks/useStreamSilence.ts`
  only shows a hint after 20 s); a refresh whose body stalls leaves `refreshInFlight` pending forever, and since
  every request joins it, the whole app stops talking to the API until it is killed. The standards require
  "Handle timeouts, cancellation" (`docs/ENGINEERING_STANDARDS.md:104-105`).
- Fix: in `lib/api/client.ts` keep the deadline alive through the body: abort the controller on timeout until
  `request()` has parsed the body (move `clearTimeout` after `response.json()`/`text()`), and race
  `refreshAccessToken()` against the caller's signal/timeout (and give the refresh body the 15 s budget). For
  streams: an idle deadline per event (e.g. 45 s without any SSE line or WebSocket frame after `start`, which the
  server already exceeds only when broken — its provider idle limit is 30 s, `fly.toml:37` `CHAT_STREAM_TIMEOUT_SECONDS`),
  then run the existing dropped-turn reconcile. One seam each: `lib/api/client.ts`, `features/chat/model/sse.ts`,
  `features/chat/model/wsTransport.ts`.
- Effort: S
- Verify: client tests with a `fetch` mock whose `json()` never resolves → `request()` rejects after `timeoutMs`;
  a refresh whose body hangs → queued requests reject, the next request starts a new refresh; SSE/WS tests with a
  silent stream → reconcile starts after the idle deadline.

### NETM-10 — Opening a search hit deep in a long chat pages backwards 40 messages at a time until the hit is loaded
- Severity: Medium
- Confidence: High
- Locations:
  - `apps/mobile/features/chat/hooks/useChatHighlightScroll.ts:79-112` (effect re-runs after each page, `:100-110`, until the hit is found or `hasMoreOlder` is false; no cap)
  - `apps/mobile/features/chat/hooks/useChatRouteLoader.ts:461-499` (`loadOlderMessages`, `MESSAGE_PAGE_SIZE` = 40, `features/chat/model/constants.ts:2`)
  - entry: `apps/mobile/components/ConversationList.tsx:166-171` (`openChat(id, messageId)` from a drawer search result)
  - server supports only `limit` (≤200) and `before` (`apps/api/app/modules/chat/api.py:180-195`)
- Evidence:
  ```ts
  // useChatHighlightScroll.ts
  const cursor = messages[0].id;
  if (!hasMoreOlder || chatLoading || loadingOlder || request.loading || request.cursor === cursor) return;
  ...
  try { await loadOlderMessages(); }
  finally { ...setPageRevision((value) => value + 1); }   // re-runs the effect → next page
  ```
- Impact: a hit 1,000 messages back is 25 sequential round trips (several seconds of waiting on mobile
  latency) and downloads every message in between (often 1-3 MB of reply text, fences and simulation JSON) —
  exactly for the power users with long tutoring threads who use search most.
- Fix: server `GET /chats/{id}/messages?around={message_id}&limit=40` (window plus `has_more` both ways) and a
  list model that can hold one gap; or, as a stopgap, page with `limit=200` while seeking (5× fewer round trips).
- Effort: M (around-window) / S (stopgap)
- Verify: `features/chat/hooks/__tests__/useChatHighlightScroll.test.tsx`: a hit 1,000 messages back → ≤2
  requests; server test for `around`.

### NETM-11 — Follow-up reads where the response or a shared cache already has the data
- Severity: Low
- Confidence: High
- Locations:
  - `apps/mobile/hooks/useSubscriptionActions.ts:9-14` — `api.syncSubscription` already returns the updated `User` (`features/account/api.ts:32-33`), then `refreshUser()` sends `GET /auth/me` (`contexts/AuthContext.tsx:250-258`); same for `devUpgrade` (`:16-24`)
  - `apps/mobile/features/account/screens/ArchivedChatsScreen.tsx:20-23` with `features/account/hooks/useFocusedList.ts:27-31` — every focus downloads the full `GET /chats` (≤200 active + ≤50 archived) to show the archived part, bypassing `lib/cache/chatListCache.ts`, which already holds `archived`; rows past 50 are unreachable (`apps/api/app/modules/chat/service.py:35`)
  - `apps/mobile/features/chat/hooks/useQuotaNudge.ts:49` calls `api.todayUsage` directly while Settings → Usage goes through `lib/cache/usageCache.ts:5-24` (20 s, in-flight dedupe); that cache is keyed by bearer token, so every rotation is a miss (HomeContext learned to key by account, `features/home/context/HomeContext.tsx:34-37`)
  - reminder-card confirm ignores the `items` it gets back (`features/todos/hooks/useReminderProposal.ts:27-30`) — counted in NETM-08
- Evidence:
  ```ts
  const syncSubscription = async () => {
    if (!token) return false;
    await api.syncSubscription(token);   // returns User
    await refreshUser();                 // GET /auth/me again
  ```
- Impact: small per event (one extra round trip on purchase/restore, settings visits, nudge refreshes), but each
  is a second authenticated request for data already in hand; the token-keyed usage cache defeats its own dedupe.
- Fix: `setCurrentUser(await api.syncSubscription(token))` via a `mergeUser`-style setter; read archived rows
  through `fetchChatList` (or a dedicated `GET /chats/archived?cursor=` that pages); route the nudge through
  `fetchTodayUsage` and key `usageCache` by user id.
- Effort: S
- Verify: hook tests asserting one request per action (`hooks/__tests__`), and that a token rotation hits the usage cache.

### NETM-12 — The push token is registered again on every cold start (the 12 h freshness lives in module memory)
- Severity: Low
- Confidence: High
- Locations:
  - `apps/mobile/lib/pushNotifications.ts:181-191` (`lastPushSync` is a module variable keyed by session generation, which restarts at 0 each process), `:200-240` (`sync()` on attach), `:123-146` (`getExpoPushTokenAsync` at `:101` — a call to Expo's push service — then `POST /users/push-token` at `:142`)
  - trigger: `apps/mobile/hooks/useBootstrapSync.ts:63-91` (once per process after sign-in)
  - server: `apps/api/app/repositories/push_tokens.py:38` (`upsert`, a DB write per call)
- Evidence: `git show fce17eb0d` fixed the per-return and per-token-refresh re-registration ("once per sign-in"), but
  "sign-in" here is one process: iOS and Android kill backgrounded apps routinely, so most launches are cold.
- Impact: one Expo round trip and one DB upsert per cold start per user (several per day each), for a token that
  almost never changes.
- Fix: persist `{ userId, expoToken, enabled, at }` (AsyncStorage) after a successful sync and skip within 12 h
  unless the permission or the setting changed; keep the cheap local permission check.
- Effort: S
- Verify: `lib/__tests__` push sync test: two simulated cold starts (module reset, persisted record) → one
  `registerPushToken` call.

### NETM-13 — Link previews: no in-flight dedupe, failures are never remembered, no cancellation
- Severity: Low
- Confidence: High
- Locations:
  - `apps/mobile/lib/linkPreview.ts:11-33` — success-only `Map` (`:11,19-20,31`); a non-OK response throws and is retried on the next mount (`:29`); no `AbortSignal` (`:25-28`); a SecureStore read per call through the serialized storage queue (`:24` → `lib/auth.ts:104-107`)
  - `apps/mobile/components/LinkPreviewCard.tsx:26-41` — one fetch per mount; FlashList recycling and the streaming-row → final-row swap remount cards
  - server: results (including empty ones) are cached in Redis (`apps/api/app/modules/link_preview/service.py:176-205`) and every request, cached or not, passes a per-user rate limit first (`apps/api/app/modules/link_preview/api.py:30-50`, 429; also 429 + `Retry-After` when the user's fetch slots are busy, which the phone ignores)
- Evidence:
  ```ts
  const cached = cache.get(url);
  if (cached) return cached;
  const token = await getToken();
  const res = await requestRaw(`/link-preview?url=${encodeURIComponent(url)}`, token);
  if (!res.ok) throw new Error("preview failed");   // not remembered: every remount asks again
  ```
- Impact: two cards for one URL (same link twice, or a remount while the first is in flight) send two requests;
  a 429 or 4xx is retried on every scroll past the card, keeping the user at the rate limit. Small, bounded
  by the server cache.
- Fix: store the in-flight promise in the map; remember failures for the session (or a few minutes); pass the
  card's `AbortSignal` (abort on unmount, the server cache keeps the result anyway); take the token from
  `useAuthToken()` instead of SecureStore.
- Effort: S
- Verify: `lib/__tests__/linkPreview.test.ts`: two concurrent calls → one request; a 429 → no second request on remount.

---

## 4. Looked wrong, actually fine

- **Drawer search**: debounced 300 ms, 2-character minimum, aborts the previous request, pages of 20
  (`apps/mobile/features/search/model/drawerSearchLogic.ts:3-5`, `features/search/hooks/useDrawerSearch.ts:88-124`).
- **Attachment indexing status**: one shared poller per attachment, backoff ×1.5 from 2 s to 15 s, 6-minute cap,
  pauses offline and when nothing on screen shows it, resumes on reconnect
  (`apps/mobile/features/attachments/model/attachmentIndexStatus.ts:18-23,87-140`). Old files settle on the first answer.
- **Images**: every remote image uses `expo-image` with `cachePolicy="memory-disk"`; no React Native `Image` loads a
  remote URI. Chat and gallery thumbnails ask the server for a resized copy (`?w=`, `components/ChatMessageImage.tsx:134-147`,
  `features/attachments/components/GalleryThumbnail.tsx:47-51`).
- **Attachment downloads** (viewer, PDF cards, share): in-flight dedupe with waiter counting, native download straight
  to disk, disk cache 7 days / 200 MB swept once per run (`features/attachments/model/downloadChatAttachment.ts:21-35,129-170,204-231`,
  `attachmentFileStore.ts:9-11,89-103`). PDF cards download the whole PDF for a page-1 preview, but once per week per
  device; a server-side page-1 thumbnail would only save that first download (optional).
- **Uploads**: `new File(…).arrayBuffer()` + `fetch(PUT)` (`features/attachments/model/attachments.ts:313-316`,
  `features/attachments/api.ts:96-127`) looked like React Native's base64 bridge path
  (`node_modules/react-native/Libraries/Network/convertRequestBody.js:38-41`), but Expo SDK 57's global `fetch` is
  `expo/fetch`, which hands the bytes to native as a `Uint8Array` (`node_modules/expo/src/winter/fetch/RequestUtils.ts`
  `normalizeBodyInitAsync`). Remaining cost: up to 10 MB held in the JS heap once; images are first resized to 2048 px
  and re-encoded (`features/attachments/model/attachmentPrep.ts:66-80`). If `EXPO_PUBLIC_USE_RN_FETCH` is ever set,
  this becomes a real JS-thread base64 stall.
- **Image-intent pre-check** (`POST /images/intent`): asked only when the prefilter matches (~19% of sends per ES-05),
  3 s timeout, any failure = plain send (`features/images/model/imageIntentPrefilter.ts:76-83`, `features/images/api.ts:29-30,55-66`,
  `features/images/model/imageGenTurn.ts:21-44`). A serial round trip before those sends, but measured and documented (ES-05).
- **Retries and reconnects**: the network layer has no retry loops; only one 401 → refresh → retry
  (`lib/api/client.ts:243-251`). The WebSocket never reconnects in a loop: only on a send, a return to the app or a chat
  open; 4408/1001/1012 reconnect on the next send, other closes fall back to SSE (`features/chat/model/wsTransport.ts:30-39,153-166`).
  So a deploy causes no reconnect storm (the dropped-turn polling in NETM-06 is the only burst).
- **Cold-start 401 storm**: fixed in `d85a7faa5` — requests join the single-flight refresh before leaving the device when
  the JWT is already expired (`lib/api/client.ts:222-232`).
- **ES-17 caches**: intact; `lib/cache/sessionResource.ts:172-201` joins in-flight reads, honours freshness and reports
  failures once. Drawer list, memory list/documents and gallery use it. No regression found.
- **Drawer list**: one idle prefetch at start, then opening the drawer paints from cache without a read; pull-to-refresh
  forces (`lib/drawerChatList.ts:13-31`, `hooks/useDrawerChatList.ts:120-137`).
- **Per keystroke / per token**: composer drafts are in memory (`contexts/ComposerDraftContext.tsx`), email-card edits are
  persisted with a 600 ms debounce (`features/drafts/hooks/useEmailCardPersist.ts:9,48-50`), and the streaming bubble is
  published once per animation frame (`features/chat/hooks/useChat.ts:115-136`). No request per keystroke or per streamed token.
- **Share / export** loads every message (100 per page), but only on an explicit tap
  (`features/chat/hooks/useChatActions.ts:133-140`, `useChatMenuActions.ts:84-90`).
- **Charts and diagrams**: Vega, Mermaid, pdf.js and SMILES are inlined (`lib/vendor/*.ts`); only user "HTML Run" previews
  may load CDN scripts (`lib/htmlRunCdn.ts`).
- **Local reminder sync** after each to-do refresh is versioned and skips unchanged rows
  (`features/todos/model/todoReminders.ts:31,70-95`).
- **Push sync on return to the app**: deduplicated to 12 h within a process since `fce17eb0d` (cold starts: NETM-12).

## 5. Open questions for the team

1. **Response compression.** No `GZipMiddleware` (or other compression) in `apps/api/app/main.py`; `expo/fetch` accepts
   gzip on both platforms (`node_modules/expo/android/src/main/java/expo/modules/fetch/TransparentCompressionInterceptor.kt`).
   Does Fly's proxy compress? If not, `/chats` (~250 rows), 40-message pages and the to-do list travel as plain JSON
   (typically 5-10× larger than gzip). Backend I/O agent to confirm.
2. **Fly socket accounting** (`docs/PRODUCTION.md:205-213`): if every open chat WebSocket counts against
   `hard_limit = 200`, NETM-05's view-time sockets set the Machine count. Has the load test been run?
3. **RevenueCat on launch.** `registerPlanChangeListener` treats the first CustomerInfo event in a process as a change
   (`lastPlan` starts `null`, `lib/purchases.ts:203-218`) and posts `/auth/me/sync-subscription`, which calls RevenueCat's
   REST API server-side (`apps/api/app/modules/billing/subscription.py:72`). Whether the native SDK delivers such an event
   to the JS listener on every launch depends on SDK timing and could not be settled by reading code; a staging log
   line would answer it. If yes, that is one RevenueCat REST call per launch per user.
4. **Drawer payload.** `GET /chats` returns up to 200 active + 50 archived rows at every start
   (`apps/api/app/modules/chat/service.py:34-35`). Would a first page of ~50 plus "load more" do?
5. **Eager socket benefit.** Is there `chat_ttft` data comparing a socket opened at view time with one opened on composer
   focus (NETM-05)?
6. **Greeting language.** The server's `/home` greeting is English-only while the phone's `localGreeting` is translated —
   intended? (NETM-02 proposes dropping the request.)
7. **Telemetry sampling.** Are `chat_ttft` / `chat_turn_outcome` meant to cover 100% of production turns (NETM-07)?
