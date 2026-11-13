# Physics and STEM review — 2026-11-12

Baseline: `main` at `2cb3346` (12 Nov 2026, 0 commits behind `origin/main`). It includes the
decider read from 10–11 Nov. Every claim below cites a file, a command, or a measured run.
Anything not measured is marked **not verified**.

## Verdict

| Question | Answer | Evidence |
|---|---|---|
| Are physics answers correct? | **Yes, when the server answers.** 41 of 44 fresh numeric questions got a checked answer, and none was wrong. Across 64 rewordings and probes, no checked answer was wrong either. | §1.1, §1.4 |
| Is the answer clean and easy to follow? | **Mostly.** The layout is the same every time (Given → Required → Solution → law → Substitution → Answer card). But 6 presentation defects recur: unit notation that is mathematically wrong, conversions shown then never used, undefined symbols, inconsistent rounding, and awkward stock phrases. | §1.2 |
| Does it animate when it should? | **When the server solves, yes.** 16 of the 18 questions that needed a picture got one, plus 7 more where a picture helped. **When the server can't solve, never.** The model is told `Do NOT emit … simulation`, so those replies are plain text even for a projectile. | §1.3 |
| Is it robust? | **No, and this is the main weakness.** The numbers come from word patterns. 16 of 24 natural rewordings solved (67%), and 0 of 6 non-English questions did (the app ships 9 languages). The decider does not change this: it picks the lane and the layout, not the numbers. | §1.4 |
| Is the code clean? | **Safe, but heavy.** No resource leaks, almost no dead code, low copy-paste. The weight is elsewhere: about 2,000 hand-written regexes reading English, 13 functions graded F for complexity in physics alone, an extractor order that silently matters, two SymPy cold starts of 0.3–2.7 s on the request path, and one Pint hot spot worth about 45% of read time. | §2 |
| Add a subject tomorrow? | **At review time it would not "just work"**: a test subject wired through the documented seam was read correctly, then silently never solved. **Fixed the same day (§6):** the same test subject now solves with only the seam files plus its adapter, and a completeness test fails if a subject misses something chat asks. A subject the decider, scanner or model reader should know still needs those measured prompts and lists edited, and tests flag each one. | §3.1, §6 |
| Add or remove a model tomorrow? | **Adding works**: 3 files (catalog plus 2 guard tests), 4 with Auto routing; no mobile change. **Removing is unsafe**: catalog-only removal fails 25 tests, and users whose saved model was removed can neither send messages nor fix their settings until a data migration rewrites the saved value. A lane naming a removed model causes a `KeyError` at runtime. | §3.2 |

## How this was tested, and its limits

- **The 50 questions are new.** I wrote them for this review and worked the answers independently from the textbook formulas (g = 9.81 m/s², CODATA constants, `questions.json`). Two had matched existing corpus prompts word for word, so I reworded them. The mix is 44 numeric, 3 conceptual, 2 under-specified ("should decline") and 1 everyday look-alike. 18 are tagged with the picture a student would want.
- **They ran through the real chat path, offline:** `app/tests/behavior/harness.py` `route_case` → finalize, judged by `stem_sweep.judge`. That is the same code that writes production's server replies. Command: `run_questions.py`.
- **No model ran.** This container has no OpenRouter key; the stored environment setting could not be approved from the phone. A turn the server solves is written entirely by the server (`instant=solver`), so those 40 replies are exactly what a student sees. For the 10 turns a model would write, I report what the model is *given* (its system prompt and verified blocks), not what it would say. The conceptual answers (q45, q46) and the declines (q48, q49) were therefore **not judged**.
- **The decider is not exercised offline.** Its call is a model call, so the harness falls back to word rules. The model shown for model-written turns (`qwen-3.7-flash`) is the rules' pick. In production the decider would read these turns as physics and route them per `models/routing_lanes.py` (commit `81b92ba`: STEM on DeepSeek, Free STEM on Qwen). I checked that the decider has no path into the numbers or the pictures: `modules/chat/decided_turn.py:1-22` decides the lane, thinking, ```` ```worked ```` layout and follow-up notes. Nothing in `modules/physics/` or `chat/turn_prep/reading.py` reads it.
- **Regression baseline before testing:** `stem_sweep physics` on the repo corpus gave 1,596 turns, 1,049/1,146 answered, and 16 wrong, all 16 of them known `gap` entries. `pytest app/tests/modules/physics app/tests/behavior/test_stem_sweep.py` gave **12,255 passed, 16 xfailed** in 9 m 25 s.

## 1. The 50-question physics test

### 1.1 Accuracy

| Result | Count |
|---|---|
| Numeric questions with a checked answer | **41 / 44** |
| Wrong checked answers | **0** |
| Unsolved (handed to the model, no check) | 3: q06 package dropped from a plane, q21 orbital speed given Earth's radius, q26 "How long are its radio waves?" |
| Two-part question (q44) | Both parts checked (11.5 m; 3.06 s). The model writes around the two verified blocks, and the server adds the animation. |
| Look-alike (q50, phone battery) | Not read as physics ✔ |
| Server time per turn (route + finalize, offline) | median **58 ms**, max 414 ms (the first turn, cold) |

