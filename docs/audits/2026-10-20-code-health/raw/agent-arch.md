# Dimension A — Architecture and boundaries (ARCH-)

Audited tree: `/home/user/recall-audit` at `d2ec42b0`. Read-only. Scripts and raw outputs:
`/home/user/recall/tmp/code-audit/raw/scratch-arch/` (`outside_modules.py`/`.out`,
`hidden_cycles_noparents.py` + `hidden_cycles_np.out`, `component_graph.py` + `component_{load,all}.out`,
`scc_full_noparents.py`, `services_consumers.py`, `txn_owner.py`/`.out`, `txn_uncond.py`/`.out`,
`side_effect_before_commit.py`, `barrel_users.py`, `orm_barrel.py`, `shared_repo_writes.py`,
`infra_reach.py`, `path_find.py`, `mobile_owners.py`, `comp_importers.py`, `shared_to_feature.py`,
`cross_feature.py`, `mobile_components.py`, `ui_closure.py`, `doc_paths.py`). All parse source only
(Python `ast`, regex over TS imports); none imports the app.

Judged against the audited tree's own `CLAUDE.md` (which is newer than the copy in the main checkout:
e.g. it already drops the `/suggestions` routes), `docs/ENGINEERING_STANDARDS.md`, `docs/ARCHITECTURE.md`,
`docs/SCALING.md`, and the ES tickets. Composition roots that ARCHITECTURE.md sanctions (main.py, process
bootstrap, `background/handlers.py`, `services/mcp/__init__.py`, `models/orm/__init__.py`) and the
documented "leaves import chat's turn cues through the `app.modules.chat` package" (ARCHITECTURE.md §13)
are not reported as violations.

## Metrics

