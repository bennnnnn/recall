# The Grade 8 Physics book in the STEM sweep (2026-11-19)

The live round of 2026-11-18 asked 54 questions from the Ethiopian Grade 8 Physics textbook and
found the failures cluster in a few classes. Three fixes are in progress (A: one authority for the
answer; B: one gate for pictures; C: one resolver for follow-ups). To prove them, and to hold them
afterwards, the whole book is now in the offline STEM corpus:
`apps/api/app/tests/behavior/stem_corpus/physics/textbook_grade8.json`, 150 entries (it held 3).

Source: *Physics Grade 8 Student Textbook*, Ethiopian Ministry of Education,
`chilot.wordpress.com/wp-content/uploads/2023/02/01853-grade-8-physics-textbook.pdf` (176 pages,
6 units). Every numeric worked example, check point, activity and end-of-unit problem is in, in
the book's own wording: its lost superscripts ("10m/s2", "1000kg/m3", "2.7 × 102N", "27 0C",
"40o") and its line breaks. A figure the text does not describe in words is either written out
(and said so in `note`) or kept as printed and expected to be declined. Every answer was worked
independently from the book's numbers (the book's g = 10 m/s² where it states it, otherwise
9.81; CODATA e and torr), never read from the app, and its method is in `note`.

Run offline (no model, no network): `uv run python -m app.tests.behavior.stem_sweep physics --show`.

## Scorecard

| expect | entries | answered right | gap | pending-critical |
|---|---|---|---|---|
| answer | 100 (+5 pending) | 29 | 71 | 5 |
| explain | 21 | 21 left to the model | – | – |
| decline | 18 (+1 pending) | 18 never given a number | – | 1 |
| not_subject | 11 | 11 never read as physics | – | – |
| **all** | **150 (+6 pending)** | | | **6** |

Follow-ups with `history`: 11 (9 ask a number; 1 of those 9 is answered, g8-097).
No answered entry is wrong, no decline got a number, no look-alike was read as physics, and no
picture is broken. Every critical problem the sweep found is held out of CI in
`stem_corpus_pending/physics/textbook_grade8.json` (format below).

Coverage by the book's units (`answer` entries in the corpus; pending ones apart):

| unit | area | answer entries | answered | gap | pending |
|---|---|---|---|---|---|
| 1 Physics and measurement | measurement | 20 | **0** | 20 | – |
| 2 Motion in one dimension | kinematics | 14 | 5 | 9 | 3 |
| 3 Pressure | pressure (+ g8-03, filed `dynamics`) | 23 | 5 | 18 | 2 |
| 4 Heat energy | heat | 9 | 6 | 3 | – |
| 5 Electricity and magnetism | electricity / magnetism | 25 | 11 | 14 | – |
| 6 Light | optics | 9 | 2 | 7 | 1 |
| **total** | | **100** | **29** | **71** | **6** |

Unit 5's magnetism half and unit 4's heat transfer have no numbers. Their questions are
`explain` entries (transformers, commutators, convection, Ohm's law).

## Pending-critical: wrong numbers and misreads (the most valuable findings)

`stem_corpus_pending/physics/textbook_grade8.json` holds them in the corpus format, each `note`
starting with what the sweep reported. Four are verified wrong numbers. All four come from book
questions written the way a student types them, and each stays green in CI today only because
the book's own spelling is unread:

| id | question (book source) | the server's card | right | cause |
|---|---|---|---|---|
| g8-153 | "What is the angle between incident ray and reflected ray if the angle of incidence is 40°?" (Check point 6.3 Q5) | **40°** ✓verified | 80° | `_BETWEEN_RAYS_RE` (`modules/physics/extractors/optics.py:65`) wants "between **the** incident"; without "the" the fallback at `optics.py:124` takes the bare word "reflected" and answers the angle of reflection. The book's "40o" is unread, which is the only thing keeping g8-084 from this answer. |
| g8-154 | "A car starts from rest and accelerates. What is its velocity after 10 seconds?" (Check point 2.3 Q2 without its numbers; also "A ball rolls along the floor. What is its velocity after 10 seconds?") | **−98.1 m/s** ✓verified | no answer (no acceleration given) | the cue "velocity after" (`extractors/kinematics.py:75`) opens the free-fall reader with no falling word, and it fills v0 = 0, g = 9.81. The toy's v-t table (g8-027) binds the same free fall. Only the part split keeps it from the chat. |
| g8-155 | "What is the pressure at a depth of 0.76 m in mercury of density 1.36 × 104 kg/m3? Take g = 10 m/s2." (§3.5) | **790.4 Pa** ✓verified | 103,360 Pa | `fold_scientific` (`services/number_text.py:153`, `_SCIENTIFIC`) folds only "× 10^n". "1.36 ×" is dropped unread and 104 kg/m³ becomes the density. |
| g8-156 | "A car's velocity changes from 60 km/h north to 80 m/s south in 20 s. What is its acceleration?" (Review Q6) | **3.17 m/s²** ✓verified | 4.83 m/s² south | `_extract_suvat_intent` (`extractors/suvat.py:215`) reads both speeds as magnitudes and has no directions. |
| g8-026 | three legs north, stop, south: "What is the distance traveled by the car?" (§2.3, Fig 2.6) | read as **maths** | 160 km | see class 7 |
| g8-035 | "A rectangular block of mass 50 kg lies with a side 2m by 1m on a table. What is the pressure …? (g = 10 m/s2)" (Examples 3.1 Q3) | read as **maths** | 250 Pa | see class 7 |

**One root cause behind all four wrong numbers: a reader answers with words or symbols of the question
left unread.** "the", the direction words, the mantissa before "×", the missing fall: in each, the
reader takes the part it recognises and fills the rest with its law's default (the other angle,
g = 9.81 from rest, a plain magnitude). The completeness check already exists for numbers in
words beside a unit (`modules/physics/spelled.py:60`, `has_unread_quantity`, called at
`modules/physics/request.py:359`), but not for anything else that changes the meaning. **General
fix:** a verified answer must account for every number, operator ("×", "−"), direction word and
asked noun phrase in the question. Anything left over declines the turn, and never falls back to
a default law or value. This is not covered by A (A checks the reply against the server's givens,
and here the server wrote the wrong givens itself), nor by B or C. It is the most urgent class
here because it is the one that produces wrong numbers with a check mark.