Every checked value was compared at 1% in any unit of the same kind (`same_quantity`). Full table: `results.json`.

### 1.2 Is the answer clean and easy to understand?

**Good:** the layout is identical across all 40 server-written replies, and "where" lines name every symbol. The law has a heading ("Inclined-plane force equation") and an assumption line ("Assumes constant g, no air resistance…"). Units are carried through the substitution, and the answer card is marked `verified: true`. The median reply is 526 characters of prose, which is short and scannable.

**Defects a student would notice** (each quoted from the actual reply in `results.json`):

| # | Defect | Example | Where it comes from |
|---|---|---|---|
| D1 | Unit notation that is mathematically wrong | q33: `q₁ = 3 µC × 10⁻⁶ = 3 × 10⁻⁶ C`. Read literally, `3 µC × 10⁻⁶` is 3 × 10⁻¹² C. Also q41 `80 g × 0.001`, q43 `30 cm × 0.01` | Deliberate format, `modules/physics/direct.py:240-247` docstring ("500 nm × 10⁻⁹ = 5 × 10⁻⁷ m"). Should be `3 µC = 3 × 10⁻⁶ C`. |
| D2 | Conversions shown, then never used | q41 (half-life) converts 80 g → 0.08 kg and 5 days → 4.32 × 10⁵ s, then substitutes `80/2⁴` in grams | Given rows are written by SI rule, not by what the substitution uses |
| D3 | Undefined symbol | q41 writes `N = N₀/2ⁿ`, then `2⁴`; `n = t/T½ = 4` never appears | The working skips the step |
| D4 | Wrong or awkward stock phrases | q35 says "Solve for ΔT" when nothing is solved for, and `ΔT = 60` has no unit. q35 and q43: "τ = F d — the same law for these quantities" | `direct.py:234` |
| D5 | Inconsistent precision | Working shows 6 significant figures (`0.939693`, `31.0357 m`, `6.28319`), while answer cards range from 2 sf (`31 m`) to 6 sf (`502320 J`, `117720 Pa`) | Card rounding follows the inputs' significant figures. The working always prints 6. |
| D6 | "Required" sometimes has no words | q22/q38/q41/q43 show `T`, `P`, `N`, `τ` alone; others show "a (acceleration)" | |

None of these makes an answer wrong. D1–D3 are the ones that confuse a learner, and all of them come from the server's templates, so each fix is one place.

### 1.3 Animations and pictures

- Of the **18** questions tagged with a picture, **16** got one: projectile ×4, free body, incline ×2, collision, orbit, spring, pendulum, wave, rays ×2, circuit ×3 (on two of them a trajectory graph sits beside the animation). The 2 misses are q06 (projectile) and q21 (orbit), the unsolved ones.
- **7 untagged questions got a sensible extra picture:** a free body for F = ma, work, Coulomb and buoyancy; a recoil collision; a circuit for the kettle; a lever for the spanner.
- Every scene passed the server schema and the sweep's bounds checks (`check_visuals`). The phone plays scenes with play/pause controls and honours reduce-motion (`apps/mobile/components/rich/SimulationBlock.tsx:49-51, 274-285`).
- **Gap 1: an unsolved turn never animates.** The model's prompt says `Do NOT emit ```answer, ```graph, ```simulation, or ```geometry` (q06, q21, q26 system prompts). A projectile the reader misses becomes plain text.
- **Gap 2: the same physics animates or not depending on wording.** The orbit question solved with an orbit scene in one phrasing and with no scene in two others (§1.4).
- **Not animated where it would help:** braking and acceleration (q01, q02), and energy conservation on a track (q13, the roller coaster).

### 1.4 Robustness: the same physics in other words

`probe.py` with `probes1.json` and `probes2.json`:

| Probe | Solved | Notes |
|---|---|---|
| The 3 unsolved questions, reworded 3 ways each | 9 / 9 | The solver knows all three laws, so the miss is the reader. `extract_physics_intent` returns `None` on the original wording. |
| 12 solved questions × 2 natural rewordings | **16 / 24** | Misses: "Braking at 1.5 m/s², a 30 m/s train comes to rest. Stopping distance?"; "how deep is a well if a stone takes 2.5 s to hit the water"; "μk = 0.4. Find a." (**read as maths**); "roller coaster drops 45 m from rest…"; "3kg cart at 4 m/s hits a 1kg cart sitting still…"; both lens rewordings; "2 Ω, 4 Ω and 6 Ω are wired in series to 24 V". |
| 6 questions in Spanish, French and German, app language set to match | **0 / 6** | Matches the project's own measurement, 6/200 (`docs/MODEL_READER.md`, results table) |
| Extra information given | breaks it | Orbital speed solves for "400 km above the Earth" but not when the student also states Earth's mass and radius |
| Wrong numbers in all 64 probes | **0** | |

So the design is **safe but narrow**: a reading it doesn't recognise falls back to the model rather than guessing. But a reading it doesn't recognise is common. The repo already records the cause: physics understanding is "458 `re.compile` … 413 word lists" (`docs/MODEL_READER.md`, "Where reading is today"). The model-reader experiment that addresses it is off (`model_reader_shadow_enabled = False`, `core/settings/stem.py:75`).

