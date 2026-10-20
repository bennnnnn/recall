# Dimension C — Resource leaks and lifecycle (agent-leak)

Audited: worktree `/home/user/recall-audit` at `d2ec42b0`. Read-only. Paths are repo-relative.
Library versions read from `apps/api/uv.lock` and the installed venv: FastAPI 0.142.2, Starlette 1.3.1,
SQLAlchemy 2.1.0, redis-py 8.1.0, uvicorn 0.54.0; phone: expo-audio 57.0.5, react-native-webrtc 124.0.8,
react-native-reanimated 4.5.1, @shopify/flash-list 2.3.2.

Scratch scripts (source parsing only): `tmp/code-audit/raw/scratch-leak/session_awaits.py` (every
`async with SessionLocal()/session_factory()` block and the awaits inside it),
`module_state.py` (module-level mutable containers), `effect_cleanup.js` (phone effects that register
listeners/timers without returning a cleanup — it found only two harmless single-frame
`requestAnimationFrame` calls).

---

### LEAK-01 — A pooled Postgres connection is held (open read transaction) across R2 I/O, a semaphore wait, an LLM call and 20 s of waiting

- Severity: High
- Confidence: High
- Locations (one pattern; the first is the hot path):
  - `apps/api/app/modules/attachments/api.py:175-201` (`GET /attachments/{id}/file?w=`, every chat image and gallery tile) → `apps/api/app/modules/attachments/workflow.py:68` (`_verified_row`: `SELECT` on the request session, transaction stays open) → `apps/api/app/modules/attachments/workflow.py:295-299` → `apps/api/app/modules/attachments/thumbnails.py:103-122` (R2 GET of the thumb; on a miss: wait on the process-wide semaphore of **2** (`apps/api/app/core/settings/attachments.py:37`), R2 GET of the original (≤10 MB), PIL resize on a thread, R2 PUT). The connection goes back to the pool only when FastAPI closes the request session after the response is sent.
  - `apps/api/app/modules/attachments/workflow.py:257-272` (`POST /attachments/{id}/confirm`) and `workflow.py:72-82` (first view of an unverified row) → `apps/api/app/modules/attachments/content.py:321-335`: R2 download + magic-byte check of the whole object inside the open read transaction.
  - `apps/api/app/modules/chat/service.py:216-219` (`GET /chats/{id}/messages`): `get_chat` runs a `SELECT` (opens the transaction), then `wait_for_inflight_stream` (up to 10 s) and `wait_for_pending_finalize` (up to 10 s, `apps/api/app/modules/chat/finalize_registry.py:40`) run with the connection checked out. The finalize it waits for needs its own pool connection (`apps/api/app/modules/chat/turn_settle.py:294`). `set_message_feedback` and `update_message_email` (`apps/api/app/modules/chat/service.py:281-285`, `:303-307`) do the same when the message is not saved yet. The turn path does this correctly (`apps/api/app/modules/chat/turn_load.py:187`, `:303`: wait first, then open a session).
  - `apps/api/app/modules/chat/compaction.py:37-89` (`compress` job, `history_compression_enabled` defaults on): four `SELECT`s, then `summarize_conversation` → `complete_text` (LLM, `background_llm_timeout_seconds` 60 s, plus a fallback model: up to ~120 s) inside the same `async with SessionLocal()`, then `commit`.
  - `apps/api/app/modules/images/search.py:246-293` with `:160-180`: `_store_photos` flushes an `INSERT` for photo 1, then does the R2 `put_object` for photos 2 and 3 inside that transaction (`image_search_max_results` 3).
  - `apps/api/app/modules/attachments/reuse.py:31-54` (called from `apps/api/app/modules/chat/turn_prep/attachments.py:175-199`, the chat critical path): R2 `copy_object` per linked Library file inside the session that already ran `get_by_ids`.
  - `apps/api/app/modules/billing/subscription.py:143-180` (RevenueCat TRANSFER webhook): `users_repo.update` commits then `refresh`es (new transaction, `apps/api/app/repositories/users.py:104-106`), then RevenueCat HTTP calls run for each source id. Rare path.
