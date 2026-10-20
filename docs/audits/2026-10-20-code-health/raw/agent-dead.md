# Dimension E — Bloat and dead code (`DEAD-`)

Audited tree: `/home/user/recall-audit` at `d2ec42b0` (detached origin/main). Read-only; scripts in
`tmp/code-audit/raw/scratch-dead/` (all parse source or the lead's tool reports only; nothing was
run against the app, a database, Redis or a provider). Already-removed or deliberately kept items
from #1913 (`fcc09ae6`) and #1914 (`e64a7032`) are not re-reported (suggestions table, removed
test-only helpers, 13 i18n keys, 22 icons, 82 package re-exports, etc.).

Context that changes several verdicts: the app has **not launched**. `docs/PRODUCTION.md:327-334`
still has "Build" and "Submit to App Store / Play Console" unchecked and `apps/mobile/app.json:5` is
`"version": "1.0.0"`. Code kept "for older apps / older builds" therefore serves only developer and
internal installs.

## Metrics

| Source | Candidates | Confirmed dead (prod) | False positives | Notes |
|---|---|---|---|---|
| vulture (`--min-confidence 80`) | 112 (1 prod, 111 tests) | 0 | 112 | prod hit `math/tools/school/complex.py:77` is a `while True: for…else: break` loop vulture misreads; test hits are fixture params, fake signatures, `raise; yield` async-generator idioms |
| Own import-aware reachability over API top-level defs (`scratch-dead/pyreach.py`) | 10,904 defs, 6 unreached | 1 unused (`WORKOUT_PROMPT_SHORT`) + 5 test-only | 0 | resolves `from X import`, package re-exports, lazy `_EXPORTS`, module objects passed as DI values, memory `seams.X` |
| Own method scan (424 production methods) | 0 | 0 | — | every method name is read somewhere |
| Own route→client match (92 routes, `route_clients.py`) | 24 with no phone literal + 1 method mismatch (`GET /todos`; the phone only POSTs there) | **13 routes with no client** | 12: dynamic paths (`/{subject}/scan/read` ×3, `/ws/chats/{id}`), external callers (RevenueCat webhook, store-listing `/legal/*` ×3, `/health/ready`), ops/dev (`/admin/dlq` ×2, `/chats/usage/today/reset`) | |
| Own settings scan (209 fields) | 16 unread by name | 0 unread | 16 (`<base>_plus/_pro` read via `getattr` in `billing/entitlements.py:95`) | 3 `*_enabled` flags are never in the state production runs (DEAD-02) |
| knip unused files | 7 | 0 | 7 | metro stub, 2 config plugins, test-run script, vendored `image-size` (pnpm override) |
| knip unused deps / devDeps / unlisted | 2 / 2 / 1 | 0 / 0 / — | 4 | `expo-device` via native registry; vision-camera-worklets required by `useFrameOutput`; babel plugin; `lucide-static` by `scripts/generate-icons.mjs`; `expo-system-ui` unlisted is a *missing* dep (open question) |
| knip unused exports / types | 38 / 36 | 5 values + 36 types are export-only noise (used in-file) | 33 (vendored `image-size`) | DEAD-13 |
| Own mobile export scan (2,724 exports, import-resolving, tests not entries) | 57 test-only, 50 export-only | 14 test-only functions + 43 test-only barrel re-exports | screens re-exported by `app/` routes | DEAD-09 |
| depcheck | 3 deps + 4 devDeps | 0 | 7 | adds `@config-plugins/react-native-webrtc` (app.json plugin), `@react-native/metro-config` (peer of RN cli plugin and worklets), `@types/jest` |
| deptry (prod) | DEP002 ×5, DEP003 ×85 | 0 | 5 DEP002 | `asyncpg` (driver), `websockets` (uvicorn WS), `python-multipart` (`request.form()`), `cryptography` (PyJWT ES256, `gateways/apple_revoke.py:65`), `defusedxml` (openpyxl switches to defused parsing when installed, `openpyxl/xml/__init__.py:42`). DEP003 = undeclared direct use of transitive `pydantic`/`starlette`/`botocore`/`mpmath` (hygiene, not bloat) |
| Own over-engineering scan (API) | 20 `Protocol`s, 0 ABCs; registries with ≤1 literal entry | 0 | 20 + 2 | 14 `Protocol`s are the `ChatTurnDeps` seam; of the other 6, `StorageGateway` (2 impls) and `ToolAdapter` (4) are real interfaces, `TavilyBudget` keeps `gateways/` module-free, and `StreamStatusFn`, `MemorySection`, `_HasPlan`, `_Named` are callback/structural types; `_REGISTRY`/`_HANDLERS` are filled at startup. Real over-engineering found instead: the memory seams barrel (DEAD-04) and facades (DEAD-05) |
| Own i18n scan (931 keys) | 4 | 0 | 4 | built as `` `rich.diagram_a11y_${kind}` `` / `rich.diagram_source_*` |
| radon cc (grade C+) | 954 functions | — | — | production: C 616, D 124, E 42, F 32 (814); tests: 140 |
| radon mi (grade C) | 19 files | — | — | production: 4 (`chat/calculation_layout.py` 0.00, `math/solve/traces.py` 6.83, `math/match/calculus.py` 7.17, `math/match/discrete.py` 7.39) — all 4 already in `scripts/file_size_baseline.json`; 15 test files |

Worst 15 production functions by cyclomatic complexity (radon):

| CC | Function | Location | In size baseline? |
|---|---|---|---|
| 95 | `calculus_direct_request` | `apps/api/app/modules/math/tools/direct_calculus.py:113` | no (file 330 lines) |
| 75 | `_extract_torque_intent` | `apps/api/app/modules/physics/extractors/torque.py:51` | no (244) |
| 71 | `can_direct_verified_math_reply` | `apps/api/app/modules/math/tools/direct.py:163` | yes (501) |
| 67 | `_extract_circuit_intent` | `apps/api/app/modules/physics/extractors/circuits.py:70` | no (285) |
| 64 | `_extract_trig_intent` | `apps/api/app/modules/math/tools/school/trig.py:86` | no (392) |
| 61 | `_extract_friction_intent` | `apps/api/app/modules/physics/extractors/friction.py:112` | — |
| 59 | `SimulationBlockSpec.coherent_scene` | `apps/api/app/modules/physics/schemas/simulation.py:506` | — |
| 58 | `MathImageExtract.normalize_kind` | `apps/api/app/modules/math/schemas/algebra.py:110` | — |
| 58 | `classify_math_response_intent` | `apps/api/app/modules/math/response_intent.py:239` | — |
| 53 | `_extract_kinematics_intent` | `apps/api/app/modules/physics/extractors/kinematics.py:121` | — |
| 51 | `_extract_momentum_intent` | `apps/api/app/modules/physics/extractors/momentum.py:180` | — |
| 51 | `_extract_magnetism_intent` | `apps/api/app/modules/physics/extractors/magnetism.py:59` | — |
| 49 | `extract_rate_intent` | `apps/api/app/modules/physics/extractors/rates.py:32` | — |
| 49 | `apply_calculus_extension` | `apps/api/app/modules/math/tools/school/calculus.py:264` | — |
| 48 | `_extract_waves_intent` / `_extract_pass` | `physics/extractors/waves.py:59`, `memory/extraction_workflow.py:269` | — |

Observation (for the clarity agent, not a DEAD finding): the file-size gate cannot see these; four
of the five worst functions live in files under 500 lines.

## Findings

### DEAD-01 — 13 API routes no client calls, and the server code only they reach