### 1.5 What the model gets when the server can't solve

- The system prompt is 28.7–37.9 k characters (median 33.8 k, about 8–9 k tokens) for a one-line homework question.
- It carries the worked layout and a self-check rule. It also carries the "no verified result, don't claim verification" note, which is correct.
- The cost is real, though: every unsolved STEM turn pays for roughly 34 k characters of instructions. **Not verified:** how often the model then gets the number right. The project measured 69 right, 13 wrong and 34 with no plain value on 116 model-only answers (`docs/MODEL_READER.md`, "Second opinion").

## 2. Code review: STEM code

Scope: `modules/{physics,math,chemistry,money,turn_reading}`, `services/{law_binding,subjects,solving,workout,…}`, `core/{sympy_executor,sympy_slots,readings}.py`, and the chat glue in `turn_prep/` and `finalize_*`. That is about 156 k lines; physics alone is 229 files and 49 k lines. Tools: vulture, pylint duplicate-code, radon, cProfile, and AST scripts.

### 2.1 Performance

| Sev | Finding | Evidence | Fix |
|---|---|---|---|
| **High** | Catalog formulas are rearranged with `sympy.solve` **during a turn** | `services/law_binding/inverse.py:257` `rearranged` (lru 1024), reached from `physics/binding.py:251`. All 821 rearrangements take **24.9 s**; the slowest single one 2.7 s. A cold "critical angle" read took **324–509 ms** (warm: 6–13 ms). Workers recycle every 500 jobs (`core/sympy_executor.py:58`), which empties the cache, and `PhysicsSubject.warm()` is a no-op (`physics/subject.py:209-210`). The read budget is 3.0 s. | Generate the rearrangement table at build time and check it in a test. |
| **High** | A SymPy proof of textbook identities runs before every drag solve | `physics/solvers/drag.py:29-58`: 11 `simplify`/`limit` calls. The first drag solve per worker takes **226–313 ms**; later ones 1 ms. | Move the proof into a unit test. |
| Med | `to_si` re-parses unit strings with Pint on every call | `physics/solvers/si.py:86`, called 3× per parameter from `accounting.py:146`. 23,560 calls and 41,478 Pint parses over the corpus; **11.9 s of 33.2 s** profiled. Caching an affine map per (unit, kind) took extract from 4.5 → **2.3–2.6 ms** median with identical results (1,009 intents, same 9 solve errors). | `lru_cache` an affine map. |
| Med | Chemistry builds a new regex from each message, flushing the 512-entry `re` cache | `chemistry/extractors/shapes.py:126-127`: `re.fullmatch(rf"(?P<lead>{_LEAD}){phrase}{_TAIL}", …)` with substance names taken from the message. 363 recompiles in 60 warm turns, about **13% of wall time** (maths: 1 in 60). 46 such sites in scope. | Compile once with a generic group, or cache by name set. |
| Low | Several SymPy-pool round trips per turn, each shipping the readings memo | 5.6 pool calls per maths turn, 4.1 per chemistry turn. `core/readings.py:168` pickles the memo every call (median 22–33 KB, max 79 KB). | Merge the pre-stream reads into one pool call. |
| ok | Overall read speed | `needs_physics` median 0.2 ms; extract 4.5 ms (p95 10.4); solve 0.7 ms. Chain search capped (`law_binding/chain.py` `_MAX_ASKS=4`). No ReDoS: `EQUATION_RE` takes 8 ms on 1,000 terms. | |

### 2.2 Resource leaks

| Sev | Finding | Evidence |
|---|---|---|
| Low–Med | **The only unbounded cache keyed on user text** | `math/function_calls.py:173` `@cache def _spelling(name)`. Any word followed by `(` becomes a key holding a compiled regex. Repro: 3,000 made-up words → `currsize=3000, maxsize=None`. Bounded in practice only by worker recycling. Fix: `lru_cache(256)`. |
| Low | Slot wait raises a plain `TimeoutError`, not the documented `WorkerBusyError` | `core/sympy_slots.py:125` `asyncio.wait_for(asyncio.shield(running), remaining)`. `WorkerBusyError` subclasses `TimeoutError` (`:21`), so nothing crashes, but a caller can't tell "busy, retry" from "ran too long". |
| ok | SymPy pool lifecycle | Single-worker slots, kill on timeout (SIGTERM then SIGKILL, off the loop), recycle and warm after 500 jobs, exit with parent, a reserved readings slot. A timed-out task does not keep a worker busy, except in the documented macOS thread fallback. `tests/loop_guard.py` fails any test that runs SymPy or a reading on the loop. The claim "a turn reads its message once" holds: `ask_turn_readings` ran once in each of 120 instrumented turns. |
| ok | Everything else | Every other `lru_cache` in scope is bounded. There are no threads, `open()` calls or global SymPy objects in physics. PubChem uses one pooled client. |

### 2.3 Dead code

- CI's `vulture` over `app/` exits 0. AST scans of about 2,300 top-level names found **2 dead constants**: `physics/extractors/suvat.py:59 _IN_SENTENCE` and `physics/row_units.py:66 _ROW`. Both were grep-checked, tests included; vulture misses them because another file defines the same name.
- No function used only by tests, and no unimported module.
- **Dead code is effectively solved here.**