- Evidence:
  ```python
  # modules/attachments/workflow.py:295-299
  row, gateway = await _verified_row(session, settings, user, attachment_id)   # SELECT, tx open
  edge = thumbnail_edge(width)
  if edge is not None and is_image_content_type(row.content_type):
      try:
          thumb = await thumbnail_bytes(gateway, settings, row.storage_key, edge)  # R2 + semaphore + resize + R2
  ```
  ```python
  # modules/chat/service.py:216-219
  chat = await get_chat(session, user, chat_id)                      # SELECT, tx open
  await finalize_registry.wait_for_inflight_stream(chat_id)          # ≤10 s
  await finalize_registry.wait_for_pending_finalize(chat_id, redis)  # ≤10 s
  msgs, has_more = await messages_repo.list_page(session, chat_id, ...)
  ```
  ```python
  # modules/chat/compaction.py:84-89
  new_summary = await summarize_conversation(settings, chat.summary, transcript)  # LLM, session open
  ...
  await session.commit()
  ```
  The scanner output (`scratch-leak/session_awaits.txt`) lists every session block; these are the ones whose body awaits network I/O or a wait.
- Impact: CLAUDE.md ("Slow provider calls should run outside an open DB transaction") and SCALING.md's pool budget (20 + 10 per process, `pool_timeout` 5 s) assume a checkout lasts a query. A Library page or a chat with images fires one `?w=` request per tile (the phone builds `?w=` URLs in `apps/mobile/features/attachments/model/attachmentUri.ts:29-58`, and an image fetcher runs several at once per phone). Every new image's first view is a cold thumbnail; cold ones queue two at a time per machine on the semaphore while **each waiting request holds a connection**, so a handful of users opening a gallery or an image-heavy chat on one machine can take all 30 connections for seconds, and every other request there (chat turns included, they use the same engine) fails after the 5 s pool timeout. Through Neon's transaction-mode pooler an idle-in-transaction client also pins a server connection, so the effect crosses machines. `GET /messages` during a stream holds a connection for up to 20 s while the finalize it waits for competes for the same pool.
- Fix: end the read transaction before slow work. In `get_file_access`/`confirm_upload`, take what is needed from the row and `await session.commit()` (expire_on_commit=False keeps it loaded) — or read the row in a short `async with SessionLocal()` — before any storage call; write `verified_at` in its own short session after the check. In `list_messages_page`, commit after the ownership check, then wait, then list. In compaction, read in one session, call the model with none open, write in a second (re-check `summary_message_count` under the existing Redis lock). In `_store_photos`, upload all bytes first, then insert the rows. In `ensure_unlinked_copies`, copy first, then insert the clones. Seams: `modules/attachments/workflow.py`, `modules/chat/service.py`, `modules/chat/compaction.py`. Add a lint/test guard: `session_awaits.py`-style AST check that a session block awaits nothing from `gateways/` or a finalize wait.
- Effort: M
- Verify: a test that drives `GET /attachments/{id}/file?w=` with a storage fake that blocks, and asserts `engine.pool.checkedout()` is 0 while it blocks; same for `list_messages_page` with a pending finalize task, and for `compress_chat_history` with a blocking `summarize_conversation`. In production, Neon `pg_stat_activity` `state = 'idle in transaction'` count and SQLAlchemy pool checkout time (p99) per route.

### LEAK-02 — The auth dependency's request-scoped session pins a pooled connection for the whole request on a user-cache miss — across SSE chat streams (600 s cap), image generation, TTS streaming and export

- Severity: Medium
- Confidence: High
- Locations:
  - `apps/api/app/core/deps.py:37-62` (`get_current_user` depends on `get_db`; on a miss `users_repo.get_by_id` → `session.get` runs a `SELECT`, `apps/api/app/repositories/users.py:22-23`, and nothing ends that transaction)
  - `apps/api/app/core/db.py:46-48` (`get_db`: a plain `yield` dependency → FastAPI "request" scope)
  - `apps/api/app/modules/account/consent.py:39-50` (`get_consented_user`: `session.refresh(...)` on a cached row without consent, same effect)
  - Streaming routes that inherit it: `apps/api/app/modules/chat/stream_api.py:262-326` (both SSE routes; `require_chat_rate_limit` at `:59` also depends on it), `apps/api/app/modules/speech/api.py:163-205` (`/speech/tts/stream`), `apps/api/app/modules/account/api.py:438-444` (`/auth/me/export`)
  - Slow non-streaming routes: `apps/api/app/modules/images/api.py:22` (image generation, `_GENERATE_TIMEOUT` 120 s + 60 s download, `apps/api/app/gateways/image_gateway.py:18-21`), `apps/api/app/modules/memory/api.py:103-143` (LLM), `apps/api/app/modules/math/api.py:33` and the physics/chemistry scan reads (vision model), `/speech/transcribe`, `/link-preview`, `/speech/live/*`, `/auth/me/sync-subscription`.
