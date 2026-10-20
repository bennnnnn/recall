# H. Tests as an asset (TEST-) — audit of d2ec42b0

Auditor: tests dimension. Read-only; no test suite was run by me. Where I quote test output it is
the lead's own runs in `tmp/code-audit/raw/pytest/` and `tmp/code-audit/raw/pytest-stale-venv/`.
Scratch scripts (source parsing only) are in `tmp/code-audit/raw/scratch-test/`.
Note: `apps/api/app/tests/security/test_zz_audit_io_counts.py` is an untracked file another
auditor created at 19:04 (not part of d2ec42b0); every count below is over `git ls-files` only.

## Metrics

| Metric | Value | How |
|---|---|---|
| API test files (`test_*.py`) / all `.py` under `app/tests` | 555 / 596 | `git ls-files apps/api/app/tests` |
| API test lines / test functions | 143,644 / 6,306 | `def test_` count |
| API `assert` statements / with a message / bare comparisons | 15,410 / 263 (1.7 %) / 13,199 (85 %) | `scratch-test/assert_msgs.py` |
| API `@pytest.mark.parametrize` uses | 1,609 | grep |
| API hypothesis use | 2 files, 10 `@given` (both `modules/math`); 0 in physics/chemistry | grep |
| API sleeps | 119 calls: 27 `sleep(0)` yields; 78 inside fakes; 21 non-zero waits in test bodies (≈3.8 s literal) | `scratch-test/sleeps.py` |
| API "hang until cancelled" fakes (`sleep(≥10)`, `Event().wait()`) | 28 in 15 files; 38 `asyncio.wait_for` guards suite-wide; no `pytest-timeout`; no CI `timeout-minutes` | grep |
| API wall-clock assertions (`perf_counter`/`monotonic` elapsed bounds) | 64 clock reads in 21 files; ~25 elapsed-bound asserts in 15 files (the regex-linearity budgets among them are deliberately loose) | grep |
| API wall-clock reads (`datetime.now`/`date.today`/`time.time`) | 127 in 42 files; no freezegun/time-machine; 2 home-grown frozen clocks (`quota_clock`, sweep `frozen_clock`) | grep |
| API `random` module use | 0 | grep |
| API skip / skipif / xfail | 0 / 0 / 3 (all `strict=True`, generated from `gap` entries); 1 runtime `pytest.skip` (Postgres unavailable, `core/test_db_timeouts.py:62`) | grep |
| Open `gap` entries (strict xfails) | battery 0 of 173 cases; sweep 0 of 1,574; STEM 0 of 1,471 | parsed `cases.py` + corpora JSON |
| STEM floors (answered, drawn) vs corpus answers | physics (574,162) of 597 answers/163 visuals; math (367,0) of 390/0; chemistry (166,0) of 175/0 | `test_stem_sweep.py:30` |
| API tests needing real Postgres | 21 files via `db_session` (savepoint rollback) + 5 `security/` files via committed rows + 5 other real-engine files | grep |
| `Settings(` constructions in tests / with `_env_file=None` | 1,574 / 36 | grep |
| `patch("dotted.path")` / of which private leaf | 2,910 / 66; `patch.object` 530 / 49 private; `monkeypatch.setattr` 182 | `scratch-test/patch_targets.py` |
| String patches into `app.modules.chat.*` internals / files using the `ChatTurnDeps` fakes | 343 / 25 files (87 uses) | grep |
| Mock interaction asserts (`assert_called*`/`assert_awaited*`) / `call_args` reads | 1,012 / 455 | grep |
| Asserts pinned to verbatim prompt copy | 209 in 33 files (conservative) ; 745 membership asserts with ≥4-word literals vs 281 with a named constant | `scratch-test/prompt_copy.py`, `const_vs_literal.py` |
| Unspecced fakes: `session = AsyncMock()` / `user = MagicMock()` / any `spec=`/autospec | 267 / 186 / 59 | grep |
| Fixture/helper families copied per module | `_settings()` 40 modules; `_user()` 31 (+ `make_user` 8); `FakeSessionCM`-style class 13 local copies beside the shared one in `chat_test_support.py`; `fake_session` fixture 9 (4 spec'd, 4 bare); `_answer` 21, `_verified_answer` 18 | `scratch-test/helper_families.py` |
| Top-level grab-bag API test files | 46 files, 13,117 lines (`test_routers.py` 3,097) | wc |
| Fix commits that touched app code / that also changed a test or corpus | 394 / 337 (86 %) | `git log` over full history, subject matches "fix" |
| Mobile test files / lines / `it`+`test` callbacks | 496 (287 `.test.ts`, 209 `.test.tsx`) / 66,720 / 4,158 (8 without an `expect`) | git ls-files; `scratch-test/mobile_noexpect.js` |
| Mobile duplicated mocks | `react-i18next` hand-mocked in 94 files (51 identical); 103 local re-mocks of modules `jest.componentsSetup.js` already mocks; `jest.mock` 1,201 calls; no `clearMocks`/`restoreMocks` in config, 129 of 284 mocking files never reset | grep |
| Mobile skipped | 7 `it.skip` (one generator, `lib/__tests__/graphExpr.test.ts:167`); 0 `xit`/`.only`/`.todo` | grep |
| Mobile snapshots | 4 files, 33 snapshots, 45 KB, compact custom serializers | `__snapshots__` |
| Mobile fake timers / real sleeps / global console mute | 32 files / 0 / none (7 targeted spies) | grep |
| Mobile `@/lib/api` mocks | 50 files, hand-written factories; 95 mocked keys, 0 absent from the real `api` object | `scratch-test/stale_api_mocks.js` |
| Mobile tests type-checked | `.test.ts` via ts-jest only; 209 `.test.tsx` never (`tsconfig.json` excludes `**/__tests__/**`, babel-jest) | config |

## Findings

### TEST-01 — Test isolation from real services is patched one consumer at a time; settings, Redis, DB and network still leak by default
- Severity: High
- Confidence: High (mechanism and history); Medium (which tests leak today: no live leak was proven statically)
- Locations:
  - `apps/api/app/core/config.py:48` `model_config = SettingsConfigDict(env_file=".env", ...)`: every `Settings()` reads `apps/api/.env` (per CLAUDE.md: Neon `DATABASE_URL`, Upstash `REDIS_URL`, provider keys). Tests build `Settings(` 1,574 times; 36 pass `_env_file=None`. Root conftest neutralises only `ENVIRONMENT`, `LITELLM_MODE`, `OPENROUTER_API_KEY`, `RECALL_STRICT_DECLINES` (`apps/api/app/tests/conftest.py:11-27`). `TAVILY_API_KEY`, `OPENAI_API_KEY`, `MATHPIX_*`, `RESEND_API_KEY`, `REVENUECAT_SECRET_KEY`, `R2_*`, `DAILY_TOKEN_LIMIT`, `DATABASE_URL`, `REDIS_URL` all still flow in.
  - Redis: 37 production modules call `get_redis_client()`; root conftest fakes 4 of them (`conftest.py:57` rest_rate_limit, `:93` llm_spend, `:105` structured_completion, `:127` ocr_allowance). A process-wide fake exists only in `apps/api/app/tests/security/conftest.py:225-228` (`use_fake_redis` patches `redis.asyncio.from_url`). CI gives the whole run one real `redis:7` (`.github/workflows/api-ci.yml:60-68,72`), never flushed.
  - Network: no socket guard (no pytest-socket / respx). `apps/api/app/gateways/web_search_gateway.py:227-237` tries DuckDuckGo *before* `if settings.mock_llm_enabled: return mock_search_results(...)`; default `web_search_fallback_enabled: bool = True` (`apps/api/app/core/settings/search.py:13`). DDG goes through `primp` (Rust HTTP client), which a Python socket guard would not even see. Opt-outs are per test: the battery (`apps/api/app/tests/behavior/harness.py:176,185` "Every feature on, no provider keys: nothing leaves the process") and a few web-search tests (7 references to `web_search_fallback_enabled` in 3 test files). `apps/api/app/gateways/pubchem_gateway.py:154-257` has no mock gate at all.
  - Database: unit tests reach the real asyncpg pool. Lead's run: `RuntimeWarning: coroutine 'Connection._cancel' was never awaited` during `modules/chat/test_chat.py::test_build_prompt_includes_chart_vega_hint` (`tmp/code-audit/raw/pytest/modules_chat.txt`) and `modules/account/test_account.py::test_export_returns_data` (`modules_account.txt`); `apps/api/app/tests/modules/chat/test_chat.py:1339-1340` keeps a local fake "to keep this unit test off the process-wide asyncpg pool". `scripts/check.sh:20-26` (the documented local gate) runs `alembic upgrade head` and the suite against whatever `.env` names; `security/conftest.py:97-180` commits rows there (deleted on teardown).
- Evidence (the class keeps recurring and is fixed per case):
  - `git log -S` on `apps/api/app/tests/conftest.py`: rate-limiter fake `eaf93cf7e` (07-02, "spurious 429s and order-dependent failures locally", `conftest.py:60`); `LITELLM_MODE` `f77bbe7ad` (10-18, #1874: "quota and entitlement default tests then failed locally ... and passed in CI" — fixed for "those two tests" with `Settings(_env_file=None)`); `OPENROUTER_API_KEY=""`, embedding refusal, OCR fake Redis `f51358c9a` (10-19, #1909: "the provider key from a developer's .env no longer turns mock mode off, the embedding provider is never called"); spend Redis `9dcfa20f1` and structured-invalid Redis `c7544b544` (10-19). Six isolation patches on 18-19 October alone.
  - `conftest.py:131`: OCR fake added because tests "would otherwise reach the real Redis (and a client bound to an earlier test's event loop)".
  - `_settings()` copies disagree: `modules/math/test_math_category_regressions.py:13` uses `Settings(_env_file=None)`, 26 other `_settings()` builders call plain `Settings(...)`.
  - Mobile has the same shape: Node 20 global `fetch` is live in both jest projects (`apps/mobile/jest.config.js:28`), 11 test files stub it individually.
- Impact: a developer's run is not the CI run (documented failures both ways); a test can spend paid quota (Tavily, OpenAI speech, Mathpix) or hit DuckDuckGo/PubChem from CI; shared Redis state makes results order-dependent; every new Redis/HTTP consumer silently reopens the hole until someone notices a flake.
- Fix: make isolation the default in `apps/api/app/tests/conftest.py`, before any `app` import: (1) one test settings source: either `os.environ` defaults for every infra/provider variable (keys `""`, `WEB_SEARCH_FALLBACK_ENABLED=false`, `DATABASE_URL`/`REDIS_URL` to local test services) or make `env_file` configurable (`RECALL_ENV_FILE`) and set it empty under pytest; (2) an autouse per-test FakeRedis for `redis.asyncio.from_url` + `get_redis_client.cache_clear()` (lift `security/conftest.py:225-228` to the root), with a `@pytest.mark.real_redis` opt-out; (3) refuse non-loopback egress: pytest-socket `--allow-hosts=127.0.0.1,localhost` plus an autouse patch that makes `ddgs.DDGS`/`primp` raise; (4) assert `DATABASE_URL` names a `*_test` database before `db_session`/`world` run, and point `scripts/check.sh` at it. Then delete the per-consumer fixtures that become redundant.
- Effort: M
- Verify: run the suite with network disabled (`unshare -rn` or pytest-socket) and with an `apps/api/.env` holding bogus keys and `DAILY_TOKEN_LIMIT=1`: pass count equals CI's. `grep -c "get_redis_client" conftest.py` drops to the one generic fixture.

### TEST-02 — Three tests cannot detect the regression they are named for
- Severity: Medium
- Confidence: High
- Locations:
  - `apps/api/app/tests/modules/web_search/test_web_search_run.py:166-191` `test_run_search_parallelizes_queries`: fakes sleep 0.04 / 0.01 / 0.01 s (line 175), so a *serial* `_run_search` takes 0.06 s, and the assertion is `assert elapsed < 0.08` (line 191). Present unchanged since the parallelisation commit `3ddbc0953` (2026-07-01). No other test checks the fan-out (`asyncio.gather` at `apps/api/app/modules/web_search/search_cache.py:139`).
  - `apps/api/app/tests/modules/chat/test_ws.py:879-938` `test_ws_done_waits_for_finalize_commit`: the only ordering check is `assert elapsed >= 0.0` (line 937), a tautology. `871ecfba3` (2026-07-15) inverted the behaviour ("done-after-finalize") and replaced the old meaningful `assert elapsed < 4` with this. A `done` sent before the commit still passes it (the failure-path test at `test_ws.py:941` covers the invariant only indirectly).
  - `apps/api/app/tests/test_services.py:369-388` `test_extract_and_store_skips_when_memory_disabled`: transcript is `"t"`. One- and two-letter lines are discarded as small talk (`apps/api/app/modules/memory/text.py:230`, reached from the candidate gate at `extraction_workflow.py:315`) before `revise_memory_facts` is reached, so deleting the memory-off gate (`apps/api/app/modules/memory/extraction_workflow.py:288-289`) keeps the test green. The file's autouse `_memory_persistence_gate_enabled` (`test_services.py:32-35`) also forces the third gate (`lock_memory_enabled`) open. Contrast the right pattern in the same area: `modules/chat/test_chat_history_rag.py:448-532` (`_index_a_turn`) runs the identical setup with memory on and off.
- Evidence: see lines quoted above; e.g. `await asyncio.sleep(0.04 if query == "slow" else 0.01)` … `assert elapsed < 0.08`.
- Impact: false confidence on three product promises: search fan-out latency, no "ghost done" with an unsaved message id, and "memory off means no personal recall" (CLAUDE.md) when a job was queued before the switch flipped.
- Fix: web search, make each fake wait on a shared `asyncio.Barrier(3)` (or "all started" events) inside `asyncio.wait_for(…, 1)`, the pattern already used at `modules/web_search/test_web_classifier_latency.py:159-188`; ws, assert `done` is not received while `release_finalize` is unset (receive with a short timeout on the thread, or assert the finalize task was done when `done` was built); memory, use a substantive transcript ("I live in Austin and work at Uber") and assert `revise_memory_facts` and `apply_memory_facts` were not awaited, plus a memory-on control with the same input. Then sweep the 945 tests whose only checks are negative (`scratch-test/negative_only.py`) for a missing positive control, starting with memory, consent, quota and billing names.
- Effort: S
- Verify: mutate each guarded line (serial loop, send `done` before awaiting, delete the gate) and see each test go red.

### TEST-03 — `--assert=plain` hides every failing value; it outlived the crash it worked around
- Severity: Medium
- Confidence: High
- Locations: `apps/api/pyproject.toml:73` `addopts = ["--assert=plain", "--import-mode=importlib"]`; the companion workarounds `.github/workflows/api-ci.yml:100-109` (suite split in two runs), `:45,117` (`ubuntu-22.04`); `scripts/check.sh:3,26` says it "mirrors CI exactly" but runs one invocation.
- Evidence: added in `9ede08cbf` (2026-07-01, #7: "Use plain assertions in CI to avoid rewrite crashes on Ubuntu runners ... split the suite to avoid runner segfaults"). The crash was later root-caused to the CPython 3.12.3 compiler and fixed by the `>=3.12.4` floor (`bb545e0d0`, 2026-08-12, #625; comment at `pyproject.toml:5-13`). The lead's own stale-venv run shows the cost: `tmp/code-audit/raw/pytest-stale-venv/modules_chemistry.txt:58-64` prints `assert getattr(constants, name) == pytest.approx(value, rel=1e-15)` then just `E AssertionError`, no actual value. 13,199 of 15,410 asserts (85 %) are bare comparisons with no message.
- Impact: every red test, in CI or locally, needs a re-run with prints to see what differed; flaky failures in CI are often not reproducible, so their one log is all there is.
- Fix: remove `--assert=plain` (keep `--import-mode=importlib`); collapse CI to the single invocation `check.sh` uses; drop the 22.04 pin if nothing else needs it.
- Effort: S
- Verify: a deliberately failing `assert 1 == 2` prints `assert 1 == 2`; CI green with one pytest step.

### TEST-04 — Concurrency and lease tests assert on wall-clock time or fixed sleeps
- Severity: Medium
- Confidence: High (mechanism); Medium (observed flake rate unknown)
- Locations:
  - `apps/api/app/tests/modules/chat/test_turn_prep_parallel.py:234-333`: four fakes sleep 0.25/0.25/0.30/0.30 s (lines 244-256), the test asserts `elapsed < 0.90` (line 329) on the whole prompt build. Costs ~0.55 s per run; fails if the event loop is held for ~0.35 s.
  - `apps/api/app/tests/core/test_jobs_inflight.py:209-236`: lease renewal every 0.03 s vs `_CLAIM_IDLE_MS` 150 ms with `sleep(0.05)` x8; a 150 ms stall lets the "peer" reclaim and the test fails. `:241-256` relies on `sleep(0.1)` exceeding a 50 ms idle.
  - Fixed "let it land" waits followed by a positive assert (can fail on a slow runner): `apps/api/app/tests/test_jobs.py:591` (`await asyncio.sleep(0.05)  # let the ack land` then a consumer count), `core/test_jobs_inflight.py:136,167,202` (`sleep(0.05|0.1)` then `assert await _pending(...) == 0`). Fixed windows before a negative assert (can only pass wrongly): `core/test_jobs_inflight.py:161`, `modules/chat/test_chatprep_lock.py:475`, `modules/chat/test_finalize_registry.py:180`. The rest of the 21 body sleeps are bounded polls and fine (`test_chatprep_lock.py:296-301` even says why).
  - `apps/api/app/tests/test_jobs.py:450-471` `test_process_entries_parallel_drain_faster_than_serial` (4x0.15 s jobs; `parallel_s < 0.45`, `serial_s > 0.50`), although the test just above it (`:422-446`) already proves concurrency with "all 5 started" before release; `apps/api/app/tests/modules/chat/test_chat_history_rag.py:234-273` asserts ordering as `recent_at["t"] - t0 < 0.1` against a 0.2 s fake.
  - About 25 elapsed-bound asserts overall; the regex-linearity ones (`modules/physics/test_physics_detection_speed.py:28-29`, `services/test_number_text.py:93,135`, `services/test_routing.py:287`, `modules/chemistry/test_chemistry_input_safety.py:71`) use deliberately loose budgets and are fine.
- Evidence: `await asyncio.sleep(0.25)` … `assert elapsed < 0.90, f"fetches ran serially (elapsed={elapsed:.2f}s)"`.
- Impact: under a busy runner (the team already saw macOS semaphore exhaustion when suites run in parallel) these fail with no code change; or they are loosened until they test nothing (TEST-02's web-search case).
- Fix: prove overlap with events (each fake sets `started[name]` then awaits a gate; the test asserts all started before releasing, wrapped in `asyncio.wait_for`), as `modules/web_search/test_web_classifier_latency.py:159-188` already does; drive leases with an injected clock or by calling the renew/reclaim functions directly; replace "let X land" sleeps with the `_wait_until(predicate)` helper that already exists at `core/test_jobs_inflight.py:48-53`.
- Effort: S
- Verify: `grep -n "assert elapsed <" ` limited to the documented linearity tests; run the touched files 50x under `stress -c $(nproc)` with no failure.

### TEST-05 — 2,910 string-path patches tie tests to import layout, and production code is being shaped to keep them working
- Severity: Medium
- Confidence: High
- Locations:
  - 2,910 `patch("app....")` (66 on a private leaf), 530 `patch.object` (49 private), 182 `monkeypatch.setattr` (27 private); most-patched privates: `app.modules.chat.turn_prep.augment._load_prior_user_messages` (9), `_stream_chat_once` (8), `_run_off_loop` (8), `app.modules.math.tools._build_verified_block_async` (7), `app.modules.todos.spoken_add._now` (6).
  - Chat: CLAUDE.md says chat tests "pass [a ChatTurnDeps] with fakes instead of patching" (`apps/api/app/modules/chat/turn_deps.py:1-8`), yet 343 string patches still reach into `app.modules.chat.*` (71 of them on per-module `SessionLocal`); worst files: `modules/chat/test_finalize_quota.py` 33, `test_ws.py` 27, `test_chat_stream_orchestration.py` 24, `services/test_tool_loop.py` 23, `modules/chat/test_chat_history_rag.py` 20. The deps helpers (`modules/chat/chat_test_support.py:40-134`) are used in 25 files.
  - Production shaped for patch targets: `apps/api/app/modules/billing/api.py:24-25` re-exports `_already_processed`/`_try_claim` from `revenuecat.py` and passes them back in (`:126-127`) so `test_routers.py:1747` `patch.object(webhooks_mod, "_try_claim", ...)` still bites (left by `8b81a40dc`, #863, when the logic moved); `apps/api/app/modules/todos/sync.py:103-106` ("Resolve apply via package so tests can patch todos_service.apply_todo_actions"); `apps/api/app/modules/memory/selection.py:1-6` (imports kept "so tests patching `app.modules.memory.format_memory_block` ... still intercept"); `apps/api/app/gateways/litellm_gateway.py:15-18` ("so a test patches each seam once, here").
  - 1,012 mock-interaction asserts (`assert_called*`/`assert_awaited*`) and 455 `call_args` reads.
- Evidence: the four production comments quoted above.
- Impact: a move or rename breaks hundreds of tests, or leaves a patch on a name the code no longer reads so the real dependency runs (TEST-01); production keeps aliases and function-local imports nobody needs at runtime; the module migration CLAUDE.md describes gets more expensive per file.
- Fix: finish moving chat stream tests onto `ChatTurnDeps` (`session_factory`, repos, quota) starting with the five files above; for billing pass `event_claim=`/`processed_check=` in tests and delete the `api.py` aliases; add an architecture test that ratchets the count of `patch("app.…._private")` targets and of string patches into `app.modules.chat`.
- Effort: L (incremental, file by file)
- Verify: count of string patches into `app.modules.chat` falls each release; `grep -n "so tests can patch"` in `app/` returns nothing.

### TEST-06 — 209 assertions pin verbatim prompt copy, next to a golden test built to be reword-proof
- Severity: Medium
- Confidence: High (count is a floor: only literals ≥4 words or ≥25 chars found verbatim in files whose path contains "prompt")
- Locations: 209 asserts in 33 files; top: `apps/api/app/tests/modules/chat/test_chat.py` 44 (e.g. `:112` "Email and message drafting", `:200-203`), `modules/chat/test_chat_teaching.py` 34 (`:191-194`), `services/test_compact_output_format.py` 21 (`:29`), `modules/chat/test_prompt_builder_style_hints.py` 19 (`:41`), `modules/chat/test_reply_shape_rules.py` 10, `modules/math/test_math_llm_extract.py` 9 (`:201`), `modules/math/test_math_tools.py` 8 (`:580`), `modules/chat/test_everyday_writing_routing.py` 8 (`:122`), `services/test_day_planning.py` 7 (`:72`), `modules/todos/test_service.py` 5 (`:661`). Suite-wide: 745 membership asserts on a ≥4-word literal vs 281 on a named constant.
- Evidence: `apps/api/app/tests/modules/chat/test_prompt_golden.py:1-13` stores prompts as `@CONSTANT_NAME` tokens: "Rewording a named constant leaves the fixture as it is; a change to which text a turn gets, or its order, fails here." The 209 literal asserts do the opposite.
- Impact: every wording change to a prompt constant reds a scatter of unrelated tests whose fix is re-pasting text; the tests then pin copy, not behaviour.
- Fix: assert by identity (`assert EMAIL_DRAFT_HINT in system`) or via the golden's token form; keep literal asserts only for safety phrases ("Never say you sent") and mark them so.
- Effort: M
- Verify: `scratch-test/prompt_copy.py` count trends to the agreed safety-phrase list.

### TEST-07 — Copied fakes drift apart; the bare copies change the contract they fake
- Severity: Medium
- Confidence: High
- Locations:
  - `fake_session` fixture copied into 9 modules: 4 are `AsyncMock(spec=AsyncSession)` (`apps/api/app/tests/repositories/test_chats.py:12-14`, `test_messages.py:11-13`, `test_usage.py:14-16`, `test_users.py:13-15`), 4 are bare `AsyncMock()` (`modules/attachments/test_repository.py:10-11`, `modules/memory/test_repository.py:11-17`, `modules/todos/test_repository.py:20-21`, `repositories/test_push_tokens.py:10-11`).
  - The bare copies turn the synchronous `AsyncSession.add` into a coroutine. Lead's run: `app/modules/attachments/repository.py:80: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited  session.add(row)` (and `:109`, `app/repositories/push_tokens.py:94`). `modules/attachments/test_repository.py:28` asserts `fake_session.add.assert_called_once()`, which also passes if the code wrongly wrote `await session.add(row)`.
  - Suite-wide: 267 `session = AsyncMock()` and 186 `user = MagicMock()` unspecced vs 59 spec'd mocks. An unspecced user answers every attribute with a truthy mock, e.g. `apps/api/app/modules/chat/prompt_memory.py:100` treats it as memory-on unless the test remembered to set it.
  - Session context-manager class: 13 local copies (`modules/todos/test_service.py:24`, `modules/chat/test_finalize_quota.py:16`, `modules/chat/test_chat.py:1339`, `modules/chat/test_turn_prep_parallel.py:27`, `modules/chat/test_compaction.py:12`, `modules/memory/test_memory.py:51`, `test_consolidation_job.py:16`, `test_extraction_job.py:22`, `test_instruct.py:15`, `test_push_scheduler.py:16`, `background/test_billing_reconcile_scheduler.py:12`, `test_jobs.py:17`, `test_services.py:15`) beside the shared `modules/chat/chat_test_support.py:21`. `_settings()` builder in 40 modules, `_user()` in 31 (+ `make_user` 8), `_answer` 21, `_verified_answer` 18.
  - Mobile, same family: `jest.mock("react-i18next", …)` is hand-written in 94 files (51 are the identical identity `t: (key) => key`); 103 local re-mocks in `.test.tsx` files of modules `apps/mobile/jest.componentsSetup.js` already mocks globally (`react-native-safe-area-context` 45, of which 30 are the same zero insets the global mock gives; `expo-clipboard` 26; `expo-haptics` 24, whose 17 identical local copies drop the `ImpactFeedbackStyle` enum the global mock provides).
- Evidence: the `RuntimeWarning` lines above from `tmp/code-audit/raw/pytest/modules_attachments.txt` and `services.txt`.
- Impact: tests pass against fakes that accept calls the real object rejects; fixing a fake means finding its copies; reviewers can't tell which copy is "right".
- Fix: one `apps/api/app/tests/fakes.py`: `fake_session()` = `AsyncMock(spec=AsyncSession)` (sync `add`/`add_all`/`expunge` come out as MagicMock), `session_cm(session)`, `make_user(**overrides)` returning a real `User(...)` or `MagicMock(spec=User)`, `test_settings(**overrides)` = `Settings(_env_file=None, **overrides)`; replace the copies; lint (architecture test) against new local `class _FakeSessionCM`. Mobile: a `__mocks__/react-i18next.ts` (or a setup-file mock) for the identity translator, and delete local re-mocks that equal the global ones in `jest.componentsSetup.js`.
- Effort: M
- Verify: zero `coroutine ... never awaited` warnings from repository tests; copies count → 1 per family.

### TEST-08 — The property-based testing rule is applied to maths only
- Severity: Medium
- Confidence: High
- Locations: rule `docs/ENGINEERING_STANDARDS.md:94` ("Use property-based tests (`hypothesis`) for invariants over wide input ranges"); users: `apps/api/app/tests/modules/math/test_math_properties.py` (9 `@given`) and `modules/math/test_math_triangle_laws.py:207` (1). None for physics or chemistry, though they have natural invariants: `apps/api/app/modules/chemistry/equations.py:73` `balance_equation` (atoms conserved), `modules/chemistry/nuclear.py:190` `balance_nuclear` (A and Z conserved), `modules/chemistry/quantity.py:41` `convert` (round trip), `modules/physics/solvers/common.py:85` `quadratic_roots` (roots satisfy the equation), `services/number_text.py:157` `fold_scientific`.
- Evidence: `grep -rl "from hypothesis" apps/api/app/tests` → 2 files. One property runs non-derandomised (`test_math_properties.py:45` `@settings(max_examples=100, deadline=None)`), so CI explores new random inputs per run with no saved example database: an unrelated PR can go red (that is how `@example(text="P❶")` at `:43` was found).
- Impact: STEM correctness is a release requirement (`ENGINEERING_STANDARDS.md:85`); the STEM corpus checks chosen examples, not the invariants that make a whole family right.
- Fix: add ~6 cheap properties for the functions above; register a CI profile (`settings.register_profile("ci", derandomize=True)`) and keep random exploration local or nightly.
- Effort: S
- Verify: `grep -rl "@given" apps/api/app/tests/modules/{physics,chemistry}` non-empty; CI loads the `ci` profile.

### TEST-09 — No per-test or per-job timeout; hang-style fakes rely on the code under test to time out
- Severity: Low
- Confidence: High
- Locations: no `pytest-timeout` in `apps/api/pyproject.toml:49-58`; no `timeout-minutes` in `.github/workflows/api-ci.yml` (GitHub default 360 min); no `testTimeout` in `apps/mobile/jest.config.js`. 28 never-returning fakes in 15 files (e.g. `apps/api/app/tests/modules/web_search/test_web_search_run.py:474` `sleep(3600)` guarded only by the code's own `_DDG_TIMEOUT_SECONDS`; `test_jobs.py:932` `sleep(3600)` then an unguarded `await started.wait()`; `test_gateways.py:1146`; `modules/web_search/test_web_classifier_latency.py:167,204,279,328`; `background/test_periodic.py:54,76,105`) against 38 `asyncio.wait_for` guards suite-wide.
- Evidence: e.g. `async def never_finishes(...): await asyncio.sleep(3600)` patched over `asyncio.to_thread`.
- Impact: a regression in a timeout/cancel path becomes a CI job that hangs for hours (blocking the deploy gate, `scripts/require-green-ci.sh`) instead of one red test.
- Fix: add `pytest-timeout` (`timeout = 60`, method thread) and `timeout-minutes: 30` on the API and mobile jobs; mobile `testTimeout` stays at jest's default 5 s.
- Effort: S
- Verify: a test that awaits `asyncio.Event().wait()` fails after 60 s locally.

### TEST-10 — Runtime warnings that flag broken fakes are ignored
- Severity: Low
- Confidence: High
- Locations: `apps/api/pyproject.toml:69-73` has no `filterwarnings`. From the lead's run: `app/modules/chat/stream_paths.py:311` "coroutine ... never awaited" ×14 (`modules/chat/test_chat_stream_orchestration.py`, `test_stream_scaffold.py`: async generators finalised after the test ended); `coroutine 'WebSocket.receive_json' was never awaited` (`modules/chat/test_ws.py::test_ws_passes_client_timezone_to_stream`); `Connection._cancel` never awaited (real asyncpg in unit tests, TEST-01); `session.add` never awaited (TEST-07); `PytestUnraisableExceptionWarning: '_RecordingSession' object has no attribute 'close'` (`gateways/test_external_timeouts.py` fake lacks the real interface).
- Evidence: warnings summaries in `tmp/code-audit/raw/pytest/{modules_chat,modules_attachments,services,gateways,modules_account}.txt`.
- Impact: each warning is a test whose fake or cleanup is wrong; nothing makes anyone look.
- Fix: `filterwarnings = ["error::RuntimeWarning", "error::pytest.PytestUnraisableExceptionWarning"]` (with explicit ignores for third-party noise such as the Starlette `httpx` deprecation), then fix the ~20 offenders.
- Effort: S
- Verify: suite green with the filter on.

### TEST-11 — Module tests live in grab-bag files by date or theme
- Severity: Low
- Confidence: High
- Locations: 46 top-level files, 13,117 lines under `apps/api/app/tests/`: `test_routers.py` 3,097 lines holds 27 RevenueCat webhook tests (auth, replay dedupe, concurrent claim, stale event, sandbox: lines 495-2108) and 32 speech tests (2269-3083), while `tests/modules/billing/` has 3 files/371 lines (37 tests) and `tests/modules/speech/` exists; also `test_services.py` 1,010, `test_new_features.py` 701, `test_misc.py` 538, `test_optimizations.py` 210, `test_model_switch_oct_2026.py` 297.
- Evidence: `grep -c "def test_revenuecat" apps/api/app/tests/test_routers.py` → 27.
- Impact: `pytest app/tests/modules/billing` (what a billing change runs) skips the webhook's idempotency and auth tests; names like `new_features`/`misc`/`oct_2026` give no owner.
- Fix: move by owning module (`git mv` + split), then an architecture test that limits `app/tests/test_*.py` to an allow-list.
- Effort: S
- Verify: `pytest app/tests/modules/billing` collects the webhook tests.

### TEST-12 — Leftover process state between tests: a tool registry, a JWKS cache, the cached settings, and real-clock dates beside a frozen-clock fixture
- Severity: Low
- Confidence: Medium (no current victim proven)
- Locations:
  - `apps/api/app/tests/test_mcp.py:222-235` (`test_mcp_registry_sympy_absent_when_math_tools_disabled`) ends with `setup_mcp_adapters(Settings(math_tools_enabled=True))` and never clears the process-wide `_REGISTRY` (`apps/api/app/gateways/mcp/registry.py:15`), so later tests that reach `_tools_for_user` (`apps/api/app/modules/chat/tool_loop/selection.py:204`) see four adapters built from a `.env`-reading `Settings()`. The job registry shows the right pattern (`patch.dict(queue._HANDLERS)`, `core/test_jobs_inflight.py:25-28`).
  - `apps/api/app/tests/test_apple_auth.py:138-178` assigns `apple_auth._jwks_cache`/`_jwks_fetched_at` and never restores them.
  - `apps/api/app/tests/test_auth_dev.py:9-17` flips `dev_auth_enabled` on the process-wide cached `get_settings()` object and restores it on the next line without `try/finally`, so any exception in the request leaves dev auth off for every later test that reads `get_settings()`.
  - `apps/api/app/tests/services/test_quota.py:81,131,259,269,280` compute `day = datetime.now(UTC).date()` while the code under test calls `utc_today()`; the `quota_clock` fixture (`app/tests/conftest.py:43-53`) exists for exactly this and is used in 7 test files, including other tests in `test_quota.py` itself. Same in `repositories/test_usage.py:25,41`.
  - The sweep's home-grown frozen clock (`apps/api/app/tests/behavior/sweep.py:263-299`, added after "On the real clock those turns failed whenever the suite ran after 16:00 UTC") patches only modules that did `from datetime import datetime`; `time.time()` readers (7 production sites, e.g. `apps/api/app/modules/notifications/push.py:79`) and `date.today()` stay live. No freezegun/time-machine; 127 wall-clock reads in 42 test files.
- Impact: order- or time-of-day-dependent results that are hard to reproduce.
- Fix: `patch.dict(registry._REGISTRY)` autouse (or snapshot/restore in `test_mcp.py`), `monkeypatch.setattr` for the JWKS globals and the cached settings (or a dependency override with a fresh `Settings`), use `quota_clock` in the quota tests, adopt time-machine (or one injected clock) instead of module-by-module patching.
- Effort: S
- Verify: `pytest -p no:randomly app/tests/test_mcp.py app/tests/services` and the reverse order give the same result; run quota tests with time-machine at 23:59:59.999.

### TEST-13 — Mobile component tests are never type-checked
- Severity: Low
- Confidence: Medium (mechanism certain; number of current type errors not measured)
- Locations: `apps/mobile/tsconfig.json` `"exclude": ["**/__tests__/**"]` (so `pnpm typecheck`, `package.json:106`, skips all tests); `.test.ts` files are checked by ts-jest at run time, but the 209 `.test.tsx` files run through `babel-jest` (`apps/mobile/jest.config.js:62-66`), which strips types. Exclusion dates from the bulk commit `fa9691358` (2026-06-28) with no stated reason.
- Evidence: config lines above.
- Impact: a renamed prop or changed hook shape keeps compiling in the tests that should catch it; mocks typed `as unknown as` (13 in `.test.tsx`) drift unseen.
- Fix: a `tsconfig.test.json` that includes `__tests__` and a `pnpm typecheck:tests` step in Mobile CI (or drop the exclude once errors are fixed).
- Effort: S-M (depends on the error count)
- Verify: `tsc --noEmit -p tsconfig.test.json` exits 0 in CI.

## Critical paths, by reading (what is covered, and the branches that are not)

| Area | Covered (test that proves it) | Untested or weakly tested branch |
|---|---|---|
| Quota | refund on any escape from `turn_resources` (`modules/chat/test_turn_quota_reserve.py:225`); cancel (`test_stream_quota.py:103`); image-gen pre-reserve (`test_stream_quota.py:68`); finalize-owned reservation not refunded twice (`test_chatprep_lock.py:399`); regenerate (`test_regenerate_image_input.py:157`, `test_finalize_quota.py:143`); counter refund after midnight (`services/test_quota.py:370`) | Midnight race in the quota tests that read the real date (TEST-12). Nothing significant otherwise. |
| Auth | reuse revokes all (`modules/account/test_tokens.py:67`); concurrent refresh one winner (`test_session_reliability.py:130`); lost WATCH stays retryable (`:109`); purge includes a session issued mid-snapshot (`:155`); logout/purge (`test_tokens.py:138-194`); revoke other session (`:263,290`); dev auth refused in production (`test_config.py:99`); `/auth/dev` loopback (`test_dev_guards.py`, `test_auth_dev.py:9`) | `app/modules/account/tokens.py:245-248`: refresh for an account whose user row is gone (revoke that refresh token, "User not found") — no test feeds `users_repo.get_by_id → None` into `refresh_token_pair` (checked `test_tokens.py`, `test_session_reliability.py`, `test_redis_unavailable.py`). |
| Memory | explicit fact survives the cap (`modules/memory/test_erase_db.py:156`, DB, cap 4); mute keeps fact, stops recall (`test_erase_db.py:112`); sensitive skipped unless opted in, with a positive control (`test_extraction_job.py:607,630`); memory off ⇒ no prompt memory, no history RAG, no indexing, no job enqueue (`modules/chat/test_prompt_memory.py:79`, `test_chat_history_rag.py:530`, `test_chat_stream_orchestration.py:154`) | Worker-level memory-off gate (`app/modules/memory/extraction_workflow.py:288-289`): its test cannot fail (TEST-02). Cap eviction order (`app/modules/memory/ops.py:107-131`: `_CAP_EVICT_ORDER` at `:32`, protected profile facts ≥0.75 importance at `:33,128`): `evict_for_cap` is never called by a test; the one cap test uses four `focus` facts. |
| Streaming | SSE disconnect, hung producer cancelled, partial reply saved (`modules/chat/test_chat_stream.py:83-230`); finalize failure → `error`, timeout → `persisting` (`test_ws.py:941,981`); shutdown stops in-flight streams (`test_finalize_registry.py`, `test_process_bootstrap.py`, `test_shutdown_signal.py`) | `done` only after the commit: `test_ws.py:879-938` asserts a tautology (TEST-02); covered indirectly by the failure-path test. |
| Billing | auth 401/503, body cap, replay dedupe, hashed id, concurrent claim, failed processing keeps the dedupe key, stale vs newer events, sandbox in prod/dev, subscriber lock busy (`app/tests/test_routers.py:495-2108`); expiration/grace/refund rechecks and transfer (`modules/billing/test_webhook_events.py`) | `app/modules/billing/revenuecat.py:266-279,358-359` `_advance_transfer_watermarks`: transfer tests patch `advance_rc_event_watermark` with a bare `AsyncMock()` and never assert it (`modules/billing/test_webhook_events.py:54`), so "an old EXPIRATION for the source account after a TRANSFER is ignored" is unverified. `revenuecat.py:312-316` (non-TRANSFER event with no `app_user_id`: claim released, event dropped) untested. |

## API skips, xfails and gaps; the 7 skipped jest tests

- API: no `skip`/`skipif`; one runtime `pytest.skip` when Postgres is unreachable (`apps/api/app/tests/core/test_db_timeouts.py:62`); 3 `xfail` call sites, all `strict=True`, generated from corpus `gap` fields (`behavior/test_battery.py:17`, `test_sweep.py:20`, `test_stem_sweep.py:37`). Open gaps: 0 of 173 battery cases, 0 of 1,574 sweep turns, 0 of 1,471 STEM entries.
- Mobile: the 7 skips are one loop, `apps/mobile/lib/__tests__/graphExpr.test.ts:166-168`, one placeholder per `phone_gap` case in the shared server/phone fixture `docs/fixtures/graph_expr_cases.json`: `sin x`, `cos 2x`, `sqrt x`, `log x` (server applies a bare function name; phone does not), `√x` (server rewrites √ first), `|x|` (server pairs bars into Abs), `xe^x` (server splits `xe` into x·e). The behaviour is still asserted: `graphExpr.test.ts:170-177` checks the phone *refuses* each of those forms, and the server's bracketed form travels in the fence (checked at `:151-160`).

## Looked wrong, actually fine

- **Strict xfails from `gap` entries** (`behavior/test_battery.py:16-18` etc.): `strict=True`, so a fixed gap goes red until its line is deleted. Zero open.
- **The 7 jest skips**: reporting placeholders, not hidden tests (above).
- **Real-Postgres isolation**: `db_session` wraps each test in an outer transaction with savepoints (`apps/api/app/tests/conftest.py:178-205`); the `security/` world commits on purpose because API code opens its own `SessionLocal` (reasoned in `security/conftest.py:1-8`), uses uuid-unique accounts and deletes them on teardown.
- **Regex-linearity time budgets** (`modules/physics/test_physics_detection_speed.py:1-8,28-29`, `services/test_number_text.py:93,135`, `services/test_routing.py:287`): wall-clock, but budgets are 10-100x a linear run and the docstrings say why.
- **Job-handler registry hygiene**: `patch.dict(queue._HANDLERS)` autouse in the job tests (`core/test_jobs_inflight.py:25-28`); global writes in `test_jobs.py:96-161` are restored in `finally`.
- **Behavior battery / sweep / STEM sweep**: offline, frozen clock for the sweep, providers stubbed (`behavior/harness.py:175-198`), corpora well-formed checks (`test_stem_sweep.py:63-72`); STEM answer floors sit 9-23 below the corpus answer counts.
- **Regression-test discipline**: 337 of 394 fix commits that touched app code also changed a test or corpus (86 %); the misses are mostly visual UI fixes.
- **Mobile**: 0 real sleeps, fake timers in 32 files, console muted only in 7 targeted spies with restores in most; 8 of 4,158 test callbacks lack an `expect`; snapshots are 4 small, custom, reviewable serialisations; the 50 hand-written `@/lib/api` mock factories name 95 methods and none is missing from the real `api` object; all 496 test files are matched by a jest project (checked with micromatch against `jest.config.js`).
- **Test-side prompt helpers** (`app/tests/modules/math/prompt_support.py`, `app/tests/modules/web_search/augment_support.py`, 82 call sites) re-create a two-line composition that production also does (`app/modules/chat/prompt_builder.py:169-183`, both via `inject_before_last_user`); moved out of production as dead code in `e64a70326`. Low risk, noted only.
- **Hypothesis settings**: 9 of 10 properties are `derandomize=True, deadline=None`, so they are deterministic (the one exception is in TEST-08).

## Open questions for the team

1. Is `apps/api/.env` on developer machines pointed at the Neon/Upstash dev services when people run `./scripts/dev.sh check`? If yes, TEST-01 is writing test rows and running migrations against the same database the local app uses.
2. Is there still a reason for `--assert=plain`, the two-step CI pytest run and the `ubuntu-22.04` pin now that the 3.12.3 segfault is fixed by the version floor?
3. Should the worker re-check memory-off at all (`extraction_workflow.py:288`), or is the enqueue-time check (`post_turn.py:80,105`) the contract? The answer decides whether TEST-02's third case needs a real test or the gate can go.
4. Do you want the property-testing rule (`ENGINEERING_STANDARDS.md:94`) to cover physics and chemistry solvers, or only the maths extractors?
5. Would you accept a ratchet test on string-path patches into `app.modules.chat` (count may only go down) to finish the `ChatTurnDeps` migration?
6. Lead verification ideas: (a) re-run one area with `-W error::RuntimeWarning` to size TEST-10; (b) run `tsc --noEmit` with `__tests__` included to size TEST-13; (c) mutate `search_cache.py:139` to a serial loop and `extraction_workflow.py:288-289` to `pass` and confirm TEST-02's tests stay green.
7. `apps/api/pyproject.toml` `[tool.coverage.run] omit` still drops `app/background/push_scheduler.py` ("covered via service-layer mocks", added in `023316c7f` while raising coverage to 80 %), yet `app/tests/test_push_scheduler.py` now imports and exercises it. Keep the omit?