### 2.4 Duplicate code

Copy-paste of whole blocks is low: pylint at ≥8 lines finds **1** hit in about 156 k lines. The duplication that matters is **copies of the same knowledge that have started to disagree**:

| Finding | Evidence |
|---|---|
| Two layout rules that contradict each other | The shared `services/workout.py:354-360` says "never a bare **Formula**". `modules/money/block.py:29-38` tells the model to write a bare **Formula** with no Required or Solution sections. Money imports nothing from `workout`; physics, maths and chemistry do. |
| Unit spelling tables | `chemistry/given_units.py` (171) and `physics/given_units.py` (464) share 74 spellings, 73 identical. Further tables in `chat/working_check.py:55`, `chat/follow_up_units.py:58` and `services/unit_text.py`. |
| About 50 private number regexes | Shared `DECIMAL`/`SIGNED_DECIMAL`/`TEXT_NUMBER` exist (`services/number_text.py`). Copies disagree, for example `physics/bodies.py:162` (reads "t" as tonnes, `\d[\d.]*`) vs `:172` in the same file (no "t", `\d+(?:\.\d+)?`). `display.py:341` and `working_steps.py:58` parse the same `\times 10^{…}` rows differently. |
| Units hand-written into regexes despite `PHYSICS_UNITS` | `m/s` appears 177× in `physics/extractors/`; `seconds?` in 18 files; only 11 files use the table. |
| Identical regex and fence code | 41 regex literals duplicated across 95 sites (8 across packages). `force_pictures.py:48 _INCLINE` == `force_rigs.py:36 _SLOPE`. `catalog/thermal.py:18` == `catalog/heat.py:15`. `chemistry/fence.py:334` and `physics/fence.py:211` are twin fallbacks. Five separate AST walkers (`law_binding/{expression,inverse,leaf_units}`, `physics/symbolic/parse`, `chat/working_check`). |

### 2.5 Unorthodox code

| Sev | Finding | Evidence |
|---|---|---|
| **High (design)** | Natural-language understanding is about 2,000 hand-written English regexes | Physics: 767 `re.*` calls (556 compiles). Scope total: 1,463 compiles outside physics. 72 regexes with more than 25 alternatives; the largest is `chemistry/request.py:68 _STRONG_CUE`, 213 alternatives in 3.2 KB. 98 physics word lists (1,048 words). This is the direct cause of §1.4. |
| Med | The extractor order is a silent rule set | `physics/registry.py:126` `PHYSICS_EXTRACTORS`: 32 extractors, first match wins, and 31 comments like "Before fluids, the ordering is load-bearing". Fix: explicit priorities, plus a test per "before" constraint. |
| Med | Very large functions | Physics: 13 F-grade and 20 E-grade functions (radon), 18 over 100 lines. `extractors/torque.py:47` is 194 lines with complexity 75, and compiles the same clockwise regex inline 3 times (`:67, 77, 88`). `friction.py:110` has complexity 61 and depth 7. Outside physics: `math/tools/direct_calculus.py:135` is 209 lines with complexity 89. All are frozen in `scripts/function_size_baseline.json`, so they can't grow but aren't shrinking. |
| Med | Catch-alls that hide solver bugs | `physics/split_parts.py:125-126` (`except Exception: return None`, no log), `solvers/si.py:167`, `working_steps.py:113`. `chemistry/extract.py:56-66`: one extractor raising skips **every** later extractor for that message. 111 of 300 handlers in scope catch everything; 9 are silent. |
| Low | Substring cues without word boundaries | `physics/lane.py:28 _PHYSICS_HOMEWORK_CUES` uses `cue in lower`, so "incline" matches "disinclined". |
| Low | Import-time work | `physics/constants.py` evaluates 16 Pint constants at import: 195 ms of its own time, 504 ms including Pint. Importing `extract` costs 0.94 s cumulative. Total API import 6.9 s. |

### 2.6 What is done well (keep it)

- `services/law_binding` is subject-agnostic: it imports nothing from `modules/`, and `chain()` takes callables. It is shared by physics, chemistry, money and the model reader.
- The physics catalog is data: 516 `FormulaSpec`s, 343 with typed `Binding`s.
- The symbolic parser has no `eval`/`sympify` and has hard limits (`MAX_NODES=160`, `MAX_SYMBOLS=16`, 512 characters).
- The SymPy process pool (§2.2) is carefully engineered.
- The test net is large: 12,255 physics tests, a 1,596-turn sweep with a per-question coverage snapshot, and a holdout file.

## 3. How abstracted are subjects and models?

### 3.1 Subjects: will a new subject "just work"?

**No.** Solving through the registry works, but chat still calls the subjects by name. A new subject wired through the documented seam is read correctly, then silently never solved. Nothing fails, so nothing warns you.

**The experiment.** In a throwaway worktree, never committed, I added `modules/astronomy/` with one operation, the distance modulus (m − M = 5 log₁₀ d − 5). I wired it exactly as CLAUDE.md's Seams table says: `SubjectName`, a `SUBJECTS` entry, an order step, and a settings flag. Then I sent "What is the distance modulus for a star 100 parsecs away?" through the real offline turn.