- Evidence:
  ```python
  # core/deps.py:51-62
  cached = user_cache.cached_user(user_id)
  if isinstance(cached, User):
      return await session.merge(cached, load=False)   # no SQL: no connection
  ...
  user = await users_repo.get_by_id(session, user_id)  # SELECT: connection checked out, tx left open
  user_cache.remember_user(user)
  return user
  ```
  The export shows the intent this defeats: `apps/api/app/modules/account/export.py:258-259` "Open a session per repository call and close it before yielding so a slow client download cannot pin a Neon connection for the stream lifetime" — yet the route's own auth session, on a miss, does exactly that.
  FastAPI 0.142.2 (`fastapi/routing.py:147-153` in the venv) closes "request"-scoped `yield` dependencies only after `await response(scope, receive, send)` returns, i.e. after the last byte of a `StreamingResponse`; `get_db` has no `scope=` (`fastapi/dependencies/models.py:229-234` computes "request").
- Impact: the cache is per machine and expires 60 s after the row was cached (`apps/api/app/core/user_cache.py:24`), and a user's requests spread over N machines, so misses are routine. Every SSE turn (phone fallback; `apps/web`'s only transport) that starts on a miss keeps one connection idle in transaction for the whole turn (`chat_stream_max_seconds` 600, `apps/api/app/core/settings/llm.py:50`), on top of the connections the turn itself checks out. Image generation holds one for up to ~3 min. This compounds LEAK-01 against the same 30-connection pool and Neon's server pool.
- Fix: in `get_current_user`, end the read before returning on a miss (`await session.commit()` — `expire_on_commit=False`, `core/db.py:37`, keeps the row loaded; or load the user in a short `async with SessionLocal()` and `merge(load=False)` it into the request session as the cache-hit path already does). Same for the consent refresh. For the streaming routes, also give them a function-scoped session (`Depends(get_db, scope="function")`) or no session at all, since the stream opens its own short sessions. Seam: `core/deps.py` (one place covers every route).
- Effort: S
- Verify: test that a `get_current_user` miss leaves `session.in_transaction()` False / `engine.pool.checkedout()` 0 after the dependency returns; an SSE test that asserts no checked-out connection while the fake stream is parked. Production: pool checkout duration by route.

### LEAK-03 — Timed-out `asyncio.to_thread` work keeps running: orphaned parse/render/search threads stack up (retries add more) on a 5-thread default executor

- Severity: Medium
- Confidence: High (mechanism); Medium (how often real files hit it)
- Locations:
  - `apps/api/app/modules/attachments/content.py:205-215` — `asyncio.timeout` around `asyncio.to_thread(extract_text_details, ...)` (pure-Python pypdf/python-docx parse; chat-turn budget 5 s from `apps/api/app/modules/attachments/content.py:377`, index budget 60 s). The docstring says "same pattern as the SymPy math solve offload", but `core/sympy_executor.py:8-12` exists precisely because a thread cannot be killed.
  - `apps/api/app/modules/attachments/rag.py:156-178` — on that timeout the index job raises `AttachmentIndexError`, which `core/jobs/worker.py:131-173` retries 3 times: each attempt downloads the file again and starts **another** parse thread while the earlier ones are still running (up to 3 per bad PDF, 500-page limit, `content.py:41-42`), on the 512 MB worker where `attachment_index` has no `max_running` (`apps/api/app/background/handlers.py:314`).
  - `apps/api/app/modules/attachments/ocr.py:198-206` — PDF page rendering under a 30/120 s timeout; the render thread outlives it.
  - `apps/api/app/gateways/web_search_gateway.py:137-150` — `wait_for(to_thread(_search_duckduckgo_sync), 8 s)`; the thread runs up to three sequential DDG calls of 8 s each (`:115-128`) after the caller gave up.
  - `apps/api/app/gateways/storage_gateway.py:196-320` — every R2 call is a boto3 call on a default-executor thread with no outer deadline; botocore allows 5 s connect + 20 s read × 3 attempts (`apps/api/app/core/settings/attachments.py:83-85`), and a cancelled request (client gone, Stop) does not stop it.
  - Nothing sizes the default executor (no `loop.set_default_executor` anywhere), so on Fly's 1-vCPU machines it is `min(32, cpu_count + 4)` = 5 threads, shared by R2 reads/writes/presigns, thumbnail resizes, parsing, OCR renders, Google sign-in verification (`apps/api/app/gateways/google_auth.py:106-108`) and DDG.
