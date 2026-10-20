# Recall code-health audit

## 1. Header

- **Commit audited:** `d2ec42b0a9d546b0dd22ff2cb569443c3b38ab6f` on `main` (2026-10-20 14:26 −0400, "Physics working: the law's name heads it, givens show their factor, the arithmetic reaches the answer (#1920)"). `origin/main` moved to `09a8b39d` during the audit; the audit stayed on `d2ec42b0`.
- **Date:** 2026-10-20.
- **Time spent:** about 1 h 26 min of wall-clock time (18:48–20:15 UTC). Ten read-only investigators ran in parallel, one per dimension (D and F were each split in two), for 30–40 minutes each, about 5.5 investigator-hours in all. The lead then verified every finding at its cited lines, ran all measurements and test suites one at a time, and reproduced the main issues against the real code. Six drafting agents condensed the verified findings into this report's format. The lead reviewed every section (fixing three line numbers and one config list on the way) and wrote the summary, scorecard, metrics, quick wins and roadmap.
- **Environment:** adapted from the brief, because this ran in a cloud container, not the team's Mac.
  - Repository at `/home/user/recall` in the container; the audit ran in a separate worktree, `/home/user/recall-audit`, detached at `d2ec42b0` and removed afterwards. Output was written to `tmp/code-audit/` and is committed in this folder, `docs/audits/2026-10-20-code-health/`.
  - Database-backed tests used a local PostgreSQL 16.15 (pgvector 0.6.0) at migration head `0115` and a local Redis 7.0.15. Neon and production were never touched, and no migration was run.
  - The clone was shallow (125 commits), so the full history (2,749 commits) was fetched before any `git log` or `git blame` conclusion was drawn.
  - The shared API venv was stale against this commit's `uv.lock` (Pint 0.24.4 instead of 0.26.1, plus 7 minor bumps), and three chemistry constant tests failed because of it. A venv was built from the frozen lockfile (`uv sync --frozen --all-groups`; lockfile untouched) and every suite was re-run. The stale-venv run is kept in `raw/pytest-stale-venv/`.
  - Tests ran on Python 3.13.16. Production and CI pin Python 3.12, which may affect timings slightly.
- **Tools run (versions):**
  - API checks: ruff 0.17.0 (check and format), mypy 2.4.0, pytest 9.1.1 with pytest-cov 7.1.0.
  - Analysis, via `uvx`: pylint 4.1.3 (duplicate-code), vulture 2.16, radon 6.0.1, deptry 0.25.1.
  - Mobile, via `npx --yes` / pnpm: jscpd 4.3.0, knip 6.42.1, depcheck 1.4.7, tsc 6.0.3, ESLint 9.39.4, jest 30.5.2. Node 22.22.0, pnpm 9.15.9.
  - Lead scratch instruments (raw output under `raw/`):
    - a SQLAlchemy `before_cursor_execute` listener, pool `checkout` events, asyncpg call counters and fake-Redis command counters on the real app (`world` fixture: real middleware, auth and routers, mock model);
    - a `pg_stat_activity` probe taken mid-stream;
    - timing probes of the real reader functions, run in a subprocess with a timeout;
    - a micro-benchmark of memory ranking.
  - The scratch test lived only in the worktree and was deleted with it.
- **Out of scope:**
  - `apps/web` (a deferred slice).
  - A full security audit; only security-adjacent notes were taken (§5.S).
  - Production data: no `EXPLAIN` on production-sized tables, so index findings name the `EXPLAIN` that would settle them.
  - Live provider calls (no chat messages sent, no paid API used), native device builds, Fly and Neon configuration beyond what the repo holds.

## 2. Executive summary

Recall is unusually well engineered for its age, and well above the typical bar for a product at this stage.

- **Guardrails CI enforces:** module boundaries, import cycles, retired paths, pure solvers, migration safety, and a file-size ratchet.
- **Clean baselines:** ruff, mypy, tsc and ESLint report no errors.
- **Tests:** 25,598 API tests and 7,036 phone tests, all green, with 91.9% API coverage. Every critical area (quota, auth, memory, billing, chat, jobs) is above 90%.
- **Behavioural corpora:** behaviour, sweep and STEM, with zero open gaps.
- **Documentation:** SCALING.md and ARCHITECTURE.md are candid about per-machine state.

The gap to a Google-scale production bar is real but concentrated in a few classes:

1. **Unbounded work on the single event loop.** One crafted chat message freezes every socket on an API machine for a minute (measured) or for hours (by extrapolation). Separately, memory recall ranks every fact in pure Python on every memory turn.
2. **Database hygiene at scale.**
   - Five foreign keys have no index, so account and chat deletion will hit the 120 s statement timeout.
   - Connections stay idle-in-transaction through streams and slow I/O.
   - A per-session round-trip tax costs 27 round trips for 7 statements per turn.
   - Embeddings are stored twice, and two append-only tables are never pruned.
3. **Background work that is silently lost.**
   - History compression effectively never runs on active chats.
   - The stream trim drops jobs no worker has read.
   - Retries all happen within about 6 s.
4. **Observability that cannot see trouble.**
   - Nothing measures loop lag, the DB pool or the executors.
   - The model-health breaker records the wrong model and never half-opens.
   - 91 swallowed errors log at DEBUG under an INFO root logger.
   - User content reaches logs and Sentry.
5. **A long tail of rules written twice.** Two of the copies already give wrong answers to students: water + ethanol is "verified" at 60 °C instead of about 66.5 °C, and a two-equation system is laid out with a row stating x + y = 5.

The two Critical items should be fixed before launch, and both have small instance fixes. Most High items are effort S.

**Top ten issues, by impact × likelihood**

1. [SCALE-01](#scale-01) — One chat message can stall an API machine's event loop for minutes or hours. Exponential regex in a physics reader; unbounded SymPy power towers in a maths reader. Reproduced: `graph 2y = 9^9^8 + x` blocks for 56 s. *Critical.*
2. [SCALE-02](#scale-02) — Five unindexed foreign keys turn every message, chat and memory delete into scans of the referencing tables. Account deletion, which App Store review requires, will time out at scale. *Critical.*
3. [LEAK-01](#leak-01) — Pooled DB connections stay idle-in-transaction across SSE streams, image generation, thumbnails and waits. Measured on the real app. One gallery open or a burst of slow requests can drain a machine's 30-connection pool. *High.*
4. [SCALE-03](#scale-03) — History compression runs at most once per chat per day, and that first run is a no-op. Long chats silently drop their middle from the prompt. *High.*
5. [DUP-01](#dup-01) — "Water only" is written twice in physics. Water mixed with ethanol is answered as a verified 60 °C; the correct answer is about 66.5 °C. Reproduced. *High.*
6. [DUP-02](#dup-02) — Both calculation-layout twins lay out `$x + y = 10, 2x - y = 5$` with a row stating x + y = 5. Reproduced on the server. *High.*
7. [NET-01](#net-01) — Memory recall loads every fact with two embedding copies (~6 MB) and ranks them in pure Python on the event loop: 62 ms of CPU per memory turn, measured. *High.*
8. [CLAR-01](#clar-01) — User content (to-do titles and text, reminder subjects, SQL parameters) reaches logs and Sentry. *High.*
9. [SCALE-04](#scale-04) — The model-health circuit breaker never records a failing primary model, counts mid-stream failures as successes, mistakes long replies for slowness, and never half-opens. *High.*
10. [NET-09](#net-09) — The phone's connectivity probe polls every 1.5 s, with no backoff or jitter, whenever the API looks unhealthy. Every foreground phone hammers `/health` (and Google) in lockstep during an incident. *High.*

Next in line: [SCALE-05](#scale-05) (documents read whole and at once: out-of-memory risk), [NET-02](#net-02) (round-trip tax), [TEST-01](#test-01) (tests can reach real services and a developer's `.env`), [LEAK-03](#leak-03) (push tokens survive sign-out).

## 3. Scorecard

Scores run from 1 (far below the bar) to 5 (at a large-company production bar).

| Dim | Area | Score | Why |
|---|---|---|---|
| A | Architecture and boundaries | **4** | Modular-monolith migration is essentially done, and CI enforces boundaries, cycles and retired paths. Gaps: code outside `modules/` and the whole phone have no boundary check; routing inverts layering (billing → chat/maths/physics); transaction ownership is broken in one live-talk path. |
| B | Duplication | **3** | Textual duplication is tiny (0.40%), but concepts are still written several times: three fence grammars, nine number-word tables, eleven glyph tables. Two duplicated rules already produce wrong STEM output, and the shared presentation fixture misses the cases where both twins are wrong. |
| C | Resource leaks and lifecycle | **3** | Task, socket, lock, job and SymPy lifecycles are excellent, and phone effects all clean up. But connections are held through streams and slow I/O, timed-out threads keep running, and push tokens and voice recordings outlive sign-out. |
| D | Network and I/O efficiency | **3** | No ORM N+1s, turn loads run in parallel, and every outbound call has a timeout. But each DB session pays about 5 extra round trips; memory recall moves ~6 MB and runs ~62 ms on the loop; a turn makes ~40 Redis commands. The phone polls and refetches widely: a 1.5 s probe, `/home` on every focus, no conditional requests. |
| E | Bloat and dead code | **4** | Very little dead code: 0 of 112 vulture candidates confirmed, and #1914 just cleaned up. Remaining: 13 routes no client calls, about 700 lines reachable only under non-production flags, and 6.1 MB of vendor JS in the JS bundle. |
| F | Scalability and reliability | **2** | Two Critical failures at scale (a loop stall from one message; delete timeouts) plus several silent-loss paths (compression, stream trim, 6 s retries). No saturation metrics, a broken circuit breaker, and unbounded document memory per turn. Strong foundations (Redis locks, leases, dedupe, spend caps, SCALING.md) keep this from a 1. |
| G | Clarity and consistency | **3** | The code is consistent, ruff- and mypy-clean, and well commented. But user content goes to logs and Sentry, 91 swallowed errors are invisible, strict typing covers about 5% of the API, 32 functions grade radon F, config disagrees across three files, and about 47 untranslated strings ship per locale. |
| H | Tests as an asset | **4** | A large, fast suite (25.6k API tests in about 8 minutes serial; 7k phone tests in 105 s) at 91.9% coverage, with behaviour and STEM corpora. But isolation is opt-in (`.env`, real Redis, DuckDuckGo before mocks), `--assert=plain` hides failing values, three tests are vacuous, and fakes have drifted. |

## 4. Metrics

**Size** (production code, counted with `scripts/check_file_sizes.py` rules)

| Tree | Files | Lines | Files > 300 | Files > 500 | Tests |
|---|---|---|---|---|---|
| `apps/api/app` | 955 | 183,369 | 200 | 39 | 596 files / 143,644 lines |
| `apps/mobile` (app, components, contexts, features, hooks, lib, ui) | 795 | 104,479 | 84 | 16 | 501 files / 67,456 lines; vendor 63 files |

CLAUDE.md's "~168k" for the API is now about 9% low. Every file over 500 lines has a recorded reason in `scripts/file_size_baseline.json` (the check passes). Three files are already smaller than their recorded ceiling.

**Largest production files**

- API: `modules/physics/catalog/optics.py` 862 (data), `modules/chemistry/formula_laws.py` 754 (data), `modules/chemistry/formula_bindings.py` 699, `modules/physics/catalog/thermal.py` 670, `modules/chat/prompt_constants/routing.py` 662, `modules/math/solve/key_steps.py` 661, `modules/math/solve/work_slips.py` 660, `modules/math/tool.py` 650, `modules/math/fence.py` 642, `modules/math/match/graph.py` 636.
- Phone: `features/chat/components/MathDraftPreview.tsx` 677, `lib/physics/optics.ts` 649, `features/chat/hooks/useChat.ts` 581, `features/chat/screens/ChatScreen.tsx` 571, `components/MathEquationScanner.tsx` 564, `lib/math/draftSlots.ts` 559, `features/chat/components/ChatComposer.tsx` 556.
- Full top-30 lists: `raw/line-counts.txt`.

**Largest functions** (`raw/api-function-lengths.txt`, `raw/mobile-function-lengths.txt`)

- API: 6,004 functions; 378 are over 50 lines and 61 over 100 (the standards audit counted 87). The longest:
  - `calculus_direct_request` 218 (`modules/math/tools/direct_calculus.py:113`)
  - `_extract_circuit_intent` 216
  - `_extract_torque_intent` 194
  - `_extract_trig_intent` 184
  - `_iter_export_json` 181
  - `_extract_pass` 177
  - On the chat path: `_stream_tokens_sse` 159 (`modules/chat/stream_api.py:80`), `_stream_chat_once` 147 (`gateways/litellm_gateway.py:286`), `stream_over_ws` 146 (`modules/chat/ws_turn.py:57`).
- Phone: 3,427 functions; 330 are over 50 lines and 104 over 100. The longest:
  - `useChat` 550
  - `ChatScreen` 514
  - `useChatRouteLoader` 473
  - `useLiveTalk` 436
  - `MathEquationScanner` 425
  - `useChatSend` 417
  - `useChatIncomingEvents` 395
  - `ConversationList` 373

**Complexity hotspots** (radon, production code)

- Cyclomatic grades: C 616, D 124, E 42, F 32.
- Worst by complexity:
  - `calculus_direct_request` CC 95
  - `_extract_torque_intent` 75
  - `can_direct_verified_math_reply` 71
  - `_extract_circuit_intent` 67
  - `_extract_trig_intent` 64
  - `_extract_friction_intent` 61
  - `SimulationBlockSpec.coherent_scene` 59
- Maintainability index grade C: `modules/chat/calculation_layout.py` (MI 0.00), `modules/math/solve/traces.py`, `modules/math/match/calculus.py`, `modules/math/match/discrete.py`. All four are in the size baseline.
- Four of the five worst functions sit in files under 500 lines, so the size ratchet cannot see them ([CLAR-03](#clar-03)).

**Duplication**

- jscpd (min 10 lines): 78 clone groups, 1,274 duplicated lines, **0.40%**. By language: Python 0.29%, TS 0.13%, TSX 0.74%.
  - The "javascript 1.82%" line is TSX tokenized a second time.
  - Only 20 groups are real logic; the rest are data tables, look-alike UI, signatures and facades.
- pylint duplicate-code: 7 groups, 5 of them real.
- Conceptual duplicates found by reading: 14 families ([§5.B](#b-duplication)).

**Dead-code candidates**

- vulture: 112 candidates, 0 confirmed.
- knip: 7 unused files, 4 unused dependencies and 38 unused exports, all false positives or export noise.
- depcheck: 0 of 7 confirmed.
- deptry production run: 0 of 5 DEP002 confirmed (`defusedxml` is used by openpyxl, `cryptography` by PyJWT ES256). 85 DEP003 imports of transitive packages (`pydantic` ×67, `starlette` ×14, `botocore` ×3, `mpmath` ×1).
- Confirmed dead or vestigial code: 11 findings ([§5.E](#e-bloat-and-dead-code)).

**Dependencies**

- API: 29 direct and 8 dev dependencies; about 375 locked packages.
- Phone: 67 dependencies and 16 dev dependencies; about 1,228 resolved packages.

**Baseline gates at `d2ec42b0`**

| Gate | Result |
|---|---|
| ruff check / ruff format | clean (1,551 files) |
| mypy | no issues in 1,551 files (non-strict for about 95% of lines, see [CLAR-06](#clar-06)) |
| `pnpm typecheck` | clean |
| `pnpm lint` | 0 errors, 126 warnings |
| `check_file_sizes.py` | pass |

**Tests**

| Suite | Tests | Result | Time |
|---|---|---|---|
| API, one area at a time | 25,598 | all pass (18 deselected: `core/test_sympy_executor.py`) | 497 s summed |
| API, single full coverage run | 25,598 | **91.9%** of 77,438 statements | 651 s |
| Phone (jest) | 7,036 + 7 skipped | all pass | 105 s (308 s summed across workers) |

- Coverage of critical areas (full run):
  - quota 98.7%
  - auth (`modules/account`) 92.2%
  - token check, deps and user cache 98.6%
  - memory 91.9%
  - billing 92.9%
  - chat 94.1%
  - tool loop 93.0%
  - `core/jobs` 91.0%
- Lowest-covered files with 40 or more statements:
  - `repositories/message_chunks.py` 49%
  - `services/scan_text.py` 46%
  - `modules/attachments/chunks_repository.py` 63%
  - `gateways/revenuecat_gateway.py` 64%
  - `core/sympy_executor.py` 32% (its tests were deselected per the brief)
- Slowest API tests:
  - `test_stem_coverage_holds_its_floor[physics]` 18.9 s
  - `[math]` 16.8 s
  - `test_the_corpus_covers_the_school_extension_suites` 9.8 s
  - only 10 tests take 2 s or more (`raw/pytest-slowest.txt`)
- Slowest phone suites: `StreamingChatMessageRow` 14.6 s, `markdownRenderRules` 13.6 s, `markdownPreprocess` 12.5 s (`raw/jest-slowest.txt`).
- The 7 phone skips are the documented graph-parity gaps (`lib/__tests__/graphExpr.test.ts`).
- The behaviour battery, sweep and STEM corpora have 0 open `gap` entries.

**One chat turn, measured on the real app** (fake Redis, mock model; `raw/io-counts.json`, `raw/sql-text.json`, `raw/wire-roundtrips.json`)

| Request | SQL statements | DB round trips | Redis commands |
|---|---|---|---|
| Plain turn (warm) | 7–10 | 27 for 7 statements (4 checkouts × [ping + BEGIN + ROLLBACK/COMMIT]) | 37–40 |
| Maths turn | 8 | — | 30 |
| Regenerate | 14–15 (`messages` read 4×, plus `count(*)` and a by-id read) | — | 28 |
| `GET /models` | 0 | — | 10 (6 `ZRANGE` model-health reads) |
| Any authenticated REST GET | — | — | at least 4 (rate-limit pipeline + 3 revocation GETs) |

## 5. Findings

Each finding has:

- **ID:** one prefix per dimension. ARCH (A), DUP (B), LEAK (C), NET (D), DEAD (E), SCALE (F), CLAR (G), TEST (H).
- **Severity:**
  - Critical: data loss, an outage, a security hole, or certain failure at scale.
  - High: a likely production problem or a major maintenance cost.
  - Medium: real but contained.
  - Low: polish.
- **Confidence:** High, Medium or Low.
- **Effort:** S is up to half a day, M up to three days, L more.

In the Evidence field, **"Lead check"** is what the lead verified personally at the cited lines: a reading, a measurement, or a reproduction against the real code. **Source** points to the investigator report that holds the full evidence, the history, and any locations beyond the twelve listed here.

Findings are ordered by dimension. Within each dimension, the most severe come first.

### A. Architecture and boundaries

<a id="arch-01"></a>

#### ARCH-01 — Code outside `modules/` is not held to the public-surface rule (26 imports reach 22 internal module files)
- **Severity:** Medium · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/services/routing.py:219`, `:220`, `:450`, `:510`, `apps/api/app/services/subject_solving.py:53`, `:93`, `:338`, `apps/api/app/services/solving.py:27`, `apps/api/app/background/push_scheduler.py:17`, `apps/api/app/background/email_reminder_scheduler.py:17`, `apps/api/app/tests/architecture/test_product_module_boundaries.py:349-363`, `apps/api/app/modules/chat/__init__.py:19-44`, and 15 more (see raw/agent-arch.md ARCH-01)
- **Evidence:** Of 127 import bindings from outside `modules/` into `app.modules.*`, 51 bypass the public surface: 25 in sanctioned composition roots, 26 elsewhere (`routing.py` 13, `subject_solving.py` 9, `solving.py` 2 type-only, the two schedulers 2). The rule only walks `modules_root.rglob("*.py")`, and chat's `__init__.py` exports none of the six routing cues these imports reach. Lead check: Static scan by investigator; routing's imports are function-local, so the cycle test misses them.
  ```
  services/subject_solving.py:93   from app.modules.chemistry.species import parse_reaction
  services/subject_solving.py:338  from app.modules.chemistry.block import VerifiedChemistry
  services/routing.py:450          from app.modules.math.match.scan import prepare
  services/routing.py:220          from app.modules.chat.prompt_constants.routing import (...)
  ```
- **Impact:** ENGINEERING_STANDARDS' "one subject imports another only through its public files" is enforced inside `modules/` but not for the dispatcher and router that sit between the subjects on every turn; a rename inside `chemistry/species.py` or `math/match/scan.py` breaks a function-local import that only a test of that branch catches.
- **Fix:** Run `_foreign_module_import_violations` over production files outside `modules/` with the five composition roots allowlisted; subjects export a `SubjectAdapter` from `service.py`/`_EXPORTS` for `subject_solving` to import (or the dispatcher moves into `modules/chat/`, as its docstring claims); chat exports the six routing cues (or routing moves into chat, ARCH-02); the scheduler logic moves to `modules/notifications/scheduler.py`.
- **Verify:** New `test_code_outside_modules_imports_modules_only_through_public_files` (allowlist = 5 roots) passes; `outside_modules.py` reports 0 non-root violations.
- **Source:** raw/agent-arch.md ARCH-01

<a id="arch-02"></a>

#### ARCH-02 — Model routing makes billing depend on chat, maths and physics; picking a model runs the physics solver in-process
- **Severity:** Medium · **Confidence:** High · **Effort:** M
- **Locations:** `apps/api/app/modules/billing/plan.py:10`, `:88-117`, `:154`, `apps/api/app/services/routing.py:217-227`, `:277-327`, `:390-416` (`solve_physics` at `:405`), `:419-439`, `:442-466`, `:505-517`, `apps/api/app/modules/chat/turn_load.py:260`, `apps/api/app/modules/chat/turn_prep/persist.py:72`, `apps/api/app/services/thinking_effort.py:16`, `:59`
- **Evidence:** The load path runs `chat.turn_load → billing.plan → services.routing →` (function-local) `chat.prompt_constants.*`, `chat.json_output`, `chat.continuation_subject`, `math.match.*`, `physics.extract_physics_intent` + `solve_physics`, so the component graph holds `modules.chat → modules.billing → services.routing → modules.chat`. Auto is the default (`billing/plan.py:68-71`), so this runs for most users, and `thinking_effort.py` reaches routing again per turn. Lead check: Lead read `services/routing.py:390-410` (`_physics_solves`: `extract_physics_intent` + `solve_physics`, `lru_cache(128)`); this runs on the event loop (see SCALE-01).
  ```python
  # services/routing.py:390
  @lru_cache(maxsize=128)
  def _physics_solves(content: str) -> bool:
      from app.modules.physics import extract_physics_intent, solve_physics
      ...
      solve_physics(intent)
  ```
- **Impact:** Plan policy (CLAUDE.md: decided in one place, `modules/billing/entitlements.py`) sits beside per-message classification, so `billing/plan.py` cannot load or be tested without chat's prompt classifiers and two subject pipelines; a full physics extraction and verified solve runs on the critical path before `turn_prep` does the same question again (the LRU only helps repeat calls inside one turn).
- **Fix:** Billing keeps pool policy (`model_pool`, `allowed_model_ids`, override validation); `route_chat_model`, `resolve_alias_in_pool` and `message_needs_thinking`, with `routing_signals.py` and `rate_problems.py`, move to `modules/chat/model_routing.py`, which composes pool + routing; routing reads the turn's subject verdict (`turn_prep/intents.py` plan / `detect_subject`) instead of running the solver.
- **Verify:** A `sys.modules` test that `import app.modules.billing.plan` loads no `app.modules.chat|math|physics`; the component graph shows no billing → chat path; turn timing shows no physics solve before `turn_prep`.
- **Source:** raw/agent-arch.md ARCH-02

<a id="arch-03"></a>

#### ARCH-03 — `services/` root keeps absorbing code only one module uses
- **Severity:** Low · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/services/reply_labels.py`, `apps/api/app/services/working_check.py`, `apps/api/app/services/recurring_pay.py`, `apps/api/app/services/context_window.py`, `apps/api/app/services/mermaid_sanitize.py`, `apps/api/app/services/prompt_inject.py`, `apps/api/app/services/topic.py:7-8`, `apps/api/app/services/routing_signals.py`, `apps/api/app/services/rate_problems.py`, `apps/api/app/services/calendar_facts.py`, `apps/api/app/modules/chat/finalize_passes.py:65`, `apps/api/app/background/handlers.py:40`, and 14 more (see raw/agent-arch.md ARCH-03)
- **Evidence:** Ten root files (1,682 lines) have exactly one consumer, seven of them chat-only, and five arrived since 2026-10-01 despite CLAUDE.md's rule that the `services/` root is for genuinely cross-cutting code (`reply_labels.py`, a finalize pass, in the audited head). Lead check: cited code read at the listed lines.
- **Impact:** This code sits outside every module boundary test (ARCH-01) and sends readers looking for a broken chat feature to the wrong folder.
- **Fix:** Move the seven chat-only files into `modules/chat/`, `routing_signals`/`rate_problems` with routing (ARCH-02) and `calendar_facts` beside `time_context`, and add a CI check that a root `services/` file has at least two owners or a recorded reason.
- **Verify:** `services_consumers.py` shows no single-consumer row outside a reasoned allowlist and the moved paths are in `RETIRED_LEGACY_MODULES`.
- **Source:** raw/agent-arch.md ARCH-03

<a id="arch-04"></a>

#### ARCH-04 — Infrastructure reaches product modules through the `models.schemas`/`models.orm` barrels; `structured_completion` holds memory's rules
- **Severity:** Medium · **Confidence:** High · **Effort:** M
- **Locations:** `apps/api/app/models/schemas/__init__.py:44-68`, `apps/api/app/gateways/structured_completion.py:21-27`, `:127-131`, `:184-192`, `:197-230`, `apps/api/app/gateways/mock_llm.py:96`, `:116`, `:165`, `apps/api/app/repositories/users.py:9-19`, `:128-137`, `apps/api/app/tests/architecture/test_module_boundaries.py:43-50`
- **Evidence:** The schema barrel re-exports 19 names from attachments, memory and todos schemas; outside those modules only `structured_completion.py:21` and `mock_llm.py:96/116/165` import them. The generic structured-output gateway imports five memory types through it, uses `settings.memory_fallback_model_alias` as every structured call's fallback and runs memory-only partial salvage; `repositories/users.py` imports four modules' ORM classes via `app.models.orm`. The infrastructure test checks only the literal `app.modules` prefix, and `apps/api/app/tests/modules/math/test_math_word_problem.py:486` pins `aliases == ["gpt-6-luna", "fallback-memory-model"]`. Lead check: cited code read at the listed lines.
  ```python
  # gateways/structured_completion.py:184
  except Exception:
      if schema is MemoryFactUpdateResult and isinstance(data, dict):
          fact_partial = _parse_memory_facts_partial(data)
  ```
- **Impact:** "gateways/ must not import modules" holds in text only: a memory schema change can break the gateway every LLM job uses, and every structured job (maths' word-problem translator included) silently falls back to memory's fallback alias. ARCHITECTURE.md says the migration re-exports were deleted; the schema barrel kept three modules' worth.
- **Fix:** Put the salvage behind a schema hook (an optional `salvage_partial(data) -> Self | None` classmethod in `modules/memory/schemas.py`, looked up with `getattr`) or a salvage callable memory passes in; rename the fallback setting neutrally or make it a routing lane; delete the module re-exports from `models/schemas/__init__.py` (10 module files import their own schemas through it); make the infrastructure test resolve barrel imports to the defining module.
- **Verify:** The extended infrastructure test fails on today's tree and passes after; `rg -n "Memory" apps/api/app/gateways/structured_completion.py` is empty.
- **Source:** raw/agent-arch.md ARCH-04

<a id="arch-05"></a>

#### ARCH-05 — "Repositories stay private" is met by forwarding facades and exported repositories
- **Severity:** Low · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/modules/attachments/service.py:1-48`, `apps/api/app/modules/images/generation.py:25`, `:361-411`, `apps/api/app/modules/images/search.py:28`, `apps/api/app/modules/images/turn_references.py:13`, `apps/api/app/modules/images/reply_picture.py:23`, `apps/api/app/modules/todos/__init__.py:12-36`, `apps/api/app/modules/notifications/push.py:33`, `:344-347`, `apps/api/app/modules/home/service.py:21`, `apps/api/app/modules/account/export.py:36`, `apps/api/app/services/model_catalog.py:1-61`, and 5 more (see raw/agent-arch.md ARCH-05)
- **Evidence:** `attachments/service.py` is 13 `_call_through(...)` pass-throughs that images imports as `attachments_repo` and composes into its own transactions, todos exports its `repository` and two repository writers, and the model catalog has two import paths and two documented homes (the facade itself is DEAD-05). Lead check: cited code read at the listed lines.
- **Impact:** The boundary test passes while images writes attachments' rows and notifications writes todos' rows, so attachments and todos cannot change a table or a repository signature without editing three other modules.
- **Fix:** Replace the pass-throughs with intent-level operations the owner keeps (`attachments.service.attach_generated_image(session, …)`, `todos.service.mark_reminder_notified(...)`), reject `repository` names in `_EXPORTS`/`_MODULE_EXPORTS`, and delete `services/model_catalog.py` (moving `is_available`) and list it in `RETIRED_LEGACY_MODULES`.
- **Verify:** A boundary-test assertion over `_EXPORTS`/`_MODULE_EXPORTS`, an empty `rg -n "as attachments_repo" apps/api/app/modules/images`, and `test_retired_module_cannot_be_imported[app.services.model_catalog]`.
- **Source:** raw/agent-arch.md ARCH-05

<a id="arch-06"></a>

#### ARCH-06 — Hard-coded model alias and second model lists bypass the catalog and routing lanes
- **Severity:** Medium · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/modules/math/tools/word_problem.py:30-33`, `apps/api/app/modules/math/tools/llm_extract.py:150`, `apps/api/app/modules/account/settings_intent.py:21-35`, `apps/api/app/modules/account/settings_proposal.py:32-38`, `apps/api/app/modules/speech/service.py:88`, `:123`, `apps/api/app/models/model_catalog.py:141`, `:156`, `:173`, `:189`, `apps/api/app/models/routing_lanes.py:33-40`, `apps/mobile/features/account/screens/ModelsSettingsScreen.tsx:113`, and 3 more (see raw/agent-arch.md ARCH-06)
- **Evidence:** Two maths LLM jobs pin `"gpt-6-luna"`; `settings_intent.py` keeps its own `_MODEL_IDS` (`auto`, `free-chat`, `smart-chat`, `gpt-6-luna`, `qwen-3.7-flash`), `settings_proposal.py` its own labels (`"free-chat": "Flash"`, `"smart-chat": "Pro"`), and `speech/service.py` provider model names (`gpt-4o-mini-tts`, `gpt-4o-mini-transcribe`, `gpt-4o-transcribe`), while ARCHITECTURE.md:47 says "there is no second list". Lead check: Lead grep: `"gpt-6-luna"` hard-coded at `modules/math/tools/llm_extract.py:150` and `modules/math/tools/word_problem.py:33`; it is a catalog alias (`models/model_catalog.py:206`), so not a Golden Rule 2 breach, but it bypasses "route by capability, never by name".
- **Impact:** User-visible: "switch to GLM" finds no model although both GLM entries (`glm-5.3-flash`, `glm-5.2`) are selectable, and a chat settings card says "Default model → Flash" / "Pro" while Settings → Models shows the same models under their catalog display names. The lane capability test does not cover the two maths jobs, and retiring that catalog entry breaks word-problem translation and the LLM maths-intent fallback at runtime.
- **Fix:** Add `math_word_problem` and `math_llm_extract` lanes to `RoutingLanes` (checked for `json_mode`); `settings_intent` derives ids from `model_catalog.selectable_models()` plus a nickname table keyed by tier; `settings_proposal` uses `model_catalog.get(id).label`; the speech provider-name allowlists move to the speech catalog entries or the speech gateway.
- **Verify:** A test that no `model_alias=` string literal remains under `modules/`; a test that `_MODEL_IDS ⊇ {m.id for m in selectable_models()}` and that proposal labels equal catalog labels.
- **Source:** raw/agent-arch.md ARCH-06

<a id="arch-07"></a>

#### ARCH-07 — To-do writes commit and roll back a session they do not own; live talk hands them its unit of work
- **Severity:** Medium · **Confidence:** Medium · **Effort:** S
- **Locations:** `apps/api/app/modules/speech/live_talk.py:333-381` (`:339`, `:348`, `:361`, `:376`, `:378-380`), `apps/api/app/modules/todos/reminder_writes.py:156`, `:163`, `:165`, `:176`, `:186-188`, `apps/api/app/modules/todos/actions.py:322-323`, `apps/api/app/modules/todos/spoken_apply.py:210`, `apps/api/app/modules/chat/finalize_reminders.py:82-83` (the safe caller: its own session)
- **Evidence:** Live talk inserts both message rows with `commit=False` and passes the same session to `materialize_reminder_fences`, whose to-do writes commit by default (`apply_todo_actions` also commits the session it was handed), against CLAUDE.md's rule that whoever passes `commit=False` owns commit and rollback. A spoken reminder that hits `uq_todo_open_content_due` (a duplicate outside the `list_for_user(limit=500)` snapshot, or a concurrent insert) rolls back the whole voice turn; `session.refresh(user_message)` then raises `InvalidRequestError` and `POST /speech/live/persist` fails (path read, not executed). Normally the to-do create commits the voice turn midway. Lead check: Lead read `modules/todos/reminder_writes.py:174-190` (create with default commit; on `IntegrityError` → `state.session.rollback()`) and `modules/speech/live_talk.py:333-381` (message rows `commit=False`, then `materialize_reminder_fences` on the same session).
- **Impact:** Rare loss of a voice turn's transcript for heavy users or concurrent writes; `materialize_reminder_fences(session, …)` is safe only in a throwaway session, which its signature does not say (chat complies, speech does not).
- **Fix:** Pass `commit=False` throughout the to-do write path and never commit or roll back a passed session, with a SAVEPOINT (`async with session.begin_nested():`) around the insert; or run live talk's reminder pass in its own session after committing the messages, as chat does.
- **Verify:** DB test: a live-talk turn whose reminder hits `uq_todo_open_content_due` (duplicate pre-inserted beyond the 500-row snapshot) keeps both messages; a spy-session test shows `materialize_reminder_fences` never calls `commit`/`rollback`.
- **Source:** raw/agent-arch.md ARCH-07

<a id="arch-08"></a>

#### ARCH-08 — Chat message rows have four writers; image and photo turns skip chat's turn invariants
- **Severity:** Medium · **Confidence:** High · **Effort:** M
- **Locations:** `apps/api/app/modules/images/generation.py:389`, `:443`, `apps/api/app/modules/images/search.py:255`, `:272`, `apps/api/app/modules/speech/live_talk.py:339`, `:348`, `apps/api/app/modules/todos/proposals.py:254`, `apps/api/app/modules/chat/turn_settle.py:201`, `apps/api/app/modules/chat/turn_intercepts.py:127`, `:222`, `apps/api/app/modules/chat/stream_entry.py:133-144`, `apps/api/app/repositories/chats.py:88`, and 10 more (see raw/agent-arch.md ARCH-08)
- **Evidence:** `repositories/messages.py` is written by chat, images, speech and todos. `images/generation.py:_persist_turn` (`:361-411`) and `images/search.py` (`:240-296`) never touch `chats.updated_at` (an ORM `onupdate` only, no DB trigger), the intercepts return through `stream_entry.py:133-144` with a refund and no touch or post-turn jobs, and the drawer orders by `updated_at`; an intercept-first chat stays untitled until a later message-page load backfills it (`chat/service.py:221-238`). Live talk hand-rolls the touch (`live_talk.py:375`) and its own job list (`:399-492`), missing `compress`, `lesson_progress` and the `turn.spend_capped` gate. Lead check: Lead grep: `touch_by_id` is called only from `modules/chat/turn_settle.py:201`.
- **Impact:** "Save a chat turn" has three owners: an image or photo turn in an existing chat does not move it up the drawer or into "Today", and every new turn invariant (a post-turn job, a `chats` column, usage) must be added to chat, images and speech separately, contrary to ARCHITECTURE.md ("the payload shape lives in one place").
- **Fix:** Chat owns message writes: a composable `chat.service.record_turn(session, …)` (insert rows, touch, usage) and `post_turn` builders taking a `FinishedTurn` that images, speech and the intercept path call; move `repositories/{chats,messages,message_chunks}.py` into `modules/chat/`.
- **Verify:** A test that an image-intercept turn bumps `chats.updated_at`; a parity test that live talk and a typed turn enqueue the same job set for the same inputs.
- **Source:** raw/agent-arch.md ARCH-08

<a id="arch-09"></a>

#### ARCH-09 — Home's cache invalidation is spread over 19 call sites (one before its commit)
- **Severity:** Low · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/modules/home/service.py:113-119`, `apps/api/app/modules/todos/actions.py:322-323`, `apps/api/app/modules/todos/crud.py:48`, `apps/api/app/modules/todos/sync.py:138`, `apps/api/app/modules/todos/reminder_fences.py:346`, `apps/api/app/modules/todos/proposals.py:300`, `apps/api/app/modules/todos/spoken_apply.py:131`, `apps/api/app/modules/memory/crud.py:20`, `apps/api/app/modules/memory/apply.py:126`, `apps/api/app/modules/account/settings_proposal.py:359`, `apps/api/app/modules/account/lifecycle.py:76`, `apps/api/app/modules/home/service.py:40-83`, and 10 more (see raw/agent-arch.md ARCH-09)
- **Evidence:** Todos, memory and account call `invalidate_home_cache` at 19 sites, `todos/actions.py:322` does so before the commit at `:323`, and home no longer reads memory at all. Lead check: cited code read at the listed lines.
- **Impact:** A `GET /home` between the INCR and the commit re-caches pre-commit rows for `home_cache_ttl` (120 s), todos and home import each other (load-time 2-cycle), and memory pays a Redis INCR per write for nothing.
- **Fix:** Home folds a todos-owned generation (bumped once after commit) and the user row's `updated_at` into its cache key so producers never import home, memory's two calls go, and meanwhile `actions.py:322` moves below `:323`.
- **Verify:** `rg -n "home_service.invalidate_home_cache" apps/api/app/modules | rg -v modules/home` is empty and a parametrized test shows `GET /home` reflecting a to-do change from every write path.
- **Source:** raw/agent-arch.md ARCH-09

<a id="arch-10"></a>

#### ARCH-10 — Mobile features have no public surface and no boundary check
- **Severity:** Medium · **Confidence:** High · **Effort:** M
- **Locations:** `apps/mobile/components/MessageBubble.tsx:5`, `:9`, `:16`, `:24`, `apps/mobile/components/ConversationList.tsx:10`, `apps/mobile/features/chat/model/sendIntercept.ts:3-4`, `apps/mobile/features/images/hooks/useImageGeneration.ts:6`, `apps/mobile/features/chat/components/ChatComposer.tsx:26-27`, `apps/mobile/features/speech/components/LiveTalkButton.tsx:5`, `apps/mobile/features/chat/model/sendLogic.ts:2`, `apps/mobile/features/attachments/hooks/useGalleryLibrary.ts:11`, `apps/mobile/hooks/useSettingsProposal.ts:6-7`, and 8 more (see raw/agent-arch.md ARCH-10)
- **Evidence:** 57 cross-feature value imports, all into internals (model 36, components 12, hooks 6, context 3), and no `features/*/index.ts`; 23 files in top-level `components/`, `hooks/`, `contexts/` and `lib/` import features 44 times; one 16-node component SCC holds 11 of 12 features. Chat-only code such as `MessageBubble` (importing todos, images, drafts and chat internals), `ConversationList` and `components/drawer/*` lives outside the feature. Enforcement: API tests only bar `@/app/` imports (`apps/api/app/tests/architecture/test_module_boundaries.py:88-93`), ESLint restricts only `ui/**` and `lib/{math,physics,chemistry}/**` (`apps/mobile/eslint.config.js:82-128`), and `apps/mobile/lib/__tests__/importCycles.test.ts:94` is file-level. Lead check: cited code read at the listed lines.
- **Impact:** ARCHITECTURE.md's "Chat may orchestrate public feature interfaces; it must not know how another feature stores data" is unenforced on the phone though the API has a CI rule for it, and `test_mobile_chat_has_one_feature_home_and_thin_route` holds only for files named `chat`.
- **Fix:** One public `index.ts` per feature and a jest structural test mirroring `_foreign_module_import_violations` (feature A imports B only via `@/features/B` or its `api.ts`; shared folders import features only at allowlisted composition points), seeded with today's edges as a shrink-only allowlist; move the message row and drawer into `features/chat/` (and update CLAUDE.md's `components/drawer/`); replace cross-feature cache pokes with owner-subscribed events.
- **Verify:** The structural test fails today with 101 edges and passes with an allowlist that only shrinks; `mobile_components.py` shows features as a DAG.
- **Source:** raw/agent-arch.md ARCH-10

<a id="arch-11"></a>

#### ARCH-11 — Nothing checks module-level dependency direction; function-local imports hide cycles
- **Severity:** Low · **Confidence:** High · **Effort:** M
- **Locations:** `apps/api/app/tests/architecture/test_import_cycles.py:32-37`, `apps/api/app/tests/architecture/boundary_support.py:189-192`, `docs/ENGINEERING_STANDARDS_TICKETS.md:1310-1312`, `apps/api/app/core/request_id.py:61`, `apps/api/app/gateways/structured_completion.py:147`, `apps/api/app/gateways/tool_completion.py:96`, `apps/api/app/gateways/vision_completion.py:50`, `apps/api/app/modules/attachments/content.py:222`, `apps/api/app/modules/chemistry/request.py:552`, `apps/api/app/modules/math/tools/block/__init__.py:122`, `apps/api/app/modules/web_search/subject.py:96`, `apps/api/app/services/routing.py:343`, and 15 more (see raw/agent-arch.md ARCH-11)
- **Evidence:** The CI cycle test reads a load-time file graph, so 24 function-local imports close cycles it cannot see (the tickets doc says "about 8"), and with them counted 13 modules and 6 `services/` files form one component SCC. Lead check: cited code read at the listed lines.
- **Impact:** ENGINEERING_STANDARDS rule 6 ("No import cycles") holds only per file and at load time, so module-level inversions grow without a failing test.
- **Fix:** Add a contract test over `_module_imports(load_time=False)` that fixes the allowed direction between modules and `services/`, names chat's cue surface as the one sanctioned back-edge and allowlists today's back-edges shrink-only (import-linter contracts express the same), and correct the count in the tickets doc.
- **Verify:** The contract test runs in API CI and its allowlist shrinks as ARCH-01, ARCH-02 and ARCH-09 land.
- **Source:** raw/agent-arch.md ARCH-11

<a id="arch-12"></a>

#### ARCH-12 — CLAUDE.md's map is wrong in seven places
- **Severity:** Low · **Confidence:** High · **Effort:** S
- **Locations:** `CLAUDE.md:16`, `:17`, `:79-80`, `:130`, `:148`, `:161`, `:189`, `:198`, `apps/api/app/modules/chat/history_rag.py`, `apps/api/app/tests/architecture/test_module_boundaries.py:77`, `apps/api/app/process_bootstrap.py:83-86`, `apps/mobile/features/speech/model/realtimeSdp.ts:1-8`, and 5 more (see raw/agent-arch.md ARCH-12)
- **Evidence:** Path checks on the audited tree's CLAUDE.md find wrong homes for the `services/` packages, the model catalog, `chat_history_rag.py` and `lib/todos/`, a worker list without billing reconcile, and a Golden Rule 1 that omits the `realtimeSdp.ts` OpenAI SDP exception. Lead check: cited code read at the listed lines.
- **Impact:** CLAUDE.md is the map people and agents follow, and its wrong homes are exactly where the ARCH-03 and ARCH-05 drift happened.
- **Fix:** Correct those lines and add a CI check that backticked paths in CLAUDE.md's catalog and seams tables resolve.
- **Verify:** The path check passes.
- **Source:** raw/agent-arch.md ARCH-12

### B. Duplication

<a id="dup-01"></a>

#### DUP-01 — Physics writes "water only" twice; the copies disagree and water + ethanol gets a verified wrong answer
- **Severity:** High · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/modules/physics/bodies.py:136-156,159`, `apps/api/app/modules/physics/binding_values.py:42`, `apps/api/app/modules/physics/catalog/heat.py:157-205` (`excludes` at `:186-201`), `apps/api/app/services/law_binding/fit.py:287`
- **Evidence:** Both lists state the same rule (`bodies.py:136`, `heat.py:157-158`), but only `_NOT_FRESH_WATER` (18 words) has `sea`, `salt`, `mercury`, `alcohol`, `ethanol`, `glycerin`, and only the law's `excludes` (14 words) has `block`, `specific heat`. The law binds on `cues=("water",)` with two masses and two temperatures; no typed mixing extractor exists and chemistry never closes on Q = mcΔT (`apps/api/app/services/subject_solving.py:138-140`). Lead check: reproduced with `extract_physics_intent` + `solve_physics` on "100 g of water at 80 °C is mixed with 50 g of ethanol at 20 °C. What is the final temperature?" → op `water_mixture_temperature`, answer **60 °C**, identical to the water + water control. With ethanol's c ≈ 2.44 J/(g·K) the answer is ≈ 66.5 °C.
- **Impact:** A verified wrong number, the failure ENGINEERING_STANDARDS ranks first; any later water-only law that copies either list inherits the drift.
- **Fix:** One public `NOT_FRESH_WATER` in `physics/bodies.py`, used as `excludes=(*NOT_FRESH_WATER, "block", "specific heat")` in `heat.py`; better, a `WATER_ONLY` id set beside the catalog that `bind_physics_intent` (`apps/api/app/modules/physics/binding.py:63`) drops unless `names_only_water(lower)`, keeping `services/law_binding` subject-neutral.
- **Verify:** STEM look-alikes (water + ethanol, water + alcohol, seawater + water, water + mercury → decline, or the right answer with the second c) beside today's only mixing rows, which are water + water (`apps/api/app/tests/behavior/stem_corpus/physics/investigation.json:114,243`, `apps/api/app/tests/modules/physics/test_physics_thermal_fluids.py:124`), run in the physics STEM sweep; a unit test that every `cues=("water",)` law excludes all of `NOT_FRESH_WATER` or sets the flag.
- **Source:** raw/agent-dup.md DUP-01

<a id="dup-02"></a>

#### DUP-02 — Both calculation-layout twins split a two-equation system into a row that states a false equation
- **Severity:** High · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/modules/chat/calculation_layout.py:123-129` (`_thousands_separator`), `apps/mobile/lib/markdown/calculationLayout.ts:75` (TS twin), `docs/fixtures/presentation_cases.json` (no such row)
- **Evidence:** `_thousands_separator` skips spaces after the comma, so the comma in `10, 2x` counts as a thousands separator and the span is laid out as an equals chain (agent-dup open question 8, static reading). Lead check: reproduced on the server:
  ````text
  layout_calculations("Solve the system $x + y = 10, 2x - y = 5$ for x and y.")
  → 'Solve the system\n$x + y = 10, 2x - y$  \n$x + y = 5$\nfor x and y.'
  ````
  The second row states x + y = 5. The phone twin has the same `_thousands_separator` logic (reading only), and `docs/fixtures/presentation_cases.json` has no such row. The same function also splits the twins on Unicode digits (twin check below).
- **Impact:** A maths reply that writes a system of equations on one line is saved (server) and streamed (phone) with a row asserting an equation the model never wrote. Because the twins agree, the shared corpus cannot flag it until a row pins the right layout.
- **Fix:** In both twins, the separator rule must not join across ", " followed by a new equation. Add fixture rows (system of equations, list of values) to `docs/fixtures/presentation_cases.json`, the corpus both suites load, so one change corrects and pins both twins.
- **Verify:** The new rows pass in `apps/api/app/tests/modules/chat/test_presentation.py:23` and `apps/mobile/lib/__tests__/presentationCorpus.test.ts:16` (exact output and fixed point on both sides).
- **Source:** raw/agent-dup.md open question 8 and "Intentional twins: agreement check"; lead note in final-mapping.md

<a id="dup-03"></a>

#### DUP-03 — Three code-fence grammars plus ~19 ad-hoc readers; the parity-based fence closer appends a stray fence
- **Severity:** Medium · **Confidence:** High · **Effort:** M
- **Locations:** `apps/api/app/services/md_fence_scan.py:8-29,168-183,284-296`, `apps/api/app/modules/chat/finalize_text.py:83-88`, `apps/api/app/modules/chat/finalize_passes.py:162`, `apps/api/app/modules/chat/markdown_regions.py:17-33`, `apps/api/app/services/answer_fence.py:41,80,109-147`, `apps/api/app/services/working_check.py:26`, `apps/api/app/services/answer_check.py:222`, `apps/api/app/modules/math/fence.py:68`, `apps/api/app/modules/todos/proposals.py:34`, `apps/mobile/lib/mdFenceScan.ts:4-25`, `apps/mobile/lib/settingsProposal.ts:20,75-81`, `apps/mobile/features/todos/model/reminderProposal.ts:51-52,103-110`, and 16 more (see raw/agent-dup.md DUP-03)
- **Evidence:** `md_fence_scan` (15 importers) knows backticks only and lets any run of 3+ backticks close any fence; `markdown_regions._fence_marker` and the phone's `readFenceMarker` are CommonMark-like (tildes, at most 3 spaces of indent, closer at least as long as the opener); `answer_fence._scan` is a third, lenient grammar. `working_check._FENCE_BLOCK` equals `answer_check.py:222`, `math/fence.py:68` copies `ANSWER_FENCE_LANGS`, `proposals.py:34` uses a regex although `md_fence_scan.iter_closed_fences(text, lang)` exists, and the phone's protocol-card strippers close on the first ```` ``` ```` anywhere. Lead check: reproduced; this call appends `"\n```\n"`, so an empty code block opens at the end of the saved reply:
  ````python
  close_unclosed_fences("A fence starts with three backticks and a language:\n\n~~~\n```python\n~~~\n\nThen write your code.")
  ````
- **Impact:** `close_unclosed_fences` runs on every saved reply, so a markdown how-to that shows a ```` ``` ```` line inside a `~~~` or four-backtick block gets a stray fence; `strip_gfm_pipe_tables` would strip a pipe table inside `~~~`.
- **Fix:** Move `markdown_regions._fence_marker` (the phone's twin) into `services/md_fence_scan.py` as `read_fence_marker`; rebuild `iter_closed_fences`, `close_unclosed_fences` (real open/close tracking, not parity) and `strip_gfm_pipe_tables` on it, with `answer_fence._scan`'s leniency as a flag; `math/fence.py` imports `ANSWER_FENCE_LANGS`. Phone: the three protocol strippers become `stripClosedLangFence(text, lang)` plus one `stripUnclosedLangTail(text, lang)` in `lib/mdFenceScan.ts`.
- **Verify:** Fence-grammar rows in `docs/fixtures/presentation_cases.json`, which has 1 tilde and 1 four-backtick case today (tilde or four-backtick fence holding ```` ``` ````, a closer shorter than its opener, indented 4+, inside `>`), a `close_unclosed_fences` test over them, and a grep test that fails on a new `startswith("```")` in `apps/api/app` outside the owner.
- **Source:** raw/agent-dup.md DUP-03

<a id="dup-04"></a>

#### DUP-04 — Unwrapping a model's fenced JSON is copied four times; the LaTeX-escape fix reached one copy
- **Severity:** Medium · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/gateways/structured_completion.py:50-80,165-171`, `apps/api/app/modules/math/image_extract.py:27-29,219-226`, `apps/api/app/services/scan_text.py:22-35`, `apps/api/app/modules/attachments/ocr.py:133-148`, `apps/api/app/modules/chat/json_output.py:68-75`
- **Evidence:** `structured_completion.py:166-169` and `image_extract.py:222-225` are identical (`if raw.startswith("```"): raw = raw.split("```")[1]; if raw.startswith("json"): raw = raw[4:]`), but only the first then runs `_escape_latex_in_json` (`280dbedc0`, #1917, 2026-10-20), added because LaTeX in the JSON decoded `\t` as a tab and `\frac` as a form feed, and `\alpha` failed to parse. The image-extract copy (`55c5f198c`, 2026-07-08) never got it, though its prompt asks for an "exact transcription" in `source_text`. `scan_text.reading_from_vision` (physics and chemistry `/scan/read`) and `ocr._page_text_from_response` unwrap without the escape; trailing-comma and curly-quote repair live separately in `repair_json`. Lead check: compared `apps/api/app/gateways/structured_completion.py:165-171` and `apps/api/app/modules/math/image_extract.py:219-226` (byte-identical unwrap; only the first calls `_escape_latex_in_json`) and `apps/api/app/services/scan_text.py:22-35`.
- **Impact:** LaTeX in a vision reading's `source_text` turns `\frac` into a form feed, and `\sqrt` fails the whole extract over to the backup model (frequency unmeasured); every hardening must be copied by hand, and the copies already differ.
- **Fix:** One reader in `gateways/structured_completion.py`, e.g. `parse_model_json(raw) -> object` (unwrap any fence, escape LaTeX, repair trailing commas and curly quotes), called by `image_extract._read_extract`, `scan_text.reading_from_vision` and `ocr._page_text_from_response` (text variant `unwrap_model_fence(raw, tag)`). Better: move the vision extract onto `structured_completion`, which already validates with Pydantic.
- **Verify:** A table test (`{"source_text": "\frac{1}{2}x = 3"}`, ```` ```json ```` wrapped, a trailing comma, curly quotes) through all three entry points expects the same decoded object; grep finds no other `raw.startswith("```")` in `apps/api/app`.
- **Source:** raw/agent-dup.md DUP-04

<a id="dup-05"></a>

#### DUP-05 — Four separate decisions pick a line's subject, with different precedence
- **Severity:** Medium · **Confidence:** High · **Effort:** M
- **Locations:** `apps/api/app/services/subject_solving.py:104-168` (`detect_subject`, solver), `apps/api/app/modules/chat/continuation_subject.py:145-154,199-221` (`classify_presentation_subject`, prompt pack), `apps/api/app/modules/chat/prompt_format.py:255`, `apps/api/app/modules/chat/prompt_subjects.py:37-43`, `apps/api/app/services/routing.py:277-327` (`_route_current_line`, model lane), `apps/api/app/modules/chat/related_questions.py:79-90,93-104` (`subject_for_related`, follow-ups)
- **Evidence:** `detect_subject` overrules `needs_physics` twice: closed chemistry (`:141`) wins "before physics claims its numbers" (`:138-140`), and a physics-cued curve maximum goes to maths (`:144-150`). `classify_presentation_subject` asks physics first (`:211`) and applies neither override; `_route_current_line` tries physics (`:314`) then maths (`:325`) and never chemistry; only `subject_for_related` reuses `detect_subject`. So "a ball's height is h = 20t - 5t^2, find the maximum height", pinned as a maths answer (`apps/api/app/tests/modules/math/test_math_battery_regressions.py:556`), is solved by maths but prompted with physics' reply policy and hints. Biology cues exist twice (8 needing a digit vs 10 that do not; pylint). Lead check: cited code read at the listed lines.
- **Impact:** Each new subject rule (an override, or biology arriving as a module) must be added in four places, and the precedence has already split, so the model gets one subject's layout and policy for another subject's verified block.
- **Fix:** `detect_subject` stays the one owner of "which STEM subject": `classify_presentation_subject` becomes `detect_subject(text)` with statistics/biology cues only when it returns `None`, `_route_current_line` routes on its answer (physics lane, maths lane, chemistry → fast), and one `BIOLOGY_CUES` lives in the presentation module.
- **Verify:** A table test feeds the battery, sweep and STEM corpora through all four and asserts the other three agree with `detect_subject` whenever it returns a subject; the curve-maximum and closed-chemistry-with-masses prompts are named rows.
- **Source:** raw/agent-dup.md DUP-02

<a id="dup-06"></a>

#### DUP-06 — Number words are read by nine private tables and two regexes; the change-from-payment reader stops at six
- **Severity:** Medium · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/modules/math/tools/school/shopping.py:19,27,61`, `apps/api/app/modules/math/tools/school/probability.py:41-44`, `apps/api/app/modules/math/tools/school/bag_draws.py:21-24`, `apps/api/app/modules/math/tools/word_problem.py:135-171`, `apps/api/app/modules/physics/extractors/circuit_patterns.py:118`, `apps/api/app/modules/physics/accounting.py:185`, `apps/api/app/modules/web_search/tool.py:34-45`, `apps/api/app/services/recurring_pay.py:51-65,66-70`, `apps/api/app/services/time_context.py:352-362,367,373`, `apps/api/app/modules/math/match/homework_cues.py:17`, `apps/api/app/modules/chat/prompt_constants/length.py:33,37`
- **Evidence:** The tables stop at different words: `shopping` one–six and ten; `probability` and `bag_draws` (identical) one–twelve; `word_problem` zero–twenty plus tens, hundred, thousand, twice, half; `circuit_patterns` and `accounting` two–six; `web_search/tool` and `time_context` one–ten; `recurring_pay` one–twelve and fourteen. `recurring_pay` and `time_context` re-type their keys in a regex (pylint/jscpd #77 pairs `recurring_pay` with `probability`); `homework_cues` and `length` are bare alternations. `extract_change_intent` returns `None` when an item misses `_COUNT_WORDS` (`shopping.py:27,61`), so "I bought six notebooks at $2 each. I paid with a $20 bill. How much change do I get?" is read and "seven notebooks" is not; no words-to-digits normaliser runs first. Lead check: saw `apps/api/app/modules/math/tools/school/shopping.py:19` (`one`…`six`, `ten`).
- **Impact:** Whether a word problem is verified depends on which reader owns it and how high that copy counts; ES-09 unified digit literals but left this sibling grammar out.
- **Fix:** `services/number_text.py` (ES-09's owner) gains `NUMBER_WORDS` (zero to twenty, tens), `number_word_value(word)` and `COUNT_WORD` (an alternation built from the table); each reader narrows it by a parameter (e.g. counts ≤ 12), not a copy, and `word_problem.py` keeps twice/half on top.
- **Verify:** A parametrized test runs one to twelve through every reader that accepts counts; STEM rows "seven notebooks" and "nine pens" (change from a payment) are answered like "six notebooks".
- **Source:** raw/agent-dup.md DUP-05

<a id="dup-07"></a>

#### DUP-07 — Maths glyph folding (×, ÷, −, ², ₂) lives in eleven private tables and seven one-off chains
- **Severity:** Medium · **Confidence:** High · **Effort:** M
- **Locations:** `apps/api/app/modules/math/solve/unicode_normalize.py:9-22,42-47`, `apps/api/app/modules/math/match/arithmetic.py:48-59`, `apps/api/app/modules/math/match/written.py:31-35`, `apps/api/app/modules/math/tools/work_request.py:92-105`, `apps/api/app/modules/math/tool_check.py:27-40,74-78`, `apps/api/app/services/working_check.py:122-138`, `apps/api/app/services/answer_check.py:52-53,74`, `apps/api/app/services/number_text.py:101-102,106`, `apps/api/app/services/symbolic_text.py:15-17`, `apps/api/app/modules/chemistry/input_text.py:31-32`, `apps/api/app/modules/physics/direct.py:322`, `apps/api/app/modules/math/fence_answer.py:23,105`, and 5 more one-glyph chains (see raw/agent-dup.md DUP-06)
- **Evidence:** The en dash `–` folds to minus in the solver (`unicode_normalize`), arithmetic gate, work request and tool check but not in `working_check` (the check of a reply's own arithmetic) or `written.py`; `⋅` (U+22C5) folds in three tables but not in `tool_check` or `working_check`; `⁻` folds in `answer_check`, `number_text`, chemistry and `physics.direct` but not in `symbolic_text` or `unicode_normalize` (which lean on `fold_scientific` running first). Two pairs are byte-identical (`number_text._SUPERSCRIPTS` = `answer_check.py:52`; `symbolic_text.py:15-17` = `unicode_normalize.py:42-46`), `arithmetic.py` repeats the first 10 of `_UNICODE_OP_SUBS`' 12 pairs (pylint), and no copy imports another. Lead check: cited code read at the listed lines.
- **Impact:** A glyph from a phone keyboard, OCR or a pasted page is read by some subject paths and silently left in others; adding one (e.g. `∗` or `∕`) is an 11-file change that no test checks.
- **Fix:** One subject-neutral `services/glyphs.py` beside `number_text.py` (`OPERATOR_GLYPHS`, `SUPERSCRIPT_DIGITS`, `SUBSCRIPT_DIGITS`, `fold_operator_glyphs(text)`, folding × ⋅ · ∗ to `*`, ÷ ∕ ⁄ to `/`, − – — to `-`); the maths SymPy path adds its own π/∞ and root rewrites on top, and a narrower fold is a parameter, not a copy.
- **Verify:** A property test asserts that every glyph in `OPERATOR_GLYPHS` is folded by the arithmetic gate, `tool_check._normalize`, `working_check._plain` and `unicode_normalize`; add a maths STEM row with an en dash and a `⋅`.
- **Source:** raw/agent-dup.md DUP-06

<a id="dup-08"></a>

#### DUP-08 — Student-claim grammar is still in three places and has drifted; chemistry has none
- **Severity:** Medium · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/modules/physics/claims.py:30-40,41-43,65-71,79-83`, `apps/api/app/modules/math/followup.py:264-275`, `apps/api/app/modules/math/tools/work_request.py:111-117,141-145,148-154`, `docs/ENGINEERING_STANDARDS_TICKETS.md` ("Noticed, not ticketed"); chemistry: none
- **Evidence:** Physics accepts the widest lead-ins ("I got / calculated / … / came up with / think it's", "my result/value/working/calculation/solution is", "my teacher/book says") and the trailing checks "is that ok/okay", "did I get it right", "check it". The maths readers accept "I got / get / found / have" and "my answer is/was", plus "check/verify/mark my answer" and "is it" (`followup`) or "I think it's" (`work_request`), with the tails "is that right / am I right / right / correct". So "I calculated x = 6, is that ok?" is a claim to physics and not to maths, and chemistry checks none ("I got 21.3 g, am I right?"). The ticket note (`8a20f147d`, 2026-10-16) names one line (`work_request.py:113`) where the file already held three claim regexes (`:111`, `:141`, `:148`). Lead check: already listed under "Noticed, not ticketed" in `docs/ENGINEERING_STANDARDS_TICKETS.md`; still unfixed.
- **Impact:** The same student sentence is checked or ignored depending on subject, and every new phrasing is added to one copy.
- **Fix:** As the ticket doc suggests, a subject-neutral `services/student_claim.py` with `CLAIM_LEAD`, `CHECK_TAIL` and `split_claim(text) -> (lead, value_text, tail)`; each subject keeps only its value reader (physics: quantity and unit; maths: `var = value`; chemistry: amount and unit).
- **Verify:** One table of claim phrasings × subjects (physics, maths, chemistry) asserting each is recognised, plus sweep look-alikes ("I got a dog", "my teacher says hi").
- **Source:** raw/agent-dup.md DUP-07

<a id="dup-09"></a>

#### DUP-09 — Three readers of named calendar dates, three month tables
- **Severity:** Medium · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/modules/todos/spoken_when.py:24-41,74-78,115-123`, `apps/api/app/services/recurring_pay.py:82-119`, `apps/api/app/services/calendar_facts.py:21-46`
- **Evidence:** The reminder reader (`spoken_when`) matches `_MONTHS` by three-letter prefix in "Month D" / "D of Month", with no year, ISO or slash dates. Recurring pay knows full and short names plus "sept" and the typo "dcember", ISO `\d{4}-\d{1,2}-\d{1,2}` and slash dates. Calendar facts uses a tuple plus regex, years 19xx/20xx only, ISO `[01]\d-[0-3]\d`. So "2027-1-7" is a date to recurring pay and not to calendar facts, "12/25" is a date only to recurring pay, and "remind me on 2026-12-25" names no day to the reminder reader. Each was written beside its feature (2026-09-26, 10-14, 10-18); ES-12 unified clock and day reading inside `modules/todos` only. Lead check: cited code read at the listed lines.
- **Impact:** The user's date grammar depends on which feature reads the message, and a fix (a typo, a new format) lands in one reader.
- **Fix:** `services/calendar_dates.py` owns `MONTHS`, `MONTH_RE`, `read_named_dates(text) -> list[(month, day, year | None, span)]` and ISO/slash readers with one width rule; the three callers keep their own decisions (which year is meant, whether a past date is allowed).
- **Verify:** One table of date spellings run through all three readers; the behaviour sweep `--area todo` and the time/calendar tests stay green.
- **Source:** raw/agent-dup.md DUP-08

<a id="dup-10"></a>

#### DUP-10 — Domain-error-to-HTTP mapping in four styles; the phone parses error bodies in 4–5 places and localizes by matching the server's exact English sentences
- **Severity:** Medium · **Confidence:** High · **Effort:** M
- **Locations:** `apps/api/app/modules/chat/service.py:38`, `apps/api/app/modules/attachments/workflow.py:39`, `apps/api/app/modules/chat/api.py:30-31`, `apps/api/app/modules/memory/api.py:97,130,166,178,196,216,237`, `apps/api/app/core/unavailable.py:69-70`, `apps/api/app/modules/speech/realtime.py:343-357`, `apps/api/app/services/scan_read.py:32-33,46,61-99`, `apps/mobile/lib/api/client.ts:115,152-160,178,194`, `apps/mobile/features/chat/model/errorMessage.ts:10-33`, `apps/mobile/lib/scanner/scanReadError.ts:10-16,23-35`, `apps/mobile/features/attachments/model/attachmentErrors.ts:41,60-61`, `apps/mobile/lib/quota.ts:18-25`, and 15 more (see raw/agent-dup.md DUP-09, DUP-14 and raw/agent-clar.md CLAR-09)
- **Evidence:** API: eight hand-written error classes carry HTTP fields (five byte-identical; `AttachmentWorkflowError` takes them reversed, `(status_code, detail)`); `speech/realtime.py` (16, bare `404`/`403`/`429`), `speech/gates.py`, `scan_read.py` and `account/consent.py` raise `HTTPException` themselves; routes hold 50 `except` → `HTTPException` blocks (20 copy-only), memory's lock-busy → 409 seven times; `detail` is an English string or `{"code", "message", …}`. Phone: `ApiRequestError` keeps the raw body as `message`, so five modules `JSON.parse` it again; `DETAIL_KEYS` maps the exact English of `scan_read.py:32-33,46` to i18n keys, `attachmentErrors.ts` matches `/content type/i` and `/size/i`, and `quota.ts` falls back to `/free limit|daily limit|today'?s limit/` (documented at `apps/api/app/services/quota/messages.py:62-64`). Lead check: merge of agent-dup DUP-09, DUP-14 and agent-clar CLAR-09 (lead note: "Merge the three.").
- **Impact:** Rewording a server message silently breaks the phone's localisation and error classification, or turns a spend-cap message into an upgrade prompt; HTTP concerns leak into services that the tool loop and WebSocket path also call.
- **Fix:** One base in `app/exceptions.py` (agent-clar: `DomainError(code: str, message: str)`; agent-dup: `DomainHTTPError(detail, *, status_code)`), subclassed per module, with one app-level handler on the `core/unavailable.py` `add_exception_handler` pattern (lock-busy → 409 there); every refusal body becomes `{"detail": {"code", "message"}}`, and the phone's `ApiRequestError` parses once so readers and i18n switch on `code`.
- **Verify:** A dummy-route test per subclass (status and body); an architecture test that only `api.py`, `routers/` and `core/` import `HTTPException`; a contract fixture read by both suites (`docs/fixtures/error_codes.json`, scan-read bodies included; none pins the scan sentences today); `grep -n "JSON.parse(.*message" apps/mobile` returns nothing.
- **Source:** raw/agent-dup.md DUP-09, DUP-14; raw/agent-clar.md CLAR-09

<a id="dup-11"></a>

#### DUP-11 — The "reminders due this minute" query is written twice (push and email)
- **Severity:** Low · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/modules/notifications/push.py:237-258,270-283`, `apps/api/app/modules/notifications/reminder_email.py:43-79`, `apps/api/app/services/reminder_timing.py`
- **Evidence:** Both compute the same lead window and overdue cutoff, run the same `TodoItem`/`User` join and loop the same eligibility checks, with email's recurring-row filter (`a6d0773e2`) the one deliberate difference; both detectors flagged the pair. Lead check: cited code read at the listed lines.
- **Impact:** A change to what "due" means (lead window, overdue cutoff, quiet hours) must be made twice, with the SQL outside the todos repository.
- **Fix:** One `due_reminders(session, now, channel) -> list[(TodoItem, User, title)]` in `modules/todos` (or `notifications`), taking the channel's sent marker and opt-in column as parameters, with `include_recurring=False` for email.
- **Verify:** One parametrized test over both channels (quiet hours, lead, 48 h cutoff, recurring) against the shared function.
- **Source:** raw/agent-dup.md DUP-10

<a id="dup-12"></a>

#### DUP-12 — An inequality's solution set is solved twice (answer card and number line)
- **Severity:** Low · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/modules/math/solve/graph.py:518-552`, `apps/api/app/modules/math/solve/inequalities.py:34-62,134-157`
- **Evidence:** The compound branch is copied line for line (pylint, jscpd #58), while the simple branch already differs (the answer may use `solve_univariate_inequality` on a non-real symbol, the number line always `solveset(..., S.Reals)` on a real one, and only one wraps exceptions). Lead check: cited code read at the listed lines.
- **Impact:** The drawn set and the verified answer can diverge where those two SymPy paths differ, and a fix to one solver does not reach the picture.
- **Fix:** `inequalities.py` exposes `inequality_solution_set(...)` and `compound_solution_set(...)`, and `graph.py` calls them.
- **Verify:** A test asserts, for every inequality in the maths STEM corpus, that the number-line intervals equal the set behind the answer card.
- **Source:** raw/agent-dup.md DUP-11

<a id="dup-13"></a>

#### DUP-13 — Small phone helpers copied (fence-JSON validators, boxesOverlap, prefix/suffix diff, abort check, mapGraphPoint ≡ mapPointW)
- **Severity:** Low · **Confidence:** High · **Effort:** S
- **Locations:** `apps/mobile/lib/math/graphBlock.ts:487-504,518`, `apps/mobile/lib/math/graphWorklets.ts:6-8,100-114`, `apps/mobile/lib/physics/circuit.ts:70-90`, `apps/mobile/lib/physics/optics.ts:72-122,290-297`, `apps/mobile/lib/physics/simulation/parse.ts:56-95`, `apps/mobile/lib/jsonFence.ts`, `apps/mobile/lib/physics/simulation/labelSearch.ts:16-23`, `apps/mobile/lib/math/composerChange.ts:4-18`, `apps/mobile/lib/math/pasteNormalize.ts:232-243`, `apps/mobile/features/search/model/drawerSearchLogic.ts:15-18`, `apps/mobile/features/chat/model/sse.ts:10-12`, `apps/mobile/features/speech/model/pronunciation.ts:329-331`, and 5 more (see raw/agent-dup.md DUP-12, DUP-13)
- **Evidence:** `mapGraphPoint` is `mapPointW` plus a JS default `pad = 28` (an ES-40 straggler, jscpd #5); `circuit.optionalText` = `optics.text` and the two `record`s (#4), `boxesOverlap` (#3) and the prefix/suffix diff (#8) are copies; the abort check sits in three helpers and three inline sites. Lead check: cited code read at the listed lines.
- **Impact:** Small, but the validator kit is the phone's half of the fence wire contract, so a limit rule changed on the server must be found in three parsers.
- **Fix:** `mapGraphPoint` delegates to `mapPointW`; add `lib/fenceValidate.ts`, `lib/geometry/boxes.ts` (`boxesOverlap`) and `lib/api/abort.ts` (`isAbortError`), and make `extractInsertedDelta` return `nativeEditRange(prev, next)?.added`.
- **Verify:** `apps/mobile/lib/__tests__/graphViewport.test.ts`, `graphScale.test.ts` and the parser tests (`optics.test.ts`, `circuit.test.ts`, simulation snapshots) stay green and byte-identical.
- **Source:** raw/agent-dup.md DUP-12, DUP-13

<a id="dup-14"></a>

#### DUP-14 — The retry policy "3 tries, 2 s × n" exists in three places, kept in step by a comment
- **Severity:** Low · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/core/jobs/worker.py:43-44`, `apps/api/app/background/handlers.py:48-51`, `apps/api/app/modules/memory/history_scan.py:41-42,101-105`
- **Evidence:** A "Match core.jobs.worker._RETRY_BACKOFF_S" comment is the only link between the first two, and `history_scan.py` repeats 3 tries and 2.0 s with no link. Lead check: cited code read at the listed lines.
- **Impact:** A change to the job retry policy reaches the memory-lock retries only if someone finds the comment and the unlinked third copy.
- **Fix:** `core/jobs` exports the retry constants (or a `RetryPolicy(attempts, backoff_s)`), and both memory paths import them.
- **Verify:** A grep test fails on a new numeric `*_BACKOFF*` constant outside `core/jobs`.
- **Source:** raw/agent-dup.md DUP-15

#### Intentional twins: agreement check
- **Calculation layout pair** (`apps/api/app/modules/chat/calculation_layout.py` + `calculation_layout_tail.py` ↔ `apps/mobile/lib/markdown/calculationLayout.ts` + `calculationLayoutTail.ts`): a function-for-function mirror (28 Python functions, 29 TS; the extra TS `withIndent` is the Python's inline indent branches at `calculation_layout.py:380-391`) with identical constant sets and line-for-line control flow. They agree on ASCII input and both carry the DUP-02 bug.
- **Where the pair differs** (Unicode classification only; no corpus row exercises it): Python `str.isdigit()` accepts `²`, `³`, Arabic-Indic and Ethiopic digits where TS `/\d/` is ASCII-only (`_thousands_separator` `calculation_layout.py:129` vs `calculationLayout.ts:75`, plus `_list_prefix`, `_interior_line_blocks_fold`, the bare-number test and `converts_units`), so `y = 3², 4x = 8` is saved as `$y = 3², 4x$` / `$y = 8$` (a row stating y = 8) but streamed as `$y = 3²$` / `$4x = 8$`. Command names use `isalpha()` vs `/[A-Za-z]/`, indents `lstrip(" ")` vs `trimStart()` (NBSP included); `apps/mobile/lib/markdown/unicodeChars.ts:1-8` aligned letters but not digits. Fix: corpus rows first, then TS `\p{Nd}`-equivalents or Python `ch in "0123456789"`, whichever the corpus decides.
- **`docs/fixtures/presentation_cases.json`**: 166 cases (50 in `calculation`; ES-06 said 153), loaded by `apps/api/app/tests/modules/chat/test_presentation.py:23` and `apps/mobile/lib/__tests__/presentationCorpus.test.ts:16`, which both assert exact output and a fixed point (the phone also checks streaming against settled for five cases). A static trigger scan finds 35 of 37 branch triggers in the inputs (not triggered: a tab-indented line, a non-ASCII letter after a backslash). Gaps: the Unicode rows, DUP-02's system-of-equations row, and DUP-03's fence-grammar rows (a tilde fence holding ```` ``` ````, a closer shorter than its opener, a fence inside `>`).
- **`docs/fixtures/physics_replies.json`** is a producer/consumer contract, not a twin: `apps/api/app/tests/modules/physics/test_physics_reply_contract.py` regenerates 8 direct replies byte for byte (`UPDATE_PHYSICS_FIXTURE=1` rewrites the file) and `apps/mobile/lib/__tests__/physicsReplyContract.test.ts` reads them through `splitAnswerNotation`, `readableLatexFallback`, `markdownToCopyText` and `markdownToSpeechText`. Gap: the phone never parses the `parallel_resistance` reply's `simulation` circuit fence, and no test feeds server-written `simulation`/`circuit`/`rays`/`wave` fences to the phone parsers (`apps/mobile/lib/__tests__/fixtures/simulationScenes.ts` is hand-written). `docs/fixtures/chemistry_replies.json` follows the same pattern.
- **Simulation limits, copied by hand:** `apps/mobile/lib/physics/simulation/parse.ts:22-48` re-declares `apps/api/app/modules/physics/schemas/simulation.py:30-499`. Enums agree (`TitleKey` 22/22, `ArrowKind` 5/5; the phone's `SCENE_KINDS` lacks circuit/rays/wave by design) and so do the checked limits (bodies 4, path 500, vectors 6, parts 4, label 24, body label 32 truncated on the phone, alt 300, strobe 2–12). In agreement today, but nothing keeps it so: add the fixture's simulation fence to the phone contract test (`readScene` / `parseCircuitSpec` must accept it).

### C. Resource leaks and lifecycle

<a id="leak-01"></a>

#### LEAK-01 — Pooled Postgres connections stay idle-in-transaction across streams, slow provider calls, R2 I/O and waits
- **Severity:** High · **Confidence:** High · **Effort:** S (auth dependency) + M (other sites)
- **Locations:** `apps/api/app/core/deps.py:37-62`, `apps/api/app/modules/account/consent.py:39-50`, `apps/api/app/modules/chat/stream_api.py:262-326`, `apps/api/app/modules/attachments/workflow.py:295-299`, `:257-272`, `apps/api/app/modules/chat/service.py:216-219`, `:281-285`, `apps/api/app/modules/chat/compaction.py:37-89`, `apps/api/app/modules/images/search.py:246-293`, `apps/api/app/modules/attachments/reuse.py:31-54`, `apps/api/app/modules/billing/subscription.py:143-180`, `apps/api/app/modules/memory/crud.py:105,172`, and 37 more (see raw/agent-leak.md LEAK-01, LEAK-02; raw/agent-rel.md REL-02; raw/agent-scale.md SCALE-03)
- **Evidence:** Besides the auth dependency (below), each explicit site opens a transaction and then awaits R2, a model or embedding call, RevenueCat HTTP or a finalize wait with it open. Lead check: measured with a scratch test on the real app (`world` fixture, real Postgres, mock model): on a user-cache miss, at the first streamed SSE token `pool.checkedout()` = 1 (2 in a repeat) vs 0 warm, and `pg_stat_activity` shows one backend `idle in transaction` whose last query is `SELECT users.id, users.google_sub, …` (raw/pool-during-stream.json, raw/idle-in-transaction.json). Cause: `core/deps.py:41` `session = Depends(get_db)` + `users_repo.get_by_id` autobegin; FastAPI 0.142.2 closes request-scoped yield dependencies after the response is sent. Also read: `modules/attachments/workflow.py:295-299` + `thumbnails.py:103-124` (process-wide `Semaphore(2)`, `core/settings/attachments.py:37`), `modules/chat/service.py:216-219` (≤ 2 × 10 s waits after a SELECT), `modules/chat/compaction.py:37-89` (LLM call inside the session). Pool = 20 + 10 per process (`core/db.py`).
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
- **Impact:** Misses are routine (per-machine cache, 60 s TTL), so an SSE turn (`apps/web`'s only transport, the phone's fallback) can pin a connection for up to 600 s, and 25 cold gallery thumbnails, queued two at a time, hold most of a machine's 30 for ~10 s. Other requests, finalize writes and `/health/ready` included, then fail after the 5 s pool timeout with 503; through Neon's transaction-mode pooler each open transaction also pins a server connection.
- **Fix:** S, every route: in `apps/api/app/core/deps.py`, commit after the miss read (`expire_on_commit=False` keeps the row) or load the user in a short `async with SessionLocal()` and `merge(load=False)` it; same for the consent refresh; streaming routes take `Depends(get_db, scope="function")`. M, the explicit sites: read and commit, do the slow work outside any transaction, then write in a second short session (message-list and feedback waits moved before the first query; compaction with a compare-and-set; photo and reuse rows inserted after the upload or copy; account-delete R2 deletes moved to `storage_sweep`), plus an AST guard against `gateways/` awaits or finalize waits inside a session block.
- **Verify:** A `get_current_user` miss, a parked SSE stream, a blocking storage fake, a pending finalize and a blocking `summarize_conversation` each leave `engine.pool.checkedout()` at 0; in production, watch the `idle in transaction` count and pool checkout p99 per route.
- **Source:** raw/agent-leak.md LEAK-01, LEAK-02; raw/agent-rel.md REL-02; raw/agent-scale.md SCALE-03; raw/agent-net.md §3

<a id="leak-02"></a>

#### LEAK-02 — Timed-out `asyncio.to_thread` work keeps running on one unsized 5-thread default executor
- **Severity:** Medium · **Confidence:** High (mechanism), Medium (frequency) · **Effort:** M
- **Locations:** `apps/api/app/modules/attachments/content.py:205-215`, `apps/api/app/modules/attachments/rag.py:150-178`, `apps/api/app/core/jobs/worker.py:131-173`, `apps/api/app/background/handlers.py:314`, `apps/api/app/modules/attachments/ocr.py:198-206`, `apps/api/app/gateways/web_search_gateway.py:137-150`, `apps/api/app/modules/web_search/search_cache.py:67-100`, `apps/api/app/gateways/storage_gateway.py:196-320`, `apps/api/app/gateways/google_auth.py:102-112`, `apps/api/app/modules/attachments/thumbnails.py:103-119`, `apps/api/app/modules/attachments/vision_input.py:95-105`, `apps/api/app/modules/chat/turn_prep/attachments.py:222`, and 12 more (see raw/agent-leak.md LEAK-03; raw/agent-rel.md REL-03)
- **Evidence:** A timeout around `asyncio.to_thread` ends only the await: the document parse, OCR render, ddgs engine walk (up to three 8 s calls) and boto3 retries (5 s connect + 20 s read × 3) keep their thread, though `apps/api/app/core/sympy_executor.py:8-12` exists because a thread cannot be killed. The default executor (`min(32, cpu_count + 4)` = 5 threads) also serves R2, thumbnails, Google sign-in and DuckDuckGo. Lead check: read `modules/attachments/content.py:205-215`, `modules/attachments/rag.py:150-178` (timeout → `AttachmentIndexError`, retried; `core/jobs/worker.py:43` 3 attempts), `gateways/web_search_gateway.py:137-150`; no `set_default_executor` anywhere; `fly.toml` `cpus = 1`.
- **Impact:** One 10-PDF turn, five slow or hostile PDFs, or two news questions from users past their Tavily cap (3–4 DuckDuckGo threads each, held ~10–60 s) fill the five threads, and DuckDuckGo is the routine path once a Free user has used the day's Tavily searches. Sign-in then waits past its 12 s budget (503), R2 reads and thumbnails queue, and a parse timeout tells the model the PDF is a scan; on the 512 MB worker, retries stack up to 3 parse threads per bad PDF, risking an OOM restart.
- **Fix:** Parse and render in a killable process pool (the `BoundedSympyExecutor` seam) and make extraction timeouts non-retryable (`JobDiscardError`); give R2/boto3, document and image work, and sign-in their own bounded executors with fail-fast admission, and boto3 calls an overall deadline; cap DuckDuckGo per machine and per user; report "could not read in time", not a scan. Seams: `apps/api/app/modules/attachments/content.py`, `apps/api/app/modules/attachments/ocr.py`, `apps/api/app/gateways/storage_gateway.py`, `apps/api/app/gateways/web_search_gateway.py`, `apps/api/app/gateways/google_auth.py`, `apps/api/app/core/sympy_executor.py`.
- **Verify:** An extractor stub that sleeps past the timeout is not retried and its pool child is gone; a saturated document pool does not delay `verify_google_id_token`; production tracks default-executor queue depth and worker RSS.
- **Source:** raw/agent-leak.md LEAK-03; raw/agent-rel.md REL-03

<a id="leak-03"></a>

#### LEAK-03 — Sign-out leaves the device's push token registered; the signed-out account's reminders (to-do text) keep arriving
- **Severity:** Medium · **Confidence:** High · **Effort:** S
- **Locations:** `apps/mobile/contexts/AuthContext.tsx:177-207`, `apps/mobile/lib/signOutCleanup.ts:14-40`, `apps/mobile/lib/pushNotifications.ts:158-171`, `:209-224`, `apps/mobile/features/account/hooks/usePushNotificationToggle.ts:86`, `apps/api/app/modules/account/lifecycle.py:89-104`, `apps/api/app/models/schemas/auth.py:260-261`, `apps/api/app/repositories/push_tokens.py:38-105`, `:66-91`, `apps/api/app/modules/notifications/push.py:299-305`
- **Evidence:** `signOut` clears credentials and local stores (local reminders included), then calls `logoutSession`; `unregisterRemotePushToken` runs only from the push toggle and the foreground sync when push is off; `LogoutRequest` carries no device or push token, and the server row moves only when another account signs in on the same install. Lead check: read `apps/mobile/contexts/AuthContext.tsx:177-207` (no unregister), `apps/api/app/modules/account/lifecycle.py:89-104` (logout revokes tokens only), `apps/api/app/modules/notifications/push.py` ~:246-305 (joins TodoItem/User, `body=todo.content`, no session check). Privacy-adjacent.
  ```ts
  // contexts/AuthContext.tsx:204-206
  if (accessToken) {
    void refreshToken.then((refresh) => logoutSession(accessToken, refresh)).catch(() => {});
  }
  ```
- **Impact:** After a sign-out (a shared tablet, a phone handed on, or "sign out of all devices", since `purge_user_sessions` also leaves every device's row), the scheduler keeps putting that account's reminder text on the lock screen until another account signs in on that install or Expo invalidates the token. That breaks the sign-out contract in `apps/mobile/lib/signOutCleanup.ts:10-13` and spends Expo sends on users with no live session.
- **Fix:** Phone: call `DELETE /users/push-token` (best-effort, with the still-valid access token) before `logoutSession`. Server, so it does not depend on the phone: accept the push token (or device id) on `/auth/logout` and delete that row; on `purge_user_sessions`, logout-all or refresh-family revoke, delete the user's push rows (or store the refresh `session_id` on the row and delete rows whose session is revoked). Seams: `apps/api/app/modules/account/lifecycle.py`, `apps/api/app/repositories/push_tokens.py`, `apps/mobile/contexts/AuthContext.tsx`.
- **Verify:** API test: register a token, log out, assert the row is gone and `collect_push_outbound` sends nothing for that user. Phone test: `signOut` calls `unregisterPushToken` before `logoutSession`.
- **Source:** raw/agent-leak.md LEAK-07

<a id="leak-04"></a>

#### LEAK-04 — Phone voice recordings are never deleted, the recorder is never released, and sign-out does not remove them
- **Severity:** Medium · **Confidence:** High · **Effort:** S
- **Locations:** `apps/mobile/lib/speech/voiceAudio.ts:162-226`, `apps/mobile/features/speech/hooks/useVoiceInput.ts:136-176`, `:105-107`, `:143-146`, `:180-186`, `:208-225`, `apps/mobile/features/speech/api.ts:68-101`, `apps/mobile/lib/accountFiles.ts:8-38`, `apps/mobile/lib/signOutCleanup.ts:14-40`, `node_modules/expo-audio/ios/AudioUtils.swift:166-170`, `node_modules/expo-audio/android/.../AudioRecorder.kt:240-252`
- **Evidence:** `startVoiceRecording` creates `new AudioModule.AudioRecorder({})` and `stop()` returns `recorder.uri`; `finishRecording` uploads the file and drops the URI, and the empty-recording, cancel, unmount and error paths leave it too. expo-audio writes `recording-<uuid>.m4a` under `Caches/ExpoAudio/` (iOS) or `cache/Audio/` (Android) and never deletes it, and `grep -rn "deleteAsync"` finds deletes for TTS clips, scans, attachments, exports and the chat cache, none for recordings. Lead check: read `apps/mobile/lib/speech/voiceAudio.ts:162-226` and `apps/mobile/lib/accountFiles.ts:8-38` (sweep knows only `recall-export-`, `recall-preview-`, `recall-tts-`).
  ```ts
  // lib/speech/voiceAudio.ts:211-215
  const rawUri = recorder.uri;
  if (!rawUri) return null;
  const uri = normalizeRecordingUri(rawUri);
  const size = await waitForRecordingFile(uri);
  ```
- **Impact:** Every mic tap, cancelled ones included, leaves up to 45 s of HIGH_QUALITY audio (a few hundred KB) until the OS purges caches. Worse, `clearSignedOutAccount` promises "it starts with nothing of this one" and `apps/mobile/lib/__tests__/accountState.test.ts` guards only JS stores, so raw recordings of the user's voice outlive sign-out and account deletion on the device.
- **Fix:** In `useVoiceInput`, delete the recording once transcription settles and on every discard path (`deleteAsync(uri, { idempotent: true })`); call `recorder.release()` after `stop()`; add the recordings directories (`${cacheDirectory}ExpoAudio/` and `Audio/`) to `deleteAccountFiles`, or record under a known prefix listed in `ACCOUNT_FILE_PREFIX`. Seam: `apps/mobile/lib/speech/voiceAudio.ts`.
- **Verify:** Unit tests that `finishRecording` and `cancelVoiceInput` delete the URI (mock `expo-file-system/legacy`), and that `deleteAccountFiles` removes a `recording-*.m4a` from the recordings directory.
- **Source:** raw/agent-leak.md LEAK-04

<a id="leak-05"></a>

#### LEAK-05 — Plain `asyncio.gather` on ~14 chat-path sites leaves siblings (paid calls) running after one branch fails
- **Severity:** Low · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/modules/chat/turn_prep/augment.py:265-275` (the house fix), `apps/api/app/modules/chat/prompt_builder.py:144-156`, `apps/api/app/modules/chat/tool_loop/forced_search.py:105-115`, `:131-138`, `apps/api/app/modules/chat/tool_loop/parts.py:73`, `apps/api/app/modules/chat/prompt_context.py:189`, `:208`, `:233`, `apps/api/app/modules/chat/turn_load.py:162`, `:238`, `:249`, `apps/api/app/modules/chat/turn_prep/context.py:345`, and 2 more (see raw/agent-leak.md LEAK-06)
- **Evidence:** A plain `gather` propagates the first exception and leaves the other children running, which `_gather_or_cancel` already fixes in one place. Lead check: read `modules/chat/turn_prep/augment.py:265-275` (`_gather_or_cancel`, the house fix) and `modules/chat/prompt_builder.py:144-156` (plain gather).
- **Impact:** A failed turn still runs and pays for sibling model calls and Tavily searches, bounded only by provider timeouts.
- **Fix:** Move `_gather_or_cancel` to a shared helper (or use `asyncio.TaskGroup`) and use it at these sites.
- **Verify:** A test where one branch raises while another awaits an event asserts the other is cancelled.
- **Source:** raw/agent-leak.md LEAK-06

<a id="leak-06"></a>

#### LEAK-06 — Live Talk never calls `MediaStream.release()`; native WebRTC objects accumulate per session
- **Severity:** Low · **Confidence:** Medium · **Effort:** S
- **Locations:** `apps/mobile/features/speech/model/realtimePeer.ts:352-363`, `:181`, `apps/mobile/features/speech/model/realtimeVoice.ts:98-164`
- **Evidence:** `close()` runs `track.stop()` and `pc.close()`, but in react-native-webrtc 124.0.8 native objects leave `localStreams`/`localTracks` only through `MediaStream.release()`. Lead check: read `apps/mobile/features/speech/model/realtimePeer.ts:352-363` and RN-WebRTC `MediaStreamTrack.stop()` (flags only).
- **Impact:** Each session and each failed connect leaves a stream, an audio track and its source in WebRTCModule until the app process dies: small, but unbounded per app run.
- **Fix:** Call `localStream.release()` after `pc.close()` in `close()` and in the no-audio-track branch of `openRealtimeMicrophone`.
- **Verify:** A session test with the WebRTC mock asserts `release` is called once on close and on a connect failure.
- **Source:** raw/agent-leak.md LEAK-05

<a id="leak-07"></a>

#### LEAK-07 — Phone caches without a size or age bound (chat pages, link previews, quiz attempts)
- **Severity:** Low · **Confidence:** High · **Effort:** S
- **Locations:** `apps/mobile/features/chat/model/messageCache.ts:19`, `:74-92`, `:112-129`, `apps/mobile/features/chat/model/constants.ts:2`, `apps/mobile/lib/linkPreview.ts:11-33`, `apps/mobile/lib/lesson/quizAttempts.ts:5-14`, `apps/mobile/features/attachments/model/attachmentFileStore.ts:8-11`, `:89-103` (the bounded comparison)
- **Evidence:** `writeCachedChatMessages` writes one `chat-pages/<chatId>.json` per chat ever opened with no eviction, and the link-preview and quiz-attempt Maps have no cap and are cleared only at sign-out. Lead check: read `features/chat/model/messageCache.ts` (no sweep) and `lib/linkPreview.ts:11,31`.
- **Impact:** The chat-page cache grows by tens of KB per chat opened, for years, until the OS purges caches; the two Maps grow with every link and quiz seen in a session.
- **Fix:** Sweep chat pages on start like `attachmentFileStore` (newest N, or 30 days) and give both Maps an LRU cap like `apps/mobile/lib/math/svgMath.ts` (`CACHE_MAX = 200`).
- **Verify:** Unit tests that the sweep keeps the newest N files and that each Map stays at its cap after N+1 inserts.
- **Source:** raw/agent-leak.md LEAK-08

### D. Network and I/O efficiency

#### One chat turn, end to end (measured and traced)

"Trace" is a WebSocket turn: plain question, memory on, no attachments, a chat with ≥ 20 messages, production flags (raw/agent-net.md §1). "Measured" is the lead's runs on the real app: real Postgres, fake Redis, mock model, SSE transport, spend cap off (raw/io-counts.json, raw/sql-text.json, raw/wire-roundtrips.json).

| What | Count per turn | Before the first token? |
|---|---|---|
| DB sessions (pool checkouts) | Measured 4 on a warm plain SSE turn. Trace: 6–8; up to 12 on a personal turn | Trace: 5–7, of which 3–4 run one after another (window → turn mode → attachment probe → gap) |
| SQL statements (app) | Measured 7 on a warm plain SSE turn; 9 on one that also loaded memory and history chunks. Trace: 10–13, incl. two `count(*)` of the same chat and an unused `SELECT usage_daily` (NET-03, NET-07) | Trace: 8–11 |
| DB round trips (incl. pre-ping, `BEGIN`, `ROLLBACK`, `COMMIT`) | **Measured 27 for 7 statements**: 4 pings (`BEGIN` + `;` + `ROLLBACK` each), `BEGIN` 8, `ROLLBACK` 6, `COMMIT` 2 (NET-02). Trace estimate: ≈ 48–54 | Trace: ≈ 39–45; the sequential chain ≈ 21 (≈ 27 with the turn-mode read) ≈ 250–320 ms at 12 ms RTT |
| Redis commands | Measured 37 (warm) and 40 (turn 1). Production adds 2 `GET`s per spend check (6–8 more), ≈ 43 (NET-04) | Trace: ≈ 22 |
| Model calls | 1 reply stream (fallbacks only on failure); 1–2 follow-up-question calls on `memory-model` after `done`; worker: 1 memory extraction. The web-search classifier is off in production | The reply stream only |
| Embedding calls | 0 on a non-personal turn. A personal turn embeds the same query 2× (3× with document chunks, NET-05). Worker `message_index`: two requests (user line, reply) | The query embeddings (0.75 s budget) |
| Redis on the way to the first token | 3 sequential revocation `GET`s, rate-limit `MULTI`, prepare-lock `SET NX`, finalize `EXISTS`, quota `EXISTS`, 6 model-health `ZRANGE`s, quota reserve (4–5 sequential, incl. both spend keys), tool-loop spend `GET` × 2 | Yes |
| SQL on the way to the first token | User row (WebSocket only, uncached); chat (unless created on this machine); window `LIMIT 20` + `count(*)`; turn-mode re-read (three message shapes); attachment-RAG probe (≥ 20 messages); gap `count(*)` + `list_before`. The user-message `INSERT` + `COMMIT` overlaps the prompt build but is awaited before the first token is sent | Yes |
| Between the last token and `done` | Health-sample pipeline (3 commands); finalize-marker `SET`; reply save in one session (`INSERT messages`, `UPDATE chats`, `usage_daily` upsert, unused `SELECT usage_daily`, `COMMIT`); quota + spend settle (2); marker `DEL` | No, but it gates `done` |
| After `done` | Follow-up questions (2 spend `GET`s, 1–2 model calls, 1 `SET`). Post-turn enqueue: 2 spend `GET`s + `XADD`/`XPENDING`/`XTRIM` per job (`memory`, `compress`, `message_index`, + `topic` on turn 1) = 9 (12 on turn 1). The worker then sends ≈ 4–5 Redis commands per job plus its work | No |
| Personal turn (memory loaded) | Adds `GET memgen`/`memquery`/`memembed`, an embedding call and `SET memembed` (34 KB JSON); every active and muted fact with both embedding copies (NET-01); to-do context 1–2 SQL; a history-RAG probe, a second embedding of the same text, and a search returning 6 full chunk rows | Yes |
| Maths turn | Measured 8 SQL incl. `SELECT messages` ×2 (window + `recent_user_contents`), 30 Redis. SymPy pool (CPU). A structured model call only when the regex reader misses (2.5 s, one retry on a second provider); word problems one call (3 s + one retry) | Yes |
| Regenerate | Measured 15 SQL (messages read 4× + `count(*)` + by-id; `SELECT users` even though SSE had the cached user) and 28 Redis. One session of 5–6 sequential statements, then the window and model health are read again because `TurnRequest` carries neither (NET-03) | Yes |
| Message with attachments | Attachment rows read 3×; one session per verified row inside a loop; an R2 copy for a reused Library file inside an open transaction (LEAK-01) | Yes |

#### App start-up and opening a chat (phone)

1. **Cold start** (signed in, stored access token older than its 60-minute lifetime, i.e. most cold starts; about 14–17 requests plus a WebSocket, mostly concurrent): `POST /auth/refresh`, sent when the first authenticated request sees the expired JWT (`apps/mobile/lib/api/client.ts:226-232`, single-flight). Needed.
2. `GET /auth/me` (`apps/mobile/contexts/AuthContext.tsx:120`). Needed: preferences are not cached.
3. `GET /models`, unconditional on mount (`apps/mobile/contexts/ModelsContext.tsx:121-123`). Partly needed: the catalog is cached on disk, live health is not.
4. `GET /todos/page?limit=1000`, every page (`apps/mobile/features/todos/hooks/useTodosList.ts:115`). Open rows are needed; the full completed history is not (NET-16).
5. `GET /home`, forced (`apps/mobile/features/home/context/HomeContext.tsx:93-105`). Not needed: the UI reads only `greeting`, which the phone already computes (NET-10).
6. `GET /health` + Google `generate_204`, sent twice (`apps/mobile/hooks/useNetworkStatus.ts:47-48`), plus iOS NetInfo's own `HEAD generate_204`, then every 60 s. At most one probe is needed (NET-09).
7. `POST /chats` draft 125 ms after mount, then WebSocket `/ws/chats/{draft}` + auth frame (`apps/mobile/features/chat/hooks/useDraftChat.ts:76-84`, `useChatDraftWarmup.ts:17-23`). Speculative (NET-13).
8. `GET /chats/usage/today` at mount, and again when the refresh changes `token` (`apps/mobile/features/chat/hooks/useQuotaNudge.ts:44-60`). Needed for free users only, and the second call not at all (NET-11). Paid users also get it until the server's user arrives, because the cached plan is forced to `"free"`.
9. `GET /chats` as an idle task (`apps/mobile/hooks/useDrawerChatList.ts:120-132`): a reasonable prefetch. Expo push-token service + `POST /users/push-token` (`apps/mobile/hooks/useBootstrapSync.ts:63-91`): not needed on most launches (NET-19).
10. Needed: `PATCH /auth/me {timezone}` (only when the device zone differs), a GPS fix + reverse geocode (defensible once per launch, but it re-runs hourly, NET-11), RevenueCat `configure`, Sentry init.
11. **Opening a chat from the drawer** (from the new-chat screen): `DELETE /chats/{draft}`; a paint from disk; `GET /chats/{id}` only when the drawer list lacks the row; then `GET /chats/{id}/messages?limit=40` always, even if fetched seconds ago (`apps/mobile/features/chat/hooks/useChatRouteLoader.ts:351-353,386-412`; NET-16).
12. The draft socket closes and `/ws/chats/{id}` opens 100 ms later: one handshake per chat view, used or not (NET-13). Switching A → B → A repeats the 40-message page and the handshake every time.
13. Per visible item:
    - `GET /attachments/{id}/url` per file (shared poller with backoff) and resized image thumbnails: both fine.
    - A full PDF download per PDF card (7-day disk cache).
    - `GET /link-preview` per link (success-only cache, NET-19).
    - `GET /chats/{id}` every 2 s, up to 8 times, for an untitled chat (NET-14).
14. **Returning after ≥ 5 min** with a chat open: 6–9 requests plus a handshake, each `AppState` listener with its own staleness rule (none / 20 s / 5 min / 12 h). After > 60 min, the refresh re-runs the token-keyed effects (NET-11) and the reconnecting socket carries the expired token (NET-12).


<a id="net-01"></a>

#### NET-01 — Memory recall loads every fact with both embedding copies and ranks them in pure Python on the event loop; every vector is also stored as 34 KB of JSON
- **Severity:** High · **Confidence:** High · **Effort:** M
- **Locations:** `apps/api/app/modules/memory/repository.py:21-37,97,222,236-248`, `apps/api/app/modules/memory/retrieval.py:55-78,111,318-338,406-416`, `apps/api/app/modules/memory/selection.py:92-109`, `apps/api/app/gateways/embedding_gateway.py:32-40,118-138,141-142`, `apps/api/app/modules/memory/models.py:104-105`, `apps/api/app/repositories/message_chunks.py:58-69,90-94,99-106`, `apps/api/app/modules/attachments/chunks_repository.py:94-105,125-130,135-142`, `apps/api/app/modules/memory/writes_repository.py:83,229-249`, `apps/api/app/modules/memory/apply.py:63-73,93-103`, `apps/api/app/modules/memory/extraction_workflow.py:90`, `apps/api/app/modules/chat/history_rag.py:238-248,250-258`, `apps/api/alembic/versions/0033_pgvector_real.py:48-49`, and 10 more (see raw/agent-net.md NET-01, NET-02; raw/agent-scale.md SCALE-07)
- **Evidence:** `select(Memory)` returns every active and muted fact with both `embedding_json` (Text) and `embedding` (`Vector(1536)`). Selection then runs `json.loads` on each fact's JSON and a pure-Python cosine. No asyncpg vector codec is registered, so pgvector also parses every `vector` value, which selection never reads. A fact row moves ≈ 50 KB (~34 KB JSON + ≈ 15–21 KB vector text). The cap is 150 active facts plus muted ones. The block cache is keyed by the exact question (120 s TTL) and every memory write invalidates it, so each new question misses. Chunk writers store the same JSON beside the vector, and both chunk searches select full rows only to use `text`. Migration 0033 had moved ranking into Postgres; `c788f5d4e` (#640) moved it back in-process on a "≤5 rows" premise that one-fact-per-row memory no longer meets.

  Lead check: benchmark (audit venv, real `parse_embedding` + `cosine_similarity`): 150 facts × 34,056-byte JSON → **61.9 ms CPU on the event loop per memory turn** (best of 5, this container; slower on Fly's shared vCPU). The lead read `apps/api/app/modules/memory/retrieval.py:67` → `selection.py:90-112` and `apps/api/app/gateways/embedding_gateway.py:118-135`. JSON is written at `apps/api/app/repositories/message_chunks.py:67`, `apps/api/app/modules/attachments/chunks_repository.py:101` and `apps/api/app/modules/memory/apply.py:101`. There is no vector query on `memories` (only `message_chunks`/`attachment_chunks` use `cosine_distance`), so `ix_memories_embedding` (HNSW) is unused.
  ```python
  # modules/memory/selection.py:98-106
  for memory in eligible:
      ...
      vec = parse_embedding(getattr(memory, "embedding_json", None))
      ...
      cosine = cosine_similarity(query_embedding, vec)
  ```
- **Impact:**
  - Up to ~7.5 MB per uncached memory turn is detoasted on Neon, sent iad ← us-east-2 and parsed on the single event loop before the first token; a 40-fact user still moves ~2 MB.
  - The worker's `memory` job loads the same rows again after every turn.
  - The JSON is about half of each chunk row: per 1M turns, ~100 GB of it goes through WAL (~45–55 GB stored).
  - Each personal turn's two RAG searches pull ≈ 300 KB each just to read `text`.
  - `ix_memories_embedding` is maintained on every fact write and never read.
- **Fix:**
  1. Rank in SQL with narrow rows (`apps/api/app/modules/memory/repository.py` + `selection.py`). Select the scalar columns plus `(1 - Memory.embedding.cosine_distance(q)).label("similarity")` over the user's active facts; Postgres computes 150 distances in C without an index. Pass that similarity to `select_memories_semantic`, keeping the same scores and rules.
  2. Make every other reader select named columns: `load_only(...)` + `raiseload("*")`, not `defer`, which raises `MissingGreenlet` under async.
  3. Stop writing `embedding_json`, and select named columns in both chunk `search_semantic`s.
  4. Later, drop the three JSON columns and `ix_memories_embedding` (expand/contract), with tests moved to padded 1536-dim fakes.
- **Verify:**
  - `world` scratch test with 150 seeded 1536-dim facts: ≈ 7–8 MB per memory turn before, < 50 KB after.
  - A golden test that `select_memories_semantic` output is unchanged.
  - `replace_chunks` writes `embedding_json IS NULL`.
  - `pg_stat_user_indexes.idx_scan = 0` for `ix_memories_embedding` today.
  - Production: `prompt_ready_ms` p95 on memory turns, and event-loop lag.
- **Source:** raw/agent-net.md NET-01, NET-02; raw/agent-scale.md SCALE-07

<a id="net-02"></a>

#### NET-02 — Each DB session costs about five extra round trips (pre-ping BEGIN/;/ROLLBACK plus BEGIN/ROLLBACK)
- **Severity:** High · **Confidence:** High (count), Medium (ms) · **Effort:** S–M
- **Locations:** `apps/api/app/core/db.py:25-37`, `apps/api/.venv/.../sqlalchemy/dialects/postgresql/asyncpg.py:866-877,883-895,905-912`, `apps/api/.venv/.../sqlalchemy/pool/base.py:1314-1326`, `apps/api/.venv/.../asyncpg/transaction.py:146,206`, `apps/api/app/modules/chat/turn_load.py:87-88,121-122,157-161,189-198,257-258`, `apps/api/app/modules/chat/turn_prep/persist.py:107`, `apps/api/app/modules/chat/prompt_builder.py:229-230,302-306`, `apps/api/app/modules/chat/prompt_context.py:89-96,139,143,155,334`, `apps/api/app/modules/chat/history_rag.py:178,225`, `apps/api/app/modules/attachments/rag.py:293,326`, `apps/api/app/modules/chat/turn_prep/augment.py:261`, `apps/api/app/modules/chat/turn_settle.py:294`
- **Evidence:** With `pool_pre_ping=True`, the installed asyncpg adapter wraps each ping in a transaction. A one-query read session therefore costs ping 3 + `BEGIN` + statement + `ROLLBACK` = 6 round trips, 5 of them overhead. A long chat's plain turn chains three sessions before the first token (window → attachment probe → gap): ≈ 15 overhead round trips, ≈ 180 ms at 12 ms. The reply commit before `done` pays the ping too. Design comments assume sessions are cheap ("Each DB read gets its own AsyncSession"), and `docs/PRODUCTION.md:528` describes pre-ping as one statement.

  Lead check: measured (raw/wire-roundtrips.json). One warm plain SSE turn = 4 pool checkouts, 4 pings (each `BEGIN` + `;` + `ROLLBACK`), `BEGIN` 8, `ROLLBACK` 6, `COMMIT` 2, application SQL 7 → **27 round trips for 7 statements**. The lead read the installed SQLAlchemy 2.1 asyncpg dialect `_async_ping` (explicit transaction "to support pgbouncer transaction mode", #10226). `fly.toml` has `primary_region = "iad"`; Neon is in AWS us-east-2 (≈ 11–13 ms per round trip).
- **Impact:** Ordinary turns in long chats pay roughly 0.2–0.3 s of fixed latency before the first token (estimate). Every REST request that touches the DB pays it again. Each session also sends Neon's compute and pooler 4–5 extra statements, about 3× the app's own.
- **Fix:**
  1. Fewer sessions: fold sequential reads into existing lanes (NET-03 removes 2–3). Effort M.
  2. Set `pool_pre_ping=False` and add `checkin`/`checkout` listeners that ping only connections idle > ~30 s, raising `DisconnectionError` on failure. Effort S.
  3. Add an `isolation_level="AUTOCOMMIT"` read engine for read-only lanes (bare `;` ping, no `BEGIN`/`ROLLBACK`). Only do this if Neon's pooler handles prepared statements outside a transaction (#10226). Effort M.

  Seams: `apps/api/app/core/db.py`, `turn_deps.ChatTurnDeps.session_factory` (add a read factory).
- **Verify:** Extend the `world` scratch test to count pool `checkout` events and asyncpg `BEGIN`/`ROLLBACK`/`COMMIT`/`;` per warm plain turn (today: 27 round trips for 7 statements). In production, compare `pg_stat_statements` calls of `BEGIN`/`ROLLBACK`/`;` with the app's own statements, and watch `first_token_ms` p50/p95.
- **Source:** raw/agent-net.md NET-03

<a id="net-03"></a>

#### NET-03 — A turn re-reads rows and counts it already holds (regenerate reads messages four to six times)
- **Severity:** Medium · **Confidence:** High · **Effort:** M
- **Locations:** `apps/api/app/modules/chat/turn_load.py:64-76,79-93,192-198,246-253,257-258,306-328`, `apps/api/app/modules/chat/turn_prep/mode.py:134-148,155-168,185-188,191-193,199-202`, `apps/api/app/modules/chat/turn_prep/augment.py:180,222,237,260-262`, `apps/api/app/repositories/messages.py:248-260`, `apps/api/app/modules/chat/prompt_context.py:131-140,333-335`, `apps/api/app/modules/chat/ws_api.py:193-208`, `apps/api/app/modules/chat/stream_api.py:289`, `apps/api/app/modules/chat/stream_entry.py:69-72,268-284`, `apps/api/app/modules/chat/turn_prep/attachments.py:27,184,251-254`, `apps/api/app/modules/chat/prompt_builder.py:227-232`, `apps/api/app/modules/chat/history_rag.py:177-183`, `apps/api/app/modules/attachments/rag.py:290-297`, and 7 more (see raw/agent-net.md NET-04)
- **Evidence:**
  - `_classify_turn_mode` re-reads messages right after the 20-row window loads, for "yes"/"ok", "you should know that" and "make it shorter".
  - Augmented turns re-read earlier user lines via `recent_user_contents`, although the same module derives them from the prompt.
  - A full window costs two `count(*)`.
  - The WebSocket turn reads the user row from Postgres every time, while SSE uses `apps/api/app/core/user_cache.py`.
  - Regenerate runs 5–6 sequential statements, then reads the window and model health again because `TurnRequest` carries neither.
  - Attachment rows are read three times, with one session per verified row.
  - Three "has chunks" probes repeat every turn.

  The priors read and the second count race the user-row insert.

  Lead check: measured. Regenerate = 15 SQL statements (messages read 4× + `count(*)` + by-id; raw/sql-text.json); maths turn `SELECT messages` ×2 (raw/io-counts.json).
  ```python
  # modules/chat/turn_load.py:246-258  (recent is in hand; the mode reads messages again)
  (loaded_user, daily_limit, loaded_chat), (recent, prior_count), unhealthy = await asyncio.gather(...)
  async with deps.session_factory() as session:
      turn_mode = await _classify_turn_mode(session, loaded_chat, content)
  ```
- **Impact:** Each re-read is a full session (≈ 6 round trips ≈ 70 ms, NET-02), mostly on the sequential path before the first token. That makes 2–4 avoidable sessions per turn (≈ 10–20 statements with ping/`BEGIN`/`ROLLBACK`) on confirmations, edit follow-ups, maths/search/rich turns and long chats. Because of the races, the subject reader and the gap depend on whether the user's row committed first.
- **Fix:** Read once per turn and pass it down. Seams in `apps/api/app/modules/chat/`: `turn_prep/mode.py`, `turn_prep/request.py` (`TurnRequest`), `turn_load.py`, `ws_api.py`.
  - Derive the mode inputs and priors from the window.
  - Carry `prior_count`, and on regenerate `recent_messages` and `unhealthy_models`, on `TurnRequest`.
  - Pass `user_cache.cached_user(user_id)` from `ws_api`.
  - Read attachment rows once, and mark verified rows with one `UPDATE … WHERE id IN (…)`.
  - Cache the "has chunks" answers (a flag set by the index jobs).
- **Verify:** Extend the `world` scratch test with five turns: "yes" after a question, "make it shorter" after a draft, "solve 2x+5=17" in a 25-message chat, a regenerate, and a warm WS turn. Today they read messages 2, 2, 2 (+ 2 counts) and 6 times, and the WS turn sends `SELECT users` once. After the fix: one window read and ≤ 1 count per turn, and no `SELECT users` on the warm WS turn.
- **Source:** raw/agent-net.md NET-04

<a id="net-04"></a>

#### NET-04 — About 37–43 Redis commands per plain turn; model health (6 ZRANGE) and the spend check (incl. a legacy key nothing writes) are re-read every turn
- **Severity:** Medium · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/modules/chat/turn_load.py:283-287`, `apps/api/app/services/model_health.py:50-53,89-96,99-109`, `apps/api/app/modules/chat/turn_prep/context.py:269-275`, `apps/api/app/routers/models.py:26`, `apps/api/app/core/spend_counter.py:28-30,37-38,63-66`, `apps/api/app/modules/chat/turn_resources.py:299`, `apps/api/app/modules/chat/stream_paths.py:166`, `apps/api/app/modules/chat/post_turn.py:239`, `apps/api/app/modules/chat/related_prompts.py:184`, `apps/api/app/background/handlers.py:101`, `apps/api/app/modules/account/tokens.py:367-369`, `apps/api/app/modules/notifications/push.py:94-96,99-101,115-117`, and 4 more (see raw/agent-net.md NET-05, raw/agent-dead.md DEAD-06)
- **Evidence:** Every turn reads `ZRANGE … 0 -1` (up to 40 members) for each of the 6 selectable models, and regenerate and `GET /models` read them again, all for a best-effort hint. The spend check reads `spend_musd:{day}` and then `spend_mcents:{day}`. `bac689f0e` removed the second key's writer on 2026-10-15, so that `GET` has missed every time since 2026-10-16. Production must set `DAILY_GLOBAL_SPEND_USD > 0`, so it always pays both reads, up to 4× per plain turn and on every model-calling job (15 call sites). `GET /auth/sessions` and push-receipt cleanup send one command per item.

  Lead check: measured (fake Redis, spend cap off). Plain turn 37–40 commands, maths 30, regenerate 28. `GET /models` sends 10 (6 `ZRANGE recall:model_health:*`), and every authenticated REST GET sends ≥ 4 (rate-limit pipeline + 3 revocation GETs). SCALING.md counts REST requests only. Upstash bills per command.
- **Impact:** About 13 of ≈ 43 commands per plain turn are avoidable, ≈ 18 with the two items already in `docs/SCALING.md`, and the worker adds ≈ 15. Per 1M turns that is ≈ 13M avoidable commands (~$26 on pay-as-you-go). The 6-way `gather` can open 6 pooled connections per turn. The latency cost is small.
- **Fix:**
  1. Delete the legacy key read (`apps/api/app/core/spend_counter.py:65-66`).
  2. Read the spend verdict once per turn, or cache it in-process for 1–2 s.
  3. Cache `unhealthy_aliases` per process for 2–5 s (the `apps/api/app/core/user_cache.py` pattern), or read it in one pipeline.
  4. Use `MGET` in `list_sessions` and pipelines in the push loops.

  Seams: `apps/api/app/core/spend_counter.py`, `apps/api/app/services/model_health.py`.
- **Verify:** Run the `world` scratch test with `daily_global_spend_usd=1`: ≈ 43 → ≈ 30 commands per warm plain turn, no `GET spend_mcents:*`, and `ZRANGE` ≤ 6 per 5 s per machine. In production, track Upstash commands per turn.
- **Source:** raw/agent-net.md NET-05; raw/agent-dead.md DEAD-06 (legacy spend key)

<a id="net-05"></a>

#### NET-05 — The query embedding is requested two or three times per personal turn
- **Severity:** Low · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/gateways/embedding_gateway.py:21-24,145-192`, `apps/api/app/modules/chat/prompt_context.py:208-212,233-239`, `apps/api/app/modules/memory/retrieval.py:318-323`, `apps/api/app/modules/chat/history_rag.py:57-70,128-139,161-193`, `apps/api/app/modules/attachments/rag.py:299-308`, `apps/api/app/repositories/message_chunks.py:57-71`, `apps/api/app/core/settings/llm.py:41`
- **Evidence:** Memory, history RAG and attachment RAG start together and each reads `memembed:{user}:{sha(query)}` before any has embedded (no single-flight), and the worker's `message_index` embeds the user line and the reply in two requests and two transactions. Lead check: cited code read at the listed lines.
- **Impact:** A personal turn makes 2× the embedding requests (3× with document chunks), each with a 34 KB Redis `SET`, and the turn waits on the slower of two tail latencies within the 0.75 s budget; the money is negligible.
- **Fix:** Start one embedding task per turn in `_ContextReads` that all three readers await, and use one `embed_many` call and one transaction for both messages in `index_turn_messages`.
- **Verify:** With a counting fake, a personal turn makes 1 `embed_text` call (today 2, or 3 with attachment chunks) and `index_turn_messages` sends 1 request (today 2).
- **Source:** raw/agent-net.md NET-06

<a id="net-06"></a>

#### NET-06 — Reference-photo candidates are fetched one at a time (8 s each) against a 6 s wait; late photos are stored, then orphaned
- **Severity:** Low · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/modules/images/search.py:111-131,240-243`, `apps/api/app/core/settings/search.py:23-24`, `apps/api/app/gateways/image_search_gateway.py:21`, `apps/api/app/modules/images/answer_photo.py:30,78,79-81,102-106`, `apps/api/app/modules/chat/turn_intercepts.py:217-225`
- **Evidence:** `_fetch_candidates` tries up to 3 candidates one after another with an 8 s deadline each, while the answer photo waits only 6 s and then lets the late task finish storing an unlinked photo for the reaper to delete. Lead check: cited code read at the listed lines.
- **Impact:** One slow image host uses the whole 6 s, so the reply goes out without a photo even when candidates 2–3 would have arrived; the late photo still costs a search slot, an R2 `PUT`, a DB row and a reaper delete, and a lookup turn can take 12 + 3 × 8 s.
- **Fix:** Fetch candidates concurrently under one deadline below the caller's wait (`asyncio.wait(..., FIRST_COMPLETED)`, cancelling the rest), and cancel the task on the answer-photo timeout instead of storing an orphan.
- **Verify:** A unit test with fake fetches of 8 s, 0.2 s and 0.2 s gets a photo in < 1 s; in production, watch "Answer photo took too long" logs and reaper deletions of `source="search"` rows.
- **Source:** raw/agent-net.md NET-07

<a id="net-07"></a>

#### NET-07 — `done` waits on a SELECT whose result nobody reads
- **Severity:** Low · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/modules/chat/turn_settle.py:208-219`, `apps/api/app/repositories/usage.py:52-61`, `apps/api/app/modules/chat/ws_turn.py:115-124`
- **Evidence:** After the Core upsert, `add_tokens` re-reads the row with `session.get` (the identity map is empty, so it queries) and its only caller ignores the result, while `ws_turn.py` holds `done` for this commit. Lead check: measured: `SELECT usage_daily` is the last statement before `COMMIT` on every warm turn (raw/sql-text.json).
- **Impact:** Every turn pays one round trip (~12 ms) inside the commit that gates `done`, plus one statement on Neon.
- **Fix:** Return nothing from `add_tokens` in `apps/api/app/repositories/usage.py`, or use `RETURNING` when a caller needs the row.
- **Verify:** The same scratch count shows 0 `SELECT usage_daily` on a warm turn.
- **Source:** raw/agent-net.md NET-08

<a id="net-08"></a>

#### NET-08 — `GET /chats` reads every column (incl. summaries up to 6 KB) of up to 250 chats to return seven fields
- **Severity:** Low · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/modules/chat/service.py:58-88`, `apps/api/app/repositories/chats.py:76-95,98-109`, `apps/api/app/models/orm/chat.py:51`, `apps/api/app/services/context_window.py:14,217-221`, `apps/api/app/models/schemas/chats.py:55-64`, `apps/api/app/modules/chat/turn_load.py:121-122`
- **Evidence:** `select(Chat)` (limit 200 + 50 archived) returns `summary` (up to 6,000 chars) for a 7-field `ChatOut`, and the measured SQL shows `chats.summary` in every chat `SELECT`, including the per-turn `get_by_id`. Lead check: cited code read at the listed lines.
- **Impact:** The cost is small today because compression rarely runs (SCALE-03), but once it works a heavy user's drawer open moves up to ~1.5 MB per call on a start-up endpoint.
- **Fix:** `load_only` the seven columns in `list_for_user` (`apps/api/app/repositories/chats.py`), and read `summary` only where the prompt uses it.
- **Verify:** Run `EXPLAIN (ANALYZE, BUFFERS)` and measure response bytes for a user with 300 chats that have summaries.
- **Source:** raw/agent-net.md NET-09

<a id="net-09"></a>

#### NET-09 — Phone connectivity probe polls every 1.5 s with no backoff or jitter while degraded (two requests per tick, one to Google)
- **Severity:** High · **Confidence:** High · **Effort:** S
- **Locations:** `apps/mobile/hooks/useNetworkStatus.ts:11,33-45,47-48,50-53,63-83`, `apps/mobile/lib/networkProbe.ts:7,57-74`, `apps/mobile/lib/api/connectivity.ts:10-24`, `apps/mobile/node_modules/@react-native-community/netinfo/src/internal/defaultConfiguration.ts:3-15`, `apps/mobile/node_modules/@react-native-community/netinfo/src/internal/internetReachability.ts:105-127`, `apps/mobile/node_modules/@react-native-community/netinfo/android/src/main/java/com/reactnativecommunity/netinfo/ConnectivityReceiver.java:120-131`
- **Evidence:** While degraded, the hook probes on a fixed 1.5 s `setInterval` until `status === "online"`. Every NetInfo event and every app return probes too, and start-up probes twice. Each probe is our `/health` plus Google's `generate_204`. NetInfo is never configured, so iOS also sends its own `HEAD generate_204` every 60 s (5 s while unreachable), and Android probes on each LTE↔5G change. `d8e19b301` measured "80 requests a minute" but only paused the loop in the background.

  Lead check: read `apps/mobile/hooks/useNetworkStatus.ts:11,47-54,64-83` and `apps/mobile/lib/networkProbe.ts:57-74`.
  ```ts
  // hooks/useNetworkStatus.ts
  const OFFLINE_POLL_MS = 1_500;
  ...
  void NetInfo.fetch().then(onNetInfo);
  const unsubscribe = NetInfo.addEventListener(onNetInfo); // NetInfo calls the handler at once (state.ts:110-119)
  ...
  void tick();
  const id = setInterval(() => void tick(), OFFLINE_POLL_MS);
  ```
- **Impact:** While the API is slow (> 3.5 s), down, or blocked on a user's network, every foregrounded phone sends `/health` ~40 times a minute plus the same to Google, indefinitely and in lockstep. With 5,000 phones that is ~3,300 req/s just as the API recovers, each a TLS handshake and possibly a `hard_limit = 200` slot (`fly.toml:73-75`). Users whose network blocks our host spend 80 requests/min of battery and data.
- **Fix:** In `apps/mobile/hooks/useNetworkStatus.ts` and `apps/mobile/lib/networkProbe.ts`:
  - Back off the degraded loop (1.5 s → 3 → 6 → … → 60 s, ±20% jitter), resetting on a NetInfo change.
  - Probe once at start.
  - Skip the return probe after a recent successful API request (recorded in `requestRaw`).
  - Call `NetInfo.configure({ reachabilityShouldRun: () => false })`.
- **Verify:** Fake-timer test in `apps/mobile/hooks/__tests__/useNetworkStatus.test.tsx`: 10 min degraded → ≤ ~15 probes (today ≈ 400), and one probe at mount. In production, track the `/health` rate per active user.
- **Source:** raw/agent-netm.md NETM-01

<a id="net-10"></a>

#### NET-10 — `GET /home` is fetched at start, on every token rotation, on return and on chat focus for a greeting the phone already computes; the server greeting is English-only and replaces the translated one
- **Severity:** Medium · **Confidence:** High · **Effort:** S
- **Locations:** `apps/mobile/features/home/context/HomeContext.tsx:93-105,109-112,116-123`, `apps/mobile/features/home/hooks/useHomeRefreshOnChatFocus.ts:13-27`, `apps/mobile/features/home/components/HomeStarters.tsx:91,101,102-109,124`, `apps/mobile/features/home/model/homeWelcome.ts:7-13`, `apps/api/app/modules/home/greeting.py:11-24`, `apps/api/app/modules/home/service.py:40-83`
- **Evidence:** `HomeStarters` reads only `display.greeting` and computes the overdue row locally. No phone code reads `urgent_todos`, `.subtitle` or `.starters`; the starter chips were removed in `2cf7db33e`. The phone already has a translated `localGreeting`, while the server still queries `list_due_soon`.

  Lead check: read `apps/api/app/modules/home/greeting.py:11-24` (English phrases only) and `apps/mobile/features/home/components/HomeStarters.tsx:124` (only `display.greeting` is used); `urgent_todos` is never read on the phone.
  ```tsx
  // HomeStarters.tsx
  const { screen } = useHome();
  const display = screen ?? instantHomePlaceholder();
  const urgent = listHomeUrgentTodos(todos, undefined, leadMinutes);   // local, not screen.urgent_todos
  <Text style={s.greeting}>{display.greeting}</Text>                  // the only field used
  ```
- **Impact:** Each user sends 1 request per cold start, per return after 20 s and per hourly rotation. At 100k DAU that is roughly 1–2 million a day, each an authenticated call plus a Redis read (a DB query on a miss). The greeting flickers hourly because the screen resets to the placeholder. The English server greeting then replaces the translated one ("Bonjour" → "Good morning, Sam").
- **Fix:** Render `localGreeting(now)` plus the first name from `useAuth().user`. Delete the phone's `/home` path (`HomeContext`, `useHomeRefreshOnChatFocus`, `homeApi`), and decide the server endpoint separately.
- **Verify:** A start-up request capture (or a jest test of the `app/_layout` providers with `lib/api` mocked) shows no `/home` call. A per-locale `HomeStarters` snapshot shows the translated greeting with the name.
- **Source:** raw/agent-netm.md NETM-02

<a id="net-11"></a>

#### NET-11 — Effects keyed on the bearer token re-run on every hourly token rotation
- **Severity:** Medium · **Confidence:** High · **Effort:** M
- **Locations:** `apps/mobile/contexts/ModelsContext.tsx:89-123,125-137`, `apps/mobile/features/home/context/HomeContext.tsx:34-36,93-105`, `apps/mobile/features/chat/hooks/useQuotaNudge.ts:44-60`, `apps/mobile/hooks/useBootstrapSync.ts:44-61,104-108`, `apps/mobile/lib/deviceLocation.ts:46-47,60-79`, `apps/mobile/features/todos/model/todoReminders.ts:98`, `apps/mobile/features/chat/hooks/useDraftChat.ts:43-84`, `apps/mobile/features/attachments/components/AttachmentImageStage.tsx:257-281`, `apps/mobile/features/attachments/hooks/usePdfPreview.ts:57-75`, `apps/mobile/features/chat/hooks/useChatTransport.ts:82-110`
- **Evidence:** Tokens live 60 minutes (`apps/api/app/core/settings/auth.py:21`). `apps/mobile/lib/api/client.ts:226-232` refreshes them and `apps/mobile/contexts/AuthContext.tsx:221-231` publishes the new token. Seven effects with `token` in their dependencies then redo their I/O:
  - `/models`.
  - A forced `/home`.
  - The usage GET.
  - A GPS fix + reverse geocode, which can raise the OS permission sheet from a background sync, against the rule at `todoReminders.ts:98`.
  - A new draft chat.
  - Aborted-and-restarted image and PDF downloads.

  Two instances were fixed one at a time (`fce17eb0d`, `bde74a124`), and `HomeContext.tsx:34-36` itself says "Cache/dedupe by account, not bearer token".

  Lead check: cited code read at the listed lines.
  ```ts
  // hooks/useBootstrapSync.ts:104-108 (the fixed one)
  const tokenRef = useRef(token);
  tokenRef.current = token;
  const signedIn = Boolean(token);
  ```
- **Impact:** Each active user-hour adds:
  - +1 `/models`;
  - +1 forced `/home`, with a visible reset;
  - +1 usage GET (free plan);
  - +1 GPS fix and reverse geocode (geocoders are rate-limited per app);
  - a restarted download if a viewer is open.

  Paid users also get a usage GET at cold start, because the cached plan is forced to `"free"`.
- **Fix:** Depend on account identity instead of the token: `user.id` + session generation, or a `useAuthSession()` value that changes only on sign-in/out. Read the latest token from a ref at call time. Add a guard test that re-renders `AuthProvider` with a rotated token and asserts no new `lib/api` calls.
- **Verify:** A test in `apps/mobile/contexts/__tests__/` rotates the token via `setTokenRefreshHandler` and asserts no extra `listModels`/`getHomeScreen`/`todayUsage`/`updateMe` calls and no `getCurrentPositionAsync`.
- **Source:** raw/agent-netm.md NETM-03

<a id="net-12"></a>

#### NET-12 — The chat WebSocket keeps the token it was created with; after expiry the view falls back to SSE for good
- **Severity:** Medium · **Confidence:** High · **Effort:** S
- **Locations:** `apps/mobile/features/chat/hooks/useChatTransport.ts:82-100,120-135`, `apps/mobile/features/chat/model/wsTransport.ts:113-151,183-195`, `apps/mobile/features/chat/hooks/useChatIncoming.ts:271-282`, `apps/mobile/lib/api/client.ts:226-232`, `apps/api/app/modules/chat/ws_api.py:234-275,388-403`, `apps/api/app/core/settings/edge.py:19`
- **Evidence:** A transport is built once per view with the render's `token`. Reconnects after 4408/1001/1012 send `this.options.token`. A return to the app reconnects with the React `token`, which has expired after > 60 min because only `requestRaw` refreshes proactively. On "Unauthorized" the transport sets `preferSse = true`, `connect()` becomes a no-op, and the turn replays over SSE. The server idles sockets out only after 300 s, so a busy chat keeps one socket for hours.

  Lead check: read `apps/mobile/features/chat/hooks/useChatTransport.ts:82-100` (transport built once), `apps/mobile/features/chat/model/wsTransport.ts:140-150` (auth frame sends `this.options.token`) and `:183-195` (`preferSse = true`).
  ```ts
  // useChatTransport.ts
  let transport = wsTransportRef.current;
  if (!transport) {
    transport = new ChatWsTransport({ url: chatWebSocketUrl(chatId), token, ... });
  // wsTransport.ts — on "Unauthorized":
  this.preferSse = true;   // connect() returns early from now on
  ```
- **Impact:** Reopening the app more than an hour later onto an open chat sends every turn in that view over SSE. A conversation that outlives its token has the next frame refused and replayed, costing an extra round trip plus a refresh on that turn's time to first token. SSE also loses the WebSocket stop path (`cancel` with `shown_chars`).
- **Fix:** Before `connect()` and `beginTurn`, run the `requestRaw` expiry check through a shared `freshAccessToken()` exported from `apps/mobile/lib/api/client.ts`, and make `options.token` a getter. On "Unauthorized", refresh once and retry the WebSocket instead of latching SSE.
- **Verify:** In `apps/mobile/features/chat/model/__tests__/chatWsTransport.test.ts`: token A → 4408 → the reconnect uses token B; an expired token triggers one refresh and a WebSocket retry, not `preferSse`. In production, the share of turns over SSE (`chat_ttft.transport`) should drop.
- **Source:** raw/agent-netm.md NETM-04

<a id="net-13"></a>

#### NET-13 — Every new-chat view creates a server chat and a WebSocket before the user types
- **Severity:** Medium · **Confidence:** Medium · **Effort:** M
- **Locations:** `apps/mobile/features/chat/hooks/useDraftChat.ts:7,24-28,30-41,43-70,76-84`, `apps/mobile/features/chat/hooks/useChatDraftWarmup.ts:17-23`, `apps/mobile/features/chat/model/draftLogic.ts:66-78`, `apps/mobile/features/chat/hooks/useChatTransport.ts:102-110`, `apps/mobile/features/chat/model/wsConnect.ts:13`, `apps/mobile/features/chat/hooks/useChatRouteLoader.ts:160-186,272-283,341-353`, `apps/mobile/features/chat/api.ts:63-78`, `apps/mobile/features/chat/hooks/useEnsureChatId.ts:32-37`, `apps/api/app/repositories/chats.py:83,101`, `apps/api/app/modules/chat/ws_api.py:53-54`, `apps/api/app/core/settings/edge.py:19`, `fly.toml:73-75`, `docs/PRODUCTION.md:205-213`
- **Evidence:** 125 ms after mount, `useDraftChat` sends `POST /chats` and the warmup opens a socket; every chat view opens one after a 100 ms debounce. On `background` or `inactive` with nothing typed:
  - `discardEmptyChat` sends `GET /chats/{id}/messages?limit=20` + `DELETE`.
  - `clearDraftChat` sends a second `DELETE` of the same id.

  The draft is not re-created on return, so the next send pays a serial `POST /chats`. No job deletes empty chats whose `DELETE` never left. The prewarm was added for time to first token (`49a3dee1c`).

  Lead check: cited code read at the listed lines.
  ```ts
  // useChatRouteLoader.ts:272-282
  if (state === "background" || state === "inactive") {
    ...
    if (messages.length === 0 && chatId == null) {
      discardEmptyChat(draftId);   // GET ?limit=20 + DELETE
      clearDraftChat();            // DELETE again (same id, still in draftChatIdRef)
    }
  ```
- **Impact:** The most common session ("open the app, glance, leave") costs an insert, a WebSocket handshake (two Redis rate-limit checks + token verification), a 20-message GET and two DELETEs, for nothing. iOS `inactive` (Control Center, app switcher, alerts, calls) also throws the prewarm away mid-session. Sockets track people looking at a chat, not turns. If Fly counts them against `hard_limit = 200` (unconfirmed, `docs/PRODUCTION.md:205-213`), idle sockets set the Machine count. Users behind one NAT also share the 60/min per-IP handshake budget.
- **Fix:**
  - Prewarm on intent (composer focus, first keystroke, attach), not on mount.
  - Keep one reusable empty draft per account (idempotent `POST /chats`), or let the first message create the chat.
  - Make any remaining delete a single server-side `DELETE /chats/{id}?if_empty=1`, sent on `background` only.

  Seams: `apps/mobile/features/chat/hooks/useDraftChat.ts`, `useChatTransport.ts`, `apps/api/app/modules/chat/api.py`.
- **Verify:** In `useDraftChat.test.tsx` + `useChatRouteLoader.test.tsx`: mount → background without typing → no `createChat`/`deleteChat`/`deleteChatIfEmpty`, and `inactive` never deletes. In production, track `POST /chats` ÷ chats with a message (today ≫ 1).
- **Source:** raw/agent-netm.md NETM-05

<a id="net-14"></a>

#### NET-14 — After each turn the phone polls for data the stream could carry (usage, three to-do reloads, titles)
- **Severity:** Medium · **Confidence:** High · **Effort:** S
- **Locations:** `apps/mobile/features/chat/hooks/useChatScreenError.ts:92-99`, `apps/mobile/features/chat/hooks/useQuotaNudge.ts:44-60`, `apps/api/app/modules/chat/stream_events.py:157-173`, `apps/mobile/features/chat/model/chatEvents.ts:79-80,111-119`, `apps/mobile/features/chat/screens/ChatScreen.tsx:74-76`, `apps/api/app/core/settings/chat.py:22`, `apps/api/app/modules/todos/reminder_fences.py:97-113`, `apps/api/app/modules/chat/post_turn.py:128-134`, `apps/api/app/modules/chat/finalize_reminders.py:64-68`, `apps/mobile/features/chat/hooks/useChatTitlePolling.ts:22-23,61-95`, `apps/mobile/features/chat/model/turnReconcile.ts:10-14,56-88`, `apps/mobile/features/chat/hooks/useDroppedTurnReconcile.ts:41-42`
- **Evidence:**
  - **Usage:** free users send `GET /chats/usage/today` after every turn because `done` carries no usage.
  - **To-dos:** `todos_changed` triggers three forced full to-do reads (now, 2.5 s, 7 s), waiting for a background extraction. With `reminder_proposals_enabled = True` (the default) that extraction never runs: `materialize_reminder_fences(confirm=True)` writes nothing and the `todos` job is skipped. `todos_changed` therefore comes only from a transcript heuristic.
  - **Titles:** untitled chats poll `GET /chats/{id}` every 2 s (≤ 8 times).
  - **Dropped turns:** a dropped turn polls a 40-message page every 2 s (≤ 15 times).

  Lead check: cited code read at the listed lines.
  ```ts
  // chatEvents.ts
  /** Background Schedule extraction can finish after `done`, so the to-do list refreshes again. */
  const TODO_RESYNC_DELAYS_MS = [2_500, 7_000] as const;
  ...
  if (payload.todos_changed) {
    ctx.onTodosSyncRef.current?.();
    for (const delay of TODO_RESYNC_DELAYS_MS) { ...setTimeout(() => ctx.onTodosSyncRef.current?.(), delay) }
  ```
- **Impact:** Free users (the majority) add one authenticated GET per turn. A reminder-flavoured turn adds three full to-do downloads for no server change. After a deploy every socket gets 1012, so every phone that was mid-turn polls 40-message pages every 2 s in lockstep.
- **Fix:**
  - Put `used_tokens`/`daily_limit` in `DoneEvent` (`apps/api/app/modules/chat/stream_events.py`).
  - Send `todos_changed` only when rows were written, and delete `TODO_RESYNC_DELAYS_MS` while proposals are on.
  - Poll dropped turns with `limit=4` and ±25% jitter.
- **Verify:**
  - `useChatIncoming.test.tsx`: `todos_changed` → one `listTodos`.
  - `useChatScreenError.test.tsx`: no `todayUsage` at turn end.
  - Production: requests per turn (today 1 WebSocket frame + 1–4 GETs + 2 analytics POSTs).
- **Source:** raw/agent-netm.md NETM-06

<a id="net-15"></a>

#### NET-15 — Two analytics POSTs per chat turn, each a one-event batch
- **Severity:** Medium · **Confidence:** High · **Effort:** S
- **Locations:** `apps/mobile/features/chat/model/latency.ts:13-17,63-87`, `apps/mobile/features/chat/model/turnOutcome.ts:40-43,72-82`, `apps/mobile/features/chat/model/latencyReporter.ts:32-65`, `apps/mobile/lib/auth.ts:104-107`, `apps/mobile/lib/productAnalytics.ts:18-41`, `apps/api/app/models/schemas/analytics.py:39-42`, `apps/api/app/modules/analytics/api.py:13-24`
- **Evidence:** `chat_ttft` and `chat_turn_outcome` each go out as a 1-element batch, and each send reads SecureStore for the token. The server accepts 20 events per batch and runs `get_current_user` + insert + commit per POST. Paywall, purchase and push events do the same.

  Lead check: read `apps/mobile/features/chat/model/latencyReporter.ts:31-66` and `apps/mobile/features/chat/model/turnOutcome.ts:40-43` ("sampling" = production only, i.e. every turn).
  ```ts
  // latencyReporter.ts
  const token = await getToken();
  ...
  await analyticsApi.recordProductEvents(token, [ { name, properties, ... } ]);   // always a 1-element batch
  ```
- **Impact:** Each turn adds two HTTPS requests and two DB commits beside one WebSocket frame. At 100k DAU × 20 turns that is ~4M a day, likely more requests than the chat traffic itself. The `chat_ttft` POST also competes with the reply on a weak radio.
- **Fix:** Add an in-memory queue in `apps/mobile/lib/productAnalytics.ts`, flushed on turn end, at 20 events, after 30 s and on background. Sample the two chat events (e.g. 10–20%), and pass the token from the caller.
- **Verify:** A queue unit test: two turns → one POST with four events. In production, `/analytics/events` per turn should fall from 2 to ≤ 0.2.
- **Source:** raw/agent-netm.md NETM-07

<a id="net-16"></a>

#### NET-16 — Whole resources are re-downloaded on every trigger with no conditional request or delta
- **Severity:** Medium · **Confidence:** High · **Effort:** M
- **Locations:** `apps/mobile/features/todos/api.ts:4,8-21`, `apps/api/app/modules/todos/repository.py:72-84`, `apps/mobile/features/todos/hooks/useTodosList.ts:115,116-122`, `apps/mobile/features/todos/hooks/useTodosActions.ts:74-76,100,148`, `apps/mobile/features/todos/hooks/useReminderProposal.ts:27-30`, `apps/api/app/modules/todos/api.py:99-113`, `apps/mobile/features/chat/hooks/useChatRouteLoader.ts:225-246,268-326,408-412,419`, `apps/mobile/hooks/useNetworkStatus.ts:50-53`, `apps/mobile/contexts/ModelsContext.tsx:125-137`, `apps/mobile/features/home/context/HomeContext.tsx:116-123`, `apps/mobile/lib/pushNotifications.ts:234-239`
- **Evidence:** `listTodos` walks every `/todos/page?limit=1000` page of all rows, completed ones included, and completed rows are never deleted. It runs:
  - at start;
  - on every return after 20 s;
  - after every mutation, whose response already holds the row;
  - after a reminder confirm, ignoring the returned `items`;
  - three times per reminder turn (NET-14).

  Opening a chat always re-reads 40 messages, although the same hook's foreground path skips reads < 20 s old. Nothing in `apps/mobile` or `apps/api/app` uses `ETag`, `If-None-Match`, `If-Modified-Since` or `since=`.

  Lead check: cited code read at the listed lines.
  ```ts
  // features/todos/api.ts
  const TODO_PAGE_SIZE = 1000;
  ...
  for (;;) {
    const page = await request<TodoPage>(`/todos/page?limit=${TODO_PAGE_SIZE}${suffix}`, token, options);
    page.items.forEach((row) => rows.set(row.id, row));
    if (page.next_cursor === null) return [...rows.values()];
  ```
- **Impact:** The to-do payload grows without bound (~300 B per row; 1,500 rows ≈ 450 KB). It is re-read on every return, checkbox tap and reminder turn, and each read is a full index scan of the user's rows. Chat switching re-downloads a page that was just painted from disk.
- **Fix:**
  - Load open plus recently completed to-dos, and page older ones on demand.
  - Add `updated_since` or an `ETag` to `/todos/page`, and apply mutation responses instead of refetching.
  - Reuse `shouldSkipSilentChatRefetch` on chat open.
  - Add weak `ETag`s on `/todos/page`, `/chats` and `/chats/{id}/messages`, with `If-None-Match` sent from `apps/mobile/lib/api/client.ts`.
  - Replace the six `AppState` listeners (staleness none / 20 s / 5 min / 12 h) with one coordinator holding per-resource TTLs.
- **Verify:** In `apps/mobile/features/todos/hooks/__tests__`: a toggle → one PATCH and no `listTodos`; A → B → A within 20 s → one `listMessages` for A. In production, track `/todos/page` bytes per active user per day.
- **Source:** raw/agent-netm.md NETM-08

<a id="net-17"></a>

#### NET-17 — Phone request deadlines end when headers arrive; bodies, SSE and WebSocket have no idle deadline
- **Severity:** Medium · **Confidence:** Medium · **Effort:** S
- **Locations:** `apps/mobile/lib/api/client.ts:82-95,97-135,178-179,202-261,280,288`, `apps/mobile/features/chat/model/sse.ts:79-91`, `apps/mobile/features/chat/model/wsTransport.ts:179-181`, `apps/mobile/node_modules/expo/android/src/main/java/expo/modules/fetch/ExpoFetchModule.kt:26-31`, `apps/mobile/node_modules/react-native/ReactAndroid/src/main/java/com/facebook/react/modules/network/OkHttpClientProvider.kt:49-54`, `apps/mobile/node_modules/react-native/ReactAndroid/src/main/java/com/facebook/react/modules/websocket/WebSocketModule.kt:89-91`, `apps/mobile/node_modules/expo/ios/Fetch/ExpoURLSessionTask.swift:27`
- **Evidence:** `requestRaw` clears its 30 s timer in `finally` once headers arrive, and `request()` then reads the body unguarded. The refresh body likewise outlives its 15 s timer, and every request awaits the single-flight refresh without its own timeout. SSE has no idle deadline, and the first WebSocket event clears the only one. The transports add no deadline either: Android OkHttp timeouts are 0, the RN WebSocket read timeout is off, and iOS uses `timeoutInterval = 0`.

  Lead check: read `apps/mobile/lib/api/client.ts` `requestRaw` (timer cleared in `finally` once `fetch` resolves).
  ```ts
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  ...
  } finally {
    if (!streamingBodyReturned) externalSignal?.removeEventListener("abort", onExternalAbort);
    clearTimeout(timeout);          // runs as soon as headers arrive
  }
  // request(): the body is read afterwards, unguarded
  const data = response.status === 204 ? undefined : await response.json();
  ```
- **Impact:** On a half-open connection after headers:
  - An opening chat stays loading, and Send is silently blocked (`apps/mobile/features/chat/model/sendGuards.ts:21-25`).
  - A reply keeps its typing indicator until the user taps Stop.
  - A stalled refresh body wedges every API call until the app is killed.

  `docs/ENGINEERING_STANDARDS.md:104-105` requires timeouts and cancellation to be handled.
- **Fix:**
  - Clear the timer only after the body is parsed.
  - Race `refreshAccessToken()` against the caller's signal and timeout.
  - Add a per-event stream idle deadline (e.g. 45 s; the server's provider idle limit is 30 s, `fly.toml:37`) that runs the dropped-turn reconcile.

  Seams: `apps/mobile/lib/api/client.ts`, `features/chat/model/sse.ts`, `features/chat/model/wsTransport.ts`.
- **Verify:**
  - A `json()` that never resolves makes the request reject after `timeoutMs`.
  - A hanging refresh rejects the queued requests, and the next request starts a new refresh.
  - A silent SSE/WS stream starts the reconcile after the idle deadline.
- **Source:** raw/agent-netm.md NETM-09

<a id="net-18"></a>

#### NET-18 — Opening a search hit deep in a chat pages back 40 messages at a time, without a cap
- **Severity:** Medium · **Confidence:** High · **Effort:** S
- **Locations:** `apps/mobile/features/chat/hooks/useChatHighlightScroll.ts:79-112`, `apps/mobile/features/chat/hooks/useChatRouteLoader.ts:461-499`, `apps/mobile/features/chat/model/constants.ts:2`, `apps/mobile/components/ConversationList.tsx:166-171`, `apps/api/app/modules/chat/api.py:180-195`
- **Evidence:** Opening a drawer search hit (`openChat(id, messageId)`) re-runs `loadOlderMessages` (`MESSAGE_PAGE_SIZE` = 40) after each page until the hit is found or `hasMoreOlder` is false. The server offers only `limit` (≤ 200) and `before`.

  Lead check: cited code read at the listed lines.
  ```ts
  // useChatHighlightScroll.ts
  const cursor = messages[0].id;
  if (!hasMoreOlder || chatLoading || loadingOlder || request.loading || request.cursor === cursor) return;
  ...
  try { await loadOlderMessages(); }
  finally { ...setPageRevision((value) => value + 1); }   // re-runs the effect → next page
  ```
- **Impact:** A hit 1,000 messages back takes 25 sequential round trips (several seconds on mobile) and downloads 1–3 MB of messages in between. This falls on the power users with long tutoring threads, who search most.
- **Fix:** Add `GET /chats/{id}/messages?around={message_id}&limit=40` (a window plus `has_more` both ways) and a list model that can hold one gap. As a stopgap, use `limit=200` while seeking (5× fewer round trips).
- **Verify:** `apps/mobile/features/chat/hooks/__tests__/useChatHighlightScroll.test.tsx`: a hit 1,000 messages back takes ≤ 2 requests. Add a server test for `around`.
- **Source:** raw/agent-netm.md NETM-10

<a id="net-19"></a>

#### NET-19 — Smaller phone re-reads: subscription sync then `/auth/me`; push token re-registered every cold start; link previews without in-flight dedupe or failure memory
- **Severity:** Low · **Confidence:** High · **Effort:** S
- **Locations:** `apps/mobile/hooks/useSubscriptionActions.ts:9-14,16-24`, `apps/mobile/contexts/AuthContext.tsx:250-258`, `apps/mobile/features/account/screens/ArchivedChatsScreen.tsx:20-23`, `apps/mobile/features/account/hooks/useFocusedList.ts:27-31`, `apps/mobile/features/chat/hooks/useQuotaNudge.ts:49`, `apps/mobile/lib/cache/usageCache.ts:5-24`, `apps/mobile/lib/pushNotifications.ts:101,123-146,181-191,200-240`, `apps/mobile/hooks/useBootstrapSync.ts:63-91`, `apps/api/app/repositories/push_tokens.py:38`, `apps/mobile/lib/linkPreview.ts:11-33`, `apps/mobile/components/LinkPreviewCard.tsx:26-41`, `apps/api/app/modules/link_preview/api.py:30-50`, and 7 more (see raw/agent-netm.md NETM-11, NETM-12, NETM-13)
- **Evidence:** `syncSubscription` already returns the `User` yet `refreshUser()` then sends `GET /auth/me`; the archived-chats screen re-downloads all of `GET /chats` on every focus; the quota nudge bypasses the token-keyed `usageCache`; the push token's 12 h freshness lives in module memory reset every process; and link previews cache successes only, with no in-flight dedupe or abort. Lead check: cited code read at the listed lines.
- **Impact:** The cost is small per event: an extra authenticated round trip per purchase/restore, settings visit or nudge; an Expo round trip plus a DB upsert per cold start per user; and duplicate or retried link-preview requests (a 429 retried on every scroll), bounded by the server cache.
- **Fix:** Set the user from the `syncSubscription` response, read archived rows through `fetchChatList` (or a paged `GET /chats/archived`), route the nudge through `fetchTodayUsage` keyed by user id, persist the push-sync record for 12 h, and keep in-flight promises and failures in the link-preview map with an `AbortSignal`.
- **Verify:** Hook tests assert one request per action and a usage-cache hit after token rotation, two simulated cold starts give one `registerPushToken`, and two concurrent link-preview calls send one request with no retry after a 429.
- **Source:** raw/agent-netm.md NETM-11, NETM-12, NETM-13

### E. Bloat and dead code

<a id="dead-01"></a>

#### DEAD-01 — 13 API routes no client calls, plus ~540 lines only they reach
- **Severity:** Medium · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/modules/todos/api.py:25` (`GET /todos`), `:55` (`/todos/topics`), `:84` (`/todos/reorder`), `:144` (`/todos/topic/{topic}`), `apps/api/app/modules/memory/api.py:146` (`/memories/consolidate`), `:170` (`/memories/type/{memory_type}`), `:222` (`…/facts/{fact_index}`), `apps/api/app/modules/speech/api.py:163-204` (`/speech/tts/stream`), `:282`, `:291`, `:300`, `:309` (410 tombstones `live/turn|refund|commit|speak`), `apps/api/app/modules/speech/realtime.py:224-237` (426 tombstone `live/webrtc`), and 24 more (see raw/agent-dead.md DEAD-01)
- **Evidence:** Matching all 92 routes against the non-test sources of `apps/mobile` and `apps/web` leaves these 13 without a client once dynamic, external and dev/ops routes are set aside; `/speech/tts/stream` never had a caller on `main`. Lead check: Lead grep of the phone (`lib`, `features`, `contexts`, `hooks`, `components`, `app`, tests excluded): `/todos/topics`, `/todos/reorder`, `/todos/topic/`, `/memories/consolidate`, `/memories/type/`, `/facts/`, `/speech/tts/stream` → 0 references; `GET /todos` unused (the phone lists via `/todos/page`). `apps/web` uses only login + chat SSE.
- **Impact:** Five authenticated routes write or delete user data with no caller, the 82-line index-based fact delete is a second delete semantics that re-embeds and rewrites a row, `/tts/stream` calls a paid provider and spends TTS quota, and the tombstones answer pre-launch clients (the 426 detail is developer instructions: "restart Metro").
- **Fix:** Delete the 13 routes and the ≈540 lines only they reach, the `RealtimeOfferIn/Out` and `TodoReorder*` schemas and re-exports, the surface wrappers and their tests; update `FEATURES.md:213,1311`; re-add a route with its client if `apps/web` ever needs it; keep `/legal/delete-account` and the dev-gated `/chats/usage/today/reset` and `/auth/me/pro-dev`.
- **Verify:** Re-run `route_clients.py` (every route has a client or a documented external caller); `uv run pytest app/tests/modules/{todos,memory,speech}` green; `grep -rn "iter_tts_pcm\|stream_pcm_via_openai\|delete_by_type\|request_user_consolidation\|reorder_todos\|delete_by_topic" apps/api/app` empty.
- **Source:** raw/agent-dead.md DEAD-01

<a id="dead-02"></a>

#### DEAD-02 — ~700 lines run only in configurations production never uses (pre-stream web-search inject, the LLM search classifier, the todo-sync LLM job)
- **Severity:** Medium · **Confidence:** High · **Effort:** M
- **Locations:** `apps/api/app/modules/web_search/augment.py:69-70`, `:72-157`, `apps/api/app/modules/chat/turn_prep/augment.py:104-107`, `:189-224`, `fly.toml:28-30`, `apps/api/app/core/settings/search.py:10`, `apps/api/app/modules/web_search/classify.py`, `apps/api/app/modules/web_search/detection.py:310-332`, `apps/api/app/tests/behavior/harness.py:184`, `apps/api/app/modules/chat/post_turn.py:132`, `apps/api/app/modules/todos/sync.py`, `apps/api/app/background/handlers.py:224-231`, and 18 more (see raw/agent-dead.md DEAD-02)
- **Evidence:** (1) `mcp_tool_loop_enabled` is on (default, never overridden), so `build_search_augmentation` returns `(None, [])` at `augment.py:69-70` and the heuristic search below never runs, yet every augmented turn awaits it; 53 test sites turn the loop off to reach it. (2) `fly.toml` has kept the LLM classifier off since #1297, while the behavior harness forces it on. (3) `reminder_proposals_enabled` is on (default), so `_todos_job` returns `[]` and the todo-sync job (`sync.py`, `extract.py`, `jobs.py`, handler, mock, schema) is never enqueued. Spans: 125, 174 and ≈410 lines. Lead check: Lead read `fly.toml` `WEB_SEARCH_CLASSIFIER_ENABLED = "false"` vs `core/settings/search.py:10` default `True`.
- **Impact:** Three paths are maintained and tested as if they ship, two of them calling paid models; the battery and sweep certify a classifier production does not run, so a routing regression can hide behind a passing battery; CLAUDE.md ("Heuristic SymPy + web-search inject still run") calls the dead branch live.
- **Fix:** Decide per switch and record it in `core/settings/` with a date: delete `augment.py:63-157`, its three helpers and the 53 test sites (the flag stays only as the loop's kill switch); delete the classifier with its settings and harness override, or default it to `False` so dev, tests and production agree; once reminder cards ship, delete the todo-sync job, its registration, its CLAUDE.md job entry and the mock.
- **Verify:** `grep -rn "mcp_tool_loop_enabled=False" apps/api/app/tests | wc -l` → 0 (or only the loop's kill-switch test); `uv run pytest`, `./scripts/dev.sh battery`, `test_battery.py` and `test_sweep.py` pass with the harness on production settings.
- **Source:** raw/agent-dead.md DEAD-02

<a id="dead-03"></a>

#### DEAD-03 — 6.1 MB of vendor JS/CSS is embedded as TypeScript strings and statically imported into the JS bundle
- **Severity:** Medium · **Confidence:** High · **Effort:** M
- **Locations:** `apps/mobile/lib/vendor/` (`mermaidMinJs.ts`, `pdfWorkerMinJs.ts`, `pdfMinJs.ts`, `vegaMinJs.ts`, `vegaLiteMinJs.ts`, `vegaEmbedMinJs.ts`, `katexCss.ts`, `smilesDrawerMinJs.ts`), imported at `apps/mobile/components/rich/MermaidBlock.tsx:25`, `apps/mobile/lib/pdfPreviewHtml.ts:4-5`, `apps/mobile/lib/chartPreviewHtml.ts:13-15`, `apps/mobile/lib/printDocument.ts:6` (print only, via `apps/mobile/features/chat/model/exportMessagePdf.ts:4`), `apps/mobile/lib/chemistry/smilesDrawerHtml.ts:7`
- **Evidence:** Each file is a top-level static import, so Metro puts it in the single bundle, Hermes keeps the strings in the bytecode mapped at start, and `expo-updates` re-downloads the whole bundle on every update (assets only when their hash changes). Lead check: Lead ran `ls -la apps/mobile/lib/vendor` (6.1 MB; `mermaidMinJs.ts` 3,406,171 bytes, `pdfWorkerMinJs.ts` 1,108,931) and found the static imports (`components/rich/MermaidBlock.tsx:25`, `lib/chartPreviewHtml.ts:13-15`, `lib/pdfPreviewHtml.ts:4-5`, `lib/chemistry/smilesDrawerHtml.ts:7`, `lib/printDocument.ts:6`); the likely reason for inlining is that the sandboxed WebView must work offline, a constraint the fix keeps.
- **Impact:** Install size and every OTA update carry 6.1 MB used only by Mermaid, Vega, PDF preview, SMILES and print, including 369 KB of KaTeX CSS and fonts for the rare PDF export; likely the largest single block in the bundle (its exact share needs a build).
- **Fix:** Ship each file as a local asset instead of a string module (under `assets/vendor/`, registered in `metro.config.js` `assetExts`, loaded on first render with `expo-asset` + `expo-file-system` or referenced by file URI), keeping the pinned versions and hashes in `lib/vendor/manifest.json` and `scripts/vendor-cdn.mjs` as the generator; the files stay on the device and feed the same sandboxed WebView, so offline rendering needs no CDN. Load `katexCss` only in the print path.
- **Verify:** `npx expo export --platform ios --dump-sourcemap` + `npx source-map-explorer` before and after (expect ≈6 MB smaller); Mermaid, chart, PDF preview, SMILES and PDF export still render in a dev build, offline included (`docs/QA_MATRIX.md` rows).
- **Source:** raw/agent-dead.md DEAD-10

<a id="dead-04"></a>

#### DEAD-04 — `response_style` is vestigial (column, API field, phone type, and a constant through seven functions)
- **Severity:** Low · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/models/orm/user.py:52`, `apps/api/app/models/schemas/auth.py:28`, `:103`, `apps/api/app/models/schemas/common.py:23`, `apps/api/app/modules/account/api.py:377-381`, `apps/api/app/modules/account/export.py:69`, `apps/api/app/modules/chat/prompt_sections.py:124-126`, `apps/mobile/lib/api/types.ts:29`, `apps/mobile/lib/cachedUser.ts:55`, `apps/api/app/modules/chat/turn_prep/augment.py:68-69`, `apps/api/app/modules/math/tools/lesson.py:106-109`, `apps/api/app/modules/math/tools/direct.py:497-499`, and 15 more (see raw/agent-dead.md DEAD-03)
- **Evidence:** #1873 (2026-10-18) kept the column and field "for older clients" in a pre-launch app, chat ignores the value, and the only production producer passes the literal `"balanced"`, so the `"short"`/`"detailed"` branches cannot run. Lead check: cited code read at the listed lines.
- **Impact:** Readers of the maths direct-reply path reason about three lengths that cannot occur, and the API still stores a value nothing reads that export, deletion and migrations must carry.
- **Fix:** Drop the parameter from `SubjectAdapter.direct_reply` and the seven functions, delete the unreachable branches and the API and phone fields, update the golden prompts (`apps/api/app/tests/modules/chat/golden/prompt_messages.json`), then contract the column in a later release.
- **Verify:** `grep -rn "response_style"` over API and phone sources (tests excluded) finds only the ORM column until the contract migration, and maths/chat pytest plus `pnpm typecheck` pass.
- **Source:** raw/agent-dead.md DEAD-03

<a id="dead-05"></a>

#### DEAD-05 — Leftover migration aliases (`services/model_catalog.py` re-exports 20 names; `MathServiceError` on 237 lines)
- **Severity:** Low · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/services/model_catalog.py:1-55`, `:57-61`, `apps/api/app/services/solving.py:133-136`, `apps/api/app/modules/math/solve/__init__.py:77`, `:82`, `apps/api/app/modules/physics/solver.py:1`, `:39-66`, `apps/api/app/modules/physics/block.py:23`, `apps/api/app/modules/physics/answer_checks.py:13`, `apps/api/app/modules/chat/turn_settle.py:29`, `apps/api/app/routers/models.py:8`, `docs/ARCHITECTURE.md:47`, and 7 more (see raw/agent-dead.md DEAD-05)
- **Evidence:** The catalog facade re-exports 20 names around `is_available` (10 production files import through it, 12 directly), the `MathServiceError` alias is still the spelling on 237 production lines in 33 files, and `physics/solver.py`'s `__all__` lists 26 names (three private) of which production imports two. Lead check: cited code read at the listed lines.
- **Impact:** ARCHITECTURE.md says the migration re-exports were deleted, yet new code still picks between two import paths and two exception names, and CLAUDE.md names the wrong catalog owner.
- **Fix:** Move `is_available` beside `model_health` and point imports at `app.models.model_catalog`, rename `MathServiceError` to `SolveServiceError` in the 33 files and delete the alias, trim `physics/solver.py`'s `__all__` to what callers use, and fix CLAUDE.md.
- **Verify:** `grep -rn "MathServiceError" apps/api/app` is empty and `uv run mypy` and `uv run pytest` pass.
- **Source:** raw/agent-dead.md DEAD-05

<a id="dead-06"></a>

#### DEAD-06 — Shims that outlived their data (legacy refresh-record formats; the topic job's no-user path)
- **Severity:** Low · **Confidence:** Medium · **Effort:** S
- **Locations:** `apps/api/app/modules/account/tokens.py:62-63`, `:66-85`, `:125-142`, `:250-285`, `:373`, `apps/api/app/core/settings/auth.py:22`, `apps/api/app/services/topic.py:25-32`, `:45-46`, `apps/api/app/background/handlers.py:128-129`, `apps/api/app/modules/chat/post_turn.py:166`, `apps/api/app/modules/chat/service.py:231-235`, `apps/api/app/modules/speech/live_talk.py:420-423`
- **Evidence:** Every refresh record written since 2026-09-11 (`0c9f0fedd`) carries `session_id` and expires in 30 days, so no legacy record can exist after about 2026-10-11 (given a prompt deploy and no restore from an older Redis snapshot), and all three topic enqueuers send `user_id`, so only a two-month-old DLQ replay reaches the unscoped title update. Lead check: cited code read at the listed lines.
- **Impact:** Security-adjacent branches (auth-session parsing, an unscoped write) that no live data can reach still need review and tests.
- **Fix:** Delete `_legacy_session_id` and `parse_refresh_record`'s two legacy branches (a record without `session_id` is invalid, so the user signs in again), require `user_id` in the topic payload and drop the unscoped branch, and give future shims a removal date.
- **Verify:** `grep -rn "_legacy_session_id\|older in-flight" apps/api/app --include=*.py | grep -v tests` is empty and `uv run pytest app/tests/modules/account app/tests/test_jobs.py` passes with the legacy-format cases dropped.
- **Source:** raw/agent-dead.md DEAD-06 (its legacy spend-key part is reported under NET-04)

<a id="dead-07"></a>

#### DEAD-07 — Phone dead branches: pre-launch SecureStore migrations, constant gates, test-only code in production modules
- **Severity:** Low · **Confidence:** High · **Effort:** S
- **Locations:** `apps/mobile/lib/auth.ts:89-100`, `apps/mobile/lib/filePrefs.ts:53-67`, `apps/mobile/features/todos/screens/TodosScreen.tsx:214-217`, `apps/api/app/modules/speech/schemas.py:42-50`, `apps/mobile/lib/expoRuntime.ts:52-58`, `apps/mobile/lib/speech/voiceAudio.ts:27-30`, `apps/mobile/features/chat/model/foregroundRefetch.ts:24-27`, `apps/mobile/features/chat/hooks/useChatRouteLoader.ts:443-459`, `apps/api/app/core/sympy_executor.py:373-417`, `apps/api/app/modules/chat/finalize_registry.py:183-190`, `apps/mobile/lib/physics/circuit.ts:477-486`, `apps/mobile/lib/physics/simulation/index.ts:14-78`, and 43 more (see raw/agent-dead.md DEAD-07, DEAD-08, DEAD-09)
- **Evidence:** Pre-launch (`docs/PRODUCTION.md:327-334`, `app.json` `1.0.0`), the SecureStore/Keychain migrations, the always-false `refunded` field and the `focus=list` redirect serve only developer and internal installs, two gates return constants (`canUseVoiceInput()` `true`, `shouldSilentRefetchChatOnFocus()` `false`), and 5 API helpers, 14 phone functions and 43 barrel entries have only test importers. Lead check: cited code read at the listed lines.
- **Impact:** Store installs re-read the Keychain on every cold start until a setting changes, readers must work out that two guards never fire (one in the 533-line chat route loader), and an API test double sits in `core/`.
- **Fix:** Before the first store build delete the legacy reads, `refunded` and the redirect, inline the two constant gates (dropping the dead focus effect and `skipNextFocusRef`), and move test-only code (`ThreadSympyExecutor`, `circuitLabelBoxes`, test-only barrel entries) into the tests.
- **Verify:** `grep` finds no `LEGACY_`, `canUseVoiceInput`, `shouldSilentRefetchChatOnFocus` or `skipNextFocusRef`, `pyreach.py` and `tsexports.py` report no test-only rows beyond agreed reset hooks, and `pnpm test`, `pnpm typecheck` and `uv run pytest` pass.
- **Source:** raw/agent-dead.md DEAD-07, DEAD-08, DEAD-09

<a id="dead-08"></a>

#### DEAD-08 — `react-native-render-html` and the expo-dom path run only when the WebView is missing, never in a store build
- **Severity:** Low · **Confidence:** Medium · **Effort:** S
- **Locations:** `apps/mobile/lib/webView.ts:21-33`, `:36-65`, `apps/mobile/package.json`, `apps/mobile/components/HtmlPreviewModal.tsx:18`, `:244-277`, `:319-321`, `:354-366`, `apps/mobile/lib/htmlForInlinePreview.ts:149`
- **Evidence:** `react-native-webview` is a direct dependency, so every dev and store build links it, while `StaticHtmlPreview` (the only `react-native-render-html` importer, fed by the 163-line `htmlForInlinePreview.ts`) renders only when the preview mode is not `rnc`, which in practice means Expo Go. Lead check: cited code read at the listed lines.
- **Impact:** Every store build carries an unreachable HTML-to-native renderer (`react-native-render-html@6.3.4`, 708 KB of `src`) and its CSS engine, the only consumer of old transitive packages (`ramda@0.27`, `urijs`, …) that Dependabot and the license generator must track.
- **Fix:** Drop `StaticHtmlPreview`, `lib/htmlForInlinePreview.ts` (and its tests) and the dependency, showing the existing "Open in browser" path if the WebView is ever missing, or move the fallback and the `expo-dom` branch behind `__DEV__`/`isExpoGo()` in a file Metro resolves only in development.
- **Verify:** `grep -rn "react-native-render-html" apps/mobile --include=*.ts --include=*.tsx | grep -v node_modules` is empty, `pnpm test` passes, and an `npx expo export --dump-sourcemap` + `source-map-explorer` diff shows the bytes gone.
- **Source:** raw/agent-dead.md DEAD-11

<a id="dead-09"></a>

#### DEAD-09 — Android embeds eight font families and `useFonts` bundles them again
- **Severity:** Low · **Confidence:** Medium · **Effort:** S
- **Locations:** `apps/mobile/app.json:119-175`, `apps/mobile/app/_layout.tsx:100-114`, `apps/mobile/components/rich/skia/SkiaNumberLineChart.tsx:73`, `apps/mobile/components/rich/skia/SkiaInequalityGraphChart.tsx:47`, `apps/mobile/components/rich/skia/SkiaGraphExplorer.tsx:99`, `apps/mobile/components/rich/simulation/useSimulationScene.ts:48`, `:51`, `:52`, `apps/mobile/components/rich/TrajectoryChart.tsx:43`, `apps/mobile/components/rich/skia/SkiaMoleculeCanvas.tsx:52`, `apps/mobile/assets/fonts/KaTeX_Main-Regular.ttf` (and `KaTeX_Math-Italic.ttf`, `KaTeX_AMS-Regular.ttf`)
- **Evidence:** The `expo-font` plugin embeds 8 families on Android only (1,765,284 bytes, added 2026-10-01 in `de72edfda` to fix weight lookup), `useFonts` still loads the same families from Metro assets on both platforms (2,395,852 bytes), and the KaTeX files Skia reads from `assets/fonts/` are byte-identical (`cmp`) to katex's own. Lead check: cited code read at the listed lines.
- **Impact:** Roughly 1.8 MB of duplicate fonts in every Android download (iOS also bundles KaTeX_Main and Math-Italic twice), and the runtime re-registration can mask whether the native embedding, the actual weight fix, works.
- **Fix:** Embed on both platforms through the plugin (`ios.fonts` beside `android.fonts`), delete the runtime `useFonts` entries for the embedded families, and point `_layout` and Skia at one path per face (`assets/fonts/`).
- **Verify:** Compare `unzip -l` font entries of an Android release build (`eas build -p android --profile preview` or `expo export:embed`) before and after, and QA the Android weight and math rows in `docs/QA_MATRIX.md`.
- **Source:** raw/agent-dead.md DEAD-12

<a id="dead-10"></a>

#### DEAD-10 — The Expo web target is still wired in, and `react-dom` 19.2.3 no longer matches `react` 19.3.0
- **Severity:** Low · **Confidence:** High · **Effort:** S
- **Locations:** `apps/mobile/package.json`, `apps/mobile/app/+html.tsx`, `apps/mobile/app.json:57-61`, `apps/mobile/assets/images/favicon.png`, `apps/mobile/components/PushNotificationBootstrap.tsx:39`, `apps/mobile/features/todos/model/todoReminders.ts:35`, `apps/mobile/lib/pushNotifications.ts:25`, `:31`, `:128`, `:162`, `apps/mobile/lib/productAnalytics.ts:8`, `apps/mobile/lib/purchases.ts:55`
- **Evidence:** `react` went to 19.3.0 on 2026-10-11 (`c3eb1ca2e`) while `react-dom` stayed pinned at 19.2.3, and React needs the two to match exactly, so the web target (run by nothing in `CLAUDE.md`, `docs` or `scripts`; the web client is `apps/web`) cannot have started since. Lead check: Lead read `apps/mobile/package.json`.
- **Impact:** A dependency pair that already drifted unnoticed, a web-only route file and branches for a platform the phone app does not target, which also mislead readers about where the web client lives.
- **Fix:** After confirming with the team, remove the `web` script, `react-dom`, `react-native-web`, `app/+html.tsx`, the `web` block and `favicon.png`, and the `Platform.OS === "web"` branches.
- **Verify:** `pnpm install && pnpm typecheck && pnpm test && pnpm lint` pass, `npx expo-doctor` is clean, and `grep -rn "Platform.OS === \"web\"" apps/mobile/{components,features,lib}` is empty.
- **Source:** raw/agent-dead.md DEAD-14

<a id="dead-11"></a>

#### DEAD-11 — Orphaned constant from the audited head and 41 exports used only in their own file
- **Severity:** Low · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/services/workout.py:310-315`, `:324`, `apps/api/app/modules/physics/reply_policy.py:3`, `apps/mobile/lib/math/draftText.ts:79`, `:110`, `apps/mobile/lib/physics/diagramKind.ts:6`, `apps/mobile/lib/scanner/readBack.ts:5`, `apps/mobile/lib/stackHeader.ts:8`, `apps/mobile/lib/physics/circuit.ts:206-219`, `apps/mobile/lib/chemistry/scene.ts:7-45`, `apps/mobile/lib/math/arithmeticBlock.ts:3-83`, `apps/mobile/lib/physics/rayScene.ts:61-71`
- **Evidence:** `WORKOUT_PROMPT_SHORT`'s last reader (`reply_policy.py:3`) switched to `PHYSICS_WORKOUT_PROMPT_SHORT` in #1920 (`d2ec42b0`, the audited head), and each of the 41 knip names (5 values, 36 types; full list in `raw/knip.txt`) occurs at least twice in its own file and in no other. Lead check: cited code read at the listed lines.
- **Impact:** Noise, and the stale prompt constant invites the next physics or maths edit to reuse the wrong rule.
- **Fix:** Delete `WORKOUT_PROMPT_SHORT` and reword the `:324` comment, drop `export` from the 41 names, and consider running knip in Mobile CI (exports and types only, `vendor/**` ignored).
- **Verify:** `npx knip --include exports,types` reports only the vendored `image-size` entries and `grep -rn WORKOUT_PROMPT_SHORT apps/api` is empty.
- **Source:** raw/agent-dead.md DEAD-13

### F. Scalability and reliability

<a id="scale-01"></a>

#### SCALE-01 — One chat message can stall a machine's event loop for minutes or hours (exponential regex in a physics reader; unbounded SymPy evaluation in a maths reader)
- **Severity:** Critical · **Confidence:** High · **Effort:** M (class fix), S (instance fixes)
- **Locations:** `apps/api/app/modules/physics/extractors/common.py:123-126,152,221`, `apps/api/app/modules/physics/prompt.py:62,76,102`, `apps/api/app/services/routing.py:401,405,436`, `apps/api/app/modules/physics/followup.py:128-134`, `apps/api/app/modules/physics/solvers/drag.py:4,26-52`, `apps/api/app/modules/math/tools/extractors/graph.py:194-195,202,242-243,342`, `apps/api/app/modules/math/tools/graph_followup.py:97-104`, `apps/api/app/modules/math/tools/extractors/calculus_applications.py:130-131`, `apps/api/app/modules/math/tools/prompt.py:238,265,294`, `apps/api/app/modules/chat/tool_loop/selection.py:154`, `apps/api/app/modules/math/tool.py:616`, `apps/api/app/modules/math/solve/parse.py:123-125,152-161,169,179-184`, and 2 more (see raw/agent-rel.md REL-01)
- **Evidence:** `_LABEL_GAP` (`(?:[\s,:=.]+|(?:of|is|are|...|to)\b)*`) is `(a+)*` under `fullmatch`. The graph reader parses with SymPy `evaluate=True` and calls `solve`, and the parse guard does not block power towers. Lead check: reproduced through the real functions in a subprocess with a timeout. Physics: `extract_physics_intent("What is the net force on a body of mass" + ","*n + "x 5 kg accelerating at 2 m/s^2?")` took 0.031 s at n=18, 0.116 s at n=20 and 0.473 s at n=22, doubling per comma. `needs_physics` returns True in 4 ms, so the turn takes this path. Maths: `extract_math_intent("graph 2y = 9^9^k + x")` took 0.18 s at k=6, 1.86 s at k=7 and **56.3 s at k=8**, then raised `ValueError` (int→str digit limit) instead of declining. Both are called synchronously inside async turn prep: `build_physics_augmentation` (`modules/physics/prompt.py`; only its symbolic step uses `run_sympy`), `build_math_augmentation` (`modules/math/tools/prompt.py:294`), `modules/chat/tool_loop/selection.py:154` and routing's `services/routing.py:390-410`. Regex: `common.py:123-126` (`_LABEL_GAP`), used at `:152` with `fullmatch`.
- **Impact:** one event loop serves every socket and request on the machine. While it spins, WebSocket and SSE streams freeze, and `/health` and `/health/ready` time out (Fly stops routing but does not restart the Machine). The `chatprep` refresh also stops, so other machines can start a second turn on the same chats. One user can repeat this on every machine.
- **Fix:** class fix at the reader seam: run the maths/physics/chemistry readers and the routing and follow-up `solve_physics` calls in the bounded, killable pool (`core/sympy_executor.run_sympy`, or a reader pool behind `BoundedSympyExecutor`). Use a short timeout that means "no verified answer". Instance fixes: make `_LABEL_GAP` linear (atomic group, or one character per iteration); bound `**`/`^` exponent chains on every path; precompute `_drag_identities_hold` at boot.
- **Verify:** unit tests that `_find_value_with_specific_unit("A body of mass" + ","*40 + "x 5 kg", "kg", ("mass",))` returns in < 50 ms and that `extract_math_intent("graph y = 9^9^9 + x")` returns within the reader timeout. Add a hypothesis test that feeds long punctuation runs to every reader regex, and a loop-lag alert (SCALE-15).
- **Source:** raw/agent-rel.md REL-01

<a id="scale-02"></a>

#### SCALE-02 — Five foreign-key columns have no index, so every message, chat or memory delete scans the referencing table; account and long-chat deletes will exceed the 120 s statement timeout
- **Severity:** Critical · **Confidence:** High (mechanism), Medium (threshold) · **Effort:** S
- **Locations:** FK columns: `apps/api/app/modules/memory/models.py:113-116` (`source_message_id`; `apps/api/alembic/versions/0087_memory_facts.py:127-134`), `apps/api/app/modules/memory/models.py:99-103` (`superseded_by_id`; `0087_memory_facts.py:119-126`), `apps/api/app/modules/memory/models.py:110-112` (`source_chat_id`; `0003_fk_cascades.py:30-38`), `apps/api/app/modules/todos/models.py:48-50` (`chat_id`; `0008_create_todo_items.py:27-29`), `apps/api/app/models/orm/attachments.py:46-48` (`message_chunks.chat_id`; its only index is `(user_id, chat_id)`, `:31`, `0064_message_chunks.py:48`). Deletes that fire the triggers once per deleted row: `apps/api/app/repositories/users.py:130-137`, `apps/api/app/modules/chat/service.py:139` → `apps/api/app/repositories/chats.py:256-270`, `apps/api/app/modules/chat/service.py:161`, `apps/api/app/modules/chat/turn_settle.py:167`, `apps/api/app/modules/chat/turn_intercepts.py:57`, `apps/api/app/modules/attachments/workflow.py:177`, `apps/api/app/modules/memory/writes_repository.py:173-174` → `apps/api/app/modules/memory/erase.py:53`, `apps/api/app/modules/memory/repository.py:59,142,160`
- **Evidence:** each `ON DELETE SET NULL/CASCADE` runs a query like `UPDATE ONLY memories SET source_message_id = NULL WHERE $1 = source_message_id` once per deleted row. Without an index, each run is a full scan of the referencing table. Account delete removes messages first:
  ```python
  await session.execute(delete(Message).where(Message.user_id == user_id))   # users.py:130: 1 memories seq scan per message
  await session.execute(delete(Memory).where(Memory.user_id == user_id))     # :131: 1 memories seq scan per fact (superseded_by_id)
  ...
  await session.execute(delete(Chat).where(Chat.user_id == user_id))          # :137: per chat: memories, todo_items and message_chunks scans
  ```
  Lead check: the live catalog of the local DB at the same migration head (0115) shows no leading index on `memories.source_chat_id`, `memories.source_message_id`, `memories.superseded_by_id`, `todo_items.chat_id` (all SET NULL) or `message_chunks.chat_id` (CASCADE). Every other FK is indexed. Migration 0115 (#1909, 2026-10-19) indexed `attachments.message_id` for exactly this reason ("serve a message delete (FK SET NULL)"). Postgres docs: a DELETE on the referenced table scans the referencing table for matching rows, so index the referencing column.
- **Impact:** a user with M messages, F facts and C chats costs (M + F + C) `memories` scans plus C scans each of `todo_items` and `message_chunks`. All of it runs in one statement bounded by `DB_COMMAND_TIMEOUT_SECONDS` = 120 (`apps/api/app/core/settings/infrastructure.py:25`). Estimates: at 300k users × ~50 facts (~15M `memories` rows) one scan takes seconds. A 2,000-message account or a 300-message chat delete is then cancelled (503, and the account stays). At 10k users (~100 ms per scan) such deletes already take minutes. Each regenerate also adds a scan to the finalize transaction that the chat's next turn waits on.
- **Fix:** one expand migration, with `CREATE INDEX CONCURRENTLY` inside `autocommit_block` as in `0115`. Add partial `IS NOT NULL` indexes on `memories.source_message_id`, `memories.superseded_by_id`, `memories.source_chat_id` and `todo_items.chat_id`, plus `ix_message_chunks_chat (chat_id)`, and declare them in the ORM `__table_args__`. Drop the redundant `ix_message_chunks_user` (SCALE-20) in the same pass. Add an architecture test that fails when a `ForeignKey` column has no index led by it.
- **Verify:** on a Neon branch with 1M `memories` rows, run `EXPLAIN (ANALYZE, BUFFERS) DELETE FROM chats WHERE id = :chat_with_300_messages`. It should show `Trigger for constraint fk_memories_source_message_id: calls=300` taking seconds before the fix and milliseconds after.
- **Source:** raw/agent-scale.md SCALE-01

<a id="scale-03"></a>

#### SCALE-03 — History compression effectively never runs on active chats: a fixed dedupe key plus the 24 h done marker suppresses every run after the first (a no-op on turn 1)
- **Severity:** High · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/modules/chat/post_turn.py:178-194`, `apps/api/app/core/jobs/dedupe.py:20-27,89-100`, `apps/api/app/core/jobs/worker.py:113-119,137-143`. Same class, smaller: `apps/api/app/background/handlers.py:217` (`memory_consolidate:{user_id}:lock{n}`), `apps/api/app/background/handlers.py:186-193` (the lesson_progress retry payload omits `assistant_message_id`), `apps/api/app/modules/attachments/jobs.py:21-23` with `apps/api/app/background/handlers.py:110-123` (a run skipped by `_unless_spend_capped` is marked done for 24 h), `apps/api/app/services/topic.py:61-74` with `apps/api/app/core/jobs/worker.py:142` (the worker's `done` overwrites the topic handler's self-release)
- **Evidence:** turn 1's compress run finds nothing to fold and returns normally. The worker then stores `jobdone:compress:<chat>=done` and acks every later entry for that chat as "Skipping already-processed job":
  ```python
  # dedupe.py:89-98
  async def _extend_dedupe(redis, dedupe_key):
      await redis.set(job_done_key(dedupe_key), _DEDUPE_DONE, ex=_JOB_DONE_TTL_SECONDS)   # 86_400
  ```
  Lead check: traced the path through these points:
  - `post_turn.py:178-194` (`f"compress:{chat_id}"`)
  - `core/jobs/worker.py` `_claim_entry` (SET NX fails on "done" → acked unrun)
  - `dedupe.py:89-100` (`_extend_dedupe`, 86,400 s after any normal return)
  - `core/settings/chat.py:27` (`history_compression_enabled = True`)
  - `services/context_window.py:131-139` (the design expects a run whenever the gap reaches 3)

  The post-turn job is the only trigger, and `tests/modules/chat/test_post_turn_jobs.py:75` pins the fixed key. `dedupe.unique_dedupe_key` (`dedupe.py:34-42`) exists, and its docstring names this failure.
- **Impact:** on any chat active within a day (nearly all of them), messages 21+ beyond the recent window and the 10-message gap are neither summarized nor sent. The model silently forgets mid-conversation context, which is the problem compression exists to solve. Fixing this exposes compaction's LLM call inside an open DB transaction (LEAK-01), so fix both together.
- **Fix:** in `post_turn._compress_job`, use `jobs.unique_dedupe_key(f"compress:{chat_id}")`. The per-chat `chatcompress:` lock (`modules/chat/compaction.py:32-35`) already serializes runs, and `should_run_compression` keeps extra runs cheap. Make the lock-retry stems unique and carry `assistant_message_id` in the lesson_progress retry payload. Let a handler say "not done" (e.g. `raise JobSkipped` → release the key and ack), use it in `_unless_spend_capped`, and drop the topic handler's self-release.
- **Verify:** a fakeredis worker test that enqueues `compress` for one chat twice, the first run a no-op, and asserts that the second handler call happens. In production, `History compression` runs per chat per day exceed 1 on long chats.
- **Source:** raw/agent-scale.md SCALE-02

<a id="scale-04"></a>

#### SCALE-04 — The model-health circuit breaker records the wrong model, counts mid-stream failures as success, measures whole-reply time as latency, and never half-opens
- **Severity:** High · **Confidence:** High · **Effort:** S–M
- **Locations:** `apps/api/app/modules/chat/stream_paths.py:239,269,289,308-317`, `apps/api/app/gateways/litellm_gateway.py:241-245,254-271`, `apps/api/app/services/model_health.py:17-18,50-86,99-109`. Consumers: `apps/api/app/services/routing.py:505-512`, `apps/api/app/modules/billing/plan.py:255-272`, `apps/api/app/modules/chat/turn_load.py:238-287`, `apps/api/app/modules/chat/turn_prep/context.py:259-277`
- **Evidence:** samples follow the alias that produced content (or the last failed one). So a primary that fails before its first token while a fallback answers is never recorded as failing, and a failure after the first token counts as success. `get_health` flags an alias at a 30 s latency p50 (`model_health.py:80`) over all 40 samples, whatever their age (`:53`). Unhealthy aliases leave Auto (`routing.py:512`) and the fallbacks (`plan.py:271`), so no new samples arrive and nothing half-opens. Lead check: read `modules/chat/stream_paths.py:262-320` (one sample per turn for `stream_meta["model_alias"] or requested_model`; `stream_ok = True` at the first token; latency = whole reply) and `gateways/litellm_gateway.py:236-272` (`model_alias` = the alias that produced content, or the last failed one).
- **Impact:** during a primary outage, every turn first waits for that model to fail (5 s connect, 30 s idle per chunk in production, 8 s first-content for reasoning aliases). The breaker never opens, so time to first token rises for that model's users for the whole incident. A healthy but slow-writing model can drop out of Auto for a day with no alert. Samples are shared in Redis, so both effects are fleet-wide.
- **Fix:** at `services/model_health.py` + `gateways/litellm_gateway.py`, record one sample per attempted alias inside `stream_chat_completion`, including a failure on a mid-stream break. Measure time to first content, and window samples by time. Add a half-open probe: one turn per interval to an unhealthy alias, or decay after T minutes.
- **Verify:** `stream_chat_completion` tests:
  - a failing primary with a working fallback records a failure for the primary;
  - a 60 s healthy stream stays healthy;
  - an alias with only old failures becomes routable after the window.
- **Source:** raw/agent-rel.md REL-04

<a id="scale-05"></a>

#### SCALE-05 — A chat turn reads every attached document whole and at once; no per-turn byte budget and no daily cap on document uploads
- **Severity:** High · **Confidence:** Medium · **Effort:** S–M
- **Locations:** `apps/api/app/models/schemas/chats.py:124`, `apps/api/app/core/attachment_limits.py:3`, `apps/api/app/modules/chat/turn_prep/attachments.py:222-253,270-288`, `apps/api/app/modules/attachments/content.py:373-377`, `apps/api/app/gateways/storage_gateway.py:261-266`, `apps/api/app/modules/attachments/upload.py:72-78`, `apps/api/app/modules/attachments/reuse.py:14-54`
- **Evidence:** a message carries up to 10 attachments of 10 MiB each. All unverified uploads are read concurrently into `bytes_by_key`, and every row is formatted in one `asyncio.gather`, each object read whole and then parsed. Ten 10 MiB PDFs therefore hold ≥100 MiB of raw bytes plus up to five pypdf/python-docx object trees at once. Documents take no daily slot, and a Library file can be re-attached to every message. PRODUCTION.md puts the machine at 550–850 MB before any request. Lead check: read `modules/chat/turn_prep/attachments.py:218-255` (`asyncio.gather` of `verify_uploaded_bytes`, bytes kept in `bytes_by_key`) and `modules/attachments/upload.py:72-78` (only image types reserve a daily slot). The image path is already bounded (`modules/attachments/vision_input.py`).
- **Impact:** one ten-document turn approaches the headroom, and several open chats or a few users attaching large files at once exceed it. The kernel then kills the API process (or a SymPy worker). Every in-flight turn on the machine is lost, and its `chatprep` locks block those chats for 30 s. Only the 30-messages-a-minute limit bounds repeats.
- **Fix:** in `modules/chat/turn_prep/attachments.py`:
  - process documents sequentially (or 1–2 at a time) under a per-turn byte budget, like the vision one (`attachment_vision_max_turn_bytes` 20 MB, one photo at a time);
  - drop each file's bytes once its excerpt is taken;
  - read only what `PDF_EXTRACT_MAX_PAGES`/`MAX_EXTRACT_CHARS` need (ranged GET, or a size check first);
  - add a daily document-upload allowance (`services/quota/counters.COUNTERS`).
- **Verify:** a fake-gateway test that ten 10 MiB documents never hold more than the budget at once, and a load test measuring RSS for a 10 × 10 MiB PDF turn.
- **Source:** raw/agent-rel.md REL-05

<a id="scale-06"></a>

#### SCALE-06 — The job-stream soft trim drops jobs that were never delivered when no consumer is reading; no backlog metric; level-based DLQ alert
- **Severity:** Medium · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/core/jobs/queue.py:18-19,79-104,107-128`, `apps/api/app/core/settings/worker.py:15`, `apps/api/app/core/jobs/admin.py:17,23,67-101`, `apps/api/app/core/jobs/worker.py:357-360`, `apps/api/app/core/jobs/__init__.py:5`, `docs/PRODUCTION.md:520`, `docs/SCALING.md:30`
- **Evidence:** undelivered entries sit at the newest end of the stream, so the `MINID` path is safe but the fallback is not:
  ```python
  # queue.py:123-126
  if min_id:
      await redis.xtrim(JOBS_STREAM, minid=min_id, approximate=True)
  else:
      await redis.xtrim(JOBS_STREAM, maxlen=_MAXLEN, approximate=True)   # drops undelivered jobs too
  ```
  With no consumer reading (e.g. the group is scaled to 0, or a release is crash-looping), every API enqueue silently cuts the backlog to ~10k, oldest first. With consumers up, the 50,000 hard cap on every XADD does the same. Metrics read only the DLQ's `XLEN` and `XPENDING`, and only inside the worker loop. The PEL alert (≥ 50) cannot see a backlog, since a worker's PEL holds at most 8 running + 200 waiting entries. The DLQ (5,000 cap, trimmed by length) warns at depth ≥ 20 every 300 s, from every worker. Lead check: read `core/jobs/queue.py:107-128` (MINID from XPENDING; with nothing pending → `XTRIM MAXLEN ~ 10_000`).
- **Impact:** at 100k DAU (up to 6 post-turn jobs per turn), a 5-minute worker outage silently drops most of that window's memory extraction, indexing and welcome/receipt emails. Meanwhile the docs say jobs survive restarts. A single provider blip that puts 20 jobs in the DLQ makes every worker warn every 5 minutes forever, which is the alert most likely to be muted.
- **Fix:** in `core/jobs/queue.py` and `core/jobs/admin.py`:
  - trim `MINID` at min(oldest pending, `last-delivered-id` + 1) and drop the `MAXLEN 10_000` fallback;
  - count what the hard cap drops;
  - report backlog (`XINFO GROUPS` lag) and the oldest undelivered entry's age from the API too;
  - make the DLQ alert rate-based and age-trim DLQ entries (e.g. 7 days).

  Do this before SCALING.md item 2 moves the trim onto a timer, and correct the PRODUCTION.md/SCALING.md wording.
- **Verify:** a fakeredis test that enqueues 15,000 jobs with no consumer and asserts all stay deliverable (today ~10k remain). With 30k undelivered entries, `collect_queue_metrics` reports `backlog=30000`.
- **Source:** raw/agent-scale.md SCALE-08

<a id="scale-07"></a>

#### SCALE-07 — Transient provider failures become permanent loss: retries all within ~6 s, DLQ capped and replayed by hand, chat-history indexing stores failed embeddings as indexed
- **Severity:** Medium · **Confidence:** High · **Effort:** M
- **Locations:** `apps/api/app/core/jobs/worker.py:43-44,131-173`, `apps/api/app/core/jobs/admin.py:17,45-50`, `scripts/replay_dlq.py`, `docs/ROLLBACK.md` ("Worker and job recovery"), `apps/api/app/modules/attachments/rag.py:235-251`, `apps/api/app/background/handlers.py:224-231,241-264,277-295`, `apps/api/app/modules/chat/history_rag.py:57-69`, `apps/api/app/gateways/embedding_gateway.py:97-115`, `apps/api/app/repositories/message_chunks.py:32-45,58-70,85`
- **Evidence:** a job gets three attempts with in-process sleeps of 2 s and 4 s, then goes to the DLQ (`MAXLEN ~ 5000`, newest kept, replayed by hand). A 30 s embedding or e-mail outage therefore dead-letters every job that started in it. Memory (cursor kept on `model_failed`, `modules/memory/extraction_workflow.py:334-346`) and titles (backfilled on chat open, `modules/chat/service.py:221-240`) self-heal; `attachment_index`, `transactional_email`, `storage_sweep` and `todos` do not. When embeds fail, chat-history indexing writes chunks with `None` vectors and counts them as indexed, but search skips them (`embedding IS NOT NULL`), and there is no retry or DLQ. The attachment indexer guards against exactly this ("storing all-null chunks creates dead rows"). Lead check: read `core/jobs/worker.py:43` (3 attempts, 2 s × n backoff), `modules/chat/history_rag.py:55-70` (writes `None` vectors) and `repositories/message_chunks.py:32-45` (`indexed_message_ids` counts any row).
- **Impact:**
  - Documents uploaded during an outage stay unsearchable for good.
  - Turns indexed during an embedding outage leave permanent, invisible holes in chat-history recall.
  - Welcome and receipt e-mails and account-delete storage sweeps are lost unless someone replays the DLQ, which may already have trimmed them (a 15-minute outage at 100k DAU produces tens of thousands of entries).
- **Fix:**
  - Use delayed retries with exponential backoff and jitter, outside the worker slot: re-enqueue with `attempt+1` and a `not_before` via a Redis sorted set, for up to ~1 h, then DLQ.
  - In `modules/chat/history_rag.py`, store only embedded chunks, raise when none embedded, and count only `embedding IS NOT NULL` rows as indexed.
  - Add an automatic, rate-limited DLQ replay for safe types (`storage_sweep`, `attachment_index`, `transactional_email`) once the dependency is healthy.

  Seam: `core/jobs/worker.py`, `core/jobs/queue.py`.
- **Verify:** a handler that fails for 60 s of fake time and then succeeds finishes without reaching the DLQ. A None embed writes no chunk row, and a second index run embeds the message.
- **Source:** raw/agent-scale.md SCALE-09

<a id="scale-08"></a>

#### SCALE-08 — Per-minute reminder scans walk every open dated to-do (no index leads with `due_at`), and the token lookup `IN (…)` has a parameter cliff
- **Severity:** Medium · **Confidence:** High (scan), Medium (cliff) · **Effort:** S
- **Locations:** `apps/api/app/modules/notifications/push.py:211-224,246-261,265`, `apps/api/app/repositories/push_tokens.py:151-156`, `apps/api/app/modules/notifications/reminder_email.py:52-65`, `apps/api/app/core/settings/notifications.py:14,16`, `apps/api/alembic/versions/0021_perf_indexes.py:21-23`, `apps/api/app/modules/todos/models.py:31-36`, `apps/api/app/background/push_scheduler.py:24`, `apps/api/app/background/email_reminder_scheduler.py:23`
- **Evidence:**
  ```python
  # push.py:246-259: no user_id, so the (user_id, due_at) partial index cannot seek
  select(TodoItem, User).join(User, User.id == TodoItem.user_id).where(
      TodoItem.checked.is_(False), TodoItem.due_at.isnot(None),
      TodoItem.notification_sent_at.is_(None),
      User.push_notifications_enabled.is_(True), User.push_reminders_enabled.is_(True),
      TodoItem.due_at >= overdue_cutoff, TodoItem.due_at <= window_end)   # [now-48h, now+60m]
  ```
  The aged-unsent count and the email scheduler repeat a cross-user scan every minute. The candidate set rarely shrinks. Push is on by default (`apps/api/app/models/orm/user.py:79-85`), and a user without a device token is skipped without being marked (`push.py:283-292`: "everyone who denied the OS permission lands here every minute for 48h"). Also, `.is_(False)` renders `checked IS false` against the `checked = false` predicate, which PG 16 may not treat as equivalent (confirm with EXPLAIN). Lead check: `pg_indexes` has only the partial `ix_todo_user_open_due (user_id, due_at)`; read `modules/notifications/push.py:246-265` and `repositories/push_tokens.py:151-156`. Downgraded from High: the partial index already bounds the walk to open dated rows.
- **Impact:** three cross-user walks a minute (two push, one email). Their cost grows with every user's open dated to-dos, not with the reminders actually due, on Neon's small compute, which then never scales to zero. The cliff: asyncpg refuses more than 32,767 bind parameters. Once more than ~32k distinct users have an unsent reminder in the 49-hour window (tokenless users count), `list_for_users` raises. The cycle logs "push cycle failed" (`apps/api/app/background/periodic.py:97-98`), and no one gets a reminder until the window drains.
- **Fix:**
  - Add a CONCURRENTLY expand migration with `ix_todo_push_due ON todo_items (due_at) WHERE checked = false AND notification_sent_at IS NULL AND due_at IS NOT NULL`, plus an email twin (`email_sent_at IS NULL AND recurrence_rule IS NULL`).
  - Write `TodoItem.checked == False` so the predicate matches.
  - Keyset-page the candidates (`ORDER BY due_at, id LIMIT 500`).
  - Chunk the token lookup (or use `= ANY(:ids)`).
  - Leave tokenless and quiet-hours rows out in SQL.

  Seam: `modules/notifications/push.py`, `reminder_email.py`.
- **Verify:** `EXPLAIN (ANALYZE, BUFFERS)` of the push query on a branch with ~10M `todo_items`, before and after (after: Index Scan on `ix_todo_push_due`). Add a unit test that `process_todo_reminders` handles 40,000 distinct due users without raising.
- **Source:** raw/agent-scale.md SCALE-04

<a id="scale-09"></a>

#### SCALE-09 — Push and email reminder cycles are unbounded but use the bounded-cycle lock TTL (600 s, never refreshed); rows are marked sent only after the whole batch, so reminders can go out twice
- **Severity:** Medium · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/background/periodic.py:65-67,79-100`, `apps/api/app/background/push_scheduler.py:25,28,37-51`, `apps/api/app/background/email_reminder_scheduler.py:24,32`, `apps/api/app/gateways/expo_push_gateway.py:18,59,163-164`, `apps/api/app/modules/notifications/push.py:100-104,384`, `apps/api/app/modules/notifications/reminder_email.py:92-107`
- **Evidence:** the push cycle runs in this order, and only the last step marks rows:
  1. polls receipts for every ready ticket (`ZRANGEBYSCORE` with no LIMIT, 100 per request, 15 s each);
  2. scans (SCALE-08);
  3. sends sequential 100-message chunks (15 s timeout each);
  4. marks rows.

  `CycleLock.refresh` exists and billing uses it (`apps/api/app/background/billing_reconcile_scheduler.py:66`), but the push cycle never calls it. A cycle over 600 s loses the lock to a peer that resends the still-unmarked to-dos. Examples: 40 slow chunks, or 20k unpolled receipt tickets after an Expo receipts outage (200 requests × up to 15 s). A worker stopped mid-dispatch (every deploy) also leaves accepted chunks unmarked. Lead check: read `background/periodic.py:65-76` (`lock_ttl_hold_across_ticks` = max(interval × 10, 300), docstring "Bounded cycles"), `background/push_scheduler.py:24-25`, `background/email_reminder_scheduler.py:24` and `modules/notifications/push.py:350-370` (one commit after all sends).
- **Impact:** duplicate reminder pushes (and duplicate emails for opted-in users) reach many users at once. This happens exactly when Expo is degraded, or when a peak minute (9:00 in a large time zone) makes a big batch. Receipt polling only prunes tokens, yet it delays every reminder behind it.
- **Fix:**
  - Bound the cycle (page candidates as in SCALE-08, at most N messages).
  - Call `lock.refresh()` between chunks and stop when it returns False (the billing pattern).
  - Mark each chunk's to-dos right after Expo accepts it. Better, claim rows before sending (`UPDATE … SET push_claimed_at = now() WHERE id = ANY(:ids) AND notification_sent_at IS NULL RETURNING id`).
  - Move receipt polling to its own loop with `ZRANGEBYSCORE … LIMIT 0 1000`.

  The email cycle already marks per send; add the refresh and the claim.
- **Verify:** a test with two scheduler instances and a fake Expo gateway that sleeps past a shortened lock TTL: each to-do is sent once. Metric: `Push cycle sent` lines (or Expo tickets) per to-do id stay at 1.
- **Source:** raw/agent-scale.md SCALE-05

<a id="scale-10"></a>

#### SCALE-10 — Global HNSW indexes serve user-filtered RAG queries: post-filtering returns nothing, or the planner exact-scans the user's history
- **Severity:** Medium · **Confidence:** Medium · **Effort:** M
- **Locations:** `apps/api/alembic/versions/0064_message_chunks.py:47,51-52`, `apps/api/alembic/versions/0047_attachment_chunks.py:46,57-58`, `apps/api/app/repositories/message_chunks.py:16-22,25-29,74-106,109-125,128-140`, `apps/api/app/modules/chat/prompt_builder.py:259-278`, `apps/api/app/modules/attachments/chunks_repository.py:109-142`, `apps/api/app/modules/chat/prompt_context.py:164-173`, `apps/api/app/modules/memory/erase.py:57-72`, `apps/api/app/modules/chat/history_rag.py:123,141`
- **Evidence:** pgvector applies `WHERE` after the HNSW scan, which returns `ef_search` (default 40) candidates from the whole table. With 100k users, an HNSW plan returns 0–2 rows and `retrieve_for_prompt` quietly returns `""` (`apps/api/app/modules/chat/history_rag.py:250-251`). A `user_id` btree plan instead compares every 6 KB vector the user has ever produced (never pruned) before the first token. No `hnsw.ef_search`/`hnsw.iterative_scan` setting exists. `delete_near`, `delete_mentioning_all` and a full `COUNT(*)` on every `message_index` job (where `has_chunks_for_user` would do) are O(user history) by design. Lead check: three HNSW indexes in `pg_indexes` (memories, attachment_chunks, message_chunks). Local pgvector is 0.6.0 (no iterative scan); the production version is unknown. Coverage of `repositories/message_chunks.py` is 49% and of `modules/attachments/chunks_repository.py` 63% (full-suite run).
- **Impact:** at 100k+ users, chat-history recall and document Q&A either silently find nothing, or put a per-user scan that grows with history on the turn's critical path. The HNSW insert cost is paid either way. Forget/mute on a long-time account reads every vector of the user while holding the `users` row lock (`apps/api/app/modules/memory/writes_repository.py:51-55`).
- **Fix:** at the repository seam, choose one:
  - (a) restrict candidates first (last N days, or the newest K chunks via a `MATERIALIZED` CTE on `(user_id, created_at)`), order them by distance, and drop the global HNSW indexes;
  - (b) make HNSW user-aware: `SET LOCAL hnsw.iterative_scan = relaxed_order` plus `hnsw.max_scan_tuples` (pgvector ≥ 0.8), or hash-partition `message_chunks` by `user_id`.

  Either way, replace `count_for_user` with `has_chunks_for_user` and bound `delete_near` the same way.
- **Verify:** on a branch with 10M `message_chunks` across 100k users, run `EXPLAIN (ANALYZE, BUFFERS)` on the RAG query for a light and a heavy user: rows come back and `Buffers` stays bounded. Add a regression test where two users' vectors interleave and top-k returns only the asking user's rows.
- **Source:** raw/agent-scale.md SCALE-06

<a id="scale-11"></a>

#### SCALE-11 — `message_chunks` and `product_events` grow without retention or rollup
- **Severity:** Medium · **Confidence:** High · **Effort:** M
- **Locations:** `apps/api/app/modules/chat/history_rag.py:105-148`, `apps/api/app/core/settings/chat.py:13-15`, `apps/api/app/repositories/message_chunks.py:57,109-145`, `apps/api/app/modules/analytics/api.py:13-20`, `apps/api/app/modules/analytics/service.py:79-97`, `apps/mobile/features/chat/model/latency.ts:76-77`, `apps/mobile/features/chat/model/turnOutcome.ts:78`, `apps/mobile/features/chat/model/latencyReporter.ts:34-65`, `apps/api/app/models/orm/usage.py:40-43`
- **Evidence:** each turn indexes the user line and the reply, up to `chat_history_rag_max_chunks_per_message` = 6 chunks each. Chunks are deleted only per message, per user, per forgotten fact or on "clear all". The phone sends `chat_ttft` and `chat_turn_outcome` as two separate requests per turn (the request side is NET-15), and each row updates two btree indexes. Only the account cascade deletes `product_events`. A grep for `MessageChunk`/`ProductEvent` deletes and `retention|prune|older_than` in `apps/api/app` finds no scheduler, job or migration that prunes either table. Lead check: cited code read at the listed lines.
- **Impact:** estimated at 100k DAU and ~10 turns a day, `message_chunks` gains millions of rows a day. Each row carries a 6 KB vector, ~15–34 KB of duplicate JSON (NET-01), ~0.9 KB of text and an HNSW entry. That adds up to tens of GB a day, kept forever, billed per GB-month and copied into every branch and restore. `product_events` adds ~2M rows and ~2M extra authenticated requests a day for two bucketed metrics. Both tables raise the cost of SCALE-10's per-user scans and of account deletion.
- **Fix:** add one locked, batched retention cycle in `background/periodic.py`: either `DELETE … WHERE created_at < now() - :ttl … LIMIT 5000` on a `created_at` index, or monthly partitions dropped whole. Example limits: chunks 12 months or the newest N per user; events 90 days, with a daily aggregate table for the PRODUCTION.md "Cost telemetry" dashboards. Batch the two per-turn events into one request (the endpoint already accepts `ProductEventBatchIn`), or derive `chat_turn_outcome` server-side.
- **Verify:** `pg_total_relation_size` per table on a dashboard plateaus after the job, and the request log shows one analytics call per turn.
- **Source:** raw/agent-scale.md SCALE-10

<a id="scale-12"></a>

#### SCALE-12 — Search runs an unscoped trigram GIN plus an exact COUNT of every hit on each request
- **Severity:** Medium · **Confidence:** Medium · **Effort:** M
- **Locations:** `apps/api/app/modules/search/repository.py:43-48,79-97`, `apps/api/app/modules/search/api.py:18-20`, `apps/api/alembic/versions/0009_add_search_indexes.py:21-24`, `apps/mobile/features/search/model/drawerSearchLogic.ts:3`
- **Evidence:** the query is `content % q OR content ILIKE '%q%'` in a CTE of all hits, then `COUNT(*)` over it and `ORDER BY created_at OFFSET … LIMIT` (2-character minimum, `offset ≤ 10000`). Either the global GIN returns candidates from all users for recheck, or the planner uses `ix_messages_user_id` and computes `similarity()` over the full text of every message the user has. With an exact `total` and recency order over all hits, no plan can stop early. Two-character queries cannot use trigrams, and `%` almost never matches long bodies (similarity ≪ 0.3). Lead check: confirmed `ix_messages_content_trgm` is an unscoped GIN on `messages.content`.
- **Impact:** search latency and DB CPU grow with each user's history on the shared Neon compute; heavy users see seconds per keystroke burst, even behind the phone's 300 ms debounce. Every message insert (2 per turn, in the finalize transaction) writes GIN entries. With `fastupdate`, an overflowing insert flushes the pending list synchronously, causing a latency spike on reply saves.
- **Fix:** at `modules/search/repository.py`, plus one CONCURRENTLY migration:
  - user-scope the index (`btree_gin`: `USING gin (user_id, content gin_trgm_ops)`), or move to full-text search (`tsvector` generated column + GIN on `(user_id, tsv)`);
  - drop the `%` clause for message bodies;
  - replace the exact `total` with "has more" (fetch `limit + 1`) or a capped count;
  - require ≥ 3 characters.
- **Verify:** `EXPLAIN (ANALYZE, BUFFERS)` of the search for a heavy user on a seeded branch, before and after, and `pg_relation_size('ix_messages_content_trgm')` against the table.
- **Source:** raw/agent-scale.md SCALE-11

<a id="scale-13"></a>

#### SCALE-13 — Tool calls and searches before the first token have no per-call or overall deadline
- **Severity:** Medium · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/modules/chat/tool_loop/calls.py:125-146,166,180-185`, `apps/api/app/gateways/mcp/registry.py:59-90`, `apps/api/app/core/settings/llm.py:14-19`, `apps/api/app/modules/web_search/tool.py:87-113`, `apps/api/app/modules/images/gen_tool.py:51`, `apps/api/app/modules/images/search_tool.py:55`, `apps/api/app/modules/chat/prompt_builder.py:130`, `apps/api/app/modules/chat/tool_loop/rounds.py:117,140`
- **Evidence:** the only bounds are per-phase httpx timeouts:
  - Tavily: 12 s each for connect, write, pool and every read (`apps/api/app/gateways/web_search_gateway.py:23,163-164`), then DuckDuckGo 8 s (`:137-141`);
  - image generation: 120 s per read (`apps/api/app/gateways/image_gateway.py:18,50`);
  - photo lookup: 8 s per candidate, one after another (`apps/api/app/modules/images/search.py:119-127`).

  A turn allows up to 2 rounds × 4 sequential calls plus the forced search. The 20 s "invoke timeout" only stops new calls from starting. Lead check: read `modules/chat/tool_loop/calls.py` (`invoke_deadline` only checked in `_refusal` before a call; `_run_call` awaits `invoke_validated` with no timeout).
- **Impact:** in a Tavily or OpenRouter-images brownout, a turn can sit in "Searching…" for 30–90 s before any token while the phone only says "still working". The turn holds the prepare lock, the quota reservation and the socket the whole time, instead of failing fast with "search unavailable".
- **Fix:** wrap each `invoke_validated` in `asyncio.timeout(remaining)` against the round's deadline. Give the whole pre-stream phase (heuristic search + tool rounds + forced search) one budget (`ChatTurnDeps`/`stream_paths.run_tool_loop_path`). Give Tavily an overall `asyncio.timeout` in the gateway. Seam: `modules/chat/tool_loop/calls.py`, `gateways/web_search_gateway.py`.
- **Verify:** a fake search adapter that sleeps 60 s gets the round's refusal message within the deadline. Track TTFT p99 broken down by the `tool_loop_done` phase (`turn_timing`).
- **Source:** raw/agent-rel.md REL-06

<a id="scale-14"></a>

#### SCALE-14 — The SymPy pool (3 per machine) has no per-user share
- **Severity:** Medium · **Confidence:** Medium · **Effort:** M
- **Locations:** `apps/api/app/core/sympy_executor.py:212-226,228-262,269-343`, `apps/api/app/core/settings/stem.py:19-24`. Callers with no user key: `apps/api/app/modules/math/tools/prompt.py:425`, `apps/api/app/modules/math/tool.py:100`, `apps/api/app/modules/chat/tool_loop/calls.py:99`, `apps/api/app/modules/chat/finalize_subjects.py:140,217`, `apps/api/app/modules/physics/prompt.py:40,92`, `apps/api/app/modules/chemistry/context.py:310`
- **Evidence:** `run` waits 2 s for a slot and solves for up to 5 s. Any exception or cancel kills the slot, and the next caller waits up to 20 s for a new worker's ~4 s SymPy import. `_kill_slot` runs `proc.join` and `pool.shutdown(wait=True)` synchronously on the event loop. A turn can call `run_sympy` several times (pre-solve, tool-call match check, finalize checks). Three chats with a pathological expression each can therefore hold all three slots at about 20 messages a minute, under the 30/min chat limit (`apps/api/app/core/chat_rate_limit.py:13-14`). A Stop mid-solve also kills the worker. Lead check: cited code read at the listed lines.
- **Impact:** every other maths, physics and chemistry turn on that machine waits 2 s and is answered unverified, though verified STEM answers are a release requirement (ENGINEERING_STANDARDS.md "STEM correctness"). SCALING.md documents the 2 s fallback, not that one user can force it.
- **Fix:** in `BoundedSympyExecutor.run` (`core/sympy_executor.py`):
  - cap slots per user: pass the user id, allow at most one slot per user per machine, and queue or decline the rest for that user only;
  - kill a worker only on timeout; on a plain caller cancel, let the job finish and discard the result;
  - move `_kill_slot`'s joins to `asyncio.to_thread`.
- **Verify:** a fake-executor test that two users with saturating jobs leave a slot for a third, plus the existing `sympy queued` log (`:327-331`) reported per user.
- **Source:** raw/agent-rel.md REL-07

<a id="scale-15"></a>

#### SCALE-15 — No saturation signals: event-loop lag, DB pool, executor queue and Redis pool are not measured
- **Severity:** Medium · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app` (no metrics exporter or gauges: no Prometheus/StatsD/OpenTelemetry, no `engine.pool.checkedout()`, executor-queue or loop-lag sampling), `apps/api/app/core/sympy_executor.py:327-331` (the only saturation log), `apps/api/app/modules/chat/turn_timing.py:34-60` (phase timing, completed turns only)
- **Evidence:** SCALING.md "CPU" says "Measure before moving any of it" and gates its changes 2–5 and 9 on measurements. PRODUCTION.md §4 asks the owner to "watch Fly's proxy concurrency metrics". Nothing in the API emits those numbers, and SCALE-01, LEAK-01, LEAK-02 and SCALE-05 each fail silently until requests time out. Lead check: grep of `apps/api/app` for loop lag / `checkedout()` / executor queue: nothing.
- **Impact:** at 100k DAU, the first signal of loop stalls, pool exhaustion or executor starvation is user-visible 503s and timeouts. The logs show symptoms ("Dependency unavailable", "timed out") rather than the saturated resource, and capacity planning for N machines is guesswork.
- **Fix:** add one `core/metrics.py` (or Sentry custom metrics), sampled every 10 s from the lifespan, with:
  - a loop-lag heartbeat (sleep 0.1 s, record the overshoot);
  - DB pool `checkedout()`/`overflow()`;
  - the default executor's `_work_queue.qsize()`;
  - free SymPy slots and open sockets per machine;
  - the Redis pool's `_in_use_connections`.

  Alert on loop lag > 250 ms and on pool checkout waits.
- **Verify:** the gauges appear on the dashboard, and a synthetic blocking call in staging raises the loop-lag alert.
- **Source:** raw/agent-rel.md REL-09

<a id="scale-16"></a>

#### SCALE-16 — The data export has no per-user rate or concurrency limit
- **Severity:** Low · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/modules/account/api.py:438-445`, `apps/api/app/modules/account/export.py:46-57,227-229,252-305`, `apps/api/app/core/settings/edge.py:15`
- **Evidence:** the route has only `Depends(get_current_user)` and the global 240 requests/minute, while sign-in, chat, voice, scan reads, link preview and memory instruct each have their own limiter. Lead check: cited code read at the listed lines.
- **Impact:** one account can start dozens of exports at once, each reading up to ~1M rows in 200-row pages, serialized on the shared event loop, with up to 2,000 executor hops.
- **Fix:** allow one export at a time per user (a Redis `SET NX` lock with TTL) plus a daily or hourly cap in `modules/account/api.py`, or produce the export in a worker job to a presigned R2 object.
- **Verify:** a second concurrent `GET /auth/me/export` for the same user gets 429.
- **Source:** raw/agent-rel.md REL-10

<a id="scale-17"></a>

#### SCALE-17 — Withdrawing AI-data consent (or turning memory or web search off) is not honoured for up to 60 s on other machines' SSE, voice and scan paths
- **Severity:** Low · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/modules/chat/stream_api.py:267,289`, `apps/api/app/modules/chat/turn_load.py:79-84`, `apps/api/app/modules/account/consent.py:39-50`, `apps/api/app/core/deps.py:51-56`, `apps/api/app/core/user_cache.py:24`, `apps/api/app/modules/account/profile.py:54-62,66-77`
- **Evidence:** the 60 s cached user row is re-read only when it lacks consent, so a withdrawal is not seen while the cached row still says yes (the WebSocket path re-reads every turn). Lead check: cited code read at the listed lines.
- **Impact:** for up to a minute, another machine keeps sending the user's messages, voice and photos to the model providers, injecting memory and searching the web, contrary to the promise in `consent.py:3-11`.
- **Fix:** bump a per-user Redis generation key on `PATCH /auth/me` and check it in `core/user_cache.cached_user` (SCALING.md change 4), or re-read those columns on the SSE, voice and scan entry points as the WebSocket path does.
- **Verify:** a two-process test (two caches) where a withdrawal on one makes the next SSE turn on the other answer `consent_required`.
- **Source:** raw/agent-rel.md REL-08

<a id="scale-18"></a>

#### SCALE-18 — Every job's dedupe marker lives 24 h (millions of Redis keys at scale)
- **Severity:** Low · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/core/jobs/dedupe.py:20-21,34-42,89-100`, `apps/api/app/modules/chat/post_turn.py:94,117,155,192,216`, `apps/api/app/modules/account/lifecycle.py:166-195`
- **Evidence:** `_JOB_DONE_TTL_SECONDS = 86_400` applies to every successful keyed job, although an acked entry only needs cover for a crash between success and ack. Only `welcome:`/`receipt:` (`apps/api/app/modules/notifications/jobs.py:15,40`) and the once-per-chat `topic:` need a long window. Lead check: cited code read at the listed lines.
- **Impact:** ~1–2 keyed jobs per turn × 24 h is a few million live keys at 100k DAU (hundreds of MB of Upstash memory), and they dominate the keyspace that the account-delete `SCAN MATCH *<uuid>*` walks.
- **Fix:** a per-job done TTL in `core/jobs/queue.register` and `dedupe._extend_dedupe` (`done_ttl`, default 1 h or 15 min; keep 24 h for `transactional_email` and `storage_sweep`).
- **Verify:** Upstash key count (`INFO keyspace`) before and after, and a unit test that a `message_index` success sets a TTL ≤ 3600.
- **Source:** raw/agent-scale.md SCALE-12

<a id="scale-19"></a>

#### SCALE-19 — Six INCR-then-EXPIRE pairs are not atomic; two Redis sets have no TTL
- **Severity:** Low · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/services/quota/tokens.py:149-151,199-201`, `apps/api/app/services/quota/live_talk.py:106-108`, `apps/api/app/core/spend_counter.py:57-59`, `apps/api/app/gateways/structured_completion.py:105-106`, `apps/api/app/modules/memory/extract_backlog.py:146-147`, `apps/api/app/modules/memory/history_scan.py:121-122,131-132`, `apps/api/app/modules/attachments/lifecycle.py:23,69-76,80-103`, `apps/api/app/modules/notifications/push.py:50,75-84`
- **Evidence:** a crash or cancel between INCRBY/HINCRBY/SADD and EXPIRE leaves a key with no TTL; the class is already fixed in `apps/api/app/services/quota/counters.py:81-107` and `apps/api/app/core/rate_limit.py:19-20`. Separately, `recall:storage:pending_delete` and `recall:push:receipts:pending` have no TTL or size bound. Lead check: read `core/spend_counter.py:50-59`.
- **Impact:** immortal dated keys accumulate with every crash or cancel during a reservation, and the pending-delete set can grow until one reaper cycle cannot finish its SMEMBERS-and-retry pass.
- **Fix:** route every pair through `pipeline(transaction=True)` with `INCRBY` + `EXPIRE … NX` (as in `counters._reserve_daily_slot`), and give the pending-delete set a sorted-set form with attempt counts, a cap and paged reads.
- **Verify:** per-site fakeredis tests that cancel between the two commands (a patched `expire` raising `CancelledError`) and assert `TTL >= 0`.
- **Source:** raw/agent-scale.md SCALE-13

<a id="scale-20"></a>

#### SCALE-20 — Redundant prefix indexes on the hottest insert tables
- **Severity:** Low · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/models/orm/chat.py:67,73`, `apps/api/app/models/orm/attachments.py:29-32`, `apps/api/app/modules/todos/models.py:26-27`, `apps/api/alembic/versions/0002_indexes_and_constraints.py:22`, `apps/api/alembic/versions/0063_msg_chat_created_id_idx.py:33`, `apps/api/alembic/versions/0064_message_chunks.py:42,47-49`, `apps/api/alembic/versions/0012_add_todo_topic.py:26`, `apps/api/alembic/versions/0018_add_todo_sort_order.py:22-26`
- **Evidence:** a btree whose columns are a leading prefix of another btree on the same table serves no query the longer one cannot, yet `messages` (2 inserts per turn, 6 indexes) and `message_chunks` (3–12 inserts per turn, 5 indexes) pay for them on every turn. Lead check: confirmed in `pg_indexes`: `ix_messages_chat_created` ⊂ `ix_messages_chat_created_id`; `ix_message_chunks_user` ⊂ `ix_message_chunks_user_chat`; `ix_message_chunks_message` ⊂ `uq_message_chunks_message_index`; `ix_todo_user_topic` ⊂ `ix_todo_user_topic_sort`.
- **Impact:** extra WAL, write I/O and storage on every turn, with no read benefit.
- **Fix:** drop the four in a contract migration (`DROP INDEX CONCURRENTLY`, with an `# expand-contract:` note per `docs/ROLLBACK.md`), remove them from the ORM `__table_args__`, and pair the change with SCALE-02 so `message_chunks` swaps `(user_id)` for `(chat_id)`.
- **Verify:** `pg_stat_user_indexes.idx_scan` stays ~0 for the four over a week before the drop, and `EXPLAIN` of the window and chunk queries still uses the longer indexes after it.
- **Source:** raw/agent-scale.md SCALE-14

<a id="scale-21"></a>

#### SCALE-21 — A worker that does not know a job type dead-letters it (blue-green overlap, rollback)
- **Severity:** Low · **Confidence:** Medium · **Effort:** S
- **Locations:** `apps/api/app/core/jobs/queue.py:131-140`, `apps/api/app/core/jobs/worker.py:144-147`, `apps/api/app/background/handlers.py:141-146,170`, `docs/ROLLBACK.md` ("Schema changes: expand, then contract"), `docs/SCALING.md:33`
- **Evidence:** an unknown type or bad JSON raises `JobDiscardError` and goes to the DLQ without retry, and handlers read required fields with `payload["…"]`. Yet ROLLBACK.md's expand/contract rule covers tables only, and SCALING.md says "leases, dedupe and scheduler locks cover" the worker overlap. Lead check: read `core/jobs/queue.py:131-140`.
- **Impact:** in a blue-green deploy, the old worker dead-letters job types (or required payload fields) added in the release. After a rollback, the restored worker dead-letters every such job already queued. With manual replay (SCALE-07), that work is lost unless someone notices.
- **Fix:** on an unknown type, leave the entry pending (or re-enqueue with a delay) for a bound such as 24 h before the DLQ. Accept the previous payload shape for one release (`payload.get` with defaults), and add expand/contract for job types and payload fields to `docs/ROLLBACK.md`.
- **Verify:** a worker test with an entry of an unregistered type: it stays deliverable (not in the DLQ) and runs once the handler is registered.
- **Source:** raw/agent-scale.md SCALE-15

#### docs/SCALING.md and PRODUCTION.md claims checked against the code

This table keeps the rows whose verdict is false or partly (from raw/agent-rel.md "Doc claims checked against the code"), plus the two understatements from raw/agent-scale.md. Claims the sources found true, or true but understated, are left out.

| Claim | Verdict | Evidence (file:line) | Final finding ID |
|---|---|---|---|
| SCALING.md: one turn per chat at a time; Redis lock `chatprep:{chat}`, TTL 30 s, refreshed every 10 s | partly | `apps/api/app/modules/chat/turn_resources.py:34-35,97-140`; a failed or refused refresh is only logged (`:152-169`), so after a >30 s Redis blip or a blocked loop a second machine can start a concurrent turn on the same chat | SCALE-01 (blocked loop) |
| SCALING.md: "wait for the last reply to be saved"; other machines poll `chatfinal:{chat}` (50 ms, ≤10 s) | partly | `apps/api/app/modules/chat/finalize_registry.py:40-44,113-180`; the marker's 30 s TTL is shorter than the 120 s statement timeout (`apps/api/app/core/settings/infrastructure.py:25`), so a slow commit outlives it | none (open question) |
| SCALING.md: user row cached 60 s; "Consent is re-read from the row before a turn is refused" | partly (understates) | only an agreement is re-read. A withdrawal (and memory or web search off) is not, on SSE, voice and scan reads (`apps/api/app/modules/chat/turn_load.py:79-84`, `apps/api/app/modules/account/consent.py:44-46`). The same dependency pins a DB connection per request on a cache miss | SCALE-17, LEAK-01 |
| SCALING.md: SymPy pool of 3 workers, 2 s slot wait; "a maths turn that waits more than 2 s … is answered unverified" | partly (understates) | true per machine (`apps/api/app/core/sympy_executor.py:269-343`), but one user can hold all slots, and SymPy also runs on the event loop outside the pool | SCALE-14, SCALE-01 |
| SCALING.md: "SymPy runs in its own processes and document parsing on threads, but prompt building, the maths/physics/chemistry readers and the finalize passes run on the loop. Measure before moving any of it." | false (as a safety claim) | the readers run SymPy `parse_expr(evaluate=True)`/`solve` and an exponential regex on the user's text on the loop. Thread parsing is not bounded by its timeout, and nothing measures loop lag | SCALE-01, LEAK-02, SCALE-15 |
| SCALING.md change 9: "the readers and finalize passes are text processing over the reply" | false | the readers read the user's message and run SymPy (`apps/api/app/modules/math/tools/extractors/graph.py:194-202`) | SCALE-01 |
| Comment `apps/api/app/core/settings/attachments.py:8-11`: the parse is "bounded by this timeout so a large or adversarially crafted file can't block the event loop" | partly | the await is bounded, the thread is not, and the budget includes queue time | LEAK-02 |
| Comment `apps/api/app/gateways/web_search_gateway.py:24-25`: the DuckDuckGo bound keeps it from pinning "a shared thread-pool worker indefinitely" | false | `wait_for` does not stop the thread, and ddgs keeps walking engines (`apps/api/app/gateways/web_search_gateway.py:137-141`) | LEAK-02 |
| Comment `apps/api/app/modules/physics/solvers/drag.py:4`: "Chat already runs physics in the SymPy worker" | false | `apps/api/app/services/routing.py:405` and `apps/api/app/modules/physics/followup.py:134` solve in-process | SCALE-01 |
| Setting name `mcp_tool_loop_invoke_timeout_seconds` (`apps/api/app/core/settings/llm.py:19`) implies a per-invoke timeout | false | it is a start deadline (`apps/api/app/modules/chat/tool_loop/calls.py:125-146,180-185`) | SCALE-13 |
| Comment `apps/api/app/modules/account/export.py:258-259`: a session per page, so a slow download "cannot pin a Neon connection for the stream lifetime" | false on a user-cache miss | `get_current_user`'s own session pins one (`apps/api/app/core/deps.py:37-62`) | LEAK-01 |
| `apps/api/app/core/jobs/__init__.py:5`: "jobs survive a process restart" | partly (overstates safety) | with nothing pending, every enqueue runs `XTRIM MAXLEN ~ 10_000`, dropping jobs that were never delivered (`apps/api/app/core/jobs/queue.py:107-128`); there is no backlog metric (`apps/api/app/core/jobs/admin.py:67-101`) | SCALE-06 |
| `docs/SCALING.md:30` "the stream is bounded"; `docs/PRODUCTION.md:520` "The 10k soft trim only runs while nothing is pending" | partly (overstates safety) | the bound is kept by trimming undelivered entries when no consumer is reading, and by the 50,000 hard cap on every XADD (`apps/api/app/core/jobs/queue.py:79-104,123-126`) | SCALE-06 |
| SCALING.md item 6: "make the account-delete sweep independent of total size" | partly (understates) | the keyspace that `SCAN MATCH *<uuid>*` walks on every delete (`apps/api/app/modules/account/lifecycle.py:166-195`) is dominated by 24 h `jobdone:` markers (`apps/api/app/core/jobs/dedupe.py:20-21,89-100`) | SCALE-18 |

#### Hot queries and their indexes

Condensed from raw/agent-scale.md "Hot query index table". A migration reference `NNNN:line` means `apps/api/alembic/versions/NNNN_*.py:line`.

| Query | Location | Filter / order columns | Index present? |
|---|---|---|---|
| Recent window (every turn) and message page | `apps/api/app/repositories/messages.py:43-57,107-150` | `chat_id`; ORDER BY `created_at DESC, id DESC` LIMIT 20, or `(created_at, id) <` cursor | Yes: `ix_messages_chat_created_id` (`0063:33`) |
| Prior-count for the window | `apps/api/app/repositories/messages.py:315-320` | `chat_id` COUNT(*) | Yes (index-only scan, O(chat length)): `ix_messages_chat_created` (`0002:22`) |
| Chat list (drawer) | `apps/api/app/repositories/chats.py:76-95` | `user_id`, `archived`, EXISTS(messages.chat_id); ORDER BY `pinned, updated_at, id` | Partly: `ix_chats_user_updated` (`0002:29`); the `pinned`-first sort is done in memory (bounded by the user's chats) |
| Memory load and ranking (memory turns) | `apps/api/app/modules/memory/repository.py:21-37` → `apps/api/app/modules/memory/selection.py:101-106` | `user_id`, `status IN`; ranked in Python | Yes: `ix_memories_user_status` (`0087:113`), but it reads both embeddings of every row; the `ix_memories_embedding` HNSW (`0033:48-49`) is never used (NET-01) |
| Chat-history RAG | `apps/api/app/repositories/message_chunks.py:74-106` | `user_id`, `embedding IS NOT NULL`, `message_id NOT IN`; ORDER BY `embedding <=> q` LIMIT 6 | Global HNSW `ix_message_chunks_embedding` (`0064:51-52`) + btree `user_id` (`0064:47`); no user-scoped ANN path (SCALE-10) |
| Attachment RAG | `apps/api/app/modules/attachments/chunks_repository.py:109-142` | `user_id`, `chat_id`; ORDER BY `embedding <=> q` | Global HNSW (`0047:57-58`) + `(user_id, chat_id)` (`0047:46`); same caveat (SCALE-10) |
| Per-user chunk scans: "existing" count on every `message_index` job; fact purge of chat snippets | `apps/api/app/repositories/message_chunks.py:25-29` (called at `apps/api/app/modules/chat/history_rag.py:123`), `:109-125` | `user_id` COUNT(*); `user_id`, `embedding <=> v <= 0.5` | `0064:47`, but O(user's chunks): a COUNT where EXISTS would do, and an exact distance over every chunk of the user (SCALE-10) |
| Search | `apps/api/app/modules/search/repository.py:43-97` | `messages.user_id`, `content % q OR content ILIKE '%q%'`; COUNT of all hits; ORDER BY `created_at` | `ix_messages_user_id` (`0011:20`); the trigram GIN is global (`0009:22-23`) (SCALE-12) |
| Reminder scans, every minute: push candidates, aged-unsent count, email | `apps/api/app/modules/notifications/push.py:246-261,211-224`, `apps/api/app/modules/notifications/reminder_email.py:52-65` | `checked`, `due_at` range, `notification_sent_at` / `email_sent_at IS NULL` (email also `recurrence_rule IS NULL`; the count adds EXISTS(push_tokens)); no `user_id` | No index leads with `due_at`. Only the partial `ix_todo_user_open_due (user_id, due_at)` (`0021:21-23`), which bounds the walk to open dated rows (SCALE-08) |
| Push tokens for due users | `apps/api/app/repositories/push_tokens.py:151-156` (`list_for_users`) | `user_id IN (...)` | Yes: `ix_push_tokens_user` (`0025:37`); one bind parameter per user (SCALE-08 cliff) |
| Orphan reaper | `apps/api/app/modules/attachments/repository.py` (`list_orphans`) | `message_id IS NULL`, `created_at <` | Yes: partial `ix_attachments_unlinked_created` (`0115:46-52`) |
| Billing reconcile page | `apps/api/app/repositories/users.py:43-56` | `plan = :p`, `id > :after` ORDER BY `id` | No `plan` index: each hourly cycle walks the users PK once per paid plan (noted only) |
| Memory history scan | `apps/api/app/modules/memory/history_scan.py:87-98` | `chats.user_id` + EXISTS(messages `chat_id`, `role`); ORDER BY `updated_at` LIMIT 20 | Yes: `0002:29` + `ix_messages_chat_role` (`0002:25`) |
| Usage seed / settle | `apps/api/app/repositories/usage.py` | PK `(user_id, date)` | Yes (PK) |
| FK lookups fired by deletes | RI triggers on `memories.source_message_id`, `memories.superseded_by_id`, `memories.source_chat_id`, `todo_items.chat_id`, `message_chunks.chat_id` | the FK column alone | No for all five (SCALE-02). Present for `attachments.message_id` and `attachment_chunks.chat_id` (`0115:38-58`), every `user_id` FK, `messages.chat_id` and `message_chunks.message_id` |

### G. Clarity, consistency and maintainability

<a id="clar-01"></a>

#### CLAR-01 — User content reaches logs and Sentry (to-do titles and text, reminder subjects, SQL parameters, raw paths)
- **Severity:** High · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/modules/todos/reminder_writes.py:204-209`, `apps/api/app/modules/todos/actions.py:201-206`, `apps/api/app/gateways/email_gateway.py:93`, `apps/api/app/gateways/email_gateway.py:119`, `apps/api/app/modules/notifications/email_copy.py:352`, `apps/api/app/modules/notifications/reminder_email.py:101-103`, `apps/api/app/modules/math/tools/prompt.py:441`, `apps/api/app/modules/math/solve/parse.py:186`, `apps/api/app/core/db.py:25-37`, `apps/api/app/core/request_id.py:63-65`, `apps/api/app/core/sentry.py:82-92`, `apps/mobile/lib/sentry.ts:42`, and 11 more (see raw/agent-clar.md CLAR-01)
- **Evidence:** To-do text is logged:
  ```
  "To-do fence applied: user_id=%s chat_id=%s title=%s", …, title[:80]
  "Todo delete missed: user_id=%s topic=%s content=%r", …, (action.content or "")[:120]
  ```
  A reminder email's subject is `"{title}: {content}"`. Every failed send logs it via `logger.exception` (ERROR plus a Sentry event), though the function masks the recipient. `MathServiceError` messages, logged at INFO, embed the user's input. Without `hide_parameters=True`, every SQLAlchemy `StatementError` carries `[parameters: %r]`. The access line logs raw paths, including memory-area slugs. Breadcrumbs, `logentry` params and exception values reach Sentry unscrubbed, although `SECURITY.md:22` says error reports carry no request bodies. Lead check: read `apps/api/app/modules/todos/reminder_writes.py:204-206` (INFO `title=%s`), `apps/api/app/modules/todos/actions.py:201-203` (WARNING `content=%r`), `apps/api/app/gateways/email_gateway.py:119` (`logger.exception(... subject=%r)`), `apps/api/app/core/db.py` (no `hide_parameters`), `apps/api/app/core/sentry.py:66-92` (`before_send` scrubs only `event["request"]`).
- **Impact:** Reminder text (often health, family or money) lands in the Fly log drain and in Sentry, whose retention and access differ from the database's; a failed message insert ships its text to Sentry.
- **Fix:** Log ids and lengths only (`title_len=`, `content_len=`, `kind=`). Set `hide_parameters=True` on the engine and log the route template (`request.scope["route"].path`). In `apps/api/app/core/sentry.py`, scrub logging breadcrumbs and cap exception values as `apps/mobile/lib/sentry.ts` does. Add an architecture test that fails when a logger call interpolates `content`, `title`, `subject`, `text`, `prompt` or `query`.
- **Verify:** That test; a `before_send` unit test with a breadcrumb and a `StatementError`; `grep -rn "subject=%r\|title=%s\|content=%r" apps/api/app` returns nothing.
- **Source:** raw/agent-clar.md CLAR-01

<a id="clar-02"></a>

#### CLAR-02 — 91 broad excepts log only at DEBUG while the root logger is fixed at INFO; a Redis failure on the memory lock reads as "lock held"
- **Severity:** Medium · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/core/logging.py:166-177`, `apps/api/app/process_bootstrap.py:45`, `apps/api/app/modules/memory/locks.py:25`, `apps/api/app/modules/memory/extraction_workflow.py:279-284`, `apps/api/app/modules/memory/consolidation_workflow.py:114-119`, `apps/api/app/core/jobs/dedupe.py:62`, `apps/api/app/modules/attachments/content.py:147`, `apps/api/app/modules/attachments/content.py:164`, `apps/api/app/modules/attachments/lifecycle.py:198`, `apps/api/app/modules/memory/crud.py:106`, `apps/api/app/modules/speech/live_talk.py:247`, `apps/api/app/services/model_health.py:54`, and 6 more (see raw/agent-clar.md CLAR-02)
- **Evidence:** `setup_logging` takes no level, and no `LOG_LEVEL` setting exists. 91 of the 338 broad `except Exception` handlers log only at DEBUG. On a Redis error the memory lock returns `None`, so extraction and consolidation log "skipped: write lock held" at INFO and re-enqueue:
  ```
  logger.debug("Memory write lock acquire failed", exc_info=True); return None
  root.setLevel(logging.INFO)
  ```
  Other DEBUG-only failures: a dedupe claim that fails open (a duplicate job runs), PDF and DOCX extraction (no text for RAG), an image-quota refund (a lost slot), a re-embed after an edit (the vector stays NULL), Live Talk starting without memory or schedule, and a model-health read failure reported as healthy. Lead check: read `apps/api/app/modules/memory/locks.py:18-27` and `apps/api/app/core/logging.py:177`.
- **Impact:** Failing open is fine, but these failures leave no trace in production logs or Sentry breadcrumbs (both start at INFO): on-call cannot tell a Redis blip from contention, or see extraction and refunds failing.
- **Fix:** Add `log_level: str = "INFO"` to `apps/api/app/core/settings/infrastructure.py` and pass it to `setup_logging`. Raise the non-cache handlers to WARNING with ids. Count the rest through `report_breadcrumb` (`apps/api/app/core/sentry.py`), the documented best-effort seam. Have `acquire_memory_write_lock` return a distinct "Redis failed" outcome.
- **Verify:** A test that `setup_logging` honours `LOG_LEVEL`. Re-run `raw/scratch-clar/except_levels.py`: the debug-only count drops and none of the listed sites remains.
- **Source:** raw/agent-clar.md CLAR-02

<a id="clar-03"></a>

#### CLAR-03 — The long, branchy STEM functions were never ticketed: 32 production functions are radon grade F (CC > 40) and the next tier (152–218 lines) is unchanged since the standards audit
- **Severity:** Medium · **Confidence:** High · **Effort:** L
- **Locations:** `apps/api/app/modules/math/tools/direct_calculus.py:113`, `apps/api/app/modules/physics/extractors/circuits.py:70`, `apps/api/app/modules/physics/extractors/torque.py:51`, `apps/api/app/modules/math/tools/direct.py:163`, `apps/api/app/modules/memory/extraction_workflow.py:269`, `apps/api/app/modules/chat/stream_api.py:80`, `apps/api/app/modules/memory/llm.py:69`, `apps/api/app/modules/physics/block.py:107`, `apps/api/app/modules/physics/solvers/projectile.py:48`, `apps/api/app/modules/math/tools/prompt.py:238`, `apps/api/app/modules/memory/consolidation_workflow.py:106`, `apps/api/app/modules/chat/ws_turn.py:57`, and 19 more (see raw/agent-clar.md CLAR-03 and its top-15 tables)
- **Evidence:** ES-19…ES-26 and ES-37 cut functions over 100 lines from 87 to 61, but the top 15 by length (152–218 lines) predate 8a20f147d and were never ticketed (9 unchanged in length, 2 shrank by 1–2 lines, 4 grew). Growth since the audit: `_extract_pass` 163 → 177 (depth 5), `_stream_tokens_sse` 150 → 159, `revise_memory_facts` 107 → 119, `_build_physics_block` 131 → 136, `solve_projectile` 154 → 158, `build_math_augmentation` 150 → 152. Functions over 50 lines hold at 378: new ones arrive as fast as tickets remove them. Deepest: `consolidate_user_memory_sections` (depth 6). Lead check: radon production grades C 616, D 124, E 42, F 32; worst `calculus_direct_request` CC 95 (`apps/api/app/modules/math/tools/direct_calculus.py:113`), `_extract_torque_intent` 75, `can_direct_verified_math_reply` 71; API 6,004 functions, 378 > 50 lines, 61 > 100.
- **Impact:** The chat transports and memory extraction change most (`apps/api/app/modules/memory/extraction_workflow.py`: 7 commits since 2026-08-20). At depth 5–6 a reviewer cannot see which writes a forget, mute or history pass produces.
- **Fix:** Treat this as ES-37 part 4 (capture and compare). Split `_extract_pass` into `_load_pass_input` → `_compose_writes(snapshot, result, flags)` (pure) → `_apply_and_stamp`, and reshape `consolidate_user_memory_sections` the same way. Add a function-length baseline, like `scripts/file_size_baseline.json`, that may only go down.
- **Verify:** The `raw/scratch-clar/py_metrics.py` counts go down. A function-length ratchet test in `apps/api/app/tests/architecture/`.
- **Source:** raw/agent-clar.md CLAR-03

<a id="clar-04"></a>

#### CLAR-04 — The phone's chat hooks are state machines held in refs (`useChat` 550 lines, 29 refs)
- **Severity:** Medium · **Confidence:** High · **Effort:** L
- **Locations:** `apps/mobile/features/chat/hooks/useChat.ts:32`, `apps/mobile/features/chat/hooks/useChat.ts:40`, `apps/mobile/features/chat/hooks/useChat.ts:71-72`, `apps/mobile/features/chat/hooks/useChat.ts:86-93`, `apps/mobile/features/chat/hooks/useChatRouteLoader.ts:61`, `apps/mobile/features/chat/screens/ChatScreen.tsx:48`, `apps/mobile/features/chat/components/ChatComposer.tsx:118`, `apps/mobile/features/speech/hooks/useLiveTalk.ts:46`, `apps/mobile/features/chat/hooks/useChatSend.ts:95`, `apps/mobile/features/chat/hooks/useChatIncoming.ts:28`, `apps/mobile/eslint.config.js:132`, `apps/mobile/eslint.config.js:133-134`
- **Evidence:** `useChat` (29 `useRef`, 18 `useCallback`, 6 `useState`) mirrors state into refs, writing `messagesRef.current = messages` during render and keeping `streamingRef` beside `streaming`. Four late-bound handler refs let sibling hooks call each other. `react-hooks/refs`, which would flag this, is off app-wide, as are `set-state-in-effect` and `preserve-manual-memoization`. ES-38 skipped them though `useChat` was already 558 lines at the audit; only `useChatSend` was ticketed (ES-35). Phone functions over 50 lines grew from 359 to 374. Lead check: function-length metrics give `useChat` 550, `ChatScreen` 514, `useChatRouteLoader` 473, `useLiveTalk` 436, `useChatSend` 417, `useChatIncomingEvents` 395.
- **Impact:** Every chat bug (stop, regenerate, socket fallback, switching chats mid-stream) is a race between refs mutated from several hooks. This is the phone's most-changed area: since 2026-08-20 the chat screen changed in 65 commits, `useChatSend` in 55, `ChatComposer` in 40+ and `useChat` in 29. No other phone file reaches 51.
- **Fix:** Apply ES-36's pure-reducer approach (`realtimeTurnState.ts`) to the chat turn: a `chatTurnState.ts` reducer over socket and SSE payloads, sends, stop and regenerate. Keep `useChat` as the effect shell, and replace the late-bound refs with the reducer's dispatch. Then re-enable `react-hooks/refs` for `features/chat/**`.
- **Verify:** `raw/scratch-clar/ts_metrics.js` shows `useChat` under 200 lines with fewer than 10 refs; a reducer test over recorded event sequences (`chatSocketReduce.test.ts` style); the lint rule passes on `apps/mobile/features/chat`.
- **Source:** raw/agent-clar.md CLAR-04

<a id="clar-05"></a>

#### CLAR-05 — Memory keeps the `_seams()` = `sys.modules` lookup ES-23 removed from chat, behind a compatibility barrel of forwarding wrappers
- **Severity:** Medium · **Confidence:** High · **Effort:** M
- **Locations:** `apps/api/app/modules/memory/surface.py:1-5`, `apps/api/app/modules/memory/surface.py:131-133`, `apps/api/app/modules/memory/__init__.py:15-20`, `apps/api/app/modules/memory/__init__.py:32`, `apps/api/app/modules/memory/locks.py:18`, `apps/api/app/modules/memory/locks.py:43`, `apps/api/app/modules/memory/retrieval.py:40-42`, `apps/api/app/modules/memory/retrieval.py:56`, `apps/api/app/modules/memory/crud.py`, `apps/api/app/modules/memory/cache.py`, `apps/api/app/services/reminder_timing.py:46-50`, `apps/api/app/modules/todos/sync.py:103-106`, and 34 more (see raw/agent-clar.md CLAR-05 and raw/agent-dead.md DEAD-04)
- **Evidence:** `surface.py` is a "Compatibility barrel … so existing `app.modules.memory.*` monkeypatches continue to affect collaborators":
  ```
  def _seams(): return sys.modules["app.modules.memory"]
  ```
  Its 22 receivers typed `seams: Any`, in `apps/api/app/modules/memory/{cache,crud,locks,retrieval}.py`, reach 29 names through it in 51 lookups. The barrel holds 19 forward-only wrappers and 42 re-exports (9 unread, 3 read only by tests). Tests patch the package in 65 places (raw/agent-dead.md DEAD-04 counts 119 patch strings). `_profile_kwargs`, `reminder_timing` and `apps/api/app/modules/todos/sync.py` also bend to fit test fakes. ES-23's fix (`ChatTurnDeps`) reached chat only. Lead check: read `apps/api/app/modules/memory/surface.py:131-133`.
- **Impact:** mypy cannot check the 51 lookups, so a renamed memory function breaks only at runtime. Dead code hides behind `seams.X`, and every new memory function needs a wrapper to stay patchable.
- **Fix:** Do what ES-23 did for chat: pass a frozen `MemoryDeps` (Redis client getter, repositories, embedder, background-task spawner) built by `default_deps()`. Tests use fakes or patch the defining modules. Then delete the wrappers, the re-exports and `_profile_kwargs`, and read `user.quiet_hours_enabled` directly. A first step that changes no behaviour: drop the 9 unread re-exports and `is_memory_correction` from `__init__.__all__`.
- **Verify:** `grep -rn "seams" apps/api/app/modules/memory` returns nothing; no test patches `app.modules.memory.*`; mypy checks the memory calls; `uv run pytest app/tests/modules/memory app/tests/modules/chat -k memory` stays green.
- **Source:** raw/agent-clar.md CLAR-05; raw/agent-dead.md DEAD-04

<a id="clar-06"></a>

#### CLAR-06 — Strict typing covers about 5% of the API; lazy `__getattr__` turns 58 imports into `Any`; stale `# type: ignore`s go unreported
- **Severity:** Medium · **Confidence:** High · **Effort:** M
- **Locations:** `apps/api/pyproject.toml:107-110`, `apps/api/pyproject.toml:116-142`, `apps/api/pyproject.toml:139`, `apps/api/app/modules/billing/__init__.py:22`, `apps/api/app/modules/chat/__init__.py:49`, `apps/api/app/modules/memory/__init__.py:15`, `apps/api/app/modules/images/generation.py:32`, `apps/api/app/modules/web_search/augment.py:42`, `apps/api/app/modules/chat/post_turn.py:25`, `apps/api/app/modules/physics/schemas/intent.py:61`, `apps/api/app/modules/physics/extractors/school_common.py:33`, `apps/api/app/modules/chemistry/binding.py:392`, and 33 more (see raw/agent-clar.md CLAR-07)
- **Evidence:** The strict overrides cover 8,601 of 183,369 production lines (4.7 %) and have not grown since cbd011072 (#474, 2026-07-18). Seven packages export through `def __getattr__(name: str) -> Any` without `TYPE_CHECKING` stubs, so mypy types 58 production imports in 28 files as `Any`, including `can_use`. 10 of the 30 production `# type: ignore`s no longer suppress anything, because `physics_op` became `str | None` (f6d18d066, 2026-10-02) and `chemistry_op` is `str`:
  ```
  physics_op: str | None = Field(default=None, max_length=64)
  def _intent(operation: str, …): … physics_op=operation,  # type: ignore[arg-type]
  ```
  `warn_unused_ignores` is on only in the strict override. 13 of 29 `eslint-disable` and 5 of 13 `# noqa` lack the required one-line reason. Lead check: read `apps/api/pyproject.toml` `[tool.mypy]` (`strict = false`; strict flags only for `app.core`, `app.exceptions`, `app.models.schemas`, `app.repositories`, `app.services.quota` and three attachment files).
- **Impact:** Calls across module boundaries go unchecked: a renamed parameter on `can_use` or `solve_physics` passes CI. The clean mypy run over 1,551 files reflects unchecked paths, not typed ones.
- **Fix:** Generate `if TYPE_CHECKING:` imports from `_EXPORTS` in each lazy `__init__.py`. Widen the strict override package by package, `modules.billing`, `modules.memory`, `modules.todos` and `gateways` first. Delete the 10 stale ignores and enable `warn_unused_ignores = true` globally. Enforce suppression reasons with a grep test and `@eslint-community/eslint-comments/require-description`.
- **Verify:** `reveal_type(can_use)` under mypy; `raw/scratch-clar/lazy_imports.py` reports 0; `uv run mypy --warn-unused-ignores app/modules/physics app/modules/chemistry` lists the 10 stale ignores before and none after.
- **Source:** raw/agent-clar.md CLAR-07

<a id="clar-07"></a>

#### CLAR-07 — Production configuration lives in three places that disagree
- **Severity:** Medium · **Confidence:** High · **Effort:** S
- **Locations:** `fly.toml:23-26`, `fly.toml:30`, `fly.toml:33`, `fly.toml:36`, `fly.toml:37`, `apps/api/app/core/settings/search.py:10`, `apps/api/app/core/settings/memory.py:27`, `apps/api/app/core/settings/llm.py:47`, `apps/api/app/core/settings/llm.py:52`, `apps/api/.env.production.example:47`, `apps/api/.env.production.example:57-59`, `apps/api/app/core/settings/edge.py:12`, and 10 more (see raw/agent-clar.md CLAR-08)
- **Evidence:** `fly.toml` `[env]` overrides four code defaults: `WEB_SEARCH_CLASSIFIER_ENABLED="false"` vs `True`, `MEMORY_QUERY_EMBED_TIMEOUT_SECONDS="0.75"` vs `2.0`, `CHAT_STREAM_CONNECT_TIMEOUT_SECONDS="5"` vs `15` and `CHAT_STREAM_TIMEOUT_SECONDS="30"` vs `45`. Only the last field's comment mentions fly.toml. `apps/api/.env.production.example` repeats all four and sets its own `TRUSTED_PROXY_CIDRS`. `fly.toml:23-26` says the default covers Fly's private ranges, while the example says Fly's proxy connects from the RFC1918/CGNAT ranges. Despite their names, `math_solve_timeout_seconds` and `math_scan_read_rate_limit_per_hour` also govern physics and chemistry. Lead check: compared `apps/api/app/core/settings/edge.py:12` with `apps/api/.env.production.example:47` (`TRUSTED_PROXY_CIDRS`: 127.0.0.1/32 vs 100.64.0.0/10).
- **Impact:** Development and the tests run the web-search classifier (an extra model call before the first token) and 15 s/45 s stream timeouts that production does not, so latency and fallbacks differ. The CIDR disagreement decides whether per-IP rate limits key on the client or on Fly's proxy.
- **Fix:** Make each code default the production value, with development relaxations in `apps/api/.env.example`, or keep the override and write "production: N (fly.toml)" in the field's comment. Add `apps/api/app/tests/test_config.py::test_fly_env_matches_defaults_or_is_listed`, which fails on any `fly.toml` or `.env.production.example` value that is neither the default nor allowlisted with a reason. Rename `math_solve_timeout_seconds` to `stem_solve_timeout_seconds`, with the old env name as an alias for one release.
- **Verify:** The new config test. `grep -n TRUSTED_PROXY_CIDRS` gives one value.
- **Source:** raw/agent-clar.md CLAR-08

<a id="clar-08"></a>

#### CLAR-08 — Phone catches that look like success (store offerings failure, in-chat PDF export)
- **Severity:** Medium · **Confidence:** High · **Effort:** S
- **Locations:** `apps/mobile/features/chat/hooks/useChatActions.ts:133-140`, `apps/mobile/features/chat/hooks/useChatActions.ts:142-152`, `apps/mobile/features/chat/hooks/useChatMenuActions.ts:84-90`, `apps/mobile/lib/purchases.ts:139-141`, `apps/mobile/components/UpgradeSheet.tsx:137`, `apps/mobile/components/UpgradeSheet.tsx:220`, `apps/mobile/components/UpgradeSheet.tsx:233`, `apps/mobile/features/memory/hooks/useMemoryDocuments.ts:107`, `apps/mobile/features/memory/hooks/useMemoryDocuments.ts:160`, `apps/mobile/features/memory/hooks/useMemoryDocuments.ts:176`, `apps/api/app/modules/memory/api.py:29`, `apps/api/app/modules/memory/api.py:133`
- **Evidence:** `loadTranscriptMessages` swallows the failure:
  ```
  try { return await api.listAllMessages(token, chatId); } catch { return messages; }
  ```
  `handleExportPdf` then exports whatever is loaded (pages of 40) and its `chat.export_pdf_failed` report never fires; the drawer's share path propagates the error. A failing `getOfferings()` returns `{}`, like "no products", so plan cards show "See price in store" above a disabled Subscribe button, with no message, warning or analytics event. The memory hooks collapse 409 busy, 409 "Memory is off.", 404, 422 and offline into one generic "Memory couldn't be updated". Of the phone's 197 silent catches, these three break ENGINEERING_STANDARDS rule 8 ("Never swallow a failure or return a made-up success"). Lead check: read `apps/mobile/lib/purchases.ts:139-141` and `apps/mobile/features/chat/hooks/useChatActions.ts:133-140`.
- **Impact:** Users export "the whole chat" and silently get the last page; a store outage looks like Recall sells no plans, and nobody is alerted; a busy memory write looks broken.
- **Fix:** Let `loadTranscriptMessages` throw, or return `{ messages, complete: false }` and say so in the PDF. Have `getPlanPackages` return `{ packages, error }`, show "Store unavailable, try again" and call `reportRecoverableWarning`. Have the memory hooks surface the server's `code` or `detail` (after DUP-10), with a separate retry toast for 409-busy.
- **Verify:** Unit tests: a rejected `listAllMessages` shows the error toast without calling `exportConversationAsPdf`; a rejected `getOfferings` shows the unavailable state; a memory 409 shows the busy toast.
- **Source:** raw/agent-clar.md CLAR-10

<a id="clar-09"></a>

#### CLAR-09 — About 47 English strings per locale (75 in Amharic) are untranslated; the i18n test checks key parity only
- **Severity:** Medium · **Confidence:** High · **Effort:** S–M
- **Locations:** `apps/mobile/lib/i18n/{de,es,fr,it,pt,ru,tr}.json`, `apps/mobile/lib/i18n/am.json`, `apps/mobile/lib/__tests__/i18n.test.ts:19-29`
- **Evidence:** Each of the seven locales has 47–48 values of three or more words identical to `apps/mobile/lib/i18n/en.json`; `am.json` has 75. Examples from `de.json` include `settings.memory_clear_all_confirm_body` ("This removes every saved fact. Recall can learn them again from new chats."), `chat.voice_permission_title` ("Microphone access needed"), `chat.scan_rate_limit`, `chat.scan_spend_cap`, `chat.model_unavailable`, `settings.push_register_failed` and `common.not_found_title`. New keys arrive in English in every locale at once: `chat.scan_rate_limit` was added to all nine files in English in 190a34984 (2026-10-03). The test only asserts that "`${code}.json` has every en.json key". The counts come from `raw/scratch-clar/i18n_untranslated.py`. Lead check: `apps/mobile/lib/i18n/de.json` `chat.email_card_copy` = "Copy email", `chat.email_card_done` = "Done editing" (identical to English).
- **Impact:** Destructive-action confirmations, permission prompts and error toasts appear in English inside an otherwise German or Amharic app. CLAUDE.md's "9 locales, key parity tested" reads as full coverage, and the test is green.
- **Fix:** Translate the ~50 keys per locale. Add a test that fails when a non-English value equals the English one, with an allowlist for brand names, units and code (`rich.graph_expr_placeholder`, "Open in Maps"…).
- **Verify:** The new test passes with an allowlist of fewer than 10 entries per locale.
- **Source:** raw/agent-clar.md CLAR-14

<a id="clar-10"></a>

#### CLAR-10 — A third of WARNING+ log lines carry no id; the WebSocket path and the worker get no request id
- **Severity:** Medium · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/modules/chat/ws_turn.py:86`, `apps/api/app/modules/chat/ws_turn.py:228`, `apps/api/app/modules/chat/stream_events.py:265`, `apps/api/app/modules/chat/finalize_passes.py:225`, `apps/api/app/modules/chat/finalize_reminders.py:70`, `apps/api/app/modules/chat/related_prompts.py:126`, `apps/api/app/modules/images/search.py:343`, `apps/api/app/modules/images/answer_photo.py:83`, `apps/api/app/modules/images/reply_picture.py:121`, `apps/api/app/modules/account/tokens.py:147`, `apps/api/app/modules/account/tokens.py:426`, `apps/api/app/core/request_id.py:47`, and 9 more (see raw/agent-clar.md CLAR-15)
- **Evidence:** 97 of the 305 `warning`/`error`/`exception`/`critical` calls in API production code pass no arguments (`raw/scratch-clar/log_calls.tsv`). They include `logger.exception("Chat stream failed")` and "Unexpected chat stream error" on the preferred transport, although `chat_id` is a parameter of the enclosing `run_chat_stream` (`apps/api/app/modules/chat/ws_turn.py:205`), and seven account-token lines that say only "… failed; Redis unavailable". `RequestIdMiddleware` is a Starlette `BaseHTTPMiddleware`, which passes WebSocket scopes straight through, so `request_id_context` is never set on `/ws/chat` or in worker jobs. The formatter prints `[request_id=…]` only when it is set (`apps/api/app/core/logging.py:96-104`), and nothing calls `sentry_sdk.set_tag`, `set_user` or `set_context`. Lead check: cited code read at the listed lines.
- **Impact:** "Chat stream failed" with a traceback and no id cannot be tied to a user report, a chat, or the same turn's `turn_cost` and `chat_stream_timing` lines. Error-rate alerts cannot be split by model or plan.
- **Fix:** Set a turn-scoped contextvar (`turn_id`, `chat_id`, `user_id`) in `stream_over_ws` and `_stream_tokens_sse`, and a `job_id`/`job_type` one in `apps/api/app/core/jobs/worker.py`. Print it in the formatters, mirror it with `sentry_sdk.set_tag` (ids only), make `RequestIdMiddleware` pure ASGI, and add ids to the 97 calls, chat and account first.
- **Verify:** A test that a log record inside a WebSocket turn carries `chat_id`. Re-running `raw/scratch-clar/log_args.py` leaves only a short allowlist of startup and config warnings.
- **Source:** raw/agent-clar.md CLAR-15

<a id="clar-11"></a>

#### CLAR-11 — 284 `getattr(obj, "field", default)` reads of typed columns; `memory_enabled` read with two different defaults
- **Severity:** Low · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/modules/chat/prompt_memory.py:98-100`, `apps/api/app/modules/speech/live_talk.py:233`, `apps/api/app/modules/memory/extraction_workflow.py:82`, `apps/api/app/modules/memory/consolidation_workflow.py:89`, `apps/api/app/modules/memory/learning_progress.py:59`, `apps/api/app/modules/account/lifecycle.py:45`, `apps/api/app/modules/account/export.py:137`, `apps/api/app/modules/account/export.py:145-151`, `apps/api/app/models/orm/user.py:48-103`, `apps/api/app/modules/account/profile.py:13`, `apps/api/app/modules/notifications/push.py:283`, `apps/api/app/services/reminder_timing.py:50-58`, and 11 more (see raw/agent-clar.md CLAR-06)
- **Evidence:** The `memory_switch_on` helper defaults to True and Live Talk's read to False, although every `User` field read this way is a declared `Mapped[...]` column. Lead check: cited code read at the listed lines.
- **Impact:** mypy types each read as `Any`, a renamed column breaks nothing, and the default becomes the behaviour: memory on for chat, off for Live Talk.
- **Fix:** Read typed attributes directly, route every memory-switch read through `memory_switch_on(user: User)`, and ban the three-argument form on ORM types with a small AST test.
- **Verify:** `grep -rn 'getattr(user, "' apps/api/app --include=*.py | grep -v tests` returns nothing.
- **Source:** raw/agent-clar.md CLAR-06

<a id="clar-12"></a>

#### CLAR-12 — Five pagination shapes across five list endpoints
- **Severity:** Low · **Confidence:** High · **Effort:** M
- **Locations:** `apps/api/app/modules/chat/api.py:51-60`, `apps/api/app/modules/chat/api.py:180-193`, `apps/api/app/modules/chat/service.py:34`, `apps/api/app/models/schemas/chats.py:72-79`, `apps/api/app/models/schemas/chats.py:94-96`, `apps/api/app/modules/todos/api.py:25-38`, `apps/api/app/modules/todos/api.py:42-52`, `apps/mobile/features/todos/api.ts:14`, `apps/api/app/modules/attachments/api.py:58-66`, `apps/api/app/modules/attachments/schemas.py:47-49`, `apps/api/app/modules/search/api.py:16-31`
- **Evidence:** The endpoints use three list keys, three continuation signals and three cursor kinds, and `GET /chats` (limit ≤ 200, no continuation signal) never shows the 201st chat in the drawer. Lead check: cited code read at the listed lines.
- **Impact:** Every client writes a pager per endpoint, and offset paging over lists that change while you page (attachments, search) repeats or skips rows.
- **Fix:** Add one `Page[T] = {items, next_cursor}` schema and a keyset helper in `apps/api/app/repositories/`, move attachments and search to it, give `/chats` a `next_cursor`, and retire the bare-list `GET /todos` once no installed client calls it.
- **Verify:** An architecture test checks that every `GET` returning a list declares `response_model=Page[...]`.
- **Source:** raw/agent-clar.md CLAR-11

<a id="clar-13"></a>

#### CLAR-13 — Stale comment references and changelog-style comments
- **Severity:** Low · **Confidence:** High · **Effort:** S
- **Locations:** `apps/mobile/lib/math/cameraPrompt.ts:1-4`, `apps/api/app/core/config.py:85`, `apps/api/app/modules/memory/consolidation.py:3-4`, `apps/api/app/gateways/image_gateway.py:83`, `apps/api/app/modules/images/generation.py:337`, `apps/api/app/services/reminder_timing.py:66-67`, `apps/api/app/modules/chat/stream_api.py:62`, `apps/api/app/core/settings/stem.py:25`, `apps/mobile/lib/math/latexCommands.ts:88`, `apps/mobile/lib/markdown/preprocessMathInline.ts:27`, `apps/mobile/lib/math/textMarkers.ts:3`, `apps/api/app/modules/math/solve/parse.py:129`, and 12 more (see raw/agent-clar.md CLAR-12)
- **Evidence:** 16 comment paths name deleted files, among them a "byte-for-byte identical" camera-prompt contract and the dev-auth guard pointer, and 19 `BUG FIX:` comments narrate history. Lead check: cited code read at the listed lines.
- **Impact:** A reader who follows the camera-prompt contract or the dev-auth security pointer finds nothing, and history comments age into wrong claims.
- **Fix:** Repoint the 16 paths, pin the camera prompt with a shared fixture in `docs/fixtures/`, rewrite `BUG FIX:` notes as present-tense reasons, and run the two stale-path scripts as a test.
- **Verify:** `raw/scratch-clar/stale_paths.py` and `raw/scratch-clar/stale_paths_ts.js` report 0, and a cross-side test reads `MATH_CAMERA_PROMPT` from one fixture.
- **Source:** raw/agent-clar.md CLAR-12

<a id="clar-14"></a>

#### CLAR-14 — Naming and constants: `GoogleAuthError` as the app-wide auth error, 1,120 cross-file `_private` imports, limits retyped with different values
- **Severity:** Low · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/gateways/google_auth.py:29`, `apps/api/app/gateways/apple_auth.py:67`, `apps/api/app/core/access_tokens.py:98-108`, `apps/api/app/core/deps.py:47`, `apps/api/app/modules/chat/ws_api.py:272`, `apps/api/app/modules/account/api.py:143`, `apps/api/app/modules/physics/extractors/common.py`, `apps/api/app/modules/physics/solvers/common.py`, `apps/api/app/models/schemas/auth.py:125`, `apps/api/app/modules/chat/prompt_profile.py:109`, `apps/api/app/modules/speech/live_talk.py:183`, `apps/api/app/modules/todos/schemas.py:44`, and 17 more (see raw/agent-clar.md CLAR-13)
- **Evidence:** `GoogleAuthError` also covers Apple, JWT, refresh and dev-login failures (40 production references in 9 files), 1,120 `_private` imports cross files, and the custom-instruction and to-do limits differ between schema and readers (1000 vs 2000; 1000 vs 500). Lead check: cited code read at the listed lines.
- **Impact:** `core/` takes its auth error from a Google gateway, an underscore no longer marks a file-local name, and two values for one limit drift silently.
- **Fix:** Rename the error to `AuthenticationError` in `apps/api/app/exceptions.py` with `GoogleAuthError` as a Google-only subclass, un-underscore the 20 most-imported helpers and split each `common.py` by purpose, and define each limit once beside its schema.
- **Verify:** `GoogleAuthError` appears only in the Google gateway, the `raw/scratch-clar/private_imports.py` count trends down, and each limit has one definition.
- **Source:** raw/agent-clar.md CLAR-13

#### Metrics (from raw/agent-clar.md)
- **Function size, standards audit (8a20f147d) → now (d2ec42b0):** API production functions 5,202 → 6,004; over 50 / over 100 lines 378 / 87 → 378 / 61; nested deeper than 3: 105 → 98 (32 are deeper than 4 now). Phone functions (components and hooks included) over 50 / over 100 lines 359 / 137 → 374 / 119 (investigator's rule; the lead's count in §4, which takes named functions only, gives 330 / 104 now); phone nesting deeper than 3: 39 → 36.
- **API typing:** 1,161 `Any` references in 185 files (`dict[str, Any]` 257, `x: Any` 360, `-> Any` 80; maths SymPy code holds ~40 %); 49 `cast(` calls in 24 files; 30 `# type: ignore`, all with an error code, none with a reason, and ≥10 that suppress errors that no longer exist (CLAR-06).
- **Type-check reach:** mypy's strict flags cover 4.7 % of API production lines (8,601 of 183,369). Through lazy package `__getattr__`, mypy types 58 production imports in 28 files as `Any` (CLAR-06).
- **TypeScript (production):** 0 `any`; 213 `as` casts (non-`const`) and 104 `as const`; 1 `as unknown as` (`apps/mobile/lib/markdown/parser.ts:10`); 125 non-null `!` (worst: `apps/mobile/lib/markdown/preprocessMathFences.ts`, 17).
- **Suppressions:** 0 `@ts-ignore` and 0 `@ts-expect-error`; 29 `eslint-disable`, 13 without the one-line reason the standard requires; 13 API `# noqa`, 5 without a reason.
- **API broad `except Exception` / bare `except`:** 401 at the audit → 338 now. Handlers that neither log nor re-raise: 93 by the investigator's rule (the ticket counted 98) → 9 silent plus 6 that only use the exception value. 91 handlers log only at `logger.debug`, which is invisible because the root level is hard-coded to INFO (CLAR-02).
- **Phone `catch` clauses (production):** 263; 61 empty; 197 that neither log, toast nor rethrow, of which 72 carry a comment explaining the fallback.
- **Settings:** 209 fields; 0 declared twice, 0 never read, 0 read but undefined. One env read outside settings: `apps/api/app/modules/math/solve/declines.py:58`, the documented test strict mode.
- **Logging:** 500 API logger calls, 0 of them f-strings (a consistent `%s` style). 97 of the 305 WARNING+ calls pass no arguments (CLAR-10).

### H. Tests as an asset

<a id="test-01"></a>

#### TEST-01 — Test isolation from real services is opt-in per consumer: settings read `.env`, Redis is real by default, there is no network guard, and DuckDuckGo runs before mock results
- **Severity:** High · **Confidence:** High (mechanism) · **Effort:** M
- **Locations:** `apps/api/app/core/config.py:48`, `apps/api/app/tests/conftest.py:11-27`, `:57,93,105,127`, `apps/api/app/tests/security/conftest.py:225-228`, `:97-180`, `.github/workflows/api-ci.yml:60-68,72`, `apps/api/app/gateways/web_search_gateway.py:227-237`, `apps/api/app/core/settings/search.py:13`, `apps/api/app/tests/behavior/harness.py:176,185`, `apps/api/app/gateways/pubchem_gateway.py:154-257`, `apps/api/app/tests/modules/chat/test_chat.py:1339-1340`, `scripts/check.sh:20-26`
- **Evidence:** Every `Settings()` reads `apps/api/.env` (1,574 constructions in tests, 36 with `_env_file=None`; the root conftest neutralises four variables), so provider keys, `DATABASE_URL` and `REDIS_URL` flow in. 37 production modules call `get_redis_client()`, the root conftest fakes 4, and CI shares one real `redis:7`, never flushed. Nothing guards sockets (DuckDuckGo's `primp` client would bypass a Python guard anyway), PubChem has no mock gate, and the class is fixed per case: six isolation patches on 18–19 October alone. Lead check: read `core/config.py:48` (`env_file=".env"`) and `gateways/web_search_gateway.py:227-237` (DuckDuckGo fallback before `if settings.mock_llm_enabled`). The lead's runs logged `RuntimeWarning: coroutine 'Connection._cancel' was never awaited` inside unit tests in modules/account, modules/chat, services and the top-level area (real asyncpg pool touched).
- **Impact:** A developer's run is not CI's (failures documented both ways); a test can spend paid quota (Tavily, OpenAI speech, Mathpix) or call DuckDuckGo or PubChem from CI; shared Redis makes results order-dependent; every new Redis or HTTP consumer silently reopens the hole.
- **Fix:** Make isolation the default in `apps/api/app/tests/conftest.py`, before any `app` import: one test settings source (empty provider keys, `WEB_SEARCH_FALLBACK_ENABLED=false`, local test services, or an empty `env_file` under pytest); an autouse per-test FakeRedis on `redis.asyncio.from_url` plus `get_redis_client.cache_clear()` (lift `apps/api/app/tests/security/conftest.py:225-228`) with a `real_redis` opt-out; pytest-socket plus a patch that makes `ddgs.DDGS`/`primp` raise; a check that `DATABASE_URL` names a `*_test` database, also in `scripts/check.sh`. Then delete the per-consumer fixtures.
- **Verify:** Run the suite with network disabled (`unshare -rn` or pytest-socket) and with a `.env` holding bogus keys and `DAILY_TOKEN_LIMIT=1`: the pass count equals CI's.
- **Source:** raw/agent-test.md TEST-01

<a id="test-02"></a>

#### TEST-02 — Three tests cannot fail for the regression they are named for
- **Severity:** Medium · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/tests/modules/web_search/test_web_search_run.py:166-191`, `apps/api/app/modules/web_search/search_cache.py:139`, `apps/api/app/tests/modules/chat/test_ws.py:879-938`, `:941`, `apps/api/app/tests/test_services.py:369-388`, `:32-35`, `apps/api/app/modules/memory/text.py:230`, `apps/api/app/modules/memory/extraction_workflow.py:288-289`, `:315`, `apps/api/app/tests/modules/chat/test_chat_history_rag.py:448-532`
- **Evidence:** Search fan-out: the fakes sleep 0.04/0.01/0.01 s, so a serial `_run_search` also passes `assert elapsed < 0.08`, and no other test checks the `gather`. Done after finalize: `871ecfba3` replaced `assert elapsed < 4` with `assert elapsed >= 0.0`, so a `done` sent before the commit passes. Memory off: the transcript `"t"` is discarded as small talk before `revise_memory_facts`, so deleting the gate keeps the test green (an autouse fixture also forces `lock_memory_enabled` open). Lead check: read `tests/modules/chat/test_ws.py:937` (`assert elapsed >= 0.0`) and `tests/modules/web_search/test_web_search_run.py:186-191` (a serial run takes 0.06 s; the bound is 0.08 s).
- **Impact:** False confidence in three product promises: search fan-out latency, no "ghost done" with an unsaved message id, and "memory off means no personal recall" for a job queued before the switch flipped.
- **Fix:** Search: each fake waits on a shared `asyncio.Barrier(3)` inside `asyncio.wait_for(…, 1)`, as `apps/api/app/tests/modules/web_search/test_web_classifier_latency.py:159-188` does. WebSocket: assert `done` is not received while `release_finalize` is unset. Memory: a substantive transcript ("I live in Austin and work at Uber") asserting `revise_memory_facts` and `apply_memory_facts` were not awaited, plus a memory-on control. Then check the 945 tests whose only checks are negative for a missing positive control, starting with memory, consent, quota and billing.
- **Verify:** Mutate each guarded line (serial loop, `done` before the commit, gate deleted) and see each test go red.
- **Source:** raw/agent-test.md TEST-02

<a id="test-03"></a>

#### TEST-03 — `--assert=plain` hides every failing value; the crash it worked around was fixed in August
- **Severity:** Medium · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/pyproject.toml:73`, `.github/workflows/api-ci.yml:104-108`, `:45,117`, `scripts/check.sh:3,26`
- **Evidence:** The rewrite crash it avoided was later traced to the CPython 3.12.3 compiler and fixed by the `>=3.12.4` floor (`bb545e0d0`, 2026-08-12, #625; `apps/api/pyproject.toml:5-13`), and 13,199 of 15,410 asserts (85 %) are bare comparisons with no message. Lead check: demo with the audit venv: the same failing test prints `E AssertionError` under `--assert=plain` and `E AssertionError: assert {'plan': 'pro', 'limit': 90} == {'plan': 'pro', 'limit': 100}` plus the differing items with rewriting. The lead's first (stale-venv) chemistry failures showed only `E AssertionError`. The workaround (`9ede08cbf`, #7, 2026-07-01) also split CI's pytest run (`.github/workflows/api-ci.yml:104-108`); pytest is now 9.1.1.
  ```toml
  addopts = ["--assert=plain", "--import-mode=importlib"]
  ```
- **Impact:** Every red test, in CI or locally, needs a re-run with prints to see what differed, and a flaky CI failure's only log shows no values.
- **Fix:** Remove `--assert=plain` (keep `--import-mode=importlib`), collapse CI to the single pytest invocation `scripts/check.sh` uses, and drop the `ubuntu-22.04` pin if nothing else needs it.
- **Verify:** A deliberately failing `assert 1 == 2` prints `assert 1 == 2`, and CI is green with one pytest step.
- **Source:** raw/agent-test.md TEST-03

<a id="test-04"></a>

#### TEST-04 — Concurrency and lease tests assert on wall-clock time or fixed sleeps
- **Severity:** Medium · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/tests/modules/chat/test_turn_prep_parallel.py:234-333`, `apps/api/app/tests/core/test_jobs_inflight.py:209-236`, `:241-256`, `:136,167,202`, `:161`, `apps/api/app/tests/test_jobs.py:591`, `:450-471`, `apps/api/app/tests/modules/chat/test_chatprep_lock.py:475`, `apps/api/app/tests/modules/chat/test_finalize_registry.py:180`, `apps/api/app/tests/modules/chat/test_chat_history_rag.py:234-273`, and 6 more that are fine (see raw/agent-test.md TEST-04)
- **Evidence:** The prompt-build test's fakes sleep 0.25/0.25/0.30/0.30 s and it asserts `elapsed < 0.90`, so a ~0.35 s loop stall fails it; lease tests renew every 0.03 s against a 150 ms `_CLAIM_IDLE_MS`, so a 150 ms stall lets the "peer" reclaim; fixed `sleep(0.05|0.1)` "let it land" waits precede positive asserts, and fixed windows precede negative asserts that can only pass wrongly; the parallel-drain test times 4 × 0.15 s jobs although the test above it already proves concurrency with "all 5 started". Lead check: cited code read at the listed lines.
- **Impact:** On a busy runner (the team already saw macOS semaphore exhaustion when suites run in parallel) these fail with no code change, or get loosened until they test nothing (TEST-02's web-search case).
- **Fix:** Prove overlap with events (each fake sets `started[name]` and awaits a gate; assert all started before release, inside `asyncio.wait_for`), as `apps/api/app/tests/modules/web_search/test_web_classifier_latency.py:159-188` does; drive leases with an injected clock or by calling renew and reclaim directly; replace "let it land" sleeps with the existing `_wait_until(predicate)` helper (`apps/api/app/tests/core/test_jobs_inflight.py:48-53`).
- **Verify:** `grep -n "assert elapsed <"` finds only the documented linearity tests, and the touched files pass 50x under `stress -c $(nproc)`.
- **Source:** raw/agent-test.md TEST-04

<a id="test-05"></a>

#### TEST-05 — 2,910 string-path patches tie tests to import layout; production is shaped to keep them working
- **Severity:** Medium · **Confidence:** High · **Effort:** L
- **Locations:** `apps/api/app/modules/chat/turn_deps.py:1-8`, `apps/api/app/tests/modules/chat/chat_test_support.py:40-134`, `apps/api/app/tests/modules/chat/test_finalize_quota.py`, `apps/api/app/tests/modules/chat/test_ws.py`, `apps/api/app/tests/modules/chat/test_chat_stream_orchestration.py`, `apps/api/app/tests/services/test_tool_loop.py`, `apps/api/app/tests/modules/chat/test_chat_history_rag.py`, `apps/api/app/modules/billing/api.py:24-25`, `:126-127`, `apps/api/app/tests/test_routers.py:1747`, `apps/api/app/modules/todos/sync.py:103-106`, `apps/api/app/modules/memory/selection.py:1-6`, `apps/api/app/gateways/litellm_gateway.py:15-18`
- **Evidence:** 2,910 `patch("app....")` (66 on a private leaf), 530 `patch.object` (49 private) and 182 `monkeypatch.setattr` (27 private). CLAUDE.md says chat tests pass a `ChatTurnDeps` with fakes instead of patching, yet 343 string patches still reach into `app.modules.chat.*` (71 on per-module `SessionLocal`; the five test files above hold 33, 27, 24, 23 and 20), and the deps helpers are used in 25 files. Production keeps shims for patch targets: billing re-exports `_already_processed`/`_try_claim` and passes them back in so `apps/api/app/tests/test_routers.py:1747` still bites (left by `8b81a40dc`, #863); `apps/api/app/modules/todos/sync.py`, `apps/api/app/modules/memory/selection.py` and `apps/api/app/gateways/litellm_gateway.py` carry comments like "Resolve apply via package so tests can patch todos_service.apply_todo_actions". Lead check: cited code read at the listed lines.
- **Impact:** A move or rename breaks hundreds of tests, or leaves a patch on a name the code no longer reads so the real dependency runs (TEST-01); production keeps aliases and function-local imports nobody needs at runtime, and each module migration costs more per file.
- **Fix:** Finish moving chat stream tests onto `ChatTurnDeps` (`session_factory`, repos, quota), starting with the five files above; in billing tests pass `event_claim=`/`processed_check=` and delete the `api.py` aliases; add an architecture test that ratchets the count of `patch("app.…._private")` targets and of string patches into `app.modules.chat`.
- **Verify:** The count of string patches into `app.modules.chat` falls each release, and `grep -n "so tests can patch"` in `app/` returns nothing.
- **Source:** raw/agent-test.md TEST-05

<a id="test-06"></a>

#### TEST-06 — 209 assertions pin verbatim prompt copy
- **Severity:** Medium · **Confidence:** High · **Effort:** M
- **Locations:** `apps/api/app/tests/modules/chat/test_chat.py:112`, `:200-203` (44 asserts), `apps/api/app/tests/modules/chat/test_chat_teaching.py:191-194` (34), `apps/api/app/tests/services/test_compact_output_format.py:29` (21), `apps/api/app/tests/modules/chat/test_prompt_builder_style_hints.py:41` (19), `apps/api/app/tests/modules/chat/test_reply_shape_rules.py` (10), `apps/api/app/tests/modules/math/test_math_llm_extract.py:201` (9), `apps/api/app/tests/modules/math/test_math_tools.py:580` (8), `apps/api/app/tests/modules/chat/test_everyday_writing_routing.py:122` (8), `apps/api/app/tests/services/test_day_planning.py:72` (7), `apps/api/app/tests/modules/todos/test_service.py:661` (5)
- **Evidence:** 209 asserts in 33 files is a floor (only literals of ≥4 words or ≥25 chars found verbatim in files whose path contains "prompt"); suite-wide, 745 membership asserts use a ≥4-word literal against 281 that use a named constant. Beside them, `apps/api/app/tests/modules/chat/test_prompt_golden.py:1-13` stores prompts as `@CONSTANT_NAME` tokens: "Rewording a named constant leaves the fixture as it is; a change to which text a turn gets, or its order, fails here." Lead check: cited code read at the listed lines.
- **Impact:** Every wording change to a prompt constant turns a scatter of unrelated tests red, and the fix is re-pasting text, so these tests pin copy, not behaviour.
- **Fix:** Assert by identity (`assert EMAIL_DRAFT_HINT in system`) or through the golden test's token form; keep literal asserts only for safety phrases ("Never say you sent") and mark them so.
- **Verify:** The count from `tmp/code-audit/raw/scratch-test/prompt_copy.py` trends to the agreed safety-phrase list.
- **Source:** raw/agent-test.md TEST-06

<a id="test-07"></a>

#### TEST-07 — Copied fakes drift; the bare copies change the contract they fake
- **Severity:** Medium · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/app/tests/modules/attachments/test_repository.py:10-11`, `:28`, `apps/api/app/tests/modules/memory/test_repository.py:11-17`, `apps/api/app/tests/modules/todos/test_repository.py:20-21`, `apps/api/app/tests/repositories/test_push_tokens.py:10-11`, `apps/api/app/tests/repositories/test_chats.py:12-14`, `apps/api/app/modules/attachments/repository.py:80`, `:109`, `apps/api/app/repositories/push_tokens.py:94`, `apps/api/app/modules/chat/prompt_memory.py:100`, `apps/api/app/tests/modules/chat/chat_test_support.py:21`, `apps/mobile/jest.componentsSetup.js`, and 16 more (see raw/agent-test.md TEST-07)
- **Evidence:** `fake_session` is copied into 9 modules: 4 use `AsyncMock(spec=AsyncSession)`, 4 a bare `AsyncMock()`, which turns the synchronous `AsyncSession.add` into a coroutine, and `fake_session.add.assert_called_once()` also passes if the code wrongly writes `await session.add(row)`. Suite-wide, 267 `session = AsyncMock()` and 186 `user = MagicMock()` are unspecced against 59 spec'd mocks; an unspecced user reads as memory-on in `apps/api/app/modules/chat/prompt_memory.py:100`. 13 local session context-manager classes sit beside the shared one. On the phone, `react-i18next` is hand-mocked in 94 files (51 identical), and 103 local re-mocks repeat the global setup (17 `expo-haptics` copies drop its `ImpactFeedbackStyle` enum). Lead check: the lead's runs logged `coroutine 'AsyncMockMixin._execute_mock_call' was never awaited` at `modules/attachments/repository.py:80,109` (`session.add(row)` on a bare AsyncMock session).
- **Impact:** Tests pass against fakes that accept calls the real object rejects; fixing a fake means finding its copies, and reviewers cannot tell which copy is right.
- **Fix:** One `apps/api/app/tests/fakes.py` with `fake_session()` = `AsyncMock(spec=AsyncSession)`, `session_cm(session)`, `make_user(**overrides)` (a real `User` or `MagicMock(spec=User)`) and `test_settings(**overrides)` = `Settings(_env_file=None, **overrides)`; replace the copies and add an architecture test against new local `class _FakeSessionCM`. Phone: one `__mocks__/react-i18next.ts`, and delete local re-mocks that equal those in `apps/mobile/jest.componentsSetup.js`.
- **Verify:** Zero `coroutine ... never awaited` warnings from repository tests, and one copy per fake family.
- **Source:** raw/agent-test.md TEST-07

<a id="test-08"></a>

#### TEST-08 — The property-based-testing rule is applied to maths only
- **Severity:** Medium · **Confidence:** High · **Effort:** M
- **Locations:** `docs/ENGINEERING_STANDARDS.md:94`, `apps/api/app/tests/modules/math/test_math_properties.py`, `apps/api/app/tests/modules/math/test_math_triangle_laws.py:207`, `apps/api/app/modules/chemistry/equations.py:73`, `apps/api/app/modules/chemistry/nuclear.py:190`, `apps/api/app/modules/chemistry/quantity.py:41`, `apps/api/app/modules/physics/solvers/common.py:85`, `apps/api/app/services/number_text.py:157`
- **Evidence:** `grep -rl "from hypothesis" apps/api/app/tests` finds 2 files (9 + 1 `@given`) and none for physics or chemistry, although `balance_equation` (atoms conserved), `balance_nuclear` (A and Z conserved), `convert` (round trip), `quadratic_roots` (roots satisfy the equation) and `fold_scientific` have natural invariants. One property runs non-derandomised (`apps/api/app/tests/modules/math/test_math_properties.py:45`, `max_examples=100, deadline=None`) with no saved example database, so an unrelated PR can go red; that is how `@example(text="P❶")` (`:43`) was found. Lead check: cited code read at the listed lines.
- **Impact:** STEM correctness is a release requirement (`docs/ENGINEERING_STANDARDS.md:85`), but the STEM corpus checks chosen examples, not the invariants that make a whole family right.
- **Fix:** Add about six cheap properties for the functions above, and register a CI profile (`settings.register_profile("ci", derandomize=True)`), keeping random exploration local or nightly.
- **Verify:** `grep -rl "@given" apps/api/app/tests/modules/{physics,chemistry}` is non-empty and CI loads the `ci` profile.
- **Source:** raw/agent-test.md TEST-08

<a id="test-09"></a>

#### TEST-09 — No per-test or per-job timeout, and RuntimeWarnings that flag broken fakes are ignored
- **Severity:** Low · **Confidence:** High · **Effort:** S
- **Locations:** `apps/api/pyproject.toml:49-58`, `:69-73`, `.github/workflows/api-ci.yml`, `apps/mobile/jest.config.js`, `apps/api/app/tests/modules/web_search/test_web_search_run.py:474`, `apps/api/app/tests/test_jobs.py:932`, `apps/api/app/tests/test_gateways.py:1146`, `apps/api/app/tests/modules/web_search/test_web_classifier_latency.py:167,204,279,328`, `apps/api/app/tests/background/test_periodic.py:54,76,105`, `apps/api/app/modules/chat/stream_paths.py:311`, `apps/api/app/tests/modules/chat/test_ws.py::test_ws_passes_client_timezone_to_stream`, `apps/api/app/tests/gateways/test_external_timeouts.py`, and 2 more (see raw/agent-test.md TEST-10)
- **Evidence:** No `pytest-timeout` or CI `timeout-minutes` backs the 28 never-returning fakes in 15 files, and with no `filterwarnings` the lead's run shows warnings such as "coroutine ... never awaited" ×14 at `apps/api/app/modules/chat/stream_paths.py:311` passing silently. Lead check: cited code read at the listed lines.
- **Impact:** A broken timeout or cancel path hangs CI for hours (GitHub's default 360 min, blocking `scripts/require-green-ci.sh`) instead of failing one test, and each ignored warning marks a wrong fake or cleanup.
- **Fix:** Add `pytest-timeout` (`timeout = 60`, method thread), `timeout-minutes: 30` on the API and mobile jobs, and `filterwarnings = ["error::RuntimeWarning", "error::pytest.PytestUnraisableExceptionWarning"]` with explicit third-party ignores, then fix the ~20 offenders.
- **Verify:** A test awaiting `asyncio.Event().wait()` fails after 60 s, and the suite is green with the warning filter on.
- **Source:** raw/agent-test.md TEST-09, TEST-10

<a id="test-10"></a>

#### TEST-10 — Module tests in grab-bag files and leftover process state between tests
- **Severity:** Low · **Confidence:** Medium · **Effort:** S
- **Locations:** `apps/api/app/tests/test_routers.py:495-2108`, `:2269-3083`, `apps/api/app/tests/test_services.py`, `apps/api/app/tests/test_new_features.py`, `apps/api/app/tests/test_misc.py`, `apps/api/app/tests/test_mcp.py:222-235`, `apps/api/app/gateways/mcp/registry.py:15`, `apps/api/app/tests/test_apple_auth.py:138-178`, `apps/api/app/tests/test_auth_dev.py:9-17`, `apps/api/app/tests/services/test_quota.py:81,131,259,269,280`, `apps/api/app/tests/repositories/test_usage.py:25,41`, `apps/api/app/tests/behavior/sweep.py:263-299`, and 8 more (see raw/agent-test.md TEST-11, TEST-12)
- **Evidence:** 46 top-level files (13,117 lines) hold module tests, such as 27 RevenueCat webhook tests in `apps/api/app/tests/test_routers.py`, and several tests leave process state behind: a filled tool `_REGISTRY`, the Apple JWKS globals, `dev_auth_enabled` flipped on the cached settings without `try/finally`, and real-date reads beside the `quota_clock` fixture. Lead check: cited code read at the listed lines.
- **Impact:** `pytest app/tests/modules/billing` skips the webhook's idempotency and auth tests, and results can depend on test order or the time of day.
- **Fix:** Move tests to their owning modules with an allow-list architecture test for top-level files; restore registry, JWKS and settings state with `patch.dict`/`monkeypatch`; use `quota_clock`, and adopt time-machine or one injected clock.
- **Verify:** `pytest app/tests/modules/billing` collects the webhook tests, and `app/tests/test_mcp.py` with `app/tests/services` gives the same result in either order.
- **Source:** raw/agent-test.md TEST-11, TEST-12

<a id="test-11"></a>

#### TEST-11 — Mobile component tests are never type-checked
- **Severity:** Low · **Confidence:** High · **Effort:** S
- **Locations:** `apps/mobile/tsconfig.json`, `apps/mobile/package.json:106`, `apps/mobile/jest.config.js:62-66`
- **Evidence:** `apps/mobile/tsconfig.json` excludes `**/__tests__/**`, so `pnpm typecheck` skips every test, and the 209 `.test.tsx` files run through `babel-jest`, which strips types (the exclusion dates from bulk commit `fa9691358`, 2026-06-28). Lead check: cited code read at the listed lines.
- **Impact:** A renamed prop or changed hook shape keeps compiling in the tests that should catch it, and the 13 `as unknown as` mocks in `.test.tsx` files drift unseen.
- **Fix:** Add a `tsconfig.test.json` that includes `__tests__` and a `pnpm typecheck:tests` step in Mobile CI, or drop the exclude once errors are fixed.
- **Verify:** `tsc --noEmit -p tsconfig.test.json` exits 0 in CI.
- **Source:** raw/agent-test.md TEST-13

#### Critical-path branches with no test
- **Refresh for a deleted account** (`apps/api/app/modules/account/tokens.py:245-248`): the branch that revokes the refresh token with "User not found" has no test feeding `users_repo.get_by_id → None` into `refresh_token_pair` (checked `apps/api/app/tests/modules/account/test_tokens.py`, `apps/api/app/tests/modules/account/test_session_reliability.py`, `apps/api/app/tests/test_redis_unavailable.py`).
- **Memory cap eviction order** (`apps/api/app/modules/memory/ops.py:107-131`; `_CAP_EVICT_ORDER` at `:32`, profile facts with importance ≥0.75 protected at `:33,128`): no test calls `evict_for_cap`; the one cap test uses four `focus` facts.
- **RevenueCat transfer watermarks** (`apps/api/app/modules/billing/revenuecat.py:266-279,358-359`, `_advance_transfer_watermarks`): transfer tests patch `advance_rc_event_watermark` with a bare `AsyncMock()` and never assert it (`apps/api/app/tests/modules/billing/test_webhook_events.py:54`), so "an old EXPIRATION for the source account after a TRANSFER is ignored" is unverified.
- **RevenueCat event without `app_user_id`** (`apps/api/app/modules/billing/revenuecat.py:312-316`): a non-TRANSFER event with no `app_user_id` releases its claim and is dropped, and no test covers it.

### S. Security-adjacent notes (not a security audit)

What was checked, and held:

- **Route authentication.** All 87 HTTP and WebSocket routes were inventoried (`raw/scratch-lead/routes.tsv`). Every non-public route depends on `get_current_user` or `get_consented_user`. The public ones are deliberate:
  - sign-in, refresh and logout;
  - the RevenueCat webhook (shared secret);
  - the chat WebSocket, which takes the token in its first frame and re-verifies it on every chargeable frame (`apps/api/app/modules/chat/ws_api.py:234-276`, `:393`);
  - health and legal pages.
- **Admin routes.** `/admin/dlq*` requires `dev_auth_enabled` plus an `ADMIN_USER_IDS` allowlist (`apps/api/app/routers/admin.py:36-56`).
- **Cross-user isolation.** It has its own real-app suite (`apps/api/app/tests/security/test_cross_user_isolation.py`).
- **Outbound fetches.** Every fetch of a user-influenced URL (link preview, reference-photo mirror, image download) goes through `gateways/safe_fetch.py`, which checks each redirect hop and has an overall deadline. PubChem's URL host is fixed.

Security-adjacent findings in this report:

- [SCALE-01](#scale-01): denial of service by any authenticated free user, with one message.
- [CLAR-01](#clar-01): personal data in logs and Sentry.
- [LEAK-03](#leak-03): reminder text keeps reaching a signed-out phone.
- [LEAK-04](#leak-04): voice recordings survive sign-out.
- [SCALE-17](#scale-17): consent withdrawal lags up to 60 s on other machines.
- [CLAR-07](#clar-07): `TRUSTED_PROXY_CIDRS` differs between the code default and the production example, which decides whether per-IP limits key on the client.
- [SCALE-16](#scale-16): the export has no per-user limit.

## 6. Quick wins (high value, effort S)

| # | Change | Closes |
|---|---|---|
| 1 | One `CREATE INDEX CONCURRENTLY` migration (expand-only) for `memories(source_message_id)`, `memories(source_chat_id)`, `memories(superseded_by_id)`, `todo_items(chat_id)` and `message_chunks(chat_id)`. Use partial `WHERE col IS NOT NULL` where nullable. | [SCALE-02](#scale-02) |
| 2 | Make `_LABEL_GAP` linear (one character or word per iteration). Reject `**`/`^` towers whose exponent would exceed a bound before SymPy evaluates; decline on `ValueError`. Then add the timing tests. | [SCALE-01](#scale-01) (instance fixes; the class fix is roadmap theme 1) |
| 3 | End the auth dependency's read transaction: `await session.commit()` after `users_repo.get_by_id`, or load the user in a short `SessionLocal()` and `merge(load=False)`. One place covers every route. | [LEAK-01](#leak-01) part 1 |
| 4 | `jobs.unique_dedupe_key(f"compress:{chat_id}")` for the compress job, plus a test that a second compress for the same chat runs. | [SCALE-03](#scale-03) |
| 5 | One owner for "water only" (`physics/bodies.NOT_FRESH_WATER`, or a water-only law flag). Add STEM look-alikes: water + ethanol, + alcohol, + mercury, seawater. | [DUP-01](#dup-01) |
| 6 | Stop the thousands-separator rule joining across `", "` followed by a new equation, in both twins. Add `presentation_cases.json` rows for systems of equations. | [DUP-02](#dup-02) |
| 7 | Drop user text from the three log lines. Set `hide_parameters=True` on the engine. Scrub Sentry breadcrumbs and exception values in `before_send`. | [CLAR-01](#clar-01) |
| 8 | Exponential backoff with jitter (cap about 60 s) on the phone's degraded-connectivity probe; probe Google only when `/health` fails. | [NET-09](#net-09) |
| 9 | Record one health sample per attempted alias, measure time to first content, window samples by time, add a half-open probe. | [SCALE-04](#scale-04) |
| 10 | Unregister the push token on sign-out (phone), and delete push rows on logout and on logout-all (server). | [LEAK-03](#leak-03) |
| 11 | Remove `--assert=plain` and run CI's pytest in one invocation. | [TEST-03](#test-03) |
| 12 | Never `MAXLEN`-trim undelivered entries: trim at min(oldest pending, last delivered). Count what the hard cap drops. | [SCALE-06](#scale-06) |
| 13 | Delete the legacy `spend_mcents` read. Cache the health verdict per process for 2–5 s. Batch the two per-turn analytics events. Drop the unused `SELECT usage_daily`. | [NET-04](#net-04), [NET-15](#net-15), [NET-07](#net-07) |
| 14 | A per-turn document byte budget and sequential document reads (mirror `vision_input.py`). | [SCALE-05](#scale-05) |
| 15 | Fix the three vacuous tests (barrier-based concurrency check; assert `done` waits for the commit; substantive transcript plus a memory-on control). | [TEST-02](#test-02) |
| 16 | Delete recordings after transcription and on every discard path; release the recorder; add the recordings directory to the sign-out sweep. | [LEAK-04](#leak-04) |

## 7. Refactor roadmap

Themes in order. Each lists the findings it closes and its risk.

1. **Nothing unbounded on the event loop.** Close: [SCALE-01](#scale-01), [NET-01](#net-01), [LEAK-02](#leak-02), [SCALE-14](#scale-14), [SCALE-15](#scale-15), [ARCH-02](#arch-02).
   - First add a loop-lag heartbeat metric (a 100 ms task that logs lag over 250 ms), with pool and executor gauges.
   - Then run the maths, physics and chemistry readers and routing's physics solve inside a bounded, killable process pool behind the existing `BoundedSympyExecutor` seam, with a short timeout that declines.
   - Rank memory with `embedding <=> :q` in Postgres.
   - Give parsing and R2 their own bounded executors.
   - Risk: medium. Readers gain inter-process latency (measure p50 and p99 per phase before and after), and a per-user share for the pool changes fairness.
2. **Database hygiene for scale.** Close: [SCALE-02](#scale-02), [LEAK-01](#leak-01), [NET-02](#net-02), [NET-03](#net-03), [NET-07](#net-07), [NET-08](#net-08), [SCALE-10](#scale-10), [SCALE-11](#scale-11), [SCALE-12](#scale-12), [SCALE-20](#scale-20), plus the JSON-embedding contract step of [NET-01](#net-01).
   - Expand/contract migrations (`docs/ROLLBACK.md`).
   - Fewer sessions per turn; ping only connections that sat idle.
   - User-scoped vector search; a retention job; drop redundant indexes after a week of `idx_scan` = 0.
   - Risk: low to medium. Index builds must be `CONCURRENTLY`, and column drops wait one release.
3. **Background work never silently lost.** Close: [SCALE-03](#scale-03), [SCALE-06](#scale-06), [SCALE-07](#scale-07), [SCALE-09](#scale-09), [SCALE-18](#scale-18), [SCALE-21](#scale-21).
   - Per-enqueue keys, delayed retries with backoff (a Redis sorted set), a backlog-lag metric, rate-based DLQ alerts, and unknown types left pending instead of dead-lettered.
   - Risk: medium. Job semantics change, so a fakeredis worker test is needed for each rule.
4. **Observability and graceful degradation.** Close: [SCALE-15](#scale-15), [SCALE-04](#scale-04), [SCALE-13](#scale-13), [CLAR-02](#clar-02), [CLAR-10](#clar-10).
   - Saturation metrics, a correct breaker, and one deadline for the pre-first-token phase.
   - Log swallowed errors at WARNING with ids; a request id for WebSocket turns and jobs.
   - Risk: low.
5. **Privacy hygiene.** Close: [CLAR-01](#clar-01), [LEAK-03](#leak-03), [LEAK-04](#leak-04), [SCALE-17](#scale-17), and the expo-image cache question.
   - Risk: low.
6. **One owner per rule (STEM and text).** Close: [DUP-01](#dup-01), [DUP-02](#dup-02), [DUP-03](#dup-03), [DUP-04](#dup-04), [DUP-05](#dup-05), [DUP-06](#dup-06), [DUP-07](#dup-07), [DUP-08](#dup-08), [DUP-09](#dup-09), [DUP-10](#dup-10), [DUP-14](#dup-14).
   - Pin each with STEM-sweep or presentation-corpus rows first, then collapse the copies. Several changes are intended behaviour fixes.
   - Risk: low to medium.
7. **Phone network discipline.** Close: [NET-09](#net-09) through [NET-19](#net-19).
   - One "app resumed" coordinator with a freshness rule per resource; token-independent effects; WebSocket token refresh; conditional requests; analytics batching.
   - Risk: low.
8. **A hermetic test suite with clear failure signals.** Close: [TEST-01](#test-01) through [TEST-11](#test-11).
   - Default-deny network, a per-test fake Redis, a test-only settings source, plain asserts off, one shared fake library.
   - Risk: low, though the suite may turn up hidden leaks when isolation becomes the default.
9. **Boundaries and typing.** Close: [ARCH-01](#arch-01) through [ARCH-12](#arch-12), [CLAR-03](#clar-03), [CLAR-04](#clar-04), [CLAR-05](#clar-05), [CLAR-06](#clar-06).
   - Extend the public-surface test to callers outside `modules/`; widen mypy strict package by package; extract the phone chat state machine; split the radon-F STEM extractors.
   - Risk: medium. These are large refactors; do them in small, tested steps.
10. **Bloat.** Close: [DEAD-01](#dead-01) through [DEAD-11](#dead-11).
    - Retire unused routes; delete paths behind non-production flags; ship vendor libraries as on-demand assets.
    - Risk: low. Vendor assets must still load inside the sandboxed WebView offline.

## 8. What's already good (keep it)

- **Rules enforced, not just written.**
  - `apps/api/app/tests/architecture/` (module boundaries, public files, import cycles, retired paths, pure solvers, migration safety, schema matches migrations) and the file-size ratchet run in CI.
  - The ES-01 to ES-45 standards programme was actually executed.
- **Clean gates.** ruff, ruff format, mypy, tsc and ESLint report no errors; no TypeScript `any`; no f-string logging; settings live in one place (209 fields, none unread).
- **The chat turn is well built.**
  - Short per-step sessions, parallel loads, `turn_resources` owning quota and the prepare lock, a finalize registry with a Redis marker, cancel-safe saves.
  - WebSocket auth by first frame, plus re-verification on every chargeable frame.
  - An owned, typed `ChatTurnDeps` for tests.
- **Durable jobs done carefully.** Lease keep-alive (`XCLAIM … JUSTID`), running and done dedupe claims, poison-entry dead-lettering, cancel-safe deploys, scheduler locks.
- **Gateways.** Pooled clients with named timeouts, `safe_fetch` for user-influenced URLs, a timeout on every outbound call, Redis clients without hidden retries.
- **Tests as a product asset.**
  - 25.6k API tests and 7k phone tests, fast and green, at 91.9% coverage; critical areas ≥ 90%.
  - The behaviour battery and sweep, and STEM corpora judged by SymPy, with coverage floors that only go up.
  - A real-app cross-user isolation suite.
- **Phone hygiene.**
  - An AST scan found no effect that registers a listener, timer, socket or player without cleanup.
  - Session-fenced caches (`lib/cache/sessionResource.ts`), FlashList everywhere, transports closed on chat switch.
  - Attachment, scan and TTS files swept.
- **Honest documentation.** SCALING.md, ARCHITECTURE.md and PRODUCTION.md state per-machine trade-offs, budgets and runbooks. This audit could check them claim by claim (§5.F), which most codebases cannot offer.

## 9. Looked wrong, actually fine

**Architecture and dead code**

- **Composition roots import module internals** (`apps/api/app/main.py`, `process_bootstrap.py`, `background/handlers.py`, `services/mcp/__init__.py`, `models/orm/__init__.py`). ARCHITECTURE.md names exactly these as the places that connect infrastructure and modules.
- **Leaf modules import the `app.modules.chat` package** (web search detection, physics direct replies, maths follow-ups, to-do classification, live talk). This is the documented, lazy back-edge (ARCHITECTURE.md §13).
- **Phone egress that skips the API client** (Live Talk SDP, the connectivity probe, presigned R2 PUTs, attachment bytes, the PDF preview XHR). Each one goes to a host or protocol the API client is not for, by design.
- **Fourteen single-implementation `Protocol`s in `modules/chat/turn_deps.py`.** They are the documented `ChatTurnDeps` test seam, not speculative interfaces. `StorageGateway` (2 implementations) and `ToolAdapter` (4) are real interfaces.
- **Always-on kill switches** (`chemistry_enabled`, `chat_history_rag_enabled`, `history_compression_enabled`, `semantic_memory_enabled`). Each is one early return, the pattern ARCHITECTURE.md prescribes. Only [DEAD-02](#dead-02)'s three hide whole alternative paths.
- **Routes with no app client on purpose:**
  - dev-only `/chats/usage/today/reset` and `/auth/me/pro-dev` (behind `require_dev_privilege_access`);
  - `/admin/dlq*`;
  - `/legal/delete-account` (the store-listing deletion URL);
  - `/webhooks/revenuecat`.
- **Tool "unused" hits, all checked and all false.**
  - vulture: 112 of 112 are test idioms or framework hooks.
  - knip: unused files, dependencies and vendored exports are used indirectly (Expo config plugins, `lucide-static` by `pnpm icons`, `react-native-vision-camera-worklets` by `useFrameOutput`).
  - depcheck: 0 of 7 confirmed.
  - deptry DEP002: `asyncpg` is the SQLAlchemy driver, `websockets` serves uvicorn's WebSocket, `python-multipart` handles FastAPI forms, `cryptography` signs PyJWT ES256 for Apple, `defusedxml` is used by openpyxl.

**Duplication**

- **jscpd's numbers.** 78 groups, 20 of them real logic. The other 58 are catalog rows and data tables (19), look-alike diagrams and JSX (12), signatures (9), import blocks (8), facades (4), style sheets (4) and detector artifacts (2). The "javascript 1.82%" row is 277 `.tsx` files tokenized a second time: only `lib/webrtcStub.js` and `lib/easBuildConfig.js` are real JavaScript.
- **Shared seams that differ on purpose.** The three `/scan/read` endpoints are thin over `services/scan_read.read_scan`. The maths, physics and chemistry fence passes share `services/answer_fence`, `services/answer_check` and `services/workout`. Push and email skip recurring rows differently on purpose (`a6d0773e2`).
- **Re-checked and holding.** No ES-01 rounding or ES-09 number-literal stragglers. The repository `if commit: … else: flush()` tail is the documented transaction convention.

**Leaks and lifecycle**

- **The chat turn's own lifecycle is clean.**
  - The WebSocket producer is registered and always awaited, and the receivers are cancelled and awaited.
  - The prepare lock's refresh task is cancelled and the lock released in `finally`.
  - Finalize-registry entries leave by done-callback, with a 30 s marker fallback.
  - The per-user socket count is decremented in `finally`.
- **Background tasks** are strongly referenced, drained for 10 s, then cancelled at shutdown. The jobs consumer cancels and awaits every job and its lease loop.
- **The SymPy pool** returns its slot on every path, kills and replaces timed-out or broken workers, and its workers exit with their parent.
- **In-process caches are bounded:** user `TtlCache` 5,000, chat `TtlCache` 10,000, and every `lru_cache`. Pooled httpx clients close at shutdown; per-call clients use `async with`.
- **Phone effects, transports and WebViews.** An AST scan found no effect that registers a listener, timer, socket or player without a cleanup. The WebSocket closes on chat switch, on unmount and when idle in the background. WebView mount tickets are always released.
- **DNS is not on the starved executor.** uvloop resolves names on libuv's own pool, so [LEAK-02](#leak-02) does not reach httpx, asyncpg or Redis lookups.

**Network and I/O**

- **No ORM N+1.** Nothing iterates relationships, and an async lazy load would raise rather than issue N queries.
- **Every message read is bounded.** The window, regenerate and page reads all carry `LIMIT` (measured SQL text), so no turn loads a whole chat history.
- **The turn's independent loads already overlap.** User, chat, quota probe, window and model health run in one `gather`.
- **The six model-health reads run concurrently**, so they cost Redis commands, not latency.
- **No extra model call on an ordinary turn.** The web-search classifier is off in production, and the tool loop runs only for search, unsolved maths, photo lookup or image generation.
- **Every outbound call is bounded:** LiteLLM connect, idle and wall-clock limits; `asyncio.timeout` on structured, tool, vision and embedding calls; named httpx timeouts; R2 5 s / 20 s × 3; Redis 5 s; DB 10 s connect, 120 s command, 5 s pool.
- **Redis does not retry silently.** `from_url` builds the pool with `Retry(0)`.
- **Start-up REST reads are cheap (measured).** Warm `/auth/me` runs 0 SQL; `/chats`, `/chats/{id}/messages` and `/todos` take 1–2 statements.
- **The phone does not hammer the API in these places:**
  - uploads go through `expo/fetch` with no base64 bridge;
  - no retry or reconnect loops;
  - drawer search is debounced, aborted and paged;
  - the attachment-status poller backs off from 2 s to 15 s and pauses offline;
  - nothing is sent per keystroke or per streamed token.

**Scalability and reliability**

- **A 900 s job cannot run twice against a 60 s reclaim.** `XCLAIM … JUSTID` resets the entry's idle time every 20 s, and the running claim is refreshed every 150 s.
- **A crash or deploy mid-job** leaves the entry pending and releases only a claim the run owned. An entry delivered more than 5 times is dead-lettered.
- **The `MINID` trim path is safe.** Only the `MAXLEN` fallback and the hard cap drop work ([SCALE-06](#scale-06)).
- **Billing reconcile refreshes its lock after every user** and stops if the lock is lost.
- **Every Redis `SET` has a TTL** (58 calls, all with `ex=` or `keepttl=`). The gaps are only [SCALE-19](#scale-19)'s increment and set pairs.
- **Streaming backpressure holds.** uvicorn waits on `writable` and pings every 20 s. The SSE queue holds at most one reply, and the middleware passes the body through zero-buffer streams.
- **No hidden LLM retries**, and the physics symbolic parser is bounded and runs only inside the killable SymPy pool.

**Clarity**

- **338 broad excepts remain** (401 at the standards audit). The 9 fully silent ones are narrow, documented fallbacks, such as the fail-closed SSRF guard.
- **Settings are read only through `get_settings()`.** The one direct env read is the documented test strict mode.
- **Datetime handling:** all timestamps are aware UTC; no `utcnow()` and no naive `now()`.
- **Logging style is consistent:** `%s` formatting, `__name__` loggers, no f-strings, no `print`. Internal errors reach users only as a generic message.
- **TypeScript:** 0 `any`, 0 `@ts-ignore`. The phone's Sentry scrubber is stricter than the API's.

**Tests and security**

- **0 open `gap` entries.** The strict xfails in the battery, sweep and STEM corpora go red when a gap is fixed. The 7 jest skips are placeholders for documented phone gaps, and the next test still asserts the phone refuses those inputs.
- **`db_session` isolates each test** with an outer transaction and savepoints. The security "world" commits on purpose, with uuid-unique accounts deleted on teardown.
- **The wall-clock regex-linearity budgets** are 10–100× a linear run and documented.
- **`InsecureKeyLengthWarning` in tests is test-only.** Production refuses a `JWT_SECRET` under 32 characters (`validate_production_settings`).
- **Route auth, the admin gate, SSRF protection and WebSocket auth all hold** (§5.S).

## 10. Open questions for the team

1. **Database placement and versions.**
   - Which Postgres major version and which pgvector version run in production? This decides how [SCALE-10](#scale-10) fails and whether `hnsw.iterative_scan` exists, and whether [SCALE-08](#scale-08)'s partial index is usable.
   - What is the iad → Neon us-east-2 round-trip time, and does Neon's pooler run in transaction mode and drop idle clients? This sizes [NET-02](#net-02) and [LEAK-01](#leak-01).
   - Would a Neon project in us-east-1, next to Fly `iad`, be worth more than the Neon Storage option CLAUDE.md keeps open?
2. **Indexes added by hand.** Do production indexes exist that migrations do not create? That changes [SCALE-02](#scale-02)'s urgency, not its fix.
3. **Compression's 24 h suppression.** Was it ever meant as cost control ([SCALE-03](#scale-03))? The compaction code says the opposite.
4. **Model-health threshold.** Was the 30 s p50 meant as time to first token ([SCALE-04](#scale-04))?
5. **Worker throughput.** One worker at `JOBS_WORKER_CONCURRENCY` 8 clears about 100 LLM-bound jobs a minute; peak post-turn volume at 100k DAU is thousands a minute. Is the plan more workers or higher per-worker concurrency? [SCALE-06](#scale-06)'s backlog metric is needed either way.
6. **Chat-history retention.** Should chat-history recall search a user's whole history forever? This product decision sets [SCALE-11](#scale-11)'s retention.
7. **Finalize marker TTL.** The `chatfinal:{chat}` marker lives 30 s, but a statement may run 120 s. Under a slow database, another machine can start the next turn before the previous reply commits. Is that acceptable?
8. **Usage numbers that size the findings.**
   - Facts per active user, p50 and p95: sizes [NET-01](#net-01).
   - Share of turns over SSE, and each machine's user-cache hit rate: sizes [LEAK-01](#leak-01).
   - The Upstash plan (per-command billing or fixed): sizes [NET-04](#net-04) and [SCALE-18](#scale-18).
9. **Edge behaviour.**
   - Does Fly's proxy gzip responses? `main.py` has no compression middleware.
   - Does Fly count each open chat WebSocket against `hard_limit = 200`?
   - Is `TRUSTED_PROXY_CIDRS` set in Fly secrets ([CLAR-07](#clar-07))?
10. **SSE disconnects.** Does SSE disconnect detection work through the two `BaseHTTPMiddleware` layers? `watch_disconnect` probes `receive` inside a cancelled scope. One full-app test, or converting both middlewares to plain ASGI, settles it.
11. **Data left on the phone after sign-out.** Should sign-out also clear expo-image's disk cache? Chat images and gallery tiles use `cachePolicy="memory-disk"`. This is the same gap class as [LEAK-04](#leak-04).
12. **Reminders spoken in Live Talk.** Live Talk applies spoken reminder changes without a tap (`modules/speech/live_talk.py:361`), while typed chat needs one (`reminder_proposals_enabled`). Is that intended?
13. **Intercept turns.** Image-generation and photo-lookup turns enqueue no post-turn jobs (no memory, no `message_index`), and they don't move the chat up the drawer ([ARCH-08](#arch-08)). Deliberate?
14. **Old builds.** Are any pre-2026-09-04 internal builds still in testers' hands? If not, [DEAD-07](#dead-07)'s migrations and [DEAD-01](#dead-01)'s tombstones can go before the first store build.
15. **The web-search classifier.** Is it coming back? If not, delete it; if so, turn it on in production. Either way, should tests and the behaviour harness run the production setting ([DEAD-02](#dead-02), [CLAR-07](#clar-07))?
16. **Privacy defaults.** `memory_switch_on` treats a not-yet-loaded account row as memory on. Is fail-open the intended default for a privacy switch ([CLAR-11](#clar-11))?
17. **Function-local imports.** There are 542 function-local `app.*` imports against the tickets doc's "about 8". Is a deferred import now the standard way to break a cycle ([ARCH-11](#arch-11))?
18. **Boot-time network dependency.** LiteLLM fetches its remote cost map at import, with retries, before falling back to the bundled copy. Recall prices from its own catalog, so should `LITELLM_LOCAL_MODEL_COST_MAP=True` remove this dependency on GitHub?
19. **Developer `.env`.** Does `./scripts/dev.sh check` on developer machines run the suite against the Neon and Upstash dev services named in `apps/api/.env` ([TEST-01](#test-01))?
20. **RevenueCat on launch.** Does the first CustomerInfo event in a process trigger `/auth/me/sync-subscription`, and so one RevenueCat REST call, on every launch (`apps/mobile/lib/purchases.ts:203-218`)?

## Appendix: raw evidence and how to re-run it

All in this folder (`docs/audits/2026-10-20-code-health/`). Raw outputs are kept verbatim, so they still name the container paths: `/home/user/recall-audit` is the audit worktree at `d2ec42b0`, and `/home/user/recall/tmp/code-audit/` is this folder.

- **Working notes and verification**
  - `notes.md`: running notes.
  - `verified.md`: what the lead checked for each finding.
  - `final-mapping.md`: the final IDs, severities and sources.
- **Investigator reports, one per dimension:** `raw/agent-{arch,dup,leak,net,netm,dead,scale,rel,clar,test}.md`. Each has full evidence, history and every location.
- **Tool output**
  - API: `raw/ruff.txt`, `raw/mypy.txt`, `raw/radon-cc.txt`, `raw/radon-mi.txt`, `raw/vulture.txt`, `raw/pylint-dup.txt`, `raw/deptry-prod.txt`.
  - Phone: `raw/typecheck.txt`, `raw/lint.txt`, `raw/knip.txt`, `raw/depcheck.txt`.
  - Both: `raw/file-sizes.txt`, `raw/jscpd.txt`.
- **Test runs**
  - API per area: `raw/pytest/` (summary and durations). The first run on the stale venv is in `raw/pytest-stale-venv/`.
  - Coverage: `raw/coverage/full.txt` and `raw/coverage/by-file.tsv` (full suite, per file) and the per-area runs.
  - Phone: `raw/jest.txt`.
  - Slowest tests: `raw/pytest-slowest.txt`, `raw/jest-slowest.txt`.
- **Measurements**
  - `raw/io-counts.json`: SQL and Redis per request.
  - `raw/sql-text.json`: the turn's SQL.
  - `raw/wire-roundtrips.json`: checkouts, pings, BEGIN, ROLLBACK and COMMIT.
  - `raw/pool-during-stream.json` and `raw/idle-in-transaction.json`: [LEAK-01](#leak-01).
- **Scripts**
  - `raw/scratch-lead/test_zz_audit_io_counts.py`: the measurement test. To re-run, copy it into `apps/api/app/tests/security/` and run it with `pytest` against a test database; it uses that folder's `world` fixture. Don't commit it.
  - `raw/scratch-lead/redos_probe.py`: the [SCALE-01](#scale-01) physics timing. Run it in a subprocess with a timeout.
  - `raw/scratch-lead/routes.tsv`: the route-auth inventory.
  - Each investigator's scripts are in `raw/scratch-<dimension>/`.
- **Not committed** (bulky machine output, regenerable with the scripts above): jest's JSON results, coverage's `full.json`, jscpd's HTML report, the deptry run without packages, scratch files over 100 KB and the section drafts. `raw/depcheck.txt` keeps only its dependency keys.
