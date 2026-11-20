# Review: hard multi-part questions, and output that makes a student say "how does it do that?"

2026-11-20. Read-only review of `main` at d9dd2e086. Two questions:

1. Does Recall understand the most complicated, multi-part STEM questions?
2. Is the output dynamic and stateful enough to wow a student, and is it groomed for the
   two STEM features planned next (a flash-card page with access to the chat, and a
   teacher page that tutors by voice while the key points appear on a canvas)?

Method: 46 questions sent through the real offline turn path (`tests/behavior/harness.py`
`route_case`: the reading, routing, subject solvers, instant replies and the saved reply,
on Pro, no model call), plus a code map of the backend part pipeline and the phone's
rich blocks. With no model key, the model-written replies are not seen here; what the
server verifies, says on its own, or hands the model is.

## Verdict

- **The solvers are strong; splitting a question into its parts is the gap.** Asked one
  part at a time, the solvers verified 18 of 21 parts correctly (and caught that one
  made-up system of equations has no solution). Asked as the multi-part questions they came
  from, 11 of 17 verified nothing, and five of the other six verified one part.
- **Two correctness bugs undercut the checked card**, which is Recall's strongest promise:
  a solver reply that answers one part of several ships alone with no model, and `3X^2+2x+2=7`
  is certified with `X` and `x` as two variables.
- **The output is mostly static.** A few cards are interactive (quiz, graph explorer,
  simulation play/pause, calculator sliders, molecule rotate), but worked solutions appear
  all at once, server pictures are held until the reply ends, nothing a student taps goes
  back to the chat except the clarify card, and quiz state is lost on restart.
- **Flash cards and the teacher page have almost no foundation yet**: no saved-item model,
  no persisted quiz results, live talk is audio only with markdown banned, and no canvas.

## 1. Multi-part questions: what happened

All on Pro. "Checked" means a server solver verified it before the reply.

