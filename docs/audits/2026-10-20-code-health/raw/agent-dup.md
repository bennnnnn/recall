# Code-health audit — B. Duplication (`DUP-`)

Audited tree: `/home/user/recall-audit` at `d2ec42b0` (detached). Read-only. Paths below are repo-relative.
Method: triage of every jscpd and pylint clone group, then reading the families the lead listed
(and the ones those reads led to), checked against `docs/ENGINEERING_STANDARDS.md` rules 2 and 3
and the ES tickets. History was checked with the full clone (2,749 commits) after the lead's note;
no conclusion here rests on the shallow history.

Scratch scripts (read-only parsers): `/home/user/recall/tmp/code-audit/raw/scratch-dup/`
(`dump_clones.py`, `triage.py`, `fixture_triggers.py`, `sim_schema_diff.py`, `latex_sites.py`).

## Metrics

### Clone detectors

| Source | Groups | Lines | Verdict breakdown |
|---|---|---|---|
| jscpd 4 (min 10 lines) | 78 | 1,274 duplicated (0.4%) | real cross-file logic 10 (244 lines; 3 API, 7 phone) · real intra-file repetition 10 (141; 8 API, 2 phone) · catalog rows / data tables 19 (295) · look-alike diagrams and JSX 12 (220) · signatures 9 (142) · import blocks 8 (106) · facades / prop plumbing 4 (74) · style sheets 4 (80) · detector artifacts (a range overlapping itself) 2 (50) |
| pylint duplicate-code (min 8) | 7 | ~75 | real 5 (compound inequality, unicode operator table, biology cues, reminder scan, not-water substances) · vocabulary near-twins / catalog 2 (picture nouns, plane-figure kinds) |

Per-group verdicts are in `scratch-dup/triage.py` (index = order in `jscpd-report.json`).

