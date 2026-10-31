# Model reader: a model reads the question, the server checks and solves

The external structure review (2026-10-31, finding 1) found that understanding a student's
question is thousands of hand-written English patterns, that each new phrasing is new code,
and that 8 of the app's 9 languages get almost nothing. This document is the plan to test
the review's fix **as a measured experiment**: a cheap model reads the question into a typed
request built from the subject catalogs, the server checks that request against the
message, and the same deterministic solvers answer it. Nothing a user sees changes until
the measurement below says so.

## Where reading is today

Measured on `main` (2026-10-31), production code only:

| Area | Lines | `re.compile` | Inline `re.*(r"…")` | `frozenset` word lists |
|---|---|---|---|---|
| `modules/math` | 48,032 | 518 | 104 | 94 |
| `modules/physics` | 40,349 | 458 | 90 | 413 |
| `modules/chemistry` | 23,492 | 271 | 157 | 84 |
| `modules/money` | 2,965 | 68 | 1 | 2 |
| `services/law_binding` | 1,899 | 22 | 1 | 13 |
| `modules/chat` | 34,299 | 495 | 29 | 83 |

How each subject turns a message into solver input:

- **Maths:** 41 matchers in `match/` and the extractors in `tools/extractors/` build a
  `MathIntent` (101 fields, 34 kinds). When they find nothing, `tools/llm_extract.py`
  already asks a model once (`ROUTING.math_extract`, JSON mode, 2.5 s) for a narrow typed
  extract (`LLMMathExtract`: equation, system, inequality, calculus, limit, graph) and
  maps it onto a `MathIntent`; SymPy decides whether it closes.
- **Physics:** 516 operations in `catalog/` are `FormulaSpec` records; 343 carry a
  `Binding` (the phrases that ask for the result, each input's Pint dimension and the
  input sets the solver answers from). `binding.py` reads a question into one of them
  with the shared engine in `services/law_binding/` (stated values by dimension, the words
  around them, fallbacks such as g). About 40 hand-written extractors in `extractors/`
  read the shapes the binder does not. The result is a `PhysicsIntent` (kind, op id, SI
  parameters).
- **Chemistry:** `catalog.py` lists 216 operations. 121 law records in `laws.py` (109
  operations) bind through the same engine after `binding.prepare` names each substance's
  role; the template extractors in `extractors/` read the rest (formulas, equations,
  stoichiometry). The result is a `ChemistryIntent` (kind, op, params, units, formula).
- **Money:** 8 products in `catalog.py` are data; `read.py` reads amounts, rates, terms
  and compounding into a `MoneyRequest` that `solve.py` works.

So two subjects already describe what they can solve as data with typed inputs, and maths
already trusts a model read as a *candidate* that SymPy confirms. The experiment builds on
both instead of adding a third way.

## Design

### One typed read per subject, generated from the catalogs

The model never writes free-form intents. Each subject publishes a menu generated from its
catalog, and the model fills a Pydantic schema with closed choices:

```
ReadQuestion (per subject)
  op:        one id from the menu, or "none"
  givens:    [{name: one of the op's input names, value: number, unit: SI symbol,
               quote: the exact words of the message that state it}]
  unused:    [quotes of numbers the message states that are not inputs]
  formula:   the substance a chemistry law is about (validated by the chemistry parser)
```

- **Physics** menu: every `FormulaSpec` with a `Binding`: its id, its first ask phrase, and
  each visible input's name, symbol and Pint dimension.
- **Chemistry** menu: every law in `laws.LAWS` the same way, plus the substance role it
  needs (`law.species`).
- **Maths** keeps `LLMMathExtract`; the experiment only changes *when* it runs (first, in
  every language, instead of after the patterns find nothing).
- **Money** is left for a later round: its reader changed in PRs #2154 and #2160, and the
  product inputs are few enough that the menu is one short schema.

Reading is two short calls so no prompt carries the whole catalog (the physics menu alone
is about 33,000 characters): the first picks the subject and the catalog `kind`
(19 physics kinds, chemistry's law kinds, maths, none); the second reads the op and its
givens from that kind's menu only (largest: physics `modern`, 58 operations, about 5,600
characters).

### The server checks every read before anything solves it

A read that fails any check gives no verified card; the turn goes on exactly as it does
today when the patterns find nothing.

