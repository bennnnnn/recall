# Review: hard multi-part questions get the right answer, and the output feels alive

2026-11-20. Read-only review of `main` at d9dd2e086. Two questions:

1. Does Recall give the right, complete answer to the most complicated, multi-part STEM
   questions?
2. Is the output dynamic and stateful enough to wow a student, and is it groomed for the
   two STEM features planned next (a flash-card page with access to the chat, and a
   teacher page that tutors by voice while the key points appear on a canvas)?

Method: 46 questions sent through the real offline turn path (`tests/behavior/harness.py`
`route_case`: the reading, routing, the server's solvers, its replies and the saved reply,
on Pro), plus a code map of the backend part pipeline and the phone's rich blocks. There is
no model key here, so replies the model writes are not seen. "Solved by the server" below
means Recall worked the number out itself with its solvers (SymPy and the physics and
chemistry engines) before the reply; otherwise the model answers alone, and how often it
is right is not measured here.

## Verdict

- **Recall can already work out almost every part on its own; it fails to find the parts.**
  Asked one part at a time, the server solved 18 of 21 parts, every one correctly (and
  caught that one made-up system of equations has no solution). Asked as the multi-part
  questions they came from, it solved nothing in 11 of 17 and only one part in five more.
  Those answers are left to the model alone.
- **Three questions get a wrong or incomplete answer with no model involved**: a four-part
  calculus question answered with its first part only (and working that skips a root), a
  three-part chemistry question answered with its first part only, and `3X^2+2x+2=7`
  solved with `X` and `x` as two unknowns.
- **The output is mostly static.** Worked solutions appear all at once, the server's
  pictures stay blank until the reply ends, nothing a student taps goes back to the chat
  except the clarify card, and quiz results are lost on restart.
- **Flash cards and the teacher page have almost no foundation yet**: no saved study
  items, live talk is audio only with markdown banned, and no canvas.

## 1. Multi-part questions: what happened

All on Pro.