Real cross-file jscpd groups and where they went: #3 `boxesOverlap`, #4 `record()`, #8 prefix/suffix
diff → DUP-13; #5 `mapGraphPoint` → DUP-12; #58 compound inequality → DUP-11; #63 reminder scan →
DUP-10; #77 number words → DUP-05; #10 memory screens' `submit`/error state, #28 inline token
renderer, #30 Chart/Mermaid toolbar → "Looked wrong, actually fine" (polish). The ten real intra-file
groups (#6, #7, #39, #40, #57, #59, #60, #62, #65, #73) repeat a few lines inside one file. One helper
each would do, but none is a cross-owner rule; they are listed, not ticketed.

### The 279 "javascript" files in jscpd

They are not JavaScript files. 277 of the 279 are `.tsx` files that jscpd also lists under `tsx`
(same paths): jscpd's reprism tokenizer splits a TSX file into two token streams, and the regions it
tokenizes with the JavaScript grammar are reported as a second "javascript" source. Only two are real
JS: `apps/mobile/lib/webrtcStub.js` and `apps/mobile/lib/easBuildConfig.js`. Consequences:

- "Files analyzed 2,001" counts 277 files twice (1,724 distinct); the javascript row's 1.82% is a
  second view of TSX code, not a separate code base.
- A component-level clone is split across the two streams, and each half must reach 10 lines on its
  own, so TSX clones are under-detected. Example: #10 is reported as 122 lines in
  `MemoryDocumentScreen.tsx` against 73 lines in `MemoryScreen.tsx` for the same token run (the stream
  skips the lines that went to the other stream).
- Not scanned, and fine to skip: 22 one-line route files under `apps/mobile/app/` (below min-lines),
  `apps/mobile/plugins/*.js` (2 Expo config plugins, 39 lines), `app.config.ts`, `scripts/*`, root
  config files. Nothing there changes a verdict.

### Families found by reading (the detectors saw none or a sliver of these)

| Family | Copies | Ticket status | Finding |
|---|---|---|---|
| "Substances other than water" rule (physics) | 2, already disagree | never covered | DUP-01 |
| Which subject owns a line | 4 decisions (solver, prompt pack, model lane, follow-ups) | never covered | DUP-02 |
| What counts as a code fence | API 3 named grammars + 10 ad-hoc readers; phone 1 named + 9 ad-hoc | never covered (ES-06 shared only the presentation pass) | DUP-03 |
| Unwrapping a model's fenced JSON | 4 copies (+ a separate repair set in `json_output`); a fix from 2026-10-20 landed in 1 | never covered | DUP-04 |
| Number words ("seven" → 7) | 9 tables + 2 bare alternations | ES-09 sibling, not covered | DUP-05 |
| Maths glyph folding (×, ÷, −, –, ⁻, ², ₂) | 11 tables + 7 one-glyph chains | ES-09 sibling, not covered | DUP-06 |
| Student-claim grammar ("I got…") | 8 regexes in 3 files, chemistry none | "Noticed, not ticketed" — still open, has drifted | DUP-07 |
| Named calendar dates ("Dec 25", ISO) | 3 readers | ES-12 covered reminders only | DUP-08 |
| HTTP-shaped domain errors + mapping | 8 classes, 50 `except` → `HTTPException` (20 copy-only) | never covered | DUP-09 |
| Due-reminder scan (push vs email) | 2 | never covered | DUP-10 |
| Inequality solution set (answer vs number line) | 2 | never covered | DUP-11 |
| ES-40 stragglers and new small phone helpers | 6 pairs | ES-40 done; 1 documented leftover | DUP-12, DUP-13 |
| FastAPI error-body parsing on the phone | 4 parsers + server English keyed in a phone table | never covered | DUP-14 |
| Retry/backoff constants copied "by comment" | 3 | never covered | DUP-15 |

Already-fixed families re-checked, no straggler worth a finding: ES-01 rounding (one owner, every
answer-producing site imports it; remaining `.Nf`/`.4g` sites format irrational values or working
lines), ES-09 number literals (`fold_scientific` runs first in all three subjects), ES-11 constants,
ES-16 embedding fan-out, ES-17 session caches, ES-40 (one documented leftover: DUP-12).

---
## Findings

### DUP-01 — "Water only" is written twice in physics, and the catalog copy lets water + ethanol through as water + water
- Severity: High (two copies that already disagree; the looser one guards a verified answer)
- Confidence: Medium (both lists and the binder's `excludes` rule are read directly; the wrong verified answer is inferred from the binder code, not run)
- Locations:
  - `apps/api/app/modules/physics/bodies.py:136-156` `_NOT_FRESH_WATER` (18 words) and `:159` `names_only_water`, used by `apps/api/app/modules/physics/binding_values.py:42` before it supplies water's c or density
  - `apps/api/app/modules/physics/catalog/heat.py:157-205` law `water_mixture_temperature`, `excludes` at `:186-201` (14 words)
  - how `excludes` is applied: `apps/api/app/services/law_binding/fit.py:287`
- Evidence: both copies state the same rule. `bodies.py:136`: "Another substance in the question: water's numbers may not be the ones meant." `heat.py:157-158`: "Both are water, so c cancels; any other substance named rules this out." The word sets differ:
  - in `_NOT_FRESH_WATER` only: `sea`, `salt`, `mercury`, `alcohol`, `ethanol`, `glycerin`
  - in the law's `excludes` only: `block`, `specific heat`

  The law binds on `cues=("water",)` plus two masses and two temperatures (`inputs=frozenset({"m1","m2","temp_a","temp_b"})`, `interchangeable`), and computes `(m1*temp_a + m2*temp_b)/(m1 + m2)`. "100 g of water at 80 °C is mixed with 50 g of ethanol at 20 °C. What is the final temperature?" names water, has two masses and two temperatures, and has no word from the law's `excludes`. Nothing else stops it: no typed mixing extractor exists (no `mix` in `physics/extractors/` thermal files), and chemistry never closes on Q = mcΔT (`apps/api/app/services/subject_solving.py:138-140`: those laws "are physics' alone"). So the binder would answer 60 °C as verified, where ethanol's c gives about 66 °C. No test or corpus row mixes water with another liquid. The only mixing rows are water + water (`tests/behavior/stem_corpus/physics/investigation.json:114,243`, `tests/modules/physics/test_physics_thermal_fluids.py:124`).
- History: both lists arrived in one commit, `9b57ffb07` (2026-10-02, "Read thermal, fluid, modern and upper-level laws from the catalog"), already different. Neither word list has changed since; the law gained only the ask "final temp" (`63b6907ec`, 2026-10-15).
- Impact: a verified wrong number, the failure ENGINEERING_STANDARDS ranks first ("never show a plausible guess as a verified result"). The same drift would hit any later "water only" law that copies one of the two lists.
- Fix: one owner, `physics/bodies.py` (`NOT_FRESH_WATER`, public), with `excludes=(*NOT_FRESH_WATER, "block", "specific heat")` in `heat.py`. Better, physics marks its water-only laws (a `WATER_ONLY` id set beside the catalog) and `physics/binding.py:63` `bind_physics_intent` drops them unless `names_only_water(lower)`. The rule then lives in code and in one list, and the shared `services/law_binding` engine stays subject-neutral.
- Effort: S
- Verify: add STEM look-alikes (water + ethanol, water + alcohol, seawater + water, water + mercury → decline, or the right answer with the second c), then run the physics STEM sweep. A unit test asserts that every law with `cues=("water",)` either excludes every word in `NOT_FRESH_WATER` or sets the flag.

### DUP-02 — Four decisions about which subject owns a line, with different precedence
- Severity: Medium (the prompt's reply policy and the model lane can belong to a different subject than the solver that verified the turn)
- Confidence: High (code read; the disagreeing input class is documented in the owner's own comments)
- Locations:
  - Solver owner: `apps/api/app/services/subject_solving.py:104-168` `detect_subject`. Order: image → math; code → none; scanner caption; closed chemistry (`:141`) before physics (`:143`); a physics-cued curve maximum goes to math (`:144-150`); symbol givens → physics; chemistry-shaped before math; math (`:161`); chemistry question.
  - Prompt pack: `apps/api/app/modules/chat/continuation_subject.py:199-221` `classify_presentation_subject`. Order: physics (`:211`), chemistry question (`:213`), statistics cues (`:215`), digit + biology cues (`:217`), math (`:219`). It feeds `effective_presentation_subject` → `apps/api/app/modules/chat/prompt_format.py:255` → `apps/api/app/modules/chat/prompt_subjects.py:37-43` (`PHYSICS_REPLY_POLICY` vs `MATH_REPLY_POLICY`).
  - Model lane: `apps/api/app/services/routing.py:277-327` `_route_current_line`. Physics (`:314`, `needs_physics` + `extract_physics_intent`), then math (`:325`); chemistry is never considered.
  - Follow-up questions: `apps/api/app/modules/chat/related_questions.py:93-104` `subject_for_related` (`detect_subject`, then biology cues).
  - Biology vocabulary twice: `continuation_subject.py:145-154` (8 cues, a digit required) vs `related_questions.py:79-90` (10 cues, adds `photosynthesis` and `mitosis`, no digit). pylint flagged this pair.
- Evidence: `detect_subject` exists to overrule `needs_physics`. Its comment at `subject_solving.py:145-147`: '"h = 20t - 5t^2, find the maximum height" cues physics, but it states the function and asks its maximum: physics extracts nothing, calculus does', and `:138-140` says a closed chemistry calculation wins "before physics claims its numbers". `classify_presentation_subject` asks `needs_physics` first and never applies either override. So "a ball's height is h = 20t - 5t^2, find the maximum height" (pinned as a math answer, `tests/modules/math/test_math_battery_regressions.py:556`) is solved by math but prompted with physics' reply policy and hints. The same holds for any closed chemistry question that `needs_physics` also cues. `related_questions` reuses `detect_subject`; the presentation and routing gates do not.
- History (full clone):
  - `detect_subject`: 2026-09-27 (`574553aaa`).
  - `classify_presentation_subject`: 2026-09-28 (`07f46a288`, #1525).
  - The closed-chemistry override reached `detect_subject` the same day (`05719db0b`, #1529, "Route chemistry through the subject registry"); the curve override came on 2026-10-13 (`1dbe0b840`).
  - Neither override was carried to the presentation or routing readers. `subject_for_related` (2026-10-10, `d82433e6c`) reuses `detect_subject` and so is the only one that agrees.
- Impact: subject rules (a new override, biology arriving as a module, as ENGINEERING_STANDARDS plans) must be added in four places. The precedence has already split, so the model is told one subject's layout and policy for another subject's verified block.
- Fix: `detect_subject` stays the one owner of "which STEM subject". `classify_presentation_subject` becomes `detect_subject(text)`, falling back to statistics/biology cues only when it returns `None`. `_route_current_line` routes on `detect_subject`'s answer (physics lane, math lane, chemistry → fast). One `BIOLOGY_CUES` lives in the presentation module (the only owner until biology is a module).
- Effort: M
- Verify: a table test feeds the battery, sweep and STEM corpora through all four and asserts that `classify_presentation_subject`, the routing subject and `subject_for_related` agree with `detect_subject` whenever it returns a subject. Add the curve-maximum and closed-chemistry-with-masses prompts as named rows.

### DUP-03 — What counts as a code fence: three named grammars and about 19 ad-hoc readers, and the same-named scanners differ across sides
- Severity: Medium (edge-case rendering divergence, large maintenance surface)
- Confidence: High
- Locations (API):
  - `apps/api/app/services/md_fence_scan.py:8-29` (`is_fence_closer`, `next_fence_marker_line`). Backticks only, any indent; any run of 3+ backticks closes any fence. Used by the finalize passes, the subject fence passes, email, places, mermaid and web-search formatting (15 importers). Also `:168-183` `strip_gfm_pipe_tables` (```` ``` ```` toggle) and `:284-296` `close_unclosed_fences` (parity of ```` ``` ```` lines). The latter runs on every reply as finalize pass `close_fences` (`apps/api/app/modules/chat/finalize_text.py:83-88`, `finalize_passes.py:162`).
  - `apps/api/app/modules/chat/markdown_regions.py:17-33` `_fence_marker`. CommonMark-like: at most 3 spaces of indent; backticks or tildes; the closer must use the same character and be at least as long as the opener; an info string with `|` is not a fence. Used by the presentation passes; twin of the phone's.
  - `apps/api/app/services/answer_fence.py:80,109-147` `_OPENER`/`_opener`/`_closes`/`_scan`, a third, lenient grammar: any indent, `>` quote prefixes, a one-line ```` ```code``` ```` excluded.
  - Verbatim copy: `apps/api/app/services/working_check.py:26` `_FENCE_BLOCK` equals `apps/api/app/services/answer_check.py:222` (both 2026-10-15, `19ca57eb3` / `863d43168`).
  - Ad-hoc backtick toggles: `apps/api/app/modules/todos/reply_claims.py:123,142`, `apps/api/app/modules/chat/prose_normalizer.py:55,135`.
  - Ad-hoc regexes: `apps/api/app/services/reply_labels.py:28`, `apps/api/app/services/context_window.py:13`, `apps/api/app/modules/todos/reply_check.py:124`, `apps/api/app/modules/chat/prompt_constants/coding.py:109`, `apps/api/app/modules/todos/proposals.py:34` (```` ```reminder_proposal ```` by regex, though `md_fence_scan.iter_closed_fences(text, lang)` exists), `apps/api/app/modules/images/answer_photo.py:24`.
  - Fence-language lists: `apps/api/app/modules/math/fence.py:68` `_ANSWER_FENCE_LANGS` is a copy of `apps/api/app/services/answer_fence.py:41` `ANSWER_FENCE_LANGS`; `apps/api/app/modules/physics/fence.py:49` and `:107` repeat one inline tuple.
- Locations (phone):
  - `apps/mobile/lib/mdFenceScan.ts:4-25` `readFenceMarker` is CommonMark (backticks or tildes, at most 3 spaces, closer length), although its header copies the API file's "Linear markdown-fence scan" line.
  - Protocol-card strippers that bypass it with near-identical regex chains ("strip closed, strip the unclosed tail, collapse blank lines"): `apps/mobile/lib/settingsProposal.ts:20,75-81`, `apps/mobile/features/todos/model/reminderProposal.ts:51-52,103-110`, `apps/mobile/features/todos/model/reminderFence.ts:4-12`. All three run in sequence in `apps/mobile/lib/markdown/assistantMessageContent.ts:91-94`, next to `stripSearchSourcesFromContent`, which does use `mdFenceScan.stripClosedLangFence`.
  - Backtick-only toggles and parity: `apps/mobile/lib/markdown/preprocessCallouts.ts:30,157,240,264`, `apps/mobile/lib/markdown/preprocessStream.ts:58,148-149`, `apps/mobile/lib/markdown/preprocessTables.ts:80`, `apps/mobile/lib/printDocument.ts:109-115`, `apps/mobile/lib/timeQuestion.ts:16-18`, `apps/mobile/lib/lesson/lessonFences.ts:149`.
- Evidence:
  - Tilde fences: `md_fence_scan.next_fence_marker_line` tests `stripped.startswith("```")` only. `markdown_regions._fence_marker` and the phone's `readFenceMarker` accept `` ` `` or `~` with `length >= 3`.
  - Closer length: `is_fence_closer` returns `stripped == "`" * len(stripped)` for any length ≥ 3. `markdown_regions` requires `marker[0] == char and marker[1] >= length`.
  - Phone protocol regexes close on the first ```` ``` ```` anywhere (`/```settings_proposal\s*\n([\s\S]*?)```/gi`), not at a line start.
  - History: each new need added a grammar instead of upgrading `md_fence_scan` (`9cacc7b0d` 2026-08-28 backticks only; phone CommonMark 2026-09-03 `a479d3674`; `markdown_regions` 2026-09-28; `answer_fence._scan` 2026-10-15).
- Impact:
  - `close_open_fences` runs on every saved reply. A reply that shows one ```` ``` ```` line inside a `~~~` or ```` ```` ```` block (a markdown how-to, exactly when models use those fences) has odd parity and gets a stray ```` ``` ```` appended, so the phone opens an empty code block at the end.
  - `strip_gfm_pipe_tables` would strip a pipe table that sits inside a `~~~` fence.
  - Each new pass picks one of the three grammars or writes a fourth. The rules the server and the phone renderer disagree on are the ones ES-06's shared corpus does not cover (the fixture has 1 tilde and 1 four-backtick case).
- Fix:
  - One API owner: `markdown_regions._fence_marker` (already the phone's twin) moves under `services/md_fence_scan.py` as `read_fence_marker`. `iter_closed_fences`, `close_unclosed_fences` (real open/close tracking, not parity) and `strip_gfm_pipe_tables` are rebuilt on it.
  - `answer_fence._scan` keeps only its documented leniency (indent and `>`) as a flag on that reader. The `_FENCE_BLOCK` regexes, toggles and lang regexes call it.
  - Phone: the three protocol strippers become `stripClosedLangFence(text, lang)` plus one `stripUnclosedLangTail(text, lang)` in `lib/mdFenceScan.ts`; the toggles call `readFenceMarker`.
  - `math/fence.py` imports `ANSWER_FENCE_LANGS`.
- Effort: M
- Verify: add fence-grammar rows to `docs/fixtures/presentation_cases.json` (tilde fence holding ```` ``` ````, four-backtick fence holding ```` ``` ````, a closer shorter than its opener, indented 4+, inside `>`) and a `close_unclosed_fences` parity test over them. A grep test (like `test_pure_solvers.py`) fails on new ```` startswith("```") ```` in `apps/api/app` outside the owner.

### DUP-04 — Unwrapping a model's fenced JSON is copied 4×; the LaTeX-escape fix from 2026-10-20 reached one copy
- Severity: Medium (a fix in one copy only; silent corruption of LaTeX in vision readings)
- Confidence: High for the copies and the missing fix; Medium for how often the vision model writes single-backslash LaTeX into JSON
- Locations:
  - `apps/api/app/gateways/structured_completion.py:165-171`: unwrap ```` ``` ````/`json`, then `json.loads(_escape_latex_in_json(...))` (helper at `:50-80`)
  - `apps/api/app/modules/math/image_extract.py:219-226` `_read_extract`: the same unwrap, byte for byte, then `json.loads(raw.strip())`, no escape
  - `apps/api/app/services/scan_text.py:24-35` `reading_from_vision` (the physics and chemistry `/scan/read` path): a variant unwrap, then `json.loads(text)`, no escape
  - `apps/api/app/modules/attachments/ocr.py:133-148` `_page_text_from_response`: the same unwrap with a `text` tag
  - Related repair rules live elsewhere again: `apps/api/app/modules/chat/json_output.py:68-75` `repair_json` (trailing commas, curly quotes) for user-requested JSON
- Evidence:
  - `structured_completion.py:166-169` and `image_extract.py:222-225` are identical: `if raw.startswith("```"): raw = raw.split("```")[1]; if raw.startswith("json"): raw = raw[4:]`.
  - `_escape_latex_in_json` exists because "`$15\text{ cm}$` decoded `\t` as a tab … `\frac` as a form feed, and `\alpha` is no JSON escape at all, so the whole output failed to parse" (`structured_completion.py:51-55`).
  - It landed in `280dbedc0` (#1917, 2026-10-20). The image-extract copy dates from `55c5f198c` (2026-07-08) and was never updated. Its prompt asks for ASCII maths but also for an "exact transcription" in `source_text` (`image_extract.py:27-29`), the field that later audits whether a printed condition was dropped. When the model writes LaTeX there anyway, a `\frac` becomes a form feed and `\sqrt` makes the whole extract fail over to the backup model.
- Impact: model-output hardening has to be repeated by hand in each copy, and the copies already differ (LaTeX escape in one, trailing-comma and curly-quote repair in another, neither in the vision readers).
- Fix: one reader in `gateways/structured_completion.py`, e.g. `parse_model_json(raw) -> object`: unwrap any fence, escape LaTeX, repair trailing commas and curly quotes. `image_extract._read_extract`, `scan_text.reading_from_vision` and `ocr._page_text_from_response` (text variant: `unwrap_model_fence(raw, tag)`) call it. Better, move the vision extract onto `structured_completion` itself, since it already validates with Pydantic.
- Effort: S
- Verify: a table test over `{"source_text": "\frac{1}{2}x = 3"}`, ```` ```json ```` wrapped, a trailing comma and curly quotes, run through all three entry points, expects the same decoded object; grep finds no other ```` raw.startswith("```") ```` in `apps/api/app`.

### DUP-05 — Number words ("seven" → 7) are read by 9 private tables and 2 bare alternations; the change-from-payment reader stops at six
- Severity: Medium (already drifted, with an inconsistent decline)
- Confidence: High
- Locations: `apps/api/app/modules/math/tools/school/shopping.py:19` (one to six, and ten: no seven, eight or nine), `apps/api/app/modules/math/tools/school/probability.py:41-44` (one to twelve), `apps/api/app/modules/math/tools/school/bag_draws.py:21-24` (identical to probability), `apps/api/app/modules/math/tools/word_problem.py:135-171` (zero to twenty, tens, hundred, thousand, twice, half, …), `apps/api/app/modules/physics/extractors/circuit_patterns.py:118` (two to six), `apps/api/app/modules/physics/accounting.py:185` (two to six), `apps/api/app/modules/web_search/tool.py:34-45` (one to ten), `apps/api/app/services/recurring_pay.py:51-65` (one to twelve, and fourteen) with `:66-70` re-typing the keys in a regex, `apps/api/app/services/time_context.py:352-362` (one to ten) with `:367`, `:373` re-typing the keys. Bare alternations with no table: `apps/api/app/modules/math/match/homework_cues.py:17`, `apps/api/app/modules/chat/prompt_constants/length.py:33,37`.
- Evidence: `shopping.py:27` builds its count group from `_COUNT_WORDS`, and `extract_change_intent` returns `None` when an item does not match (`:61`). So "I bought six notebooks at $2 each. I paid with a $20 bill. How much change do I get?" is read, but "seven notebooks" is not. No words-to-digits normaliser runs before extraction (no such helper in `math/` or `services/`). pylint/jscpd flagged `recurring_pay` against `probability` (#77).
- Impact: whether a word problem is verified depends on which reader owns it and how high that copy counts. ES-09 unified digit literals but left this sibling grammar out.
- Fix: `services/number_text.py` (ES-09's owner) gains `NUMBER_WORDS` (zero to twenty, tens), `number_word_value(word)` and `COUNT_WORD` (a regex alternation built from the table). Each reader narrows the table (e.g. counts ≤ 12) by a parameter, not a copy. `word_problem.py` keeps its multi-valued extras (twice/half) on top.
- Effort: S
- Verify: a parametrized test runs one-to-twelve through every reader that accepts counts. STEM rows: "seven notebooks" and "nine pens" (change from a payment), which must be answered like "six notebooks".

### DUP-06 — Maths glyph folding (×, ÷, −, –, ⋅, ², ₂, ⁻) is eleven private tables and seven one-glyph chains; two pairs are byte-identical, the rest fold different glyph sets
- Severity: Medium (shared constant copied; the copies differ in what they fold)
- Confidence: High
- Locations:
  - `apps/api/app/modules/math/solve/unicode_normalize.py:9-22` `_UNICODE_OP_SUBS` (12 pairs) and `:42-47` superscript/subscript tables
  - `apps/api/app/modules/math/match/arithmetic.py:48-59` `_ARITH_OP_ASCII`, the first 10 pairs verbatim (pylint)
  - `apps/api/app/modules/math/match/written.py:31-35` (× ÷ − only)
  - `apps/api/app/modules/math/tools/work_request.py:92-105` (’ − – × · ⋅ ÷ ≤ ≥ ± ² ³)
  - `apps/api/app/modules/math/tool_check.py:27-40` and `:74-78` (² ³ ⁴ − – × · ÷ π √ ≤ ≥, \cdot, \times)
  - `apps/api/app/services/working_check.py:122-138` (\times \cdot × · \div ÷ −; no –, ⋅ or ∗)
  - `apps/api/app/services/answer_check.py:52-53,74`
  - `apps/api/app/services/number_text.py:101-102,106` (`_SUPERSCRIPTS` is byte-identical to `answer_check.py:52`)
  - `apps/api/app/services/symbolic_text.py:15-17` (identical to `unicode_normalize.py:42-46`)
  - `apps/api/app/modules/chemistry/input_text.py:31-32`
  - `apps/api/app/modules/physics/direct.py:322` (no ⁺)
  - one-glyph chains: `apps/api/app/modules/math/fence_answer.py:23,105`, `apps/api/app/modules/math/match/literal_plot.py:45`, `apps/api/app/modules/math/tools/direct_graph.py:342`, `apps/api/app/modules/math/tools/direct_newton.py:115`, `apps/api/app/modules/math/tools/direct_calculus.py:122`, `apps/api/app/modules/physics/numbers.py:126`
- Evidence: the en dash `–` folds to minus in the solver (`unicode_normalize`), arithmetic gate, work request and tool check, but not in `working_check` (the check of a reply's own arithmetic) or `written.py`. The dot operator `⋅` (U+22C5) folds in three tables and not in `tool_check` or `working_check`. The superscript minus `⁻` folds in `answer_check`/`number_text`/`chemistry`/`physics.direct` and not in `symbolic_text`/`unicode_normalize` (which lean on `fold_scientific` running first). Every copy was written next to its own reader; none imports another.
- Impact: a glyph a phone keyboard, OCR or a pasted page produces is read by some subject paths and silently left in others. Adding a glyph (e.g. `∗` or `∕`) is an 11-file change that no test checks.
- Fix: one `services/glyphs.py` (subject-neutral, beside `number_text.py`) with `OPERATOR_GLYPHS` (× ⋅ · ∗ → `*`; ÷ ∕ ⁄ → `/`; − – — → `-`), `SUPERSCRIPT_DIGITS`, `SUBSCRIPT_DIGITS`, `fold_operator_glyphs(text)`. The math SymPy path adds its own π/∞ and root rewrites on top. Readers that need a narrower fold say so with a parameter, not a copy.
- Effort: M
- Verify: a property test asserts that every glyph in `OPERATOR_GLYPHS` is folded by the arithmetic gate, `tool_check._normalize`, `working_check._plain` and `unicode_normalize`. Add a math STEM row with an en dash and a `⋅`.

### DUP-07 — Student-claim grammar is still in three places, and the copies have drifted (known item, not ticketed)
- Severity: Medium
- Confidence: High
- Status: the "Noticed, not ticketed" item in `docs/ENGINEERING_STANDARDS_TICKETS.md` (added `8a20f147d`, 2026-10-16) is unfixed at `d2ec42b0`. The note names one work-request line (`:113`). The file holds three claim regexes (`:111`, `:141` from 2026-09-27, `:148` from 2026-10-14 `75f7d3314`), all older than the note, so the note undercounted; the family did not grow after it.
- Locations:
  - `apps/api/app/modules/physics/claims.py:30-40` `_STATED`, `:41-43` `_OWN`, `:65-71` `CHECK_ONLY`, `:79-83` `_TRAILING_CHECK`
  - `apps/api/app/modules/math/followup.py:264-275` `_CLAIM_LEAD`, `_CLAIM_TAIL`
  - `apps/api/app/modules/math/tools/work_request.py:111-117` `_SEGMENT_SPLIT` ("i got/and i got"), `:141-145` `_ROOT_CLAIM`, `:148-154` `_ANSWER_CLAIM`
  - chemistry: none
- Evidence: lead-ins accepted:
  - physics: "I got / calculated / computed / worked out / found / obtained / reckon / estimated / came up with / ended up with / wrote / answered / think it's", "my result/value/working/calculation/solution is", "my teacher/book says"
  - `math/followup`: "I got / get / found / have", "my answer is/was", "check/verify/mark my answer", "is it"
  - `work_request`: "I got / found / get / have", "my answer is/was", "I think it's"

  Trailing checks: physics adds "is that ok/okay", "did I get it right", "check it"; math knows "is that right / am I right / right / correct". So "I calculated x = 6, is that ok?" is a claim to physics and not to math, and chemistry checks none ("I got 21.3 g, am I right?").
- Impact: the same student sentence is checked or ignored depending on subject; every new phrasing is added to one copy.
- Fix: as the ticket doc suggests, `services/student_claim.py` (subject-neutral): `CLAIM_LEAD`, `CHECK_TAIL`, `split_claim(text) -> (lead, value_text, tail)`. Each subject keeps only its value reader (physics: quantity and unit; math: `var = value`; chemistry: amount and unit).
- Effort: M
- Verify: one table of claim phrasings × subjects (physics, math, chemistry) asserting each is recognised. Sweep look-alikes ("I got a dog", "my teacher says hi").

### DUP-08 — Three readers of a named calendar date ("Dec 25", "25 December", ISO), each with its own month table
- Severity: Medium
- Confidence: High
- Locations: `apps/api/app/modules/todos/spoken_when.py:24-41,74-78,115-123` (reminders; `_MONTHS` by three-letter prefix; "Month D" / "D of Month"; no year, no ISO, no slash), `apps/api/app/services/recurring_pay.py:82-119` (full and short names plus "sept" and the typo "dcember"; ISO `\d{4}-\d{1,2}-\d{1,2}`; slash dates), `apps/api/app/services/calendar_facts.py:21-46` (tuple plus regex; years 19xx/20xx only; ISO `[01]\d-[0-3]\d`).
- Evidence: "2027-1-7" is a date to recurring pay and not to calendar facts. "12/25" is a date only to recurring pay. "remind me on 2026-12-25" names no day to the reminder reader. The created dates differ (2026-09-26, 10-14, 10-18), each written beside its feature. ES-12 unified clock and day reading inside `modules/todos` only.
- Impact: the user's date grammar depends on which feature reads the message; a fix (a typo, a new format) lands in one.
- Fix: `services/calendar_dates.py` owns `MONTHS`, `MONTH_RE`, `read_named_dates(text) -> list[(month, day, year | None, span)]` and ISO/slash readers with one width rule. The three callers keep their own decisions (which year is meant, whether a past date is allowed).
- Effort: M
- Verify: one table of date spellings run through all three readers. The behavior sweep `--area todo` and the time/calendar tests stay green.

### DUP-09 — HTTP-shaped domain errors: 8 hand-written classes and 50 `except` → `HTTPException` blocks
- Severity: Low
- Confidence: High
- Locations: the classes are `apps/api/app/modules/chat/service.py:38` `ChatsError`, `apps/api/app/modules/todos/crud.py:25` `TodosError`, `apps/api/app/modules/todos/proposals.py:55` `ProposalError`, `apps/api/app/modules/images/generation.py:52`, `apps/api/app/modules/images/search.py:55`, `apps/api/app/modules/attachments/upload.py:27`, `apps/api/app/modules/attachments/workflow.py:39` (arguments reversed: `(status_code, detail)`), and `apps/api/app/modules/account/settings_proposal.py:80`. Mappers: `apps/api/app/modules/chat/api.py:30-31` `_map_error` plus 12 `except`, `apps/api/app/modules/todos/api.py:18-19` plus 5, `apps/api/app/modules/images/api.py:39-40`, `apps/api/app/modules/attachments/api.py:52-53,109-110`, and `apps/api/app/modules/memory/api.py:97,130,166,178,196,216,237` (the same lock-busy → 409 seven times). The app-level seam already exists: `apps/api/app/core/unavailable.py:69-70` `add_exception_handler`.
- Evidence: six classes carry the same two fields (`self.detail = detail; self.status_code = status_code`, five of them byte-identical); `AttachmentWorkflowError` takes the same two the other way round; `SettingsProposalError` stores only `status_code` on a `ChatServiceError`. 20 of the 50 mapping blocks only copy `exc.status_code`/`exc.detail` into `HTTPException`.
- Impact: boilerplate in every new endpoint. The response shape (only `detail`, no machine `code`) is decided per module, and DUP-14 shows the cost on the phone.
- Fix: one `DomainHTTPError(detail, *, status_code)` in `app/exceptions.py`, subclassed per module, plus one `add_exception_handler` beside `core/unavailable.py`. `MemoryWriteLockBusyError` maps to 409 there.
- Effort: S
- Verify: a test that raises each subclass from a dummy route and asserts status and detail. Grep finds no `raise HTTPException(status_code=exc.status_code` left.

### DUP-10 — The "which reminders are due this minute" scan is written twice (push and email)
- Severity: Low
- Confidence: High
- Locations: `apps/api/app/modules/notifications/push.py:237-258` (query) and `:270-283` (quiet hours → lead → `should_notify_todo` → title); `apps/api/app/modules/notifications/reminder_email.py:43-79` (the same window, joins and checks). Shared pieces already live in `apps/api/app/services/reminder_timing.py`. Found by both detectors.
- Evidence: both compute `window_end = now + MAX_REMINDER_LEAD_MINUTES`, `overdue_cutoff = now - OVERDUE_MAX_HOURS`, `select(TodoItem, User).join(...)` with `checked false`, `due_at not null`, a per-channel `*_sent_at is null`, a per-channel opt-in and the cutoff window, then loop the same eligibility checks. The deliberate difference (email skips recurring rows, `a6d0773e2` "Protect reminder email delivery from recurring and edited occurrences") is one extra filter.
- Impact: a change to what "due" means (lead window, overdue cutoff, quiet hours) must be made twice; the SQL sits outside the todos repository.
- Fix: `modules/todos` (or `notifications`) owns `due_reminders(session, now, channel) -> list[(TodoItem, User, title)]` with the channel's sent-marker and opt-in column as parameters; email passes `include_recurring=False`.
- Effort: S
- Verify: one parametrized test over both channels (quiet hours, lead, 48 h cutoff, recurring) against the shared function.

### DUP-11 — An inequality's solution set is solved twice: once for the answer, once for the number line
- Severity: Low
- Confidence: High
- Locations: `apps/api/app/modules/math/solve/graph.py:518-552` `_inequality_solution_set` vs `apps/api/app/modules/math/solve/inequalities.py:34-62` `solve_compound_inequality` and `:134-157` `solve_inequality` (pylint and jscpd #58).
- Evidence: the compound branch is copied line for line (`ascending`/`descending`, `Gt`/`Ge`/`Lt`/`Le`, `solveset(...).intersect(...)`). The simple branch already differs: the answer uses `_expr_needs_real_domain` and, when that is false, `solve_univariate_inequality` on a non-real symbol, while the number line always uses a real symbol and `solveset(..., S.Reals)`. Exceptions are wrapped in one and not the other.
- Impact: the drawn set and the verified answer can diverge on the cases where those two SymPy paths differ, and a fix to one solver does not reach the picture.
- Fix: `inequalities.py` exposes `inequality_solution_set(...)` and `compound_solution_set(...)`; `graph.py` calls them.
- Effort: S
- Verify: a test that for every inequality in the math STEM corpus asserts the number-line intervals equal the set behind the answer card.

### DUP-12 — ES-40 straggler: `mapGraphPoint` is still the JS twin of `mapPointW`
- Severity: Low
- Confidence: High
- Status: straggler of ES-40 (done). ES-40 moved the viewport, unmap, tick-step and tick-count functions to the worklet versions and kept `axisTicksW`/`formatTickW` apart for a stated reason (tick snapping). `mapPointW` is identical to its twin, and no reason is given for keeping both.
- Locations: `apps/mobile/lib/math/graphBlock.ts:487-504` `mapGraphPoint` (callers `graphBlock.ts:518`, `lib/math/trajectory.ts:100,109,120`, `components/rich/GraphCanvas.tsx:9`) vs `apps/mobile/lib/math/graphWorklets.ts:100-114` `mapPointW`. The header `graphWorklets.ts:6-8` notes "mapPointW, axisTicksW and formatTickW still have JS twins in graphBlock.ts".
- Evidence: the same four lines (`innerW`, `innerH`, `px`, `py` with `|| 1`); the only difference is the JS default `pad = 28` (jscpd #5).
- Fix: `mapGraphPoint = (x, y, b, w, h, pad = 28) => mapPointW(x, y, b, w, h, pad)`, or have callers import `mapPointW`.
- Effort: S
- Verify: `lib/__tests__/graphViewport.test.ts` / `graphScale.test.ts` stay green.

### DUP-13 — Phone: small helpers copied across `lib/` and features
- Severity: Low
- Confidence: High
- Locations:
  - Fence-JSON validator kit, one per diagram parser: `apps/mobile/lib/physics/circuit.ts:70-90` (`Invalid`, `fail`, `record`, `optionalText`), `apps/mobile/lib/physics/optics.ts:72-122` (`Invalid`, `fail`, `num`, `bool`, `record`, `point`, `text`, `list`, `guard`), `apps/mobile/lib/physics/simulation/parse.ts:56-95` (`MalformedScene`, `reject`, `codePoints`, `readPoint`, `optionalLabel`, `optionalList`). `circuit.optionalText` and `optics.text` have identical bodies, as do the two `record`s (jscpd #4). The shared `apps/mobile/lib/jsonFence.ts` `isJsonRecord` exists and only `simulation/parse.ts` uses it. These encode the server's Pydantic rules ("Pydantic counts code points") three times.
  - `boxesOverlap`: `apps/mobile/lib/physics/optics.ts:290-297` = `apps/mobile/lib/physics/simulation/labelSearch.ts:16-23` (jscpd #3).
  - Common-prefix/suffix diff: `apps/mobile/lib/math/composerChange.ts:4-18` `nativeEditRange` vs `apps/mobile/lib/math/pasteNormalize.ts:232-243` `extractInsertedDelta` (jscpd #8). The second could be `nativeEditRange(prev, next)?.added`.
  - "Is this an abort?": `apps/mobile/features/search/model/drawerSearchLogic.ts:15-18`, `apps/mobile/features/chat/model/sse.ts:10-12`, `apps/mobile/features/speech/model/pronunciation.ts:329-331` (also `CanceledError`), and inline in `apps/mobile/lib/api/client.ts:88`, `apps/mobile/features/speech/api.ts:98`, `apps/mobile/lib/cache/sessionResource.ts:47`.
- Impact: small, but the validator kit is the phone's half of the fence wire contract, so a limit rule changed on the server must be found in three parsers.
- Fix: `lib/fenceValidate.ts` (`strictRecord`, `optionalText(max)`, `point`, `list(max)`, `guard`) used by the three parsers; `lib/geometry/boxes.ts` `boxesOverlap`; `lib/api/abort.ts` `isAbortError`.
- Effort: S
- Verify: the existing parser tests (`optics.test.ts`, `circuit.test.ts`, the simulation snapshots) stay byte-identical.

### DUP-14 — Phone: FastAPI error bodies parsed in four places, and scan errors keyed by the server's English sentences
- Severity: Low
- Confidence: High
- Locations: `apps/mobile/features/chat/model/errorMessage.ts:10-33` `parseApiErrorDetail` (string or validation array), `apps/mobile/lib/scanner/scanReadError.ts:23-35` `scanFailureDetail` (string only), `apps/mobile/lib/api/consentRefusal.ts:21-29` (`detail.code`), `apps/mobile/features/auth/model/accountExists.ts:16-27` (`detail.code` plus `sign_in_with`). `ApiRequestError` (`apps/mobile/lib/api/client.ts:152-160`) keeps only the raw body as `message`, so each caller re-parses it. String keys: `apps/mobile/lib/scanner/scanReadError.ts:10-15` `DETAIL_KEYS` maps the exact English of `apps/api/app/services/scan_read.py:32-33,46` to i18n keys. `apps/mobile/lib/quota.ts:18-25` falls back to `/free limit|daily limit|today'?s limit/`, a coupling the server documents at `apps/api/app/services/quota/messages.py:62-64`.
- Evidence: no shared fixture pins the four scan sentences. The phone tests repeat the literals (`lib/scanner/__tests__/scanReadError.test.ts`, `components/__tests__/MathEquationScanner.test.tsx`, `features/chat/hooks/__tests__/useChatSend.test.tsx`).
- Impact: rewording a server message silently drops the phone's localisation, or turns a spend-cap message into an upgrade prompt.
- Fix: `ApiRequestError` parses once (`detail`, `code`); the server sends a `code` on the scan refusals (as it does for `consent_required` and `account_exists`), and the phone keys its i18n on `code`.
- Effort: S
- Verify: a contract fixture of the scan-read error bodies, generated by the API test and read by `scanReadError.test.ts`.

### DUP-15 — Retry policy "3 tries, 2 s × n" copied by comment
- Severity: Low
- Confidence: High
- Locations: `apps/api/app/core/jobs/worker.py:43-44` (`_MAX_ATTEMPTS = 3`, `_RETRY_BACKOFF_S = 2.0`), `apps/api/app/background/handlers.py:48-51` (`_MEMORY_LOCK_MAX_RETRIES = 3`, `_MEMORY_LOCK_RETRY_BACKOFF_S = 2.0`, "Match core.jobs.worker._RETRY_BACKOFF_S"), `apps/api/app/modules/memory/history_scan.py:41-42,101-105` (`_LOCK_RETRIES = 3`, `_LOCK_RETRY_SECONDS = 2.0`, linear backoff).
- Evidence: a "keep in sync" comment is the only link between the first two; the third repeats the numbers with no link.
- Fix: `core/jobs` exports the retry constants (or a `RetryPolicy(attempts, backoff_s)`), and both memory paths import it.
- Effort: S
- Verify: a grep test fails on a new numeric `*_BACKOFF*` constant outside `core/jobs`.

---
## Intentional twins: agreement check

### `apps/api/app/modules/chat/calculation_layout.py` (+ `calculation_layout_tail.py`) ↔ `apps/mobile/lib/markdown/calculationLayout.ts` (+ `calculationLayoutTail.ts`)

- Shape: function-for-function mirror (28 functions in Python, 29 in TS; the extra TS `withIndent` is the Python's two inline indent branches at `calculation_layout.py:380-391`). Every constant set is identical: math fence langs, `TEXT_COMMANDS`, `NUMERIC_COMMANDS`, the 11 `CHAIN_STOP_COMMANDS`, `CHAIN_STOP_WORDS`, trailing punctuation, chemistry marks, unit marks. Control flow matches line for line in every function I compared.
- Fixtures: `docs/fixtures/presentation_cases.json` (166 cases, 50 in `calculation`; ES-06 said 153). It is loaded by `apps/api/app/tests/modules/chat/test_presentation.py:23` and `apps/mobile/lib/__tests__/presentationCorpus.test.ts:16`. Both assert input → expected exactly and that expected is a fixed point; the phone file also checks streaming against settled for five cases. `test_inline_code_math.py` and `test_repl_transcript.py` point at the corpus in their docstrings.
- Branch coverage by the corpus (static trigger scan, `scratch-dup/fixture_triggers.py`; I could not run coverage): 35 of 37 branch triggers occur in at least one input, including `\begin`/`&` refusals, `\approx`, `\quad` breaks, thousands separators, chain stops, unit conversions, bare-number spans, lists, tables, headings, quotes, `\(…\)` (one line, multi-line, unclosed), `\[…\]`, math/latex fences, tilde and 4-backtick fences, `$$` blocks across lines, and hard breaks. Not triggered: a tab-indented line (`leave_prose_line`'s `\t` branch) and a non-ASCII letter after a backslash.
- Disagreements found by reading. All are Unicode classification, and none is exercised by the corpus:
  - Digits: Python `str.isdigit()` is true for `²`, `³`, Arabic-Indic and Ethiopic digits; TS `/\d/` is ASCII only. Sites: `_thousands_separator` (`calculation_layout.py:129` vs `calculationLayout.ts:75`), `_list_prefix` (`:404` vs `:383`), `_interior_line_blocks_fold` (`:438` vs `:421`), the bare-number test (`:314` + `inline_code.py:71-74` vs `:284-285`) and `converts_units` (`calculation_layout_tail.py:55` vs `calculationLayoutTail.ts:61`).
    - A diverging input: the plain line `y = 3², 4x = 8`. Python reads `², 4` as a thousands separator, finds no break and lays out an equals chain: `$y = 3², 4x$` / `$y = 8$`. TS breaks at the comma: `$y = 3²$` / `$4x = 8$`. The streaming phone and the saved server reply differ, and the server's row states y = 8.
    - The phone's `lib/markdown/unicodeChars.ts:1-8` aligned letters with Python (`\p{L}`) but not digits.
  - Command names: `_command_end` uses `isalpha()` (Unicode) vs `/[A-Za-z]/` (`calculation_layout.py:72,75` vs `calculationLayout.ts:61,64`). This matters only for a non-ASCII letter after `\`.
  - Whitespace: `lstrip(" ")` vs `trimStart()` (all whitespace, NBSP included) for the indent and the table/heading/list checks (`calculation_layout.py:380,388,414,432` vs `calculationLayout.ts:341,392,407`).
- Verdict: in agreement on ASCII. The three Unicode gaps should become corpus rows; then fix the TS to use `\p{Nd}`-equivalents, or make the Python use `ch in "0123456789"`, whichever the corpus decides.

### `docs/fixtures/presentation_cases.json`

Covers the twin above plus boundaries (42), maths (16), inline code (15), fences (12), repl (11), lists (9), replies (8) and notation (3), loaded by both suites as above. Gaps besides the Unicode rows: no rows for the fence-grammar cases in DUP-03 (a tilde fence holding a ```` ``` ```` line, a closer shorter than its opener, a fence inside `>`).

### `docs/fixtures/physics_replies.json`

A producer/consumer contract, not a twin:

- API: `apps/api/app/tests/modules/physics/test_physics_reply_contract.py` regenerates 8 direct replies (one per answer shape) and requires byte equality. `UPDATE_PHYSICS_FIXTURE=1` rewrites the file.
- Phone: `apps/mobile/lib/__tests__/physicsReplyContract.test.ts` reads them through `splitAnswerNotation`, `readableLatexFallback`, `markdownToCopyText` and `markdownToSpeechText`.
- Gap: the `parallel_resistance` reply carries a ```` ```simulation ```` circuit fence that the phone test never parses. No test feeds server-written `simulation`/`circuit`/`rays`/`wave` fences to the phone parsers; `apps/mobile/lib/__tests__/fixtures/simulationScenes.ts` is hand-written on the phone.
- The phone re-declares the server's Pydantic limits by hand (`apps/mobile/lib/physics/simulation/parse.ts:22-48` vs `apps/api/app/modules/physics/schemas/simulation.py:30-499`). I diffed the enums (`scratch-dup/sim_schema_diff.py`): `TitleKey` 22/22 and `ArrowKind` 5/5 agree; the phone's `SCENE_KINDS` lacks circuit/rays/wave by design, since those have their own parsers. The limits I checked also agree: bodies 4, path 500, vectors 6, parts 4, label 24, body label 32 (truncated on the phone), alt 300, strobe 2–12.
- Verdict: in agreement today, but nothing keeps it so. Add the fixture's simulation fence to the phone contract test (`readScene` / `parseCircuitSpec` must accept it). The sibling `docs/fixtures/chemistry_replies.json` follows the same pattern (`test_chemistry_reply_contract.py`, `chemistryReplyContract.test.ts`).

---

## Looked wrong, actually fine

- **The three `/scan/read` endpoints** (`modules/{math,physics,chemistry}/api.py`) are thin over one seam, `services/scan_read.read_scan`. The differences are deliberate: math reads with Mathpix, physics de-LaTeXes, chemistry passes text through.
- **Subject fence passes** share `services/answer_fence` (`land_answer_card`, `normalize_owned_fences`, `strip_forged_verified_markers`), `services/answer_check` (`stated_verdict`, `correction_line`) and the `services/workout` five-part layout. Apart from the fence-language lists in DUP-03, no plumbing is re-implemented per subject.
- **Physics catalog rows and chemistry `stated_bindings`** (13 + 1 jscpd groups) are documented catalog exceptions; the repetition is the data.
- **Forwarding signatures:**
  - `memory/surface.py` ↔ `memory/retrieval.py` (#66, #67) is a forwarding facade. Whether it should exist is the dead-code reviewer's call (rule 9).
  - `subject_solving._augment_*` (#75, #76) is one protocol implemented three times.
  - `turn_resources` (#70) and `stream_pipeline` (#71) repeat signatures.
  - `useChatScreenBodyProps` ↔ `ChatScreen` (#12) is prop plumbing, not logic.
- **`Molecule3DBlock` (SVG) ↔ `SkiaMoleculeCanvas` (Skia)** (#25) is an intentional fallback pair over one shared layout (`laidOut`).
- **`ChartBlock` ↔ `MermaidBlock`** (#30, #31) already share `useWebPreviewHeight`, `useDeferredWebViewMount`, `useStaticOnlyNavigation`, `getPreviewWebView`, `VisualCard` and `CopyButton`. What is left is about 40 lines of toolbar JSX (source toggle, expand, copy-and-open-editor), whose accessibility labels differ for the same control. Polish.
- **`MemoryScreen` ↔ `MemoryDocumentScreen`** (#10) repeat the instruct `submit` callback and the error `StateView`. A `useMemoryInstruct(isCurrentView)` hook would remove about 12 lines. Polish.
- **`ChipText` ↔ `RichBodyText`** (#28) are two tiny inline-token renderers. Polish.
- **The `if commit: … else: flush()` tail** (12 sites in 9 repository files, #78) is the transaction convention CLAUDE.md documents.
- **Lazy `__getattr__` exports** in module `__init__` files (#64) are the module-surface convention.
- **ES-01 re-check.** The remaining `.Nf`/`.4g` formatting (`math/solve/geometry.py:35-45`, `school/geometry_measures/working.py:18-24`, `school/number_facts.py:197`, physics working lines) formats irrational values (π, √), non-terminating fractions or working rows, never a tie-able verified answer. No ES-01-class straggler found.
- **ES-09 re-check.** `fold_scientific` runs before `normalize_symbolic_request` in all three subjects (`math/match/scan.py:107`, `physics/extract.py:117,199`, `chemistry/extract.py:50`).
- **Push vs email reminders** skip recurring rows differently on purpose (`a6d0773e2`). The duplication is the rest (DUP-10).
- **Phone reminder lead options** `[5,10,15,30,60]`, default 10 (`features/todos/model/reminderTiming.ts:3-6`), match the server (`services/reminder_timing.py:11-13`). The surrounding semantics (local alert vs server scan) differ on purpose.

## Open questions for the team

1. **Fence grammar.** Is the API's backticks-only `md_fence_scan` deliberate (the server only ever writes ```` ``` ````), with `normalize_owned_fences` the designated bridge for model text? If so, every pass that reads model text must run after it, and `close_unclosed_fences` still needs real open/close tracking instead of parity (DUP-03).
2. **Subject classifiers.** May the prompt pack ever differ from the solver's subject (`classify_presentation_subject` vs `detect_subject`)? If yes, say why at both sites (DUP-02).
3. **Picture nouns.** `chat/prompt_constants/visuals.py:124-139` `_IMAGE_GEN_MENTION_WORDS` vs `images/gen_intent_words.py:15-33` `IMAGE_NOUNS` (pylint) serve different purposes (honesty hint vs intent), but the mention list lacks `drawing`/`drawings`. Intended?
4. **Fence-type lists.** Plane-figure kinds appear in `math/schemas/geometry_request.py:12-22` (a Literal), `math/fence.py:73-85` (with the alias `rect`) and `math/tools/direct.py:383-393`. Graph fence types appear in `math/schemas/graph.py:57`, `math/fence.py:87`, `math/text_plot.py:24` and `math/tools/direct.py:371-376`. Derive them from the schema Literals (`typing.get_args`)? Low.
5. **Chemistry scan reading.** `modules/chemistry/read.py:23-38` returns the vision text raw, while physics de-LaTeXes it (`modules/physics/read.py:77-96`, applied at `:99-115`). Intended? That is a missing reuse, not a copy.
6. **Tool-call arguments.** The same `arguments` JSON string is `json.loads`ed in six places during one turn (`modules/chat/tool_loop/calls.py:84,115`, `tool_loop/text_calls.py:46`, `gateways/tool_completion.py:127`, `gateways/mcp/registry.py:73`, `modules/math/tool_check.py:309`), each with its own error handling. Parse once into the call object?
7. **Regenerate error frame.** `modules/chat/ws_api.py:134` builds the invalid-regenerate error frame by hand (no `user_message_saved`), while the invalid-message path at `:179` uses `stream_events.turn_error_payload`. Intended?
8. **Presentation bug, both twins.** Out of this dimension, for the correctness reviewer. `_thousands_separator` skips spaces after the comma (`calculation_layout.py:123-129`, same in TS), so `$x + y = 10, 2x - y = 5$` is laid out as `$x + y = 10, 2x - y$` / `$x + y = 5$`, a row that states x + y = 5. Static reading only; add it as a `presentation_cases.json` row.
9. **Fence wire schemas.** These are written twice: Pydantic on the API, hand validators on the phone (DUP-13's kit). They agree today. Generate the phone's limits from `model_json_schema()`, or keep a fixture of server-written fences that the phone parsers must accept?
