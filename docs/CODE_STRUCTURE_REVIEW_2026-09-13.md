# Recall — Code Structure Review: domain grouping and scalability (Sep 2026)

A structural pass over both apps, asking one question: **can a person find the code for a
subject, and does adding the next subject cost one file or twenty?** Not a correctness or
security review — those live in the dated `*_REVIEW_*.md` files alongside this one.

Findings are recorded first, then what was changed in response, then what is deliberately
left.

## Overall verdict

**Infrastructure scales. Subject and feature domains did not.**

The layering is real and enforced in practice. Repositories import no services, gateways, or
routers; `core` reaches into domain code only in `deps.py`; one gateway imports one repository
constant. At 44k lines of application Python that is unusually clean, and none of it needed
changing.

What did not scale was *grouping*. Domains were spread across sibling packages and flat modules
with no rule for which a new file should be, and math — the most-invested subject — had sprawled
furthest. Nothing named `math/` existed anywhere, while ~17.5k lines of math sat in three sibling
packages plus six loose modules plus four outliers.

The leading indicator, measured as non-test files mentioning a subject **outside its own
directory**:

| Subject | Before | After | Had a package before? |
|---|---:|---:|---|
| math | 171 | 47 | no |
| chemistry | 22 | 8 | yes, plus three aliases |
| physics | 14 | 11 | no |

Math started where chemistry was and grew into the codebase because no seam contained it. That
curve, not any individual file, was the actual finding.

## Findings

### 1. `services/` root was a dumping ground

80 flat modules (~17.5k lines) beside 12 packages (~38k). No written rule for when a domain earns
a package, so it was decided case by case, and the case-by-case answer was usually "not yet".

### 2. The domain-package migration was half-done and split by subject

`chemistry/`, `learning/` and `notifications/` had been packaged. `math`, `physics`,
`attachments`, `images` and `email` had not. The repo taught two conflicting patterns at once.

### 3. Packaged domains still carried a second copy of themselves

Eight compatibility aliases (`chemistry_service`, `chemistry_context`, `chemistry_fence`,
`push_notifications`, `transactional_email`, `reminder_emails`, `daily_learning`, `sm2`) forwarded
to their packages via `sys.modules`, and live code still went through them —
`services/chat/turn_prep/context.py` imported `chemistry_context`, and modules *inside*
`services/learning/` imported `app.services.daily_learning`, their own shim. A seam test asserted
the aliases resolved correctly, which pinned the split-brain layout in place rather than retiring
it.

### 4. Math was five siblings plus six loose files, under names that said nothing

`math_tools/` (6.9k), `math_text_match/` (3.2k), `math_service/` (2.9k), `math_fence.py`,
`math_school.py`, `math_ocr.py`, `math_followup.py`, `math_image_extract.py`,
`math_reply_policy.py`, and `sympy_executor.py` — which did not even carry the prefix. Plus
`gateways/mathpix_gateway.py`, `models/schemas/math/`, `services/mcp/sympy_adapter.py`,
`services/chat/prompt_constants/math.py`.

The three package names were the worst part: nothing in `math_tools` vs `math_service` vs
`math_text_match` tells a reader where an equation is parsed versus solved.

### 5. Physics had no home — it was filed inside math's tooling

1,467 lines across three different parents: `services/physics_solver.py`,
`math_tools/physics.py`, `math_tools/direct_physics.py`, `math_tools/block/physics.py`, plus
routing in `services/routing.py`. Physics is a peer subject to math and chemistry; it was
structured as a subfolder of math's extractor layer.

### 6. Mobile was worse: 201 flat files in `lib/`, with the same splits

`lib/math/` held 9 files against 9 flat `lib/math*.ts` siblings — plus six math features whose
names did not say math (`geometryBlock`, `graphBlock`, `graphExpr`, `graphViewport`,
`inequalityGraph`, `normalizeImplicitMath`). `lib/chat/` held 9 against 16. `lib/markdown/` held
9 against 2. Chemistry had no folder at all despite having a backend package.

Inside the folders the convention was itself inconsistent: `lib/math/` mixed `answerLayout.ts`
with `mathFenceRetag.ts`, so the prefix meant nothing either way.

### 7. A size rule without a grouping rule manufactures sprawl

`.cursor/rules/code-quality.mdc` says split files over ~300 lines. Where it was followed without
a domain to split *into*, it produced seven flat siblings — `direct_calculus`, `direct_geometry`,
`direct_newton`, `direct_physics`, `direct_solids`, `direct_statistics`, `direct_units`. The rule
is good; it needs a destination.

### 8. Doc drift in the map people trust

CLAUDE.md's registered-router list omitted `analytics` and `speech_realtime`, both live in
`main.py`.

### 9. Tests do not mirror the source tree

