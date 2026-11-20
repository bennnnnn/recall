# Review: the physics reading layer: from a student's words to a check mark (2026-11-19)

**Scope.** How a question becomes a verified physics answer: the subject decision, the physics gate,
the request preflight, the extractors, the catalog binder, the solve, and the formal reader. Read
from `origin/main` at 6777dac1, which holds the Grade 7 and 8 corpora and the finalize review.

**No app code is changed.** The only code added is
`apps/api/app/tests/review/test_reading_completeness.py`: 17 probes, each asserting a verified
wrong number that the server gives today. They are skipped unless `RECALL_REVIEW_PROBES=1`, the
same convention as the finalize probes. Paths are `apps/api/app/modules/physics/…` unless they
start with `app/` or another top folder.

**Why this area.** Every verified wrong number found in the Grade 7 and 8 rounds came from here:
- the 9 in `stem_corpus_pending/physics/`;
- 17 more found below.

Fixes A, B and C, and the finalize review, all act after the answer exists. This layer decides what
the answer *is*, and whether it carries a check mark.

## Summary

- **One rule is missing: a check mark is given by one reader that never accounts for the whole
  question.**
  - The extractors take the words they recognise and fill the rest with defaults: g = 9.81, v₀ = 0,
    the law's "default result", the first value of a kind, a magnitude for a velocity.
  - The only completeness checks are for numbers beside a unit (`accounting.py`) and number words
    beside a unit (`spelled.py:60-75`).
  - Meaning words ("average", "between", "not", "north/south", "half of") and operators ("×") are
    never accounted for.
- **This is systematic, not anecdotal.** 9,929 meaning-changing rewordings of the 1,332 answered
  physics corpus questions went through the real chat path:
  - "average" is ignored in 25 of 26;
  - a north→south reversal in 36 of 37;
  - "not" in 411 of 426;
  - a lost-superscript given ("3 × 102 K") in 118 of 234;
  - "half of 20 m" or "2 × 20 m" in 78–96%.

  Wrong verified numbers span about 60 ops (section 2).
- **Seven default fills have no check against the question** (section 1.3). Each one has a
  reproduced wrong verified number.
- **The one reader that reads the whole question (the formal reader) is off whenever an extractor
  answers** (`app/modules/chat/formal_turn.py:74-75`). The two readers never meet.
- **The physics gate measures solver coverage, not physics.** A physics question no cue covers goes
  to maths' catch-all (`math/tools/word_problem.py:203`): 3 critical misreads. The turn's own model
  read never decides the subject (section 3).
- **The offline judge can't see a wrong sign or direction** (`abs()` on both sides). It drops the
  first value of "I1 = 2 A, I2 = 4 A", and accepts any value on the card for any part. 46% of
  catalog ops are never reached by the corpus (section 5).
- **Recommendation:** two independent readers, with a check mark only when they agree, plus one
  structural completeness rule for numbers. The migration is 7 small PRs, and the judge and
  fixtures come first (sections 6 and 7).

## 1. The map

The full path, with file:line for every step, is in Appendix A. In short:

### 1.1 The pipeline (first match wins at every step)

1. **Two subject readers, never reconciled:**
   - the turn's deterministic read (`app/modules/chat/turn_prep/reading.py:49-73`, through
     `app/services/subjects/order.py`);
   - the model's live read beside it, which decides Auto's lane, the worked layout, pictures and
     the formal reader, but never the subject.
2. **Subject order** (`order.py`): code, scanned photo, closed chemistry (:199), the physics gate
   (:201), physics symbol givens (:213), chemistry-shaped (:216-220), maths (:225; its
   word-problem catch-all), chemistry lookup (:240).
3. **The physics gate** `needs_physics` (`extract.py:114-175`): 294 phrase cues, 100 regexes
   (`registry.py:192-251`), and "some catalog law binds". It doesn't ask its own extractors.
4. **Request preflight** (`request.py:355-377`):
   - `fold_scientific` (`app/services/number_text.py:153`);
   - `main_question` and `claims` stripping;
   - `has_unread_quantity`, the only "unread means decline" rule;
   - collision and projectile parsing.
5. **32 ordered extractors** (`PHYSICS_EXTRACTORS`, 11,062 lines). The first claim wins. A value is
   picked by nearness to a keyword, else the first match of its unit
   (`stated_values.py:157-179`).
6. **Completion** (`complete_physics_intent`): gravity rules and the accounting check
   (`accounting.py`: "left unbound", "of a kind the law never uses").
7. **The catalog binder** (`binding.py`: `bind_physics_intent`, `bind_solved_for`;
   `app/services/law_binding/`): inverse solves and chains, for laws with a binding only. It also
   catches a question whose extractor claim was refused (`extract.py:279-295`).
8. **Solve** (`solver.py:128`). Its one result check refuses an impossible sign or kind
   (`_rule_its_kind_breaks`). Then the verified block (`block.py`) and the direct reply
   (`direct.py`).
9. **The formal reader** (`formal_read.py`, `app/services/formal/`): only when no solver verified
   the turn.

### 1.2 Size

| component | lines |
|---|---|
| `modules/physics` total | 51.5k |
| the catalog | 13.1k |
| the extractors | 11.1k |
| the solvers | 9.7k |
| the shared law-binding engine (`app/services/law_binding/`) | 3.3k |

### 1.3 Every place a value or law is filled in, not read

19 kinds (Appendix A §2). **Seven have no check against the question, and each has a reproduced
wrong verified number:**

| # | default | file:line | the check that's missing | reproduced |
|---|---|---|---|---|
| D2 | v₀ = 0 | `extractors/kinematics.py:201`, `:217` | the motion is a drop | −98.1 m/s for "a car accelerates… velocity after 10 s" (pending g8-154); "thrown straight down" with no speed (probe 5) |
| D3 | the free-fall law from "velocity after" / "speed after" | `kinematics.py:75-84`; gravity cues are required only for an acceleration ask (`:174-180`) | anything falls | g8-154 |
| D5 | `reflection_angle` from the word "reflected" | `extractors/optics.py:124` (after `_BETWEEN_RAYS_RE`, `:65-68`, misses) | the ask is the angle of reflection | 40° for 80° (g8-153) |
| D6 | the final velocity for any "speed" or "velocity" | `extractors/suvat.py:97-111` (`_PHRASE_OP`) | the ask is not an average | 10 for 5 (g7-034, g7-157); 30 for 20 (probe 2) |
| D7 | magnitudes for velocities with compass words | `suvat.py:215`; `motion.py:126` reads only rest | directions agree | 3.17 for 4.83 (g8-156), 2 for 6 (g7-159) |
| D16 | an unread mantissa | `app/services/number_text.py:153` (`_SCIENTIFIC` folds only "× 10^n") | the number before "×" was read | 790.4 Pa for 103,360 (g8-155); 25.8 Pa for 500 (g7-158); 76.3 m/s for 20 (probe 1) |
| D17 | a stated equivalence read as a given | `accounting.py:8-9` (a different-kind leftover is a "distractor") | the law actually uses what was stated | 14.7 W for 4414 W (g7-069); 44.3 m/s for 8.33 (probe 7) |

**The other twelve fills are read from the question's words, or are physically harmless:**
- g on another planet;
- water's density;
- a planet's mass;
- particle constants;
- "from air";
- the first value of a kind;
- and the rest listed in Appendix A §2.

D13 (sea-level pressure) is unconditional, but harmless.

## 2. Wrong answers, systematically: the rewording hunt

**Harness.** Every answered physics entry with no history (1,332) was put through every rewording
that applies to it, 9,929 rewordings in all. Each went through `stem_sweep.run_entry`, the real chat
path, beside its unchanged baseline. Each rewording kind has an oracle:

| oracle | used for | a verified number is wrong when |
|---|---|---|
| decline | a needed given removed, "not" | any verified number is given |
| changed | a direction, "average" | it equals the baseline: the new words were ignored |
| explicit | "half of 20 m", "2 × 20 m" | it differs from the server's own answer on the explicit value ("10 m") |
| same | the meaning is unchanged | it differs from the baseline |

There were no harness errors.

| rewording | judged | wrong or ignored |
|---|---|---|
| half of a given | 824 | 96% |
| a product given ("2 × 20 m") | 828 | 78% |
| "average" before speed/velocity, in accelerated motion | 26 | 25 |
| compass reversal on two velocities | 37 | 36 |
| "not" in the setup | 426 | 411 |
| lost superscript ("3 × 102 K") | 234 | 118 |
| a needed given removed | 828 | 61 (a default filled in) |
| "(1 hour = 3600 s)" | 1,332 | 13 |
| a second body with its own mass | 1,332 | 9 |
| "It happened at 3 pm." | 1,332 | 6 |
| "the" removed from the ask | 687 | 4 |
| the question moved before the setup | 856 | 5 |
| "initial" ↔ "final" | 39 | 2 |

**The ops hit most:** `time_to_ground` 134, `suvat_distance` 118, `suvat_velocity` 67, `net_force`
65, `range` 65, and about 55 more. Every extractor family is hit.

### 2.1 The clusters