## The gaps, by root cause

Each unanswered `answer` entry carries `"gap": "<one-line reason>"` naming its cause. The root
causes below were each found by reading the code and confirmed with a minimal rewording of the
book's question. Ranked by how many book questions they cost (gaps + pending):

### 1. Laws the book teaches are missing from the catalog: 17 (+ g8-153 near it)
g8-010, 012 (a displaced volume V2 − V1, and ρ = m/(V2 − V1)), 022 (three-leg Σd/Σt), 032
(a velocity reversal), 044, 050 (a barometer column ratio ρ1h1 = ρ2h2), 045, 046, 091
(pressure units: cmHg, torr, bar, millibar), 064 (resistor colour code), 072, 073 (one current
in a series loop; identical parallel branches adding), 081, 088 (angle given to the surface),
082 (images in two mirrors, 360°/θ − 1), 085 (a speed as a fraction of another), 087 (plane
mirror image distance), 092 (a ratio of specific heats).
- The gate (`modules/physics/extract.py:114`, `needs_physics`) says "physics" only when a cue or
  a catalog law fits, so most of these are not even read as physics, and the formal reader never
  sees them.
- The angle-to-surface reader names its reference only through fixed phrasings
  (`extractors/optics.py:56-75`), so "strikes the surface of a mirror at angle of 30°" leaves it
  unread. That decline is safe; the 40° above is the unsafe sibling.
- **Covered by:** none of A, B, C.
- **General fix:** add Grade 7–8 school laws as catalog rows with a `binding`, their vocabulary
  taken from their variables (the book's "input/output coil", "column of mercury", "inclined
  mirrors"), not from phrases.

### 2. Book wording the readers do not read: 15 (+ g8-155)
- **Lost superscripts and degree signs:** "10-4", "102", "1.36 104", "27 0C", "40o" (g8-014,
  015, 019, 043, 055, 084).
- **Spelled numbers and ordinals:** "one hour", "½ hr", "first hour", "one coulomb" reject the
  whole request through `has_unread_quantity` (`spelled.py:60`, `request.py:359`). Costs g8-022,
  030, 093.
- **A liquid's "height" and "pressure exerted at the base":** these miss ρgh's cues ("depth",
  "bottom"), and "exert" is in ρgh's `excludes` (`modules/physics/catalog/fluids.py:449`) because
  it is P = mg/A's cue. Costs g8-038, 039, 048.
- **A stated result away from its value:** "is known to be 2560pa then, how much is the density"
  (g8-051).
- **A value stated twice:** "labeled as 220V, 60W … connected to 220V". The second finds no open
  input in `services/law_binding/fit.py:283` (g8-071).
- **The formula restated in the question:** "vi = 0, a = g = 9.8m/s2 , v f = gt"; "we use
  p = ρgh where …" (g8-090, 043).
- **Part labels that are not "a) b) c)" from a:** "b) c)", "1. 2. 3.", "i) ii)"
  (`modules/physics/split_parts.py:34`, `_LABEL`).
- **Covered by:** none of A, B, C. A's contradictory-givens comparison is the mirror of the
  restated-value case and could share its code.
- **General fix:** one normaliser at the request boundary that rewrites a textbook's typography
  before any reader runs:
  - a power of ten after "×", or after a unit-bearing mantissa;
  - a lost degree sign;
  - number words and ordinals as digits;
  - any enumerator as a part label;
  - a restated equal value as one given.

  Laws are chosen by which inputs are stated (density + depth → ρgh), not by verbs in `excludes`.

### 3. Mensuration and scientific notation have no owner: 14
g8-004–009, 011, 013 (area and volume of a table, a plate, a box, a pool, a glass), 016–018,
020, 021, 089 (writing a number in scientific notation). They are geometry, so the entries carry
`shared: "math"`. Neither subject answers them:
- Maths' area and volume readers open only on a shape noun (`modules/math/match/dimensions.py:16`,
  `need_signals.py:52-139`: rectangle, square, circle, cuboid). "Table", "plate", "box", "pool"
  and "glass" open nothing, even with length × width given.