- Evidence:
  ```python
  # modules/attachments/content.py:206-214
  try:
      async with asyncio.timeout(timeout_seconds or settings.attachment_extract_timeout_seconds):
          details = await asyncio.to_thread(
              extract_text_details, content_type, data, max_chars=max_chars
          )
  except TimeoutError as exc:
      ...
      if raise_on_timeout:
          raise ExtractTimeoutError(content_type) from exc   # job retried; the thread keeps parsing
  ```
- Impact: a few slow or hostile PDFs (a user can attach them to chat sends at 30 messages/min) leave threads parsing after the turn moved on. Five of them fill the default executor, after which every `to_thread` caller on that machine queues: presigned upload/download URLs, thumbnails, sign-in, R2 reads in turn prep. A CPU-bound pure-Python parse also holds the GIL, slowing the one event loop that serves every socket on the machine. On the worker, retries multiply the threads and their 10 MB inputs plus parse state, which risks an OOM restart on 512 MB.
- Fix: run the CPU-bound parsers where they can be killed — through the same bounded process pool as SymPy (`BoundedSympyExecutor` is already the seam SCALING.md item 9 names) or a second instance of it for documents; then a timeout really ends the work. Mark an extraction timeout as non-retryable (`JobDiscardError`, or record the timeout and skip on redelivery) so retries cannot stack. Give blocking I/O its own bounded `ThreadPoolExecutor` (R2) instead of the default one, and give each boto3 call an overall deadline smaller than its retry budget. Seams: `modules/attachments/content.py`, `modules/attachments/ocr.py`, `gateways/storage_gateway.py`, `core/sympy_executor.py`.
- Effort: M
- Verify: a test with an extractor stub that sleeps past the timeout and checks (a) the job is not retried, (b) with a process pool the child is gone after the timeout. Production: a gauge of default-executor queue depth / active threads (`loop._default_executor._work_queue.qsize()`), worker RSS.

### LEAK-04 — Phone: every voice-input recording stays on disk forever, and sign-out does not remove them

- Severity: Medium
- Confidence: High
- Locations:
  - `apps/mobile/lib/speech/voiceAudio.ts:162-226` (`startVoiceRecording` creates `new AudioModule.AudioRecorder({})`; `stop()` returns `recorder.uri`; nothing deletes the file or calls `recorder.release()`)
  - `apps/mobile/features/speech/hooks/useVoiceInput.ts:136-176` (`finishRecording`: uploads it and drops the URI; the empty-recording, cancel, unmount and error paths at `:105-107`, `:143-146`, `:180-186`, `:208-225` also leave the file)
  - `apps/mobile/features/speech/api.ts:68-101` (`transcribeSpeech` reads it as base64; no delete)
  - `apps/mobile/lib/accountFiles.ts:8-15`, `:31-42` and `apps/mobile/lib/signOutCleanup.ts:14-40` (the sign-out sweep only knows `recall-export-`, `recall-preview-`, `recall-tts-` and `Print/*.pdf`)
  - Where expo-audio writes them: iOS `Caches/ExpoAudio/recording-<uuid>.m4a` (`node_modules/expo-audio/ios/AudioUtils.swift:166-170`), Android `cache/Audio/recording-<uuid>.m4a` (`node_modules/expo-audio/android/.../AudioRecorder.kt:240-252`); expo-audio never deletes them.
- Evidence:
  ```ts
  // lib/speech/voiceAudio.ts:211-215
  const rawUri = recorder.uri;
  if (!rawUri) return null;
  const uri = normalizeRecordingUri(rawUri);
  const size = await waitForRecordingFile(uri);
  ```
  `grep -rn "deleteAsync" apps/mobile/{lib,features}` shows deletes for TTS clips, scans, attachments, exports and the chat cache, none for recordings. Compare the care taken elsewhere: attachment copies are swept to 200 MB / 7 days (`apps/mobile/features/attachments/model/attachmentFileStore.ts:8-11`, `:89-103`), scan files are tracked and discarded (`apps/mobile/lib/scanner/scanImage.ts:79-104`), TTS clips are deleted after playback (`apps/mobile/features/speech/model/pronunciation.ts:258-270`).