| question (abridged) | parts | checked | what the turn did |
|---|---|---|---|
| ball off a 15 m cliff at 20 m/s, 30°: (a) time (b) distance (c) impact speed | 3 | **3** | 3.04 s; 52.7 m; 26.3 m/s, all correct, plus a server-drawn scene |
| f(x)=x³−6x²+9x+1: critical points, classify, inflection, sketch | 4 | 1 | **instant server reply, no model:** "the maximum value of f = 5", with step "⇒ x = 1" hiding x = 3; minimum, inflection and sketch dropped |
| balance C₃H₈ + O₂; grams of CO₂ from 44 g; volume at STP | 3 | 1 | **instant server reply, no model:** the balanced equation only; 132 g and the STP volume dropped |
| `3X^2+2x+2=7` | 1 | 1 (wrong) | instant reply, certified: x = 5/2 − 3X²/2 (should be x = 1 or −5/3) |
| 1) factor 6x²+x−2 2) solve 2^(x+1)=32 3) circle area r=7 | 3 | 1 | part 2 checked; 1 and 3 left to the model |
| block on 30° incline, μ=0.2: acceleration, friction, speed after 3 m | 3 | 0 | model alone (same with (a)(b)(c) labels); as three "?" questions, part 1 checked |
| 12 V, 4 Ω ∥ 6 Ω, + 2 Ω: total R, current, current in 6 Ω | 3 | 0 | model alone (labelled too) |
| quadratic, then derivative, then integral | 3 | 0 | model alone (labelled, or one per line, too) |
| 3×3 system, then its determinant | 2 | 0 | model alone |
| heat to warm and boil 500 g water; methane mass | 2 | 0 | model alone |
| limit, geometric series sum, p-series convergence | 3 | 0 | model alone |
| dy/dx = 3y, y(0)=2, then y(2) | 2 | 0 | model alone |
| kicked at 15 m/s, 40°: max height and range, show its path | 3 | 0 | model alone; without "show its path" both are checked |
| eigenvalues and eigenvectors of [[2,1],[1,2]] | 1 | 1 | correct |
| mean, median, standard deviation, histogram | 4 | 0 | no subject read |
| pipes filling and draining | 2 | 0 | read as physics, model alone |
| prove the sum of the first n odd numbers is n² | 1 | 0 | model alone (proofs are out of the solvers' scope by design) |

Each part asked alone (abridged): quadratic ✓, derivative ✓, definite integral ✓, 3×3
system ✓ ("no solution", correct: the first two equations add to 3x+2y+z = 8), determinant ✓
(0), critical points ✓, inflection ✓, incline acceleration ✓ (3.21 m/s²), resistance ✓
(4.4 Ω), limit ✓, series ✓, heat ✓ (167 440 J), range ✓ (22.6 m), mean ✓, standard
deviation ✓ (population, 12.32), factor ✓, circle area ✓, grams of CO₂ ✓; the ODE, the
pipes problem and the proof ✗. **18 of 21.**

### Why

From the code (file:line in `apps/api/app/`):

- **Parts are found by word rules, not by reading.** `turn_prep/intents.py:127` and
  `turn_prep/clauses.py` cut on "and also", new sentences, "; " and a list of task verbs
  (`clauses.py:68-73`, without "differentiate" or "integrate"); "(b) …" never counts as a
  request (it starts with "("), and ", then" is no cut. At most 5 clauses and 600
  characters, beyond which a message stays whole (`clauses.py:62-63`). Physics and
  chemistry each split again with their own grammars (`physics/split_parts.py`,
  `physics/chain_solve.py`, `chemistry/parts.py`); `docs/STRUCTURE_TICKETS.md:507` counts
  six files that split multi-part questions, each differently. Whether a question is
  checked therefore depends on its punctuation: the incline question is unchecked with
  commas or labels and gets one part checked as three "?" questions.
- **Maths verifies one answer per turn.** One `MathIntent` and one `VerifiedMathBlock`
  (`math/tools/prompt.py:289-371`); in the tool loop several SymPy calls overwrite one
  `canonical_answer` (`tool_loop/results.py:119`).
- **One failed part sinks the rest.** A physics chain or split returns nothing if any part
  fails, and the words "then", "if", "later" or "instead" in any part decline it
  (`split_parts.py:41-45`); a labelled question with a partial result is dropped whole
  (`chat/whole_question.py:212-234`); chemistry needs every question to verify
  (`chemistry/parts.py`).
- **The model-written route is physics only and adds no card.** The formal reader (the
  model writes the question down as maths, the server solves it) handles one physics setup
  with up to 8 parts, runs only when nothing else verified, and only corrects cards the
  reply already wrote (`formal_cards.py:13`). Mixed physics and chemistry is read as one
  subject, which also turns the formal reader off (`formal_turn.py:97`).
- **The whole-question guard sees labels, not asks.** `whole_question.py` drops a
  one-part result only when the parts are labelled (a)(b)(c) or are options, so an
  unlabelled list ("find …, classify …, find …, and sketch …") lets a one-part solver
  reply ship as the whole answer.
- **Case folding stops at mixed case.** `math/match/letter_case.py:49-51` leaves `X` and `x`
  as two letters when both appear, and `math/solve/parse.py:186-193` lets SymPy invent
  `Symbol('X')`.
- **The tests barely cover this.** About 65 of 3,929 STEM sweep entries have parts, nearly
  all two short labelled ones; none is a worksheet-length, chained or mixed-subject question.

## 2. Output: how dynamic and stateful it is today

From `apps/mobile` (fence registry `lib/fence/registry.ts:109-376`):

| what the student sees | today |
|---|---|
| worked solution (Given / Required / Solution / Answer) | all at once; no step reveal, nothing tappable (`components/markdown/rules/workout.tsx`) |
| answer card | static; the green check appears when the reply settles, no motion (`AnswerBlock.tsx:119-130`) |
| server pictures (graph, geometry, simulation, molecule, calculator, chem scene) | **held blank until the reply is done** (`lib/fence/held.ts`), though the server drew them before the model began |
| physics scene | autoplay, Play/Pause only; no scrub, no sliders (`SimulationBlock.tsx:278`); sliders and "solve with these values" are planned, not started (`docs/INTERACTIVE_SCENES_TICKETS.md`, IS-04) |
| graph | inline card still; pinch, pan and trace only inside the explorer modal |
| quiz / flash card | Check answer with haptics; attempt kept in memory only, lost on restart, never sent (`lib/lesson/quizAttempts.ts`) |
| tap a block to ask about it | only the clarify card sends to the chat; no "why this step?" (`ClarifyCard.tsx:73-80`) |
| motion | streaming caret, typing orb, playback; no entering or reveal animation on blocks |
| live talk | audio only, a full-screen orb; the voice prompt bans markdown (`speech/live_talk.py:48`); no canvas exists |
| saved items | none: no bookmarks, no study cards; spaced repetition was removed (`FEATURES.md:1227`) |

## 3. Recommendations, in order

Each item says which planned feature it also prepares. "Flash cards" and "teacher" are
the two pages planned for the STEM-only Recall.

### First: never show a wrong or partial answer as checked

1. **A solver reply answers every ask or is not shown alone.** The guard should hold a
   result to the question's asks, not only to its labels. The turn's read already runs a
   model on every message (`chat/decider_read.py`); have it list the asks (the model
   reads), and drop or hand to the model any instant reply that covers fewer (the server
   checks). Add the curve and propane questions above as sweep cases.
2. **`X` and `x` as one unknown** when a line uses both and nothing marks them as
   different (no "where X is …", not a physics or chemistry formula where case means
   something, such as `PV = nRT`). Never certify an answer that keeps an unknown the
   question asked to solve for.
3. **A step never hides a root:** "3x² − 12x + 9 = 0 ⇒ x = 1" must say x = 1 or x = 3.

### Then: understand the hard question (prepares the teacher page)

4. **One decomposition, read by the model, checked by the server.** Extend the formal
   reader's pattern beyond physics: one model read writes the message as a list of parts,
   each with its subject, its givens, what it asks and which earlier answers it uses. The
   server solves each part with the solvers that already exist (18 of 21 above), feeds
   earlier answers forward, and checks the list covers the message. This replaces the six
   regex splitters with one owner and removes the dependence on punctuation. The same
   part list is what a teacher page walks through point by point.
5. **One checked card per part, and partial results kept.** Give maths a parts form like
   physics' `physics_parts`; keep the parts that verified as checked and mark the rest as
   the model's, instead of dropping everything when one part fails.
6. **A multi-part corpus in the STEM sweep**, with snapshot coverage: labelled, unlabelled,
   chained ("use your answer to (a)"), mixed subject, worksheet length (8–12 parts), and
   numbered lines. Today's sweep cannot see regressions here.

### Then: output that wows (prepares both pages)

7. **Show the server's pictures and checks as they are ready, not at the end.** The
   projectile scene above existed before the model wrote a word; stream it first. Show
   each part's check arriving ("checked by the solver ✓") as the server finishes it. Making
   the double-check visible is the "how does it do that?" moment, and Recall is the only
   one with it.
8. **Worked solutions as steps the student steps through:** reveal one step at a time (or
   follow the stream), with a "why?" on each step that sends a scoped follow-up.
9. **One "ask about this" path from any block to the chat**, generalising what the clarify
   card does (`clarifyContext.tsx`). Flash cards and the teacher page both need it.
10. **Interactive scenes (IS-04):** sliders on a scene's givens and "solve with these
    values". The slider control already exists for the calculator.
11. **Small motion:** cards enter, the answer check draws itself, parts light up as
    checked. Keep it short and respect Reduce Motion.

### Groom for flash cards and the teacher page

12. **A study item model on the server:** front, back, the verified answer, and the source
    chat and message. A quiz card's attempts are saved to it instead of a memory `Map`.
    Today `Memory` and `TodoItem` are the only rows that point back to a chat message, and
    neither fits.
13. **Fences that render outside a chat bubble.** The fence registry renders inside
    messages; a board and a card page need the same blocks standalone.
14. **A board channel for live talk.** The voice model needs a tool that puts a key point,
    formula or fence on the screen (`realtimeTools.ts` has only memory lookup and web
    search), drawn by the same registry. The part list from item 4 is what it would put
    there.

## Not covered

- Model-written replies: no model key here, so whether the model covers the parts the
  server leaves it is not measured. A live run of the questions above, before and after
  items 1–6, would be the measure.
- The phone was read from code, not run.
- The three questions no solver checks alone (an ODE initial-value problem, a rates word
  problem, a proof) are coverage questions, not multi-part ones.
