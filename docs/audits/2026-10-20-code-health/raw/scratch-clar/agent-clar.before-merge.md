# Agent CLAR — Clarity, consistency and maintainability

Audited tree: `/home/user/recall-audit` at `d2ec42b0` (read-only). Paths are repo-relative.
Method: Python `ast` and the TypeScript compiler API over production code only (tests, vendor,
`node_modules`, `__tests__`, `*.test.*` excluded), plus grep/git. Scripts:
`/home/user/recall/tmp/code-audit/raw/scratch-clar/` (`py_metrics.py`, `ts_metrics.js`,
`log_args.py`, `settings_*.py`, `stale_paths*.{py,js}`, `lazy_imports.py`, `mypy_cover.py`,
`magic.py`). Raw tables: `py_functions.tsv`, `ts_functions.tsv`, `py_excepts.tsv`,
`ts_catches.tsv`, `log_calls.tsv` in the same folder. The ES audit baseline was re-measured by
running the same scripts on the tree at `8a20f147d` (2026-10-16, the commit that added
`docs/ENGINEERING_STANDARDS_TICKETS.md`); my length metric reproduces the ticket's snapshot
exactly (378 API functions over 50 lines, 87 over 100), so the before/after numbers below are
comparable. (Nesting counts `if/for/while/with/try/match`, `elif`/`else if` at the same level; the
ticket's 171 "deeper than 3" used a different nesting rule, so compare my 105 → 98.)

## Metrics

| Measure | At ES audit (8a20f147d) | Now (d2ec42b0) |
|---|---|---|
| API production functions | 5,202 | 6,004 |
| API functions over 50 / over 100 lines | 378 / 87 | 378 / 61 |
| API functions nested deeper than 3 / deeper than 4 | 105 / – | 98 / 32 |
| Phone functions over 50 / over 100 lines (components and hooks included) | 359 / 137 | 374 / 119 |
| Phone functions nested deeper than 3 | 39 | 36 |
| API broad `except Exception`/bare `except` | 401 | 338 |
| …that neither log nor re-raise | 93 by my rule (ticket: 98) | 9 silent + 6 that only use the exception value |
| …whose only log is `logger.debug` (invisible: root level is hard-coded INFO) | – | 91 |
| API `Any` references (Name/attr nodes) | – | 1,161 in 185 files (`dict[str, Any]` 257; `x: Any` 360; `-> Any` 80; math SymPy code holds ~40%) |
| API `cast(` calls | – | 49 in 24 files |
| API `# type: ignore` | – | 30, all with an error code, none with a reason; ≥10 suppress errors that no longer exist (CLAR-08) |
| mypy strict-flag coverage of API production lines | – | 4.7 % (8,601 of 183,369; `app.core`, `models.schemas`, `repositories`, `services.quota`, 3 attachment files) |
| Imports that mypy types as `Any` through lazy package `__getattr__` | – | 58 production imports in 28 files (CLAR-07) |
| API logger calls / f-string logger calls | – | 500 / 0 (consistent `%s` style) |
| TS `any` (production) | – | 0 |
| TS `as` casts (non-`const`) / `as const` | – | 213 / 104 |
| TS `as unknown as` | – | 1 (`lib/markdown/parser.ts:10`) |
| TS non-null `!` | – | 125 (worst: `lib/markdown/preprocessMathFences.ts` 17) |
| TS `@ts-ignore` / `@ts-expect-error` / `eslint-disable` | – | 0 / 0 / 29 |
| TS `catch` clauses / empty / no log, toast or rethrow | – | 263 / 61 / 197 (88 of the 197 carry a comment) |
| Settings fields / declared twice / never read / read but undefined | – | 209 / 0 / 0 / 0 |
| Env reads outside settings | – | 1 (`modules/math/solve/declines.py:58`, the documented test strict mode) |

### API: top 15 functions by length (lines, nesting)

| Lines | Depth | Location | Function |
|---|---|---|---|
| 218 | 3 | apps/api/app/modules/math/tools/direct_calculus.py:113 | `calculus_direct_request` |
| 216 | 3 | apps/api/app/modules/physics/extractors/circuits.py:70 | `_extract_circuit_intent` |
| 194 | 3 | apps/api/app/modules/physics/extractors/torque.py:51 | `_extract_torque_intent` |
| 184 | 3 | apps/api/app/modules/math/tools/school/trig.py:86 | `_extract_trig_intent` |
| 181 | 4 | apps/api/app/modules/account/export.py:252 | `_iter_export_json` |
| 177 | 5 | apps/api/app/modules/memory/extraction_workflow.py:269 | `_extract_pass` (163 at the audit) |
| 177 | 3 | apps/api/app/modules/math/tools/school/calculus.py:264 | `apply_calculus_extension` |
| 174 | 2 | apps/api/app/modules/physics/extractors/kinematics.py:121 | `_extract_kinematics_intent` |
| 173 | 2 | apps/api/app/modules/physics/extractors/waves.py:59 | `_extract_waves_intent` |
| 168 | 2 | apps/api/app/modules/math/solve/written_division.py:114 | `build_long_division` |
| 165 | 2 | apps/api/app/modules/math/solve/fractions.py:125 | `build_fraction_work` |
| 160 | 2 | apps/api/app/modules/math/tools/direct.py:163 | `can_direct_verified_math_reply` |
| 159 | 3 | apps/api/app/modules/chat/stream_api.py:80 | `_stream_tokens_sse` (150 at the audit) |
| 158 | 2 | apps/api/app/modules/physics/solvers/projectile.py:48 | `solve_projectile` (154) |
| 152 | 3 | apps/api/app/modules/math/tools/prompt.py:238 | `build_math_augmentation` (150) |

### API: top 15 by nesting depth

| Depth | Lines | Location | Function |
|---|---|---|---|
| 6 | 94 | apps/api/app/modules/memory/consolidation_workflow.py:106 | `consolidate_user_memory_sections` |
| 6 | 80 | apps/api/app/modules/chat/prompt_constants/writing_kind.py:231 | `_next_sentence_tail` |
| 6 | 46 | apps/api/app/modules/chat/related_questions.py:155 | `_space_math_span` (phone twin `features/suggestions/model/promptMath.ts:23` `spaceMathSpan` is the phone's deepest too) |
| 6 | 32 | apps/api/app/services/symbolic_text.py:80 | `collapse_repeated_si_unit_powers` |
| 5 | 177 | apps/api/app/modules/memory/extraction_workflow.py:269 | `_extract_pass` |
| 5 | 147 | apps/api/app/gateways/litellm_gateway.py:286 | `_stream_chat_once` |
| 5 | 146 | apps/api/app/modules/chat/ws_turn.py:57 | `stream_over_ws` |
| 5 | 100 | apps/api/app/gateways/image_gateway.py:24 | `generate_via_openrouter` |
| 5 | 98 | apps/api/app/modules/memory/apply.py:21 | `apply_memory_facts` |
| 5 | 96 | apps/api/app/modules/speech/live_talk.py:301 | `persist_live_talk_turn` |
| 5 | 95 | apps/api/app/gateways/litellm_gateway.py:180 | `stream_chat_completion` |
| 5 | 91 | apps/api/app/modules/math/match/calculus.py:493 | `parse_series` |
| 5 | 79 | apps/api/app/modules/speech/live_talk_tools.py:33 | `execute_tool` |
| 5 | 79 | apps/api/app/modules/attachments/content.py:102 | `extract_text_details` |
| 5 | 77 | apps/api/app/modules/chat/turn_prep/camera_math.py:15 | `camera_math_extract` |

### Phone: top 10 functions and components by length

| Lines | Depth | Location | Function | At audit |
|---|---|---|---|---|
| 550 | 0 | apps/mobile/features/chat/hooks/useChat.ts:32 | `useChat` (29 `useRef`, 18 `useCallback`) | 558 |
| 514 | 1 | apps/mobile/features/chat/screens/ChatScreen.tsx:48 | `ChatScreen` | 577 |
| 473 | 1 | apps/mobile/features/chat/hooks/useChatRouteLoader.ts:61 | `useChatRouteLoader` | 473 |
| 438 | 1 | apps/mobile/features/chat/components/ChatComposer.tsx:118 | `ChatComposer` | 582 |
| 436 | 0 | apps/mobile/features/speech/hooks/useLiveTalk.ts:46 | `useLiveTalk` | 424 |
| 425 | 1 | apps/mobile/components/MathEquationScanner.tsx:99 | `MathEquationScanner` | 462 |
| 417 | 1 | apps/mobile/features/chat/hooks/useChatSend.ts:95 | `useChatSend` | 622 |
| 395 | 0 | apps/mobile/features/chat/hooks/useChatIncoming.ts:28 | `useChatIncomingEvents` | 434 |
| 373 | 0 | apps/mobile/components/ConversationList.tsx:43 | `ConversationList` | 373 |
| 366 | 0 | apps/mobile/features/chat/hooks/useChatScreenBodyProps.tsx:131 | `useChatScreenBodyProps` | 376 |

Phone deepest: `features/suggestions/model/promptMath.ts:23` `spaceMathSpan` (6), `lib/math/fenceRetag.ts:314`
`retagMathAndDiagramFences` (5, 83 lines), `lib/math/pasteNormalize.ts:110` `rewriteUnicodeSqrts` (5),
`lib/math/draftSlots.ts:328` `deleteTokenBefore` (5), `lib/fallbackFence.ts:55` `visualSnippet` (5).

## Findings

### CLAR-01 — User content reaches the log sink and Sentry: to-do text, reminder email subjects, SQL parameters
- Severity: High
- Confidence: High
- Locations:
  - apps/api/app/modules/todos/reminder_writes.py:204-209 — every reminder a chat reply writes or proposes logs its title at INFO (`create_one` also runs under `write_log.recording()` when reminder proposals are on): `"To-do fence applied: user_id=%s chat_id=%s title=%s", …, title[:80]`
  - apps/api/app/modules/todos/actions.py:201-206 — WARNING with 120 chars of the to-do text: `"Todo delete missed: user_id=%s topic=%s content=%r", …, (action.content or "")[:120]`
  - apps/api/app/gateways/email_gateway.py:75, :84, :93, :119 — `subject=%r` at DEBUG / WARNING / INFO / ERROR (`logger.exception`). For reminder emails the subject *is* the reminder: apps/api/app/modules/notifications/email_copy.py:352 `"subject": "{title}: {content}"`, filled with `occurrence.content` (apps/api/app/modules/notifications/reminder_email.py:101-103). The reminder scheduler runs only when email can actually be sent (background/email_reminder_scheduler.py:29 `can_send`), so in production the leak is :119: ERROR plus a Sentry event, with the reminder text, on every failed send. In development and test mock mode, :93 logs every reminder's subject at INFO. The same function's comment (:89-91) says reminder emails "contain PII and recipient-specific content that shouldn't sit in INFO logs" and masks the recipient (`*@domain`), but not the subject.
  - apps/api/app/modules/math/tools/prompt.py:441 — `logger.info("math_tools skipped: %s", exc)`, where `MathServiceError` messages embed the user's input (apps/api/app/modules/math/solve/parse.py:186, :190 `f"Could not parse expression: {expr}"`; 34 f-string `MathServiceError` messages in `modules/math`).
  - apps/api/app/core/db.py:25-37 — `create_async_engine(...)` without `hide_parameters=True`. SQLAlchemy 2.1 formats `[parameters: %r]` into every `StatementError` string (`sqlalchemy/exc.py:597`), so each `logger.exception(...)` around a failed write of a message, memory fact or to-do, and the Sentry event for it, carries the row's text.
  - apps/api/app/core/sentry.py:82-92 — `before_send` scrubs only `event["request"]`. Sentry's default `LoggingIntegration` (sentry-sdk 2.71: INFO and above become breadcrumbs, ERROR and above become events) forwards the lines above with their `%s` arguments. Breadcrumbs, `logentry` params and exception values are not scrubbed. The phone does scrub them: apps/mobile/lib/sentry.ts:42 drops console breadcrumbs, :28/:33 caps exception text at 300 characters, and :66 deletes `extra`. Yet its header comment (:1-4) says it follows the "Same rule as the API's".
- Evidence: SECURITY.md:22 promises "Error reports (Sentry) carry no request bodies and no stack-frame variables, so prompts and tokens stay out of them". `docs/ENGINEERING_STANDARDS.md` says "No secrets in the phone app, logs, …". The codebase's own logging convention is lengths and ids: `prompt_len=%s` (gateways/image_gateway.py:122), `chars=%s` (gateways/speech_gateway.py:217), `content_chars=%s` (modules/chat/turn_timing.py:61). Of the 500 API logger calls, these are the ones that break it. `_PIIRedactFilter` (core/logging.py:43; patterns at :27-29) redacts only emails and JWT or bearer tokens.
- Impact: Reminder text is often health, family or money ("take sertraline", "call the lawyer"). It lands in the Fly log drain for every chat-created reminder and in Sentry breadcrumbs and events, where retention and access differ from the database's. A failed message insert also ships the user's message text to Sentry.
- Fix: Log ids, counts and lengths only: `title_len=`, `content_len=`, and `kind=` instead of the subject. Pass `hide_parameters=True` to `create_async_engine`. In `core/sentry.py`, scrub breadcrumbs from `category="logging"` down to the template, or set `LoggingIntegration(level=None)` for breadcrumbs, and cap exception values the way `lib/sentry.ts` does. Add an architecture test that fails when a logger call interpolates an argument named `content`, `title`, `subject`, `text`, `prompt` or `query` (the AST walk in `scratch-clar/log_args.py` is about 40 lines).
- Effort: S
- Verify: The new architecture test. Unit-test `before_send` with a breadcrumb and a `StatementError`. `grep -rn "subject=%r\|title=%s\|content=%r" apps/api/app` returns nothing.

### CLAR-02 — Failures logged only at DEBUG are invisible in production (root level hard-coded to INFO)
- Severity: Medium
- Confidence: High
- Locations: apps/api/app/core/logging.py:166-177. `setup_logging(*, json_output)` takes no level and ends with `root.setLevel(logging.INFO)`, called from apps/api/app/process_bootstrap.py:45. No `LOG_LEVEL` setting or env exists. 91 of the 338 broad `except Exception` handlers log only at DEBUG (full list: `scratch-clar/except_levels.py`). The ones that hide more than a cache miss:
  - apps/api/app/modules/memory/locks.py:25. A Redis error on lock acquire returns `None`. apps/api/app/modules/memory/extraction_workflow.py:279-284 and consolidation_workflow.py:114-119 then log INFO "skipped: write lock held" and re-enqueue, so an outage reads as lock contention.
  - apps/api/app/core/jobs/dedupe.py:62 (claim fails open, so a duplicate job runs), :84
  - apps/api/app/modules/attachments/content.py:147 (PDF), :164 (DOCX); attachments/office_text.py:85. An upload silently has no text for RAG.
  - apps/api/app/modules/attachments/lifecycle.py:198 — "Image quota refund failed for user %s": a user silently loses an image slot
  - apps/api/app/modules/memory/crud.py:106, :173 — re-embed after an edit fails, and the vector stays NULL
  - apps/api/app/modules/speech/live_talk.py:247, :263 — a Live Talk session starts without memory or schedule. ES-18 moved the sibling `live_talk_tools.py:113` to WARNING; these two were left.
  - apps/api/app/services/model_health.py:54 (read failure reports healthy), modules/chat/turn_load.py:137, modules/attachments/workflow.py:343
- Evidence: `logger.debug("Memory write lock acquire failed", exc_info=True); return None` (locks.py:24-26). `root.setLevel(logging.INFO)` (logging.py:177). ES-39's `solve/declines.py:103` also logs only at DEBUG, by design, and its `decline_counts()` "nothing exports it yet" (ES-39 text).
- Impact: Fail-open choices are fine, but these leave no trace in production: not in logs, and not in Sentry breadcrumbs, which also start at INFO. On-call cannot tell a Redis blip from normal contention, and cannot see that PDF extraction or refunds are failing.
- Fix: Add `log_level: str = "INFO"` in `core/settings/infrastructure.py` and pass it to `setup_logging`. Raise the non-cache handlers above to WARNING with ids. Report the rest as counters through `core/sentry.report_breadcrumb`, which is the documented seam for best-effort paths in docs/ARCHITECTURE.md. Return a distinct outcome from `acquire_memory_write_lock` for "Redis failed" versus "held".
- Effort: S
- Verify: A test that `setup_logging` honours `LOG_LEVEL`. Re-run `scratch-clar/except_levels.py`: the debug-only count drops and none of the listed sites remains.

### CLAR-03 — API: the second tier of god functions is untouched since the ES audit, and six grew
- Severity: Medium
- Confidence: High
- Locations: the top-15 tables above. ES-19…ES-26 and ES-37 split the long functions the audit named, and functions over 100 lines fell from 87 to 61. But the current top 15 (152–218 lines) were already there at the audit and were not ticketed: 9 have exactly the same length, 2 shrank by 1–2 lines and 4 grew. For example apps/api/app/modules/math/tools/direct_calculus.py:113 `calculus_direct_request` is 218 lines then and now, and physics/extractors/circuits.py:70 is 216 then and now. These grew after the audit (8a20f147d → d2ec42b0):
  - apps/api/app/modules/memory/extraction_workflow.py:269 `_extract_pass` 163 → 177, depth 5. It does lock, snapshot, transcript expansion, command detection, the model call, five write-composition rules, apply and cursor stamping.
  - apps/api/app/modules/chat/stream_api.py:80 `_stream_tokens_sse` 150 → 159
  - apps/api/app/modules/memory/llm.py:69 `revise_memory_facts` 107 → 119
  - apps/api/app/modules/physics/block.py:107 `_build_physics_block` 131 → 136
  - apps/api/app/modules/physics/solvers/projectile.py:48 `solve_projectile` 154 → 158
  - apps/api/app/modules/math/tools/prompt.py:238 `build_math_augmentation` 150 → 152

  The count over 50 lines is unchanged at 378, so new code keeps adding long functions as fast as tickets remove them. Deepest: apps/api/app/modules/memory/consolidation_workflow.py:106 (depth 6: try › try › for › if › if › if) and modules/chat/ws_turn.py:57 `stream_over_ws` (146 lines, depth 5; it was ws_api.py `_stream_over_ws`, 151, at the audit).
- Evidence: `scratch-clar/py_functions.tsv` and `at_audit_out/py_functions.tsv`. The same script reproduces the ticket's 378/87 snapshot.
- Impact: The chat transports (`_stream_tokens_sse`, `stream_over_ws`) and memory extraction are the most-changed paths; `extraction_workflow.py` had 7 commits since 2026-08-20. At depth 5–6 a reviewer cannot see which writes a forget, mute or history pass produces.
- Fix: Treat this as ES-37 part 4 with the same capture-and-compare method. Split `_extract_pass` into `_load_pass_input` → `_compose_writes(snapshot, result, flags)` (pure, unit-testable) → `_apply_and_stamp`, and give `consolidate_user_memory_sections` the same shape. Add a CI ratchet: a baseline file of function lengths, like `scripts/file_size_baseline.json`, that may only go down.
- Effort: M
- Verify: The `py_metrics.py` counts go down. A function-length ratchet test in `app/tests/architecture/`.

### CLAR-04 — Phone: the chat feature's hooks are 400–550-line state machines held in refs
- Severity: Medium
- Confidence: High
- Locations: apps/mobile/features/chat/hooks/useChat.ts:32 `useChat` is 550 lines (29 `useRef`, 18 `useCallback`, 6 `useState`). It mirrors state into refs: `messagesRef.current = messages` during render (:40), `streamingRef`/`finalizingRef` (:71-72) beside `streaming`/`finalizing`, and four late-bound handler refs (`payloadHandlerRef`, `fallbackHandlerRef`, `sendFailureRef`, `regenerateFailureRef`, :86-93) that let sibling hooks call each other. Also apps/mobile/features/chat/hooks/useChatRouteLoader.ts:61 (473), features/chat/screens/ChatScreen.tsx:48 (514), features/chat/components/ChatComposer.tsx:118 (438), features/speech/hooks/useLiveTalk.ts:46 (436, was 424 at the audit), features/chat/hooks/useChatSend.ts:95 (417 after ES-35), useChatIncoming.ts:28 (395). The lint rule that would flag ref reads and writes during render is off for the whole app: apps/mobile/eslint.config.js:132 `"react-hooks/refs": "off"` (with `set-state-in-effect` and `preserve-manual-memoization`, :133-134). Phone functions over 50 lines grew from 359 to 374.
- Evidence: the phone top-10 table above. ES-38's "remaining long phone functions" list ran from 117 to 226 lines and did not name these hooks, although `useChat` was already 558 lines at the audit. Only `useChatSend` (via ES-35) was ticketed.
- Impact: Every chat bug (stop, regenerate, socket fallback, switching chats mid-stream) is a race between refs mutated from several hooks. The generation guards (`isCurrentView`, `sessionGeneration`) are re-derived in each hook. This is the phone's most-changed area. Since 2026-08-20, counting old and new paths, the chat screen changed in 65 commits (`app/index.tsx` 56 before the move, then `ChatScreen.tsx` 9), `useChatSend` in 55 (45 + 10), `ChatComposer` in 40+ and `useChat` in 29 (22 + 7). No other phone file reaches 51.
- Fix: Apply ES-36's proven approach (`realtimeTurnState.ts`, a pure reducer) to the chat turn. Make `chatTurnState.ts` a reducer over the socket and SSE payloads, sends, stop and regenerate, and keep `useChat` as the effect shell. Replace the late-bound refs with the reducer's dispatch. Re-enable `react-hooks/refs` for `features/chat/**` once the mirrors are gone.
- Effort: L
- Verify: `ts_metrics.js` shows `useChat` under 200 lines and fewer than 10 refs. A reducer unit test over the recorded event sequences (`chatSocketReduce.test.ts` style). The lint rule passes on `features/chat`.

### CLAR-05 — Memory still runs on the test-patch "seams" pattern ES-23 removed from chat
- Severity: Medium
- Confidence: High
- Locations: apps/api/app/modules/memory/surface.py:131-133 `def _seams(): return sys.modules["app.modules.memory"]` ("Callers patch the package … not this module"). Every wrapper passes that module object into collaborators typed `seams: Any`: apps/api/app/modules/memory/locks.py:18, :43; crud.py; cache.py; retrieval.py. They reach 29 distinct names through it, 51 lookups on 50 lines (lines: retrieval.py 29, crud.py 15, locks.py 4, cache.py 2), including private ones (`seams._memory_block_key`, `seams._warm_semantic_memory_cache`) and exception classes (`seams.MemoryWriteLockBusyError`). apps/api/app/modules/memory/__init__.py:15-21 installs the names lazily. Tests patch `app.modules.memory.*` in 65 places. Other production code is shaped the same way for tests:
  - apps/api/app/modules/memory/retrieval.py:40-42 `_profile_kwargs` passes `with_profile` "only when set, so seams patched in tests stay compatible"
  - apps/api/app/services/reminder_timing.py:46-50 reads `getattr(user, "quiet_hours_enabled", False) is not True` "so MagicMocks in tests are not treated as opted-in"
  - apps/api/app/modules/todos/sync.py:103-106 uses function-local imports "so tests can patch todos_service.apply_todo_actions", plus a private `_apply_bulk_shift_due_today_to_tomorrow`
- Evidence: ES-23's problem statement: "`_seams()` returns `sys.modules[__name__]` … reach every repository, service and gateway as `seams.<name>` through a parameter typed `Any` … The dependency surface is invisible to type checking and to the module-boundary tests". Its fix (`ChatTurnDeps`) was applied to chat only. Memory's seam dates from 49183abe5 (2026-09-22, "Move Memory into an owned module").
- Impact: mypy cannot check any of the 51 lookups, so renaming a memory function breaks only at runtime on the path that uses it. Production signatures bend to what test fakes accept.
- Fix: Do what ES-23 did. Add a frozen `MemoryDeps` dataclass (redis client getter, repositories, embedder, background-task spawner) with `default_deps()`, and pass it explicitly. Tests build fakes instead of patching the package. Delete `surface.py`'s re-export block and `_profile_kwargs`, and make `reminder_timing` read `user.quiet_hours_enabled`.
- Effort: M
- Verify: `grep -rn "seams" apps/api/app/modules/memory` returns nothing. `grep -rn "monkeypatch.setattr(\"app.modules.memory\.\|patch(\"app.modules.memory\." apps/api/app/tests` returns nothing. mypy checks the memory calls.

### CLAR-06 — Typed ORM columns read by name with `getattr(obj, "field", default)`; the memory privacy switch has five readers and two defaults
- Severity: Medium
- Confidence: High
- Locations: there are 284 three-argument `getattr(x, "<literal>", default)` calls in API production code. By the name of the object read: `user` 32, `memory` 30, `message` 20, `row` 17. The SymPy duck-typing ones (`rhs`, `expr`, `lhs`, `term`) are legitimate. Every `User` field read this way is a declared `Mapped[...]` column in apps/api/app/models/orm/user.py:48-103.
  - The `memory_enabled` switch ("Memory off means no personal recall", CLAUDE.md) has a helper, `memory_switch_on(user: object)` at apps/api/app/modules/chat/prompt_memory.py:98-100, whose default is True ("an account row not loaded yet counts as on"). Four other places re-read the field themselves: apps/api/app/modules/memory/extraction_workflow.py:82, consolidation_workflow.py:89 and learning_progress.py:59 default to True; apps/api/app/modules/speech/live_talk.py:233 defaults to False. apps/api/app/modules/account/lifecycle.py:45 reads `user.memory_enabled` directly.
  - The account export reads columns with `None` defaults: apps/api/app/modules/account/export.py:137, :145-151 (`getattr(memory, "topic", None)` and so on).
  - Others: modules/account/profile.py:13, :15, :45, :50, :61; modules/account/consent.py:30; modules/chat/prompt_profile.py:63, :105; modules/notifications/push.py:283, :295, :299; services/reminder_timing.py:50-58; modules/memory/extraction_workflow.py:96, :110.
- Evidence: `if not getattr(user, "memory_enabled", False):` (live_talk.py:233) next to `return getattr(user, "memory_enabled", True) is not False` (prompt_memory.py:100). Introduced and copied since 50336c5dd (2026-06-29).
- Impact: mypy types each read as `Any`. If a column is renamed or dropped (expand/contract migrations do exactly that), nothing fails. The default silently becomes the behaviour: memory stays on for chat but turns off for Live Talk, and the export emits `null` for a field it promises to include. The defaults only matter for test doubles, so the code is shaped for mocks rather than for the model.
- Fix: Read typed attributes directly (`user.memory_enabled`). Route every memory-switch read through `memory_switch_on(user: User)` and drop the `object` type. Where tests pass partial objects, give them a `User` factory. Add a ruff rule: `B009` (getattr with a constant attribute) is already in flake8-bugbear, but only flags the two-argument form, so ban the three-argument form on ORM types with a small AST test.
- Effort: S
- Verify: `grep -rn 'getattr(user, "' apps/api/app --include=*.py | grep -v tests` returns nothing. One `memory_switch_on` reader per call site (grep). The mypy strict override for `modules.memory` passes.

### CLAR-07 — Type checking is strict for 4.7 % of the API, and lazy package exports make 58 cross-module imports `Any`
- Severity: Medium
- Confidence: High
- Locations: apps/api/pyproject.toml:107-110 sets `[tool.mypy] strict = false`, `ignore_missing_imports = true`. The strict overrides (:116-142) cover `app.core`, `app.exceptions`, `app.models.schemas`, 3 `attachments` files, `app.repositories` and `app.services.quota`: 8,601 of 183,369 production lines. Apart from the quota path rename in ES-33, that list has not grown since cbd011072 (#474, 2026-07-18). Seven product packages define `def __getattr__(name: str) -> Any` for lazy exports, with no `TYPE_CHECKING` stubs: apps/api/app/modules/billing/__init__.py:22, chat/__init__.py:49, math/__init__.py:32, memory/__init__.py:15, notifications/__init__.py:19, physics/__init__.py:37, todos/__init__.py:40. Under PEP 562, mypy gives every name imported that way the `__getattr__` return type `Any`. That is 58 production imports in 28 files, among them `can_use` (plan entitlements: modules/images/generation.py:32, images/gen_tool.py:17), `StreamStatusFn` (a type alias, so `on_status: StreamStatusFn | None` at modules/web_search/augment.py:42/55 is `Any`), `PHYSICS_REPLY_POLICY`/`physics_prompt_hints` (modules/chat/prompt_subjects.py:21), `apply_todo_actions` and 20 memory names (modules/chat/post_turn.py:25).
- Evidence: `scratch-clar/lazy_imports.py` and `scratch-clar/mypy_cover.py`. ENGINEERING_STANDARDS.md (Enforcement) promises "mypy (strict per package, widening)". The lead's mypy run reports success over 1,551 files because these paths are unchecked, not because they are typed.
- Impact: The calls that cross module boundaries, which ARCHITECTURE.md calls the public surface, are exactly the ones mypy does not check. A renamed parameter on `can_use` or `solve_physics` passes CI.
- Fix: In each lazy `__init__.py`, add `if TYPE_CHECKING: from .entitlements import can_use as can_use …` generated from `_EXPORTS`, so the laziness stays at runtime and mypy sees real types. A test can assert that `_EXPORTS` and the stub block match. Then widen the strict override one package at a time, starting with `modules.billing`, `modules.memory`, `modules.todos` and `gateways`, and record the share in CI.
- Effort: M
- Verify: `reveal_type(can_use)` in a scratch file under mypy. `lazy_imports.py` reports 0. The `mypy_cover.py` share goes up per PR.

### CLAR-08 — `# type: ignore` comments have no reasons, and at least 10 suppress errors that no longer exist
- Severity: Low
- Confidence: High
- Locations: 30 ignores in production code, all with an error code and none with a reason (`scratch-clar/py_typing.txt`). Ten are on assignments that no longer error: `physics_op` became `str | None` in f6d18d066 (2026-10-02, "Read a stated law straight from the catalog"; apps/api/app/modules/physics/schemas/intent.py:61), and `chemistry_op` is `str` (modules/chemistry/schemas/intent.py:63). The stale lines are:
  - apps/api/app/modules/physics/extractors/school_common.py:33
  - rotational_readings.py:24
  - waves.py:227
  - rotation.py:128
  - energy_conservation.py:88
  - projectile.py:196, :227
  - suvat.py:264, :279
  - apps/api/app/modules/chemistry/binding.py:392

  `physics/binding.py:110`, written the next day (f348bc90c, 2026-10-03), passes `physics_op=chosen.spec.id` with no ignore. The stale ones predate the change: `git blame` puts `school_common.py:33` at ef6f00fde, 2026-09-28. `warn_unused_ignores` is on only in the strict override (pyproject.toml:139), so mypy never reports these.
- Evidence: `physics_op: str | None = Field(default=None, max_length=64)` against `def _intent(operation: str, …): … physics_op=operation,  # type: ignore[arg-type]`.
- Impact: Stale ignores also hide the next real error on the same line (`kind=kind  # type: ignore[arg-type]` sits beside them). ENGINEERING_STANDARDS rule 7 bans unexplained ignores.
- Fix: Delete the 10. Narrow `kind` with a `TypeAdapter(PhysicsKind).validate_python` or a typed table, so its 3 ignores go too. Turn on `warn_unused_ignores = true` globally (it only reports), and require `# type: ignore[code]  # reason` through a small grep test.
- Effort: S
- Verify: `uv run mypy --warn-unused-ignores app/modules/physics app/modules/chemistry` (lead to run) lists exactly these 10 before the change and nothing after.

### CLAR-09 — Production configuration lives in three places that disagree with each other
- Severity: Medium
- Confidence: High
- Locations:
  - fly.toml:30, :33, :36, :37 (`[env]`) override four code defaults. `WEB_SEARCH_CLASSIFIER_ENABLED="false"` against `web_search_classifier_enabled: bool = True` (apps/api/app/core/settings/search.py:10). `MEMORY_QUERY_EMBED_TIMEOUT_SECONDS="0.75"` against `2.0` (core/settings/memory.py:27). `CHAT_STREAM_CONNECT_TIMEOUT_SECONDS="5"` against `15` (core/settings/llm.py:52). `CHAT_STREAM_TIMEOUT_SECONDS="30"` against `45` (llm.py:47). Only the last field's comment mentions fly.toml (llm.py:43-46); the other three read as if the default were production.
  - apps/api/.env.production.example:57-59, :66 repeats the same four, and :47 sets `TRUSTED_PROXY_CIDRS=…,100.64.0.0/10,fdaa::/16`, which differs from the code default `…,127.0.0.1/32,fdaa::/16` (apps/api/app/core/settings/edge.py:12). fly.toml:23-26 says "The default TRUSTED_PROXY_CIDRS cover Fly's private ranges", while the example says "Fly's proxy connects from these RFC1918/CGNAT ranges". Which one production runs depends on whether someone copied the example into Fly secrets.
  - Names that outlived their scope: `math_solve_timeout_seconds` bounds physics and chemistry solves too (apps/api/app/modules/physics/prompt.py:45, :50, :96; chemistry/context.py:311, :314; chat/finalize_subjects.py:144, :220). `math_scan_read_rate_limit_per_hour` is "shared by every subject's reader" (core/settings/stem.py:48-49).
- Evidence: `scratch-clar/env_vs_defaults.py` (run after `settings_fields.py`). The settings package itself is clean: 209 fields, none declared twice, none unread, no reads of undefined fields, and one env read outside it (declines.py:58, the documented test switch).
- Impact: docs/ARCHITECTURE.md says "A setting … One field, with its default and a comment saying why". Here, developers and the test suite run the web-search classifier (an extra model call on the time-to-first-token path) and 15 s/45 s stream timeouts that production does not, so latency and fallback behaviour seen in development differ from production. The proxy CIDR disagreement decides whether per-IP rate limits key on the client or on Fly's proxy.
- Fix: Make each code default the production value and put development-only relaxations in `.env.example`, or keep the override and say "production: N (fly.toml)" in the field's comment. Add `tests/test_config.py::test_fly_env_matches_defaults_or_is_listed`, which parses fly.toml `[env]` and `.env.production.example` and fails on any value that is neither the default nor in an allowlist with a reason. Rename `math_solve_timeout_seconds` to `stem_solve_timeout_seconds` (keep the old env name as an alias for one release).
- Effort: S
- Verify: The new config test. `grep -n TRUSTED_PROXY_CIDRS` gives one value.

### CLAR-10 — Mapping a domain error to HTTP takes four forms, and the phone recovers meaning by parsing English
- Severity: Medium
- Confidence: High
- Locations:
  - Service-layer errors that carry HTTP status codes: apps/api/app/modules/chat/service.py:38 `ChatsError(detail, *, status_code)`, modules/todos/crud.py:25 `TodosError`, modules/images/generation.py:52 `ImageGenerationError`, modules/attachments/workflow.py:39 `AttachmentWorkflowError(status_code, detail)` (argument order reversed), modules/account/settings_proposal.py:80 `SettingsProposalError` (read as `.message`, account/api.py:400).
  - Services that raise `HTTPException` themselves: modules/speech/realtime.py (16, with bare `404`/`403`/`429` at :343-357 beside `status.HTTP_*` elsewhere in the file), modules/speech/gates.py:34-67, services/scan_read.py:61-99, modules/account/consent.py:48.
  - Per-route type mapping: modules/memory/api.py repeats `except MemoryWriteLockBusyError → 409 _LOCK_BUSY_DETAIL` seven times (:97, :130, :166, :178, :196, :216, :237). docs/ARCHITECTURE.md prescribes "one contextmanager when several routes share the mapping, as in attachments/api.py".
  - The shape of `detail` differs: usually an English string, sometimes `{"code", "message", …}` (account/api.py:84, account/consent.py:33-36).
  - Phone: `ApiRequestError` keeps the raw response body as its `message` (apps/mobile/lib/api/client.ts:115, :178, :194). Five modules each `JSON.parse` it again: features/chat/model/errorMessage.ts:10, features/attachments/model/attachmentErrors.ts:41, lib/scanner/scanReadError.ts:23, lib/api/consentRefusal.ts:21 and features/auth/model/accountExists.ts:16. Localisation is keyed on exact server sentences: lib/scanner/scanReadError.ts:10-16 maps `"Too many scans in a row. Try again in a few minutes."` (services/scan_read.py:32) to a locale key. attachmentErrors.ts:60-61 classifies by `/content type/i` and `/size/i` on the detail.
- Evidence: the quoted constructors and maps. No shared fixture pins the scan sentences on both sides; each side has its own test literal.
- Impact: A copy edit to a server message silently breaks the phone's localisation and error classification. Each new module picks one of the four styles, and HTTP concerns leak into services, which the tool loop and the WebSocket path also call.
- Fix: One `DomainError(code: str, message: str)` base in `app/exceptions.py`, with a single app-level exception handler mapping `code` → status (the `core/unavailable.py:69` pattern). Every refusal body becomes `{"detail": {"code", "message"}}`. On the phone, `ApiRequestError` parses once (`code`, `detail`), and readers switch on `code`. Keep the English for display only.
- Effort: M
- Verify: An architecture test that no module other than `api.py`, `routers/` or `core/` imports `HTTPException`. A contract fixture `docs/fixtures/error_codes.json` read by both test suites. `grep -n "JSON.parse(.*message" apps/mobile` returns nothing.

### CLAR-11 — Phone `catch` blocks that turn a server failure into a plausible result
- Severity: Medium
- Confidence: High
- Locations:
  - apps/mobile/features/chat/hooks/useChatActions.ts:133-140 `loadTranscriptMessages`: `try { return await api.listAllMessages(token, chatId); } catch { return messages; }`. `handleExportPdf` (:142-152) then exports a PDF of whatever page of messages is loaded (pages of 40). Its own `catch` → `reportRecoverableError(… "chat.export_pdf_failed")` never fires, because the error was already swallowed. The drawer's share path on the same data propagates the error (features/chat/hooks/useChatMenuActions.ts:84-90).
  - apps/mobile/lib/purchases.ts:139-141: `getOfferings()` failing (store or RevenueCat unreachable, misconfigured offering) returns `{}`, the same value as "no products". components/UpgradeSheet.tsx:233 then just disables the Subscribe buttons (`disabled={!pkg …}`) and `onSubscribe` returns early (:137). There is no message, no `reportRecoverableWarning` and no analytics event on the revenue path.
  - apps/mobile/features/memory/hooks/useMemoryDocuments.ts:107, :160, :176 collapse 409 "Memory is being updated right now — try again in a moment." (apps/api/app/modules/memory/api.py:29), 409 "Memory is off." (:133), 404, 422 and offline into `false`/`{ ok: false }`. The screen then shows one generic "Memory couldn't be updated".
- Evidence: 263 `catch` clauses in production phone code. 197 neither log, toast nor rethrow, and 88 of those carry a comment explaining the fallback, so most are deliberate (JSON parse fallbacks, best-effort device calls). These three are the ones where a server failure becomes a made-up success or an unexplained dead control. ENGINEERING_STANDARDS rule 8: "Never swallow a failure or return a made-up success." ES-17 and ES-18 fixed the cache and push cases; these were not in the ticket's list.
- Impact: A user exports "the whole chat" and gets the last page without being told. A store outage looks like Recall has no plans for sale, and nobody is alerted. A busy memory write looks like a broken one.
- Fix: Let `loadTranscriptMessages` throw (or return `{ messages, complete: false }` and say so in the PDF). Make `getPlanPackages` return `{ packages, error }`, show "Store unavailable, try again" and call `reportRecoverableWarning`. Have the memory hooks return the server's `code` or `detail` (after CLAR-10) and map 409-busy to its own retry toast.
- Effort: S
- Verify: Unit tests: `listAllMessages` rejects → `exportConversationAsPdf` not called and the error toast shown; `getOfferings` rejects → sheet shows the unavailable state; memory 409 → busy toast.

### CLAR-12 — List endpoints use five pagination shapes
- Severity: Low
- Confidence: High
- Locations:
  - apps/api/app/modules/chat/api.py:51-60 `GET /chats`: `limit` only (≤ 200, chat/service.py:34). The response is grouped `ChatListOut` (models/schemas/chats.py:72-79) with no continuation signal, so the 201st chat onwards never appears in the drawer list (search can still find it).
  - apps/api/app/modules/chat/api.py:180-193 `GET /chats/{id}/messages`: `limit` + `before` (UUID keyset), returning `{messages, has_more}` (chats.py:94-96).
  - apps/api/app/modules/todos/api.py:25-38 `GET /todos`: `limit`/`offset` as plain ints clamped by hand, returning a bare `list[TodoOut]`. apps/api/app/modules/todos/api.py:42-52 `GET /todos/page`: `limit` + `cursor` (UUID) validated by `Query(ge, le)`, returning `{items, next_cursor}`. The phone uses only `/todos/page` (apps/mobile/features/todos/api.ts:14).
  - apps/api/app/modules/attachments/api.py:58-66: `limit` + `offset`, returning `{items, has_more}` (attachments/schemas.py:47-49).
  - apps/api/app/modules/search/api.py:16-31: `limit` + `offset` (≤ 10000), returning `{results, total}`.
- Evidence: three list keys (`messages`, `items`, `results`), three continuation signals (`has_more`, `next_cursor`, `total`) and three cursor kinds (`before`, `cursor`, `offset`).
- Impact: Every client (phone slices, the planned web slices) writes a pager per endpoint. Offset paging over lists that change while you page (attachments, search) repeats or skips rows, which the keyset endpoints avoid.
- Fix: One `Page[T] = {items, next_cursor}` schema and one keyset helper in `repositories/`. Move attachments and search to it; give `/chats` a `next_cursor`. Retire the bare-list `GET /todos` once no installed client calls it.
- Effort: M
- Verify: An architecture test that every `GET` returning a list declares `response_model=Page[...]`.

### CLAR-13 — Stale comments: 16 path references to files that no longer exist (one is a "keep byte-for-byte identical" contract), and 19 changelog "BUG FIX:" notes
- Severity: Low
- Confidence: High
- Locations (from `scratch-clar/stale_paths.py` and `stale_paths_ts.js`, which check every path mentioned in a comment against `git ls-files`):
  - apps/mobile/lib/math/cameraPrompt.ts:1-4: "Must stay byte-for-byte identical to MATH_CAMERA_PROMPT in apps/api/app/services/math_image_extract.py". That file is gone; the constant is `apps/api/app/services/subject_scan.py:10`, and no shared fixture pins the two strings.
  - apps/api/app/core/config.py:85: the dev-auth "hard protection is the loopback guard on /auth/dev (see routers/auth.py)". `routers/auth` is retired (boundary_support.py `RETIRED_LEGACY_MODULES`); the guard is `core/dev_guards.py` and `modules/account/api.py:417`.
  - apps/api/app/modules/memory/consolidation.py:3-4: "the LLM call and the DB write live in background/memory_consolidation.py" (retired; now `memory/consolidation_workflow.py`).
  - apps/api/app/gateways/image_gateway.py:83 and modules/images/generation.py:337: `routers/attachments.py` (retired).
  - apps/api/app/services/reminder_timing.py:66-67: `reminder_emails.py`, `push_notifications.py`.
  - apps/api/app/modules/chat/stream_api.py:62: `ws.py`.
  - apps/api/app/core/settings/stem.py:25: `math_image_extract.py`.
  - Phone renames that left comments behind: apps/mobile/lib/math/latexCommands.ts:88, :119 (`mathFenceRetag.ts` → `lib/math/fenceRetag.ts`); lib/markdown/preprocessMathInline.ts:27, :39 (`mathText.ts` → `lib/math/latexPreprocess.ts`); lib/math/textMarkers.ts:3 (`markdownPreprocess.ts` → `lib/markdown/preprocess.ts`).
  - 19 `BUG FIX:` comments narrate history ("used to", "was the most severe correctness bug found in the audit"): for example modules/math/solve/parse.py:129, modules/math/solve/extract_eq.py:195, modules/math/tools/extractors/algebra.py:330, gateways/expo_push_gateway.py:19, services/routing.py:130, models/model_catalog.py:464, repositories/messages.py:164 (full list: `grep -rn "BUG FIX" apps/api/app`).
- Evidence: otherwise the comments are in good shape. Six trivial "what" comments in 280k lines, and every `keep in sync` pointer between the phone and the API (`web_search/distance_patterns.py` ↔ `lib/localPlacesQuery.ts`) names files that exist.
- Impact: A reader following the camera-prompt contract or the dev-auth security pointer finds nothing. History comments age into wrong claims.
- Fix: Repoint the 16 paths. Replace the camera-prompt comment with a shared fixture (`docs/fixtures/` already holds six), and rewrite `BUG FIX:` notes as present-tense reasons ("Only DeviceNotRegistered proves a token is dead…"). Add the two stale-path scripts as a test so renames update comments.
- Effort: S
- Verify: The two scripts report 0. A cross-side test reads `MATH_CAMERA_PROMPT` from one fixture.

### CLAR-14 — Names and constants that no longer say what they are (rule 10)
- Severity: Low
- Confidence: High
- Locations:
  - `GoogleAuthError` (apps/api/app/gateways/google_auth.py:29) is the app-wide "authentication failed" error. Apple sign-in raises it (gateways/apple_auth.py:67, :88, :104-111), as do JWT access-token checks (core/access_tokens.py:98-108), refresh and dev login (modules/account/tokens.py:223, :248; modules/account/service.py:217), and `SessionNotFoundError(GoogleAuthError)` / `CurrentSessionError(GoogleAuthError)` (tokens.py:346, :350). It is caught in core/deps.py:47, modules/chat/ws_api.py:272, :401 and account/api.py:143 (`apple_login` catches `GoogleAuthError`). That makes `core/` depend on a Google gateway module for its auth error type. It has been this way since the initial commit (7e31659b8); no rename followed Apple, JWT and sessions.
  - Underscore-private names are the shared API inside packages: 1,120 imports of `_name`s from another file (255 importing files, 180 source modules; 3 cross-domain, so the module-boundary tests are satisfied). The worst are `physics/extractors/common.py` (194 imports; `_find_value_with_specific_unit` 30, `_NUMBER` 27, `_LENGTH_UNIT_PATTERN` 25), `physics/solvers/common.py` (52; `_params_in_si` 28), `math/tools/block._finish_with_answer` (30) and `math/solve/parse._parse_expression` (23, the function ES-39 found returning wrong types). ES-40 split `chemistry/solvers/common_chem.py` for mixing jobs. `physics/solvers/common.py` ("Shared result types and SI-unit conversion", 282 lines) and `physics/extractors/common.py` ("lexical, cue, numeric, and unit extraction helpers", 336 lines) are the same pattern.
  - The same limit written twice with different values: custom instructions are capped at 1000 characters by the request schema (apps/api/app/models/schemas/auth.py:125) but cut at 2000 by two copy-pasted prompt builders (modules/chat/prompt_profile.py:109, modules/speech/live_talk.py:183). To-do text is ≤ 1000 by schema (modules/todos/schemas.py:44) but cut to 500 by both chat readers (todos/reminder_fence_parse.py:229, todos/spoken_add.py:225). The filename/label column width 255 is retyped in images/generation.py:371, images/search.py:177, images/reply_picture.py:75 and attachments/upload.py:43.
- Evidence: `scratch-clar/private_imports.py`. `grep -rn GoogleAuthError apps/api/app` gives 40 production references in 9 files.
- Impact: A leading underscore no longer tells a reader whether a change is file-local. A reader of `except GoogleAuthError` in the WebSocket handler would not guess that it covers revoked JWTs. Two numbers for one limit drift silently.
- Fix: Rename to `AuthenticationError` in `app/exceptions.py`, keeping `GoogleAuthError` as a subclass for the Google-only path. Drop the underscore from the 20 most-imported helpers and split each `common.py` by purpose (`units.py`, `readings.py`, `results.py`), as ES-40 did for chemistry. Put `CUSTOM_INSTRUCTIONS_MAX_CHARS`, `TODO_TEXT_MAX_CHARS` and the column width next to their schemas and import them in the readers. Ruff `PLC2701` (import-private-name) can ratchet the private imports.
- Effort: M
- Verify: `grep -c GoogleAuthError` limited to the Google gateway. `private_imports.py` count trending down. One definition per limit (grep).

### CLAR-15 — About 47 user-facing strings per locale are still English; the parity test checks keys, not translations
- Severity: Medium
- Confidence: High
- Locations: apps/mobile/lib/i18n/{de,es,fr,it,pt,ru,tr}.json each have 47–48 values of three or more words identical to `en.json`; `am.json` has 75. Examples from `de.json`: `settings.memory_clear_all_confirm_body` "This removes every saved fact. Recall can learn them again from new chats.", `chat.voice_permission_title` "Microphone access needed", `chat.scan_rate_limit`, `chat.scan_spend_cap`, `chat.model_unavailable`, `settings.push_register_failed` and `common.not_found_title`. Keys arrive in English in every locale at once: `chat.scan_rate_limit`, for example, was added to all nine files in English in 190a34984 (2026-10-03). apps/mobile/lib/__tests__/i18n.test.ts:19-29 asserts only "`${code}.json` has every en.json key".
- Evidence: `scratch-clar/i18n_untranslated.py` flattens every locale and counts values of three or more words that equal the English.
- Impact: Destructive-action confirmations, permission prompts and error toasts appear in English inside an otherwise German or Amharic app. CLAUDE.md's "9 locales, key parity tested" reads as full coverage, and the test is green.
- Fix: Translate the ~50 keys per locale. Add a test that fails when a non-English value equals the English one, with an allowlist for brand names, units and code (`rich.graph_expr_placeholder`, "Open in Maps"…).
- Effort: S (code), M (translation)
- Verify: The new test, with an allowlist of fewer than 10 entries per locale.

### CLAR-16 — A third of WARNING+ log lines carry no id, and the WebSocket and worker paths have no request id either
- Severity: Medium
- Confidence: High
- Locations: 97 of the 305 `warning`/`error`/`exception`/`critical` calls in API production code pass no arguments at all (`scratch-clar/log_calls.tsv`, column 6 empty). On the preferred chat transport:
  - apps/api/app/modules/chat/ws_turn.py:86 `logger.exception("Chat stream failed")`
  - :228 `logger.exception("Unexpected chat stream error")`; `chat_id` is a parameter of the enclosing `run_chat_stream` (:205)
  - apps/api/app/modules/chat/stream_events.py:265 "Finalize commit failed before done"
  - modules/chat/finalize_passes.py:225 "Post-stream enrichment failed; persisting the last committed text"
  - modules/chat/finalize_reminders.py:70
  - modules/chat/related_prompts.py:126, :129, :160, :194
  - modules/images/search.py:343, images/answer_photo.py:83, images/reply_picture.py:121
  - modules/account/tokens.py:147, :211, :298, :316, :342, :364, :426 ("… failed; Redis unavailable")

  apps/api/app/core/request_id.py:47 `class RequestIdMiddleware(BaseHTTPMiddleware)`. Starlette's `BaseHTTPMiddleware` passes WebSocket scopes straight through, so `request_id_context` is never set on `/ws/chat`, and the worker's jobs never set it either. No code calls `sentry_sdk.set_tag`, `set_user` or `set_context`, so Sentry events from these paths carry no user, chat or request id.
- Evidence: the formatter only appends `[request_id=…]` when the contextvar is set (core/logging.py:96-104). The convention elsewhere is `user_id=%s chat_id=%s` (for example modules/chat/turn_settle.py:121, modules/memory/retrieval.py:121), so these lines are the exceptions.
- Impact: At scale, "Chat stream failed" with a traceback and no id cannot be tied to a user report, a chat, or the `turn_cost` and `chat_stream_timing` lines of the same turn. Rate-of-error alerts cannot be split by model or plan.
- Fix: Set a turn-scoped contextvar (`turn_id`, `chat_id`, `user_id`) in `ws_turn.stream_over_ws` and `stream_api._stream_tokens_sse`, and a `job_id`/`job_type` one in `core/jobs/worker`. Have the formatters print it, and mirror it with `sentry_sdk.set_tag` (ids only). Make `RequestIdMiddleware` a pure ASGI middleware so WebSocket scopes get a request id. Add ids to the 97 context-free calls, starting with chat and account.
- Effort: S
- Verify: A test that a log record emitted inside a WebSocket turn carries `chat_id`. Re-run `log_args.py`: the WARNING+ calls without args drop to a short allowlist (startup and config warnings).

## Looked wrong, actually fine

- **Broad excepts after ES-39 and ES-18.** 338 broad handlers remain, down from 401 at the audit. Only 9 neither log nor re-raise nor use the exception, and each is a narrow, documented fallback: the SSRF guard fails closed (gateways/safe_fetch.py:47), a ZoneInfo fallback (todos/recurrence.py:26), the health probe (routers/health.py:47), Pint unit reads (physics/solvers/common.py:261, physics/working_steps.py:95), and the storage-delete retry enqueue (attachments/content.py:295). `modules/math` has 44, the 43 ES-39 left plus one, none a plain decline. No regression.
- **Settings access.** `os.environ`/`os.getenv` appears once (`math/solve/declines.py:58`, the documented `RECALL_STRICT_DECLINES` test switch). `get_settings()` and `Depends(get_settings_dep)` are used consistently. The only module-level read is `core/db.py:19`, which builds the engine. There are no duplicate or orphan fields (209 fields).
- **Datetime handling.** There is no `utcnow()`, naive `datetime.now()`, `date.today()` or tz-less `fromtimestamp()` in production. Every ORM timestamp is `DateTime(timezone=True)`. The 21 "if naive assume UTC" guards are defensive, not a sign of mixed handling.
- **Logger naming and style.** 160 of the 172 `getLogger` calls are `getLogger(__name__)`, and 167 modules bind it to `logger`. There are 0 f-string logger calls and 0 `print(` calls in production. `app.core.jobs` is a shared name on purpose across the six `core/jobs/*` files after the ES-32 split.
- **Comment style.** Comments overwhelmingly explain why. I found 6 trivial "what" comments in about 280k lines. Phone-to-API "keep in sync" pointers all name files that exist (CLAR-13 lists the ones that don't).
- **TypeScript.** There are 0 `any`, 0 `@ts-ignore`/`@ts-expect-error` and 1 `as unknown as` (`lib/markdown/parser.ts:10`, a markdown-it options object). Most of the 125 `!` are on array indexes, such as `lines[i]!` in `lib/markdown/preprocessMathFences.ts`. Without `noUncheckedIndexedAccess` (not set in `apps/mobile/tsconfig.json`) they are no-ops rather than unchecked casts.
- **Phone logging and Sentry.** 17 `console.*` calls, none with message text. The Live Talk debug log is `__DEV__`-only (`features/speech/model/realtimePeer.ts:91-97`). `lib/sentry.ts` drops console breadcrumbs, strips request bodies, `extra` and user fields, and redacts tokens. It is the stricter of the two scrubbers (see CLAR-01).
- **Inline magic numbers.** Only 42 numeric timeout, TTL or limit keyword arguments are inline in the API. Most constants are named (`_MEMORY_WRITE_LOCK_TTL`, `RESEND_TIMEOUT_SECONDS`, …). The real problem is limits written twice with different values (CLAR-14), not the count.
- **Response schemas.** Only five routes return an untyped `dict` instead of a Pydantic `response_model` or a `Response`: `health`, `ready`, `link_preview`, `consolidate_memories` and the realtime tool endpoint, which return small dicts.
- **Internal errors shown to users.** The chat stream maps known exceptions to fixed messages, and anything else to "Something went wrong. Try again." (apps/api/app/modules/chat/stream_events.py:347-372). Provider text is logged, never forwarded. The `HTTPException(detail=str(exc))` sites (modules/account/api.py:110-383, modules/analytics/api.py:23, core/deps.py:48) wrap exceptions whose messages are fixed strings (`GoogleAuthError("Invalid Apple ID token")`, `ValueError("Choose an uploaded photo…")`). The one wide catch is `update_me`'s `except ValueError` (account/api.py:382-383), which would surface any internal ValueError's text as a 400.
- **SymPy `Any`.** About 40 % of the 1,161 `Any` references are in `modules/math/solve/*`, where SymPy objects are untyped and `ignore_missing_imports = true` makes them `Any` anyway. That is not worth fighting.

## Open questions for the team

1. **TRUSTED_PROXY_CIDRS.** Do Fly secrets set it? If not, production runs the code default, which lacks `100.64.0.0/10`. `.env.production.example:45-47` says Fly's proxy connects from that range. Which list is right decides whether per-IP rate limits key on the client (CLAR-09).
2. **`WEB_SEARCH_CLASSIFIER_ENABLED=false` in production.** Should the code default follow production, so tests and development stop exercising a path production never runs? Or is the classifier meant to come back?
3. **Phone response validation.** `request<T>()` returns `data as T` (apps/mobile/lib/api/client.ts:181), so every API response is an unchecked cast, while rule 7 says to validate data from outside. Is the first-party API treated as trusted on purpose, with the ES-45-style parity tests as the contract? If so, record that as an exception in ENGINEERING_STANDARDS.md.
4. **Memory's fail-open switch.** `memory_switch_on` treats "an account row not loaded yet" as memory on (prompt_memory.py:98-100). For a privacy switch, is fail-open the intended default?
5. **`GET /todos`.** The phone uses only `/todos/page`. Is the bare-list, offset-paged `GET /todos` kept for installed builds or for the web slice, and when can it go (CLAR-12)?
6. **Function-local imports.** The ES ticket's "Noticed, not ticketed" counted "about 8". I measure 542 function-local imports of `app.*` modules in 161 files (652 at the audit). `test_import_cycles.py` deliberately leaves them out of the graph ("deferring an import is the accepted way to break a load-order cycle"). Is there a target, or is a deferred import now the standard way to break a cycle? It hides dependencies from the top of the file and from the cycle test.
7. **Mobile tests and type checking.** `tsconfig.json` excludes `**/__tests__/**`. The `lib` Jest project type-checks through ts-jest with an inline non-strict tsconfig, and the components project runs through babel-jest with no type check. Is that intended? This is for the tests auditor.