| # | mechanism | file:line | probes in `test_reading_completeness.py` |
|---|---|---|---|
| U1 | **An operator on a number is never read or refused.** The mantissa before "×" is dropped. "Half of 20 m" passes because number words are refused only beside a unit | `app/services/number_text.py:153`; `spelled.py:60-75` | `1` (76.3 m/s for 20), `1b` (15.7 L for 5.33), `3` (2.02 s for 1.43), `3b` (4 m/s² for 2) |
| U2 | **Qualifiers in the ask are unread** ("average", "initial") | `extractors/suvat.py:97-111`; the kinematics and collision asks | `2` (30 m/s for 20), `11` (1.75 for 4) |
| U3 | **Negation is unread** | no reader | `4` ("thrown, not dropped": 3.03 s; must decline) |
| U4 | **Defaults fill a missing value**: v₀ = 0, a single value as the whole change, a named part without a value left out | `kinematics.py:217`; `extractors/stated_change.py:102-103` | `5` (24.3 m/s), `5b` (10 V), `5c` (1.05 mA) |
| U5 | **A value is bound by its unit's family, not its role**: the first length is the height, the first mass is the particle's, a clock time feeds refraction | `kinematics.py:205-214`; `extractors/quantum.py:160`; `extractors/optics_laws.py:203` | `6` (1.41 s), `10` (2.21e-40 m for 7.27e-10), `10b` (90° for 19.5°) |
| U6 | **A refused reading falls through to a looser law** (the catalog binder fits any law whose inputs appear); the direction of a throw is read by word position | `extract.py:279-295`; `kinematics_asks.py:129` | `7` (44.3 m/s for 8.33), `7b` (4.93 s for 2.48) |
| U7 | **The ask is read by a word list that needs grammar** ("How long must runway be?" is a time) | `ask.py:260-264` | `8` (20 s for 600 m) |
| U8 | **States are read in text order**: with the question first, start and end swap | the gas-law state readers | `9` (1.5 L for 2.67) |

```
RECALL_REVIEW_PROBES=1 uv run pytest app/tests/review/test_reading_completeness.py -q   # 17 passed
uv run pytest app/tests/review/ -q                                                       # skipped in CI
```

**Caveats:**
- "minimum" is a weak oracle, since a minimum can equal the value; it has no probe.
- Mechanically inserted "not" reads unnaturally; the natural "thrown, not dropped" reproduces.
- Halves and products use the server's own answer on the explicit value as the oracle. That can
  hide a case but never invents one.

## 3. The gate and the subject split

Measured over the 7,750 corpus lines (Appendix B).

- **Physics questions that miss physics:** 49 of 1,525 standalone physics `answer` questions get no
  physics subject.
  - 42 get none: multi-problem lines, a lap's velocity, compass directions, tables, "kN".
  - 7 go to maths. 3 of those are the critical misreads (g8-026, g8-035, g7-023), all claimed by
    `word_problem_candidate`, which takes any line with a request word and two numbers. The other 4
    are unit conversions ("Convert 30 m/s to mph").
- **The gate and its own readers disagree.** g7-037 completes in an extractor but gets no subject.
  Separately, 151 standalone physics questions pass the gate and stay unanswered.
- **Physics' guard against maths is missing.** Chemistry has a "shaped" guard step before maths
  (`order.py:216-220`); physics has none.
- **The model read's subject is never the subject.** `TurnReading.subject` is decided from the
  order before the read arrives.
- **A cue on the wrong side:** the cue "how long until" (`extractors/kinematics.py:64`) makes credit
  card payoff and battery-percentage lines physics. Money takes them at prep, so this is the mirror
  of the finalize review's car-loan card.
- **A units-only gate**, prototyped in a review script, not committed:
  - **As a replacement, no.** Its recall is equal (1,476 against 1,481), but it claims 39 of 115
    physics look-alikes, 144 maths geometry lines and 185 chemistry lines.
  - **As a guard step before maths, yes**, only where the gate says no, needing a physics unit, an
    ask and no errand words. It newly claims 63 physics answers, including all 3 misreads, and 28
    physics declines. It needs pure-length units left to maths' shapes. The 9 look-alikes it still
    takes need the model read.

## 4. The formal reader as a second reader

Appendix C has the detail.

**What it is.** A model writes the question as a `FormalProblem` (`app/services/formal/problem.py`):
- the givens, each with its quote from the question;
- the unknowns and equations;
- the target;
- its own answer.

The server checks and solves the setup (`app/services/formal/solve.py:217-306`):
- every quote must be in the question and contain its number (`grounded`, :118-130);
- units must agree across each equation;
- constants must be standard;
- the solution must check back.

The server's answer is used only when it agrees with the setup's own.

**Today it runs only when no solver verified the turn** (`formal_turn.py:74`), so it can catch none
of the wrong numbers above. Each of those turns already had an extractor's check mark.

**What it costs and how it's measured:**
- Setup read: median 0.99 s, p90 1.5 s; finalize waits 2 s at most.
- Cost: about $0.18 per 1,000 turns.
- Recorded evals (`docs/FORMAL_READER.md`):
  - 430 setups agreed with the model's own answer, and none was wrong;
  - in disagreements with the Free reply model, the server was right 36/36.
- **None of this is reproducible offline:** no setups are recorded, and `formal_eval.py` needs a
  live key.

**Against the wrong numbers here:**
- **Caught by construction:** "1.36 × 104". Grounding confirms 13600 and refuses 104.
- **Likely declined:** a missing acceleration (`solvable: false`).
- **Up to the model:** "average", directions, "between the rays", stated equivalences. A model reads
  these words; a regex doesn't.
- **What grounding doesn't check:**
  - a given's unit against its quote;
  - a dropped given;
  - a misreading the setup and the model share.

**Three architectures:**

| | how it works | correctness | latency | offline testable | migration |
|---|---|---|---|---|---|
| A (today) | extractors, formal only as a fallback | the 9 + 17 ship with a check mark | none added | yes | none |
| B | formal beside **every** physics turn; a check mark only when the extractor and the formal setup agree; on disagreement the server's own check decides, or the reply goes unmarked | each misreading becomes a disagreement | ≈1 s before an instant card is marked | only with recorded setups (section 5) | small: drop the `:74` guard, add an agree-or-unmark step |
| C | extractors only, plus a completeness rule over every meaning word | depends on a word inventory | none added | yes | large, and it is a word list deciding intent, against the owner's rule |

**Recommendation: B, plus one word-free structural rule.** Every number token the question states,
mantissas and number words included, must be bound or the turn declines. The rule extends
`accounting.py` and drops its "different-kind distractor" waiver for anything the formal setup
quotes. B keeps "the model reads, the server checks", and turns every misreading found here into a
disagreement instead of a check mark.

## 5. What the offline tests can't see

Appendix D has the detail.

- **No model read runs offline.** `route_case` (`app/tests/behavior/harness.py:391`) runs in mock
  mode and never calls `stream_entry._attach_reads` (`app/modules/chat/stream_entry.py:102`).
  - The live read, the formal reader, figures and charts are `None` offline.
  - The sweep judges the deterministic subject (`harness.py:557`).
  - In production, the formal reader runs on exactly the corpus's `gap` and `decline` entries, and
    nothing offline shows what it does there.
- **"Answered" proves an end-to-end reply only for server-written replies.** For a model-written
  reply, only the server's `verified_answer` is matched, against any part.
- **The judge's blind spots, all reproduced:**
  - **Sign and direction are ignored** (`abs()` on both sides): +6 passes where −6 is right.
  - **A direction word breaks unit parsing**, so a right "6 m/s² west" is reported wrong.
  - **`card_values("I1 = 2 A, I2 = 4 A")` keeps only 4 A**: digit-named symbols drop values.
  - **Any value on the card passes for any part**, so swapped parts pass.
  - **False criticals:** °F, and "K" for a °C rise. The Grade 7/8 corpus worked around both.
- **Coverage:** 249 of 539 catalog ops (46%) are reached by no corpus entry, and 97 more by exactly
  one. School-level ops among the unreached include `acceleration`, `bernoulli_pressure`,
  `combined_gas_*` and `electric_potential`.
- **The trace doesn't record which extractor claimed a turn**, so per-extractor coverage can't be
  measured.
- **The fix extends a pattern that already exists.** Cases already pin a model's pick with an
  `AsyncMock` (`Case.referent`, `posed`, `figure`). Add:
  - `Entry.read`: a recorded `TurnDecision`, run through the real `_attach_reads`;
  - `Entry.formal`: patch `read_physics_setup`, `formal_read.py:60`;
  - `Entry.reply`: run through `enrich_final_content`.

  A recorder script like `formal_eval.py` writes them once, and CI replays them.


## 6. A target design

**One rule: a check mark means two independent readings of the whole question agree, and every
number the question states is accounted for.**

1. **The subject.**
   - The deterministic order decides when its readers agree.
   - When the physics gate and its extractors disagree, or nothing claims the line, the turn's
     model read decides.
   - A units guard step before maths' catch-all keeps a physics line away from
     `word_problem_candidate` offline. It never verifies anything.
2. **The reading.** Both run on every physics turn:
   - **Extractors and the binder (fast, offline)** read a setup.
   - **The formal setup (model, about 1 s)** reads one too.
   - Both are normalised to the same form: givens with values, the asked quantity, the law or the
     equations.