1. **Closed choices:** the op is on the menu; every given names one of the op's inputs.
2. **Quoted, not invented:** each quote appears verbatim in the message (whitespace and
   case normalised, every Unicode digit read as its ASCII digit, so Arabic-Indic and
   Devanagari numerals count); the value is a number written in its quote (`3 × 10⁸`,
   `3e8` and `3,5` included).
3. **Every number accounted for:** each number in the message falls inside some given's or
   `unused` quote. A value the model dropped is a misread, not a smaller question.
4. **Dimensions:** the unit parses in the subject's `UnitTable` and its dimension is the
   input's (`services/law_binding/units.dimension_of`).
5. **Solvable inputs:** the given names, with the inputs the subject fills itself (g, the
   named planet's mass, water's specific heat), are one of the binding's input sets.
6. **Same answer from the deterministic reader:** phase 1 renders the checked read as one
   canonical English question ("What is the impact speed? Given: initial height 7.5 m,
   …") and reads that with today's binder, which fills fallbacks, converts units and
   builds the intent exactly as it does for an English question; the bound op and
   parameters must equal the read's. A contract test renders every bindable operation
   this way and holds which ones read back (`round trip`); an operation that does not
   read back is not model-readable yet, by name.

Phase 2, only if phase 1 measures well, builds the intent straight from the checked read
and retires the canonical sentence.

### Where it lives

`modules/turn_reading/` (the module the structure plan's ticket ST-04 names, PR #2162), below
chat and above the subjects: the two calls, the checks, and the comparison with the
pattern read. Each subject owns its menu and its read-to-intent step behind its package
exports, the first piece of the `SubjectAdapter` the review asks for (finding 6).

### Model, time and cost

- Alias: the existing `ROUTING.math_extract` lane (`gpt-6-luna`, JSON mode, "the maths read
  when the rules find none"); a dedicated `reader` lane only if the measurement picks a
  different model. Product aliases only, as everywhere.
- Time: 1.5 s per call, 3 s in all. In shadow mode the read runs beside the turn and is
  never awaited past the turn's own end.
- Cost: about 3,000 input and 200 output tokens per read, about $0.40 per 1,000 turns at
  Luna's prices; measured below.

### Failure modes and what each costs

| Failure | Effect |
|---|---|
| Timeout, provider error, invalid JSON | no read; the pattern read stands |
| Wrong op, right numbers | caught by the dimension and input-set checks, or by the binder disagreeing |
| Invented or dropped number | caught by the quote and every-number checks |
| A value read with the wrong input of the same dimension (u for v) | the hard case: the canonical sentence carries the input's own words, and both-must-agree mode (below) refuses any disagreement |
| Prompt injection in the question | the model can only choose menu ids and quote the message; nothing it writes reaches the reply |

## Measurement

`apps/api/app/tests/behavior/reader_eval.py` runs a corpus through (a) today's readers and
solvers, (b) the model read and the same solvers, (c) both, keeping a card only when the
two agree, and judges every card with the STEM sweep's own checks
(`stem_sweep.check_answer`). It reports per subject and language: reach (verified
answers), wrong verified cards (the worst failure), read latency p50/p95, and tokens and
cost per 1,000 turns.

Corpora: the STEM sweep corpus (all three subjects), the Ethiopian Ministry of Education
textbook sets used in the live rounds (read from a path; not copied into the repo), and a
translated copy (Amharic, Spanish, French, Arabic, Hindi) whose every number is checked to
survive translation.

Shadow mode (`model_reader_shadow_enabled`, off by default) records the same comparison on
live turns in the per-turn `turn_trace` line, op ids only.

### Decision rule

- **Ship both-must-agree for English** when it gives 0 wrong verified cards on every
  corpus and costs no reach: it can only remove cards, never add a wrong one.
- **Ship model-read for other languages** when its wrong-card rate on the translated
  corpus is no higher than the pattern readers' rate in English, and its reach there
  beats the patterns' (which is near zero today).
- **Retire a pattern reader** only when shadow traffic shows the model read agreeing with
  it on its own questions for two weeks, and the STEM snapshot (`stem_snapshot.json`)
  holds every answered entry.

## Not doing

- No model writes a verified answer, a formula or a number the reply shows: the solvers do.
- No pattern reader is deleted in this experiment.
- No per-phrasing rules are added to make the model read pass a test; a miss is a menu or
  check problem, fixed in the catalog or the checks for every operation at once.