| Step | Result | Cause |
|---|---|---|
| Before the change | Read as **maths**, unverified | No subject knows the law |
| Seam files only | Read as `astronomy`, **`solved: False`** | `chat/turn_prep/augment.py:211-217` `_turn_needs` returns only `(needs_math, needs_chem)`, so augmentation is skipped. Calling `build_subject_augmentation` directly does verify it, so the registry part works. |
| + surprise edit 1 (`augment.py`) | Solved, but the saved reply **lost its answer card**, demoted to plain `m - M = 5.00` | `chat/finalize_subjects.py:149-151` `_math_owns` = "not chemistry and not physics", so maths' fence check ran on the astronomy block |
| + surprise edit 2 (`_math_owns`) | ✔ `verified: true` card. Physics, maths and chemistry samples unchanged | |
| + surprise edit 3 | `test_subject_registry.py::test_the_subject_literals_are_the_registrys_names` failed (`Extra items … 'astronomy'`) until `model_reader/schemas.py`'s `Subject` Literal was edited | |

**Still broken after those three edits**, each confirmed by a probe:

| What | Evidence |
|---|---|
| The adapter's `hints` never reach the prompt | `prompt_subjects.py:20-26` `SUBJECT_HINTS` is a hand-written dict |
| Routed as everyday; physics decides its lane | `model_routing/route.py:283-287` asks physics' `fast_lane` about every line that isn't maths |
| The status phase would raise `KeyError` | `stream_status.py:40-58`: a 3-key dict, indexed with `[subject]`. Dormant only because `prompt_builder.py:82-126`'s if/elif never sets it. mypy passes. |
| Follow-ups ("what about 200 pc?") never asked | `turn_prep/followups.py:30-48`: `SubjectFollowup` has the fields `math`/`chemistry`/`physics` only |
| `fence.check/recover/draw/tidy/unverified_note` never called | `finalize_passes.py:259-308`: one hand-written pass per subject |
| Left out of hand-kept subject sets | `worked_turn.py:35`, `answer_photo_offer.py:27`, the decider's subject choices (`decider_read.py:56-59`), `model_routing/decided.py:30`, `models/routing_lanes.py:119-121`. `model_reader/service.py:82-130` sends any unknown subject down the **chemistry** branch. |

**Where subjects are named outside the registry** (`grep`, verified):
- 43 `subject_adapter("math"|"physics"|"chemistry")` calls in 16 chat files;
- only **2** places in chat loop over `SUBJECTS` (`turn_prep/attachments.py:216`, `reading.py:287`);
- `services/subjects/order.py` threads only `chemistry_enabled` through `detect_subject`, `plan_turn` and `TurnReading`.
- The architecture tests list three subjects too (`architecture/test_module_direction.py:21`, `test_pure_solvers.py:25`), so a new subject isn't held to the layer rules.

**Mobile is entirely hard-coded:**
- `features/images/api.ts:22` (subject union);
- `features/chat/model/turnOutcome.ts:17` `TOOL_PHASES`;
- `lib/typingPulse.ts:44`;
- `lib/streamStatusLabel.ts` with `chat.status.<phase>` × 9 locales;
- the scanner (`lib/scanner/subjects.ts:3`, `ScannerSubjectSwitcher.tsx`, `ScannerSubjectMark.tsx:60-92`, `scanner/model/liveText.ts`, `chat.math_scan_subject_*` × 9 locales);
- `lib/answerNotation.ts:24`.

**What a real new subject costs today:**
- **Backend:** the module, 5 seam files, 3 forced edits, and about 15 more chat/service files for feature parity.
- **Mobile:** about 8 files plus 9 locale files.
- **Tests:** 3 subject lists.

With the seam files alone, every test in `architecture/`, `test_battery`, `test_stem_sweep` and `test_sweep` passed (5,957 + 1,824 passed). The one test that did fail is the reader-Literal check above.

**Fix (small and mechanical):**
1. Add `enabled(settings)`, `status_phase` and a finalize hook to `SubjectAdapter`.
2. Replace the per-subject finalize passes, `SUBJECT_HINTS`, `SubjectFollowup` and `_turn_needs` with loops over `SUBJECTS`.
3. Pass settings, not `chemistry_enabled`, through `order.py`.
4. Add **one test that every `SubjectName` has a status phase, hints, a finalize owner, a lane and a decider choice.** Today mypy and all tests pass while each of these is missing.

### 3.2 Models: add one or remove one?

**Adding a model works.** **Removing one is unsafe without a data migration**, and nothing reminds you to write one. Both were tested in a throwaway worktree, nothing committed.

**The layer.**
- The catalog is one list: `models/model_catalog.py:145-380`.
- Each entry carries an OpenRouter slug and its capabilities: `supports_vision`, `supports_tools`, `json_mode`, `context_tokens`, `cache_breakpoints`, plan access, thinking levels and quota multiplier.
- Which model does which job is data: `models/routing_lanes.py:94-124`.
- The phone keeps no model list; it renders what `/models` returns (`ModelsSettingsScreen.tsx`).
- Chat goes through one gateway (`gateways/litellm_gateway.py`, `resolve_route` at :74).