- Impact: up to 45 s per note (`VOICE_MAX_RECORDING_MS`, `voiceAudio.ts:128`) at expo's HIGH_QUALITY preset (`voiceAudio.ts:172`) — a few hundred KB each, every mic tap including cancelled ones — accumulating until the OS purges caches under storage pressure. The bigger problem is the contract: `clearSignedOutAccount` promises "it starts with nothing of this one" and `lib/__tests__/accountState.test.ts` only guards JS module-level stores, so raw recordings of the user's voice outlive sign-out and account deletion on the device.
- Fix: delete the recording in `useVoiceInput` once transcription settles (success or failure) and on every discard path (`deleteAsync(uri, { idempotent: true })`), call `recorder.release()` after `stop()`, and add the recordings directory (`${cacheDirectory}ExpoAudio/` and `Audio/`) to `deleteAccountFiles`. Or pass a known directory/prefix through `RecordingOptions` and list it in `ACCOUNT_FILE_PREFIX`. Seam: `lib/speech/voiceAudio.ts` (it already owns start/stop).
- Effort: S
- Verify: a unit test that `finishRecording` and `cancelVoiceInput` delete the URI (mock `expo-file-system/legacy`), and an `accountFiles` test that a `recording-*.m4a` in the recordings directory is removed by `deleteAccountFiles`.

### LEAK-05 — Phone: Live Talk never releases its WebRTC local stream; native stream/track objects accumulate per session

- Severity: Low
- Confidence: Medium (leak is certain; its size is small)
- Locations: `apps/mobile/features/speech/model/realtimePeer.ts:352-363` (`close`: `track.stop()` + `pc.close()`, no `stream.release()`), `:181` (the no-audio-track path), `apps/mobile/features/speech/model/realtimeVoice.ts:98-164` (a failed connect tears down the same way).
- Evidence: in react-native-webrtc 124.0.8, `MediaStreamTrack.stop()` only sets `enabled = false` and `readyState = 'ended'` (`node_modules/react-native-webrtc/src/MediaStreamTrack.ts:123-126`); the native objects leave `localStreams` / `localTracks` only through `MediaStream.release()` → `mediaStreamRelease` / `mediaStreamTrackRelease` (`src/MediaStream.ts:156-168`; `ios/RCTWebRTC/WebRTCModule+RTCMediaStream.m:395-414`, where release also calls `stopCapture`).
- Impact: each Live Talk session (and each failed connect) leaves one RTCMediaStream, RTCAudioTrack and its audio source in WebRTCModule's dictionaries until the app process dies. Small per session, unbounded per app run for heavy Pro users.
- Fix: call `localStream.release()` (releases tracks too) after `pc.close()` in `close()` and in the no-audio-track branch of `openRealtimeMicrophone`. Seam: `realtimePeer.ts`.
- Effort: S
- Verify: a session test with the WebRTC mock asserting `release` is called once on close and on a connect failure.

### LEAK-06 — `asyncio.gather` without cancelling siblings: when one branch raises, the others (paid model calls, Tavily searches) keep running detached

- Severity: Low
- Confidence: High
- Locations: the team already fixed this once — `apps/api/app/modules/chat/turn_prep/augment.py:265-275` (`_gather_or_cancel`: "gather does not cancel siblings when one fetch raises. Own all Phase B work so paid classification cannot outlive failed prep"). The same plain `gather` remains at `apps/api/app/modules/chat/prompt_builder.py:144-156` (web search beside the subject augmentation), `apps/api/app/modules/chat/tool_loop/forced_search.py:105-115` and `:131-138` (query writing; Tavily searches), `apps/api/app/modules/chat/tool_loop/parts.py:73` (one classifier call per part), `apps/api/app/modules/chat/prompt_context.py:189`, `:208`, `:233`, `apps/api/app/modules/chat/turn_load.py:162`, `:238`, `:249`, `apps/api/app/modules/chat/turn_prep/context.py:345`, `apps/api/app/modules/chat/turn_prep/attachments.py:222`, `:270`.
- Evidence: `asyncio.gather(*aws)` with `return_exceptions=False` propagates the first exception and leaves the other children running (Python docs); `_gather_or_cancel` is the house fix.
- Impact: a failed turn still pays for and runs the sibling provider calls; each also keeps its own short DB session or Redis call going after the turn has answered with an error. Bounded by provider timeouts, so contained.
- Fix: move `_gather_or_cancel` to a shared helper (e.g. `core/` or `modules/chat/`) and use it at these sites, or `asyncio.TaskGroup` (cancels siblings on the first failure). Seam: one helper.
- Effort: S
- Verify: a test where one branch raises and the other awaits an event; assert the other is cancelled.

