# Recall — Engineering standards tickets

The October 2026 audit measured the production code in `apps/api/app` and `apps/mobile` against
the engineering-standards policy: single responsibility, one authoritative implementation of each
rule or formula, purpose-named shared modules, independent subjects, no God files or functions,
UI → application → domain layering, and no silent error swallowing. This doc ranks the work.

Import cycles, `any` uses and the `lib/math/clipboard.ts` layering fix are being handled
separately and are not repeated here.

Paths: API paths are relative to `apps/api/app/`; phone paths are relative to `apps/mobile/`.

The rule for every ticket: **pin the behavior first** (the test named under *Tests*), then move
code. A split ticket changes no behavior unless it says so. A ticket that fixes a bug lands its
regression test in the same change.

## Snapshot

| Measure | API | Phone |
|---|---|---|
| Production lines | 167,867 Python in 729 files (CLAUDE.md's "~44k" is stale) | 100,321 TS/TSX |
| Files over 500 lines | 73 | 27 |
| Files over 900 lines | 5 (`geometry_measures.py` 1222, `block/discrete.py` 1164, `core/jobs.py` 939, `extractors/formulas.py` 927, `stream_pipeline.py` 908) | 3 (`lib/physics/simulation.ts` 2717, `SimulationBlock.tsx` 1476, `markdownRenderRules.tsx` 1182) |
| Functions over 50 / over 100 lines | 378 / 87 | 330 over 50 (many are components) |
| Functions nested deeper than 3 | 171 | 70 |
| Clone detector: jscpd 4, at least 12 lines and 80 tokens | 13 clone groups, 251 lines (0.15%) | 15 clone groups, 320 lines (0.28%) |
| Clone groups that are real duplicated logic | 6 (the other 7 are catalog rows, signatures or facades) | 5 (the other 10 are styles, buttons or look-alike diagrams) |
| Duplicated-rule families found by reading, which the clone detector cannot see | 18 (table below) | |
| Broad `except` with no log and no re-raise | 98 (80 of them in `modules/math`) | — |
| Uncommented `catch { return … }` | — | 65 (most are `JSON.parse` fallbacks; about 8 hide server or network failures) |

The clone detector undercounts badly. Textual clones are rare because most duplicates were
written twice by different people at different times, so they differ in names and edge cases. The
families below were found by reading the code. Two of them are verified bugs today (ES-01, ES-02).

| # | Duplicated rule | Copies | Ticket |
|---|---|---|---|
| 1 | School rounding (half up vs binary float) | 6: `math/formulas.py`, `math/solve/teaching_elementary.py`, `physics/display.py`, `chemistry/solvers/types.py`, `services/answer_check.py`, `services/working_check.py` | ES-01 |
| 2 | "Not a picture" word lists | 6: three lists in the API (`gen_intent_words.py` ×2, `lookup_intent.py`) and three on the phone | ES-02 |
| 3 | Image generation and photo lookup intent | API `modules/images/gen_intent*.py`, `lookup_intent.py`; phone `features/images/model/imageGenIntent*.ts`, `imageLookupIntent.ts` (1,242 phone lines) | ES-05 |
| 4 | Reply presentation: calculation rows, inline boundaries, inline code, REPL transcripts | API `modules/chat/*.py`; phone `lib/markdown/*.ts` (913 phone lines), with no shared fixture | ES-06 |
| 5 | "What time is it?" detection | API `services/time_context.py`; phone `lib/timeQuestion.ts` (already drifted) | ES-04 |
| 6 | Geo and location intent | API `modules/web_search/patterns.py`; phone `lib/localPlacesQuery.ts` | ES-07 |
| 7 | Plot expression semantics | SymPy on the API; `lib/math/graphExpr.ts` on the phone | ES-07 |
| 8 | Model catalog, prices and quota multipliers | `services/model_catalog.py`; `lib/modelCatalogFallback.ts` | ES-08 |
| 9 | Number-literal grammar | 16 private regexes in math and physics, plus two scientific-notation folders | ES-09 |
| 10 | Cosine and sine rules | 3 math files | ES-10 |
| 11 | Physical constants: 273.15, c, e, mₑ, Nₐ, R and F in display text | 9 places in chemistry and physics | ES-11 |
| 12 | Reminder clock and day reading | 4 readers in `modules/todos` | ES-12 |
| 13 | Percent, vector, coordinate and complex extraction split across two owners | `tools/extractors/formulas.py` and `tools/school/*.py` | ES-13 |
| 14 | Direct-reply presenters re-reading the user's words | `direct_geometry_working.py`, `direct_graph.py` | ES-14 |
| 15 | Math detection runs the extractors that extraction runs again | `match/needs.py` | ES-15 |
| 16 | Bounded-concurrency embedding fan-out | 3 places | ES-16 |
| 17 | Session-fenced fetch caches on the phone | 4 hand-rolled, next to an unused shared one | ES-17 |
| 18 | Graph viewport and WAV encoding on the phone | 2 pairs | ES-40 |

---

## P0 — Correctness and duplicated rules

### ES-01 — One school-rounding rule (verified wrong answers today)

- **Status:** done (#1811).
- **Problem:** "Round 2.675 to 2 decimal places" is extracted (`school_op="round_decimal"`) and
  answered **2.67** with a verified check. The textbook answer is 2.68. The same path gives 0.12
  for 0.125 and **"1"** for "round 1.005 to 2 decimal places". The cause is that the rounding rule
  has six implementations:
  - `math/formulas.py:51-60` uses `round()` and `f"{v:.{n}g}"` (binary float, ties to even).
  - `math/solve/teaching_elementary.py:350-365`: the rounding *lesson* uses `Decimal` half up, so
    the lesson and the answer card disagree.
  - `physics/display.py:31-44` (`_parts`) uses `f"{v:.{n-1}e}"`.
  - `chemistry/solvers/types.py:25-60` uses `Decimal(repr(v))` half up, which is the documented
    school rule: "62.5 mL to two figures is 63 mL".
  - `services/answer_check.py:480-482` uses half up.
  - `services/working_check.py:286` uses `quantize` with the default context, which rounds ties to
    even.
- **Measured** (value and figures: physics / chemistry / math):
  - 62.5 to 2 figures: 62 / 63 / 62
  - 0.1225 to 3 figures: 0.122 / 0.123 / 0.122
  - 1.005 to 3 figures: 1 / 1.01 / 1
- **Change:**
  - Add `services/school_rounding.py`, subject-neutral, with:
    - `round_places(value: float | str, places) -> Decimal` (half up on the shortest decimal repr)
    - `round_figures(value, figures) -> tuple[Decimal, int]` (mantissa and exponent, with the carry
      case that chemistry `_round_significant` already handles)
    - `format_places(value, places)`, which keeps the requested trailing zeros: 1.005 to 2 places
      is "1.01", and 3.999 is "4.00".
  - Make all six call sites use it. Physics and chemistry keep their own figure *policies*
    (`ANSWER_FIGURES = 3`; chemistry's 2–4 from the givens). Only the primitive moves.
  - Note: `MathIntent.percent_base` and `combo_n` are reused as "value to round" and "places"
    (`tools/school/arithmetic.py:286-303`). Rename them in a follow-up, not here.
- **Tests (add first):**
  - A table-driven `app/tests/services/test_school_rounding.py` over
    `[2.675, 0.125, 62.5, 1.005, 12.25, 9.995, 0.0001235]`.
  - In `stem_corpus/math/traps.json`, three rows (`"round 2.675 to 2 decimal places"` → 2.68,
    0.125 → 0.13, 1.005 → 1.01).
  - A parity test asserting that `physics.display.plain_number`,
    `chemistry.solvers.types.format_number` and `math.formulas.round_significant_figures` agree
    on ties.
- **Risk:** low to medium. A physics answer that lands exactly on a tie changes in its last
  figure; the STEM sweep floors will show it.
- **Size:** M.

### ES-02 — Photo lookup steals "show me the html / regex / recipe"

- **Status:** done (#1812).
- **Problem:** `lookup_intent.py:89` `_NON_IMAGE_WORDS` says it "extends image_gen_intent's
  non-image denylist", but it is a hand copy that has drifted. It lacks 109 words of
  `gen_intent_words.py:47` `NON_IMAGE_WORDS`, including html, css, sql, regex, json, website,
  recipe, poem, song and button. Measured: `extract_image_lookup_query` returns a photo query for
  "show me the html page", "show me a regex", "show me the sql query", "show me a recipe" and
  "show me a poem". The chat path (`chat/stream_entry.py:189`) then runs a Tavily image search
  instead of answering, for free and Pro users, with `image_search_enabled` on by default. The
  phone copy (`features/images/model/imageLookupIntent.ts:37-38`, "Keep in sync with…") has the
  same gap. In total there are six lists: `NON_IMAGE_WORDS`, `SHOW_NON_IMAGE_WORDS`
  (`gen_intent_words.py:479`) and `_NON_IMAGE_WORDS` on each side.
- **Change:**
  - In the API, `_NON_IMAGE_WORDS = NON_IMAGE_WORDS | _LOOKUP_ONLY_NON_IMAGE_WORDS`, where the new
    set holds the 135 lookup-only words: math, chemistry, steps, budget and so on.
  - Do the same composition on the phone (`imageLookupIntent.ts` imports from
    `imageGenIntentWords.ts`).
  - Delete the "keep in sync" comments. ES-05 then removes the phone copy altogether.
- **Tests (add first):**
  - Add the look-alikes above to `behavior/sweep_corpus/` (area `photo`, `expect: answer`) and to
    `docs/fixtures/image_intent_cases.json` (lookup → `null`).
  - Both contract tests (`tests/modules/images/test_intent_contract.py`,
    `features/images/model/__tests__/imageIntentContract.test.ts`) then pin both sides.
- **Risk:** low.
- **Size:** S.

### ES-03 — Enrichment failure throws away a reminder card the user was already offered

- **Status:** done. The reminder pass runs last (`modules/chat/finalize_reminders.py`); a failed text pass falls back to the last committed text.
- **Problem:** `chat/stream_pipeline.py:392` `enrich_final_content` runs the side-effecting step
  first. It calls `materialize_reminder_fences` (around line 418), which with proposals on (the
  default) stores a proposal in Redis and puts its card in the text, and with proposals off writes
  `todos` rows. About 25 pure text passes follow in the same `try`. If any later pass raises, the
  outer `except` (around line 616) persists `_fallback_text(raw_assistant_text)`, which is the raw
  model text. The proposal card is lost while the proposal sits in Redis, or the reminder row
  exists but the reply shows a raw fence. `todos_sync` is never set, so the phone does not
  refresh.
- **Change:**
  - Split the function into `_text_passes(text, ctx) -> str` (pure, all-or-nothing) and
    `_side_effect_passes`: reminder materialization, answer photo and search-source chips.
  - Run the reminder pass last, on the already-enriched text.
  - Make the fallback start from the last successfully materialized text, never from
    `raw_assistant_text`, once a side effect has happened.
  - This is the first step of ES-22.
- **Tests (add first):** in `tests/services/test_enrich_final_content.py`, monkeypatch
  `sanitize_mermaid_fences` to raise on a reply that carries a reminder fence. Assert that the
  persisted text keeps the `reminder_proposal` card and that `result["todos_sync"]` is set.
- **Risk:** medium, because the order of passes matters. The behavior sweep's `todo` area pins it.
- **Size:** M.

### ES-04 — Delete the phone's "what time is it?" classifier (already drifted)

- **Status:** done (the clock card reads the reply; IANA zones only).
- **Problem:** `lib/timeQuestion.ts:2-30` copies `services/time_context.py:13-40` and
  `is_time_question` (:497). The copies have drifted: the server normalizes curly apostrophes and
  courtesy prefixes first (`_normalize_now_ask`, :151), and the phone does not. The server answers
  "what’s the time?" (iOS smart punctuation) as a local time question; the phone regex needs a
  straight `'`. The phone uses the copy only to decide whether to show the clock widget
  (`assistantReplyIsTimeAnswer`, used by `lib/markdown/assistantMessageContent.ts:126`). The
  server already answers every local time question with a ```` ```clock ```` fence
  (`format_time_answer`, :547).
- **Change:**
  - Make `assistantReplyIsTimeAnswer` decide from the reply alone: a `clock` fence, or a clock or
    timezone-only fence body.
  - Delete `TIME_QUESTION`, `REMOTE_TIME_QUESTION`, `SCHEDULED_EVENT`, `isTimeQuestion` and
    `isRemoteTimeQuestion`, and stop passing `priorUserText`.
- **Tests:**
  - Rewrite `lib/__tests__/timeQuestion.test.ts` around reply bodies.
  - Add a server case to `tests/services/test_time_context.py` showing that "what’s the time?"
    gets the clock fence.
- **Risk:** low.
- **Size:** S.

### ES-05 — The server is the only image-intent reader

- **Problem:** image generation and photo lookup intent exist twice: in the API
  (`modules/images/gen_intent.py` 682, `gen_intent_words.py` 491, `lookup_intent.py` 586) and on
  the phone (`features/images/model/imageGenIntent.ts` 516, `imageGenIntentWords.ts` 469,
  `imageLookupIntent.ts` 257). Each helper has a "same-named Python twin; change both". A shared
  fixture holds them together, and ES-02 shows it is not enough. The phone already calls the
  server on this path: `stemSubjectOwnsTurn` (`POST /images/intent`, `modules/images/api.py:47`)
  runs before every generate (`features/chat/hooks/useChatSend.ts:361`).
- **Change:**
  - Extend `POST /images/intent` to return the whole verdict:
    `{subject, lookup_query, generate_prompt, revision}`. It is computed by the existing server
    functions from `text` plus `chat_id`, and the server loads the recent window.
  - On the phone, keep only a non-authoritative prefilter: a 20-word trigger set (draw, image,
    picture, photo, show, "look like", …) decides whether the round trip is worth making. A false
    positive costs one request; it never decides.
  - `useChatSend.handleSend` (:341-361) uses the verdict.
  - Delete `imageGenIntent.ts`, `imageGenIntentWords.ts`, `imageLookupIntent.ts`,
    `stemSubjectOwnsTurn.ts` and the TypeScript half of `docs/fixtures/image_intent_cases.json`.
- **Tests:**
  - `tests/modules/images/test_intent_contract.py` becomes the contract for the endpoint.
  - `features/images/model/__tests__/imageGenTurn.test.ts` and `useChatSend.test.tsx` mock
    `api.imageIntent`.
- **Risk:** medium (latency on image-like sends, and the offline path). Keep "offline → normal
  send" as today.
- **Size:** L.

### ES-06 — Reply presentation: one contract, a shared corpus, the phone only on the streaming tail

- **Problem:** the phone re-runs the server's presentation pipeline on every message:
  - `lib/markdown/presentation.ts:13`
  - `calculationLayout.ts` (582)
  - `inlineBoundaries.ts`
  - `inlineCode.ts`
  - `replTranscript.ts`

  The server side is `modules/chat/presentation.py`, `calculation_layout.py`,
  `inline_boundaries.py`, `inline_code.py` and `repl_transcript.py`. The server docstring
  `calculation_layout.py:3` says "This is the only calculation-layout implementation", which is
  false. The phone headers point at stale paths (`services/chat/…`). No shared fixture exists;
  `lib/__tests__/presentationCorpus.test.ts` and `tests/modules/chat/test_presentation.py` assert
  different strings. Persisted assistant rows are already presented by the server, so the phone
  pass is redundant on them and diverges silently.
- **Change:**
  1. Add `docs/fixtures/presentation_cases.json` (input → expected) and run it from both test
     files.
  2. Fix the docstrings and paths.
  3. In `lib/markdown/preprocess.ts:139`, apply `presentAssistantMarkdown` only to unsettled
     streaming text (`presentStreamTail`) and to rows older than the server's presentation
     cut-over, gated by `created_at` or a `presentation_version` on the message.
- **Tests:** the shared corpus (step 1) first, plus `markdownPreprocess.test.ts` and
  `markdownPreprocessStream.test.ts`.
- **Risk:** medium (old messages).
- **Size:** M.

### ES-07 — Parity fixtures for the remaining phone twins (geo intent, plot expressions)

- **Status:** done. Seven geo divergences fixed on the phone; seven plot forms recorded as `phone_gap` (ES-43).
- **Problem:**
  - `lib/localPlacesQuery.ts` mirrors `modules/web_search/patterns.py` (`_DISTANCE_INTENT`
    :427, `_MOTION_HOMEWORK` :444, `_HOW_MANY_ASKED` / `_TRIP_PLACE` :487) and `is_location_question`
    by "keep in sync" comments. One of them points at the stale `services/web_search/patterns.py`
    (:17). The phone needs this before sending, to decide whether to read GPS, so it cannot simply
    be deleted.
  - `lib/math/graphExpr.ts:1-4` re-parses and evaluates the plot expression the server verified
    ("plot-only eval"). It has its own precedence and implicit-multiplication rules, and nothing
    checks them against SymPy.
- **Change:**
  - Add `docs/fixtures/geo_intent_cases.json` and `docs/fixtures/graph_expr_cases.json`. The API
    test generates the expected samples with SymPy: `expr`, `x`, `y` for `-x^2`, `2x`, `sin x^2`,
    `x^-1`, `e^x` and `2^3^2`.
  - The phone tests assert parity within 1e-9. Fix the stale path.
- **Tests:** this ticket is the tests. Extend `lib/__tests__/localPlacesQuery.test.ts` and
  `graphExpr.test.ts`, plus a new `tests/modules/web_search/test_geo_intent_contract.py`.
- **Risk:** low.
- **Size:** S.

### ES-08 — The phone stops carrying a copy of the model catalog

- **Status:** done (the last /models response is cached per account; the fallback is free-chat alone).
- **Problem:** `lib/modelCatalogFallback.ts:7` hard-codes every selectable model with prices and
  `quota_multiplier`, "mirrors backend `model_catalog.selectable_models()`". It seeds
  `contexts/ModelsContext.tsx:60`. Its test (`lib/__tests__/modelCatalogFallback.test.ts`) pins
  the copy against more literals, not against the server, so a price change on the server is
  wrong on the phone until someone notices.
- **Change:**
  - Persist the last successful `/models` response, the way `lib/cachedUser.ts` does, and seed
    from it.
  - Reduce the fallback to the single `free-chat` entry the composer needs to send.
  - Delete the price and multiplier literals.
- **Tests (add first):** `ModelsContext` renders the cached catalog when `/models` fails, and
  falls back to `free-chat` alone on a fresh install.
- **Risk:** low.
- **Size:** S.

### ES-09 — One number-literal grammar for every subject

- **Problem:** 16 private number regexes with different rules:
  - Optional exponent in some, length caps in others, `(?<!\d)` only in physics.
  - Files: `math/tools/direct_calculus.py:13`, `direct_units.py:10`, `direct_newton.py:14`,
    `direct_statistics.py:11`, `work_request.py:128`, `followup.py:261`, `word_templates.py:29`,
    `school/_parse.py:11,14` (two identical), `school/geometry_facts.py:17`,
    `school/algebra_facts.py:31`, `school/curve_points.py:31`,
    `school/probability_formulas.py:19`, `match/discrete.py:41`, `physics/symbol_givens.py:55`,
    `physics/extractors/common.py:18`.
  - Math also keeps its own scientific-notation folder (`match/scan.py:432-450`, only `x` and
    `^`). Physics and chemistry use `services/number_text.read_scientific_numbers`, which also
    reads `×`, `·`, `\times`, `**` and superscripts.
  - `mtm._NUM` (private) is imported across 9 math files.
  - `_finite_match_value` and `_number_immediately_before` live in `school/_parse.py:29-48`
    (ES-13 deleted the verbatim copy in `extractors/formulas.py`).
- **Change:**
  - Give `services/number_text.py` named public patterns: `SIGNED_DECIMAL`, `SIGNED_DECIMAL_SCI`,
    `FRACTION_OR_DECIMAL` and `bounded_decimal(max_digits)`.
  - Add the two helpers there, and `fold_scientific(text, style="e" | "product")`.
  - Make `match/scan.prepare` use `style="product"` (SymPy keeps it exact).
  - Replace the 16 locals and delete the copies.
- **Tests:**
  - `tests/services/test_number_text.py` gains the math cases.
  - The STEM sweep (math, physics, chemistry) and `test_math_everyday_spellings.py` pin
    behavior.
  - Add "1.8·10⁻⁵ divided by 3" to `stem_corpus/math/notation.json` first. Measured today: math
    declines it, and `match/scan.prepare` rewrites it to `1.8·10⁻^5`.
- **Risk:** medium (extraction edge cases). Land one subject at a time.
- **Size:** M.

### ES-10 — The triangle laws are computed once

- **Status:** done. Every copy calls `math/solve/triangle.py`, which takes exact values from SymPy.
- **Problem:** the cosine rule is computed three times with three different validity checks:
  - `math/solve/geometry.py:268` `triangle_sides_geometry` (SSS, with Heron)
  - `math/tools/school/geometry_measures.py:711` `_extreme_angle` (SSS, checks the triangle
    inequality)
  - `math/tools/school/algebra_facts.py:221` `_cosine_rule` (SAS, with a hand table
    `{60: 0.5, 120: -0.5, 90: 0.0}` for "exact" cosines that misses 30°, 45° and 150°)

  The sine rule is in `solve/geometry.py:51` and `geometry_measures.py:1033`.
- **Change:**
  - Add `math/solve/triangle.py` with `cosine_rule_side(a, b, C)`, `cosine_rule_angle(a, b, c)`,
    `sine_rule_side(...)`, `heron_area(a, b, c)` and `triangle_valid(a, b, c)`.
  - Exact values come from SymPy (`cos(pi/3)`, `sqrt` forms), not a table.
  - The three school files keep only their working rows and call it.
- **Tests:** `tests/modules/math/test_math_geometry_advanced.py` and
  `test_math_battery_regressions.py` pin today's numbers. Add SAS cases at 30°, 45° and 150° that
  now get exact surds.
- **Risk:** low to medium.
- **Size:** M.

### ES-11 — Physical constants and offsets come from one place per subject

- **Status:** done. One home each: `services/units.CELSIUS_OFFSET_K`, Pint's values in
  `physics/constants.py`, and chemistry rows that name `{N_A}`, `{R_J}`, `{R_atm}` and `{F}`.
- **Problem:**
  - The Celsius offset 273.15 is a named constant three times in chemistry (`sig_figs.py:49`,
    `solvers/common_chem.py:137`, `solvers/solutions.py:231`). It also appears as six literals:
    `common_chem.py:254-256`, `extractors/electrochemistry.py:156`,
    `physics/extractors/thermal_readings.py:106`, `services/law_binding/units.py:39`,
    `chemistry/formula_bindings.py:33` and `chemistry/binding.py:74`.
  - c is written as a literal twice (`physics/solvers/catalog_scenes.py:40` `_C_LIGHT`,
    `physics/extractors/modern_laws.py:33`), next to the Pint value
    `physics/solvers/common.py:180`.
  - `physics/bodies.py:97,112` hand-types `ELEMENTARY_CHARGE` and `ELECTRON_MASS`, while
    `solvers/common.py:175-189` pulls every other constant from Pint, and other files import the
    `_`-private names.
  - Chemistry's substitution templates print constants as text that the arithmetic does not use:
    `formula_laws.py:184` "6.022 × 10^23", `:396` "6.0221 × 10^23" (the same constant at two
    precisions), `:424/442/454/465/627` "8.314" and `:319` "96485". Meanwhile the expression uses
    `N_A`, `R_J` and `F` from `solvers/constants.py`, and the hand solvers print `const(AVOGADRO)`.
- **Change:**
  - Add `services/units.CELSIUS_OFFSET_K`, used everywhere.
  - Add `modules/physics/constants.py` with public names, all from Pint, and drop the hand-typed
    values and the `_` imports.
  - Let `FormulaLaw.substitution` rows name `{N_A}`, `{R_J}` and `{F}`, rendered by
    `format_constant` (5 figures).
- **Tests:** `tests/modules/chemistry/test_chemistry_constants.py` (extend it to the template
  text), `test_physics_display.py`, and the chemistry `homework.json` sweep.
- **Risk:** low.
- **Size:** S–M.

### ES-12 — Reminders: one clock-and-day reader (and the todo God files)

- **Status:** done.
- **Problem:** four readers of the same words, with different rules:
  - `todos/reminder_fences.py:289-383` (`_parse_ampm`, `_parse_clock`, `_due_date_for_day`,
    `_next_date`)
  - `todos/spoken_add.py:441` `parse_clock_only`, `:562` `day_for_a_bare_clock`, `:692`
    `_bare_hour`
  - `todos/spoken_change.py:632` `_clock_in_change`, `:644` `_bare_hour_in`, `:613` `_due_on_day`,
    which imports the *private* `reminder_fences._due_date_for_day`
  - `todos/spoken_when.py:105` `_find_day`, `:134` `_find_clock`

  The two bare-hour readers disagree. `_bare_hour` accepts "6:30" and turns "0" into 12:00;
  `_bare_hour_in` rejects both. The files are 887, 719 and 736 lines; `_materialize` alone is
  217 lines.
- **Change:**
  - Make `todos/spoken_when.py` the owner, with public `read_clock(text)`,
    `bare_hour_as_pm(text, *, allow_minutes)`, `date_for_day(day_name, now)` and
    `find_when(text)`. The other three call it.
  - Then split `reminder_fences.py` into `reminder_fence_parse.py` (fence JSON, :202-282),
    `reminder_writes.py` (`_create_one` / `_mutate_one`, :445-599) and `reminder_fences.py`
    (`materialize_reminder_fences` plus a `_materialize` cut into find → match → write → render).
- **Tests:** `tests/services/test_spoken_remind.py`, `tests/modules/todos/test_reminder_lookalikes.py`
  and `test_service.py`, plus `uv run python -m app.tests.behavior.sweep --area todo`. Add the
  "6:30" and "0" bare-hour cases first.
- **Risk:** medium (the frozen-clock sweep is the safety net).
- **Size:** M–L.

### ES-13 — One owner per math school operation (dissolve `extractors/formulas.py`, 927 lines)

- **Status:** done. Each reader sits beside its block: percent in `school/percentages.py`,
  present value in `interest.py`, proportion in `ratios.py`, rounding in `rounding.py`, the sum to
  infinity in `sequences.py`, coordinates and SAS area in `coordinate.py`, vectors and complex
  numbers in theirs. `probability.py` and `extractors/calculus.py` were at their size ceilings, so
  geometric, Poisson, Bayes and complement went to `school/probability_formulas.py`, and calculus
  to `extractors/multivariable.py` (one `_named_axis_bounds`, with the double integral) and
  `extractors/calculus_methods.py`. Registry order is unchanged; 24,864 prompts extract, build and
  reply byte-identically.
- **Problem:** `math/tools/extractors/formulas.py` is a grab bag:
  - percent, discount, proportion, rounding and present value (125-338)
  - coordinates, vectors and SAS area (382-520)
  - probability and Bayes (52-125, 522-597)
  - complex numbers (597-612)
  - multivariable calculus (613-917)

  Each topic already has an owner in `tools/school/`, which calls back into this file. Vectors:
  `school/vectors.py:12-16` → `extract_vector_formulas`; coordinates: `school/coordinate.py:16-19`;
  percent: `school/percentages.py` blocks `discount` and `percent_change_from`, but the extraction
  lives in `formulas.py:158,227`. `_named_axis_bounds` is copied verbatim in `formulas.py:613` and
  `extractors/calculus.py:200` (jscpd).
- **Change:** move each block into its owner and delete `formulas.py`:
  - percent → `school/percentages.py`
  - vectors → `school/vectors.py`
  - coordinates and SAS area → `school/coordinate.py`
  - complex → `school/complex.py`
  - probability → `school/probability.py`
  - multivariable → `extractors/calculus.py`, which removes the `_named_axis_bounds` copy

  Each owner then holds its extraction and its block side by side.
- **Tests:** `tests/modules/math/test_math_school_readers.py`, `test_math_school_registry.py`
  and the math STEM sweep (`homework.json`, `lookalikes.json`).
- **Risk:** low (mechanical, the same registry order).
- **Size:** M.

### ES-14 — Direct replies stop re-reading the user's words

- **Status:** done. Extraction records `GeometryRequest(kind, quantity, target)` (plus the given area, whether the sides were named, and a solid's measures) and the literal `plot_point`; `_build_verified_block` copies both to `VerifiedMathBlock` (server-side only, never serialized to the phone). The working is a `_WORKINGS[(shape, quantity)]` table over `direct_geometry_working/` (`quadrilaterals`, `triangles`, `circles`, `solids`), and the point guard reads `plot_point` bound to its request. Golden fixtures and a 32k-prompt capture are byte-identical; the math STEM sweep is unchanged.
- **Problem:** `math/tools/direct_geometry_working.py:93` `format_direct_geometry_working` is the
  second-longest API function at 346 lines. It re-parses the question
  (`parse_solid`, `parse_named_rectangle_request`, imported at :13-17) to rediscover which shape
  and quantity were asked, after the extractor already decided. It then branches through about 40
  `kind`/`quantity` pairs inline. `direct_graph.py:140` `_literal_plot_point` and
  `can_direct_point_or_vertical` re-read the plot request that `match/graph.py:207` `plot_point`
  already parsed.
- **Change:**
  - Carry the extractor's decision on the verified block: `GeometryRequest(kind, quantity, target)`
    on the intent, copied to `VerifiedMathBlock`.
  - Replace the branch ladder with a table, `_WORKINGS: dict[tuple[kind, quantity], Callable]`,
    with one function per shape in a `direct_geometry_working/` package (`rectangles.py`,
    `triangles.py`, `circles.py`, `solids.py`).
  - Make `direct_graph` read `intent.plot_point`.
- **Tests:** `tests/modules/math/test_math_word_templates.py` (the only direct reference today).
  Add a golden test of `format_direct_geometry_working` for every `(kind, quantity)` pair before
  moving anything.
- **Risk:** medium.
- **Size:** M.

### ES-15 — Math detection does not run the extractors twice

- **Problem:** `math/match/needs.py:67` `needs_symbolic` (265 lines) decides "is this math?" by
  calling about 15 extractors in order: `extract_fraction_intent`,
  `extract_function_value_intent`, `CALCULUS_APPLICATION_EXTRACTORS`,
  `extract_single_draw_intent`, `extract_bag_draws_intent`, `extract_how_many_in_intent`,
  `extract_change_intent` and so on. When it says yes, `tools/extract.py` runs the same extractors
  again to build the intent. The gate and the extractor can disagree, and every math turn pays for
  extraction twice.
- **Change:**
  - Turn the cheap lexical gates (equation, keyword, bare arithmetic, shape-with-measures) into a
    `NEED_SIGNALS` tuple of named predicates.
  - Replace the extractor calls with one `extract_math_intent(cleaned)`, memoized per turn
    (`functools.lru_cache` keyed on the cleaned text), whose result the extraction step reuses.
- **Tests:** 25 test files reference `needs_symbolic` (for example
  `tests/services/test_subject_scan.py`, `test_math_category_regressions.py`), plus the math sweep
  `lookalikes.json`.
- **Risk:** medium.
- **Size:** M.

### ES-16 — One embedding fan-out

- **Status:** done. `embedding_gateway.embed_many` (input order, a failed text is None in its slot) under one `embedding_concurrency` setting (8; memory's re-embeds were 6). `MEMORY_EMBED_CONCURRENCY` was in no deploy config, so it was renamed without an alias.
- **Problem:** the same bounded-concurrency embed loop exists three times:
  - `modules/attachments/rag.py:104,140` (`_EMBED_CONCURRENCY = 8`, `_embed_pieces`)
  - `modules/chat/history_rag.py:20,38` (an identical copy; jscpd)
  - `modules/memory/apply.py:87` (from settings)
- **Change:** add `gateways/embedding_gateway.embed_many(settings, texts, *, concurrency)`, with a
  single `embedding_concurrency` setting, and call it from all three.
- **Tests:** `tests/modules/chat/test_chat_history_rag.py`, the attachments RAG tests and
  `tests/modules/memory/test_memory.py`.
- **Risk:** low.
- **Size:** S.

### ES-17 — Phone: one session-fenced resource cache, with failures that say so

- **Status:** done. `lib/cache/sessionResource.ts` `SessionResourceCache` (values and timestamps
  in `StaleResourceCache`) owns the session fence, one request per key, replay of edits made
  during a read, subscribers, and `fetch()` → `{ data: previous ?? null, error }`. The four
  caches are ports onto it, and `lib/__tests__/sessionResourceCache.test.ts` runs one contract
  against all four. A server-side failure while older rows stay on screen (drawer, memory
  pages) warns once through `reportRecoverableWarning`; offline and sign-out never do. A memory
  page whose read failed now says so instead of "This memory is gone".
- **Problem:** four hand-rolled caches implement the same protocol: a session-generation fence,
  in-flight dedupe, replay of updates made during a fetch, and `catch { return null }`:
  - `lib/cache/chatListCache.ts:75-101`
  - `features/memory/model/memoryListCache.ts:65-100`
  - `features/memory/model/memoryDocumentsCache.ts:57-74`
  - `features/attachments/model/galleryListCache.ts:83,116`

  The shared `lib/cache/staleResource.ts` `StaleResourceCache` already exists and is used only by
  `usageCache.ts` and `HomeContext`. Because every fetch maps a 401, a 500 or offline to `null`,
  screens cannot tell "empty" from "failed".
- **Change:**
  - Add a `SessionResourceCache<T>` in `lib/cache/` built on `StaleResourceCache`: session fence,
    `pendingUpdates`, `subscribe`, and `fetch()` returning `{ data, error }`.
  - Port the four caches.
  - Call `reportRecoverableWarning` on non-network errors.
- **Tests:** `features/chat/model/__tests__/chatListCache.test.ts`,
  `features/memory/model/__tests__/memoryListCache.test.ts` and
  `features/attachments/model/__tests__/gallery.test.ts`. Add one shared contract test run against
  all four first.
- **Risk:** medium (drawer and memory screens).
- **Size:** M.

### ES-18 — Stop hiding failures that look like success

- **Status:** done. Unreadable queue counts are `None` with `metrics_error` and a Sentry warning (pending was always 0: redis-py returns a dict); the SSRF guard blocks an address it cannot classify; live talk and home log at warning, and home skips the cache instead of reading generation "0"; the phone toasts a non-routine push token failure once per app run.
- **Problem:**
  - `core/jobs.py:769,775` `collect_queue_metrics` turns a Redis error into `dlq_depth = 0` and
    `pending_entries = 0`. `report_queue_metrics` then never raises its DLQ alert, exactly when
    Redis is failing.
  - `gateways/safe_fetch.py:41-46`: the SSRF guard's `except Exception` around `addr.is_global`
    falls *open* for IPv6.
  - `modules/speech/live_talk_tools.py:113` returns `[]` sources on a Redis or JSON error with no
    log.
  - `modules/home/__init__.py:87` treats a Redis error as cache generation "0".
  - Phone: `lib/pushNotifications.ts:65` `resolveExpoPushToken` maps every error to `null`, so
    push is silently off.
- **Change:**
  - Make metrics return `None` with a `metrics_error` field and capture a warning.
  - Make the SSRF guard fail closed (`return True`).
  - Log at warning in the live-talk and home cases.
  - On the phone, report through `reportRecoverableWarning`.
- **Tests:** `tests/core/test_jobs_backlog.py` (a Redis that raises gives an alert, not 0), and
  the existing `safe_fetch` tests with a stub address whose `is_global` raises.
- **Risk:** low.
- **Size:** S.

---

## P1 — God functions on the chat path

### ES-19 — Split `build_stream_prompt_context` (421 lines)

- **Status:** done. `build_stream_prompt_context(TurnRequest, settings, redis)` keeps only the phase order and its latency marks (78 lines, was 421). `_load_turn_identity` reads only what the caller left out, in one branch; `turn_prep/instant.py` (recurring pay, the Phase A time/location/profile/settings replies, "location not set"), `followups.py::resolve_subject_followup`, `augment.py::gather_and_inject`, and `request.py` (`TurnRequest`, `TurnIdentity`, client geo). `settings` and `redis` stay arguments, not request fields. Byte-identical capture over 4,113 turns (battery, sweep and STEM corpora, and turns for each job). `context.py` 731 → 354 lines, out of the size baseline.
- **Problem:** `chat/turn_prep/context.py:311` mixes six jobs:
  1. loading user, chat and mode, in two branches that repeat the same geo, timezone and
     rich-context code (:350-385)
  2. the recurring-pay instant reply
  3. "Phase A" (prompt, instant reply, fallback models)
  4. math, chemistry and physics follow-up resolution
  5. the geo "location not set" fallback
  6. "Phase B/C" augmentation gather and inject

  It takes 22 parameters.
- **Change:**
  - `_load_turn_identity(...) -> TurnIdentity` (one branch, no duplication)
  - `turn_prep/instant.py` (recurring pay, time/location instant replies)
  - `turn_prep/followups.py::resolve_subject_followup(...) -> SubjectFollowup`
  - `turn_prep/augment.py::gather_and_inject(...)`
  - The 22 keyword arguments collapse into a `TurnRequest` dataclass.
- **Tests:** `tests/modules/chat/test_turn_prep_parallel.py`, `test_turn_prep_attachments.py`,
  `test_regenerate_image_input.py`, `test_stream_latency_phases.py` (phase marks) and the
  behavior harness.
- **Risk:** medium (latency phases).
- **Size:** M.

### ES-20 — Split `prepare_chat_turn` (303 lines)

- **Problem:** `chat/turn_prep/prepare.py:53` mixes several jobs:
  - attachment processing
  - user-message persistence with a nested session, attachment linking and rollback (:57-130)
  - overlapping the persist with prompt build
  - vision injection for the current images and the prior turn's images (:240-280)
  - building the `StreamContext`
- **Change:**
  - `turn_prep/persist.py::persist_user_turn(...)` (one transaction, the service owns
    commit and rollback per CLAUDE.md)
  - `turn_prep/vision.py::inject_turn_images(...)`
  - `prepare_chat_turn` keeps only orchestration (about 60 lines).
- **Tests:** `test_turn_prep_attachments.py`, `test_chat_turn_history.py`,
  `tests/modules/math/test_math_followup_turn_prep.py` and `tests/test_services.py`.
- **Risk:** medium.
- **Size:** M.

### ES-21 — Prompt assembly: `build_prompt_messages` (301) and `_style_format_hints` (244)

- **Status:** done. `build_prompt_messages` is orchestration: `_context_plan` (rich context, the attachment probe), `prompt_window.py` (window, omit, gap, adjacency, history text) and `prompt_sections.py` (`PROMPT_SECTIONS` and `NEARBY_CONTRACTS`, ordered `PromptSection(applies, render)` over a `PromptTurn`); the profile block is `prompt_profile.py`. `_style_format_hints` is the ordered `HINT_RULES` table over a `StyleTurn`. Subject hints live with the subject (`math/reply_policy.py`, `physics/reply_policy.py`, `chemistry/reply_policy.py`) and chat lists them in `prompt_subjects.py`, with no registration; statistics and biology have no module, so their hints stay in `prompt_constants/format.py`. Byte-identical: `test_prompt_golden.py` checks 268 recorded prompts (every battery case, one in eight sweep turns with history, 95 branch cases); all 618 matched locally.
- **Problem:**
  - `chat/prompt_builder.py:389` mixes deciding rich context and the RAG probe, loading the
    window and omitting ids, classifying adjacency, the memory, RAG and summary gather, system
    prompt sections, and "nearby contracts" (:284-301).
  - `chat/prompt_format.py:224` is a 40-branch rule chain with subject branches
    (`if subject == "physics" … elif "math" … "chemistry" … "statistics" … "biology"`) inside the
    shared chat layer. Subject policy belongs to the subject.
- **Change:**
  - `prompt_window.py` (history and omit)
  - `prompt_sections.py`: a list of `PromptSection(predicate, render)` evaluated in order
  - `_style_format_hints` → an ordered `HINT_RULES` table
  - Subject hints come from a `subject_prompt_hints(subject, turn)` hook that each subject module
    registers (physics already has `modules/physics/prompt.py`).
  - The output is byte-identical; assert it.
- **Tests:** freeze golden prompts for about 30 behavior-battery cases before moving anything
  (`tests/behavior/cases.py` → `build_prompt_messages`). Existing:
  `test_prompt_builder_style_hints.py`, `test_continuity.py`, `test_memory.py`,
  `test_compact_output_format.py`.
- **Risk:** medium.
- **Size:** M–L.

### ES-22 — Finalization as an ordered list of passes; split `stream_pipeline.py` (908)

- **Status:** done. `chat/finalize_passes.py` runs 20 `FinalizePass`es in one declared order, each with its `on_error`, then the reminder pass; chemistry, physics and maths each have a fence pass that recovers its own fences. The stream paths are in `chat/stream_paths.py`, and `stream_pipeline.py` (297 lines) keeps `stream_and_finalize` and registration. The function-local imports there are module imports now.
- **Problem:** `enrich_final_content` (246 lines, `stream_pipeline.py:392`) is about 25 passes in
  one `try`:
  - prepare model reply
  - answer photo
  - reminders
  - subject fence validation through local imports (`run_sympy`, `VerifiedPhysicsBlock`,
    chemistry, physics)
  - unverified notes
  - working check
  - text plots
  - markers
  - chemistry enrich
  - sources and places fences
  - prose normalization
  - Mermaid and places sanitizing
  - clock fixes

  The file also holds the instant-reply path, the tool-loop path, the token stream, finalize
  registration and terminal-image finalize.
- **Change** (after ES-03):
  - `chat/finalize_passes.py`: `FinalizePass(name, run, on_error)` in one declared order, with
    per-pass timing and logging. Subject fence passes register from each subject's `fence.py`.
  - `chat/stream_paths.py` (instant reply, tool loop, LLM stream)
  - `stream_pipeline.py` keeps `stream_and_finalize` and registration.
- **Tests:** `tests/services/test_enrich_final_content.py`,
  `tests/modules/chat/test_verified_answer_card.py`, `behavior/sweep.py` and
  `test_stream_event_parity.py`.
- **Risk:** medium.
- **Size:** L.

### ES-23 — Replace the `stream.py` seam module with explicit dependencies

- **Problem:** `chat/stream.py:138` `_seams()` returns `sys.modules[__name__]`. `stream_entry.py`
  (79 uses), `stream_pipeline.py` (29) and `turn_resources.py` (20) reach every repository,
  service and gateway as `seams.<name>` through a parameter typed `Any`, "so existing
  `app.modules.chat.stream.*` monkeypatches remain effective". The dependency surface is invisible
  to type checking and to the module-boundary tests. `stream.py` (438) is mostly 18-argument
  pass-through wrappers (`stream_chat_response`, `stream_regenerate_response`, …). The functions
  behind it are long as well: `stream_entry.stream_chat_response` is 240 lines.
- **Change:**
  - Add a frozen `ChatTurnDeps` dataclass (repos, `litellm_gateway`, `quota`, images, todos,
    web search, math fence, `SessionLocal`, locks) with `default_deps()`.
  - Pass it explicitly. Tests build a `ChatTurnDeps` with fakes instead of monkeypatching.
  - Delete the facade wrappers and expose `stream_entry` functions directly.
  - Split `stream_chat_response` into intercepts (photo lookup, image generation), quota and lock
    resources, and the stream.
- **Tests:** the 11 test files that patch `app.modules.chat.stream` (`test_ws.py`,
  `test_chatprep_lock.py`, `test_stream_quota.py`, `test_chat_stream_orchestration.py`, …)
  migrate to the deps fixture. Keep one test that the default deps wire the real modules.
- **Risk:** medium to high (wide test churn).
- **Size:** L.

### ES-24 — A typed turn outcome instead of `result: dict[str, Any]`

- **Problem:** a mutable `result` dict threads through `stream_entry`, `stream_pipeline`,
  `related_prompts`, `ws_api` and `stream_api`:
  - 14 string keys, including private task handles (`_finalize_task`, `_finalize_db_task`,
    `_related_task`, set at `stream_pipeline.py:719-720,752`, `related_prompts.py:670`, popped at
    `stream_events.py:139-140`, `ws_api.py:609`, `stream_api.py:196`)
  - wire fields that are double-encoded: `search_sources` is `json.dumps(...)` inside the JSON
    event, and `todos_sync` is the string `"1"`

  The phone mirrors that in `features/chat/model/socketReduce.ts` (`search_sources?: string`,
  `todos_sync === "1"`) and re-parses it (`lib/searchSources.ts`).
- **Change:**
  - Add `TurnOutcome` (a dataclass: `message_id`, `final_content`, `resolved_model`,
    `fallback_used`, `search_sources: list[Source]`, `todos_changed: bool`, plus the task handles
    as typed fields).
  - The `done` and `stream_end` events become Pydantic models in `stream_events.py`.
  - Send `search_sources` as an array and `todos_changed` as a boolean. The phone accepts both
    shapes for one release.
- **Tests:** `tests/modules/chat/test_stream_events.py`, `test_stream_event_parity.py` (WS and
  SSE), `features/chat/model/__tests__/chatSocketReduce.test.ts` and `chatSse.test.ts`.
- **Risk:** medium (wire contract; ship tolerant clients first).
- **Size:** M.

### ES-25 — Tools get their turn context as an argument, not from 14 ContextVars

- **Problem:** `gateways/mcp/base.py` `ToolAdapter.invoke(args)` has no context parameter, so
  adapters read per-turn state from module ContextVars:
  - `modules/web_search/tool.py:56-62` (7)
  - `modules/images/gen_tool.py:25-27` (3)
  - `modules/images/search_tool.py:28-30` (3)
  - `modules/web_search/search_cache.py:27` (1)

  The `bind_*` context managers set them (`services/tool_loop.py:586-594`,
  `modules/speech/live_talk_tools.py:79`). An adapter called without the right `bind_*` sees
  `None`, and the tool loop has to import each adapter's module to bind it.
- **Change:**
  - `invoke(args, ctx: ToolContext)`, where `ToolContext` holds user, redis, `chat_id`,
    timezone, user query and a `TavilyBudget`. The registry passes it through.
  - Delete the ContextVars and `bind_*`.
  - `tool_loop.py` no longer imports `modules.images.*`.
- **Tests:** `tests/services/test_tool_selection_loop.py`, `test_tool_loop_user_match.py`,
  `tests/test_mcp.py`, and the image and web-search tool tests (`test_gen_tool.py`, …).
- **Risk:** medium.
- **Size:** M.

### ES-26 — Split `services/tool_loop.py` (839) and move it into `modules/chat/`

- **Problem:** one file holds four jobs:
  - tool-result parsing (`_canonical_*`, `_search_hits_*`, `_terminal_image_*`)
  - turn routing (`turn_needs_tool_loop`, `_needs_non_web_tool`, `_user_asks_for_image`,
    `_search_before_the_model`, `_tools_for_user`)
  - recovering tool calls from text (`_tool_calls_from_text`, 53 lines)
  - the round loop (`_run_tool_rounds_bound`, 195 lines, the 23rd-longest API function)

  It lives in legacy `services/` while CLAUDE.md puts new chat-loop code in `modules/chat/`.
- **Change:** add `modules/chat/tool_loop/` with `results.py`, `selection.py`, `text_calls.py` and
  `rounds.py`, where `_run_tool_rounds_bound` is cut into round → execute calls → merge results →
  terminal check. Keep a re-export shim for one release.
- **Tests:** about 30 files, led by `tests/services/test_tool_selection_loop.py` and
  `tests/behavior/harness.py`.
- **Risk:** medium.
- **Size:** M.

---

## P2 — God files

### ES-27 — Split `lib/physics/simulation.ts` (2717 lines; `layoutSimulationScene` 564)

- **Problem:** one file holds eight jobs:
  - fence types and parsing (15-570; `readScene` 120 lines)
  - viewport (598-716)
  - path sampling and tangents (716-835)
  - arrow geometry (835-1230)
  - label boxes and collision nudging (1257-2035)
  - scene layout (2036-2600)
  - the accessibility description (2603-2648)
  - incline geometry (2649-2717)

  `layoutSimulationScene` is the longest phone function, with nine commented sections.
- **Change:**
  - Turn it into a `lib/physics/simulation/` package: `spec.ts`, `viewport.ts`, `paths.ts`,
    `arrows.ts`, `labels.ts`, `incline.ts`, `describe.ts` and `layout.ts`.
  - `layoutSimulationScene` becomes `layoutVectors`, `layoutDerivedArrows`, `layoutTethers`,
    `layoutAngles`, `labelObstacles`, `layoutBodyLabels`, `planVectorLabels` and
    `separateLabels`, over a shared `SceneFrames` context.
  - Keep `"worklet"` directives in place.
  - An `index.ts` keeps the import surface.
- **Tests:** `lib/__tests__/simulationLayout.test.ts`, `simulationScene.test.ts`,
  `simulationV2.test.ts` and `components/__tests__/SimulationBlock.test.tsx`. Add a snapshot of
  `layoutSimulationScene` output for one scene of each `SimulationKind` first.
- **Risk:** low to medium.
- **Size:** L.

### ES-28 — Split `components/rich/SimulationBlock.tsx` (1476)

- **Problem:** the file holds:
  - SVG path builders (103-191)
  - the 314-line component (192-506): playback clock, layout memo and render
  - 20 sub-components: bodies, springs, tethers, pulley, support, angles, riding, derived and
    stated vectors, labels and markers (513-1456)
- **Change:**
  - `components/rich/simulation/paths.ts` (pure, testable)
  - `parts.tsx` (BodyShape, BodyMarks, SpringCoil, Tether, PulleyWheel, Support, SolidShape)
  - `vectors.tsx` (Riding*, Derived*, StatedVector)
  - `labels.tsx` (SceneLabels, BodyLabel, SceneMarkers, AngleArc)
  - `useSimulationClock.ts`
  - `SimulationBlock.tsx` stays under 300 lines.
- **Tests:** `components/__tests__/SimulationBlock.test.tsx`. Add path-builder unit tests when the
  builders become exported.
- **Risk:** low.
- **Size:** M.

### ES-29 — Split `components/markdown/markdownRenderRules.tsx` (1182; `makeSharedRules` 511)

- **Problem:** the file mixes:
  - lesson and workout rendering (77-419)
  - `renderTextWithMath` (192 lines, 439-631)
  - heading sizes
  - `makeSharedRules`, one 511-line object literal of every markdown rule: lists, tables, code,
    blockquote, links, images and headings
- **Change:**
  - `components/markdown/rules/` with `workout.tsx`, `textWithMath.tsx`, `lists.tsx`,
    `tables.tsx`, `code.tsx`, `blocks.tsx` and `links.tsx`, each returning a partial rules object.
  - `makeSharedRules` spreads them.
  - `renderTextWithMath` splits into segmenting (pure) and rendering.
- **Tests:** `components/markdown/__tests__/markdownRenderRules.test.tsx`,
  `markdownParagraphWrap.test.tsx` and `lib/__tests__/mathRenderCorpus.test.ts`.
- **Risk:** low.
- **Size:** M.

### ES-30 — Make `math/tools/school/geometry_measures.py` (1222) a package

- **Problem:** the file holds:
  - the `_RULES` extraction table (105-262) and intent builders (285-400)
  - circle and sphere solvers (402-597)
  - polygon and angle solvers (597-864)
  - coordinate geometry (864-1033)
  - triangle trigonometry (1033-1160)
  - dispatch (1163-1222)

  The functions are small; the file is not.
- **Change:**
  - `school/geometry_measures/`: `rules.py`, `circles.py`, `polygons.py`, `coordinates.py`,
    `triangle_trig.py` (calling ES-10's `solve/triangle.py`), and an `__init__.py` with
    `_SOLVERS` and `geometry_measure_block`.
  - The two silent `except Exception: return None` (:897, :969) go through ES-39's decline helper.
- **Tests:** `tests/modules/math/test_math_battery_regressions.py` and the math STEM sweep. Add a
  golden test of `geometry_measure_block` per `_SOLVERS` key first; none exists.
- **Risk:** low.
- **Size:** M.

### ES-31 — Split `math/tools/block/discrete.py` (1164) by topic

- **Problem:** "discrete" holds calculus, limits, series, statistics, combinatorics, number theory
  and matrices. It contains two of the 25 longest functions: `_verified_block_calculus` (217
  lines, :412) and `_verified_calculus_application` (199, :47). It also has 7 silent
  `except Exception` blocks.
- **Change:**
  - `block/calculus.py` (47-631 and 1096-1164; `_verified_block_calculus` → a dispatch on
    `operation` with one function per operation)
  - `block/limits.py` (631-775)
  - `block/series.py` (775-857)
  - `block/statistics.py` (857-957)
  - `block/discrete.py` (combinatorics and number theory)
  - `block/matrix.py`
- **Tests:** `tests/modules/math/test_math_calculus_applications.py`,
  `test_math_phone_regressions.py`, `test_math_advanced.py` and the math sweep.
- **Risk:** low.
- **Size:** M.

### ES-32 — Split `core/jobs.py` (939) and move product payloads out of `core`

- **Problem:** the file holds:
  - enqueue and stream trim
  - product-specific enqueuers in `core`: `enqueue_welcome_email` (:184),
    `enqueue_purchase_receipt` (:193), which know `transactional_email` payload shapes and are
    called from `modules/account/service.py` and `modules/billing/*`
  - the dedupe-claim protocol
  - the worker loop, reclaim and poison handling (`_process_one_entry` is 103 lines)
  - heartbeat and liveness
  - metrics
  - DLQ list and replay
  - per-user purge
- **Change:**
  - `core/jobs/queue.py`, `dedupe.py`, `worker.py` and `admin.py` (metrics, DLQ, purge), plus a
    re-exporting `__init__`.
  - Move the two enqueuers to `modules/notifications/jobs.py`.
  - `_process_one_entry` → claim → dispatch → ack or DLQ helpers.
  - The metrics fix is ES-18.
- **Tests:** `tests/core/test_jobs_deadline.py`, `test_jobs_backlog.py`,
  `tests/security/test_account_delete.py` and 10 more files.
- **Risk:** medium (the worker).
- **Size:** M.

### ES-33 — `services/quota.py` (789): one counter table instead of 15 wrappers

- **Problem:** the file holds:
  - the daily token budget (reserve, refund, heal, seed)
  - per-feature daily counters written as 15 two-line wrappers (`reserve_speech_tts`,
    `refund_image_search`, `image_upload_limit_for_user`, … :424-526)
  - live-talk monthly seconds
  - carried usage
  - the global USD spend breaker
  - user-facing messages
- **Change:**
  - A `services/quota/` package: `tokens.py`, `counters.py` (`COUNTERS: dict[str, CounterSpec]`
    with key prefix, limit function and message; generic `reserve(counter, …)` and `refund`),
    `live_talk.py` and `spend.py`.
  - Callers use `counters.reserve("image_search", …)`.
  - Coverage target: 90% (CLAUDE.md marks quota as critical).
- **Tests:** 16 files, led by `tests/security/test_quota_carryover.py`,
  `tests/modules/chat/test_stream_quota.py` and `test_soft_chat_quota.py`.
- **Risk:** medium (billing-adjacent).
- **Size:** M.

### ES-34 — Math solve and parse splits, and the end of `tools/helpers.py`

- **Problem:**
  - `math/tools/helpers.py` (499, 17 importers) is a catch-all: LaTeX normalization,
    request-text filler and lead-in stripping, English powers, function-definition peeling and
    `substituted_eval_expr` (68 lines), and Newton guess parsing (:447-500) that belongs to
    `tools/direct_newton.py`.
  - `solve/parse.py` (823) mixes about 20 LaTeX and Unicode rewrites, safety checks and display
    formatting.
  - `solve/algebra.py` (745) mixes equations, systems, Newton's method,
    simplify/factor/expand and inequalities.
  - `match/scan.py` (744) mixes masking, number folding (ES-09) and geometry dimension reading.
  - `tools/school/equation_features.py` (894) is extraction (24-309) plus 25 feature solvers.
- **Change:**
  - helpers → `tools/request_text.py`, `tools/expr_rewrite.py` and `tools/function_def.py`;
    Newton parsing → `direct_newton.py`.
  - parse → `solve/latex_normalize.py`, `solve/parse.py` and `solve/display.py`.
  - algebra → `solve/equations.py`, `solve/systems.py`, `solve/inequalities.py` and
    `solve/numeric.py`.
  - scan → `match/scan.py` and `match/dimensions.py`.
  - equation_features → `equation_features/{extract,solvers}.py`.
- **Tests:** `test_math_wrong_verified_answers.py`, `test_math_key_step.py`,
  `test_math_service.py`, `test_math_assignment_evaluation.py`,
  `test_math_newton_leading_decimal.py`, `test_math_text_match.py`,
  `test_math_school_registry.py` and the math sweep.
- **Risk:** low (moves only).
- **Size:** L (land as five PRs).

### ES-35 — Phone chat send path: `useChatSend` (622-line hook), `handleChatPayload`, `submitPrompt`

- **Problem:**
  - `features/chat/hooks/useChatSend.ts:295` `handleSend` (262 lines) mixes guards (offline,
    streaming, double send), the composer intercept, photo lookup, image-generation intent and
    the server STEM check, auth, the geo permission, the optimistic bubble, the email-draft flush,
    the attachment upload, draft-chat creation and dispatch.
  - `features/chat/hooks/useChatIncoming.ts:123` `handleChatPayload` (164) is an `if (type ===)`
    ladder over nine event types, with magic re-sync timers `setTimeout(…, 2500)` and `7000` for
    todos (:218-219). **It has no test file.**
  - `features/images/hooks/useImageGeneration.ts:120` `submitPrompt` (158) repeats the
    `ensureChatId` and upload steps.
  - `ChatComposer` is a 582-line component.
- **Change:**
  - `model/sendGuards.ts` (pure `canSend`)
  - `resolveSendIntercept()` (shrinks to the ES-05 server verdict)
  - `useSendAttachment()` and `ensureChatId()`, shared with image generation
  - `handleChatPayload` → `CHAT_EVENT_HANDLERS: Record<EventType, Handler>` in
    `model/socketReduce.ts`
  - The todo re-sync waits become named constants, removed by ES-24's `todos_changed`.
- **Tests:** `features/chat/hooks/__tests__/useChatSend.test.tsx` and
  `features/images/hooks/__tests__/useImageGeneration.test.tsx`. Add
  `useChatIncoming.test.tsx` covering each event type before refactoring.
- **Risk:** medium.
- **Size:** L.

### ES-36 — `features/speech/model/realtimeVoice.ts`: pull the state machine out of a 523-line closure

- **Problem:** `createRealtimeVoiceSession` (:227, 523 lines) holds 20 mutable `let`s (`turnEpoch`,
  `userMuted`, `assistantSpeaking`, `suppressCurrentInputTurn`, …), two timers and a 195-line
  data-channel `onmessage` handler. WebRTC setup, mic gating, the echo and barge-in policy and the
  turn state cannot be tested apart.
- **Change:**
  - `realtimeTurnState.ts`: a pure reducer `(state, event) → {state, commands}`
  - `realtimePeer.ts` (media, peer, data channel, SDP)
  - `realtimeMicGate.ts` (mute and resume timers)
  - The factory wires them together.
- **Tests:** `features/speech/model/__tests__/realtimeVoice.test.ts`,
  `realtimeVoiceSession.test.ts` and `liveTalkEvents.test.ts`. Add reducer tests for barge-in and
  echo drop first.
- **Risk:** medium (device-only behavior; manual QA on device per `docs/QA_MATRIX.md`).
- **Size:** M.

---

## P3 — The rest

### ES-37 — The remaining long API functions in the top 15

| Function | Lines | Mixes | Split | Pinned by |
|---|---|---|---|---|
| `math/tools/school/arithmetic.py:161` `_verified_block_arithmetic` | 278 | an `if school_op ==` ladder over 29 operations | `_ARITHMETIC_BLOCKS: dict[str, Callable]`, like `school/__init__.py:79` | `test_math_written_arithmetic.py`, math sweep |
| `math/tools/school/trig.py:281` `_verified_block_trig` | 253 | trig equations, bounded intervals and identities (`sas_area` hands off to `school/coordinate.py` since ES-13) | dispatch by op | math sweep `homework.json` |
| `physics/solvers/kinematics.py:34` `solve_kinematics` | 249 | routing to five sub-solvers, then vertical-motion ops, then graph and scene building | `_VERTICAL_OPS: dict[op, fn]`; scenes → `solvers/motion_scenes.py` | `tests/modules/physics/test_physics_solver.py` |
| `physics/extractors/optics.py:140` `_extract_optics_intent` | 238 | 12 law branches (Malus, Brewster, slits, Snell, lens power, magnification, …) | one reader per law in `extractors/optics/`, dispatched by cue | `test_physics_em_waves_optics.py`, `test_physics_waves_optics_thermal.py` |
| `chat/turn_prep/attachments.py:83` `_process_attachment_inputs` | 231 | load, download once, format and OCR, persist markers, camera-math OCR | `load_turn_attachments` → `format_attachment_lines` → `camera_math_extract` | `tests/modules/attachments/test_acceptance.py`, `test_turn_prep_attachments.py` |
| `physics/extractors/energy.py:91` `_extract_energy_intent` | 221 | 9 unit-value scans then op selection | `_read_energy_givens()` → `_choose_energy_op()` | `tests/modules/physics/test_physics_extractors.py` |
| `images/generation.py:107` `generate_for_chat` | 221 | gates (flag, plan, storage, spend, quota), provider call, upload, persist, refund | `_authorize_generation`, `_generate_and_store`, `_persist_turn`; a `reserved_quota()` context manager owns reserve and refund | `tests/modules/images/test_api.py`, `test_reference_persistence.py` |

- **Risk:** low each.
- **Size:** S–M each.

### ES-38 — The remaining long phone functions in the top 10

Style factories (`makeTodosStyles` 189 lines, `makeConversationListStyles` 181, `makeStyles` in
`LoginScreen.tsx` 155, `makeChatComposerStyles` 154, …) are `StyleSheet` tables, not logic, and are
not counted. ES-27 covers `layoutSimulationScene` and `readScene`, ES-36 covers
`createRealtimeVoiceSession`, and ES-35 covers `handleSend`, `handleChatPayload` and
`submitPrompt`. The rest are:

| Function | Lines | Split | Pinned by |
|---|---|---|---|
| `lib/math/latexParse.ts:358` `parseSimpleLatex` | 192 | a command table `LATEX_HANDLERS: Record<cmd, (ctx) => Segment>` plus group, script and accent readers | `lib/__tests__/mathText.test.ts`, `lib/math/__tests__/mathLayout.invariants.test.ts` |
| `lib/math/layout.ts:356` `measureSegment` | 142 | one measurer per segment kind (frac, sqrt, script, accent, matrix) | `mathLayout.invariants.test.ts`, `components/__tests__/MathText.test.tsx` |
| `components/rich/diagrams/RayDiagram.tsx:117` scene memo | 152 | move geometry to `lib/physics/optics.ts` (`layoutRayScene`, pure) so the component only draws | **none**: add `RayDiagram` layout tests first, like `optics.test.ts` |
| `lib/markdown/streamBlocks.ts:71` `advanceStreamBlocks` | 117 | `scanClosedBlocks` (pure scan) vs `cutChunks` | `lib/__tests__/markdownStreamBlocks.test.ts` |
| `features/chat/components/MathDraftPreview.tsx:359` `DraftPiece` | 225 | one renderer per `DraftNode.kind` | `components/__tests__/MathDraftPreview.test.tsx` |
| `components/rich/InteractiveFunctionPlot.tsx:84` | 226 (+ a 159-line `ExplorerModal`) | `useFunctionPlotState`, `ExplorerModal.tsx` | **none**: add a render test first |

- **Risk:** low.
- **Size:** M overall.

### ES-39 — Math declines say why: one helper for 80 silent `except Exception`

- **Problem:** 80 handlers in `modules/math` catch `Exception` and return `None`, `[]` or `False`
  with no log. The worst files are `solve/traces.py` (8), `solve/key_steps.py` (8),
  `block/discrete.py` (7), `solve/key_steps_special.py` (7) and `solve/algebra.py` (7). A decline
  is the designed behavior: a failed check drops the trace and the turn keeps its model path. But
  the same handler also swallows an `AttributeError` or `NameError` from a refactor, which turns a
  bug into a silently missing trace that no test notices.
- **Change:**
  - `modules/math/solve/declines.py`, with a `@declines(default)` decorator or
    `with sympy_decline():`.
  - It catches SymPy and arithmetic failures, logs at debug with the function name, and counts a
    metric.
  - It re-raises `AttributeError`, `NameError`, `TypeError`-from-our-code and `KeyError` when
    `RECALL_STRICT_DECLINES=1`, which `conftest.py` sets for the test run.
  - Migrate one file per PR.
- **Tests:** the full math suite under strict mode. Each programming error it surfaces gets its
  own regression test.
- **Risk:** medium (strict mode will find real bugs; that is the point).
- **Size:** M.

### ES-40 — Small duplicates the clone detector found

**API**

- `chat/stream_entry.py:117-129` and `:225-238`: the image-generation and photo-lookup intercepts
  end with the same "delete the replaced assistant row, purge its attachments, fill `result`"
  tail. Extract `_finish_intercept_reply(...)`. Pinned by
  `tests/modules/chat/test_photo_reference_lookup.py`.
- `math/match/calculus.py:295` `_parse_latex_limit` and `:446` `_parse_latex_series` share the
  `\lim_` / `\sum_` subscript reader. Extract `_read_operator_subscript(text, cmd)`.
- `modules/billing/api.py:95-108` and `modules/speech/api.py:222-234` repeat the
  Content-Length-then-body size guard. Add `core/request_limits.reject_oversized(request, body,
  max_bytes, status)`.
- `chemistry/solvers/common_chem.py` mixes display formatters (`num`, `inp`, `qty`, `const`, …)
  with data (`WATER_VAPOR_MMHG`, `weak_dissociation`). Move the formatters to
  `solvers/display.py` and the data to `solvers/constants.py`.

**Phone**

- `lib/math/graphWorklets.ts` says it holds "worklet-safe copies … keep behavior in sync" of
  `graphViewport.ts` and `graphBlock.ts`, and that the worklet versions also run on the JS thread.
  Delete the JS originals (`clampGraphView`, `zoomGraphView`, `panGraphView`, tick helpers) and
  import the `W` versions. Pinned by `lib/__tests__/graphViewport.test.ts` and
  `graphScale.test.ts`.
- The WAV header writer is copied in `lib/scanner/switchCue.ts:39-57` and
  `features/speech/model/liveTalkSfx.ts:63-81`. Add `lib/audio/wav.ts`
  `encodePcm16Wav(samples, rate) → base64`. Pinned by `liveTalkSfx.test.ts`.
- `features/attachments/components/AttachmentPdfViewer.tsx:89-142` and
  `AttachmentTextViewer.tsx:82-136` share the header and footer chrome. Add one
  `AttachmentViewerChrome`.
- `features/images/hooks/useImageGeneration.ts:22-40` and `features/speech/hooks/useLiveTalk.ts`
  redeclare the `DraftChat` type. Use `ReturnType<typeof useDraftChat>`.

- **Risk:** low.
- **Size:** S.

---

### ES-41 — The server misreads `ceil(x)` as a product

- **Status:** done. `ceil` reads as SymPy's `ceiling` (`floor` and `sign` already read as
  written; `round` stays refused); `ceil(x)` and `floor(x)` rows pin it.
- **Problem:** `_parse_expression("ceil(x)")` (the parse `sample_function` plots) reads `ceil` as
  the product E·c·i·l, so "plot y = ceil(x)" cannot be drawn. The phone's `graphExpr.ts` reads it
  correctly. Found by ES-07.
- **Change:** map `ceil`/`floor` to SymPy's `ceiling`/`floor` in the expression reader's local
  names, next to the existing function names.
- **Tests:** add `ceil(x)` and `floor(x)` to `docs/fixtures/graph_expr_cases.json`; both contract
  tests then pin it.
- **Risk:** low. **Size:** S.

### ES-42 — "What’s my current location?" with a curly apostrophe is not a location ask

- **Status:** done. Both sides straighten curly apostrophes first (`straighten_apostrophes`, the time rule's too); the "current" entries are written folded, and a test holds every entry to the fold.
- **Problem:** the iPhone keyboard types a curly apostrophe by default. Neither the server nor
  the phone reads "What’s my current location?" as a location question. The typo-spelling list
  in `services/time_context.py` collapses doubled letters, so its two "current" entries can
  never match. Found by ES-07.
- **Change:** normalize U+2019 to `'` before the location rule (the time rule already does, in
  `_normalize_now_ask`), and fix the collapsed "current" entries.
- **Tests:** add the curly form to `docs/fixtures/geo_intent_cases.json` (where-am-I group).
- **Risk:** low. **Size:** S.

### ES-43 — The phone cannot resample seven plot forms the server writes

- **Status:** done. The server writes its reading into the graph fence in the phone's grammar
  (`solve/graph_expr_text.py`); the seven raw forms stay `phone_gap` and arrive as `sin(x)`,
  `cos(2x)`, `sqrt(x)`, `log(x)`, `abs(x)` and `x*e^x`.
- **Problem:** `sin x`, `cos 2x`, `sqrt x`, `log x`, `√x`, `|x|` and `xe^x` are read by the server
  and refused by `lib/math/graphExpr.ts`, so the phone draws the server's samples but cannot
  resample them on zoom. They are marked `phone_gap` in `docs/fixtures/graph_expr_cases.json`.
- **Change:** either have the server write the bracketed canonical form into the graph fence
  (`sin(x)`, `sqrt(x)`, `abs(x)`, `x*e^x`), which the phone already reads, or port the three
  rewrites. The first is smaller and keeps one parser authoritative.
- **Tests:** delete each `phone_gap` line as its form starts to agree.
- **Risk:** low. **Size:** S.

### ES-44 — Photo lookup: a dual-use word beside an unblocked one still searches

- **Status:** done. A code word beside a dual-use word blocks the lookup (`_CODE_CONTEXT_WORDS`, both sides).
- **Problem:** after ES-02, a dual-use word (branch, hook, test, ...) blocks a lookup only when it
  is the whole subject. "show me the git branch" and "show me a custom hook" still run a photo
  search, as they did before ES-02.
- **Change:** block a dual-use word that sits next to a code word (git, react, custom, unit, ...)
  in the subject, with that small word set beside `_DUAL_USE_WORDS` on both sides.
- **Tests:** contract rows in `docs/fixtures/image_intent_cases.json`, plus sweep look-alikes
  with coding history.
- **Risk:** low. **Size:** S.

---

## Documented exceptions (files over 500 lines that stay)

These are cohesive: one data table, catalog, schema or algorithm. Each stays as it is. If a file
in this list grows logic beyond its table, it leaves the list.

| File | Lines | Reason |
|---|---|---|
| `modules/physics/catalog/optics.py` | 862 | One `SPECS` table of law declarations (856 lines of data) |
| `modules/physics/catalog/thermal.py` | 670 | Law catalog; 92% data |
| `modules/physics/catalog/magnetism.py` | 607 | Law catalog; all data |
| `modules/physics/catalog/waves.py` | 603 | Law catalog; all data |
| `modules/physics/catalog/energy.py` | 587 | Law catalog; all data |
| `modules/physics/catalog/quantum.py` | 569 | Law catalog; 93% data |
| `modules/physics/catalog/kinematics.py` | 561 | Law catalog; all data |
| `modules/chemistry/formula_laws.py` | 754 | One row per one-line law, by design ("a new law of this kind is one entry") |
| `modules/chemistry/stated_bindings.py` | 566 | Binding catalog; all data |
| `modules/chemistry/catalog.py` | 537 | The one operation list (CLAUDE.md names it so) |
| `modules/chemistry/stated_laws.py` | 534 | Law catalog; all data |
| `modules/physics/schemas/simulation.py` | 600 | Pydantic wire schema for the `simulation` fence v2 (425 lines of model classes) |
| `modules/chat/prompt_constants/format.py` | 670 | Prompt copy (66% text); the functions are classifiers keyed to that copy |
| `modules/chat/prompt_constants/teaching.py` | 672 | Prompt copy (59% text), same rule |
| `modules/chat/prompt_constants/routing.py` | 662 | Prompt copy (53% text), same rule; review if the functions pass 250 lines |
| `modules/web_search/patterns.py` | 608 | Regex pattern table plus thin predicates; the phone twin is under ES-07 |
| `core/config.py` | 581 | `Settings`: one field per flag, the seam CLAUDE.md names |
| `lib/math/keyboardCatalog.ts` (phone) | 553 | Key and accessibility tables (321 lines of data) |
| `lib/codeTokenize.ts` (phone) | 517 | Prism grammar registration: Metro needs about 47 literal `require`s in one module |
| `lib/math/latexParse.ts` (phone) | 563 | One parser; the file stays and its one long function splits (ES-38) |
| `lib/math/layout.ts` (phone) | 597 | One layout algorithm; the file stays and `measureSegment` splits (ES-38) |
| `lib/math/draftSlots.ts` (phone) | 566 | One draft-node parser and editor |
| `lib/physics/optics.ts` (phone) | 649 | One diagram's parsing and pure geometry; tested by `optics.test.ts` |
| `lib/physics/circuit.ts` (phone) | 511 | One diagram's parsing and layout; tested by `circuit.test.ts` |

Not exceptions:

- `modules/images/gen_intent.py`, `lookup_intent.py` and the phone `imageGenIntent*.ts`: ES-02
  and ES-05.
- `lib/markdown/calculationLayout.ts`: ES-06.
- Every other file over 500 lines: it either has a ticket above, or it is next in line after
  them. Next in line: `services/time_context.py` 627, `chat/related_prompts.py` 670,
  `math/school.py` 657, `math/tool.py` 650, `math/fence.py` 646, `chat/ws_api.py` 618,
  `services/answer_check.py` 601, `features/chat/screens/ChatScreen.tsx` 639,
  `components/MathEquationScanner.tsx` 638.

## Noticed, not ticketed

- Student-claim grammar ("I got…", "my answer is…") is written twice: `physics/claims.py:30` and
  `math/followup.py:261-275` (plus `math/tools/work_request.py:113`). Chemistry has none, so "I got
  21.3 g, am I right?" is not checked there. A neutral `services/student_claim.py` would serve all
  three subjects.
- Gateways repeat inline httpx timeouts (`apple_auth.py:46` 10 s; `expo_push_gateway.py:55,159`,
  `revenuecat_gateway.py:21` and `email_gateway.py:75` 15 s). Named per-gateway constants, or one
  `gateways/http_client.py` default, would make them reviewable.
- `chat/stream_pipeline.py:436-437` and about 8 other function-local imports exist to dodge import
  order. They hide dependencies; ES-22 should make them module imports or remove the need.
- CLAUDE.md's size table (API ~44k, phone ~50k) is about 3.8× and 2× low.