3. **Completeness, structural and word-free.**
   - Every number token is bound by at least one of the two readings, or the turn declines. That
     includes a mantissa before "×", "half of", a number word, and a clock time.
   - A leftover given is a distractor only when the formal setup also leaves it out.
   - Defaults D2, D3, D5, D6, D7, D16 and D17 are removed as silent fills. A default is allowed only
     when the formal setup states the same value (g = 9.81 for a stated fall, v₀ = 0 for "from
     rest").
4. **The check mark.**
   - The server solves both setups.
   - **Agreement** within the rounding rule gives one check mark.
   - **Disagreement:** the reply's answer stands unmarked, under the owner's "solver disagreement
     comes first" note.
   - **Only one setup:** fast path only means unmarked; formal only means today's formal behaviour.
5. **Evidence.** The corpus carries recorded reads and setups per entry. The judge checks sign,
   direction and the part each value belongs to. The trace records the extractor and both setups.

**What this keeps from the owner's decisions:**
- The model reads and the server checks: the formal setup is a model read that the server checks.
- An unchecked right answer stays: disagreement unmarks, it doesn't refuse.
- Solver disagreement comes first.
- No per-phrase rules: completeness is about numbers, and meaning words are left to the model read
  instead of a new word list.
- v1's subjects stay maths, physics and chemistry.

## 7. The migration as small PRs

| PR | change | proof | behaviour |
|---|---|---|---|
| 0 | **Judge and trace.** Signs and directions compared, direction words parsed, digit-named symbols split, values tied to their part labels, °F and a K rise read; the trace records the extractor | the sweep re-run. Any newly visible wrong number moves to `stem_corpus_pending`, never into CI | test-only |
| 1 | **Recorded reads.** The recorder script, and `Entry.read` / `Entry.formal` / `Entry.reply` fixtures for the STEM corpora (the existing pinned-pick pattern) | the decision dump grows rows for the formal reader | test data |
| 2 | **Number completeness.** Fold or refuse a mantissa before "×"; extend `has_unread_quantity` to any number token not bound; remove the different-kind distractor waiver | probes 1, 1b, 3, 3b, 7, 10, 10b and pending g8-155, g7-158, g7-069 flip from a wrong number to a decline; the decision diff shows only declines | declines only |
| 3 | **Cue-less defaults removed.** Free fall needs a falling motion; "reflected" alone never picks the reflection angle; a refused extractor claim never falls through to a looser law (`extract.py:279-295`) | probes 5, 6, 7b and g8-153, g8-154 decline | declines only |
| 4 | **The units guard before maths' catch-all, plus the model read deciding an unclaimed subject** | g8-026, g8-035 and g7-023 become physics; the sweep's look-alikes stay non-physics | small |
| 5 | **Formal beside every physics turn, a check mark only on agreement**, behind a flag, with the recorded setups | probes 2, 4, 9, 11 and g7-034, g8-156 become unmarked or right; check-mark rate measured per corpus | flag |
| 6 | **Flag on.** Then retire the extractor ask lists that B makes redundant (`_PHRASE_OP`, `_HOW_LONG_IS_LENGTH`, the reflection fallback), one per PR, each with its decision diff | per list | removal |

**Size.**
- PRs 0 and 1 are test code and data, a few hundred lines.
- PRs 2–4 are small, each under 200 lines.
- PR 5 is about 300 lines.
- PR 6 is where code goes: the ask-reading word lists in the extractors, an estimated 1,000–2,000
  of the extractors' 11.1k lines. That number is an estimate from `wc -l` of the ask lists, not a
  measured diff.

## 8. The five changes that remove the most wrong check marks

1. **Number completeness (PR 2).** One structural rule covers U1 and D16/D17:
   - lost superscripts (50% wrong);
   - "half of" and products (78–96%);
   - stated equivalences;
   - distractor masses and clock times.

   About 1,600 of the wrong rewordings, plus 3 pending cases.
2. **A second reader for the check mark (PR 5).** The formal setup beside every physics turn covers
   the meaning words no structural rule can:
   - "average" (25/26);
   - directions (36/37);
   - "not" (411/426);
   - "between the rays";
   - initial versus final;
   - states read in text order.

   It is the only fix that doesn't need a word list.
3. **No silent defaults (PR 3).** The −98.1 m/s free fall, the 40° reflection and the looser-law
   fall-through become declines.
4. **A judge that can see a wrong sign (PR 0).** Today a direction error passes the corpus, and a
   right "6 m/s² west" fails it. Until this is fixed, no corpus result about directions can be
   trusted.
5. **The subject from quantities and the model read (PR 4).** It ends the three physics questions
   answered as maths, and the payoff and battery lines taken as physics.

## Appendices

These are the investigation notes the sections above summarise. Each was read from the code at
6777dac1, with file:line throughout.


### Appendix A: the reading path, step by step


All paths are relative to `apps/api/app/`. Sizes come from `wc -l`.

#### 0. Size

| component | files | lines |
|---|---|---|
| `modules/physics/` total | all | **51,504** |
| extractors (32 in `PHYSICS_EXTRACTORS`) | `modules/physics/extractors/` | 11,062 |
| catalog (law rows, cues, bindings) | `modules/physics/catalog/` | 13,089 |
| solvers | `modules/physics/solvers/` | 9,717 |
| shared law-binding engine | `services/law_binding/*.py` | 3,280 |
| request preflight, gate, accounting, binder | extract 295, request 515, bodies 379, claims 260, numbers 330, spelled 71, accounting 411, binding 437 | 2,698 |
| parts, chain, follow-ups | split_parts 303, chain_solve 199, followup 444 | 946 |
| solve facade, block, direct | solver 152, block 321, direct 366 | 839 |
| formal reader | `physics/formal_read.py` 116, `services/formal/*` 633 | 749 |
| subject dispatch | order 242, dispatch 310, registry 513 | 1,065 |
| the turn's reading | turn_prep/reading.py 301, core/readings.py 307, turn_reading/turn.py 141 | 749 |
| competing maths reader | `math/tools/word_problem.py` | 337 |

#### 1. The pipeline, in order

1. **The turn's read: two readers of one subject.**
   - **Deterministic: `turn_prep/reading.py:37 read_turn`.** It runs in the SymPy pool, once per
     turn (`core/readings.py:57 @reading`, `:96 kept_per_turn`). It produces
     `turn_reading/turn.py:35 TurnReading`: the subject and `subject_reason` come from
     `services/subjects/dispatch.detect_subject` (`reading.py:139-146`).
   - **Model: the live read** (`chat/decider_read.py`, `TurnDecision.subject`). It runs beside
     the turn and decides Auto's lane, the thinking, and the formal reader (step 9).
   - **No reconciliation.** The solve follows the deterministic subject; the formal reader and the
     picture passes follow the model's. Nothing reconciles the two. Finalize-review probe 1 has a
     turn dispatched to maths while the read says physics.
2. **Subject order: `services/subjects/order.py:150-242`**, first match wins.
   - code → a scanned photo → `chemistry_closed`;
   - **`needs_physics` (`:201`)**, unless a maths curve is stated and physics extracts nothing
     (`:203-206`);
   - `is_symbol_givens_request` (`:213`) → chemistry-shaped → **`needs_symbolic_math` (`:221`)**,
     which includes maths' word-problem path → chemistry question → none.
3. **The physics gate: `physics/extract.py:114 needs_physics`.** It is a union of:
   - the errand filter (`:122`);
   - a force picture (`:127`) or named symbols (`:129`);
   - `_ADVANCED_PHYSICS_RE` (`:56-63`, "recognised then unverified", including "transformer");
   - the drag request (`:142`);
   - a digit-free list (`:146`);
   - **`has_supported_physics_cue` (`registry.py:251`):** `PHYSICS_CUES` (`:193`, 24 cue lists)
     and `PHYSICS_CUE_RES` (`:224`, 26 regex lists), checked on the text **as written**;
   - **`bind_physics_intent` / `bind_solved_for` (`:157`)**, the catalog binder (step 7);
   - the two-stage, chase and legs readers (`:166-173`);
   - `reads_in_parts` (`:175`).

   **The gate is "a solver could take this", not "this is physics".** A physics question that no
   cue or law covers falls to maths.
4. **Request preflight: `extract.py:212 read_physics_request` → `request.py:356 prepare_physics_request`.**
   - `without_markup`; `_named_symbol_request`.
   - **`fold_scientific`** (`services/number_text.py:153 _SCIENTIFIC`, `:191`): folds
     `a × 10^n` and `10^n`. A mantissa then "×" then a bare number ("1.36 × 104") **is not folded
     and not refused**: "1.36 ×" is dropped as prose, and 104 becomes a given.
   - `normalize_symbolic_request`; `main_question` (`bodies.py`, which drops a side question about
     another body); `question_without_claims` (`claims.py`, which drops "I got 19.8 m/s").
   - `normalize_physics_units` (`numbers.py`).
   - **`has_unread_quantity` (`spelled.py:60`, called at `request.py:359`): rejects the whole
     message** for a number word, a scale word or a fraction beside a unit ("one hour", "half
     hr"). **This is the only "unread text ⇒ decline" rule in the path, and it covers only number
     words.**
   - `normalize_physics_numbers` (`request.py:363`); the maths-power guard (`:367`); collision and
     projectile parts (`:372-377`).
5. **Gatekeeping in `_extract_physics_intent` (`extract.py:236-295`):**
   - `has_ask` (no ask means None, `:249`);
   - a bare hypothetical with no asked phrase means None (`:254`);
   - a whole two-stage trip (`:263`).
6. **Extractors, first claim wins** (`registry.py:126-189`; refused claims fall to the binder).
   Each has a cue gate and keyword-nearness value pickers:

| # | extractor | file:line (file lines) |
|---|---|---|
| 1 | extract_drag_intent | extractors/drag.py:335 (344) |
| 2 | extract_school_extension | school_extensions.py:108 (119) |
| 3 | extract_stopping_distance | stopping.py:92 (148) |
| 4 | extract_two_stage_intent | two_stage.py:103 (196) |
| 5 | extract_chase_intent | relative_motion.py:41 (126) |
| 6 | extract_legs_intent | relative_motion.py:91 |
| 7 | extract_rate_intent | rates.py:33 (161) |
| 8 | _extract_kinematics_intent | kinematics.py:146 (316) |
| 9 | _extract_suvat_intent | suvat.py:215 (328) |
| 10 | extract_projectile_intent | projectile.py:110 (295) |
| 11 | _extract_momentum_intent | momentum.py:180 (324) |
| 12 | _extract_friction_intent | friction.py:111 (260) |
| 13 | _extract_circular_intent | circular.py:224 (310) |
| 14 | _extract_shm_intent | oscillations.py:120 (255) |
| 15 | _extract_pendulum_intent | oscillations.py:60 |
| 16 | _extract_spring_intent | oscillations.py:182 |
| 17 | _extract_electrostatics_intent | electrostatics.py:50 (129) |
| 18 | _extract_circuit_intent | circuits.py:210 (384) |
| 19 | _extract_torque_intent | torque.py:47 (240) |
| 20 | _extract_tension_intent | tension.py:74 (207) |
| 21 | _extract_vector_force_intent | tension.py:167 |
| 22 | _extract_waves_intent | waves.py:61 (233) |
| 23 | _extract_optics_intent | optics.py:137 (158) |
| 24 | _extract_thermal_intent | thermal.py:88 (205) |
| 25 | _extract_gravitation_intent | gravitation.py:49 (183) |
| 26 | _extract_magnetism_intent | magnetism.py:64 (224) |
| 27 | _extract_materials_intent | materials.py:40 (100) |
| 28 | _extract_fluids_intent | fluids.py:76 (177) |
| 29 | _extract_modern_intent | modern.py:89 (99) |
| 30 | _extract_rotation_intent | rotation.py:57 (146) |
| 31 | _extract_force_intent | forces.py:93 (162) |
| 32 | _extract_energy_intent | energy.py:101 (324) |

   Value pickers: `extractors/stated_values.py:146 find_value_with_specific_unit` takes the value
   nearest a keyword, **else the first match** (`:157-179`); `:62 find_value_after_keyword`.
   **The order carries meaning:** the registry comments justify about 10 of the positions.
7. **Completion: `request.py complete_physics_intent`** (sets `asked` and `asked_unit`; `step_of`
   at `:489`):
   - **gravity:** `takes_school_g_elsewhere` refuses an Earth g that a planet word contradicts
     (`:470-477`); a Moon or Mars g replaces Earth's when no g was written (`:478-484`);
   - `orbiting_mass_fills` (`:485`).
   - **Accounting** (`accounting.py:296 competing_given`, logs at `:333` and `:357`):
     - a stated quantity of a kind the law uses, left unbound, **declines** ("left unbound by
       op=…");
     - **a quantity of a kind the law never uses is a "distractor" and is allowed** (docstring
       `:8-9`; `:333` logs the decline only in the multi-intent case).
   - `extract.py:186 _answers_another_kind`: a law whose single result kind isn't the asked kind
     is refused, and then the binder may try.
8. **The catalog binder: `binding.py bind_physics_intent` / `bind_solved_for`**, only if
   `needs_physics` (`extract.py:279`). It runs on `services/law_binding/`:
   - `fit.py` (one value per input; `:283-286` returns None when there are leftovers or two
     values for one input);
   - `words.py` (cues and excludes);
   - `inverse.py` (solve for);
   - `chain.py` (multi-law chains, **only laws with `binding`**, `:126`);
   - `domains.py`; `reduction.py`.

   `bind_solved_for` skips laws with no binding (`binding.py:247`).
   **Parts and chains:** `split_parts.py` (`_LABEL :34`, consecutive a)…h) only; all-or-nothing at
   `:206`); `chain_solve.py`; `followup.py` (`_ABOUT`, `_CHANGED`, `_HOW :59-75`, rewritten givens).
9. **The solve: `solver.py:131 solve_physics`.**
   - Dispatch by `physics_op` (`PHYSICS_SOLVERS`, `:80`); `attach_recorded_working`.
   - `_rule_its_kind_breaks` (`:97-110`): a result whose kind can't take that value (a negative
     mass or resistance) raises `ImpossibleProblemError`. **This is the only sanity check on a
     result.**
   - Then a catalog scene.
   - **The verified block (`block.py`)** refuses an intent that "answers a different quantity"
     (`:198-199`). **The direct reply (`direct.py:94 can_direct_physics`, `:311
     maybe_direct_physics_reply`)** writes the instant reply.
