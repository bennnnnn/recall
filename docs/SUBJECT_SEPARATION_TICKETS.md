# Recall — Subject Separation Tickets: math / physics / chemistry (Phases 1, 3, 4 shipped)

Math, physics, and chemistry are meant to be three peer subjects (Golden Rule 7: "Physics is
a peer subject in `services/physics/`, not a corner of math"). Chemistry mostly lives up to
that. Physics does not yet, and the gap isn't cosmetic — it's the literal type system. Physics's
own module docstring (`services/physics/__init__.py`) says it plainly:

> "Physics — a subject domain in its own right, not a corner of math... Physics reuses math's
> shared primitives (`MathIntent`, `VerifiedMathBlock`, `MathServiceError`) and plugs into
> math's dispatch through four registry seams."

That was the actual state when this doc was written. It no longer is: physics now has its own
`PhysicsIntent` type (Phase 3), and the docstring has been updated to describe that rather than
the fusion it used to admit to. What's left is Phase 2 (turn_prep/prompt-hint parity with
chemistry), deliberately re-sequenced behind Phase 3 for reasons in its own section below. This
doc scopes the work to make the separation real. It does **not**
cover the camera/scanner subject picker (math/physics/chemistry slider) — that's deferred by
request and gets easier once S1/S5 below land, because the backend will know "this is a physics
turn" independently of math instead of inferring it from a shared enum value.

**No ticket here changes what any kind solves.** This is a structural refactor with the existing
pytest suites (61 math test files, 22 physics test files, the chemistry suite) as the regression
net — same pattern as the domain-package move in `docs/CODE_STRUCTURE_REVIEW_2026-09-13.md`,
which also touched nothing about correctness and was verified against the full suite.

## Where the three subjects actually stand today

| | Math | Physics | Chemistry |
|---|---|---|---|
| Own top-level `services/` package | yes | yes | yes |
| Own intent/schema type | `MathIntent` (`models/schemas/math/intent.py`, 29 kinds) | **fixed (S1)** — `PhysicsIntent` (`models/schemas/physics/intent.py`, 20 kinds); disjoint from `MathIntent.kind`, guarded by a test | n/a (no structured intent schema; own gate function instead) |
| Own schema package for domain-specific fence types | `models/schemas/math/` (geometry, graph, algebra, discrete) | **fixed (S7)** — `models/schemas/physics/simulation.py` (`SimulationBlockSpec` and friends), moved out of `models/schemas/math/` | n/a |
| Own turn_prep gate + context local | `needs_math` / `math_block` (`turn_prep/context.py`) | **none** — rides inside `needs_math` / `math_block`; unblocked by S1 but not yet done (Phase 2) | `needs_chem` / `chem_block` — already separate |
| Own detection gate | `needs_symbolic_math` | shares `needs_symbolic_math`; contributes cues via `has_supported_physics_cue` | `is_chemistry_question` (`services/chemistry/context.py`) — already separate |
| Prompt hint, conditionally injected only when relevant | n/a (always injected on math turns) | **none, and staying that way** (S6 descoped) — its verified-kinds paragraph is deliberately unconditional inside `MATH_SOLVER_HINT` | `CHEMISTRY_FENCE_HINT` (`prompt_constants/visuals.py`), injected only when turn_prep actually found chemistry context |
| Imports another subject's private (`_`-prefixed) internals | — | **fixed (S3)** — both helpers are now public (`extract_average_speed_intent`, `get_unit_registry`); physics calls them as intentional cross-subject API, not private reach-ins | no (checked; clean) |
| Duplicate cue list maintained outside its own package | — | kept as-is (S8) — see note below; not the bug it first looked like | no |
| Remaining imports from math, at all | — | **4, all named and allowlisted (S10)**: `MathIntent` (the average-speed union case), `GraphBlockSpec` (a genuinely shared fence type), `extract_average_speed_intent`, `get_unit_registry` | no |

Chemistry is the reference pattern. Physics needs to catch up to it, not the other way around.

## Phase 1 — stop reaching into each other's internals (no schema changes, low risk)

These don't require the type split in Phase 3 and can land first and independently.

### S2 — Give physics its own verified-block/error primitives instead of importing math's ✅ shipped