`tests/services/` is 176 flat files against 12 source packages, 58 of them math, and there is no
`tests/routers/` for 24 routers. **Not addressed** — see *What is deliberately left*.

## What changed

Every step verified against the full suite: **5,956 backend tests** (the 108 errors in
`tests/repositories/` are pre-existing and need a live Postgres) and **3,530 mobile tests**, plus
typecheck and lint.

| Change | Result |
|---|---|
| All eight compatibility aliases deleted, call sites repointed | one path per domain |
| `services/physics/` — `solver`, `extract`, `direct`, `block` | physics is a peer subject |
| `services/math/` — `match/` → `tools/` → `solve/`, plus `fence`, `school`, `ocr`, `followup`, `image_extract`, `reply_policy`, `sympy_executor` | one package, stages named for what they do |
| `services/attachments/`, `images/`, `email/` | last three flat families |
| `chat_*` → `chat/`, `memory_llm` → `memory/llm` | no module shadows its own package |
| `lib/math/`, `lib/chat/`, `lib/chemistry/`, `lib/markdown/` consolidated, redundant prefixes dropped | mobile domains match the backend |
| `test_service_layout.py` + `lib/__tests__/libLayout.test.ts` | the layout is now enforced |

`services/` root: **80 flat modules → 44**, across **14 domain packages**. Mobile `lib/`:
**201 flat → 165**.

Two things worth knowing about the mechanics:

- **A latent import cycle became a real one and was fixed.** `math.tools.block` imported physics'
  builders at module level while `physics.block` imported math's block primitives. It only worked
  because math was always imported first; importing `app.services.physics.block` cold raised
  `ImportError`. The physics import is now deferred into the function that uses it, next to the
  `SCHOOL_BLOCK_BUILDERS` import already deferred there for the same reason, and a seam test
  imports each module in a fresh interpreter so it stays honest.
- **One re-export was nearly lost.** `stream.py` re-exported `attachment_lifecycle` purely so
  `stream_entry` could reach it as `seams.attachment_lifecycle`. It survived ruff's unused-import
  pass only because it used the redundant-alias idiom (`X as X`); under the new path the alias
  differs from the name, so ruff removed it and a test caught it. It is back, with a comment
  saying why it exists.

## The rule, going forward

Both guards encode the same rule, and CLAUDE.md now states it:

> A domain lives in one package. A second module sharing a domain's prefix means the domain wants
> a package — not another sibling. Inside the package the prefix comes off, because the directory
> carries it.

The guards fail on the next violation and name the file and its destination. Writing them found
four cases nobody had noticed: `chat_history_rag`, `chat_titles`, `chat_tools`, `memory_llm` on
the backend, and `markdownIt`, `markdownPlain` on mobile.

Two deliberate exceptions, both encoded:

- `reminder_timing.py` stays at `services/` root. `notifications/`, `home/` and `learning/` all
  use it, so it is genuinely cross-cutting rather than misfiled.
- `lib/api.ts` stays beside `lib/api/`. An exact name match is the barrel idiom CLAUDE.md
  requires, not a split; only a camelCase extension of a folder name is a stray module.

## What is deliberately left

Ranked by value, honestly scoped — none of it is blocked, it is simply not done.

1. **No subject registry (the real scalability ceiling).** Subjects are still hand-wired into the
   turn as parallel locals in `services/chat/turn_prep/context.py`: `needs_math`, `needs_chem`,
   `chem_coro`, `math_block`, `chem_block`. Adding biology still means editing that file plus
   `routing.py`, `prompt_constants/`, `mode.py`, `stream_pipeline.py`, `fenceRegistry.ts`,
   `RichFence.tsx` and more. A `SubjectSpec` registry (`detect` / `build_context` / `fence_id` /
   `prompt_hint`) that `context.py` loops over would turn that into one file plus a fence.
   **Packaging the subjects was the prerequisite for this, not a substitute for it.**
2. **Tests do not mirror the source tree** (finding 9). `tests/services/` is still 176 flat files,
   and there is still no `tests/routers/`.
3. **Mobile `lib/` still has 165 flat modules.** Fourteen families of three or more remain
   (`drawer*`, `attachment*`, `image*`, `export*`, `email*`, `live*`, `home*`, …). These are
   feature and utility families rather than subject domains, so they were left rather than churned;
   the mobile guard only enforces non-shadowing, not family size, so it will not flag them.
4. **`components/` has 66 flat `.tsx` at root** beside its 10 subfolders — the same pattern one
   level up, untouched.
5. **Large files remain large.** `prompt_builder.py` (1,001), `math/match/scan.py` (900),
   `litellm_gateway.py` (873), `learning_items.py` (835). The ~300-line rule is still unenforced;
   it now at least has domains to split into.