- Unit conversion wants a space and a spelled unit (`math/tools/school/units.py:167`), so "0.8m3"
  is unread.
- Standard form wants a bare number before "in" (`math/tools/school/number_facts.py:60`), so
  "15,000,000,000 kg in the scientific notation" is unread.
- Physics has no area law.
- **Covered by:** none of A, B, C.
- **General fix:** read area and volume from the measures and the ask ("long, wide, deep";
  "sides … each") whatever the object noun, and read every quantity as number + unit through one
  shared unit reader, so a unit or a lost superscript never breaks a maths reader.

### 4. School laws with no binding: no inverse, no chain, no several asks: 12
g8-034 (F = PA), 041 (the hydraulic large piston's area), 036, 047 (an area from two sides
feeding P = F/A), 066, 068, 077–080 (a circuit asked for R_eq, then I, then each branch or each
resistor), 074, 075 (transformer turns).
- `pressure_from_force`, `hydraulic_force` and the series/parallel circuit laws have no `binding`
  (`catalog/fluids.py:8-18, 94-113`; `catalog/circuit.py:166-190`).
- The inverse binder skips them (`modules/physics/binding.py:247`), and so does the chain
  (`services/law_binding/chain.py:126`).
- Each one is reachable only by its single-ask extractor. With a second ask the block refuses,
  and the part-by-part fallback is all-or-nothing (`split_parts.py:206`).
- `transformer_voltage` (`catalog/circuit.py:300`) solves only the secondary voltage.
- Variants confirm it: g8-077's (a)+(b) alone verify; adding (c), "the potential difference
  across each resistor", declines the whole.
- **Covered by:** none of A, B, C.
- **General fix:** every catalog law gets a binding over all its variables (a list for
  resistors), with laws for each element's share. Then inverse solves, chains and several asks
  fall out of the machinery that already exists.

### 5. Follow-ups: 8. **Covered by C.**
g8-094–096, 098–102.
- The follow-up line grammar is closed (`modules/physics/followup.py:59-75`):
  - "the mass was 2 kg" has no "what if";
  - "and b?" has no part-letter shape;
  - a material swap ("what if the liquid was mercury … 13600 kg/m3") has no shape;
  - two sentences never fullmatch.
- The rewriter refuses a change of the asked kind (`services/problem_followup.py:553`), so
  "what if the force doubles?" on a hydraulic press, where input and output are both forces,
  declines.
- The prior must be the adjacent user message and itself physics
  (`problem_followup.py:97-109`). A geometry prior (g8-094), a prior with no law (g8-099) and a
  prior read as maths (g8-102) leave nothing to replay.
- g8-097 ("and with a 5 Ω resistor?") is answered and is the control.
- C's one resolver (which earlier message a short line means, read as a change to that problem's
  givens by role) covers all eight once the prior is solvable. g8-099 and g8-102 also need
  classes 1 and 7.

### 6. Several values, moments, a table or a graph: 5
- **g8-031, solved then thrown away.** The part-by-part solve verifies all four times. Then the
  chat turn reads "a) 1 m b) 5 m c) 20 m d) 100 m" as multiple-choice options
  (`modules/chat/whole_question.py:223-235`), finds no option equal to the answer and declines
  (`whole_question.py:329`). **Covered by A** (one authority for the answer).
- **g8-037:** a list of values for one input (four depths).
- **g8-028:** one quantity at two moments. The chain holds one value per variable,
  `chain.py:60-66`.