- Severity: High (5 authenticated routes that write or delete user data with no caller, ~540 production lines plus their tests, a paid-provider streaming endpoint, and five tombstones for clients that never shipped)
- Confidence: High
- Locations (route → what only it reaches):
  - Todos — phone dropped lists on 2026-08-29 (`6b07b4951`, #1082) and moved to `/todos/page` on 2026-09-04 (`a6d0773e2`, #1194):
    - `GET /todos` `apps/api/app/modules/todos/api.py:25` (`list_todos`, offset pagination "forward-compatible for the web client"; its own test calls it `legacy`, `apps/api/app/tests/modules/todos/test_api.py:247`) → `apps/api/app/modules/todos/crud.py:37-49`
    - `GET /todos/topics` `apps/api/app/modules/todos/api.py:55` → `crud.py:73-74`, `apps/api/app/modules/todos/repository.py:113-120`
    - `POST /todos/reorder` `apps/api/app/modules/todos/api.py:84` → `crud.py:120-127`, `repository.py:245-278`, `apps/api/app/modules/todos/schemas.py:102-113` (`TodoReorderItem`, `TodoReorderBody`), re-export `apps/api/app/models/schemas/__init__.py:66,119`
    - `DELETE /todos/topic/{topic}` `apps/api/app/modules/todos/api.py:144` → `crud.py:199-203`, `repository.py:227-242`
  - Memory — #1914 (`e64a7032`, 2026-10-20) deleted the phone half (`memoriesApi.deleteMemorySection`, `deleteMemoryFact`) and left the server half; `/consolidate` lost its client on 2026-06-29 (`3e7239cf2`):
    - `POST /memories/consolidate` `apps/api/app/modules/memory/api.py:146` → `apps/api/app/modules/memory/enqueue_policy.py:66-79` (`request_user_consolidation`)
    - `DELETE /memories/type/{memory_type}` `apps/api/app/modules/memory/api.py:170` → `apps/api/app/modules/memory/crud.py:222-235`, `apps/api/app/modules/memory/surface.py:338-339`, `apps/api/app/modules/memory/repository.py:131-149` (`delete_by_type`)
    - `DELETE /memories/{memory_id}/facts/{fact_index}` `apps/api/app/modules/memory/api.py:222` → `apps/api/app/modules/memory/crud.py:57-138` ("Legacy sentence-index delete", 82 lines incl. re-embed), `surface.py:300-317`, `MEMORY_FACT_TEXT_MAX_LENGTH` `apps/api/app/modules/memory/schemas.py:17`
  - Speech:
    - `POST /speech/tts/stream` `apps/api/app/modules/speech/api.py:163-204` → `api.py:48` (`TTS_STREAM_MEDIA_TYPE`), `api.py:71-74` (`_aiter_nonempty`), `apps/api/app/modules/speech/service.py:170-249` (`_collect_pcm`, `iter_tts_pcm`), `apps/api/app/gateways/speech_gateway.py:221-262` (`stream_pcm_via_openai`). Never had a caller on `main` (added `bf01d9fc2` 2026-08-16; the phone's `ttsPcm.ts` named in `.cursor/rules/lessons.mdc:786` does not exist); `FEATURES.md:1311` says it "stays server-ready".
    - Tombstones returning 410: `POST /speech/live/turn|refund|commit|speak` `apps/api/app/modules/speech/api.py:282,291,300,309` via `_raise_live_talk_route_gone` `api.py:51-57` (since 2026-08-30, `a05c994f6`, #1100)
    - Tombstone returning 426 "Legacy Live Talk client detected. Pull the latest main branch, restart Metro…": `POST /speech/live/webrtc` `apps/api/app/modules/speech/realtime.py:224-237` with `RealtimeOfferIn/Out` `realtime.py:54-62` (since 2026-08-31, `c0c744c19`, #1123)
- Evidence:
  - `python3 -I scratch-dead/routes.py <repo>/apps/api > routes.txt && python3 -I scratch-dead/route_clients.py routes.txt <repo>` matched all 92 routes against every non-test `.ts/.tsx/.js` under `apps/mobile` and `apps/web` (full table in `scratch-dead/route_clients.txt`; 18 unmatched, 5 of them dynamic-path false positives).
  - Mobile API slices list the calls: `apps/mobile/features/todos/api.ts:14,35,60,65,69` (only `/todos/page`, `POST /todos`, `PATCH|DELETE /todos/{id}`, proposals confirm); `apps/mobile/features/memory/api.ts:11-30` (no consolidate/type/facts); `apps/mobile/features/speech/api.ts:17-80` (`/speech/live`, `/live/session`, `/live/persist`, `/live/end`, `/live/tool`, `/transcribe`, `/tts`); the phone does WebRTC SDP directly with OpenAI (`apps/mobile/features/speech/model/realtimePeer.ts:333-335`, `exchangeRealtimeSdp`, `transport: "direct-ephemeral"`).
  - `grep -rn "consolidate\|/memories/type\|/facts/" apps/mobile/{features,lib,components,hooks,app,contexts,ui} | grep -v __tests__` → empty. `grep -rn "[\"'\`]/todos[\"'\`?]" apps/mobile …` → only the POST at `features/todos/api.ts:35` and router `href`s. `grep -rn "tts/stream\|live/turn\|live/refund\|live/commit\|live/speak\|live/webrtc" apps/mobile apps/web/src scripts` → empty. `grep -rln "/todos\|/memories" apps/web/src` → empty.
  - `git log -S` per path (dates above).
- Impact: each route is authenticated attack surface and test load with no product behind it (`DELETE …/facts/{index}` re-embeds and rewrites a row; `/tts/stream` calls a paid provider and spends TTS quota). The 82-line index-based fact delete is a second delete semantics next to the atomic one the app uses. The tombstones answer clients that never reached a store (pre-launch), and the 426 detail is developer instructions ("restart Metro"), the kind of text #1915 just removed from user-facing errors.
- Fix: delete the 13 routes and the code listed under each (≈540 lines: `scratch-dead/spans.py` output), the `RealtimeOfferIn/Out`/`TodoReorder*` schemas and re-exports, the surface wrappers, and their tests (`tests/modules/todos/test_api.py` legacy assertions, `tests/modules/memory/test_api.py`, `test_memory_management.py`, `tests/modules/speech/test_api_gates.py`, `test_realtime.py`, `test_service.py` PCM cases, `tests/test_routers.py`, `tests/test_new_features.py:23-76`, `tests/security/test_cross_user_isolation.py` cases). Update `FEATURES.md:213,1311`. If any route is wanted for `apps/web` later, re-add it with its client in the same PR. Keep `/legal/delete-account` (store listing URL) and the dev-gated `/chats/usage/today/reset`, `/auth/me/pro-dev`.
- Effort: M
- Verify: re-run `route_clients.py` → every route has a client or a documented external caller; `uv run pytest app/tests/modules/{todos,memory,speech}` green; `grep -rn "iter_tts_pcm\|stream_pcm_via_openai\|delete_by_type\|request_user_consolidation\|reorder_todos\|delete_by_topic" apps/api/app` empty.

### DEAD-02 — Three switches production never flips keep ~700 lines that never run in production (but run in tests)

- Severity: High (≈700 production lines and dozens of tests maintain behavior production cannot reach; rule 9 "stale flags")
- Confidence: High (the production state of each switch is in code or `fly.toml`; whether to delete is a product call, see Fix)
- Locations:
  1. `mcp_tool_loop_enabled` — default `True` since 2026-08-16 (`699272c5e`, #690; `apps/api/app/core/settings/llm.py:13`), never overridden in `fly.toml`. `build_search_augmentation` returns `(None, [])` at `apps/api/app/modules/web_search/augment.py:69-70`, so the pre-stream heuristic web search below it (`augment.py:72-157`) never runs in production, though every augmented turn still awaits it (`apps/api/app/modules/chat/turn_prep/augment.py:104-107` → `apps/api/app/modules/chat/prompt_builder.py:121-142`). Helpers only that branch uses: `_prioritize_team_hits` `apps/api/app/modules/web_search/query_builders.py:192-199`, `_geo_is_active` / `_places_list_is_active` `apps/api/app/modules/web_search/geo_intent.py:150-155`. Tests keep the off state alive: 53 call sites in 11 test files set `mcp_tool_loop_enabled=False` (e.g. `tests/modules/web_search/test_web_search_run.py:12,40,76,99`), and #1914 moved the test-only wrapper of this branch into `tests/modules/web_search/augment_support.py` instead of deleting the branch.
  2. `web_search_classifier_enabled` — default `True` (`apps/api/app/core/settings/search.py:10`) but `fly.toml:28-30` sets `WEB_SEARCH_CLASSIFIER_ENABLED = "false"` since 2026-09-10 (`49a3dee1c`, #1297, "keep a second LLM call out of time-to-first-token"). Production never reaches the LLM classifier: `apps/api/app/modules/web_search/classify.py` (115 lines), `classify_web_search` `apps/api/app/modules/web_search/detection.py:310-332` (returns `None` at 318-319), the prefetch overlap `_overlapped_classifier` `apps/api/app/modules/chat/turn_prep/augment.py:189-224` (returns `None` at 207). The behavior harness forces it on (`apps/api/app/tests/behavior/harness.py:184`, `web_search_classifier_enabled=True`; 24 test sites), so the routing battery and sweep certify a configuration production does not run.
  3. `reminder_proposals_enabled` — default `True` since 2026-10-14 (`c0f36a541`; `apps/api/app/core/settings/chat.py:22`), never overridden. The post-turn `todos` LLM sync job is then never enqueued: `_todos_job` returns `[]` at `apps/api/app/modules/chat/post_turn.py:132`; live talk's copy is gated at `apps/api/app/modules/speech/live_talk.py:460-473`. Code reachable only from those: `apps/api/app/modules/todos/sync.py` (199), `apps/api/app/modules/todos/extract.py` (80), `apps/api/app/modules/todos/jobs.py` (26), `_handle_todos` `apps/api/app/background/handlers.py:224-231` and `register("todos", …)` `handlers.py:311`, `should_recover_todo_writes` `apps/api/app/modules/todos/classification.py:162-168`, `mock_todo_actions` `apps/api/app/gateways/mock_llm.py:164-197`, `TodoExtractionResult` `apps/api/app/modules/todos/schemas.py:148-151`. (`materialize_reminder_fences(confirm=False)` stays: live talk uses it, `live_talk.py:361`.)
- Evidence: `grep -n "WEB_SEARCH_CLASSIFIER_ENABLED\|MCP_TOOL_LOOP\|REMINDER_PROPOSALS" fly.toml docs/PRODUCTION.md` → only the classifier line (`fly.toml:30`). `grep -rn "reminder_proposals_enabled" apps/api/app --include=*.py | grep -v tests` → the default and three gates (`post_turn.py:132`, `finalize_reminders.py:96`, `live_talk.py:461`). `grep -rn "extract_todo_actions\|sync_todos_from_transcript\|build_todo_sync_transcript" apps/api/app | grep -v tests` → only `sync.py`, `jobs.py`, `post_turn.py:139` (inside the gated function) and the lazy `_EXPORTS` table. Line counts: `scratch-dead/spans.py` (tool-loop-off 125, classifier 174, todo sync ≈410).
- Impact: three code paths are maintained, reviewed and tested as if they ship, and two of them call paid models. The battery's routing verdicts include a classifier production does not run, so a routing regression in production can hide behind a passing battery. `CLAUDE.md` ("Heuristic SymPy + web-search inject still run") describes the dead branch as live.
- Fix: decide per switch and record it in `core/settings/` with a date. Recommended: (1) delete `augment.py:63-157` and its three helpers and make `build_search_augmentation` go away (the tool loop owns search; keep `mcp_tool_loop_enabled` only as a kill switch for the loop itself), drop the 53 `mcp_tool_loop_enabled=False` test sites that only exist to reach it; (2) either delete the classifier (`classify.py`, `classify_web_search`, `_overlapped_classifier`, the `web_search_classifier_*` settings, the harness override) or set the default to `False` so dev, tests and production agree; (3) for reminder cards (6 days old) keep the kill switch until the cards have shipped, then delete the todo-sync job, its handler registration, the `todos` job type in `CLAUDE.md`'s job list and the mock.
- Effort: M
- Verify: `grep -rn "mcp_tool_loop_enabled=False" apps/api/app/tests | wc -l` → 0 (or only the loop's own kill-switch test); `uv run pytest` green; `./scripts/dev.sh battery` and `test_battery.py`/`test_sweep.py` green with the harness on production settings.

### DEAD-03 — `response_style`: a setting removed two days ago is still stored, served, accepted and threaded through maths as a constant

- Severity: Medium (a DB column, two API fields, a phone type, seven signatures and two unreachable branches for one constant)
- Confidence: High
- Locations:
  - Kept "for older clients" by #1873 (`c7e69ecf4`, 2026-10-18: "The column and API field stay for older clients"), in a pre-launch app:
    - column `apps/api/app/models/orm/user.py:52`; served `apps/api/app/models/schemas/auth.py:28` (`UserOut`); accepted `auth.py:103` (`UserUpdate`, type `ResponseStyle` `apps/api/app/models/schemas/common.py:23`, used nowhere else); still written: `PATCH /auth/me` passes `body.model_dump(exclude_unset=True)` to `update_account` (`apps/api/app/modules/account/api.py:377-381`); exported `apps/api/app/modules/account/export.py:69`; ignored by chat (`apps/api/app/modules/chat/prompt_sections.py:124-126`).
    - phone: typed `apps/mobile/lib/api/types.ts:29`, seeded `apps/mobile/lib/cachedUser.ts:55`, never read or sent.
  - Parameter fixed at `"balanced"`: the only production producer is `apps/api/app/modules/chat/turn_prep/augment.py:68-69` (`response_style="balanced"`); `apps/api/app/services/subject_solving.py:420` uses the default. It is threaded through `subject_solving.py:226,276,287,334,432,444` (physics `:229` and chemistry `:337` adapters `del` it on entry), `apps/api/app/modules/math/tools/direct.py:168,202,437,486,493,498` and `apps/api/app/modules/math/tools/lesson.py:93`.
  - Unreachable branches: `lesson.py:106-109` (`== "short"` / `== "detailed"`) and the `response_style == "detailed"` arm of `direct.py:497-499`.
- Evidence: `grep -rn "response_style=" apps/api/app --include=*.py | grep -v tests` → `augment.py:69` (literal `"balanced"`), `direct.py:486`, `subject_solving.py:287,444` (pass-through only). `grep -rn "ResponseStyle\b" apps/api/app | grep -v tests` → `common.py:23`, `auth.py:14,103`. `grep -rn "response_style" apps/mobile/{features,lib,components} | grep -v __tests__` → `types.ts:29`, `cachedUser.ts:55` only. 34 test `.py` files and the prompt golden (`prompt_messages.json`, 8 mentions) carry `response_style`.
- Impact: every reader of the maths direct-reply path has to reason about three lengths that cannot occur; the API still lets a client store a value nothing reads; the column must be carried through export, deletion and migrations. CLAUDE.md's preference model says length is per message, the code says otherwise.
- Fix: drop the parameter from `SubjectAdapter.direct_reply` and the seven functions, delete `lesson.py:106-109` and the `"detailed"` arm, remove `response_style` from `UserOut`, `UserUpdate`, `ResponseStyle`, export, `types.ts`, `cachedUser.ts`, then contract the column in a later release (expand/contract per `docs/ENGINEERING_STANDARDS.md` "Schema changes"). Update the seven golden short-user prompts (`tests/modules/chat/golden/prompt_messages.json`) that still assert a stored "short" is ignored.
- Effort: S (code) + S (later migration)
- Verify: `grep -rn "response_style" apps/api/app apps/mobile/{lib,features,components} --include=*.py --include=*.ts --include=*.tsx | grep -v tests` → only the ORM column until the contract migration; `uv run pytest app/tests/modules/math app/tests/modules/chat` and `pnpm typecheck` green.

### DEAD-04 — Memory's "compatibility barrel": 19 forwarding wrappers and 42 re-exports kept so tests can monkeypatch the package

- Severity: Medium (347-line production indirection whose stated purpose is test patching; every memory collaborator takes an untyped `seams: Any`)
- Confidence: High (counts); the right replacement is an architecture call
- Locations:
  - `apps/api/app/modules/memory/surface.py:1-5` ("Compatibility barrel … so existing `app.modules.memory.*` monkeypatches continue to affect collaborators"), `surface.py:131-133` (`_seams()` returns `sys.modules["app.modules.memory"]`), installed on the package by `apps/api/app/modules/memory/__init__.py:15-20`.
  - 19 wrappers that only forward their arguments plus `_seams()`: `surface.py:136,153,157,161,165,169,189,213,237,255,278,282,296,300,320,334,338,342,346`.
  - 22 receivers typed `seams: Any` that call collaborators as `seams.X`: `apps/api/app/modules/memory/cache.py` (2), `crud.py` (9), `locks.py` (3), `retrieval.py` (8; e.g. `retrieval.py:56,71,82,102`).
  - Re-exports no file reads through the package: `MemoryLoadStatus` (`surface.py:37`), `TYPE_PRIORITY` (43), `_confidence_value` (46), `_eligible_memory` (49), `_split_sentences` (67), `classify_memory_sensitivity` (70), `is_explicit_mute_command` (88), `is_memory_correction` (100; also promised in `__init__.py:32` "names other modules import from this package"), `merge_diet_facts` (118). Read through the package only by tests: `consolidation_rewrite_preserves_facts` (25), `extract_consolidation_anchors` (28), `is_food_or_diet_memory_text` (91).
- Evidence: `python3 -I scratch-dead/memory_surface.py apps/api` → `bound=64 prod=51 test_only=3 unread=10 forwarding=19` (`scratch-dead/memory_surface.txt`; the 10th unread is `_seams` itself). Per name: `grep -rn "\.\(MemoryLoadStatus\|TYPE_PRIORITY\|_confidence_value\|_eligible_memory\|_split_sentences\|merge_diet_facts\|classify_memory_sensitivity\|is_explicit_mute_command\|is_memory_correction\)\b\|app\.modules\.memory\.\(…\)" apps/api/app` → empty; production importers use the defining modules (`extraction_workflow.py:26-27,45`, `facts.py:37-39`, `consolidation.py:15`, `commands.py`). Test coupling: 119 `"app.modules.memory.<name>"` patch strings in 19 test files plus 8 `patch.object(memory_service, …)`.
- Impact: rule 9 ("thin wrappers that only forward their arguments") and "no speculative interfaces"; `docs/ARCHITECTURE.md:32-36` says the migration re-exports were deleted, but this one is the largest left. Private helpers (`_split_sentences`, `_confidence_value`) are re-exported as a public surface. Static analysis cannot follow `seams.X`, so dead memory code hides behind the barrel (my reachability pass had to special-case it), and every new memory function needs a wrapper here to stay patchable.
- Fix: do for memory what ES-23/`ChatTurnDeps` did for chat: give the collaborators explicit, typed dependencies (or import the defining modules directly), point tests at the defining modules (`monkeypatch.setattr(retrieval, "select_memories_semantic", …)`), then delete `surface.py`'s wrappers and the 12 unread/test-only re-exports. As a first, behavior-free step, delete the 9 unread re-exports and the `is_memory_correction` entry in `__init__.__all__` now.
- Effort: M (the 119 test patch targets move); S for the first step
- Verify: `grep -n "seams: Any" apps/api/app/modules/memory/*.py` → empty; `surface.py` gone or reduced to the public names other modules import; `uv run pytest app/tests/modules/memory app/tests/modules/chat -k memory` green; `test_legacy_paths_removed.py` lists `app.modules.memory.surface` in `RETIRED_LEGACY_MODULES` if removed.

### DEAD-05 — Migration aliases and re-export facades still in place: `services/model_catalog.py`, `MathServiceError`, `physics/solver.py`'s `__all__`

- Severity: Low (no behavior; two spellings for one thing, and docs point at the wrong owner)
- Confidence: High
- Locations:
  - `apps/api/app/services/model_catalog.py:1-55` — "Service-facing model catalog compatibility API": 20 names re-exported from `app.models.model_catalog` (`:10-31`, `__all__` `:33-55`) around one real function, `is_available` (`:57-61`). Production imports split 10 files through the barrel (e.g. `apps/api/app/modules/chat/turn_settle.py:29`, `turn_load.py:33`, `stream_pipeline.py:39`, `apps/api/app/modules/images/generation.py:38-39`, `apps/api/app/modules/speech/service.py:13`, `apps/api/app/routers/models.py:8`) vs 12 files direct to `app.models.model_catalog`; 4 re-exports (`CATALOG`, `is_reasoning_alias`, `litellm_openrouter_model`, `validate_user_alias`) are read through the barrel only by tests. `CLAUDE.md` (Golden rule 2 and the Seams table) says the alias mapping "lives in `services/model_catalog.py`"; `docs/ARCHITECTURE.md:47` says `models/model_catalog.py`.
  - `MathServiceError = SolveServiceError` `apps/api/app/services/solving.py:133-136` ("Compatibility … while callers migrate to the subject-neutral name"), added 2026-09-27 (`574553aaa`, #1500), re-exported again `apps/api/app/modules/math/solve/__init__.py:77,82`. Three weeks on, the alias is still the spelling at 237 production lines in 33 files (`grep -rln "\bMathServiceError\b" apps/api/app | grep -v tests` lists them: `math/school.py`, `math/solve/*.py` ×17, `math/tools/block/*.py` ×4, …) against 652 lines for `SolveServiceError`; 16 test files.
  - `apps/api/app/modules/physics/solver.py:1,39-66` — "Stable public facade" whose `__all__` lists 26 names, including private `_PARAM_SI_DIMENSIONS`, `_params_in_si`, `_to_si`. Production imports only `PhysicsResult` and `solve_physics` through it (`physics/block.py:23`, `physics/answer_checks.py:13`); tests add `PHYSICS_SOLVERS` and five `solve_*`; the other 18 entries are read by nobody through the facade (they are used inside the file's registry, so only the export is surplus; `physics/accounting.py:28` already imports `_to_si` from `solvers/common.py`).
- Evidence: `grep -rn "app.services.model_catalog\|from app.services import model_catalog" apps/api/app --include=*.py | grep -v tests` (10 files) vs `grep -rln "app.models.model_catalog\|from app.models import model_catalog" apps/api/app | grep -v tests` (12 files). `grep -rn "\bMathServiceError\b" apps/api/app --include=*.py | grep -v tests | wc -l` → 237. `grep -rn "from app.modules.physics.solver import" apps/api/app` → the 2 production lines above.
- Impact: `docs/ARCHITECTURE.md:32-36` says the migration re-exports were deleted and `test_legacy_paths_removed.py` guards against new ones, but these three survive; new code keeps choosing between two import paths and two exception names.
- Fix: move `is_available` beside `model_health` (or keep `services/model_catalog.py` with only it), point the 10 files and tests at `app.models.model_catalog`, fix CLAUDE.md; rename `MathServiceError` to `SolveServiceError` in the 33 files (mechanical) and delete the alias and its re-export; trim `physics/solver.py`'s `__all__` to `PHYSICS_SOLVERS`, `PhysicsResult`, `solve_physics` (+ the five `solve_*` tests use, or point those tests at `solvers/*`). Add the retired paths to `RETIRED_LEGACY_MODULES` where a module disappears.
- Effort: S
- Verify: `grep -rn "MathServiceError" apps/api/app` → empty; `grep -rn "services.model_catalog import \(CATALOG\|get\|openrouter_slug\)" apps/api/app` → empty; `uv run mypy` and `uv run pytest` green.

### DEAD-06 — Data-format shims that outlived the data: a legacy spend key read on every spend check, legacy refresh records, title jobs without a user

- Severity: Medium (the spend shim doubles the Redis round trips of a check that runs several times per chat turn and on every job; the other two are small but keep unscoped/legacy branches alive)
- Confidence: High for the spend key and the topic payload; Medium-High for refresh records (assumes production deployed `0c9f0fedd` within days of 2026-09-11 and Redis was not restored from an older snapshot)
- Locations:
  - `apps/api/app/core/spend_counter.py:28-30` (`_LEGACY_SPEND_UNITS_TO_MICRO_USD`, comment: "it expires with its TTL and can be dropped after that"), `:37-38` (`_legacy_spend_key()` = `spend_mcents:{today UTC}`), `:63-66` (`get_global_spend_micro_usd` awaits two sequential `GET`s). The writer of `spend_mcents:*` was removed on 2026-10-15 (`bac689f0e`); because the key name is today's date, the second `GET` has returned nil every day since 2026-10-16. Hot callers: `apps/api/app/modules/chat/turn_resources.py:299`, `stream_paths.py:166`, `post_turn.py:239`, `prompt_memory.py:158`, `related_prompts.py:184`, every job (`apps/api/app/background/handlers.py:101`), plus images, speech, scan, attachments, memory instruct, the classifier and conversation reference (15 call sites; `grep -rn "global_spend_exceeded(" apps/api/app | grep -v "tests\|def "`).
  - `apps/api/app/modules/account/tokens.py:62-63` (`_legacy_session_id`), `:66-85` (`parse_refresh_record`'s two legacy formats: JSON without `session_id`, and a bare user-id string) and `:373` (fallback in `list_sessions`). Every refresh record written since 2026-09-11 (`0c9f0fedd`, #1300) carries `session_id` (create `:125-142`, rotate `:250-285`) with `ex = jwt_refresh_expire_days * 86400` (30 days, `apps/api/app/core/settings/auth.py:22`), so no legacy record can exist after about 2026-10-11.
  - `apps/api/app/services/topic.py:25-32` + `apps/api/app/background/handlers.py:128-129`: "Backward-compat: older in-flight job payloads may omit user_id", added 2026-08-13 (`b0605b7ec`, #644). All three enqueuers send `user_id` (`modules/chat/post_turn.py:166`, `modules/chat/service.py:231-235`, `modules/speech/live_talk.py:420-423`); only a DLQ replay of a payload older than two months could reach it, and it then runs an unscoped (`user_id=None`) title update (`topic.py:45-46`).
- Evidence: `git log -S "_LEGACY_SPEND_UNITS_TO_MICRO_USD"` → `bac689f0e 2026-10-15` ("The old key is still read … it expires within 48h"); `git log -S "_legacy_session_id"` → `0c9f0fedd 2026-09-11`; `git log -S "older in-flight job payloads may omit user_id"` → `b0605b7ec 2026-08-13`. `grep -rn "spend_mcents" apps/api/app` → only `spend_counter.py:38` (no writer). The check returns early only when no cap is set, and production must set `DAILY_GLOBAL_SPEND_USD > 0` (`apps/api/app/core/config.py:127`, `docs/PRODUCTION.md:144`), so production always pays both `GET`s.
- Impact: wasted Upstash commands (billed per request; `CLAUDE.md` notes the free-tier request cap has been hit) and latency on the chat path; security-adjacent parsing branches (auth sessions, an unscoped write) that no live data can reach still need review and tests.
- Fix: delete the legacy spend key read and constant (one `GET` per check); delete `_legacy_session_id` and the two legacy branches of `parse_refresh_record` (treat a record without `session_id` as invalid → re-login); require `user_id` in the topic payload (`handlers.py:128-129` → `UUID(payload["user_id"])`) and drop the unscoped branch. Give future shims an explicit removal date in the comment.
- Effort: S
- Verify: `grep -rn "_legacy\|spend_mcents\|older in-flight" apps/api/app --include=*.py | grep -v tests` → empty; `uv run pytest app/tests/services/test_global_spend_precision.py app/tests/modules/account app/tests/test_jobs.py` green (drop the legacy-format cases).

### DEAD-07 — Upgrade paths for installs and app versions that never shipped (pre-launch)

- Severity: Low (small, but it is auth-storage and settings code that only a developer's old install can reach)
- Confidence: Medium (certain no store install exists; whether any internal/TestFlight build from before mid-August is still in use is a team question)
- Locations:
  - Token storage migration from two SecureStore keys to one record: `apps/mobile/lib/auth.ts:6-7` (`LEGACY_ACCESS_KEY`, `LEGACY_REFRESH_KEY`), `:58-63` (`deleteLegacyTokens`), `:89-100` (read-and-migrate in `readTokenPair`); added 2026-09-04 (`e8b2f5292`). A refresh token is valid 30 days, so even a developer install from before that date can no longer refresh with what it migrates.
  - Keychain→file preference migration (added 2026-08-13, `7403ebcbb`, "prefs off Keychain"): `apps/mobile/lib/filePrefs.ts:53-67` (`readLegacySecureStore`, `deleteLegacySecureStore`) and its four callers `apps/mobile/features/todos/model/reminderSeen.ts:11-14,37-41,69`, `apps/mobile/features/todos/model/reminderPrefs.ts:22,47-49,73`, `apps/mobile/lib/onboarding.ts:10,29-33,45-47`, `apps/mobile/lib/appearancePrefs.ts:14,31-35`.
  - `SpeechLiveStatusOut.refunded` "kept for old clients and is always false" `apps/api/app/modules/speech/schemas.py:42-50` (2026-10-15, `e97aac9e0`); the phone types it (`apps/mobile/features/speech/model/liveTalkLogic.ts:18`) and never reads it.
  - `apps/mobile/features/todos/screens/TodosScreen.tsx:214-217`: "Legacy links used focus=list" redirect (2026-06-28); nothing emits `focus=list` (the server's push sends `focus: "reminders"`, `apps/api/app/modules/notifications/push.py:309`; the phone's push router sends `highlight` only, `apps/mobile/lib/pushNotifications.ts:277-282`).
  - Server tombstones for old Live Talk clients are in DEAD-01; `response_style` "for older clients" is DEAD-03.
- Evidence: `docs/PRODUCTION.md:327-334` (store build and submission unchecked), `apps/mobile/app.json:5` (`1.0.0`). `grep -rn "readLegacySecureStore\|deleteLegacySecureStore\|LEGACY_ACCESS_KEY\|LEGACY_REFRESH_KEY" apps/mobile/{lib,features} | grep -v __tests__` → the lines above. `grep -rn "\.refunded" apps/mobile --include=*.ts --include=*.tsx | grep -v node_modules` → empty. `grep -rn "focus=list\|focus: \"list\"" apps/mobile apps/api/app` → only the redirect comment.
- Impact: on a store install the legacy keys never exist, yet each reader falls through to a Keychain read whenever its new file is absent and writes nothing back, so appearance, reminder lead time and seen-reminder ids re-read the Keychain on every cold start until the user changes that setting, and `readTokenPair` reads two legacy keys on every token read while signed out. Auth code keeps a second storage format. The cleanest moment to drop all of this is before the first store build; afterwards a real migration would be needed.
- Fix: before the first production build, delete the legacy reads (keep `deleteItemAsync` of the old keys only if the team wants to scrub developer devices), `readLegacySecureStore`/`deleteLegacySecureStore`, the `refunded` field on both sides, and the `focus=list` redirect; adjust `lib/__tests__/auth*.test.ts`, `onboarding`, `appearancePrefs`, `reminderPrefs`, `reminderSeen` tests. Add a rule to `docs/ENGINEERING_STANDARDS.md`: compatibility code names the released version it serves and the date it goes.
- Effort: S
- Verify: `grep -rn "Legacy\|LEGACY_" apps/mobile/lib/auth.ts apps/mobile/lib/filePrefs.ts` → empty; `pnpm test` and `pnpm typecheck` green.

### DEAD-08 — Phone gates frozen into constants still carry their branches

- Severity: Low
- Confidence: High
- Locations:
  - `canUseVoiceInput()` `apps/mobile/lib/expoRuntime.ts:52-58` returns `true` unconditionally (since 2026-09-04, `052eab2e2`, #1187). Its only production reader, `apps/mobile/lib/speech/voiceAudio.ts:27-30`, therefore never takes the `return null` branch; only a test mocks it to `false` (`apps/mobile/lib/speech/__tests__/voiceAudio.test.ts:37`), and three more tests assert or mock the constant (`lib/__tests__/expoRuntime.test.ts:27,36,45`, `lib/__tests__/purchases.test.ts:3`).
  - `shouldSilentRefetchChatOnFocus()` `apps/mobile/features/chat/model/foregroundRefetch.ts:24-27` returns `false` unconditionally (since 2026-08-25, `cbf958ef1`, #1005; its doc names the Lists and Learning screens, both since removed). The focus effect in `apps/mobile/features/chat/hooks/useChatRouteLoader.ts:443-459` returns at `:450` every time, so `:451-457` never run, and `skipNextFocusRef` (`:138`, `:307`, `:329`, `:446-449`) exists only to feed that dead effect. Test: `features/chat/model/__tests__/chatForegroundRefetch.test.ts:43`.
- Evidence: `grep -rPzo "export function \w+\([^)]*\)[^{]*\{\s*return (true|false);\s*\}" apps/mobile/{app,components,features,lib,hooks,ui,contexts}` → exactly these two. `grep -rn "canUseVoiceInput\|shouldSilentRefetchChatOnFocus" apps/mobile --include=*.ts --include=*.tsx | grep -v "node_modules\|__tests__"` → one definition and one reader each.
- Impact: readers must work out that a guard can never fire; the 533-line chat route loader (over the 500-line review threshold) carries a focus effect and a ref that do nothing.
- Fix: inline the constants: drop the `canUseVoiceInput` guard in `loadExpoAudio` and delete the function and its tests; delete `shouldSilentRefetchChatOnFocus`, the `useFocusEffect` block and `skipNextFocusRef` (its writes at `:307`, `:329`), and the test case.
- Effort: S
- Verify: `grep -rn "canUseVoiceInput\|shouldSilentRefetchChatOnFocus\|skipNextFocusRef" apps/mobile --include=*.ts --include=*.tsx | grep -v node_modules` → empty; `pnpm test -- useChatRouteLoader voiceAudio` and `pnpm typecheck` green.

### DEAD-09 — Test-only code still living in production modules (the class #1914 started moving out)

- Severity: Low
- Confidence: High (each item has no production importer; tests import them)
- Locations:
  - API (5, from the reachability pass): `ThreadSympyExecutor` `apps/api/app/core/sympy_executor.py:373-417` ("for tests (monkeypatch-friendly)", 45 lines of a test double in `core/`, including a no-op `try/except TimeoutError: raise` at `:410-414`); `reset_sympy_executor` `:455-459` (same body as `shutdown_sympy_executor` `:445-452`); `reset_storage_gateway_cache` `apps/api/app/gateways/storage_gateway.py:377-379`; `pending_finalize_count` / `inflight_stream_count` `apps/api/app/modules/chat/finalize_registry.py:183-190` ("Test/introspection helper").
  - Mobile non-reset helpers: `ownsLocalCopy` `apps/mobile/features/attachments/model/localAttachmentFile.ts:33-36` ("Test helper."); `circuitLabelBoxes` `apps/mobile/lib/physics/circuit.ts:477-486` (a layout-overlap check only `lib/physics/__tests__/circuit.test.ts` runs, the same kind of helper as `layoutChecks.ts`, which #1914 moved next to its tests).
  - Mobile module-state reset hooks exported only for tests (12): `features/attachments/model/attachmentIndexStatus.ts:172`, `features/attachments/model/galleryLayout.ts:39`, `features/attachments/model/pendingComposerAttachment.ts:25`, `features/chat/model/composerDraftReset.ts:16`, `features/speech/model/speechRate.ts:36`, `features/speech/model/ttsPreference.ts:35`, `lib/appearancePrefs.ts:47`, `lib/appearanceRuntime.ts:19`, `lib/haptics.ts:60` (`resetHapticsAvailabilityForTests`), `lib/math/svgMath.ts:192` (`setSvgMathRendererForTest`), `lib/streamingDraftStore.ts:32`, `lib/webViewMountQueue.ts:82` (all under `apps/mobile/`).
  - Mobile barrel entries read only by tests (43): `apps/mobile/lib/math/keyboardSymbols.ts:1-31` (7: `MATH_PAD_KEYS`, `SYMBOL_A11Y`, `isCursorInsideInlineMath`, `findFracSlots`, `findLognSlots`, `findNrootSlots`, `PAD_ROWS`), `apps/mobile/lib/physics/simulation/index.ts:14-78` (35 names; #1914 already dropped 13 type re-exports from this barrel), `apps/mobile/lib/markdown/preprocess.ts:74` (`isPipeTable`).
- Evidence: API: `python3 -I scratch-dead/pyreach.py apps/api` → exactly these 5 plus `WORKOUT_PROMPT_SHORT` unreached from production (`scratch-dead/pyreach2.txt`). Mobile: `python3 -I scratch-dead/tsexports.py apps/mobile` (resolves `@/` and relative imports, follows barrels, treats `app/` routes as entries, does not treat tests as entries) → `TEST-ONLY` rows in `scratch-dead/tsexports.txt`. knip cannot see these because it counts test files as entry points.
- Impact: small, but it is production surface whose only consumer is the test suite; the API test double sits in `core/`, and the reset hooks invite tests to depend on module-level state instead of injecting it.
- Fix: move `ThreadSympyExecutor` into `tests/` (the `thread_sympy_executor` fixture already wraps it) and drop `reset_sympy_executor` for `shutdown_sympy_executor`/`set_sympy_executor(None)`; move `circuitLabelBoxes` and `ownsLocalCopy`'s assertion into test helpers; keep the reset hooks only where module state cannot be injected and mark them with a `__forTests` suffix convention, or put them behind one `lib/testing/resets.ts`; drop the test-only barrel entries and import the defining modules in those tests.
- Effort: S
- Verify: re-run `pyreach.py` → 0 unreached; re-run `tsexports.py` → no `TEST-ONLY` rows except agreed reset hooks; `uv run pytest` and `pnpm test` green.

### DEAD-10 — 6.3 MB of vendored JS/CSS compiled into the app's JS bundle as string constants

- Severity: Medium (real bundle weight shipped on every install and every OTA update for features most sessions never open; not dead, but bloat in how it ships)
- Confidence: High for sizes and static imports; Medium for the share of the final bundle (no build was run; measure as below)
- Locations (bytes, from `wc -c`; all generated by `scripts/vendor-cdn.mjs`):
  - `apps/mobile/lib/vendor/mermaidMinJs.ts` 3,406,171 ← static `import` in `apps/mobile/components/rich/MermaidBlock.tsx:25`
  - `apps/mobile/lib/vendor/pdfWorkerMinJs.ts` 1,108,931 and `pdfMinJs.ts` 324,139 ← `apps/mobile/lib/pdfPreviewHtml.ts:4-5`
  - `apps/mobile/lib/vendor/vegaMinJs.ts` 526,284, `vegaLiteMinJs.ts` 258,686, `vegaEmbedMinJs.ts` 63,245 ← `apps/mobile/lib/chartPreviewHtml.ts:13-15`
  - `apps/mobile/lib/vendor/katexCss.ts` 369,142 (KaTeX CSS with 20 base64 woff2 fonts) ← `apps/mobile/lib/printDocument.ts:6`, used only when a reply is exported to PDF/printed (`features/chat/model/exportMessagePdf.ts:4`)
  - `apps/mobile/lib/vendor/smilesDrawerMinJs.ts` 256,815 ← `apps/mobile/lib/chemistry/smilesDrawerHtml.ts:7`
  - Total 6,313,413 bytes.
- Evidence: `wc -c apps/mobile/lib/vendor/*.ts`; `grep -rn "lib/vendor/" apps/mobile/{components,lib,features} | grep -v __tests__` → the six top-level `import { … } from "@/lib/vendor/…"` lines above (no `require()` inside a render path, no asset loading). Metro includes every statically imported module in the single bundle; Hermes keeps the strings in the bytecode the app maps at start, and `expo-updates` re-downloads the whole bundle on every update (assets, unlike the bundle, are fetched only when their hash changes).
- Impact: install size and OTA payload carry 6.3 MB (uncompressed) that only Mermaid, Vega, PDF preview, SMILES and print use; 369 KB of fonts ride along for the rare PDF export. This is likely the largest single block in the bundle.
- Fix: ship each vendor file as an asset (`.js`/`.css` files under `assets/vendor/` registered in `metro.config.js` `assetExts`, loaded once with `expo-asset` + `expo-file-system` when the block first renders, or referenced from the WebView by file URI), keeping the pinned versions and hashes from `lib/vendor/manifest.json`. Load `katexCss` only inside the print path. Keep `scripts/vendor-cdn.mjs` as the generator.
- Effort: M
- Verify: `npx expo export --platform ios --dump-sourcemap` then `npx source-map-explorer` on the bundle, before and after (expect ≈6 MB smaller); Mermaid, chart, PDF preview, SMILES and PDF export still render in a dev build (`docs/QA_MATRIX.md` rows).

### DEAD-11 — Expo-Go-only fallbacks ship in every store build (`react-native-render-html`, `@expo/dom-webview` path)

- Severity: Low (JS weight and an unmaintained dependency tree for a path a store build never takes)
- Confidence: Medium-High (the gate is code-certain; exact bundle bytes need a build)
- Locations:
  - `apps/mobile/lib/webView.ts:36-65` picks `react-native-webview` when its native module is linked (`isRncWebViewLinked`, `:21-33`), else `@expo/dom-webview` (`:52-63`). `react-native-webview` is a direct dependency (`apps/mobile/package.json`), so every dev and store build links it; the fallback serves Expo Go only (CLAUDE.md: "in Expo Go the preview falls back to static HTML").
  - `apps/mobile/components/HtmlPreviewModal.tsx:18` imports `react-native-render-html` statically for `StaticHtmlPreview` (`:244-277`), rendered only when `getPreviewWebView()?.mode !== "rnc"` (`:319-321`, `:354-366`); `apps/mobile/lib/htmlForInlinePreview.ts` (163 lines, one export, `:149`) exists only to prepare markup for it.
  - Dependency pulled in for this: `react-native-render-html@6.3.4` (2022; its `src` is 708 KB) with `@native-html/transient-render-engine`, `@native-html/css-processor`, `ramda@0.27`, `urijs`, `@jsamr/counter-style`, `@jsamr/react-native-li`, `stringify-entities`, and a peer on `@types/react-native@0.73` (pnpm store names).
- Evidence: `grep -rn "react-native-render-html" apps/mobile/{components,features,lib,app} | grep -v __tests__` → `HtmlPreviewModal.tsx:18` only (plus a comment in `htmlForInlinePreview.ts:148`); `grep -rlw htmlForInlinePreview apps/mobile/{components,features,lib,app} | grep -v __tests__` → `HtmlPreviewModal.tsx` and the file itself; `grep -rn "getPreviewWebView" apps/mobile/{components,features,lib}` → the mode checks above.
- Impact: every store build carries a full HTML-to-native renderer and its CSS engine that no store user can reach; it is also the only consumer of several old transitive packages that Dependabot and the license generator must keep tracking.
- Fix: in store builds show the existing "Open in browser" path when the WebView is missing (it never is), and drop `StaticHtmlPreview`, `lib/htmlForInlinePreview.ts` (and its tests) and the `react-native-render-html` dependency; or move the fallback behind `__DEV__`/`isExpoGo()` in a file Metro only resolves in development. Treat the `expo-dom` branch of `getPreviewWebView` the same way.
- Effort: S
- Verify: `grep -rn "react-native-render-html" apps/mobile --include=*.ts --include=*.tsx | grep -v node_modules` → empty; `pnpm test` green; bundle diff via `npx expo export --dump-sourcemap` + `source-map-explorer`.

### DEAD-12 — Android builds carry every UI and math font twice (about 1.8 MB)

- Severity: Low (binary size on Android)
- Confidence: Medium-High (configuration is certain; bytes are from the files, not from a built APK)
- Locations:
  - `apps/mobile/app.json:119-175`: the `expo-font` config plugin embeds 8 families natively on Android only: `KaTeX_Main`, `KaTeX_MathItalic`, `KaTeX_AMS`, `SpaceMono` (from `assets/fonts/`) and 4 Source Sans 3 weights (from `node_modules/@expo-google-fonts/source-sans-3/`) — 1,765,284 bytes. Added 2026-10-01 (`de72edfda`) to fix Android weight lookup.
  - `apps/mobile/app/_layout.tsx:100-114`: `useFonts` still loads the same families at runtime from Metro assets on both platforms (`katex/dist/fonts/*` ×4, Source Sans 3 ×7, `@expo-google-fonts/space-mono`) — 2,395,852 bytes of `require()`d `.ttf` that Metro copies into the Android build next to the embedded ones.
  - Skia reads a third set by path: `assets/fonts/KaTeX_Main-Regular.ttf` (`components/rich/skia/SkiaNumberLineChart.tsx:73`, `SkiaInequalityGraphChart.tsx:47`, `SkiaGraphExplorer.tsx:99`, `components/rich/simulation/useSimulationScene.ts:51`), `KaTeX_Math-Italic.ttf` (`useSimulationScene.ts:52`), `SpaceMono-Regular.ttf` (`TrajectoryChart.tsx:43`, `SkiaMoleculeCanvas.tsx:52`, `useSimulationScene.ts:48`). `assets/fonts/KaTeX_{Main-Regular,Math-Italic,AMS-Regular}.ttf` are byte-identical to `node_modules/katex/dist/fonts/…` (`cmp`), so iOS also bundles KaTeX_Main and Math-Italic twice under two paths.
- Evidence: `python3` over `app.json` + `app/_layout.tsx` (sizes above); `cmp apps/mobile/assets/fonts/KaTeX_Main-Regular.ttf apps/mobile/node_modules/katex/dist/fonts/KaTeX_Main-Regular.ttf` → identical (same for AMS and Math-Italic).
- Impact: roughly 1.8 MB of duplicate fonts in every Android download, plus a second registration of each family at runtime that can mask whether the native embedding (the actual weight fix) is working.
- Fix: embed on both platforms through the plugin (`ios.fonts` beside `android.fonts`), delete the runtime `useFonts` entries for the embedded families (keep only `KaTeX_Size1` and the italics, or embed them too), and point `_layout`/Skia at one path per face (`assets/fonts/`).
- Effort: S
- Verify: build an Android release (`eas build -p android --profile preview` or `expo export:embed`) and compare `unzip -l` font entries before and after; QA the Android weight and math rendering rows in `docs/QA_MATRIX.md`.

### DEAD-13 — Small leftovers: a prompt constant orphaned by the audited commit, and 41 exports used only in their own file

- Severity: Low
- Confidence: High
- Locations:
  - `WORKOUT_PROMPT_SHORT` `apps/api/app/services/workout.py:310-315`: its last reader, `apps/api/app/modules/physics/reply_policy.py:3`, switched to `PHYSICS_WORKOUT_PROMPT_SHORT` in #1920 (`d2ec42b0`, the audited head); the comment at `workout.py:324` ("the short rule above has no room for them") now points at it too.
  - knip "unused exports" in app code, each used inside its own file only: `composerTextLabel` `apps/mobile/lib/math/draftText.ts:79`, `insideInlineMath` `draftText.ts:110`, `DIAGRAM_KINDS` `apps/mobile/lib/physics/diagramKind.ts:6`, `READ_BACK_SUBJECTS` `apps/mobile/lib/scanner/readBack.ts:5`, `stackHeaderOptions` `apps/mobile/lib/stackHeader.ts:8`; and all 36 knip "unused exported types" (e.g. `lib/physics/circuit.ts:206-219` ×5, `lib/chemistry/scene.ts:7-45` ×6, `lib/math/arithmeticBlock.ts:3-83` ×6, `lib/physics/rayScene.ts:61-71` ×3; full list `tmp/code-audit/raw/knip.txt`). #1914 dropped `export` from 12 values and 23 types of this kind; these remain.
- Evidence: `python3 -I scratch-dead/pyreach.py apps/api` → `workout.py:311 WORKOUT_PROMPT_SHORT test_files=0`; `git grep -n WORKOUT_PROMPT_SHORT d2ec42b0~1 -- apps` shows the reader that #1920 removed. For each knip name, `grep -c "\b<name>\b" <file>` ≥ 2 and `grep -rlw <name> apps/mobile/{app,components,features,lib,hooks,contexts,ui}` finds no other file (`scratch-dead/knip_exports_check.txt`: 41 rows, every one `in_file≥2 other_files=0`).
- Impact: noise; a stale prompt constant invites the next physics/maths edit to reuse the wrong rule.
- Fix: delete `WORKOUT_PROMPT_SHORT` and reword the `:324` comment; drop `export` from the 41 names. Consider running knip in Mobile CI (exports and types only, `vendor/**` ignored) so this stays at zero.
- Effort: S
- Verify: `npx knip --include exports,types` → only the vendored `image-size` entries; `grep -rn WORKOUT_PROMPT_SHORT apps/api` → empty.

### DEAD-14 — The Expo template's web target is still wired into the phone app

- Severity: Low
- Confidence: Medium (nothing in the repo runs it and it likely cannot start; confirm nobody uses `pnpm web`)
- Locations:
  - `apps/mobile/package.json` scripts `"web": "expo start --web"`; dependencies `react-dom` `19.2.3` and `react-native-web` `~0.21.0` (initial commit `7e31659b8`, 2026-06-24, Expo template).
  - `apps/mobile/app/+html.tsx` ("This file is web-only … root HTML for every web page during static rendering").
  - `apps/mobile/app.json:57-61` `web` block (`bundler`, `output: "static"`, `favicon` → `apps/mobile/assets/images/favicon.png`).
  - `Platform.OS === "web"` guards: `apps/mobile/components/PushNotificationBootstrap.tsx:39`, `apps/mobile/features/todos/model/todoReminders.ts:35`, `apps/mobile/lib/pushNotifications.ts:25,31,128,162`, `apps/mobile/lib/productAnalytics.ts:8`, `apps/mobile/lib/purchases.ts:55`.
- Evidence: `CLAUDE.md` Architecture: `apps/web` is the web client ("Vite slice 1 … not react-native-web"). `grep -rn "pnpm web\|expo start --web" CLAUDE.md docs scripts` → empty. `react` was bumped to `19.3.0` on 2026-10-11 (`c3eb1ca2e`) while `react-dom` stayed pinned at `19.2.3` (`b699913a4`, #528); React requires the two to match exactly at runtime, so the web target cannot have been started since then.
- Impact: a dependency pair that has already drifted apart unnoticed, a web-only route file, and branches for a platform the phone app does not target; misleads readers about where the web client lives.
- Fix: confirm with the team, then remove the `web` script, `react-dom`, `react-native-web`, `app/+html.tsx`, the `web` block and `favicon.png`, and the `Platform.OS === "web"` branches (keep `ios`/`android` handling). Keep `@expo/dom-webview` decisions with DEAD-11.
- Effort: S
- Verify: `pnpm install && pnpm typecheck && pnpm test && pnpm lint` green; `npx expo-doctor` clean; `grep -rn "Platform.OS === \"web\"" apps/mobile/{components,features,lib}` → empty.

## Looked wrong, actually fine

- vulture `apps/api/app/modules/math/tools/school/complex.py:77` "unreachable code after while": the loop is `while True: for …: if …: break  else: break`; the `for…else: break` exits the `while`, so the code after it runs.
- vulture's 111 test-file hits: pytest fixtures requested by parameter for their side effect (`thread_sympy_executor`, `stream_offline_io`, `web_search_registered`, `sympy_registered`, `image_tools_registered`, `production_declines`), fake signatures that must match the real API (`ex`, `attribute_names`, `chunk_size`), and `raise …; yield` / `if False: yield` async-generator idioms. (`@pytest.mark.usefixtures` would quiet the fixture ones; not dead.)
- knip unused files: `apps/mobile/lib/webrtcStub.js` (resolver alias, `metro.config.js:17,32`); `plugins/googleSignInPodfile.js`, `plugins/withoutAppleSignIn.js` (config plugins, `app.config.ts:35,49`); `scripts/check-url-dependencies.cjs` (run by `lib/__tests__/urlDependencies.test.ts:6`); `vendor/image-size/**` (DoS-patched copy wired as a pnpm override, `package.json:130`, `vendor/image-size/package.json` description).
- knip/depcheck dependencies: `expo-device` (read through `requireOptionalNativeModule("ExpoDevice")` in `lib/deviceSession.ts` and `lib/expoRuntime.ts:36-44`; the package must stay for autolinking); `react-native-vision-camera-worklets` (required at runtime by `react-native-vision-camera/lib/hooks/useFrameOutput.js` via `third-party/VisionCameraWorkletsProxy.js`); `@babel/plugin-transform-dynamic-import` (`babel.config.js:8`); `lucide-static` (`scripts/generate-icons.mjs`, `generate-licenses.mjs`); `@config-plugins/react-native-webrtc` (`app.json` plugin); `@react-native/metro-config` (peer of `@react-native/community-cli-plugin` and `react-native-worklets`); `@types/jest` (ambient test types).
- deptry DEP002: `asyncpg` (SQLAlchemy driver, `core/database_url.py:22`), `websockets` (uvicorn WebSocket implementation), `python-multipart` (`request.form()`, `modules/speech/api.py:242`), `cryptography` (PyJWT ES256, `gateways/apple_revoke.py:65`), `defusedxml` (openpyxl parses XLSX through defusedxml whenever it is installed, `openpyxl/xml/__init__.py:28-42`). DEP003 (`pydantic`, `starlette`, `botocore`, `mpmath` used directly but only declared transitively) is dependency hygiene, not bloat.
- Settings `<base>_plus` / `<base>_pro` (16 fields in `core/settings/plans.py`) have no literal reader: `modules/billing/entitlements.py:90-95` reads them with `getattr(settings, setting_name(name, plan))`. Every other settings field is read by name.
- The 14 `Protocol`s in `apps/api/app/modules/chat/turn_deps.py` each have one production implementation: that is the documented `ChatTurnDeps` test seam (CLAUDE.md "The chat loop"), not a speculative interface. `StorageGateway` has two implementations, `ToolAdapter` four, and `TavilyBudget` keeps `gateways/` free of module imports.
- Always-on kill switches (`chemistry_enabled`, `math_word_problems_enabled`, `attachment_ocr_enabled`, `chat_history_rag_enabled`, `image_search_enabled`, `history_compression_enabled`, `semantic_memory_enabled`, `web_search_fallback_enabled`, …) guard with one early return each, the pattern `docs/ARCHITECTURE.md:71` prescribes; none hides a large alternative implementation (contrast DEAD-02).
- `apps/api/app/modules/suggestions/` (61 lines) and `Suggestion.dismissed` (read only by export): deliberate expand/contract from #1913, recorded in `docs/ARCHITECTURE.md:130`.
- `apps/api/app/services/mcp/__init__.py` ("legacy" in CLAUDE.md) is the tool-registration composition root.
- `needs_web_search` (`modules/web_search/detection.py:294`, docstring "tests and legacy callers") has five production callers (`turn_prep/intents.py:61`, `turn_prep/augment.py:178,182`, `tool_loop/parts.py:47`, `web_search/subject.py:98`); only the docstring is stale.
- `speech-tts-fast-model` "Legacy alias" (`apps/api/app/models/model_catalog.py:339-347`) is still sent by the phone (`features/speech/model/pronunciation.ts:459`).
- `DELETE /auth/me` optional body ("Older apps send no body", `modules/account/api.py:456`): the current phone also omits it when there is no Apple code (`features/account/api.ts:39-48`).
- Compat for *stored* messages (phone `components/rich/CalloutBlock.tsx:23` legacy ```tip, `lib/markdown/preprocessNormalize.ts:230`, `lib/messageAttachments.ts:128`, `lib/physics/simulation/arrows.ts:57`; API `services/answer_fence.py:38-40` `label: answer`) reads rows already in the database; it stays while those rows exist.
- i18n: the 4 keys with no literal (`rich.diagram_a11y_parallel|series`, `rich.diagram_source_ac|battery`) are built as `` `rich.diagram_a11y_${node.kind}` `` in `lib/physics/circuit.ts`; the other 927 keys are referenced.
- `assets/fonts/KaTeX_AMS-Regular.ttf` has no JS reference but is embedded on Android by the `expo-font` plugin (`app.json:139`).
- `features/drafts/model/openGmailCompose.ts` is not the removed Gmail integration: it opens the email-draft card in the Gmail app by URL; `PATCH /chats/{id}/messages/{id}/email` persists that card (`features/chat/api.ts:119`).
- Dev/ops routes with no app client are intended: `/chats/usage/today/reset` (`scripts/battery.py:164`) and `/auth/me/pro-dev` both call `require_dev_privilege_access`; `/admin/dlq*`; `/legal/delete-account` is the store-listing deletion URL; `/webhooks/revenuecat` is called by RevenueCat.
- `_MetaParser.handle_starttag` (`modules/link_preview/service.py:67`) is an `HTMLParser` hook. All 424 production methods are referenced by name.
- `lib/vendor/*`: all eight vendored bundles are used in production (DEAD-10 is about how they ship).

## Open questions for the team

1. Are any TestFlight/internal builds from before 2026-09-04 still in testers' hands? If not, DEAD-07 and the DEAD-01 tombstones can go before the first store build without any migration.
2. Is the web-search classifier coming back? If not, delete it; if so, turn it on in production. Either way the behavior harness should run the production setting (DEAD-02).
3. When does the reminder-card kill switch (`reminder_proposals_enabled`) end, taking the todo-sync LLM job with it?
4. Is `GET /todos` (offset list, "forward-compatible for the web client") planned for `apps/web`? The web slice does not call it today.
5. Should `apps/mobile` keep `expo start --web` at all (DEAD-14)?
6. Two TeX engines ship in the phone: `mathjax-full` (on-screen SVG, `lib/math/svgMath.ts:113-118`, lazily imported but still in the bundle) and `katex` + the 369 KB `katexCss` (print only, `lib/printDocument.ts:3,6`). Could print reuse the MathJax SVG output and drop KaTeX JS and CSS (the KaTeX font files stay for native layout)?
7. knip reports `expo-system-ui` as an unlisted dependency: `app.json:12` sets `userInterfaceStyle: "automatic"`, which on Android needs `expo-system-ui`. A missing dependency, not bloat; worth a dark-mode check on Android.
8. Memory seams (DEAD-04): typed dependency object like `ChatTurnDeps`, or tests patching the defining modules?
9. Is streaming TTS on the roadmap (`/speech/tts/stream` "stays server-ready")? If yes, re-add the route together with its client.