10. **The formal reader** (`physics/formal_read.py:69`; the server solves in
    `services/formal/solve.py`, 423 lines).
    - It is started at `chat/stream_entry.py:114` → `formal_turn.py:67 start_formal`
      **only when no solver verified the turn** (`ctx.verified_subject is None`, `:75`), and only
      when the **model's** read says physics (`:82-87`).
    - **It never checks a verified extractor answer.** The two paths are exclusive. The model only
      reads the question; the server solves.
11. **Maths, which competes: `math/tools/word_problem.py:203 word_problem_candidate`.** It takes a
    request phrase (`_MATH_REQUEST` and others) plus ≥ 2 numbers (≥ 1 in digits) plus a relation
    word. It has no unit or quantity test, so a physics story ("constant speed 40 km/hr… what is
    the distance") passes.

#### 2. Every place a value or law is filled in rather than read

The "check" column says whether anything confirms the question implied it.

| # | default | file:line | trigger | check |
|---|---|---|---|---|
| D1 | **g = 9.81** (Earth) when no g is written | `extractors/surface_gravity.py:57-69 detect_gravity`; used by kinematics.py:298, projectile.py:261/284, friction.py:210, fluids.py:137/152, fluid_laws.py:102/255, drag.py:161, circular.py:166; catalog `fallback="gravity"` ×35 (`binding_values.py:30-31`) | any law with g and no stated g | a planet word swaps the value (`:62-67`), and `takes_school_g_elsewhere` (`request.py:470`) refuses a contradiction. **Nothing asks whether the motion is under gravity at all** |
| D2 | **v0 = 0** in free fall | `kinematics.py:201` (`v0: float = 0.0`) | no velocity value found | none for "speed/velocity after t". The ask passes with only a time (`:220`, `:282-289`). A ball rolling on a floor gets v = −gt (pending g8-154) |
| D3 | **the free-fall law itself** from the cue "velocity after" / "speed after" / "acceleration of" | `kinematics.py:75-84` (`_KINEMATICS_CUES`) | a cue plus a time | `_GRAVITY_MOTION_CUES` is required only for an *acceleration* ask (`:174-180`, `:276-279`), **not for speed or velocity** |
| D4 | **op = time_to_ground** as the default ask | `kinematics.py:229` | no asked phrase matched | partly: `_answerable_without_height` (`:130-143`) |
| D5 | **reflection_angle** from the word "reflected" | `optics.py:124` | the ask names "reflected" but `_BETWEEN_RAYS_RE` (`:65-68`, which needs "between **the**") missed | none. "Between incident ray and reflected ray" gives 40° for 80° (pending g8-153) |
| D6 | **suvat_velocity (final)** for any "speed" or "velocity" | `suvat.py:102-103` (`_PHRASE_OP`) | the ask word "speed"/"velocity", even with "average" | none. Average after accelerating from rest gives 10 for 5 (pending g7-034, g7-157) |
| D7 | **magnitudes** for velocities with compass words | `suvat.py:215-` (u, v read unsigned); `motion.py:126 read_motion` reads only rest | "from 60 km/h north to 80 m/s south" | none. 3.17 for 4.83 (pending g8-156, g7-159) |
| D8 | **u = 0 / v = 0** from rest words | `suvat.py:261-266` (`read_motion`) | "from rest", "comes to a stop" | read from words. Fine |
| D9 | **water's density** (1000) | catalog `fallback="water_density"` ×5; `binding_values.py:43-46` | the question names only water | `names_only_water` |
| D10 | **water's specific heat** / calorimeter water | `binding_values.py:38-46` | "water" appears anywhere (calorimeter) | weak for calorimeter: any "water" word |
| D11 | a planet's mass and radius | `binding_values.py:32-34`; ×7 + ×5 | a body named | `central_body` |
| D12 | particle charge and mass | `binding_values.py:35-37`; ×6 + ×5 | a particle named | read from words |
| D13 | sea-level pressure | `binding_values.py:47-48` | the law needs P0 | **unconditional** |
| D14 | n = 1 for "from air" | `binding_values.py:49-50` | strikes/enters with no inside word | `light_enters_from_air` |
| D15 | **the first value of a kind** when no keyword is near | `stated_values.py:157-179` | several values of one unit | `accounting.competing_given` declines a same-kind leftover, **but only if it has a unit the law uses** |
| D16 | **an unread mantissa** | `number_text.py:153` | "1.36 × 104", "2 × 103 N" | none. 790.4 Pa for 103,360 (pending g8-155); 25.8 Pa for 500 (g7-158) |
| D17 | **a stated equivalence read as a given** | the binder plus accounting distractor rule `accounting.py:8-9` | "Note that 1 liter of water = 1 kg of water" | **the 300 L is a "kind the law never uses" (volume), so it's waved through as a distractor; the 1 kg binds as the mass.** 14.7 W for 4414 W (pending g7-069) |
| D18 | Earth g in the catalog gate | `request.py:478-484` | Moon or Mars words | read from words |
| D19 | the default part reading: the first enumerator must be "a)" | `split_parts.py:34`, `:76` | — | a decline, not a fill. Safe |

**Count:** 19 kinds of fill. **7 have no check against the question:** D2, D3, D5, D6, D7, D16, D17.
Each has a reproduced wrong verified number in the pending files. D13 is unconditional but
physically benign.

#### 3. Structural observations

- **Completeness is checked only for numbers with units** (accounting) and number words
  (spelled.py). Words that change the meaning go unchecked: "between", "average", directions, "not",
  "per", "each", and so are bare operators ("×"). That one gap explains every wrong number found.
- **The accounting rule "a quantity of a kind the law never uses is a distractor"** (`accounting.py:8`)
  turns a *wrong law choice* into an accepted solve whenever the unused given is of a different
  kind: volume beside a power law, a time beside a reflection.
- **The formal reader and the extractors never meet** (`formal_turn.py:75`). The one path that
  reads the whole question, by model, is switched off exactly when an extractor claims the turn.
- **Two subject readers, deterministic and model, unreconciled.** Solve and pictures can follow
  different subjects.
- **The gate is solver coverage.** `needs_physics` is cues plus "a law binds". The
  maths catch-all needs only a request phrase, two numbers and a relation word, so uncovered physics
  becomes maths (g8-026, g8-035, g7-023).


### Appendix B: the gate and the subject split


Review scripts (not committed): `gate_measure.py` → `gate_rows.json` (7,750 lines: battery 345,
sweep 3,582, stem_corpus + pending 3,823); `unit_gate.py` (prototype). No reader raised on any
line.

#### (b) The order, step by step (`app/services/subjects/order.py`)

`read_subject_reason` (:139) → `_ordered` (:163). First claim wins.

| step | line | reason | cue source | kind |
|---|---|---|---|---|
| 1 | :174 | `code` | `has_code_syntax` | structure |
| 2 | :180-197 | `scanned` | scanner tab caption; the photo's own words re-read by the order | structure |
| 3 | :199 | `chemistry_closed` | `is_chemistry_question` (cue words) **and** `extract_chemistry_intent` completes | words → reader |
| 4 | :201 | `physics` | **`needs_physics`** (`modules/physics/extract.py:114-175`): see below | **word list first** |
| 4a | :204 | `curve_to_math` | maths curve-point reader, when physics extracts nothing | reader |
| 5 | :213 | `physics_givens` | `is_symbol_givens_request` ("P = 200 W, t = 10 s, find W") | structure |
| 6 | :218 / :220 | `chemistry_shaped` | `_CHEMISTRY_SYMBOL`/`_CHEMISTRY_AMOUNT` regexes (:69-75), formulas, equations | structure (units and symbols) |
| 7 | :225 | `math` | `needs_symbolic_math` (`math/tools/prompt.py:120`) → … → `word_problem_candidate` (`math/tools/word_problem.py:203`, via `prompt.py:173`): **any request word + ≥ 2 numbers + a relation** | **catch-all** |
| 7a | :233 | `chart` | `chart_names_no_curve` | words |
| 8 | :240 | `chemistry_question` | `is_chemistry_question` | words |

**`needs_physics` (`extract.py:114`) checks, in order:**
1. errand regex;
2. force picture;
3. named-symbol request;
4. `_ADVANCED_PHYSICS_RE` (:58-66, words);
5. drag;
6. **digit-free only via `_DIGIT_FREE_PHYSICS_RE`**;
7. **`has_supported_physics_cue`**: **294 phrase cues + 100 regexes** merged from every extractor (`registry.py:192-251`);
8. the catalog binder;
9. two-stage, chase and legs readers;
10. `reads_in_parts`.

The gate is the cue list unioned with "some reader binds".

**Where the turn's model read (`ctx.live_read`, a `TurnDecision` with `.subject`) is used:**
- **Ignored for dispatch.** `TurnReading.subject` is built from the pooled `read_subject_reason`
  (`chat/turn_prep/reading.py:49-73`) before the live read can answer. `ctx.verified_subject`
  follows the readers. The live read is a task on the context (`turn_prep/context.py:144`).
- **Consulted downstream only:**
  - Auto's lane and effort (`decided_turn.py:253-271`);
  - the ```worked contract for a calculation "the subject readers missed" (`decided_turn.py:287-310`);
  - pictures (`decided_turn.py:152-158` `app_draws(read, verified_subject)`; `drawing_turn.py:188,195,249`);
  - `formal_answer` (physics only).
- **The result:** the model's subject can lay out or picture a turn, but never moves a line
  between maths and physics, and never stops maths' catch-all from claiming a physics question.

#### (a) Gate against readers, over every corpus

| measure | count | examples |
|---|---|---|
| gate **no**, a physics reader **completes** | **1** | g7-037 "An aircraft … 215 km/h … in 2.7 s" (subject None). The reader's verdict is never asked when the cue list misses |
| gate **yes**, `extract_physics_intent` **none** | 511 (physics 450, sweep 47, chem 10, maths 2, battery 1, pending 1) | many are answered by other paths (parts, chain, two-stage). See the next row |
| gate yes, standalone physics `answer`, **unanswered** (snapshot) | **151 of 1,468** | by file: audit_2026_11_07 45, grade8 32, grade7 21, review_2026_11_11 15, retro_probes(+counted) 17 |
| standalone physics `answer` (not `shared: math`), subject ≠ physics | **49 of 1,525** | None 42, math 7 |
| follow-up lines (history) read alone | 57 | `fu-*` "what if the mass was 4 kg": subject None alone. Expected: the thread decides (fix C) |
| maths corpus lines physics claims | 2 | wp3 "a car travels 150 km in 2.5 hours. what is its average speed" (an `answer` both can solve); pic-g37-chord "Draw a circle of radius 4 cm with a chord…" |
| chemistry lines physics claims, not `shared` | 11 | gas laws, Q = mcΔT, half-life: each `shared: physics` in spirit (owned by physics per CLAUDE.md); ca13-d04 molarity from density |
| physics `not_subject` look-alikes claimed | **0 of 115** | the cue gate is precise |
| sweep lines called physics | 107 | e.g. hs-003/hs-015 **credit-card APR payoff** and cg-016 "battery 100% → 25% in 3 hours, how long until…". They are claimed by the cue **"how long until"** (`extractors/kinematics.py:64`); money takes them at prep (`turn_prep/money.py`). The mirror of the car-loan card |

**The 49 standalone physics questions with no physics subject:**
- **maths (7):**
  - unit conversions: k09 "Convert 30 m/s to mph", kin-09, heat-05, g7-093;
  - critical misreads, all `word_problem_candidate`: pending g8-026, g8-035, g7-023.
- **none (42):**
  - multiple problems in one line: sp-01..12;
  - a lap's average velocity: q27, r5-lap-01;
  - the textbook gaps: directions ("due East"), tables, machines' MA/VR wording, Fahrenheit/Kelvin, echoes, spelled numbers, the colour code, ammeters, a fraction of c;
  - au-rv-forces-kn "3 kN and 4 kN at right angles" (kN unread).

**The critical misreads come from one mechanism.** The gate (cue list ∪ binder) misses an uncovered
physics question. Then step 7's `word_problem_candidate` claims any line with a request word and two
numbers, so maths gets it. Nothing between steps 4 and 7 asks "does this line state physical
quantities?" — the chemistry equivalent (step 6, `_chemistry_shaped`) exists for exactly this reason
(:216-217 comment).

#### (c) Design check: a gate from quantities and units (prototype, `unit_gate.py`)

**The prototype:** a number followed by one of about 130 physical units (m/s, N, J, Pa, Ω, °C, Hz,
kg/m³, …), or a quantity word (speed, force, pressure, …) within 40 characters before a number.
Lines with money words are excluded.

| group | n | unit gate | `needs_physics` | detect = physics |
|---|---|---|---|---|
| physics `answer` | 1,614 | 1,476 | 1,481 | 1,481 |
| physics `decline` | 439 | 289 | 280 | 280 |
| physics `not_subject` | 115 | **39** | 0 | 0 |
| maths subject | 1,039 | **144** | 3 | 2 |
| maths `not_subject` | 118 | 11 | 0 | 0 |
| chemistry subject | 354 | **185** | 22 | 15 |
| chemistry `not_subject` | 46 | 8 | 0 | 0 |
| sweep | 3,582 | **201** | 105 | 107 |
| battery | 345 | 13 | 6 | 6 |

- **As a replacement gate it fails.**
  - Recall on physics answers is the same (1,476 against 1,481).
  - It misses the same digit-free lines and follow-ups ("what if the mass doubled", "how long
    until 75% decays").
  - Its false positives are large:
    - 39/115 physics look-alikes ("I weigh 70 kg and want to reach 65 kg", "remind me to buy a 9V battery");
    - 144 maths geometry lines ("area of a semicircle of radius 7 cm");
    - 185 chemistry lines (molar masses, Nernst at 298 K).
- **It does catch 89 physics answers the gate misses:**
  - "Two forces of 3 kN and 4 kN at right angles";
  - "a runner does one full lap of a 400 m track in 80 s";
  - "Convert 30 m/s to mph";
  - "1 kg of ice at 0°C into water at 50°C";
  - the 3 critical misreads.
- **As a guard step it works better.** Use it like `_chemistry_shaped`, between steps 5 and 7: physics
  units, an ask, and no errand or personal words. Only where `needs_physics` said no, it newly
  claims:
  - 63 physics answers;
  - 28 physics declines (the right owner: physics' decline notes, not a maths "verified" guess);
  - 9 physics look-alikes ("my 1500 kg car was rear-ended, what do I tell insurance");
  - 3 maths look-alikes;
  - 117 maths geometry lines (cm-only lengths, which should be excluded);
  - 148 chemistry lines (already caught earlier by step 3/6 in the real order, so mostly harmless);
  - 49 sweep lines.

  Excluding pure-length units for maths' shapes and running after the chemistry steps is needed;
  the look-alike false positives then need the read.
- **Recommendation: let the turn's model read decide the subject when the readers disagree or say
  none.** It already exists, and is the owner rule ("the model reads, the server checks"). The
  turn's read (`TurnDecision.subject`) is what `decided_turn` already trusts for the lane and
  pictures. A units-shaped guard is the offline fallback that keeps a physics-shaped line from
  maths' catch-all. It is never a reason to verify: physics with no reader leaves the line to the
  model with physics' decline note, or to the formal reader. The read can't be measured offline
  today (no recorded `live_read` in the corpora), which is the same corpus gap the finalize review
  found.


### Appendix C: the formal reader


Paths are under `apps/api/app/` unless they start with `docs/`.

#### 1. What it is and when it runs today

- **What it writes.** A model writes the question down as maths, a `FormalProblem`
  (`services/formal/problem.py:28-42`):
  - `givens`: each has a symbol, a value, a unit and a `quote` (the question's own words);
    standard constants are flagged `constant`;
  - `unknowns`;
  - `equations` ("lhs = rhs" in the symbols);
  - `target` and `target_unit`;
  - the model's own `answer`;
  - `solvable`.
- **The prompt** is `modules/physics/formal_read.py:24-57`. It runs on `ROUTING.physics_setup` =
  smart-chat (`models/routing_lanes.py:130`) with 900 tokens and a 6 s timeout
  (`formal_read_timeout_seconds`, `core/settings/stem.py:88`), and makes no fallback call.
- **The server checks and solves it** (`services/formal/solve.py:217-306`, in the SymPy pool). It
  refuses a setup when:
  - a given's quote isn't in the question, or doesn't contain its number (`grounded`, :118-130).
    A wordless quote may only state zero ("from rest") or a count of 12 or less;
  - a constant isn't a standard one (`formal/constants.py`);
  - an equation isn't plain arithmetic over the declared symbols, or writes a number into
    itself other than a small factor (`_PLAIN_NUMBERS`, :41);
  - the two sides of an equation differ in units (pint);
  - there is no real or unique solution;
  - the solution fails to satisfy the equations when put back.

  It answers in `target_unit` and reports `agrees` (1% tolerance) against the model's own answer.
- **The answer is used only when `solved` and `agrees`** (`formal_read.py:114-116`).
- **When it runs:** `start_formal` (`modules/chat/formal_turn.py:67-79`), called in
  `stream_entry._attach_reads` (`stream_entry.py:114`). That call is **after**
  `prepare_chat_turn` (:240, :266), so `ctx.verified_subject` is already known. It starts only
  when **no solver answered** (`verified_subject is None`), there is no instant reply, and the
  turn's live read says physics (`_work_out`, :89-95). It runs beside the streamed reply.
- **Finalize** (`attach_formal`, :153-201) waits at most `formal_wait_seconds` = 2 s
  (`stem.py:89`):
  - same value or a rounding: the reply stands;
  - a conflict: the reply's Answer becomes the server's card, `verified: false`, with a
    provenance line in 9 languages;
  - a value the readers can't find: the server's card is appended;
  - a question in parts: skipped.

**So on main the formal reader never sees a turn a solver answered.** All 9 of tonight's
wrong numbers (`stem_corpus_pending/physics/*.json`) are solver-verified turns. The formal
reader cannot catch any of them as wired today.

#### 2. Measured (`docs/FORMAL_READER.md`, 2026-11-16; live OpenRouter runs via `tests/behavior/formal_eval.py`)

**Correct final number, by path:**

| set | n | today, Free | formal, Free | today, paid | formal, paid |
|---|---|---|---|---|---|
| English holdout | 89 | 100% | 100% | 100% | 100% |
| English reworded | 45 | 98% | 100% | 100% | 100% |
| translated (es, fr, am, ru) | 120 | 86% | 98% | 99% | 99% |
| Arabic / Hindi (40 each) | 80 | 72% / 60% | 85% / 85% | 92% / 88% | 95% / 98% |

- **Safety:** 430 setups agreed with the model's own answer, and **none was wrong**. In the
  36 disagreements with the Free reply model, the server was right **36/36**. smart-chat as the
  reply model had 0 disagreements. Arabic and Hindi: 20/20 server right.
- **Reach:** solved and agreed on 89–93% of the translated questions and 71–80% of the
  reworded. Refusal reasons: no setup, a symbol no equation determines, no real solution,
  equation units, a non-standard constant, a quote the question doesn't hold, a unit pint
  doesn't read.
- **Latency:** setup read median 0.99 s, p90 1.5 s, max 3.6 s (130 turns).
- **Cost:** $0.18 per 1,000 turns (smart-chat).

**Caveat: these numbers can't be reproduced offline.** `formal_eval.py` calls live models
(:3), and **no recorded setups are committed**. The only offline tests are:
- `tests/services/test_formal_solve.py`: 17 tests on hand-written setups;
- `test_formal_corpus.py`, which checks only that every translated id still exists.

The offline harness never exercises `formal_answer`. It has no `live_read`, and the STEM sweep
finalizes only instant replies (see the finalize review, section 4.2).

#### 3. Failure modes, from the schema

- **Arithmetic and algebra slips** are caught: the server solves, and agreement filters out a
  setup whose own answer differs. This is the measured 36/36.
- **An invented given** is caught by `grounded`: its quote must be in the question and must
  contain its number. **Gap:** the given's *unit* isn't checked against its quote. A setup could
  label "300 liter" as 300 kg and be accepted. That's harmless for water, but in general a unit
  swap passes.
- **A dropped given** isn't caught. Nothing requires every number in the question to be used.
  The model's own answer and the server's, both from the same setup, still agree.
- **A misreading of the question** isn't caught, because the agreement is self-consistency. If
  the model takes "average speed" as the final speed, its setup gives v = at = 10 and its answer
  says 10, so they agree. The design rests on the measured premise that "models rarely misread"
  and slip on arithmetic. **That premise is the inverse of the extractors'**: the regex readers
  never slip on arithmetic, and all of tonight's errors are misreadings.
- **A constant the question states** (g = 10) must be a quoted given; the prompt says a constant
  is a constant only "the question does not state" (:33-35). That's correct by construction.

#### 4. Tonight's wrong numbers under a formal setup

All are reasoned from the schema; no model was called.

| pending | extractor's error | under a formal setup |
|---|---|---|
| g8-155, g7-158 "1.36 × 104", "2 × 103 N" | mantissa dropped, 104 read as the value | **caught by grounding.** `_NUMBER` reads the quote "1.36 × 104 kg/m3" as 13600 (checked: `parse_number` gives 13600.0, and `grounded(104, …)` is False while `grounded(13600, …)` is True). A setup with 104 is refused; one with 13600 solves |
| g8-153 "angle between incident ray and reflected ray … 40°" | fell back to the angle of reflection | a setup must declare its target and the equation joining it (θ = i + r, r = i), so a model reading the words gives 80°. Not structurally enforced: a misread target would still self-agree |
| g8-156, g7-159 north→south, east→west | directions read as magnitudes | givens are unsigned quotes, but an equation may carry the sign (a = (−v − u)/t, :41 allows small factors). Depends on the model reading direction, which is the strength the eval measures |
| g7-034, g7-157 "average speed" after accelerating | final speed returned | the equation must express "average" (v_avg = (0 + a·t)/2, with u = 0 grounded by "from rest"). Model-dependent |
| g7-069 "1 liter = 1 kg" read as the mass | equivalence taken as the mass | a setup takes 300 from "300 liters" (grounded). Equivalence handled by the model; unit-vs-quote not checked |
| g8-154 "velocity after 10 s", no acceleration | free fall assumed | the prompt requires `solvable: false` when a needed value is missing. **Likely declined** |
| g8-026, g8-035, g7-023 (read as maths) | wrong subject | formal runs if the live read says physics and no solver verified, so it could answer these today. Unmeasured offline |

**Conclusion:**
- The setup's structure fixes the *mantissa* class by construction, through grounding.
- The misreading classes it fixes only to the extent the model reads correctly, which is the
  measured strength.
- On main it never runs on any of these, because they're solver-verified.

#### 5. Three architectures

| | A: today (extractors, formal as fallback) | B: formal on every physics turn; an extractor's check mark only when both agree | C: extractors only, plus a completeness rule (every number, operator, direction and asked phrase accounted for, else decline) |
|---|---|---|---|
| **correctness** | 9 known verified-wrong cases ship with a check mark; formal never sees them | two independent readers, a regex and a model; a misread by either shows as a disagreement and the check mark is withheld. Catches all 9 when the model reads them right, plausible given the 430/0 record. Grounding adds the mantissa catch | catches unread tokens ("average", "×", "south"); not a misread of tokens it did read (a fallback that reads "reflected" but not "between") unless "accounted for" is strict. Raises declines on legitimate questions |
| **latency** | instant replies are instant; formal ≤2 s only on unsolved turns | an instant reply can't carry a check mark until formal returns (median 1 s, p90 1.5 s). Either hold the instant card up to ~2 s, or show it at once and add the check mark at finalize (a re-render) | none |
| **cost** | formal on unsolved physics turns only | one smart-chat call per physics turn: +$0.18 per 1,000 turns; negligible | none |
| **offline testability** | extractors fully; formal not at all (live only, no recorded setups) | **needs recorded setups**: run `formal_eval` once with a key, commit each corpus entry's `FormalProblem` JSON, and CI runs the pure `solve_formal` and the agreement rule on them. Refresh when the prompt changes. The pieces exist (the eval, the pure solver); the fixture store doesn't | fully offline |
| **migration** | — | **small:** drop the `verified_subject is None` guard in `start_formal` (:74), add an agree-or-unmark step to the card owner (with #2501's authority), add the setup fixtures (~1 file of JSON per corpus) and a CI test. Instant-reply UX is the open design point | **large:** the rule has to understand ~60 extractors' token accounting (`physics/accounting.py` exists for numbers and units only); every miss becomes a new word list, against the owner's 2026-11-16 rule ("no wording lists") |

#### Recommendation

**Take B, with C's cheapest part as a guard. Don't make formal the only path.**

- **Run the formal setup on every physics turn**, solver-answered ones included. A solver card
  keeps its check mark only when the formal answer agrees. On a disagreement it loses the check
  mark, and finalize shows the owner's "solver disagreement first" note.
- **Two independent readers** turn every misreading class tonight into a visible disagreement,
  not a wrong check mark. Grounding fixes the mantissa class by construction.
- **Keep the extractors** as the zero-cost fast path and the offline-testable layer.
- **Add C's one structural check:** extend `accounting.py`'s "every number used" so that a
  stated number no binding reads also declines. It's word-free and catches the mantissa and
  unused-value cases even when the formal call times out.
- **Prerequisite:** commit recorded setups for the STEM corpora, so B's agreement rule is tested
  offline in CI, not only by live `formal_eval` runs.


### Appendix D: what the offline tests can't see


Paths are `apps/api/app/tests/behavior/…` unless they start with `app/`.

#### 1. Which reading decisions the STEM sweep runs: real, stubbed or never

`stem_sweep.run_entry` (stem_sweep.py:~690) runs `harness.route_case` (harness.py:391-597), then
`saved_reply` on an instant reply only.

- **Mock mode.** `route_case` runs under `battery_settings()`: `mock_llm_enabled=True`, no
  provider keys (harness.py:289-300).
- **No reads attached.** It builds the context with `build_stream_prompt_context` and
  `stream_context_from_bundle` (harness.py:510-532). It never calls `stream_entry._attach_reads`
  (`app/modules/chat/stream_entry.py:102-114`). So `ctx.live_read`, `ctx.formal`, `ctx.figure` and
  `ctx.chart` stay `None`, their defaults (`turn_prep/context.py:144`).

| decision | offline | evidence |
|---|---|---|
| the deterministic reading: plan, subject order, maths/physics intents, extractors, binder, solvers | **real** | `read_turn_message` (harness.py:417); `build_stream_prompt_context` runs turn_prep |
| the subject the sweep judges | **real, but the deterministic one** | `subject_of(text)` (harness.py:557), not the model read's `TurnDecision.subject` |
| the model read (`turn_decision.TurnDecision`: subject, effort, think, picture, follow, work, live) | **never** | started only by `stream_entry._turn_settings` (`stream_entry.py:152-164`), which the harness skips. Every read-gated branch takes its "no read" path |
| Auto's lane and thinking | **word rules only** | `model_choice.resolve_user_model` with no read (harness.py:419-426); CLAUDE.md: "word rules only without it" |
| **the formal reader** (a model writes the question as maths, the server solves it) | **never** | `start_formal` (`app/modules/chat/formal_turn.py:67-79`) runs on every physics turn with `verified_subject is None`: every `gap` and every `decline` entry. It's not attached offline, and `attach_formal` returns early with no `ctx.formal` |
| figure, chart and drawing reads | **only when pinned per case** | `Case.figure` → `patch(read_figure, AsyncMock(...))` (harness.py:646-658). Chart and live-read pictures: never |
| referent, continuation and posed picks (follow-ups) | **only when pinned per case** | `_referent_pick`, `_continuation_pick`, `_posed_pick` (harness.py:600-645). The STEM corpus pins none, so STEM follow-ups run with no model pick |
| web search, PubChem, tool rounds | stubbed | harness.py:478-508 |

#### 2. What an "answered" STEM entry proves, and what it doesn't

`answered()` (stem_sweep.py:~720) is any `answer` entry without an `unsolved` problem. `judge()`
(stem_sweep.py:~640) has two paths:

- **The server writes the reply** (`route.instant_text`). The saved reply is checked after the
  real finalize (`saved_reply`, harness.py:745): the card value, the reply's shape, its LaTeX and its
  pictures. That is real end-to-end evidence of what the student sees.
- **The model writes the reply around a verified result** (`instant_text` empty). Only the server's
  `verified_answer` is judged, as `answer\n{verified_answer}` + `verified_text`, with `whole=False`:
  any one of the answers or parts may match (stem_sweep.py:~668-678). The reply's prose and its own
  card are never produced offline, so nothing checks them. In the Grade 8 run, 4 of the 29 answered
  entries took this path (g8-053, g8-065, g8-067, g8-097).

**Never proven:**
- whether an `answer` entry with a `gap` gets a **wrong number in production**: from the model, or
  the formal reader's card;
- whether a **`decline`** entry is declined in production: the formal reader runs on exactly those
  turns, and its card is never checked offline;
- whether **`explain`** stays without a number.

The judge sees only `route.solved` and `instant` (stem_sweep.py:~650-657).

#### 3. Blind spots in the judge

Each was reproduced with `same_quantity` / `check_answer` / `card_values`.

| blind spot | where | effect | reproduction |
|---|---|---|---|
| **The sign is ignored** | `same_quantity`: `Quantity(abs(value), …)`, `target = abs(want_value)` | a wrong sign or direction passes. g8-156 and g7-159 (velocity reversals) would pass with +6 m/s² where −6 is right | `same_quantity((-6,'m/s^2'),(6,'m/s^2'))` → True; card "a = 6 m/s²" for a westward want → no problem |
| **A direction word breaks the unit** | `_pint_unit(rest)`; "m/s² west" is one unit string | a *right* "6 m/s² west" is reported **wrong** (UndefinedUnitError). A critical false positive, and why the direction cases can't be judged by direction at all | `check_answer(…, "a = 6 m/s² west")` → wrong |
| **Digit-named symbols drop values** | `card_values` split regex `,\s+(?=[a-zA-Z\\]*\s*=)` needs letters only before "=" | "I1 = 2 A, I2 = 4 A" parses to `[(4.0,'A')]`. **The first value is never judged**: "I1 = 9 A, I2 = 4 A" passes a want of 4 A | `card_values(...)` → `[(4.0,'A','4')]` |
| **Any value on the card passes** | `check_answer`: `match = next(... for want in wanted for check in matches(want))` | a card with a wrong labelled answer and an incidental right number passes | card "v = 10 m/s; v_avg = 5 m/s" for want 5 → no problem |
| **Parts are matched to no label** | each part needs some card value (`matches(part)`) | swapped part values pass ("I_1 = 2 A, I_2 = 4 A" for I1 = 4, I2 = 2) | → no problem |
| **The 1% tolerance** | `TOLERANCE = 0.01` | g = 9.8 against 9.81 (0.1%) passes; the book's g = 10 against 9.81 (1.9%) fails | 4.88 vs 4.833 → True |
| **Offset temperatures** | `_pint_unit` → `degC`; `deg F` → `degree F` | "2 K" for a °C rise is reported wrong; "104 °F" is unparseable. Both are false criticals, worked around with `answers` and `check` in the corpora | `same_quantity((104,'deg F'),(104,'degF'))` → False |
| **A unitless want with a unit on the card** | dimensionless | "4 s" against a pure-number want is wrong. Correct, but an MA or ratio card with a unit fails as a critical | — |
| **Chemistry only:** the shown significant figures widen the tolerance | `shown=` for `ROUNDED = {"chemistry"}` | "0.2" accepted for 0.204 | by design |

**Net effect.** Direction and part identity are invisible to the judge. Values in a comma list of
digit-named symbols are silently dropped. Every wrong number found tonight was a wrong *magnitude*.
A wrong-direction answer (the velocity-reversal class) would still read green if its magnitude were
right.

#### 4. Coverage by catalog operation

Measured by running every physics corpus entry (1,962) and reading the solver's op from its turn
trace (`opcov.py`, `opcov.json`).

- **Catalog:** 539 operations (`app/modules/physics/catalog`).
- **Reached at least once:** 290 operations. 291 have an answered entry (counting the generic `solve`).
- **Never reached by any corpus entry: 249 operations (46%).**
- **Reached by exactly one entry:** 97 operations.

| kind | ops | reached | answered entries |
|---|---|---|---|
| modern | 74 | 23 | 62 |
| thermal | 65 | 24 | 81 |
| circuit | 60 | 36 | 206 |
| magnetism | 40 | 12 | 44 |
| optics | 36 | 20 | 97 |
| energy | 35 | 27 | 92 |
| waves | 30 | 16 | 35 |
| fluids | 29 | 15 | 35 |
| kinematics | 24 | 22 | 175 |
| gravitation | 24 | 12 | 71 |
| spring | 22 | 19 | 64 |
| rotation | 20 | 7 | 29 |
| force | 19 | 16 | 117 |
| circular | 14 | 8 | 20 |
| momentum | 13 | 9 | 28 |
| friction | 12 | 11 | 38 |
| projectile | 7 | 6 | 50 |
| **materials** | 6 | **0** | 0 |
| suvat | 5 | 5 | 117 |
| torque | 4 | 2 | 6 |

**Never reached, examples:**
- **School-level:** `acceleration`, `angular_velocity`, `bernoulli_pressure`, `banked_speed`,
  `center_of_mass`, `combined_gas_pressure`/`volume`, `decay_constant`, `electric_potential`,
  `capacitive_reactance`, `drift_speed`.
- **The rest:** see `opcov.json` `zero`.

These ops may have unit tests under `app/tests/modules/physics`, but no corpus question reaches them
through the real reading path. So a reading change can break or mis-bind them with nothing turning
red. There's no per-extractor count: the trace records the op, not the extractor that claimed it.
That is itself a gap.

#### 5. Proposal: pinned model reads, so the corpus can exercise them offline

**Precedent already in the harness.** Model picks are pinned per case with
`patch(..., AsyncMock(return_value=pick))`:
- `Case.referent`, `Case.continues`, `Case.posed` (harness.py:600-645);
- `Case.figure`, a `FigureRequest` JSON (harness.py:646-658; used by `stem_sweep.Entry.figure`,
  stem_sweep.py `run_entry`).

Nothing records them: a case author writes them by hand. Extend the same mechanism:

1. **`Entry.read`: a recorded `TurnDecision` JSON.** The harness wraps it in a finished
   `asyncio.Task` and calls the real `_attach_reads`, so `ctx.live_read` is set and every read-gated
   branch runs (subject, effort, picture, follow, work). Judge `route.subject` against the read's
   subject as production uses it, and keep `subject_of` as the deterministic check beside it.
2. **`Entry.formal`: a recorded `read_physics_setup` result** (`app/modules/physics/formal_read.py:60`),
   patched the way `read_figure` is. The real `services/formal` solve and `attach_formal` then run in
   finalize. This is the only way to test the gap and decline entries' production path offline: does
   a decline get a formal number?
3. **`Entry.reply`: a recorded model reply for model-written turns**, run through the real
   `enrich_final_content`. That makes "answered" mean what the student reads, not just the
   `verified_answer`.
4. **A recorder script** (like `formal_eval.py`, which already calls the real models and needs a key).
   It runs the live read, the formal read and the reply once per entry, and writes them into the
   entries (or a sidecar `stem_corpus_reads/<subject>/<file>.json` keyed by id). CI replays them
   deterministically. A read that is re-recorded is a reviewed diff.
5. **The judge** compares sign and direction when the want has one: `answer: [-6, "m/s^2"]` or a
   `direction` field. It strips direction words before reading the unit, splits digit-named symbol
   lists, and binds parts to their labels.
6. **The trace** records the extractor or binder that produced the intent, beside `op`, so coverage
   can be counted per reader.


### Appendix E: the rewording hunt


#### The harness

- **Scripts:** the review's `mutate.py` and `analyze.py` (not committed; the probes in `test_reading_completeness.py` are the reproducible part).
- **Input:** every physics corpus entry the snapshot lists as answered, with no history: 1,332.
- **Mutations:** each entry gets every edit that applies, 9,929 in all. Each runs through the real
  chat path (`stem_sweep.run_entry`), as does its baseline, and as does an explicit rewording when
  one is the oracle.
- **No harness errors.** Run time is about 50 min on 4 shards.

**Oracles:**

| oracle | rule |
|---|---|
| **decline** | any verified number is wrong |
| **same** | the meaning is unchanged, so a verified number must equal the baseline's |
| **changed** | a verified number equal to the baseline's means the new words were ignored |
| **explicit** | the right answer is the server's own answer on the explicit rewording ("half of 20 m" → "10 m") |

"Irrelevant" marks an edited given that doesn't change the answer, such as a mass in a fall; it
gets no verdict.

#### Result per mutation (judged = applied minus irrelevant)

| mutation | judged | wrong or ignored | rate | verdict kind |
|---|---|---|---|---|
| half of a given ("half of 20 m") | 824 | 862 | 96%* | wrong value 836, ignored 26 |
| a product given ("2 × 20 m") | 828 | 642 | 78% | wrong value 624, ignored 18 |
| "average" before speed/velocity (accelerating motion, a duration given) | 26 | 25 | 96% | final or initial speed answered |
| compass reversal on two velocities ("… north … south") | 37 | 36 | 97% | ignored |
| "not" in the setup | 426 | 411 | 96% | still answered |
| lost superscript ("3 × 102 K", the book's form) | 234 | 118 | 50% | read as 102 K etc. |
| a needed given removed | 828 | 61 | 7% | a default filled in |
| "minimum" before the ask | 696 | 691 | 99% | ignored (weak oracle, see caveats) |
| "(1 hour = 3600 s)" | 1332 | 13 | 1% | the law or direction changes |
| "(1 liter of water = 1 kg of water)" | 28 | 1 | 4% | the mass is 1 kg |
| "It happened at 3 pm." | 1332 | 6 | 0.5% | a wrong angle or a lost asked unit |
| "Another ball of mass 3 kg rests nearby." | 1332 | 9 | 0.7% | its mass is used |
| "the" removed from the ask | 687 | 4 | 0.6% | another quantity is answered |
| question moved before the setup | 856 | 5 | 0.6% | states swapped, another part answered |
| "initial" ↔ "final" in the ask | 39 | 2 | 5% | the collision answers final for initial |

*The half-of row counts every judged-or-irrelevant row, which is why 862 exceeds 824.

**Every extractor family is hit.** The ops with the most wrong or ignored mutations:
- `time_to_ground` 134
- `suvat_distance` 118
- `suvat_velocity` 67
- `net_force` 65, `range` 65
- `speed` 49
- `suvat_initial_velocity` 46
- `image_distance` 45
- `time_of_flight` 44
- `orbital_speed_radius` 43
- `current` 42
- `suvat_acceleration` 42
- `kinetic_energy` 41
- `inductor_emf` 39
- …across about 60 ops (the full table is in `summary.txt`).

#### Clusters, by where the unread text is dropped or the default filled

| # | mechanism (file:line) | what it costs | probe(s) |
|---|---|---|---|
| U1 | **An operator on a number is never read or refused.** `fold_scientific` folds only "× 10^n" (`services/number_text.py:153`, `_SCIENTIFIC`). A mantissa and "×" before anything else are dropped, so "1.5 × 103 kg" becomes 103 kg and "2 × 5 kg" becomes 5 kg. `has_unread_quantity` (`physics/spelled.py:60-75`) refuses a number word only *beside a unit*; "half of 20 m" passes and 20 m is read | lost superscripts 118/234; half-of 836; products 624 | `test_unread_1_lost_superscript_mass` (76.3 m/s for 20), `1b` (15.7 L for 5.33), `3_half_of_a_height` (2.02 s for 1.43), `3b_a_product_given` (4 m/s² for 2) |
| U2 | **Qualifiers in the ask are unread.** `_PHRASE_OP` maps speed/velocity to `suvat_velocity` (`extractors/suvat.py:97-111`); "average", "minimum" and "initial" are never read there, nor by the kinematics or collision asks | average 25/26; initial/final 2; minimum 691 | `test_unread_2_average_speed_is_the_final_speed` (30 m/s for 20), `11_initial_velocity_of_a_collision` (1.75 for 4) |
| U3 | **Negation is unread.** No reader looks for "not" | 411/426 | `test_unread_4_thrown_not_dropped` (3.03 s; should decline) |
| U4 | **Defaults fill a missing value.** v0 = 0.0 when no speed is found (`extractors/kinematics.py:217`), even for "thrown straight down". One value alone is the whole change (`extractors/stated_change.py:102-103`), so "falls to 500 mA" fell from 0. A named part with no value (a galvanometer) is left out of the circuit | 61 removed-given cases (inductor 12, kinematics 11, circuits 9…) | `test_unread_5_thrown_down_with_no_speed` (24.3 m/s), `5b_one_current_is_the_whole_change` (10 V), `5c_a_named_part_without_a_value` (1.05 mA) |
| U5 | **A value is bound by its unit's family, not its role.** The drop height is the first length anywhere (`kinematics.py:205-214`, `require_keyword=False`), so "9.8 meters per second per second" is a 9.8 m height. The first mass is the particle's (`extractors/quantum.py:160`), so a 3 kg ball's mass goes to an electron, and a proton's radius gets a magnet's 3 kg. A clock time "at 3 pm" feeds the refraction reader (`extractors/optics_laws.py:203`) | second body 9, clock-time distractor 6, equivalence 13 | `6_g_in_words_is_a_drop_height` (1.41 s), `10_another_bodys_mass` (2.21e-40 m for 7.27e-10), `10b_a_clock_time_bends_the_ray` (90° for 19.5°) |
| U6 | **A refused reading falls through to a looser law.** When an extractor's claim is refused (here, the extra "3600 s"), the catalog binder (`extract.py:279-295`) fits any law whose inputs appear. "Starts from rest … 100 m" becomes a free fall. Also, the downward throw's direction is read by the word's position relative to the value (`extractors/kinematics_asks.py:129`) | equivalence 13, liter 1 | `7_equivalence_moves_the_law` (44.3 m/s for 8.33), `7b_equivalence_flips_a_throw` (4.93 s for 2.48) |
| U7 | **The ask is read by a word list that wants grammar.** `_HOW_LONG_IS_LENGTH` (`ask.py:260-264`) needs an article after "must"/"is", so "How long must runway be?" is a time | no-the 4 (also "reach top" → whole flight, "on small piston" → reversed press) | `8_how_long_must_runway_be` (20 s for 600 m) |
| U8 | **States are read in text order.** With the question first, "at 127 °C" is read as the start state and 27 °C as the end | question-first 5 (also parts lettered out of order) | `9_question_first_swaps_the_states` (1.5 L for 2.67) |

**Also seen, not a wrong number:** the asked unit is lost when a sentence sits between the setup
and "in hours"/"in cm"/"in MeV"/"in psi". The value is right in another unit; fix A's answer
units cover this.

#### Probes

`apps/api/app/tests/review/test_reading_completeness.py`: 17 tests, each asserting today's wrong
verified number on a student-style wording.
- `RECALL_REVIEW_PROBES=1`: 17 passed.
- Default: 17 skipped.
- ruff, format and mypy: clean.

#### Caveats

- **"minimum"** is a weak oracle: on a fixed setup the minimum can equal the value. It is reported
  but has no probe.
- **"not"** inserted mechanically is often unnatural. The natural "thrown, not dropped" reproduces
  (probe 4).
- **Products and halves** use the server's own answer on the explicit value as the oracle, so a
  wrong reading there would hide a case, never invent one.
- **The app logs a caught `PhysicsIntent` validation error** ("spring_force does not declare m",
  `services/subjects/guard.py:56`) for some mutated prompts. A reader builds an invalid intent; the
  guard catches it. Not traced further.