Moved `VerifiedMathBlock`, `MathServiceError`, the `[BEGIN/END VERIFIED MATH]` wrapping, and their
constructor helpers (`_finish_with_answer`, `_diagram_block`, `wrap_verified_math`,
`strip_verified_math_markers`) into a new `app.services.solving` — a subject-neutral module, not a
package, matching the existing `reminder_timing.py`-at-`services/`-root precedent for genuinely
cross-cutting code. `math/tools/block/common.py` kept only what's actually math-specific
(`format_quantity`, equation/system answer formatting). Every direct importer of the moved names
(~30 files, about half of them tests) was repointed to `app.services.solving`; math's own package
`__init__.py` files (`math/tools/block/__init__.py`, `math/solve/__init__.py`) still re-export them
for math's internal convenience — that's normal package API surface, not the split-brain alias
pattern the domain-package move retired, since these packages still do real work and aren't
pass-through shims to a deleted location. One real hazard found and fixed while doing this: a naive
`from app.services.math.solve.key_steps import KeyStep` at the top of the new module would have
forced `math/solve/__init__.py` to load before `solving.py` finished defining `MathServiceError`,
which `parse.py` (loaded by that same `__init__.py`) now imports back — a genuine import cycle.
Fixed by making it a `TYPE_CHECKING`-only import (every use was already an annotation). Verified:
full backend suite (5967 tests), ruff, mypy all clean.

### S3 — Stop physics reaching into math's underscore-prefixed internals ✅ shipped

Both helpers turned out to be heavily used *inside* math too (`math/school.py` calls its own
`_get_unit_registry`; `math/match/needs.py` and `math/tools/school.py` call
`_extract_average_speed_intent`), so they were never really private — physics reaching in with a
leading underscore was the actual bug, not the dependency itself. Renamed both to drop the
underscore (`get_unit_registry`, `extract_average_speed_intent`) and updated every call site
(math's own and physics's). "Average speed" stays a math-owned arithmetic concept that physics's
direct-reply path legitimately cross-checks against — that ownership call didn't need to change,
just its visibility.

### S4 — Move physics off `math.match` for text-scanning utilities ✅ shipped

Turned out to be two functions, not one: `word_index` (as scoped) plus `has_equation`, which
`services/physics/extract.py` was also reaching for 24 times via `from app.services.math import
match as mtm` / `mtm.has_equation(...)`. Both are genuinely pure string scanning (no SymPy, no
subject semantics — `has_equation` is six lines checking for a bare `=` with alphanumeric content
on both sides) and moved to a new `app.services.text_match`, sibling to the existing
`app.services.text_normalize` this codebase already had for exactly this kind of thing. `math/
match/scan.py` re-imports both for its own internal callers (`has_algebraic_equation` calls
`has_equation`; two other functions call `word_index`). ~14 files across math's extractor layer
had a one-line import-path change; physics/extract.py additionally dropped the `mtm` alias
entirely and calls `has_equation` bare.

### S8 — Fold `routing.py`'s duplicate physics-cue list into the physics package — descoped, see below

Turned out to be built on a false premise. `_looks_like_physics_homework` and
`has_supported_physics_cue` are **not** the same gate wearing two costumes: one asks "should Auto
escalate to the smarter model because the solver won't help," the other asks "might the solver's
extractors handle this text at all." Delegating the first to the second would invert the
intent — it would stop escalating exactly the physics questions the solver now covers (momentum,
simple harmonic, centripetal all shipped in round 3) and only escalate the ones it doesn't, which
is backwards, and it's a live-routing behavior change I have no way to validate is wanted from
here. Did the safe version instead: left the routing logic untouched and added a comment on
`_PHYSICS_HOMEWORK_CUES` explaining the two lists are deliberately separate and why the overlap
with now-covered kinds is likely intentional (a smarter model's prose is still worth it even when
the number is guaranteed), so a future reader doesn't mistake this for the Round 3 casing bug and
"fix" it into actually-backwards behavior. No code behavior changed.

### S9 — Audit chemistry ✅ confirmed clean

Chemistry already has its own gate, its own turn_prep locals, and a conditionally-injected prompt
hint. A grep across `apps/api/app` for `chemistry` outside its own package turned up only the
turn_prep integration points every subject needs, test files, and one legitimate disambiguation
touch in `services/images/gen_intent.py` / `lookup_intent.py` (so "draw a benzene ring" routes to
chemistry, not image generation). No private-internal reach-ins found. No refactor needed.

## Phase 2 — turn-prep parity with chemistry — re-sequenced behind Phase 3, see below

### S5 — Give physics its own `needs_physics` / `physics_block` in turn_prep — unblocked, not yet done

