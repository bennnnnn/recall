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
| Add a subject tomorrow? | PENDING | §3.1 |
| Add or remove a model tomorrow? | PENDING | §3.2 |

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

PENDING

### 3.2 Models: add one or remove one?

PENDING

## 4. Problems in the test harness itself

1. **`stem_sweep` over-counts pictures.**
   - `judge()` returns early on an unsolved turn (`app/tests/behavior/stem_sweep.py:605`) before the picture check. `drawn()` (`:664-671`) counts any visual-tagged entry without a `no_visual` problem, so unsolved turns count as drawn.
   - On this set it printed "18/18 with the picture"; the truth is 16/18.
   - The repo's own figure, "209/210", may be inflated the same way. **Not verified.**
2. **A verified reply the model writes around is never checked for its picture.** That covers a two-part question (q44) and any turn whose reply the model writes. `judge()` returns at `:614-623` before `check_visuals`, so `server_pictures` is never inspected there.

## 5. Recommendations, in order

1. **Make the reader less brittle.** This is the biggest user-facing issue (67% reword reach, 0% in other languages).
   - Turn on the model-reader shadow that is already built (`model_reader_shadow_enabled`) on a sample of real STEM turns, as `docs/MODEL_READER.md` recommends.
   - Add every reworded miss from §1.4 to the STEM corpus as `gap` entries.
2. **Let an unsolved physics turn still animate.** When the decider (or `needs_physics`) says physics but no solver verified, let the reply carry a server-built scene from the law the turn names, or relax the blanket `Do NOT emit ```simulation` for kinematics, projectile and orbit scenes the schema can validate.
3. **Fix D1–D4 in the reply templates** (`physics/direct.py`): write `3 µC = 3 × 10⁻⁶ C`; show only conversions the substitution uses; show `n = t/T½`; replace "Solve for ΔT" and "the same law for these quantities"; round working consistently.
4. **Remove the two SymPy cold starts** (§2.1 High). Precompute the `rearranged` table, and move the drag proof into a test. Then add the Pint affine cache (about 45% off extract).
5. **One unit table, one number regex, one layout rule.** Physics and chemistry spellings in `law_binding/units`; `number_text` everywhere; build money's rule from `WORKOUT_PROMPT_RULE`.
6. Small fixes:
   - `@cache` → `lru_cache(256)` (`math/function_calls.py:173`);
   - log in the three silent catch-alls, and let `chemistry/extract.py` continue past a failing extractor;
   - raise `WorkerBusyError` in `sympy_slots`;
   - delete the two dead constants;
   - word-boundary the lane cues;
   - fix the two harness gaps in §4.
7. Make extractor ordering explicit (priorities plus tests), then split the F-grade extractors as they're next touched.

## Reproduce

```bash
cd apps/api && uv sync
uv run python ../../docs/reviews/2026-11-12-physics/run_questions.py /tmp/q50.json        # §1.1–1.3
uv run python ../../docs/reviews/2026-11-12-physics/probe.py ../../docs/reviews/2026-11-12-physics/probes2.json  # §1.4
uv run python -m app.tests.behavior.stem_sweep physics                                     # baseline
```

Files here: `questions.json` (the 50 questions and their worked answers), `results.json` (every route, reply and picture), `probes1.json` and `probes2.json` (rewordings).
