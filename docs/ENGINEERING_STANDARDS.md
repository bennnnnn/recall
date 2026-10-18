# Engineering standards

Every feature, module and pull request follows these rules. They keep Recall easy to change as
maths, physics and chemistry grow and biology arrives. `CLAUDE.md` is the map of where things
live; this file is how code there is shaped. The ranked list of current violations, with the
fix for each, is [ENGINEERING_STANDARDS_TICKETS.md](./ENGINEERING_STANDARDS_TICKETS.md).

Sizes and counts below are review thresholds, not laws. A short function can still be badly
designed and a long one can be justified. What CI can check reliably, it checks (see
[Enforcement](#enforcement)); the rest is review.

## Core rules

1. **Single responsibility.** Each module, class, component, hook and function has one clear
   purpose. Split by responsibility and coupling, not by line count alone.
2. **One source of truth.** Each business rule, formula, unit table and shared constant has
   one authoritative implementation. Fix shared behavior there and test its consumers; never
   copy and patch.
3. **Reuse, without premature abstraction.** Search for an existing implementation before
   adding one. Extract shared code only when behavior and ownership really match; similar
   looking code is not necessarily the same concept.
4. **Independent modules.** Subjects and features meet through explicit public surfaces. A
   change to chemistry must not break physics or maths.
5. **No God files, objects or functions.** Nothing owns a whole subsystem or collects
   unrelated jobs.
6. **Clear dependency direction.** Presentation → application → domain; infrastructure sits
   behind adapters. No import cycles.
7. **Strict types.** No `any`, unchecked casts or unexplained `# type: ignore`; validate data
   from outside (requests, model output, provider responses) with Pydantic or a typed parser.
8. **Explicit errors.** Handle errors at the boundary that can act on them. Never swallow a
   failure or return a made-up success. Best-effort work (post-turn jobs) logs and moves on,
   by design and in the open.
9. **No dead code.** Remove unused code, unreachable branches, obsolete files, stale flags
   and thin wrappers that only forward their arguments.
10. **Names and constants.** Names say what a thing is for (`unit_conversion.py`, not
    `utils.py`; no `Manager`, `Helper2`, `processData`). Unexplained numbers and strings
    become named constants or settings. Comments explain why, not what.

## Layers

| Layer | API (`apps/api/app`) | Phone (`apps/mobile`) |
|---|---|---|
| Presentation | module `api.py`, legacy `routers/` — thin HTTP | `app/` routes, feature `screens/` and `components/`, `components/`, `ui/` |
| Application | module `service.py`, `modules/chat/` turn prep and stream, jobs | feature `hooks/`, `contexts/` |
| Domain | maths `solve/` `match/` `tools/school/`, physics `solvers/` `catalog/` `extractors/`, chemistry `solvers/` `extractors/`, `services/law_binding/` | `lib/math`, `lib/physics`, `lib/chemistry` (render models), feature `model/` |
| Infrastructure | `gateways/`, `repositories/`, `core/` (DB, Redis, jobs), `models/orm/` | `lib/api/*` and feature `api.ts`, device APIs (`expo-*`) |

- Domain code is pure: it runs without a database, network, model provider or React Native
  runtime. Calculations take inputs and return results; adapters fetch and store.
- Screens render state and handle input; logic lives in hooks and models.
- `core/` and `gateways/` never import `modules/`; `ui/` never imports product code.
- No hidden coupling: no module-level mutable state that leaks between requests, no reaching
  into another module's private helpers, no undocumented side effects.
- Shared modules are named by purpose (formula evaluation, unit conversion, dates, error
  formatting). A change to one is checked against every consumer.

## Subjects

- Each subject owns its rules: `modules/<subject>/` on the server, `lib/<subject>/` on the
  phone. The shared law-binding engine is `services/law_binding/`; shared maths primitives
  may be reused without making subjects depend on each other.
- One subject imports another only through its public files (package `__init__`, `schemas`,
  `service`, `api`), never its solvers or extractors. A law two subjects use has one owner
  (the STEM corpus `shared` field names it).
- The phone renders verified results and walks sampled paths; it never solves or re-derives
  (CLAUDE.md rule 7).
- A new subject (biology) is a new module with its own catalog, extractors, solvers, fence and
  STEM corpus folder, plugged in at the existing seams (routing, `lib/fenceRegistry.ts`). It
  needs no edits inside another subject.

## Size and shape

| What | Default | Review |
|---|---|---|
| Production file | 300 lines or fewer | Over 500 needs a recorded reason and may not grow. 900 is an exceptional ceiling. |
| Function | under 40–50 lines | Longer functions are checked for mixed responsibilities. |
| Nesting | 3 levels of control flow | Use guard clauses and small helpers. |
| Abstractions | when they pay for themselves | No speculative interfaces or wrappers. |

Tests and generated or vendored files are exempt from the file limits. Do not split a cohesive
algorithm, data table or test only to meet a number; record it as an exception instead.

## STEM correctness

Correct maths, physics and chemistry is a release requirement.

- Calculations live in deterministic domain modules with unit tests. SymPy (server) is the
  checker; a second model answer is never proof. Only the server marks an answer
  `verified: true`.
- Check units, dimensions, sign conventions, domain restrictions and edge cases. Compare
  floats with a tolerance (the STEM sweep allows 1 %, any unit of the same kind).
- Every confirmed correctness bug gets a regression test: a unit test, a STEM corpus entry or
  a behavior sweep entry. STEM sweep coverage floors only go up.
- Use property-based tests (`hypothesis`) for invariants over wide input ranges.
- Validate model-written formulas and structured output before showing them as correct. If a
  check fails, say so; never show a plausible guess as a verified result.

## Security, performance, reliability

- Validate untrusted input at the boundary: requests, scanned text, uploads, provider and
  model output. See [SECURITY.md](../SECURITY.md).
- No secrets in the phone app, logs, source control or error messages.
- Least privilege for credentials, database roles and integrations.
- No repeated work: batch independent calls, cache hot reads, no heavy work per keystroke or
  per streamed token. Handle timeouts, cancellation, retries and duplicate requests.
- Accessibility: screen-reader labels, contrast, scalable text, real touch targets.
- Measure before optimizing.

## Enforcement

| Check | How | Runs in |
|---|---|---|
| Format and lint | `ruff check`, `ruff format`; ESLint | API CI, Mobile CI |
| Types | mypy (strict per package, widening); `tsc` strict; ESLint `no-explicit-any` | API CI, Mobile CI |
| Tests | pytest with 80 % coverage floor; jest; behavior and STEM sweeps | API CI, Mobile CI |
| Import cycles | `app/tests/architecture/test_import_cycles.py`; `lib/__tests__/importCycles.test.ts` (type-only imports included) | API CI, Mobile CI |
| Layer boundaries | `app/tests/architecture/` (module boundaries; `test_pure_solvers.py` keeps solvers off infrastructure and subjects apart); ESLint `no-restricted-imports` (`ui/` leaf, subject libraries) | API CI, Mobile CI |
| File size | `scripts/check_file_sizes.py` against `scripts/file_size_baseline.json` | API CI, Mobile CI |
| Security | CodeQL, Dependabot, GitHub secret scanning | GitHub |
| Build | API image build; web build | API CI, Web CI |

`./scripts/dev.sh check` runs the same gate locally.

**Exceptions.** A file over 500 lines is listed in `scripts/file_size_baseline.json` with its
reason: either a documented exception (one table, catalog or algorithm) or the ticket that
splits it. The size there is a ceiling; after a split, `scripts/check_file_sizes.py --update`
lowers it. Any other exception (a `# noqa`, an ESLint disable) carries a one-line reason.

## Changing code

Before: read the code, its callers, its tests and the shared modules nearby. Find the root cause
and the smallest coherent change, and check for duplication and cross-module impact.

After: add or update tests, check affected consumers, run the gate, and report what changed,
which tests ran, and any risk or exception left. Never claim a check passed that did not run.

Do not rewrite broadly to make code look cleaner. Preserve working behavior, keep unrelated
changes out, and refactor in small tested steps.

## Definition of done

- Ownership is clear, and existing implementations were reused where they fit.
- Responsibilities and dependencies follow the layers above.
- Inputs, outputs, errors and edge cases are handled, and tests cover the important behavior.
- No regressions, duplication or unrelated changes.
- UI handles loading, empty, error and success states, plus accessibility.
- Docs and public interfaces are updated where they changed.
- CI is green, and every exception is written down with its reason.