Traced `turn_prep/context.py` in full before touching it. Chemistry's `needs_chem`/`chem_block`
aren't `StreamContext` fields — they're locals scoped to `build_stream_prompt_context`, used only
to decide what to inject into *this* turn's prompt messages. Physics has no equivalent because
physics detection is fused inside `needs_symbolic_math` at the top of that function (one shared
boolean, no way to ask "was the match physics specifically" without inspecting the result), and
the eventual `verified_math`/`math_block` come out of one shared fetch (`fetch_web_and_tools` →
`_build_verified_block`) that dispatches to physics or math builders by `intent.kind` — there's no
separate physics fetch to hang a `physics_block` local off. The dispatch result *does* already
carry the answer, though: `VerifiedMathBlock.physics_intent` is set exactly when the solve was
physics. A `needs_physics`/`physics_block` pair computed from that field post-fetch would be real
and truthful, but nothing today would read it — adding it now is exactly the "abstraction beyond
what the task requires" this codebase's own conventions warn against. S1 has since shipped, so the
type distinction now exists (`isinstance(verified_math.physics_intent, PhysicsIntent)` is real and
checkable) — the blocker named here is gone. Still not done in this pass: nothing yet *consumes*
`needs_physics`/`physics_block`, and adding the fields with no reader would still be the same
premature abstraction, just no longer excused by a missing type. Do this when something
(analytics, a future `SubjectSpec` registry, a physics-specific prompt addition once S6 is
revisited) actually needs to ask "was this turn's verified answer physics."

### S6 — Split `MATH_SOLVER_HINT` into independent per-subject prompt hints — descoped, see below

Do not do this as scoped. `test_physics_prompt_boundary.py` deliberately pins the physics
verified-kinds paragraph inside `MATH_SOLVER_HINT` so it ships on *every* math turn regardless of
whether the pre-check recognized the phrasing as physics — that's what lets the model say "not
checked, be cautious" about relativity/entropy/AC-circuits even on a turn the extractor itself
misreads. FEATURES.md documents this as a deliberate safety property ("a test ties that list to
the solver registry so it cannot drift"), not an accident of where the string happens to live.
Making the hint conditional on a `needs_physics` pre-check would mean the caution reminder goes
missing on exactly the turns where detection is already uncertain — trading a real, tested safety
property for a token-count optimization nobody asked for. The token-bloat concern in the original
wording of this ticket doesn't hold up against that trade. Re-evaluate only if S1 lands and
`needs_physics` becomes a true post-dispatch signal rather than a fallible pre-check — even then,
the hint would need to move to a *post-hoc* injection (after a physics solve, add extra detail)
rather than gating the existing boundary-caution paragraph, which should stay universal.

## Phase 3 — the real type split (done first, since Phase 2 depended on it)

### S1 — Split `MathIntent` into subject-specific intent types ✅ shipped

Audited physics's actual field usage before scoping the split (every `MathIntent(...)` /
`.model_validate(...)` construction site in `services/physics/*.py`, plus every non-`physics_*`
attribute access): of `MathIntent`'s fields, physics touched exactly `kind` (20 of its 49 values),
`operation` (always `"solve"`), `physics_op`, `physics_params`, `physics_units` — a clean, narrow
footprint, not the sprawling shared-schema problem it could have been. Shipped `PhysicsIntent`
with exactly those fields in a new `models/schemas/physics/` package; narrowed `MathIntent.kind`
to the remaining 29 values and removed the three `physics_*` fields from it entirely.

The two types flow through the **same** generic dispatch as a real union
(`MathIntent | PhysicsIntent`) rather than through any conversion — `_INTENT_EXTRACTORS`,
`extract_math_intent`, `_build_verified_block`, and `VerifiedMathBlock.physics_intent` all widened
to accept/return the union, and dict-keyed dispatch by `.kind` doesn't care which concrete type it
receives. One real design wrinkle: `Callable` parameters are contravariant, so a registry
(`_BLOCK_BUILDERS` / `SCHOOL_BLOCK_BUILDERS` / `PHYSICS_BLOCK_BUILDERS`) typed to the union would
have forced every math-only builder to also declare it accepts a `PhysicsIntent` it never
receives — each registry's Callable value type is `Any`-parameterized instead (`_BlockBuilder` in
`block/__init__.py`, mirrored in `school.py` and `physics/block.py`), while every individual
builder function keeps its own precise, narrow parameter type at its actual definition. Return
types don't have this problem (covariant), so `_INTENT_EXTRACTORS`'s sequence type widened cleanly
with no changes needed to individual extractors' return annotations.

One genuine union case survives on purpose: average speed is a math kind (`arithmetic`) that
physics's direct-reply path (`physics/direct.py`) cross-checks its own extraction against, so
`_expected_intent` returns `MathIntent | PhysicsIntent | None` and `can_direct_physics` narrows
with `isinstance(expected, PhysicsIntent)` before touching physics-only fields.