| question (abridged) | parts | solved by the server | what the user gets |
|---|---|---|---|
| ball off a 15 m cliff at 20 m/s, 30°: (a) time (b) distance (c) impact speed | 3 | **3** | 3.04 s; 52.7 m; 26.3 m/s, all right, plus a drawn scene of the flight |
| f(x)=x³−6x²+9x+1: critical points, classify, inflection, sketch | 4 | 1 | **wrong, sent with no model:** "the maximum value of f is 5"; the working says "3x²−12x+9 = 0 ⇒ x = 1" (x = 3 is missing), and the minimum, the inflection point and the sketch are never given |
| balance C₃H₈ + O₂; grams of CO₂ from 44 g; volume at STP | 3 | 1 | **incomplete, sent with no model:** the balanced equation only; 132 g and the STP volume are never given |
| `3X^2+2x+2=7` | 1 | 1 | **wrong, sent with no model:** x = 5/2 − 3X²/2 (right: x = 1 or x = −5/3) |
| 1) factor 6x²+x−2 2) solve 2^(x+1)=32 3) circle area r=7 | 3 | 1 | part 2 worked out; 1 and 3 left to the model |
| block on 30° incline, μ=0.2: acceleration, friction, speed after 3 m | 3 | 0 | model alone (same with (a)(b)(c) labels); written as three "?" questions, part 1 is worked out |
| 12 V, 4 Ω ∥ 6 Ω, + 2 Ω: total R, current, current in 6 Ω | 3 | 0 | model alone (labelled too) |
| quadratic, then derivative, then integral | 3 | 0 | model alone (labelled, or one per line, too) |
| 3×3 system, then its determinant | 2 | 0 | model alone (the system has no solution: will the model notice?) |
| heat to warm and boil 500 g water; methane mass | 2 | 0 | model alone |
| limit, geometric series sum, p-series convergence | 3 | 0 | model alone |
| dy/dx = 3y, y(0)=2, then y(2) | 2 | 0 | model alone |
| kicked at 15 m/s, 40°: max height and range, show its path | 3 | 0 | model alone; without "show its path" both are worked out |
| eigenvalues and eigenvectors of [[2,1],[1,2]] | 1 | 1 | right |
| mean, median, standard deviation, histogram | 4 | 0 | not read as maths |
| pipes filling and draining | 2 | 0 | read as physics, model alone |
| prove the sum of the first n odd numbers is n² | 1 | 0 | model alone (proofs are the model's by design) |

Each part asked alone, all right where solved: quadratic, derivative, definite integral,
3×3 system ("no solution": the first two equations add to 3x+2y+z = 8, the third says 10),
determinant (0), critical points, inflection point, incline acceleration (3.21 m/s²),
resistance (4.4 Ω), limit, series, heat (167 440 J), range (22.6 m), mean, standard
deviation (12.32, population), factoring, circle area, grams of CO₂. Not solved: the ODE,
the pipes problem, the proof. **18 of 21.**

### Why

From the code (file:line in `apps/api/app/`):

- **Parts are found by word rules, not by reading.** `turn_prep/intents.py:127` and
  `turn_prep/clauses.py` cut on "and also", new sentences, "; " and a list of task verbs
  (`clauses.py:68-73`, without "differentiate" or "integrate"); "(b) …" never counts as a
  request (it starts with "("), and ", then" is no cut. At most 5 clauses and 600
  characters (`clauses.py:62-63`). Physics and chemistry split again with their own
  grammars (`physics/split_parts.py`, `physics/chain_solve.py`, `chemistry/parts.py`);
  `docs/STRUCTURE_TICKETS.md:507` counts six files that split multi-part questions, each
  differently. So the answer depends on punctuation: the incline question is worked out by
  the server as three "?" questions and not at all with commas or labels.
- **Maths works out one answer per turn.** One `MathIntent` and one `VerifiedMathBlock`
  (`math/tools/prompt.py:289-371`); in the tool loop several SymPy calls overwrite one
  answer (`tool_loop/results.py:119`).
- **One part that fails throws away the parts that worked.** A physics chain or split
  returns nothing if any part fails, and "then", "if", "later" or "instead" in any part
  declines it (`split_parts.py:41-45`); a labelled question solved in part is dropped
  whole (`chat/whole_question.py:212-234`); chemistry needs every question solved
  (`chemistry/parts.py`).
- **The model-reads, server-solves route is physics only.** The formal reader handles one
  physics setup with up to 8 parts and runs only when nothing else was solved. A physics
  and chemistry question is read as one subject, which also turns it off
  (`formal_turn.py:97`).
- **The server sends a one-part answer as the whole reply.** When a solver's own reply is
  sent without the model, the only guard that it answers the whole question
  (`whole_question.py`) looks for (a)(b)(c) labels or answer options. A plain list ("find
  …, classify …, find …, and sketch …") passes, and the user gets one part.
- **Mixed case makes two unknowns.** `math/match/letter_case.py:49-51` keeps `X` and `x`
  apart when both appear, and `math/solve/parse.py:186-193` lets SymPy make `Symbol('X')`.
- **The tests barely cover this.** About 65 of 3,929 STEM sweep entries have parts, nearly
  all two short labelled ones; no worksheet-length, chained or mixed-subject question.

## 2. Output: how dynamic and stateful it is today

From `apps/mobile` (fence registry `lib/fence/registry.ts:109-376`):

| what the student sees | today |
|---|---|
| worked solution (Given / Required / Solution / Answer) | all at once; no step reveal, nothing tappable (`components/markdown/rules/workout.tsx`) |
| server pictures (graph, geometry, simulation, molecule, calculator, chem scene) | **blank until the reply is done** (`lib/fence/held.ts`), though the server drew them before the model began |
| physics scene | autoplay, Play/Pause only; no scrub, no sliders (`SimulationBlock.tsx:278`); sliders and "solve with these values" are planned, not started (`docs/INTERACTIVE_SCENES_TICKETS.md`, IS-04) |
| graph | inline card still; pinch, pan and trace only inside the explorer modal |
| quiz / flash card | Check answer with haptics; the attempt is kept in memory only, lost on restart, never sent (`lib/lesson/quizAttempts.ts`) |
| tap a block to ask about it | only the clarify card sends to the chat; no "why this step?" (`ClarifyCard.tsx:73-80`) |
| motion | streaming caret, typing orb, playback; no entering or reveal animation on blocks |
| live talk | audio only, a full-screen orb; the voice prompt bans markdown (`speech/live_talk.py:48`); no canvas exists |
| saved items | none: no bookmarks, no study cards; spaced repetition was removed (`FEATURES.md:1227`) |

## 3. Recommendations, in order

"Flash cards" and "teacher" are the two pages planned for the STEM-only Recall.

### First: stop the wrong and incomplete answers

1. **A server reply sent without the model answers everything asked, or goes to the
   model.** The turn's read already runs a model on every message (`chat/decider_read.py`);
   have it list what the message asks, and send the server's own reply alone only when it
   covers all of it. Add the calculus and propane questions above as sweep cases.
2. **`X` and `x` are one unknown** when a line uses both and nothing says otherwise (no
   "where X is …", and not a formula where case means something, such as `PV = nRT`).
3. **Working never skips a root:** "3x² − 12x + 9 = 0" gives x = 1 or x = 3.

### Then: work out every part (prepares the teacher page)

4. **One reading of the question, by the model; the solving, by the server.** Extend the
   formal reader's pattern beyond physics: one model read writes the message as a list of
   parts, each with its subject, its givens, what it asks and which earlier answers it
   uses. The server solves each part with the solvers that already exist (18 of 21 above),
   feeds earlier answers forward, and checks the list covers the message. This replaces
   the six splitters with one owner, so punctuation stops deciding the answer. The same
   part list is what a teacher page walks through point by point.
5. **Keep every part that was solved.** Give maths several parts per turn as physics
   has, and when one part fails, keep the solved parts and let the model do only the rest.
6. **A multi-part set in the STEM sweep**, with each answer checked: labelled, unlabelled,
   chained ("use your answer to (a)"), mixed subject, worksheet length (8–12 parts), and
   numbered lines. Today's sweep cannot see regressions here.
7. **Measure the model's answers live.** Run these 46 questions with a model key, before
   and after items 1–6, and count right answers per part. It is the one number this review
   could not get.

### Then: output that wows (prepares both pages)

8. **Show the server's pictures as soon as they exist.** The cliff scene above was drawn
   before the model wrote a word; put it on screen first and let the explanation stream
   under it.
9. **Worked solutions as steps the student steps through:** reveal one step at a time (or
   follow the stream), with a "why?" on each step that asks about that step.
10. **One "ask about this" path from any block to the chat**, generalising what the
    clarify card does (`clarifyContext.tsx`). Flash cards and the teacher page both need it.
11. **Interactive scenes (IS-04):** sliders on a scene's givens and "solve with these
    values". The slider control already exists for the calculator.
12. **Small motion:** cards enter, parts appear as they are solved, the graph traces
    inline. Keep it short and respect Reduce Motion.

### Groom for flash cards and the teacher page

13. **A study item on the server:** front, back, the answer, and the source chat and
    message; a quiz card's attempts saved to it instead of a memory `Map`. Today `Memory`
    and `TodoItem` are the only rows that point back to a chat message, and neither fits.
14. **Blocks that render outside a chat bubble.** The fence registry renders inside
    messages; a board and a card page need the same blocks standalone.
15. **A board for live talk.** The voice model needs a tool that puts a key point, formula
    or picture on the screen (`realtimeTools.ts` has only memory lookup and web search),
    drawn by the same registry. The part list from item 4 is what it would put there.

## Not covered

- Replies the model writes: no model key here (item 7).
- The phone was read from code, not run.
- The ODE, the rates word problem and the proof are questions the server cannot solve even
  alone; that is solver coverage, not splitting.