#### Experiment A: add a model

I added `mistral-small-4` to the catalog only (fast tier, paid plans, vision, tools and JSON).

| Check | Result |
|---|---|
| Shows in `/models`, is pickable on Plus and Pro, and is rejected on Free | ✔ |
| Joins fallback chains | ✔ `fallbacks for free-chat: ['qwen-3.7-flash', 'mistral-small-4']` |
| Auto picks it | ✘ only when a lane names it, which needs a 4th file, `routing_lanes.py` |
| Users with saved model settings get it | ✘ only users with no saved list |
| Tests | 2 deliberate guards fail (`test_selectable_models_count`, `test_every_thinking_level_is_one_the_model_lists`). After updating them, 1,173 model-related tests pass. Mobile `pnpm typecheck` passes. |

**Cost: 3 files, or 4 with Auto.** One gap: a model from a **new provider company** also needs the privacy policy (`content/privacy_policy.py:49`), the consent text (`onboarding.consent_chats_body` × 9 locales) and `apps/web/src/components/AiConsent.tsx:10` updated. No test ties those to the catalog.

#### Experiment B: remove a model

I removed `glm-5.3-flash` from the catalog only. It was the least coupled choice: it is named only in `math_backups`.

- **25 tests fail** in 10 files.
- Real behaviour changes: Free-plan hard and code questions move to `free-chat`, and Free's maths backup disappears silently, because `math_backups` still names the removed model and nothing fails.
- **Users whose saved settings name the removed model, with Auto off, are stuck:**
  1. The phone sends its first saved model (`apps/mobile/features/chat/hooks/useChatComposerState.ts:15-19`).
  2. `ChatMessageRequest` rejects it ("Unknown model alias", `model_catalog.py:488`). Over WebSocket that shows as "Invalid message" (`ws_api.py:203`); over SSE it is a 422. New chats fail the same way.
  3. Fixing it in Settings also fails. The screen sends the whole saved list back (`ModelsSettingsScreen.tsx:65-69`), and `UserUpdate.validate_enabled_models` (`models/schemas/auth.py:221-232`) rejects the dead model before the service-layer cleanup that would drop it. The dead model has no row on screen to switch off.
  4. The server-side steps were confirmed by a probe test. The phone-side steps come from reading the code (**not run on a device**).
  - This is why every earlier removal shipped with a migration (`alembic/versions/0108_model_aliases_oct_2026.py`, `0109_trim_model_lineup.py`, `0129_qwen38_replaces_glm52.py`). Nothing in the code or the docs' Model seam row says a migration is required.
- **Variant B2:** removing `gpt-6-luna` without editing the lanes.
  - The app still starts, but `tool_selector_aliases()` raises `KeyError`, and it is called outside any `try` at `modules/chat/tool_loop/rounds.py:231`. Whether a higher layer catches it: **not verified**.
  - The `word_problems` and `math_extract` lanes raise `KeyError` too.
  - Nothing checks lanes against the catalog at startup; only one test, `test_routing_lanes_point_at_models_that_can_do_their_job`, does.

#### Model names written outside the catalog

| Where | What |
|---|---|
| Speech, live talk, images, embeddings | `gateways/speech_gateway.py:22-24, 186` (OpenAI families, `startswith("gpt-4o")`), `openai_speech_gateway.py:37` `"gpt-live-transcribe"`, `modules/speech/service.py:19-22`, `gateways/embedding_gateway.py:59`, `modules/images/generation.py:53` |
| `"image-search-model"` | Used as a model name (`images/search.py:52`, `search_tool.py:103`, `chat/turn_intercepts.py:41`) but **not in the catalog** |
| Mobile | `lib/modelCatalogFallback.ts:9-10` hard-codes `free-chat` = "Claude Haiku 5.5", which goes stale if the alias is remapped. Also `features/speech/model/ttsPreference.ts:7-8` and `features/images/hooks/useImageGeneration.ts:181`. |
| Default | `models/orm/chat.py:76` `default="free-chat"` |

#### Changing provider

Chat, structured output, tools and vision all go through LiteLLM. Embeddings go through LiteLLM by catalog name. Four other paths call providers directly; all stay inside `gateways/`, and no provider SDK is imported anywhere else:
- images: direct HTTP to OpenRouter (`image_gateway.py:16`);
- the decider: OpenRouter's alpha API (`decider_gateway.py:20`);
- speech-to-text and text-to-speech: `api.openai.com` (`speech_gateway.py:15-16`);
- live talk: OpenAI realtime.

So swapping OpenRouter touches 3 gateways, and speech and live talk depend on OpenAI regardless.

**Fix:**
1. Make removal safe by default: on read, map any saved model missing from the catalog to Auto or a named replacement. Do this in `UserOut` and before `UserUpdate` validation. Have `ChatMessageRequest` fall back the same way instead of failing with 422/"Invalid message".
2. Validate `routing_lanes` against the catalog **at startup**, not only in one test.
3. Put `image-search-model` and the speech, image and embedding names in the catalog.
4. Derive the provider list in the privacy and consent text from the catalog, or test it against the catalog.