Touched ~60 construction sites in `extract.py`, all of `solver.py`/`direct.py`/`block.py`, the
dispatch seam in `math/tools/block/__init__.py`, one generic call site in
`math/tools/extract.py` (line ~142, which read `.school_op` on whatever the first matching
extractor returned — fixed with an `isinstance(intent, PhysicsIntent)` early return, since none of
the checks after it ever applied to a physics kind anyway), and ~20 test files that constructed a
physics-kind intent directly or narrowed the union to reach a subject-specific field. One test
(`test_solve_physics_unknown_kind_raises`) had relied on constructing an *invalid*-kind
`MathIntent` to exercise `solve_physics`'s own defensive dispatch-miss branch — no longer
constructible through the normal API now that `PhysicsIntent.kind` is a closed Literal, so it uses
`PhysicsIntent.model_construct(...)` (Pydantic's validation-bypass, exactly for this case) instead
of deleting the coverage. Verified: full backend suite (6984 tests, all of `app/tests/`, not just
`services/`), ruff, mypy — all clean, zero behavior change.

### S7 — Move physics-only schema types out of `models/schemas/math/` ✅ shipped

`models/schemas/math/simulation.py` was entirely physics's own scene-fence schema
(`SimulationBlockSpec`, `SimulationBody`, `SimulationVector`, `SIMULATION_SPEC_TYPES`) misfiled
under the math package — confirmed by reading the whole file, not just its name. Moved verbatim to
`models/schemas/physics/simulation.py`; `GraphBlockSpec` (genuinely shared — physics trajectory
graphs reuse math's own graph fence type) stayed put. Four consumers repointed
(`physics/solver.py`, `physics/direct.py`, `math/fence.py`, `math/tools/direct.py`), plus one
deferred (function-local) import inside `test_physics_simulation.py` that a plain top-of-file grep
missed on the first pass and the full test suite caught. Mobile needed no change — the
`simulation` fence id in `fenceRegistry.ts` is a rendering primitive, not a subject boundary.

## Phase 4 — lock it in

### S10 — Seam test pinning the separation ✅ shipped

`test_subject_separation_seams.py`, mirroring `test_domain_package_seams.py`'s existing style:

- `test_math_and_physics_intent_kinds_are_disjoint` — the two `Literal` kind spaces share no value.
- `test_physics_intent_kind_count_matches_the_verified_registry` — `PhysicsIntent.kind`'s values
  equal `PHYSICS_BLOCK_BUILDERS`'s keys, exactly twenty; a kind added to one without the other is
  a silent dispatch miss in production, caught here instead.
- `test_physics_imports_from_math_are_allowlisted` — AST-walks every file in `services/physics/`
  for `from app.services.math...` / `from app.models.schemas.math...` imports and asserts the set
  found is exactly the four named, reasoned entries in `_ALLOWED_MATH_IMPORTS` (verified by hand
  that the scanner actually finds them — an allowlist test that silently matches nothing is worse
  than no test). A new import here must be added to the allowlist with a reason, not slip in
  silently.
- `test_new_subject_neutral_modules_import_cold_in_isolation` — extends
  `test_physics_modules_import_cold_in_isolation`'s fresh-interpreter pattern to
  `app.services.solving` specifically, since it sits in the real cycle S2 found and fixed
  (`math.solve` imports `MathServiceError` from it; it type-only-imports back into
  `math.solve.key_steps`) — a regression there only reproduces cold, never in a process where
  either side is already imported.

## Suggested order (revised) — Phases 1, 3, 4 done; Phase 2 open

Actual order: Phase 1 (S2, S3, S4, S8, S9) → **Phase 3 (S1, S7)** → Phase 4 (S10). Phase 2 (S5, S6)
moved behind Phase 3 on contact with the actual turn_prep code and remains open — see their
sections for why S6 is staying descoped for good rather than merely deferred, and what would
actually motivate S5.

**Shipped, all verified against the full backend suite (6984 tests across all of `app/tests/`,
not just `services/`), ruff, and mypy, with zero intended behavior change throughout:**

- Phase 1 — S2 (shared verified-block/error primitives), S3 (physics's private-internal reach-ins
  made public), S4 (shared text-scanning utilities), S9 (chemistry confirmed already clean). S8
  shipped as a documentation-only correction once its premise didn't hold up under closer reading.
- Phase 3 — S1 (`PhysicsIntent` split from `MathIntent`), S7 (physics simulation schema moved out
  of `models/schemas/math/`).
- Phase 4 — S10 (seam tests pinning all of the above).

**Still open:** Phase 2 (S5, S6) — S6 should probably never ship as originally scoped (see its
section); S5 is unblocked by S1 but has no consumer yet.

## Explicitly out of scope for this round

- The camera/scanner subject picker (math / physics / chemistry slider) — deferred by request.
- Any change to what a kind solves or how it's verified — zero intended behavior change; existing
  suites are the regression net, same as every prior domain-grouping pass in this codebase.
