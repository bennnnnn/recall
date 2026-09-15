# Recall — Physics Tickets, Round 2 (Sep 2026)

Follow-up to [PHYSICS_TICKETS.md](./PHYSICS_TICKETS.md), whose P1–P10 shipped in
[#1324](https://github.com/bennnnnn/recall/pull/1324) and took verified physics
from four kinds to ten. One branch + PR per ticket; finish green
(`./scripts/dev.sh check`) before merging each.

Same method as round 1: every claim below was produced by driving the real
pipeline (`extract_math_intent` → `_build_verified_block` → `validate_math_fences`),
not by reading it. Two of these were **wrong answers reaching users today**, and
came first for that reason; P11 and P12 have since shipped together, since one
screenshot contained both.

| # | Ticket | Area | Status |
|---|--------|------|--------|
| P11 | [An angled collision is answered as a projectile](#p11-an-angled-collision-is-answered-as-a-projectile) | API | ✅ |
| P12 | [Never attach a verified answer to a clarifying question](#p12-never-attach-a-verified-answer-to-a-clarifying-question) | API | ✅ |
| P13 | [Constant acceleration (SUVAT)](#p13-constant-acceleration-suvat) | API | ✅ |
| P14 | [A `simulation` fence: sprites, free-body diagrams, animated orbits and collisions](#p14-a-simulation-fence-sprites-free-body-diagrams-animated-orbits-and-collisions) | Mobile + API | ✅ |
| P15 | [Pendulum period](#p15-pendulum-period) | API | ✅ |
| P16 | [Pulleys, tension and Atwood machines](#p16-pulleys-tension-and-atwood-machines) | API | ✅ |
| P17 | [Vector forces: resultants and components](#p17-vector-forces-resultants-and-components) | API | ✅ |

## Where round 1 left things

Ten verified kinds: `kinematics`, `projectile`, `force`, `energy`, `momentum`,
`friction`, `circular`, `spring`, `circuit`, `torque`.

**Only three of the ten render anything at all.** Measured by calling
`solve_physics` on one representative question per kind:

| Draws a chart | Number only |
|---|---|
| `kinematics`, `projectile`, `spring` | `force`, `energy`, `momentum`, `friction`, `circular`, `circuit`, `torque` |

P3's playback therefore reaches three kinds out of ten. P14 is where the rest of
the visual story lives.

**After P13-P17** there are eleven kinds — `suvat` joined the ten — and four of
them draw a chart, since SUVAT emits the velocity-vs-time line that P3 already
knows how to animate. Pendulum and the rope/vector ops landed as new **ops** on
the existing `spring` and `force` kinds rather than as kinds of their own, so
they did not widen that table.

**After P14** the picture is different again, because a scene is not a chart.
Ten of the eleven kinds now render, in two families — four that play and three
still figures:

| Draws | How |
|---|---|
| `kinematics`, `suvat`, `spring` | a chart |
| `projectile` | a chart *and* a played scene |
| `circular`, `momentum`, `friction` | a played scene — an orbit, a collision, a block on a slope |
| `torque`, `force`, `energy` | a still figure — a see-saw, a free body, a sum of vectors |

`circuit` is the one left, and it is left on purpose: a schematic needs battery
and resistor symbols and wires between them — a different set of primitives
from anything the scene spec has, and a renderer of its own. Not ticketed; add
one when demand shows up.

Within `energy`, potential energy and work draw and kinetic energy and power do
not, which is deliberate rather than partial: the h in mgh and the d in Fd are
quantities you can point at, and a speed is not. A block with a "3 m/s" arrow
beside it tells you nothing the sentence did.

---

## P11: An angled collision is answered as a projectile

**Problem:** Any collision question that mentions an angle is claimed by the
**projectile** extractor and answered with a range in metres. Confirmed in the
app:

> **a 2 kg ball at 3 m/s hits a 1 kg ball at rest elastically in 2D at 30 degrees**
>
> → answer pill **`0.79 m`**, plus a full "Projectile Trajectory" chart with a
> Play button.

`0.79 m` is `3² · sin(60°) / 9.81` — the range of a ball lobbed at 3 m/s. It has
nothing to do with the question.

Three of four probed phrasings land on `projectile`/`range`:

| Question | Lands on |
|---|---|
| `…hits a 1 kg ball at rest elastically in 2D at 30 degrees` | `projectile` / `range` |
| `a 2 kg ball at 3 m/s collides elastically with a 1 kg ball at 30 degrees` | `projectile` / `range` |
| `two cars collide at 20 m/s at an angle of 30 degrees, find the final velocity` | `projectile` / `range` |
| `…hits a 1 kg ball at rest and they stick together` | `momentum` / `final_velocity` ✅ |

**Cause:** P2 recognises a projectile by its *signature* — a speed and an angle
in one clause — which a 2D collision also satisfies. `_extract_projectile_intent`
sits at position 2 in `PHYSICS_EXTRACTORS`, ahead of `_extract_momentum_intent`
at position 3. P4's negative table contained no angled collision, so nothing
caught it.

**Fix:** two guards, because neither alone is right.

1. `_extract_projectile_intent` must not claim a question whose subject is a
   collision (`collide`, `collides`, `collision`, `hits … ball`, `recoil`).
2. `_extract_momentum_intent` must **refuse** a 2D or angled collision rather
   than answering with the 1D result. Only 1D conservation is solved; silently
   giving the 1D number for a 2D question is the same defect wearing a different
   hat. Same shape as P4's unstated-collision-type refusal.

**Files:** `apps/api/app/services/physics/extract.py`,
`apps/api/app/tests/services/test_physics_momentum.py`.

**Acceptance:** all four rows above resolve correctly — the first three produce
**no verified block**, the fourth still answers `2.00 m/s`. A negative test pins
each of the three against ever returning a `projectile` intent again.

**Done** in `apps/api/app/tests/services/test_physics_momentum.py` (+16 tests,
42 total). All four probed phrasings refused; the two 1D collisions and three
real projectiles unchanged; the cross-subject negative table byte-identical. One
note:

- **Three of the four angled phrasings carry a 2D *word*** — `in 2D`,
  `at an angle`, `deflected` — and a wording guard caught those three on the
  first pass. The fourth, `collides elastically with a 1 kg ball at 30 degrees`,
  carries only degrees, and it is the phrasing a person actually types; it kept
  getting the 1D answer, which is the same defect in yet another hat. Inside the
  two-mass collision branch a bare angle counts on its own: a head-on collision
  has no angle to state, so any degrees present are the deflection. The guard is
  scoped to that branch, so `p = mv` and impulse questions that merely say
  "hits" or "strikes" keep their answers.

---

## P12: Never attach a verified answer to a clarifying question

**Problem:** Separate from P11, and worse in principle. In the same screenshot
the model behaved **correctly** — it recognised the question was
under-specified and asked:

> *"Which ball's final path is at 30° — the 2 kg ball or the 1 kg ball? For a 2D
> elastic collision, that angle is needed to determine the final velocities."*

…and the pipeline attached a `0.79 m` answer pill and a trajectory chart
underneath it anyway. The model asked a question; the app answered a different
one, confidently, in the same bubble.

Reproduced directly against `validate_math_fences` with that exact reply text:

```
model asked a question, yet pipeline attached:
  answer fence: True
  graph fence : True
```

**Cause:** `_append_missing_canonical_fences`
(`apps/api/app/services/math/fence.py:614`) attaches the canonical answer and
graph whenever the reply lacks them. It has no notion of whether the reply
*answered* anything. Its guards check only for an existing fence or for prose
already stating the answer.

**Fix:** do not append canonical fences when the assistant text is a question
rather than an answer. A reply that ends in `?` and states no result is the
clear case; keep the test blunt and conservative — a false negative here only
restores today's behaviour, while a false positive silences a legitimate answer.

This generalises past P11: even with collisions fixed, the next under-specified
physics question would do the same thing.

**Files:** `apps/api/app/services/math/fence.py`,
`apps/api/app/tests/services/test_math_fence.py`.

**Acceptance:** the clarifying reply above gets **no** answer fence and **no**
graph fence; an ordinary answered reply still gets both. A test uses the real
reply text from this incident.

**Done** in `apps/api/app/tests/services/test_math_fence.py` (+6 tests, 72
total). The rule is *a verified answer exists, some line asks, and the prose
does not state it* → append nothing. Writing it changed the ticket's own
proposal twice:

- **"Ends in `?`" would have missed this very incident.** Its question is the
  **opening** line and its closing line is a plain statement, so the obvious
  rule fails on the case it was written for. Position turns out to decide
  nothing in either direction — the other natural shape, *"I need one more
  detail. Is the collision elastic?"*, asks on the **last** line. Any line that
  asks counts, and the reply is used verbatim in the test so this stays visible.
- **"States no answer" is not enough on its own** — it needs a verified answer
  to withhold. Angles alone fix a triangle's shape but not its size, so the
  solver returns a diagram, no number, and the reply asks for a side length: a
  question with no stated answer, whose diagram is exactly right. The first
  draft took it away, and the existing underdetermined-triangle tests caught it.

The reply that answers *then* asks — *"The range is about 35.31 m. Would you
like the maximum height?"* — keeps its chart, on the second half of the rule.

---

## P13: Constant acceleration (SUVAT)

**Problem:** The single largest coverage gap, and the most common school physics
topic there is. `kinematics` solves free fall **under gravity only**. Motion
under any other constant acceleration is not covered at all:

| Question | Result |
|---|---|
| `a car accelerates from rest at 3 m/s^2 for 5 s, what is its final velocity` | gap |
| `a car travelling at 20 m/s decelerates at 4 m/s^2, how far before it stops` | gap |
| `how far does a car go in 5 s accelerating from rest at 3 m/s^2` | gap |

This is arguably more valuable than anything P4–P9 added.

**Fix:** the standard five-step pattern. Ops for the SUVAT set — `v = u + at`,
`s = ut + ½at²`, `v² = u² + 2as`, `s = ½(u+v)t` — solving for whichever variable
is absent, which is the same "read the question from its givens" approach P8
used for Ohm's law and which avoids writing four sets of phrasing rules.

**Cue hazard:** `accelerates at` is already a `force` cue (added in P2), so this
extractor must run **before** `_extract_force_intent` and leave plain `F = ma`
alone — the distinction is whether a time or a distance is present. A negative
test must pin `a 5 kg mass accelerates at 2 m/s^2, what is the net force` to
`force`.

**Emits a graph:** velocity-vs-time is the natural plot and `velocity_vs_time`
already exists (P3 added it, P7 uses it), so this needs no new fence.

**Files:** shared pattern, plus `apps/api/app/tests/services/test_physics_suvat.py`.

**Acceptance:** `a car accelerates from rest at 3 m/s^2 for 5 s, what is its
final velocity` → `15.00 m/s`; all four equations verify under at least three
phrasings each; `F = ma` is untouched.

**Done** in `apps/api/app/tests/services/test_physics_suvat.py` (36 tests).
Baseline 0 of 6 probed phrasings; 6 of 6 now, all three acceptance clauses met,
cross-subject negative table byte-identical. Two notes:

- **Writing it turned up a live wrong answer of its own.** `how long to reach`
  was already a kinematics cue, so "a car accelerates from rest at 3 m/s^2, how
  long to reach 15 m/s" was claimed by free fall and answered **3.06 s** — that
  is 15/9.81, the time a ball thrown up at 15 m/s takes to stop. The stated
  3 m/s² was discarded and Earth's gravity substituted. Confirmed against the
  merged code before any of P13 was written. Ordering could not fix it (running
  SUVAT first would have had it competing with free fall for every falling
  body); kinematics declines instead, on the definition of free fall — gravity
  *is* the acceleration, so a question supplying its own is not one. A named
  gravity (`g = 1.6`, "on the moon") still is, and is compared against rather
  than special-cased.
- **The cue hazard was not where the ticket expected.** `accelerates at` being
  a force cue mattered less than predicted: what separates SUVAT from F = ma is
  not the verb but that F = ma names a mass and no time or distance, so SUVAT
  never has three of its five variables and cannot claim the question even
  though it recognises the wording.

---

## P14: A `simulation` fence: sprites, free-body diagrams, animated orbits and collisions

**Problem:** This is the ask that started the animation work — *"shows an object
being thrown with dot, car, force, gravity"* — and P3 delivered only the dot on
a graph. P3 recorded the rest as deferred precisely so it would not be
forgotten. It is now the biggest remaining piece of the visual story.

Two things are missing:

1. **Seven of ten verified kinds render nothing.** `momentum`, `friction`,
   `circular`, `circuit`, `torque`, `force` and `energy` produce a number and
   no picture. For several, the picture *is* the explanation:
   - **circular motion** — an orbiting dot is the most natural animation in the
     whole subject and currently draws nothing;
   - **collisions** — two bodies approaching, colliding and separating; a
     number cannot show a momentum transfer;
   - **inclines** — a block on a slope with weight, normal and friction arrows.
2. **The `graph` fence cannot express any of it.** It is an x-y plot. A sprite,
   a free-body diagram, or two colliding bodies need an object type, masses and
   force vectors.

**Fix:** a new `simulation` fence with its own spec and renderer, following the
fence seam in `CLAUDE.md` — a `FenceSpec` in `apps/mobile/lib/fenceRegistry.ts`,
one block component, and a Pydantic spec beside `GraphBlockSpec`.

Reuse rather than reinvent: `apps/mobile/components/rich/TrajectoryChart.tsx`
already establishes the animated-SVG pattern (`useAnimatedProps`, the
play-not-autoplay rule, the Reduce Motion fallback), and
`apps/mobile/lib/math/trajectory.ts` already provides frame-by-frame position
from a sampled path. The simulation renderer should build on both, not start
fresh.

**Scope discipline:** this is large. Suggest splitting on delivery — the spec
plus one renderer (projectile with a sprite and force arrows) first, then
circular motion, then collisions.

**Acceptance:** a projectile answer can render a moving object with gravity and
velocity arrows; a circular-motion answer animates an orbit; Reduce Motion
falls back to a static diagram; nothing autoplays.

**Done**, in two slices as the ticket suggested. The first was the spec, the
projectile renderer and the orbit — all four acceptance clauses. The second
added the two scenes the ticket named after those: **collisions** and
**inclines**. Four scene types now: `projectile_motion`, `orbit`, `collision`,
`incline`. In `apps/api/app/tests/services/test_physics_simulation.py` (48),
`apps/mobile/lib/__tests__/simulationScene.test.ts` (31) and
`apps/mobile/components/__tests__/SimulationBlock.test.tsx` (11).

Five notes from the first slice:

- **The scene and the graph share one sampled path.** A projectile emits both —
  the graph answers "what shape is the path", the scene answers "what is moving
  and what is pulling on it" — and they are the same array, so the ball can
  never be somewhere the curve is not. The renderer derives every arrow from
  that path too, rather than being handed components, so an arrow cannot
  disagree with the motion it annotates. As everywhere in this pipeline, no
  physics is repeated on the device.
- **One scale for both axes**, which is the whole reason this is not
  `mapGraphPoint`. A graph stretches each axis to fill its box; doing that here
  would turn an orbit into an ellipse and a 30° launch into some other angle —
  a picture contradicting the verified number printed beside it. The scene is
  letterboxed instead.
- **Adding a second fence silently disabled the fast path.** `can_direct_physics`
  required exactly one fence and `format_direct_math_reply` branches on
  `len(fences) == 1`, so attaching a scene made every projectile fall back to
  the provider *and* dropped the graph the fast path had always shown — with no
  error anywhere. A scene is now set aside before both checks and appended
  after, so the fast path shows all three fences.
- **The registry's contract gate did its job.** `fenceRegistry.test.ts` pins the
  fence-id set, the structured langs and the never-code-block langs, and refused
  the new entry until all three were updated deliberately. Everything else —
  dispatch, preprocess, stream preview, crash fallback — keys off the registry,
  so the entry *is* the wiring.
- **P12 already covered it.** A clarifying reply gets no scene for the same
  reason it gets no pill and no chart, and that is pinned separately: P12 was
  written when there were two kinds of extra, and a third slipping past the
  guard would put an animation under a question the model just declined.

And four from the second:

- **A collision is the case a number genuinely cannot carry.**
  `1.00 m/s and 4.00 m/s` is the right answer and says nothing about which ball
  ends up ahead, whether either turns round, or that the pair keeps moving
  together when they stick. Contact is the midpoint of the clock so both halves
  get equal screen time whatever the speeds, and radii come from the masses by
  cube root so the heavier ball reads as the heavier one. The elastic case is
  asserted through its *defining* property — the bodies separate as fast as
  they approached, so the start and end gaps are equal — which is a stronger
  check than either speed alone and catches the two final velocities being
  swapped.
- **An incline is mostly a diagram.** For two of the three friction ops the
  block never moves, so the still picture is not a fallback, it is the answer's
  illustration. That forced the one place a scene is *not* read off the path:
  normal and friction come off the stated slope instead, because a block that
  has not started moving has no tangent. `incline_deg` exists for that, and the
  spec refuses either arrow without it — a normal force pointing the wrong way
  is a more confident lie than no arrow at all.
- **"Never return a zero tangent" turned out to be wrong.** The first slice
  defaulted to pointing right when a body did not move, to stop a velocity
  arrow flipping about on a densely sampled path. Collisions made a stationary
  body a real case rather than a rounding artefact, and that default drew a
  confident velocity arrow on a ball that was sitting still. The window already
  handles the flip; zero now means zero and draws nothing, so the arrow appears
  at the moment of the collision — which is the moment it means something.
- **Three copies of the scene-type set had appeared.** The fence layer and both
  direct-reply paths each need to tell a scene from a graph, and that is exactly
  the drift `fenceRegistry.ts`'s docblock describes. They now read one
  `SIMULATION_SPEC_TYPES` derived from the `Literal` itself, with a test
  asserting the two cannot separate — a fifth scene type added to the schema and
  not to that set would be classified as a graph, since it carries `x_min` too,
  and render as an empty pair of axes.

---

## P15: Pendulum period

**Problem:** Not covered, despite being one line of physics away from code that
already ships.

```
period of a 2 m pendulum                              → gap
what is the time period of a simple pendulum of 2 m   → gap
```

`routing.py`'s `_PHYSICS_HOMEWORK_CUES` already lists `pendulum` as a topic to
escalate to the smarter model — the gap is acknowledged, just unfilled. P10
names it as explicitly unverified.

**Fix:** `T = 2π√(L/g)` — structurally identical to `shm_period`
(`T = 2π√(m/k)`) in `apps/api/app/services/physics/solver.py`, and it can emit
the same `position_vs_time` displacement curve, which P3 then animates for free.
Add to the `spring` kind rather than a new one: it is the same simple harmonic
motion with a different period formula.

**Acceptance:** `period of a 2 m pendulum` → `2.84 s`; three phrasings; emits an
animatable displacement curve.

**Done** in `apps/api/app/tests/services/test_physics_springs.py` (+11 tests, 41
total). Five phrasings, `2.84 s`, and the SHM curve builder is now shared with
`shm_period` rather than copied. One note:

- **P10's boundary rots in both directions.** P10 caught solvers the prompt had
  not been told about; the mirror is a solved topic the prompt still calls
  unchecked, and it fails quieter — the model reads "pendulum is not verified"
  while holding a verified pendulum answer, and hedges a number it was handed.
  Substring coverage cannot catch it, because after this ticket the word
  appears in *both* the verified list and the caution, so
  `test_physics_prompt_boundary.py` now reads the caution sentence on its own.

---

## P16: Pulleys, tension and Atwood machines

**Problem:** Not covered, and currently **refused on purpose**. P2 added
`tension` and `pulley` to `_UNSUPPORTED_FORCE_CONTEXT`
(`apps/api/app/services/physics/extract.py:1217`) after finding that
*"the tension supporting a 5 kg mass accelerating at 2 m/s²"* was being answered
`10.00 N` (`m·a`) when the correct answer is `T = m(g + a) = 59 N`.

The refusal is right; the gap is that it was never filled.

**Fix:** a `tension` op for a single hanging/accelerating mass
(`T = m(g ± a)`), and an Atwood pair (`a = (m₁ − m₂)g / (m₁ + m₂)`,
`T = 2m₁m₂g / (m₁ + m₂)`). Remove `tension` and `pulley` from
`_UNSUPPORTED_FORCE_CONTEXT` **only** for the shapes actually solved — per P5's
correction, the tuple guards the fall-through and entries are not deleted
wholesale when a topic lands.

**Acceptance:** `what is the tension in a rope lifting a 5 kg mass at 2 m/s^2`
→ `59.05 N`; an Atwood pair returns both acceleration and tension; a pulley
shape outside those two is still refused.

**Done** in `apps/api/app/tests/services/test_physics_tension.py` (30 tests).
All three acceptance clauses met; P2's own example now answers `59.05 N` and its
row moved out of `test_physics_phrasing.py`'s refusal table into an assertion
that says why. Two notes:

- **The refusal tuple is untouched**, per P5's correction. The new extractor
  runs ahead of force and claims only the two solved shapes; a rope at an
  angle, a rope across a table, two ropes sharing a load, and a pulley with one
  mass named all still fall through to it. Each would otherwise get a confident
  wrong number from `T = m(g ± a)` — which is the failure P2 was guarding.
- **The cue needed three conditions, not two.** "tension" beside a mass looked
  sufficient until an existing pre-filter test failed on "find the tension in a
  10 kg rope" — a rope's own mass, not a hanging load. The cue now also needs a
  word putting the rope vertical, which is the shape actually solved.

---

## P17: Vector forces: resultants and components

**Problem:** Not covered. Everything in `force` is scalar.

```
a 3 N force east and a 4 N force north, what is the resultant   → gap
resolve a 10 N force at 30 degrees into components              → gap
```

**Fix:** `resultant_force` (magnitude and bearing from two perpendicular or
angled components) and `resolve_force` (into x and y). Note `services/math/`
already has a `vector` kind for magnitude/dot/cross — check whether that
extractor should be reused before adding a physics one, and say which in the PR.

**Cue hazard:** `resolve` and `component` are generic; `resultant` is not. A
negative test must keep existing `vector` questions on the maths path.

**Acceptance:** `a 3 N force east and a 4 N force north` → `5.00 N at 53.13°`;
three phrasings per op; the existing `vector` kind is untouched.

**Done** in `apps/api/app/tests/services/test_physics_vectors.py` (25 tests).
All three acceptance clauses met. Three notes:

- **Answering the ticket's question: a physics extractor, not the maths one.**
  `services/math/`'s `vector` kind matches literal angle-bracket operands
  (`magnitude of <3, 4>`) through `is_closed_coordinate_vector_request`; a force
  question names units and compass directions instead. The two never see the
  same sentence, so neither had to give way. Asserted in the test file rather
  than only stated here.
- **One formula, not two.** The general parallelogram law drops its cosine term
  at 90°, so the perpendicular case needs no separate branch — and a test pins
  the two readings of a right angle to the same answer so they cannot drift.
- **Case-sensitivity cuts the other way here.** P8 made the circuit cues
  case-sensitive so "12 V" could be told from "12 v cards". Doing the same for
  `N` would have made this topic unreachable in the real pipeline while every
  extractor test passed, because the global pre-filter lowercases before it
  asks. N is not also an English word, and every pattern already demands
  "resultant" or "resolve"+an angle beside the reading, so these are
  case-insensitive on purpose.

---

## Still deliberately not ticketed

Unchanged from round 1, and P10 keeps the model honest about them: **pressure /
density / buoyancy**, **thermodynamics** (`Q = mcΔT`), **gravitation and
orbits**, **waves**, **optics**. All confirmed still uncovered. Add tickets when
demand shows up, not before.

> **Round 3 shipped all of these.** Circuits beyond two resistors and rotation
> beyond torque are both covered now, and the gap list below is kept as written
> for the record. See [PHYSICS_TICKETS_ROUND3.md](./PHYSICS_TICKETS_ROUND3.md).

Also out of scope, and confirmed as gaps rather than forgotten:

- **Circuits beyond two resistors** — three-resistor networks and capacitors
  (`three resistors of 2, 3 and 6 ohms in parallel` → gap).
- **Rotation beyond torque** — angular velocity, moment of inertia
  (both gaps; moment of inertia is explicitly refused by P9 rather than guessed).
- **Physics in the homework scanner** — still tracked at `FEATURES.md:898`; it
  needs the cross-subject registry that
  `docs/MATH_COVERAGE_REVIEW_2026-09-14.md` calls the remaining ceiling, and
  belongs in one ticket covering all subjects rather than a physics-only patch.
