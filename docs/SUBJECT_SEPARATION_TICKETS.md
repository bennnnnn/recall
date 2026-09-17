# Recall — Subject Separation Tickets: math / physics / chemistry (Phase 1 shipped)

Math, physics, and chemistry are meant to be three peer subjects (Golden Rule 7: "Physics is
a peer subject in `services/physics/`, not a corner of math"). Chemistry mostly lives up to
that. Physics does not yet, and the gap isn't cosmetic — it's the literal type system. Physics's
own module docstring (`services/physics/__init__.py`) says it plainly:

> "Physics — a subject domain in its own right, not a corner of math... Physics reuses math's
> shared primitives (`MathIntent`, `VerifiedMathBlock`, `MathServiceError`) and plugs into
> math's dispatch through four registry seams."

That was the actual state when this doc was written (the docstring has since been updated to
match Phase 1, below). What's left after Phase 1: one shared intent type — physics problems are
still represented as a `MathIntent` whose `kind` is one of its twenty physics values (Phase 3, not
done). This doc scopes the work to make the separation real. It does **not**
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
| Own intent/schema type | `MathIntent` (`models/schemas/math/intent.py`) | **none** — reuses `MathIntent`, its 20 kinds interleaved into math's 29 in one `Literal[...]` | n/a (no structured intent schema; own gate function instead) |
| Own turn_prep gate + context local | `needs_math` / `math_block` (`turn_prep/context.py`) | **none** — rides inside `needs_math` / `math_block` | `needs_chem` / `chem_block` — already separate |
| Own detection gate | `needs_symbolic_math` | shares `needs_symbolic_math`; contributes cues via `has_supported_physics_cue` | `is_chemistry_question` (`services/chemistry/context.py`) — already separate |
| Prompt hint, conditionally injected only when relevant | n/a (always injected on math turns) | **none** — its verified-kinds paragraph is appended inside `MATH_SOLVER_HINT` (`prompt_constants/math.py`) and ships on every math turn | `CHEMISTRY_FENCE_HINT` (`prompt_constants/visuals.py`), injected only when turn_prep actually found chemistry context — the pattern to copy |
| Imports another subject's private (`_`-prefixed) internals | — | **fixed (S3)** — both helpers are now public (`extract_average_speed_intent`, `get_unit_registry`); physics calls them as intentional cross-subject API, not private reach-ins | no (checked; clean) |
| Duplicate cue list maintained outside its own package | — | kept as-is (S8) — see note below; not the bug it first looked like | no |

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

### S5 — Give physics its own `needs_physics` / `physics_block` in turn_prep — blocked on S1

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
what the task requires" this codebase's own conventions warn against. It becomes a normal,
motivated addition the moment S1 exists: a `PhysicsIntent` result on `verified_math` (vs.
`MathIntent`) is a real type distinction to key `needs_physics` off, not a derived boolean nobody
consumes yet. Do S1 first.

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

## Phase 3 — the real type split (now first, since Phase 2 depends on it)

### S1 — Split `MathIntent` into subject-specific intent types

`models/schemas/math/intent.py` holds one `Literal[...]` with 49 values; physics's 20
(`kinematics` … `modern`) are interleaved with math's 29. No `PhysicsIntent` exists anywhere.

Audited physics's actual field usage before scoping the split further (`grep` every
`MathIntent(...)`/`.model_validate(...)` construction site in `services/physics/*.py`, plus every
non-`physics_*` attribute access): of `MathIntent`'s 49 fields, physics touches exactly `kind`
(its 20 values), `physics_op`, `physics_params`, `physics_units`, plus reads `.expr`/`.kind` for
the average-speed cross-check into math's arithmetic path. `school_op` stays math's — it's how
`average_speed` (a math/arithmetic kind) opts into the physics-style direct-reply path without
being a physics kind itself. This is a clean, narrow footprint, not the sprawling shared-schema
problem it could have been — confirms independent types are the right call and scopes the actual
diff: introduce `PhysicsIntent` (20-value `kind`, `physics_op`, `physics_params`, `physics_units`)
in a new `models/schemas/physics/` package; narrow `MathIntent.kind` to the remaining 29 values
and drop the three `physics_*` fields from it. Touches every extractor/direct/solver/block
function in `services/physics/` currently type-hinted `MathIntent` (~60 construction sites, mostly
in `extract.py`), plus the dispatch seam in `math/tools/block/__init__.py` where
`_build_verified_block(intent: MathIntent, ...)` currently hands the same object to whichever
registry (`_BLOCK_BUILDERS` / `SCHOOL_BLOCK_BUILDERS` / `PHYSICS_BLOCK_BUILDERS`) claims
`intent.kind`, plus `VerifiedMathBlock.physics_intent`'s type. Mechanical but real surface area —
the biggest ticket in this doc.

### S7 — Move physics-only schema types out of `models/schemas/math/`

`models/schemas/math/simulation.py` hosts physics simulation-scene types (`projectile_motion` and
siblings) under the `math` schema package — there is no `models/schemas/physics/` today. Once S1
creates that package, move physics-only simulation types into it; leave any genuinely
math-only graph/geometry types where they are. (Mobile's `fenceRegistry.ts` needs no change here
— the `simulation` fence id is a rendering primitive, not a subject boundary, and is fine shared
exactly as it is today.)

## Phase 4 — lock it in

### S10 — Seam test pinning the separation

This repo already polices exactly this class of drift (`test_service_layout.py`,
`test_domain_package_seams.py`, and Physics Round 3's
`test_a_solved_topic_is_not_still_listed_as_unchecked`, which loops over every kind with a solver
instead of checking one hardcoded word). Add the equivalent for this doc: `MathIntent.kind`
contains no physics-only literal, `PhysicsIntent.kind` contains no math-only literal, and
`services/physics/` imports nothing from `services/math/` outside an explicit allowlist (ideally
empty after Phase 1). Land this last so it's checking the end state, not blocking the migration
that produces it.

## Suggested order (revised)

Phase 1 (S2, S3, S4, S8, S9) → **Phase 3 (S1, S7)** → Phase 2 (S5, S6, revised scope) → Phase 4
(S10). Phase 2 moved behind Phase 3 on contact with the actual turn_prep code: S5/S6 both need a
real type distinction between a math-dispatched and a physics-dispatched verified block to be
worth doing safely, and S1 is what creates that distinction. Doing them in the original order
would have meant either shipping a field nobody reads (S5) or weakening a tested safety property
for no one's benefit (S6, see its section).

**Phase 1: done.** S2/S3/S4/S9 shipped as scoped; S8 shipped as a documentation-only correction
once the premise didn't hold up under closer reading (see its section). Verified against the full
backend suite, ruff, and mypy — zero behavior change anywhere in Phase 1.

## Explicitly out of scope for this round

- The camera/scanner subject picker (math / physics / chemistry slider) — deferred by request.
- Any change to what a kind solves or how it's verified — zero intended behavior change; existing
  suites are the regression net, same as every prior domain-grouping pass in this codebase.