- **g8-029:** a graph's slope and area map to no quantity.
- **g8-027:** a v-t table, bound as a free fall (see g8-154).
- **General fix:** a list of values for one input is a list of parts; a carried constant is kept
  apart from each moment; a graph's slope and area are read through its axes; a table is a set of
  givens or nothing.

### 7. The physics gate is solver coverage, so uncovered physics goes to maths: 2 critical (+ class 1's "not read as physics")
g8-026 and g8-035 (pending).
- `services/subjects/order.py:201` asks `needs_physics`: cue words plus "a catalog law binds".
- A three-leg trip or a block's weight-then-pressure has neither, so the line falls to maths'
  catch-all, `word_problem_candidate` (`modules/math/tools/word_problem.py:203`): two numbers and
  a relation word. Maths then reads "g = 10 m/s2" as an equation.
- The same mechanism leaves g8-032, 047, 085 claimed by no subject.
- **Covered by:** none of A, B, C.
- **General fix:** decide the subject from the physical quantities and units in the line (kg,
  m/s², km/hr, pressure, weight), separately from whether a solver covers it. An uncovered
  physics question then stays physics' and reaches the formal reader, never maths.

### Ranking
| rank | class | book questions lost | fix |
|---|---|---|---|
| 1 | answers with part of the question unread (wrong numbers) | 4 pending (+ g8-027, g8-084 one spelling away) | new, most urgent |
| 2 | missing school laws | 17 | new |
| 3 | book wording unread | 15 (+1 pending) | new |
| 4 | mensuration and notation without an owner | 14 | new (maths) |
| 5 | laws without a binding | 12 | new |
| 6 | follow-ups | 8 | **C** |
| 7 | several values, moments, tables, graphs | 5 | **A** for g8-031; new for the rest |
| 8 | subject gate = solver coverage | 2 pending (+3 unclaimed) | new |

## Mapping to fixes A, B and C

- **A, one authority for the answer:**
  - g8-031: a verified answer discarded by the multiple-choice gate.
  - g8-058: the card says "2 K" for a rise asked in °C. A's "answers in the question's units"
    covers it. The entry lists both spellings, since 2 K is right.
  - Card number style: 48000 J (g8-052) next to 1.68 × 10⁵ J (g8-057); A's one rounding standard
    covers it.
  - g8-156: the direction of the answer, though not the misreading of the givens.
- **B, one gate for pictures:** no gap is a picture's fault. 14 entries want a circuit or ray
  diagram that is missing only because the turn went unsolved (the sweep draws nothing for an
  unsolved turn). B's "the turn's read decides every picture path" would let the read draw the
  circuit it named even when the numbers decline.
- **C, one resolver for follow-ups:** class 5's eight entries.
- **None of the three:** classes 1–4 and 7, 64 of the 71 gaps, and all four wrong numbers.

## How the corpus was built and checked

- 150 entries in the corpus file, 6 more in the pending file:
  - 100 `answer` (incl. the 3 existing), 21 `explain`, 18 `decline` and 11 `not_subject` in the
    corpus;
  - in the pending file, 5 `answer` and 1 `decline`.
- **Declines:** a figure-only value (Example 1.7's water levels, Review Q1's graph, Fig 5.49);
  a value removed (the pen's area, the coil turns); contradictory givens (6 Ω + 6 Ω on 36 V
  "drawing 2 A"; the book's own Worked Example 5.4 Q2, whose Given lists 9 Ω and 12 Ω against a
  question of 12 Ω and 24 Ω). Also Review II.11, whose answer a lens's focal length does not
  determine. All 18 declined.
- **Look-alikes:** everyday lines with the book's words ("the pressure at work", "my bike's
  speed today", "the density of traffic in Addis", "Transformers is my favourite movie").
- **Book errors seen:**
  - Example 3.4 Q2 prints 108,933.68 Pa for 820 torr (it is 108,973.68 with the book's
    760 torr = 101,000 Pa).
  - §5.3 prints "6.25 electrons" for 6.25 × 10¹⁸.
  - Worked Example 5.4 Q2's Given contradicts its question.
  - Review II.11 equates a lens's centre of curvature with 2F.
- **Checks run:**
  - `uv run pytest app/tests/behavior/test_stem_sweep.py -q` (every STEM entry never wrong; the
    coverage snapshot), `app/tests/services/test_one_subject_owner.py` and
    `app/tests/services/test_simulation_scene_fixture.py` (they read every corpus prompt).
  - `stem_snapshot.json` was recorded with `UPDATE_STEM_SNAPSHOT=1`, and its diff holds
    additions only.

<!-- grade7 -->
