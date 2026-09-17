# Recall — Subject Separation Tickets: math / physics / chemistry (planned, not started)

Math, physics, and chemistry are meant to be three peer subjects (Golden Rule 7: "Physics is
a peer subject in `services/physics/`, not a corner of math"). Chemistry mostly lives up to
that. Physics does not yet, and the gap isn't cosmetic — it's the literal type system. Physics's
own module docstring (`services/physics/__init__.py`) says it plainly:

> "Physics — a subject domain in its own right, not a corner of math... Physics reuses math's
> shared primitives (`MathIntent`, `VerifiedMathBlock`, `MathServiceError`) and plugs into
> math's dispatch through four registry seams."

That is today's actual state, not an aspiration: one shared intent type, one shared verified-block
type, and physics extraction/solving code that imports two underscore-prefixed (private) helpers
out of math's internals. This doc scopes the work to make the separation real. It does **not**
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
| Imports another subject's private (`_`-prefixed) internals | — | yes: `math.tools.school._extract_average_speed_intent`, `math.school._get_unit_registry` | no (checked; clean) |
| Duplicate cue list maintained outside its own package | — | yes: `services/routing.py` keeps its own independent `_PHYSICS_HOMEWORK_CUES` / `_PHYSICS_FORMULA_CUES`, unlinked to `physics/extract.py`'s cues | no |

Chemistry is the reference pattern. Physics needs to catch up to it, not the other way around.

## Phase 1 — stop reaching into each other's internals (no schema changes, low risk)

These don't require the type split in Phase 3 and can land first and independently.

### S2 — Give physics its own verified-block/error primitives instead of importing math's

`services/physics/block.py:15-16` and `direct.py:15` import `VerifiedMathBlock` from
`app.services.math.tools.block.common`, and `block.py:15` / `solver.py:24` import
`MathServiceError` from `app.services.math.solve`. Promote both out of the `math` package into a
subject-neutral home (e.g. `services/solving/common.py`, or alongside the existing shared types
in `models/schemas/common.py`) that math, physics, and chemistry all import from equally. Math
keeps whatever math-only extensions it needs on top; physics stops importing anything through a
path that starts with `app.services.math`.

### S3 — Stop physics reaching into math's underscore-prefixed internals

Two call sites, both deferred imports (added specifically to dodge the circular-import problem
described in S-note below, which is itself a symptom of the fusion):

- `services/physics/direct.py:231` → `app.services.math.tools.school._extract_average_speed_intent`
- `services/physics/solver.py:253` → `app.services.math.school._get_unit_registry`

`_get_unit_registry` is pure Pint setup with nothing math-specific about it — promote it to a
shared utility (it's exactly the kind of thing S2's new neutral module should hold). For
`_extract_average_speed_intent`, decide which subject actually owns "average speed" as a concept
and expose it as a real public function from that subject for the other to call — an underscore
name being imported cross-package means math never intended this dependency to be load-bearing,
and it is one anyway.

### S4 — Move physics off `math.match` for text-scanning utilities

`services/physics/extract.py:17-18` imports `app.services.math.match as mtm` and
`app.services.math.match.scan.word_index`. `word_index` and similar helpers are generic string
scanning with no math semantics — promote them to a subject-neutral text-matching module (e.g.
`services/text_match.py`) that both `math.match` and `physics.extract` import from, instead of
physics importing through math to get to them.

### S8 — Fold `routing.py`'s duplicate physics-cue list into the physics package

`services/routing.py` maintains its own `_PHYSICS_HOMEWORK_CUES`, `_PHYSICS_FORMULA_CUES`, and
`_looks_like_physics_homework()` for Auto model-tier escalation, entirely independent of
`physics/extract.py`'s own cues. Three unlinked "what counts as physics" lists already exist in
this codebase (`extract.py`'s cues, `routing.py`'s cues, and the verified-kind list baked into
`MATH_SOLVER_HINT`) — that's the exact shape of bug Physics Round 3 already found once, where a
pre-filter and its extractor silently disagreed on casing and a real question never reached
extraction in production despite its own test passing. Export a public check from
`services/physics/` (`has_supported_physics_cue` already exists and is close) and have
`routing.py` call it instead of maintaining a parallel list.

### S9 — Audit chemistry (expected to be mostly a confirmation, not a fix)

Chemistry already has its own gate, its own turn_prep locals, and a conditionally-injected prompt
hint. A grep across `apps/api/app` for `chemistry` outside its own package turned up only the
turn_prep integration points every subject needs, test files, and one legitimate disambiguation
touch in `services/images/gen_intent.py` / `lookup_intent.py` (so "draw a benzene ring" routes to
chemistry, not image generation). No private-internal reach-ins found. This ticket is: confirm
that stays true (feeds directly into S10's guard test) rather than a refactor.

## Phase 2 — turn-prep parity with chemistry

### S5 — Give physics its own `needs_physics` / `physics_block` in turn_prep

`services/chat/turn_prep/context.py` currently has only `needs_math` / `math_block` as locals;
physics rides entirely inside them. Chemistry's `needs_chem` / `chem_block` in the same file is
the template — copy its shape. This is the ticket that actually makes physics a peer at the one
place every chat turn passes through, and it's mechanical: the pattern already exists three lines
away in the same function. Can key off `MathIntent.kind` membership in the physics set even
before Phase 3 ships, if sequencing needs it, though it's cleaner once S1 exists.

### S6 — Split `MATH_SOLVER_HINT` into independent per-subject prompt hints

`prompt_constants/math.py`'s `MATH_SOLVER_HINT` currently contains the physics-verified-kinds
paragraph inline, shipped on every math-flavored turn whether or not the turn is actually physics.
Extract a `PHYSICS_SOLVER_HINT` into a new `prompt_constants/physics.py`, injected only when
`needs_physics` (from S5) is true — mirrors `CHEMISTRY_FENCE_HINT`'s existing, already-correct
pattern in `visuals.py` ("Only injected when turn_prep actually has chemistry context"). Side
benefit: pure-math turns stop paying prompt tokens for a physics paragraph they never needed.

## Phase 3 — the real type split (bigger, do after Phase 1/2 de-risk the seams)

### S1 — Split `MathIntent` into subject-specific intent types

`models/schemas/math/intent.py` holds one `Literal[...]` with 49 values; physics's 20
(`kinematics` … `modern`) are interleaved with math's 29. No `PhysicsIntent` exists anywhere.
Introduce `PhysicsIntent` with its own 20-value `kind` enum in a new `models/schemas/physics/`
package; narrow `MathIntent.kind` to the remaining math-only values. This touches every
`_verified_block_*` / extractor / direct function currently type-hinted against `MathIntent` for
a physics kind — mechanical but real surface area, and the biggest ticket in this doc. Decide up
front whether math and physics intents share a base class for common fields (`variables`, etc.)
or stay fully independent; recommend fully independent given how little actually overlaps beyond
`kind`.

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

## Suggested order

Phase 1 (S2, S3, S4, S8, S9) → Phase 2 (S5, S6) → Phase 3 (S1, S7) → Phase 4 (S10). Phase 1 is
low-risk cleanup that can start immediately and ships value on its own (it's already bugs-shaped:
S8 in particular is a latent drift risk, not just a tidiness issue). Phase 3 is the one that
actually earns the word "separate" at the type level and should wait until Phase 1 has removed
the private-internal dependencies it would otherwise have to migrate too.

## Explicitly out of scope for this round

- The camera/scanner subject picker (math / physics / chemistry slider) — deferred by request.
- Any change to what a kind solves or how it's verified — zero intended behavior change; existing
  suites are the regression net, same as every prior domain-grouping pass in this codebase.