## 4. Problems in the test harness itself

1. **`stem_sweep` over-counts pictures.**
   - `judge()` returns early on an unsolved turn (`app/tests/behavior/stem_sweep.py:605`) before the picture check. `drawn()` (`:664-671`) counts any visual-tagged entry without a `no_visual` problem, so unsolved turns count as drawn.
   - On this set it printed "18/18 with the picture"; the truth is 16/18.
   - The repo's own figure, "209/210", may be inflated the same way. **Not verified.**
2. **A verified reply the model writes around is never checked for its picture.** That covers a two-part question (q44) and any turn whose reply the model writes. `judge()` returns at `:614-623` before `check_visuals`, so `server_pictures` is never inspected there.

## 5. Recommendations, in order

1. **Make the reader less brittle.** This is the biggest user-facing issue (67% reword reach, 0% in other languages). **The decider does not solve this.** It returns multiple-choice probabilities (`subject`, `think`, `hard`, `picture`, `follow`, `live`, `asked`: `chat/decider_read.py`) and "writes no text" (line 8). So it can say "physics, hard", but it cannot produce the operation and the given values a solver needs. Use it as the **gate** for the model reader that already exists (`docs/MODEL_READER.md`): when the decider says maths, physics or chemistry and the pattern reader finds nothing, ask the model reader for `op` plus `givens` with quotes, check the quotes on the server, then solve and draw.
   - Turn on the shadow (`model_reader_shadow_enabled`) for exactly those turns, and measure agreement on real questions.
   - Ship it only under the doc's decision rule (its last measurement was 4–19% wrong cards in English).
   - Add every reworded miss from §1.4 to the STEM corpus as `gap` entries.