### LEAK-07 — Sign-out never releases the device's push registration: the server keeps sending the signed-out account's reminders (to-do text) to the phone

- Severity: Medium
- Confidence: High
- Locations:
  - `apps/mobile/contexts/AuthContext.tsx:177-207` (`signOut`: clears credentials and local stores, then `logoutSession(accessToken, refresh)`; no push unregister)
  - `apps/mobile/lib/signOutCleanup.ts:14-40` (cancels *local* reminders with `cancelAllTodoReminders`, not the server binding)
  - `apps/mobile/lib/pushNotifications.ts:158-171`, `:209-224` (`unregisterRemotePushToken` runs only when the push preference is off) and `apps/mobile/features/account/hooks/usePushNotificationToggle.ts:86`
  - `apps/api/app/modules/account/lifecycle.py:89-104` (`logout` revokes tokens only) and `apps/api/app/models/schemas/auth.py:260-261` (`LogoutRequest` carries no device or push token)
  - `apps/api/app/repositories/push_tokens.py:38-105` (the row moves only when another account signs in on the same install, `:66-91`)
  - Delivery: `apps/api/app/modules/notifications/push.py:299-305` (`title=reminder_title(...)`, `body=todo.content`)
- Evidence:
  ```ts
  // contexts/AuthContext.tsx:204-206
  if (accessToken) {
    void refreshToken.then((refresh) => logoutSession(accessToken, refresh)).catch(() => {});
  }
  ```
  `grep -rn unregisterRemotePushToken apps/mobile/{lib,features,contexts}` → only the preference toggle and the foreground sync when push is disabled.
