# Recall — Physics Review Tickets (Sep 2026)

Tickets from a full review of the physics subject: what is verified, what leaks,
and what the trajectory graph shows. One branch + PR per ticket; finish green
(`./scripts/dev.sh check`) before merging each.

Findings were produced by driving the real pipeline
(`extract_math_intent` → `_build_verified_block`), not by reading it. A topic is
recorded as uncovered only when **no** phrasing of it produced a verified answer.

| # | Ticket | Area | Status |
|---|--------|------|--------|
| P1 | [Strip verified-math markers from assistant text](#p1-strip-verified-math-markers-from-assistant-text) | API | ✅ |
| P2 | [Make the existing physics ops robust to natural phrasing](#p2-make-the-existing-physics-ops-robust-to-natural-phrasing) | API | ☐ |
| P3 | [Animate the kinematics / projectile trajectory](#p3-animate-the-kinematics--projectile-trajectory) | Mobile | ☐ |
| P4 | [Momentum, impulse and 1D collisions](#p4-momentum-impulse-and-1d-collisions) | API | ☐ |
| P5 | [Friction and inclined planes](#p5-friction-and-inclined-planes) | API | ☐ |
| P6 | [Circular motion](#p6-circular-motion) | API | ☐ |
| P7 | [Springs, Hooke's law and SHM](#p7-springs-hookes-law-and-shm) | API | ☐ |
| P8 | [Ohm's law and resistance networks](#p8-ohms-law-and-resistance-networks) | API | ☐ |
| P9 | [Torque and rotational equilibrium](#p9-torque-and-rotational-equilibrium) | API | ☐ |
| P10 | [Declare the physics boundary in the prompt](#p10-declare-the-physics-boundary-in-the-prompt) | API | ☐ |

## What is verified today

`MathIntent.physics_op` (`apps/api/app/models/schemas/math/intent.py:178`) admits
exactly twelve operations:

`position`, `velocity`, `speed`, `acceleration`, `time_to_ground`, `range`,
`max_height`, `net_force`, `kinetic_energy`, `potential_energy`, `work`, `power`

Four intent kinds map to them — `kinematics`, `projectile`, `force`, `energy` —
each registered in `PHYSICS_EXTRACTORS`
(`apps/api/app/services/physics/extract.py:705`) and `PHYSICS_BLOCK_BUILDERS`
(`apps/api/app/services/physics/block.py:57`). This matches `FEATURES.md:206`,
which already calls physics "narrow verified".

Twelve further topics produced **no verified answer under any phrasing tried**:
momentum/collisions, impulse, circular motion, friction/inclines, springs/SHM,
Ohm's law/circuits, torque/rotation, pressure/density, thermodynamics,
gravitation/orbits, waves, pendulum. P4–P9 cover the six highest-frequency of
those; the rest are deliberately deferred and listed in P10 so the model stops
answering them with unearned confidence.

## The pattern P4–P9 all follow

Each new topic is the same five edits. Written once here rather than repeated in
every ticket:

1. **Schema** — add the `physics_op` literal(s), and a new `kind` if the topic
   is not a variation of an existing one
   (`apps/api/app/models/schemas/math/intent.py`).
2. **Extractor** — a `_extract_<topic>_intent(text) -> MathIntent | None` plus a
   `_<TOPIC>_CUES` tuple in `apps/api/app/services/physics/extract.py`, added to
   `PHYSICS_EXTRACTORS` (`:705`) and folded into `PHYSICS_CUES` (`:712`). The cue
   union is the solver gate, so a topic absent from `PHYSICS_CUES` never runs.
3. **Solver** — a function in `apps/api/app/services/physics/solver.py` returning
   `PhysicsResult(answer=..., answer_value=..., graph_specs=[...])`. SymPy only;
   no SciPy (see the module docstring).
4. **Block** — a `kind → builder` entry in `PHYSICS_BLOCK_BUILDERS`
   (`apps/api/app/services/physics/block.py:57`). The existing
   `_build_physics_block` already handles answer-plus-optional-graph, so most
   topics reuse it rather than adding a builder.
5. **Tests** — `apps/api/app/tests/services/test_physics_<topic>.py`, table-driven,
   asserting the verified value *and* at least three natural phrasings (see P2).

Ordering matters: physics extractors run before the generic equation extractor
(`apps/api/app/services/math/tools/extract.py:27`), so a cue that is too broad
will steal algebra. Keep cues specific and add a negative test.

---

## P1: Strip verified-math markers from assistant text

**Problem:** `[BEGIN VERIFIED MATH]` / `[END VERIFIED MATH]`
(`apps/api/app/services/math/tools/block/common.py:12-13`) are injected into the
prompt, and nothing removes them from the reply afterwards. The only defence is
instruction — *"Never mention SymPy, verification, a system block"*
(`apps/api/app/services/chat/prompt_constants/math.py:46`) — which a model can
ignore. All eight test files referencing the marker assert it is **present in the
prompt**; none assert it is absent from what the user sees.

This class is not hypothetical: `*Couldn't verify this with SymPy.*` reached a
user under an anatomy answer, fixed in #1323.

**Fix:** Strip the markers (and any line between them that survived) from
`assistant_text` in the post-stream sanitizer chain, alongside the strippers
already there — `strip_learning_chat_fences`, `strip_sources_from_text`,
`normalize_prose_artifacts`, `sanitize_mermaid_fences`, `sanitize_places_fences`
(`apps/api/app/services/chat/stream_pipeline.py:307-365`). Strip, do not refuse:
the reply's content is still useful with the scaffolding removed.

**Files:** `apps/api/app/services/chat/stream_pipeline.py`,
`apps/api/app/services/math/tools/block/common.py` (export a stripper beside
`wrap_verified_math`), new `apps/api/app/tests/services/test_prompt_leak.py`.

**Acceptance:** A test feeds assistant text containing `[BEGIN VERIFIED MATH]`
through the post-stream path and asserts neither marker survives, and that the
surrounding prose is preserved. A second test asserts the same for the whole
marker block when a model echoes it verbatim.

**Done.** `strip_verified_math_markers` sits beside `wrap_verified_math` and runs
in the post-stream chain. Text between the markers is kept — a model that echoed
the block usually put the real answer inside it. Covered by
`app/tests/services/test_prompt_leak.py` (five leak shapes, plus round-trip and
untouched-reply cases) and one test in `test_enrich_final_content.py` that drives
the real pipeline, since a unit test would not prove the stripper is wired in.

---

## P2: Make the existing physics ops robust to natural phrasing

**Problem:** The twelve verified ops only fire on some phrasings. Confirmed in
the app:

| Asked | Result |
|---|---|
| `a 5 kg mass accelerates at 2 m/s^2, what is the net force` | ✅ verified `10.00 N` |
| `what force accelerates 5 kg at 2 m/s^2` | ❌ model prose, unverified |
| `projectile launched at 20 m/s at 30 degrees find the range` | ✅ verified `35.31 m` |
| `a ball is thrown at 20 m/s at 30 degrees, what is the range?` | ❌ miss |

Both rows in each pair are the same physics, and the failing one is the more
natural way to ask. The user sees a worse, longer, unverified answer for no
reason they can perceive — which also makes the verified/unverified distinction
look arbitrary.

**Fix:** Widen the cue tuples and extractor grammars in
`apps/api/app/services/physics/extract.py` to cover verb-first and
question-first shapes (`what force …`, `a ball is thrown …`). Do not widen
`PHYSICS_CUES` so far that it steals algebra — each addition needs a negative
test proving `solve 2x + 7 = 19` still routes to the equation extractor.

**Files:** `apps/api/app/services/physics/extract.py`,
`apps/api/app/tests/services/test_physics_extractors.py`.

**Acceptance:** A table-driven test asserts each of the twelve ops verifies under
at least three natural phrasings, including the two failing rows above. A
negative test asserts no algebra ask is claimed by a physics extractor.

---

## P3: Animate the kinematics / projectile trajectory

**Problem:** A projectile answer renders as a static curve. For a thrown-object
question the motion *is* the explanation, and the app already has everything
needed to show it — it just doesn't.

Everything required is already in place:
`react-native-reanimated@4.5.1`, `react-native-svg@15.15.4` and
`react-native-gesture-handler` are dependencies; ~12 components already animate;
`GraphCanvas.tsx:1` draws with `Svg, { Circle, G, Polygon, Polyline }`; and
`trajectory_type` already flows backend → mobile and is parsed
(`apps/mobile/lib/math/graphBlock.ts:40,173,188`). No new dependency, schema or
fence is needed.

**Fix:** Animate on `trajectory_type`, which distinguishes the two cases the
solver emits (`apps/api/app/services/physics/solver.py:213,300`):

- `position_vs_time` (kinematics) — a dot tracks the existing `points`.
- `parametric` (projectile) — a dot follows the arc, leaving a fading trail.
- Gravity (constant, down) and initial-velocity arrows drawn with the
  `Polygon`/`G` primitives `GraphCanvas` already imports.

Follow the existing `Animated.createAnimatedComponent` precedent
(`apps/mobile/components/ChatMessageImage.tsx:23`). SVG is not animated anywhere
yet, so keep this to a single animated `Circle` and establish the pattern
cleanly.

**Play/pause with replay, never autoplay-forever.** Messages render in a
FlashList and heavy rich blocks are lazy-loaded (`LazyHeavyRich`), so an
animation looping in scrollback is a battery and scroll-performance problem.
Honour reduced-motion; the static curve is the fallback and must stay correct on
its own.

`velocity_vs_time` is already accepted by the mobile parser but never emitted by
the backend — either emit it for kinematics velocity asks or drop it from the
type, rather than leaving a dead branch.

**Out of scope:** a car or object sprite, labelled free-body diagrams. Those need
a richer `simulation` fence with its own spec (object type, masses, force
vectors) and its own renderer. Recorded here as a follow-up so the decision is
deliberate, not forgotten.

**Files:** `apps/mobile/components/rich/GraphCanvas.tsx`,
`apps/mobile/components/rich/FunctionGraphBlock.tsx`,
`apps/mobile/hooks/useInteractiveGraph.ts`, `apps/mobile/lib/math/graphBlock.ts`,
tests under `apps/mobile/components/__tests__/`.

**Acceptance:** A projectile answer renders a dot that traverses the arc on play
and can be replayed; a kinematics answer animates height against time. Tests
assert the static curve still renders with animation disabled, and that no
animation starts without user interaction. `pnpm typecheck` and `pnpm test` green.

---

## P4: Momentum, impulse and 1D collisions

**Problem:** No phrasing of a momentum, impulse or collision question produces a
verified answer. `p = mv`, `J = FΔt` and 1D conservation are among the most
common mechanics homework asks after kinematics.

**Fix:** Per the shared pattern above. Ops: `momentum`, `impulse`,
`final_velocity` under a new `collision` kind. Elastic and perfectly inelastic
1D only — state the assumption in the answer rather than guessing.

**Files:** the five files in the shared pattern, plus
`apps/api/app/tests/services/test_physics_momentum.py`.

**Acceptance:** `momentum of a 2 kg object moving at 3 m/s` → `6 kg·m/s`;
a 1D inelastic collision returns the combined velocity; three phrasings each.

---

## P5: Friction and inclined planes

**Problem:** Not covered. `routing.py:170` (`_looks_like_physics_homework`)
already names incline problems as a case the solver cannot handle and routes
them to the smarter model — so the gap is known but unfilled.

**Fix:** Per the shared pattern. Ops: `friction_force`, `normal_force`,
`incline_acceleration`. Needs `mu` and an angle in `physics_params`.

**Files:** shared pattern, plus `test_physics_friction.py`.

**Acceptance:** `friction force on a 10 kg block with coefficient 0.2` → `19.6 N`;
a 30° incline with friction returns the acceleration along the slope.

---

## P6: Circular motion

**Problem:** Not covered. Centripetal force and acceleration are standard.

**Fix:** Per the shared pattern. Ops: `centripetal_force`,
`centripetal_acceleration`, `orbital_period`.

**Files:** shared pattern, plus `test_physics_circular.py`.

**Acceptance:** `centripetal force on a 2 kg mass at 4 m/s in a circle of radius 3 m`
→ `10.67 N`.

---

## P7: Springs, Hooke's law and SHM

**Problem:** Not covered.

**Fix:** Per the shared pattern. Ops: `spring_force`, `spring_energy`,
`shm_period`. SHM period is a natural fit for a `position_vs_time` trajectory
graph, which P3 will then animate.

**Files:** shared pattern, plus `test_physics_springs.py`.

**Acceptance:** `force of a spring with k = 200 N/m stretched 0.1 m` → `20 N`;
an SHM period ask emits a `position_vs_time` graph spec.

---

## P8: Ohm's law and resistance networks

**Problem:** Not covered — the first topic here that is not mechanics, so it also
proves the physics package generalises beyond motion.

**Fix:** Per the shared pattern. Ops: `voltage`, `current`, `resistance`,
`electrical_power`, plus series/parallel combination. Note `power` already exists
as a mechanical op — either reuse it with a unit-aware answer or add
`electrical_power`; do not let the two collide silently.

**Files:** shared pattern, plus `test_physics_circuits.py`.

**Acceptance:** `current if the voltage is 12 V and resistance is 4 ohms` → `3 A`;
all three rearrangements of V = IR verify; two resistors in parallel combine.

---

## P9: Torque and rotational equilibrium

**Problem:** Not covered.

**Fix:** Per the shared pattern. Ops: `torque`, `moment_balance`.

**Files:** shared pattern, plus `test_physics_torque.py`.

**Acceptance:** `torque of a 5 N force at 2 m from the pivot` → `10 N·m`;
a two-force balance solves for the unknown distance.

---

## P10: Declare the physics boundary in the prompt

**Problem:** When a topic is uncovered the model answers alone, in the same
confident voice as a verified answer, with no signal to the user that nothing
was checked. After P4–P9 the uncovered set is still real — pressure/density,
thermodynamics, gravitation/orbits, waves, optics, pendulum.

This is the counterpart to P1: P1 stops internal scaffolding leaking *out*, P10
stops unearned confidence leaking *in*.

**Fix:** Extend `MATH_SOLVER_HINT`
(`apps/api/app/services/chat/prompt_constants/math.py`) to name what physics is
verified and instruct the model to be explicit about uncertainty outside it,
using the wording already applied to limits/series/statistics: *"ONLY when a
verified math block is present … If no verified block is present, do NOT claim
verification; be cautious and say when you are unsure."* Keep it short — that
file is already long and every line costs prompt budget on every turn.

**Files:** `apps/api/app/services/chat/prompt_constants/math.py`,
`apps/api/app/tests/services/test_chat.py`.

**Acceptance:** The physics hint names the verified topics; a test asserts the
constant lists them and that it stays under a sensible length budget.

---

## Deliberately not ticketed

- **Optics, waves, thermodynamics, gravitation, pressure/buoyancy, pendulum** —
  real gaps, but lower frequency than P4–P9. P10 makes the model honest about
  them in the meantime. Add tickets when demand shows up, not before.
- **A `simulation` fence** (car/object sprites, free-body diagrams) — see P3.
- **Physics in the homework scanner** — `FEATURES.md:880` already tracks this:
  physics captions hit the math-only vision extractor and it "needs a subject
  registry". That registry is the same one `docs/MATH_COVERAGE_REVIEW_2026-09-14.md`
  calls the remaining ceiling; it belongs in one ticket covering all subjects,
  not a physics-only patch.