2. **Let an unsolved physics turn still animate.** When the decider (or `needs_physics`) says physics but no solver verified, let the reply carry a server-built scene from the law the turn names, or relax the blanket `Do NOT emit ```simulation` for kinematics, projectile and orbit scenes the schema can validate.
3. **Make model removal safe** (§3.2):
   - fall back to Auto from a saved model the catalog no longer has, on read and in request validation;
   - check the routing lanes against the catalog at startup.
   Until then, every removal needs a data migration like `0129`.
4. **Make the subject registry real** (§3.1):
   - adapter hooks for the finalize pass, the status phase, `enabled` and follow-ups;
   - chat loops over `SUBJECTS` instead of 43 calls that name a subject;
   - one completeness test per `SubjectName`.
5. **Fix D1–D4 in the reply templates** (`physics/direct.py`): write `3 µC = 3 × 10⁻⁶ C`; show only conversions the substitution uses; show `n = t/T½`; replace "Solve for ΔT" and "the same law for these quantities"; round working consistently.
6. **Remove the two SymPy cold starts** (§2.1 High). Precompute the `rearranged` table, and move the drag proof into a test. Then add the Pint affine cache (about 45% off extract).
7. **One unit table, one number regex, one layout rule.** Physics and chemistry spellings in `law_binding/units`; `number_text` everywhere; build money's rule from `WORKOUT_PROMPT_RULE`.
8. Small fixes:
   - `@cache` → `lru_cache(256)` (`math/function_calls.py:173`);
   - log in the three silent catch-alls, and let `chemistry/extract.py` continue past a failing extractor;
   - raise `WorkerBusyError` in `sympy_slots`;
   - delete the two dead constants;
   - word-boundary the lane cues;
   - fix the two harness gaps in §4.
9. Make extractor ordering explicit (priorities plus tests), then split the F-grade extractors as they're next touched.

## 6. Fixes applied (same day, offline)

These are all on `claude/recall-physics-review-hlgi1j`. Every change was proven against baselines taken on `2cb3346` before any edit:
- **Decision diff** (`app.tests.behavior.decisions`): 6,311 battery, sweep and STEM turns.
- **Reply dump of every server-written STEM reply** (`reply_dump.py`): 2,680 turns.
- **All CI gates:** ruff, format, file sizes, mypy, vulture, strict typing.

| Area | Commits | Result | Proof |
|---|---|---|---|
| Harness (§4) | `d936897` | Unsolved and model-written turns are now judged for their picture | Physics corpus drawn 209/210 → **208/210** (opt-06 never had its picture); the 50 questions 18/18 → **16/18** |
| Physics speed (§2.1) | `48d2606`…`734e4dd` (7) | Rearrangements are kept as a checked-in table (891 rows; a test re-solves every row against the catalog). The drag proofs moved into a test. A per-unit SI conversion cache. Lane cues read as words. Two dead constants deleted. Silent catch-alls log or catch narrowly. `word_pattern` cache raised to 4096. | Cold critical-angle read **285–299 → 52 ms**. First drag solve **329 → ~2 ms**. Extract median **5.05 → 2.7 ms**; solve **0.85 → 0.29 ms**. No decision and no reply changed. |
| Physics replies (§1.2 D1–D6) | `71d61ed`…`5688f4d` (6) | `q₁ = 3 µC = 3 × 10⁻⁶ C`. A conversion is shown only when it is used. `n = t/T½` before the decay law. "with ΔT = T₂ − T₁" / "with θ = 90°" replace "Solve for" and "the same law for these quantities". Working values on the way to 4 figures; the last row stays the value reached, unrounded, and only the card rounds (the owner's rule, restored on review of this PR). Every Required line names its quantity. 20 new template tests. | **0 of 1,660 answer cards changed**, 0 verified values, 0 pictures. 785 replies changed in text only. Critical problems 16 → 16. No decision changed. |
| Model removal (§3.2) | `31c3d99`…`061f340` (4) | `models/model_removal.py`: saved and requested choices of a removed model fall back to Auto, while real garbage is still refused. The API and the worker refuse to start while a lane names a missing model. `PHOTO_LOOKUP_MODEL` is a named label. The phone's fallback row says "Recall". | Removal of `glm-5.3-flash` re-run for real: startup refused with the lane named. With the lane repointed, `GET /auth/me` 200 → Auto, `PATCH` 200 → cleaned list, a WebSocket send started a turn. No decision changed. |
| Chemistry / maths / money / pool (§2) | `dbd36f6`…`21bd6e8` (8) | Substance patterns compiled once per set. `_spelling` bounded at 256. `OwnerTurns` raises `WorkerBusyError`. Money's worked rule is built from `WORKOUT_PROMPT_RULE`. A failing chemistry extractor no longer stops the ones after it. Catch-alls log. 13 exact number-regex copies use `number_text`. One geometry shape list. | Chemistry corpus regex compiles **2,052 → 389**, compile share of wall time **7.9% → 0.4%**. No decision changed. 0 of 1,084 chemistry and maths replies changed. |
| Subject registry (§3.1) | `b763e94`…`d06e555` (5) | Adapters now declare `enabled`, `status_phase` and `fence.owns`. Chat's `_turn_needs`, status line, finalize ownership (replacing `_math_owns`), per-subject fence passes, `SUBJECT_HINTS`, follow-up prompt sections, Auto's lane and the model reader ask `SUBJECTS` instead of naming subjects. Subject sets derive from `SubjectName`. `test_subject_completeness.py` holds every subject to what chat asks. | Toy astronomy subject wired **only** through the seam files plus its adapter: before `solved: False`; after **`solved: True`, card `verified: true`, m − M = 5.00**. No decision changed. 0 replies changed. **System prompts byte-identical on all 6,311 turns.** Behaviour suites 6,302 passed. |
| Log privacy | `ae2e23b` | The money catch-all fix had logged the formula and the user's amounts at WARNING; it now logs sizes and slider names | The full suite caught it (`test_log_privacy`, `test_silent_excepts`) |
| Sizes | `8f64bcc` | Two files that shrank are locked in the ratchet | — |

**Combined branch** (all of the above together, against the baselines):
- no decision changed (6,311 turns), and the subject refactor left every system prompt byte-identical;
- 0 answer cards, 0 verified values and 0 pictures changed (2,680 STEM turns);
- 785 replies changed in text (the template fixes);
- the one problem-list change is opt-06's newly reported missing picture;
- the 50 questions: 41/44 checked, 16/18 pictured; the template defect phrases now occur 0 times and every Required line is named;
- **full API suite: 44,018 passed.** The only failures are the 452 tests that need Postgres, the identical list `main` fails here. Behaviour suites: 6,302 passed, 20 expected failures.

**What a new subject still touches** after the refactor:
- **Required seams:** `SubjectName`, `SUBJECTS`, a step in `order.py`, a settings flag, and `modules/<subject>/subject.py`.
- **Measured model prompts:** the decider's subject choices (`decider_read.READ_SUBJECTS` and the criteria text), `turn_decision`'s `Subject`, `ROUTING.decided`, `model_reader/schemas.py`, and `services/subject_scan.py`. Tests flag each one.
- **Optional:** follow-up re-solving (`turn_prep/followups.py`), its own fence passes, a new status phase plus its mobile label, scanner tabs, and a STEM corpus folder.
- **Left as is:** `order.py` still threads only `chemistry_enabled`; subjects are gated at solve time by `enabled()` instead.

**Not changed, on purpose:**
- Number patterns whose meaning differs from `number_text` (about 10 private ones and about 80 inline `\d+(?:\.\d+)?`). Swapping them would change what the app reads.
- `chemistry/request.py`'s copy, which is held by the file-size ratchet.
- With Auto off, a request naming no model gets the cheapest model in the pool. Changing that would change routing.
- The F-grade extractor splits (§2.5): a large churn for no user-visible gain. Do them when each file is next touched.
- Anything that needs a model to judge it: recommendations 1–2 (the model reader gated by the decider, and animating unsolved turns) wait for an OpenRouter key.

## Reproduce

```bash
cd apps/api && uv sync
uv run python ../../docs/reviews/2026-11-12-physics/run_questions.py /tmp/q50.json        # §1.1–1.3
uv run python ../../docs/reviews/2026-11-12-physics/probe.py ../../docs/reviews/2026-11-12-physics/probes2.json  # §1.4
uv run python -m app.tests.behavior.stem_sweep physics                                     # baseline
```

Files here: `questions.json` (the 50 questions and their worked answers), `results.json` (every route, reply and picture), `probes1.json` and `probes2.json` (rewordings).