- Impact: the push token is a session-scoped resource whose server row outlives the session. After a sign-out (shared tablet, handing a phone on, a "sign out of all devices" from another device: `purge_user_sessions` also leaves every device's row), the push scheduler keeps delivering that account's reminder text to the lock screen until another account signs in on the same install or Expo invalidates the token. It contradicts the sign-out contract in `lib/signOutCleanup.ts:10-13`, and costs Expo sends for users with no live session.
- Fix: phone — call `DELETE /users/push-token` (best-effort, with the still-valid access token) before `logoutSession`. Server — make it not depend on the phone: accept the push token (or device id) on `/auth/logout` and delete that row; on `purge_user_sessions` / logout-all / refresh-family revoke, delete the user's push rows (or store the refresh `session_id` on the push row and delete rows whose session is revoked). Seams: `modules/account/lifecycle.py`, `repositories/push_tokens.py`, `contexts/AuthContext.tsx`.
- Effort: S
- Verify: API test: register a token, log out, assert the row is gone (and that `collect_push_outbound` sends nothing for that user); phone test: `signOut` calls `unregisterPushToken` before `logoutSession`.

### LEAK-08 — Phone caches that grow for the life of the install or session with no size or age bound

- Severity: Low
- Confidence: High
- Locations:
  - `apps/mobile/features/chat/model/messageCache.ts:19`, `:74-92` — one `chat-pages/<chatId>.json` (a 40-message page, `features/chat/model/constants.ts:2`) per chat ever opened; removed only on chat delete or sign-out (`:112-129`). Compare the attachment copies, which are swept to 7 days / 200 MB (`apps/mobile/features/attachments/model/attachmentFileStore.ts:8-11`, `:89-103`).
  - `apps/mobile/lib/linkPreview.ts:11-33` — `Map<url, LinkPreview>`, no cap, cleared only at sign-out.
  - `apps/mobile/lib/lesson/quizAttempts.ts:5-14` — `Map` keyed by the whole quiz fence text, no cap, cleared only at sign-out.
- Evidence: `writeCachedChatMessages` writes `${CACHE_DIR}${chatId}.json` with no eviction; `fetchLinkPreview` does `cache.set(url, data)` with no bound.
- Impact: a heavy user's chat-page cache grows by tens of KB per chat opened, for years, until iOS/Android purge caches under storage pressure; the two Maps grow with every link and quiz seen in a session. Contained, but the app already has the pattern to bound it.
- Fix: run the chat-page cache through the same kind of sweep as `attachmentFileStore` (keep the N most recently read, or age out after 30 days) on start; give the two Maps an LRU cap like `lib/math/svgMath.ts` (`CACHE_MAX = 200`, `:16`, `:44-52`). Seams: `features/chat/model/messageCache.ts`, `lib/linkPreview.ts`, `lib/lesson/quizAttempts.ts`.
- Effort: S
- Verify: unit tests that the sweep keeps the newest N files, and that each Map stays at its cap after N+1 inserts.

---

## Looked wrong, actually fine

- **WS turn tasks** (`apps/api/app/modules/chat/ws_turn.py:128-202`): the producer is registered (`register_inflight_stream`) and always awaited; each per-iteration `receiver` task is cancelled and awaited when the producer finishes first; a disconnect lets the producer drain (by design: "Stop is the only hard stop") and `persist_finalize_if_pending` runs in `finally`.
- **Chat prepare lock** (`apps/api/app/modules/chat/turn_resources.py:118-140`): the refresh task is cancelled and the lock released in `finally`; both transports always drain the turn generator (`finish_open_stream`, `apps/api/app/modules/chat/stream_events.py:67-84`), so the `finally` runs. A stop during the save is covered by `await_ignoring_cancel` (`stream_events.py:50-64`).
- **Finalize registry / socket counter** (`apps/api/app/modules/chat/finalize_registry.py:55-62`, `:80-93`; `apps/api/app/modules/chat/ws_limits.py:85-103`): entries removed by done-callbacks; the `chatfinal` marker is cleared in `finally` (`apps/api/app/modules/chat/turn_settle.py:311-312`) with a 30 s TTL fallback; the per-user socket count is decremented in `finally` and the key dropped at zero.
- **Background tasks** (`apps/api/app/core/background_tasks.py`): strong references kept, discarded on completion, drained (10 s) then cancelled at shutdown. Raw `create_task` sites (`modules/images/reply_picture.py:97`, `answer_photo.py:52`, `turn_prep/prepare.py:211`, `tool_completion.py:77`, `speech/service.py:220`) are each held by their owner and cancelled or awaited on every path; `answer_photo` deliberately lets a late search finish and the orphan reaper removes the unlinked row.
- **Jobs consumer** (`apps/api/app/core/jobs/inflight.py:86-100`, `worker.py:85-106`): close cancels and awaits every job and the lease loop; a cancelled job leaves its entry pending and releases only a claim it owns.
- **SymPy pool** (`apps/api/app/core/sympy_executor.py:269-343`): the slot is returned in `finally` on every path; a timed-out, cancelled or broken worker is killed and replaced; workers exit with their parent (`_exit_with_parent`); `_kill_slot` reaps children before closing the queues.
- **In-process caches**: `TtlCache` for users (5,000) and chats (10,000) prunes on write; every `lru_cache` is bounded (largest `_read` 8,192 entries over math text capped at 1,000 chars, `apps/api/app/services/symbolic_text.py:114-123`); `http_client._clients` is keyed by a handful of named timeouts and closed at shutdown; per-call `httpx.AsyncClient`s (`gateways/image_gateway.py`, `modules/images/search.py:119`, `modules/link_preview/service.py:83`) all use `async with`.
- **Redis key lifetimes**: counters set TTLs in the same pipeline (`EXPIRE … NX`, `apps/api/app/core/rate_limit.py:18-21`, `apps/api/app/services/quota/counters.py:97-100`); the refresh-token set prunes expired members (`apps/api/app/modules/account/tokens.py:152-167`); non-context pipelines (`modules/notifications/push.py:80-84`, `services/model_health.py:41-45`) release their connection in `execute()`.
- **Jobs Redis client not closed at shutdown** (`apps/api/app/core/redis.py:36-39`; `apps/api/app/process_bootstrap.py:117` closes only the request client): only matters at process exit, where the sockets close anyway.
- **Phone effects**: the AST scan found no effect that registers a listener, interval, subscription, socket or player without returning a cleanup (two single-frame `requestAnimationFrame` calls aside). `useSharedValue` cancels its animation on unmount in Reanimated 4.5.1 (`node_modules/react-native-reanimated/src/hook/useSharedValue.ts`), so every `withRepeat` is stopped. FlashList v2 is used for every long list.
- **Phone transports**: the WebSocket closes on chat switch, unmount and when idle in the background (`apps/mobile/features/chat/hooks/useChatTransport.ts:74-135`, `features/chat/hooks/useChat.ts:222-224`); SSE is deliberately not aborted on leave (Stop is the hard cancel) and late events are dropped by the signal check (`useChatTransport.ts:152-156`).
- **Phone audio and Live Talk**: TTS players are removed and their files deleted after playback (`features/speech/model/pronunciation.ts:258-282`); cue players are released (`liveTalkSfx.ts:94-101`, `lib/scanner/switchCue.ts:79-112`); Live Talk closes on unmount, background, chat change and back, and a session that resolves after close is closed (`features/speech/hooks/useLiveTalk.ts:314-346`, `:386-390`, `:434-466`); voice input releases the mic on cancel/unmount, including a start that resolves late (`features/speech/hooks/useVoiceInput.ts:104-108`, `:208-226`). Only the recording *file* leaks (LEAK-04).
- **Phone Skia and WebViews**: Skia paths are built in `useMemo` and collected with their component; no image, surface or picture is created imperatively (the one `RuntimeEffect` is compiled once, `features/images/components/dotField.ts:109`). WebView mounts are gated by `lib/webViewMountQueue.ts` and every ticket is released on unmount or by the 6 s safety timer (`hooks/useDeferredWebViewMount.ts:63-85`).
- **Push scheduler filters**: `apps/api/app/modules/notifications/push.py:248-255` filters on the push preferences only, which is why LEAK-07 reaches signed-out devices; the receipts loop does prune tokens Expo reports dead.
- **Phone images and files**: picked/re-encoded copies, scans and downloads are tracked and deleted or swept (`features/attachments/model/attachmentPrep.ts:103-116`, `lib/scanner/scanImage.ts:79-104`, `attachmentFileStore.ts:89-103`); ImageManipulator contexts and refs are released in `finally`.

## Open questions for the team

1. **SSE disconnect detection through two `BaseHTTPMiddleware` layers.** `watch_disconnect` (`apps/api/app/modules/chat/stream_api.py:135-156`) polls `request.is_disconnected()`, which probes `receive` inside an already-cancelled scope (`starlette/requests.py:328-340`). With `RequestIdMiddleware` and `RestRateLimitMiddleware` (both `BaseHTTPMiddleware`, `core/request_id.py:47`, `core/rest_rate_limit.py:34`) in the chain, every `receive` goes through `receive_or_disconnect`, whose anyio task group must await its child on exit (`starlette/middleware/base.py:117-130`); inside the cancelled probe scope that await is cancelled, so the probe may never return the disconnect message. A disconnect would then be noticed only when the next event fails to send — late during a silent tool-loop or search phase. Worth one test through the full app (`httpx.ASGITransport` + client disconnect) before relying on it; converting those two middlewares to plain ASGI (as `body_limit` and `security_headers` already are) removes the question.
2. **SymPy kill on cancel.** `ProcessPoolSympyExecutor.run` kills the worker on any `BaseException` (`core/sympy_executor.py:333-340`), so a user's Stop (or an SSE disconnect) during a pre-solve costs a respawn plus the ~4 s warm import (`:144-147`, `:212-226`) on a 1-vCPU machine, during which that slot is unavailable to the 2 s interactive wait. Is that cheaper than letting a bounded solve finish? Worth measuring how often Stop lands in prepare.
3. **expo-image disk cache at sign-out.** Chat images, gallery tiles and avatars use `cachePolicy="memory-disk"` (`components/ChatMessageImage.tsx:103`, `features/attachments/components/GalleryThumbnail.tsx:129`, `components/Avatar.tsx:34`, …), and nothing calls `Image.clearDiskCache()` / `clearMemoryCache()`. The next account cannot address those URLs, but the previous account's private images stay on disk after sign-out, outside `accountState.test.ts`'s reach (it only sees JS stores). Decide whether sign-out should clear it (same gap class as LEAK-04).
4. **LiteLLM's own HTTP clients.** The gateway never passes a client; LiteLLM caches its own (`acompletion` in `gateways/litellm_gateway.py:79`, `:308`). Earlier LiteLLM versions leaked unclosed aiohttp sessions on cache eviction; confirm 1.105.0 closes evicted clients (watch `Unclosed client session` warnings and open-FD count on a soak run).
5. **Default executor size on Fly.** LEAK-03 assumes `os.cpu_count()` is 1 on the `shared-cpu-1x` VMs (5 default-executor threads, Python 3.12 image `apps/api/Dockerfile:9`). Worth confirming in a machine and logging the executor's queue depth.
