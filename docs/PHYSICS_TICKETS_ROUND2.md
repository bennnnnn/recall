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
| P13 | [Constant acceleration (SUVAT)](#p13-constant-acceleration-suvat) | API | ☐ |
| P14 | [A `simulation` fence: sprites, free-body diagrams, animated orbits and collisions](#p14-a-simulation-fence-sprites-free-body-diagrams-animated-orbits-and-collisions) | Mobile + API | ☐ |
| P15 | [Pendulum period](#p15-pendulum-period) | API | ☐ |
| P16 | [Pulleys, tension and Atwood machines](#p16-pulleys-tension-and-atwood-machines) | API | ☐ |
| P17 | [Vector forces: resultants and components](#p17-vector-forces-resultants-and-components) | API | ☐ |

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

---

## Still deliberately not ticketed

Unchanged from round 1, and P10 keeps the model honest about them: **pressure /
density / buoyancy**, **thermodynamics** (`Q = mcΔT`), **gravitation and
orbits**, **waves**, **optics**. All confirmed still uncovered. Add tickets when
demand shows up, not before.

Also out of scope, and confirmed as gaps rather than forgotten:

- **Circuits beyond two resistors** — three-resistor networks and capacitors
  (`three resistors of 2, 3 and 6 ohms in parallel` → gap).
- **Rotation beyond torque** — angular velocity, moment of inertia
  (both gaps; moment of inertia is explicitly refused by P9 rather than guessed).
- **Physics in the homework scanner** — still tracked at `FEATURES.md:898`; it
  needs the cross-subject registry that
  `docs/MATH_COVERAGE_REVIEW_2026-09-14.md` calls the remaining ceiling, and
  belongs in one ticket covering all subjects rather than a physics-only patch.