| Measure | Value |
|---|---|
| API production code | 955 `.py` files, 183,369 lines; 18 modules; `services/` root = 40 files + `law_binding/`, `mcp/`, `quota/` |
| Import bindings from outside `modules/` into `app.modules.*` | 127, in 20 files |
| ... that bypass the public surface (`api/schemas/service/crud`, `_EXPORTS`, `_MODULE_EXPORTS`) | 51 = 25 in sanctioned composition roots + **26 elsewhere** (`services/routing.py` 13, `services/subject_solving.py` 9, `services/solving.py` 2 type-only, `background/*_scheduler.py` 2) |
| Function-local `app.*` imports in production | 640 (modules 586, services 40, gateways 8, models 4, core 2) |
| ... that close a load-time cycle (target already reaches importer at load) | **24** (modules 18, of which `modules/math` 15; gateways 4; core 1; services 1). Tickets doc says "about 8" |
| File-level SCCs if function-local imports count | `modules/math` 49 files (+ 6, 5, 5, 4 …); zero at load time |
| Component-level SCC (modules + services files), all imports | **19 components**: 13 modules (account, attachments, billing, chat, chemistry, home, images, math, memory, notifications, physics, todos, web_search) + 6 services (conversation_reference, quota, routing, scan_read, subject_solving, thinking_effort) |
| Component-level SCCs, load-time imports only | {todos, home}; {account, chat, chemistry, images, math, physics, web_search, services.subject_solving} |
| `services/` root files with exactly one consumer | 10 files, 1,682 lines (7 of them chat-only) |
| Repository write functions with a `commit` flag / that always commit | 27 / 18 |
| `home_service.invalidate_home_cache` call sites outside `modules/home` | 19 (todos 16, memory 2, account 2) |
| Chat-message writers through shared `repositories/messages.py` | 4 modules (chat, images, speech, todos) |
| Mobile cross-feature value imports | 57, all into internals (model 36, components 12, hooks 6, context 3); no feature has a public index |
| Mobile shared → feature imports (`components/`, `hooks/`, `contexts/`, `lib/`; `lib/api.ts` barrel excluded) | 44 edges from 23 files |
| Mobile component-level SCC | 16 nodes: 11 of 12 features (all but auth) + components, contexts, hooks, lib, ui (ui only via lib's grab-bag; its own file closure is clean) |

---

### ARCH-01 — Code outside `modules/` is not held to the public-surface rule; 26 imports in `services/` and `background/` reach 22 internal module files
- Severity: Medium
- Confidence: High
- Locations:
  - apps/api/app/services/routing.py:219, :220 (3 names), :225, :292 (2 names), :309, :448, :449, :450, :451, :510 — into `chat.continuation_subject`, `chat.prompt_constants.{routing,teaching,writing_kind}`, `chat.json_output`, `math.match.{arithmetic,discrete,scan,written}`
  - apps/api/app/services/subject_solving.py:53, :77, :93, :99, :281, :312, :314, :338, :339 — into `chemistry.extract`, `chemistry.input_text`, `chemistry.species`, `math.tools.school.curve_points`, `math.tools.direct`, `chat.prompt_constants.visuals`, `chemistry.reading`, `chemistry.block`, `chemistry.direct`
  - apps/api/app/services/solving.py:27, :29 (TYPE_CHECKING: `math.response_intent`, `math.solve.key_steps`)
  - apps/api/app/background/push_scheduler.py:17, apps/api/app/background/email_reminder_scheduler.py:17 (`notifications.push` / `reminder_email`, not exported)
  - the rule only walks modules: apps/api/app/tests/architecture/test_product_module_boundaries.py:349-363 (`modules_root.rglob("*.py")`)
  - declared surfaces it bypasses: apps/api/app/modules/chemistry/__init__.py:32 (`_MODULE_EXPORTS = ("context", "fence", "followup", "reply_policy", "request")`), apps/api/app/modules/math/__init__.py:44-55, apps/api/app/modules/chat/__init__.py:19-44 (none of `is_personal_advice_question`, `is_writing_deliverable_request`, `is_teaching_request`, `is_learning_plan_request`, `is_json_request`, `is_pure_continuation` is exported)
- Evidence: `outside_modules.out` — 127 bindings, 51 bypass the surface; the 26 outside composition roots are listed above. Every routing and subject_solving one is function-local, so `test_import_cycles` (load-time only) does not see them either:
  ```
  services/subject_solving.py:93   from app.modules.chemistry.species import parse_reaction
  services/subject_solving.py:338  from app.modules.chemistry.block import VerifiedChemistry
  services/routing.py:450          from app.modules.math.match.scan import prepare
  services/routing.py:220          from app.modules.chat.prompt_constants.routing import (...)
  ```
  The dispatcher's own docstring says it belongs to chat: "The registry lives here, with chat, so a subject package never decides which peer owns a turn" (services/subject_solving.py:3-4). Churn: subject_solving.py 21 commits (7 between 2026-10-12 and 10-19), routing.py 25 commits since September.
- Impact: ENGINEERING_STANDARDS "one subject imports another only through its public files … never its solvers or extractors" and "a change to chemistry must not break physics or maths" are enforced for code inside `modules/` but not for the dispatcher and router that sit between the subjects on every turn. A rename inside `chemistry/species.py` or `math/match/scan.py` (ES-13/ES-34-style splits happen weekly) breaks a function-local import that only a test exercising that branch catches.
- Fix: (1) run `_foreign_module_import_violations` over every production file outside `modules/`, with an explicit allowlist of the five composition roots; (2) each subject exports its `SubjectAdapter` (augment, direct reply, the detection predicates the dispatcher needs) from `service.py`/`_EXPORTS`, and `subject_solving` imports only those — or move the dispatcher into `modules/chat/` (its docstring's own claim) so the existing rule applies; (3) chat exports the six routing cues (or routing moves into chat, ARCH-02); (4) the two scheduler cycles move to `modules/notifications/scheduler.py` (a file name ARCHITECTURE.md lists), `background/` only wires them.
- Effort: M
- Verify: new architecture test `test_code_outside_modules_imports_modules_only_through_public_files` (allowlist = 5 roots) passes; `outside_modules.py` reports 0 non-root violations.

### ARCH-02 — Model routing makes billing depend on chat, maths and physics; picking a model runs the physics solver
- Severity: Medium
- Confidence: High
- Locations: apps/api/app/modules/billing/plan.py:10 (`from app.services import model_catalog, routing`), :88-117 (`resolve_user_model(user, content, …)` → `routing.resolve_alias_in_pool`), :154; apps/api/app/services/routing.py:217-227, :277-327, :390-416 (`@lru_cache(maxsize=128) def _physics_solves` → `solve_physics(intent)` at :405), :419-439, :442-466, :505-517; callers on the turn's load path: apps/api/app/modules/chat/turn_load.py:260, apps/api/app/modules/chat/turn_prep/persist.py:72; and again per turn via apps/api/app/services/thinking_effort.py:16, :59.
- Evidence: chain `chat.turn_load → billing.plan → services.routing → (function-local) chat.prompt_constants.*, chat.json_output, chat.continuation_subject, math.match.*, physics.extract_physics_intent + physics.solve_physics`. Component graph (`component_all.out`): `modules.chat → modules.billing → services.routing → modules.chat`. Auto is the default (`is_auto_enabled` returns True when `enabled_models is None`, billing/plan.py:68-71), so this runs for most users:
  ```python
  # services/routing.py:390
  @lru_cache(maxsize=128)
  def _physics_solves(content: str) -> bool:
      from app.modules.physics import extract_physics_intent, solve_physics
      ...
      solve_physics(intent)
  ```
- Impact: plan policy (CLAUDE.md: "decided in one place, `modules/billing/entitlements.py`") lives beside per-message classification: `billing/plan.py` cannot load or be tested without chat's prompt classifiers and two subject pipelines, and the per-message model choice — a chat-turn decision — is split between a billing file and a services file. Routing does a full physics extraction + verified solve on the turn's critical path before `turn_prep` does the same question again (the LRU only helps the repeated calls inside one turn).
- Fix: billing keeps pool policy (`model_pool`, `allowed_model_ids`, override validation); `route_chat_model` / `resolve_alias_in_pool` / `message_needs_thinking` with `routing_signals.py` and `rate_problems.py` move to `modules/chat/model_routing.py`, which composes pool + routing; routing reads the turn's subject verdict (`turn_prep/intents.py` plan / `detect_subject`) instead of running the solver.
- Effort: M
- Verify: a sys.modules test that `import app.modules.billing.plan` loads no `app.modules.chat|math|physics`; the component graph shows no billing → chat path; turn timing shows no physics solve before `turn_prep`.

### ARCH-03 — `services/` root keeps absorbing code only one module uses
- Severity: Low
- Confidence: High
- Locations (file → its only consumer):
  - apps/api/app/services/reply_labels.py (108 lines, added in HEAD d2ec42b0) → apps/api/app/modules/chat/finalize_passes.py:65
  - apps/api/app/services/working_check.py (317) → apps/api/app/modules/chat/finalize_subjects.py:36
  - apps/api/app/services/recurring_pay.py (345) → apps/api/app/modules/chat/turn_prep/instant.py:29
  - apps/api/app/services/context_window.py (221) → modules/chat only: prompt_window.py:24, turn_resources.py:26, compaction.py:13, prompt_context.py:21, summarize.py:7, turn_prep/persist.py:28, turn_settle.py:31
  - apps/api/app/services/mermaid_sanitize.py (65) → apps/api/app/modules/chat/finalize_text.py:21
  - apps/api/app/services/prompt_inject.py (15) → apps/api/app/modules/chat/prompt_builder.py:39, tool_loop/forced_search.py:66
  - apps/api/app/services/topic.py (75; the chat-title job, imports chat titles at :7-8) → apps/api/app/background/handlers.py:40
  - apps/api/app/services/routing_signals.py (283), apps/api/app/services/rate_problems.py (58) → services/routing.py only
  - apps/api/app/services/calendar_facts.py (195) → services/time_context.py only
- Evidence: `services_consumers.py` output; 1,682 lines. Of the 15 `services/` root files created since 2026-10-01, 5 have one consumer (working_check 10-15, rate_problems 10-17, calendar_facts 10-18, routing_signals 10-19, reply_labels 10-20) — all after the rules "What is left at services/ root is genuinely cross-cutting … New chat-loop code belongs in modules/chat/" (CLAUDE.md:148, in place since 2026-08-12/09-13) and after the chat migration (fc4d53ce5, 2026-10-11). ARCHITECTURE.md lists "A finalize pass | finalize_passes.FINALIZE_PASSES" as chat's seam; reply_labels is a finalize pass.
- Impact: code there is outside every module boundary test (ARCH-01), so chat's finalize and prompt helpers are not chat's when chat's boundary is checked, and ARCHITECTURE.md's "if a product feature breaks, its module … is the first place to open" sends readers to the wrong folder.
- Fix: move the seven chat-only files into `modules/chat/` (topic → chat's titles/jobs), routing_signals/rate_problems with routing (ARCH-02), calendar_facts beside time_context; add a CI check that a `services/` root file is imported by ≥ 2 owners or carries a recorded reason.
- Effort: S
- Verify: `services_consumers.py` shows no SINGLE-CONSUMER row outside a reasoned allowlist; moved paths added to `RETIRED_LEGACY_MODULES`.

### ARCH-04 — Infrastructure reaches product modules through the `models.schemas` / `models.orm` barrels; a generic LLM gateway holds memory's rules
- Severity: Medium
- Confidence: High
- Locations: apps/api/app/models/schemas/__init__.py:44-68 (re-exports 19 names from `modules.attachments/memory/todos.schemas`); apps/api/app/gateways/structured_completion.py:21-27 (imports `MEMORY_REPLY_MAX_LENGTH, MemoryFactOp, MemoryFactUpdateResult, MemorySectionItem, MemorySectionUpdateResult` through the barrel), :127-131 (`settings.memory_fallback_model_alias` is the fallback for every structured call), :184-192, :197-230 (memory-only partial salvage); apps/api/app/gateways/mock_llm.py:96, :116, :165 (memory and todos result types); apps/api/app/repositories/users.py:9-19, :128-137 (imports `Memory, TodoItem, Suggestion, Attachment` via `app.models.orm` and deletes each module's rows); the check: apps/api/app/tests/architecture/test_module_boundaries.py:43-50 (literal `app.modules` prefix only).
- Evidence:
  ```python
  # gateways/structured_completion.py:184
  except Exception:
      if schema is MemoryFactUpdateResult and isinstance(data, dict):
          fact_partial = _parse_memory_facts_partial(data)
  ```
  `barrel_users.py`: outside the owning modules the barrel's module re-exports are imported only by gateways/structured_completion.py:21 and gateways/mock_llm.py:96/116/165. apps/api/app/tests/modules/math/test_math_word_problem.py:486 pins `aliases == ["gpt-6-luna", "fallback-memory-model"]`: maths' word-problem translator falls back to the memory model.
- Impact: "gateways/ must not import modules" (CLAUDE.md) and ARCHITECTURE.md's "An external API … imports no module" hold in text only; a memory schema change can break the generic structured-output gateway that every LLM job uses, and every structured job silently falls back to memory's fallback alias. ARCHITECTURE.md says the migration re-exports were deleted; the schema barrel kept three modules' worth.
- Fix: put the salvage behind a schema hook (e.g. an optional classmethod `salvage_partial(data) -> Self | None` defined in `modules/memory/schemas.py`, looked up with `getattr`) or let memory pass a salvage callable; rename the fallback setting to a neutral name or a routing lane; delete the module re-exports from `models/schemas/__init__.py` (10 module files in attachments, memory and todos import their own schemas through it today); make the infrastructure test resolve `from app.models.schemas import X` / `from app.models.orm import X` to the defining module.
- Effort: M
- Verify: the extended infrastructure test fails on today's tree and passes after; `rg -n "Memory" apps/api/app/gateways/structured_completion.py` is empty.

### ARCH-05 — "Repositories stay private" is met by forwarding facades and exported repositories
- Severity: Low
- Confidence: High
- Locations:
  - apps/api/app/modules/attachments/service.py:1-48 — 13 `_call_through(...)` pass-throughs of `repository`, `chunks_repository`, `jobs`, `lifecycle` (docstring: "They may not import the repository"); imported *as the repository* by apps/api/app/modules/images/generation.py:25, images/search.py:28, images/turn_references.py:13, images/reply_picture.py:23 (`from app.modules.attachments import service as attachments_repo`), which compose `create_pending`/`link_to_message`/`mark_verified(..., commit=False)` into images' own transactions (generation.py:361-411)
  - apps/api/app/modules/todos/__init__.py:12-36 — `_EXPORTS` includes `update_schedule_if_current` (schedule_repository) and `mark_email_sent_if_current` (email_repository); `_MODULE_EXPORTS = ("repository",)`; used by apps/api/app/modules/home/service.py:21, modules/account/export.py:36, modules/notifications/push.py:33 (+ :344-347 writes), modules/notifications/reminder_email.py:20
  - apps/api/app/services/model_catalog.py:1-61 — "Service-facing model catalog compatibility API": 21 re-exports of `models/model_catalog.py` plus `is_available`; production imports split 10 (services path) / 11 (models path); CLAUDE.md:17 and :161 name `services/model_catalog.py`, docs/ARCHITECTURE.md:47 and :127 name `models/model_catalog.py`
- Evidence: CLAUDE.md "Repositories and extractors stay inside the owning module"; ENGINEERING_STANDARDS rule 9 forbids "thin wrappers that only forward their arguments"; ARCHITECTURE.md "The re-exports that let callers move one at a time during the migrations are deleted."
- Impact: the boundary test passes while images writes attachments' rows, notifications writes todos' rows and home/account read todos' tables through its repository — attachments and todos cannot change a table or a repository signature without editing three other modules. One catalog has two import paths and two documented homes.
- Fix: replace pass-throughs with intent-level operations the owner keeps (`attachments.service.attach_generated_image(session, …)` / `link_turn_attachments(session, …)`, documented composable with `commit=False`; `todos.service.mark_reminder_notified(...)`, `todos.service.due_soon_for_home(...)`); reject `repository`/`*_repository` names in any `_EXPORTS`/`_MODULE_EXPORTS`; delete `services/model_catalog.py` (move `is_available` into the catalog with a `mock` flag, or into the gateway) and list it in `RETIRED_LEGACY_MODULES`.
- Effort: M
- Verify: a boundary-test assertion over `_EXPORTS`/`_MODULE_EXPORTS`; `rg -n "as attachments_repo" apps/api/app/modules/images` empty; `test_retired_module_cannot_be_imported[app.services.model_catalog]`.

### ARCH-06 — Hard-coded model ids and second model lists bypass the catalog and the routing lanes
- Severity: Medium
- Confidence: High
- Locations: apps/api/app/modules/math/tools/word_problem.py:30-33 (`_TRANSLATOR_MODEL_ALIAS = "gpt-6-luna"`); apps/api/app/modules/math/tools/llm_extract.py:150 (`model_alias="gpt-6-luna"`); apps/api/app/modules/account/settings_intent.py:21-35 (`_MODEL_NICKNAMES`, `_MODEL_IDS = frozenset({"auto", "free-chat", "smart-chat", "gpt-6-luna", "qwen-3.7-flash"})`); apps/api/app/modules/account/settings_proposal.py:32-38 (`_MODEL_LABELS`: `"free-chat": "Flash"`, `"smart-chat": "Pro"`); apps/api/app/modules/speech/service.py:88, :123 (provider model names `gpt-4o-mini-tts`, `gpt-4o-mini-transcribe`, `gpt-4o-transcribe`). Against: apps/api/app/models/model_catalog.py:141 and :156 (the `label=` display names of `free-chat` and `smart-chat`), :173 (`glm-5.3-flash`), :189 (`glm-5.2`), both selectable (`selectable=True` default, :46); apps/api/app/routers/models.py:30 (`label=m.label` to the phone); apps/mobile/features/account/screens/ModelsSettingsScreen.tsx:113 (`title={option.label}`); the seam apps/api/app/models/routing_lanes.py:1-5, :33-40.
- Evidence: ARCHITECTURE.md:47 "A model alias | One entry in models/model_catalog.py … there is no second list"; CLAUDE.md Seams "Route by capability, never by name"; routing_lanes.py "The aliases routing picks by job: data, changed here and not in routing code, and `test_model_catalog` checks each lane against the capability its job needs" (tests/services/test_model_catalog.py:286). word_problem.py:30 justifies Luna as "the user-facing fast route", but the everyday lane is `qwen-3.7-flash` (routing_lanes.py:34).
- Impact: user-visible: "switch to GLM" in chat finds no model although both GLM entries are in the picker; a chat settings card says "Default model → Flash" / "Pro" while Settings → Models shows the same models under their catalog display names. Maintenance: two maths LLM jobs pin one vendor model outside the lanes, so the lane capability test does not cover them and retiring that catalog entry breaks word-problem translation and the LLM maths-intent fallback at runtime (llm_extract.py's docstring calls its model "a fast internal alias"; gpt-6-luna is a user-selectable model).
- Fix: add `math_word_problem` and `math_llm_extract` lanes to `RoutingLanes` (checked for `json_mode`); `settings_intent` derives ids from `model_catalog.selectable_models()` plus a nickname table keyed by tier; `settings_proposal` uses `model_catalog.get(id).label`; the speech provider-name allowlists move to the speech catalog entries or the speech gateway.
- Effort: S
- Verify: a test that every `model_alias=` string literal under `modules/` is gone (lanes or catalog lookups only); a test that `_MODEL_IDS ⊇ {m.id for m in selectable_models()}` and proposal labels equal catalog labels.

### ARCH-07 — To-do writes commit and roll back a session they do not own; live talk hands them its unit of work
- Severity: Medium
- Confidence: High for the rule violation; Medium for the data-loss path (read, not executed)
- Locations: apps/api/app/modules/speech/live_talk.py:333-381 (messages created with `commit=False` at :339 and :348, then `todos_service.materialize_reminder_fences(session, …)` at :361 on the same session, `await session.commit()` :376, `session.refresh(...)` :378-380); apps/api/app/modules/todos/reminder_writes.py:156, :163, :165 (`todos_repo.update(...)`, default `commit=True`), :176 (`todos_repo.create(...)`, default `commit=True`), :186-188 (`except IntegrityError: … await state.session.rollback()`); apps/api/app/modules/todos/actions.py:322-323 (`apply_todo_actions(session, …)` commits the session it was handed); apps/api/app/modules/todos/spoken_apply.py:210; the safe caller for contrast: apps/api/app/modules/chat/finalize_reminders.py:82-83 (opens its own session).
- Evidence: CLAUDE.md "Transaction ownership": with `commit=False` repositories "must not commit or roll back"; "A caller that explicitly passes `commit=False` to a composable service owns both the eventual commit and rollback." Path: a spoken reminder whose open dated duplicate (`uq_todo_open_content_due` on user_id, lower(content), due_at) is not in `state.existing` — `list_for_user(limit=500)` over all topics with checked rows, ordered by topic (todos/repository.py:47-69, actions.py:24) — or is inserted concurrently: the create's commit fails, the IntegrityError branch rolls back the whole voice-turn transaction (the two message rows inserted in it are expunged), the final commit saves only `chat.updated_at`, and `session.refresh(user_message)` raises `InvalidRequestError`; `POST /speech/live/persist` (modules/speech/realtime.py:307) fails and the spoken turn never reaches the chat. On the normal path the todo create commits the voice turn mid-way, before the assistant text gets its result lines.
- Impact: rare loss of a voice turn's transcript for heavy users or concurrent writes; more broadly, `materialize_reminder_fences(session, …)` is safe only in a throwaway session, which its signature does not say (chat complies, speech does not).
- Fix: the todos write path passes `commit=False` everywhere and never commits or rolls back a passed session; the duplicate check uses a SAVEPOINT (`async with session.begin_nested():` around the insert) so only that insert is undone; or live talk calls the reminder pass in its own session after committing the messages (as chat does).
- Effort: S
- Verify: DB test: persist a live-talk turn whose reminder hits `uq_todo_open_content_due` (pre-insert the duplicate beyond the 500-row snapshot) and assert both messages are saved; a spy-session test that `materialize_reminder_fences` never calls `commit`/`rollback`.

### ARCH-08 — Chat message rows have four writers; image, photo and voice turns skip chat's turn invariants
- Severity: Medium
- Confidence: High (structure); Medium-High (drawer symptom)
- Locations: writes through the shared repository: apps/api/app/modules/images/generation.py:389, :443; apps/api/app/modules/images/search.py:255, :272; apps/api/app/modules/speech/live_talk.py:339, :348; apps/api/app/modules/todos/proposals.py:254 (`update_content`). Chat's settle: apps/api/app/modules/chat/turn_settle.py:201 (`touch_by_id`), apps/api/app/modules/chat/stream_pipeline.py:160-166 (tool-loop image: touch + post-turn jobs). Intercepts return early: apps/api/app/modules/chat/turn_intercepts.py:127, :222 → apps/api/app/modules/chat/stream_entry.py:133-144 (refund and return; no touch, no jobs). Live talk hand-rolls both: live_talk.py:375 (`chat.updated_at = datetime.now(UTC)`), :399-492 (`_enqueue_live_talk_jobs`). The drawer orders by `updated_at`: apps/api/app/repositories/chats.py:88, apps/mobile/features/chat/model/listSections.ts:103, :114. Job payload shapes built in four places: apps/api/app/modules/chat/post_turn.py:86-221, live_talk.py:413-486, apps/api/app/modules/chat/service.py:221-238 (topic backfill), apps/api/app/background/handlers.py:61-88, :146-160 (memory retry payloads).
- Evidence: `shared_repo_writes.py`: `repositories/messages.py` writes are called from chat, images, speech and todos. `images/generation.py:_persist_turn` (:361-411) and `images/search.py` (:240-296) never touch `chats.updated_at` (models/orm/chat.py:54-56 has only an ORM `onupdate` on the chat row; no DB trigger in `alembic/`); the phone never bumps it locally. `run_title` is only `prior_count == 0` (modules/chat/turn_prep/context.py:169-170), so an intercept-first chat is untitled until the backfill in chat/service.py:221-238 fires on the next message-page load. Live talk's job list lacks `compress` and `lesson_progress` and the `turn.spend_capped` gate that post_turn.py applies.
- Impact: "save a chat turn" has three owners. An image-generation or photo-lookup turn in an existing chat does not move it up the drawer or into "Today"; every new turn invariant (a post-turn job, a column on `chats`, usage) must be added to chat, images and speech separately, contrary to ARCHITECTURE.md ("A post-turn job | post_turn.POST_TURN_JOBS"; "the payload shape lives in one place").
- Fix: chat owns message writes: a composable `chat.service.record_turn(session, …)` (insert rows, touch, usage) and `post_turn` builders taking a `FinishedTurn` that images, speech and the intercept path call; move `repositories/{chats,messages,message_chunks}.py` into `modules/chat/` (chat is migrated; CLAUDE.md calls `repositories/` "shared persistence still used while domains migrate").
- Effort: M
- Verify: test that an image intercept turn bumps `chats.updated_at`; a parity test that live talk and a typed turn enqueue the same job set for the same inputs.

### ARCH-09 — Home's cache invalidation is spread across the modules that feed it (one call runs before the commit)
- Severity: Low
- Confidence: High
- Locations: apps/api/app/modules/home/service.py:113-119 (`invalidate_home_cache`); callers: apps/api/app/modules/todos/crud.py:48, :69, :116, :126, :156, :196, :203; todos/actions.py:322; todos/sync.py:138; todos/reminder_fences.py:310, :346, :436; todos/proposals.py:300; todos/spoken_apply.py:131, :137; apps/api/app/modules/memory/crud.py:20; memory/apply.py:126; apps/api/app/modules/account/settings_proposal.py:359; account/lifecycle.py:76. Home reads only todos and user fields: home/service.py:40-83 (`starters=[]` :82), home/greeting.py:11-24. Before-commit: todos/actions.py:322-323.
- Evidence:
  ```python
  # modules/todos/actions.py:315
      if applied > 0:
          ...
          await home_service.invalidate_home_cache(user_id)
      await session.commit()
  ```
  CLAUDE.md: "Cache invalidation … happen[s] after the owning service commits." A `GET /home` between the INCR and the commit re-caches pre-commit rows under the new generation for `home_cache_ttl` (120 s, core/settings/chat.py:18); fence mutations and the `todos` job rely on this call alone (reminder_fences.py:346 invalidates only `if created_any`). Memory's two calls came with 819570535 (2026-07-03), when home showed memory/project starters; home no longer reads memory. Phone mirror: features/chat/hooks/useChatBulkActions.ts, useChatManagementActions.ts, useChatMenuActions.ts and features/images/hooks/useImageGeneration.ts:20 invalidate attachments' `galleryListCache`; hooks/useSettingsProposal.ts:6-7 invalidates memory's caches; features/attachments/hooks/useGalleryLibrary.ts:11 clears chat's message cache.
- Impact: todos and home import each other (load-time 2-cycle); each new write path must remember to call into the consumer, after commit; memory pays a Redis INCR per write for nothing.
- Fix: home folds a todos-owned generation (bumped once after commit in todos' service) and the user row's `updated_at` into its cache key, so producers never import home; delete memory's two calls; meanwhile move actions.py:322 below :323. Same idea on the phone: owner-subscribed events instead of reaching into another feature's cache.
- Effort: S
- Verify: `rg -n "home_service.invalidate_home_cache" apps/api/app/modules | rg -v modules/home` empty; component graph has no todos → home edge; GET /home reflects a todo change made by every write path (parametrized test).

### ARCH-10 — Mobile features have no public surface and no boundary check; the chat row and drawer live outside `features/chat`
- Severity: Medium
- Confidence: High
- Locations: apps/mobile/components/MessageBubble.tsx:5, :9, :16, :24 (used only by features/chat; imports `features/todos/components/ReminderProposalCard`, `features/images/components/ImageGenPlaceholder`, `features/drafts/context/emailDraftPersist`, `features/chat/model/messageLogic`); apps/mobile/components/ConversationList.tsx:10, :15, :16, :19, :20, :29; chat ↔ images: apps/mobile/features/chat/model/sendIntercept.ts:3-4 and apps/mobile/features/images/hooks/useImageGeneration.ts:6, :22, :23; chat ↔ speech: apps/mobile/features/chat/components/ChatComposer.tsx:26-27, :59 and apps/mobile/features/speech/components/LiveTalkButton.tsx:5; chat ↔ attachments: apps/mobile/features/chat/model/sendLogic.ts:2 and apps/mobile/features/attachments/hooks/useGalleryLibrary.ts:11; shared hook → feature caches: apps/mobile/hooks/useSettingsProposal.ts:6-7.
- Evidence: `cross_feature.py`: 57 value imports from one feature into another's internals (model 36, components 12, hooks 6, context 3); no `features/*/index.ts`. `shared_to_feature.py`: 23 files in top-level components/, hooks/, contexts/, lib/ import features 44 times. `mobile_components.py`: one SCC of 16 nodes holding 11 of 12 features. Chat-only code outside the feature: components/MessageBubble, MessageActions, UserMessageContent, ChatMessage{Image,ImageStrip,Pdf}, ChatActionsMenu, ChatRenameSheet, ConversationList + components/drawer/*, hooks/useDrawerChatList, useDrawerChatSelection, useStreamLayoutHold, useAssistantMessageContent, useKeyboardInset, contexts/StreamingDraftContext, lib/drawerChatList, lib/drawerChatSelection, lib/streamUiTiming, lib/messageListLayout. Enforcement today: the API's architecture tests only assert features do not import `@/app/` (e.g. apps/api/app/tests/architecture/test_module_boundaries.py:88-93); ESLint restricts only `ui/**` and `lib/{math,physics,chemistry}/**` (apps/mobile/eslint.config.js:82-128); `lib/__tests__/importCycles.test.ts:94` is file-level.
- Impact: ARCHITECTURE.md "Chat may orchestrate public feature interfaces; it must not know how another feature stores data" is unenforced on the phone (the API has a CI rule for the same thing); `test_mobile_chat_has_one_feature_home_and_thin_route` says the chat screen's components and hooks are one feature, which is true only for files named `chat`.
- Fix: one public `index.ts` per feature and a jest structural test mirroring `_foreign_module_import_violations` (feature A may import feature B only via `@/features/B` or its `api.ts`; shared folders may not import features except allowlisted composition points), seeded with today's edges as a shrink-only allowlist; move the message row and drawer into `features/chat/` (update CLAUDE.md's "components/drawer/"); replace cross-feature cache pokes with owner-subscribed events.
- Effort: L (the rule and allowlist M; the moves incremental)
- Verify: the structural test fails today with 101 edges and passes with an allowlist that only shrinks; `mobile_components.py` shows features as a DAG.

### ARCH-11 — Nothing checks module-level dependency direction; function-local imports hide cycles the CI test cannot see
- Severity: Low
- Confidence: High
- Locations: apps/api/app/tests/architecture/test_import_cycles.py:32-37 (file graph, `load_time=True`); apps/api/app/tests/architecture/boundary_support.py:189-192 ("deferring an import into a function is the accepted way to break a load-order cycle"); docs/ENGINEERING_STANDARDS_TICKETS.md:1310-1312 ("about 8 other function-local imports exist to dodge import order"). The 24 cycle-closing sites: core/request_id.py:61; gateways/structured_completion.py:147, tool_completion.py:96, :157, vision_completion.py:50; modules/attachments/content.py:222; modules/chemistry/request.py:552; modules/math/image_extract.py:249, match/needs.py:60, solve/discrete.py:195, :209, solve/key_steps.py:106, tools/block/__init__.py:122, tools/block/calculus.py:66, :70, tools/block/derivatives.py:39, :68, tools/extractors/algebra.py:253, tools/graph_followup.py:136, tools/prompt.py:271, :360, :422; modules/web_search/subject.py:96; services/routing.py:343 (all under apps/api/app/).
- Evidence: `hidden_cycles_np.out` (CI graph semantics). Example: `math/tools/block/__init__.py:122` imports `math.tools.school` in a function while `math/tools/school/__init__.py:9` imports `math.tools.block` at load — two packages in `PURE_PACKAGES` depend on each other. With function-local imports counted, `modules/math` is one 49-file SCC, and 13 modules + 6 services files form one component SCC; at load time {todos, home} and an 8-component SCC remain. The documented back-edge (leaves import chat's turn cues, ARCHITECTURE.md §13) accounts for part of it; ARCH-01, ARCH-02 and ARCH-09 are the undocumented rest.
- Impact: ENGINEERING_STANDARDS rule 6 ("Clear dependency direction … No import cycles") holds only per file and at load time, so module-level inversions grow without a failing test, and the ticket doc understates the hidden-cycle count about threefold.
- Fix: a contract test over `_module_imports(load_time=False)` collapsed to `app.modules.<x>` / `app.services.<x>` that declares the allowed direction (subjects and features under chat, billing/home/todos/memory independent, services leaves under modules; chat's cue surface named as the one sanctioned back-edge) with a shrink-only allowlist of today's back-edges (import-linter's layers/independence contracts express the same); correct the count in the tickets doc.
- Effort: S
- Verify: the contract test runs in API CI; the allowlist shrinks as ARCH-01/02/09 land.

### ARCH-12 — CLAUDE.md's map is wrong in seven places
- Severity: Low
- Confidence: High
- Locations: CLAUDE.md:79-80 (`services/  # legacy product code until that domain is a module` / `notifications/ web_search/ mcp/` — neither notifications nor web_search is under services/; its packages are `law_binding/`, `mcp/`, `quota/`); CLAUDE.md:148 ("legacy domains remain packages under services/" — none remain; ARCH-03); CLAUDE.md:130 (`chat_history_rag.py` — the file is apps/api/app/modules/chat/history_rag.py, exported as `history_rag`, modules/chat/__init__.py:36-44); CLAUDE.md:17 and :161 (alias→provider mapping "lives in services/model_catalog.py" — it is apps/api/app/models/model_catalog.py, as docs/ARCHITECTURE.md:47 says; ARCH-05); CLAUDE.md:198 (domain libs include `todos/` — apps/mobile/lib/todos is forbidden by apps/api/app/tests/architecture/test_module_boundaries.py:77); CLAUDE.md:189 (worker schedulers omit billing reconcile, apps/api/app/process_bootstrap.py:83-86); CLAUDE.md:16 ("The app only ever talks to our API" — apps/mobile/features/speech/model/realtimeSdp.ts:1-8, :16 posts SDP to api.openai.com with a backend-minted ephemeral secret, "the one intentional provider-network exception"; the golden rule should name it).
- Evidence: path checks (`doc_paths.py` plus manual `test -e`).
- Impact: CLAUDE.md is the engineering map people and agents follow; the wrong homes (services/ for legacy product code, services/model_catalog) are exactly where ARCH-03 and ARCH-05 drift happened.
- Fix: edit those lines; add a CI check that backticked paths in CLAUDE.md's catalog and seams tables resolve.
- Effort: S
- Verify: the path check passes.

---

## Looked wrong, actually fine

- **Composition roots importing module internals** (main.py:18-30, process_bootstrap.py:23-25, background/handlers.py:28-40, services/mcp/__init__.py:5-7, models/orm/__init__.py:11-14): ARCHITECTURE.md names exactly these as the places that connect infrastructure and modules. Counted in the metrics, not reported.
- **Leaves importing the chat package** (modules/web_search/detection.py:10, physics/direct.py:16, math/followup.py:110, todos/classification.py:150, speech/live_talk.py:19): documented in ARCHITECTURE.md §13 ("they reach chat's turn cues, presentation and stream status through the app.modules.chat package"), and the package is lazy by design. It is the sanctioned back-edge ARCH-11 should name explicitly.
- **`ui/` kit purity**: the transitive import closure of all `ui/` files (63 files) reaches no product code; the one hit, `lib/feedbackTiming.ts:1 → contexts/actionFeedbackCore`, is `import type`. Control-like components outside `ui/` (CopyButton, PlaybackButton, ChatRenameSheet, UpgradeSheet, the modals) compose `@/ui/*` (FullScreenModal, Sheet, Button); no raw Modal/Alert/Switch outside `ui/overlay`. `ScannerSubjectSwitcher` is a drag-to-pick camera control `SegmentedControl` does not offer.
- **Mobile network boundary**: no `fetch` in screens. Non-API egress is deliberate: `features/speech/model/realtimeSdp.ts` (documented exception, ephemeral key; only the CLAUDE.md wording is off, ARCH-12), `lib/networkProbe.ts` (public reachability probe), `features/attachments/model/fetchAttachmentBytes.ts` (Recall URLs go through `lib/api/client` `requestRaw`/`authorizeNativeTransfer`; other URLs get no credentials), the XHR inside the PDF WebView HTML (`lib/pdfPreviewHtml.ts:63`), and the presigned PUT in `features/attachments/api.ts:121`. `features/chat/model/wsTransport.ts` owning `new WebSocket` is asserted by test_product_module_boundaries.py.
- **Screens are thin**: largest is ChatScreen.tsx 571 (already "next in line" in the tickets doc); the rest ≤ 384 lines with ≤ 3 effects and no direct API calls outside feature slices.
- **Module `api.py` files**: thin (longest handler `speech/api.py:transcribe_speech`, 62 lines, mostly HTTP body parsing plus the `speech/gates.py` checks); `routers/` holds only admin, health, legal, models, matching the catalog. `speech/realtime.py:155-202` orchestrates reserve → mint → compensate → issue in the router; borderline, not reported.
- **Shared STEM leaves in `services/`** (answer_check, answer_fence, workout, number_text, units, unit_text, school_rounding, symbolic_text, text_match, solving, subject_scan, problem_followup, md_fence_scan): a BFS with every import counted reaches no infrastructure (`infra_reach.py`); only `services/reminder_timing.py` imports `app.models.orm` (for `User`). ARCHITECTURE.md §7 places such leaves there on purpose.
- **Transaction ownership elsewhere**: multi-step units pass `commit=False` and commit once (memory/apply.py, images/generation.py:361-411, chat/turn_settle.py, chat/turn_prep/persist.py). The 18 always-committing repository functions are used as single operations; the login flows' second write is in an exclusive branch; attachments/rag.py:254-266 is two deliberate phases. The only side effect before a commit is todos/actions.py:322 (ARCH-09); memory/apply.py:87 runs after the first phase's commit.
- **Presentation inside "pure" maths packages** (42 files in `tools/block` and `tools/school` render workout markdown): a deliberate per-operation slice (ES-13: "each reader sits beside its block"); the purity test bars infrastructure, not text. Not reported.
- **`repositories/users.py:118-140` deleting every module's rows** by hand: all user FKs are `ON DELETE CASCADE` in the ORM, and the docstring explains the explicit deletes guard older migration states. Mentioned only as barrel evidence in ARCH-04.

## Open questions for the team

1. Live talk applies spoken reminder changes without the tap (`live_talk.py:361` passes no `confirm`) while `reminder_proposals_enabled` is on for typed chat. The comment covers "a reminder the user said with a clock", but every fence in the spoken reply is applied. Intended?
2. Image-generation and photo-lookup intercept turns enqueue no post-turn jobs (no memory, no message_index). Deliberate, or a side effect of ARCH-08?
3. `modules/todos/write_log.py:59-76` switches the To-do repository into "plan, don't write" through a ContextVar; `create`, `update` and `delete_by_id` check it, `delete_by_topic`, `reorder` and `schedule_repository` do not. "Nothing is saved until the tap" holds because no current proposal path reaches the unchecked ones. ES-25 removed the same ambient-state pattern from the tools — pass an explicit writer instead?
4. Pure maths reads `get_settings()` (modules/math/solve/parse.py:172, solve/equations.py:57, solve/key_steps_special.py:305-307), so SymPy workers load pydantic-settings and limits are hidden inputs. Pass them as parameters?
5. `modules/physics/symbolic/solver.py:253` does `render_workout(workout).removesuffix("\n\n**Answer**")`, depending on the renderer's exact output. A `render_workout(..., with_answer_heading=False)` would remove the string surgery.
6. Every module's `api.py` depends on `modules/account/consent.get_consented_user`, making account a hub in the module graph. Should the consent check sit in `core/deps.py` beside `get_current_user` (it reads a user-row field)?
