# Recall — Math Feature Final Pre-Launch Audit (Sep 2026)

**Status: NOT launch-ready as-is. Nine independently-reproduced P0 bugs, several of which
produce a confidently "SymPy-verified, do not recompute" answer that is mathematically
wrong, with zero LLM cross-check and zero visual distinction from a correct one.**

This is the consolidated report for a full-pipeline, line-by-line critical review of
Recall's math feature — every math type (algebra, geometry, graph/plotting, calculus,
physics, discrete/stats, units), the camera "Scan Math" scanner, the custom math keyboard,
model routing, prompt engineering, the MCP tool loop, and mobile rendering. Six independent
subagents each covered one layer of the pipeline described in `docs/math.md`, and — per
explicit instruction — verified claims by **actually running code** (live SymPy 1.14.0,
the real pytest/Jest suites, and hand-derived correct answers) rather than reading and
guessing. Every finding below has a runnable reproduction in its source report.

| # | Report | Scope | P0 | P1 | P2/P3 |
|---|---|---|---|---|---|
| 1 | [`MATH_SYMPY_CORE_REVIEW_2026-09-06.md`](./MATH_SYMPY_CORE_REVIEW_2026-09-06.md) | SymPy solver core (`math_service/`), subprocess sandbox | 1 | 1 | 2 |
| 2 | [`MATH_INTENT_EXTRACTION_REVIEW_2026-09-06.md`](./MATH_INTENT_EXTRACTION_REVIEW_2026-09-06.md) | Pre-stream intent detection (`math_text_match/`, `math_tools/extract*`) | 2 | 3 | 6 |
| 3 | [`MATH_FENCE_PHYSICS_REVIEW_2026-09-06.md`](./MATH_FENCE_PHYSICS_REVIEW_2026-09-06.md) | Post-stream fence rewrite (`math_fence.py`), physics templates | 0 | 4 | 2 |
| 4 | [`MATH_ROUTING_PROMPTS_MCP_REVIEW_2026-09-06.md`](./MATH_ROUTING_PROMPTS_MCP_REVIEW_2026-09-06.md) | Model routing, prompt hints, MCP tool-loop integration | 1 (+1 shared) | 1 | 1 |
| 5 | [`MATH_MOBILE_RENDERING_REVIEW_2026-09-06.md`](./MATH_MOBILE_RENDERING_REVIEW_2026-09-06.md) | Mobile rendering (`MathText`, KaTeX/MathJax, `GeometryBlock`, streaming) | 0 | 1 | 3 |
| 6 | [`MATH_INPUT_UX_REVIEW_2026-09-06.md`](./MATH_INPUT_UX_REVIEW_2026-09-06.md) | Camera scanner + math keyboard UX | 2 | 2 | — |

All pre-existing automated tests pass across every layer (175 + 344 + 99 + 177 + 342 + 264
+ 61 = **1,462 tests, all green**) — this audit's findings are exclusively in scenarios the
existing suites do not exercise, not regressions.

---

## 1. Verdict

**The architecture is sound and much of it is genuinely excellent** — a real Pydantic
schema for every verified math kind, a subprocess-sandboxed SymPy core with a closed RCE
surface, a fence-rewrite layer whose canonical-answer/canonical-fence pairing cannot drift
apart by construction, and mobile parsers that are all *total* (none of six reviewers could
find an input that crashes the render path rather than degrading gracefully). This is not
a codebase that needs a redesign.

**But the specific promise this feature is built around — "SymPy verifies, the model
narrates, do not recompute" — is broken in nine independently reproduced ways**, spanning
every layer from intent detection through the solver core to the fence-rewrite output gate.
Every one of these bugs fires on *ordinary, non-adversarial homework phrasing* — not
crafted edge cases:

- A student who writes **"what's the derivative of x squared plus 3x"** (the single most
  natural way to ask a calculus question in English) gets a fabricated 16-character
  nonsense symbolic expression presented as a verified answer.
- A student solving **"e + 1 = 5"** — even after explicitly typing **"solve for e"** — is
  told there's no solution, because the system silently treats their variable as Euler's
  number and never lets an explicit instruction override it.
- A student who writes **"A ball is dropped from 20m. What is its velocity after 3
  seconds?"** — an extremely common phrasing — gets a wrong answer because the word
  "**Wh­at**" contains the substring "at", which the extractor mistakes for a velocity
  keyword.
- A student solving a **"thrown downward"** kinematics problem — a phrasing the code's own
  cue list explicitly claims to support — silently gets the *upward*-throw answer instead.
- A multi-part question ("**graph y=x² and also solve 3x=9**") can have its *entire*
  server-side verification disabled by a wrong parse of one fragment, with no signal to
  the model or user that verification silently failed.
- **Two independent reviewers, working on different layers, found the same underlying gap
  from different angles**: a model that fabricates a schema-valid but numerically invented
  geometry/graph diagram ships to the student completely unmodified — there is no
  server-side check that a diagram's *numbers* are true, only that its *shape* parses.
- On the input side, tapping "Scan Math" **silently deletes whatever the student already
  typed**, and pasting the single most common bare math glyph (**√9**) corrupts into
  `\sqrt{}9` — an empty radical next to a stray digit.

None of these are exotic. Several are close to the *median* phrasing for their problem
type. This is exactly the failure mode a "math powerhouse, error-free, trusted by
students" cannot ship with: a confidently wrong answer is worse than no verification at
all, because it looks identical to a correct one.

**Recommendation: fix the P0 list below before launch.** Every fix is small and
independently shippable (effort S–M per finding, no redesign required) — the estimated
total scope is roughly 8-12 small, single-concern PRs, most of them one-line-to-one-function
changes with a new regression test.

---

## 2. P0 findings — fix before launch

Ordered by estimated blast radius (how common the triggering phrasing is), not by report.

### P0-A — Calculus/limit/series extractors sympify raw English prose into a nonsense "verified" answer
**Source:** [Intent Extraction M1](./MATH_INTENT_EXTRACTION_REVIEW_2026-09-06.md#m1--calculuslimitseries-extractors-sympify-raw-english-prose-producing-a-nonsense-verified-symbolic-result) · **Effort:** M

"What's the derivative of x squared plus 3x" is extracted as the literal string `'of x
squared plus 3x'` and handed to SymPy, which multiplies together one free variable per
English letter (`o·f·x·s·q·u·a·r·e·d...`), silently resolving the letter `e` to Euler's
number along the way, and returns a fabricated symbolic derivative presented as
`Verified result: 16.3096909707543 a d f l o p q r s^{2} u^{2} x`. Fires on **any**
spelled-out calculus phrase — differentiate/integrate/simplify/factor/expand and limits
all share this code path. Fix: translate-or-reject before sympify (dictionary substitution
for "squared"/"plus"/etc., or hard-reject any candidate expression containing multi-letter
English words after digit/operator/known-variable stripping).

### P0-B — "roots of X" / "zeros of X" prose rewrite hits the same nonsense-sympify path on non-math sentences
**Source:** [Intent Extraction M2](./MATH_INTENT_EXTRACTION_REVIEW_2026-09-06.md#m2--roots-of-x--zeros-of-x-prose-rewrite-feeds-non-math-english-into-the-same-un-parsed-sympify-path) · **Effort:** S

"roots of my hair are 2 inches long" is rewritten to `solve my hair are 2 inches long = 0`
(gated only by "contains the phrase and a digit anywhere in the message") and produces a
fully-formatted verified `a = 0.0`. Same root cause as P0-A, different entry point — share
the fix.

### P0-C — `e`/`E` silently resolve to Euler's number instead of the student's variable, defeating even an explicit "solve for e"
**Source:** [SymPy Core M1](./MATH_SYMPY_CORE_REVIEW_2026-09-06.md#m1--ee-silently-resolve-to-eulers-number-instead-of-the-users-variable-this-defeats-even-an-explicit-solve-for-e-request-and-produces-a-confidently-wrong-no-solution) · **Effort:** S

`guess_variables()` excludes `e`/`E` from candidate variable letters (correctly, to protect
`sin(pi*x)`-style expressions) — but the same exclusion is hard-coded into the *explicit
disambiguation* path (`_requested_variable`), so literally typing "**Solve for e**: e + 1 =
5" still resolves to `variable='x'` and reports "no solution" for a trivially solvable
equation (`e=4`). Every other single-letter SymPy global (`I`, `S`, `N`, `O`, `Q`, `C`) is
*not* excluded and works correctly — the fix is narrow: honor an explicit "solve for e" cue
even when `e` is otherwise excluded from the default candidate list.

### P0-D — Kinematics extractor's `"at"` velocity keyword substring-matches inside ordinary words ("What", "later", "that")
**Source:** [Fence/Physics F2](./MATH_FENCE_PHYSICS_REVIEW_2026-09-06.md#f2--the-kinematics-extractors-at-velocity-keyword-matches-as-a-substring-inside-ordinary-english-words-what-later-that-so-a-completely-standard-homework-phrasing-extracts-the-wrong-v0) · **Effort:** S

"A ball is dropped from 20m. **What** is its velocity after 3 seconds?" extracts `v0=20.0`
(the drop height) instead of `0.0`, because `lower.find("at")` matches inside "Wh**at**".
Produces a wrong verified answer (`-9.43 m/s` instead of the correct value) on one of the
single most common phrasing patterns for this problem type. Fix: word-boundary-anchor the
`"at"` keyword match.

### P0-E — Kinematics extractor never negates `v0` for "thrown downward" despite explicitly listing it as a supported cue
**Source:** [Fence/Physics F1](./MATH_FENCE_PHYSICS_REVIEW_2026-09-06.md#f1--kinematics-extractor-never-negates-v0-for-thrown-downward--thrown-down--launched-downward--three-of-its-own-recognized-cue-phrases--so-a-downward-throw-silently-gets-the-upward-throw-answer) · **Effort:** S

The extractor's own cue list includes "thrown down"/"thrown downward"/"launched downward,"
but nothing in the code negates `v0`'s sign for these cases — a downward throw silently
gets the *upward*-throw answer (reproduced: 4.06s returned for both, correct downward
answer is 1.00s). Zero test coverage exists for any of the three listed downward cues.

### P0-F — `has_verified_math` is an all-or-nothing, message-level gate: one mis-parsed sub-problem disables server-side verification for the entire rest of the turn
**Source:** [Routing/MCP R2](./MATH_ROUTING_PROMPTS_MCP_REVIEW_2026-09-06.md#r2--a-single-mis-parsed-math-sub-problem-verifying-even-incorrectly-disables-the-sympy-tool-for-the-entire-rest-of-the-turn-because-has_verified_math-is-an-all-or-nothing-message-level-gate-rather-than-scoped-to-the-specific-sub-problem-that-was-verified) · **Effort:** M

"graph y=x² and also solve 3x=9" — an ordinary multi-part homework message — gets
mis-parsed by the first-match-wins extractor as a single vertical-line intent (`x=9`,
misreading the coefficient), silently discarding both the actual graph and the actual
equation. Because *some* intent "verified," `has_verified_math=True`, which unconditionally
disables the tool loop (and therefore the model's own SymPy tool) for the **entire turn**
— the model is left to answer everything from unverified reasoning with no signal that
verification silently failed. This is the sharpest gap between the product's stated goal
and its actual behavior.

### P0-G — The "formula emit rule" has zero server-side enforcement: a fabricated geometry/graph diagram ships unmodified whenever no canonical fence of that type exists
**Sources:** [Routing/MCP R3](./MATH_ROUTING_PROMPTS_MCP_REVIEW_2026-09-06.md#r3--the-formula-emit-rule-is-prompt-only-for-model-fabricated-geometrygraph-fences-a-schema-valid-but-entirely-invented-diagram-wrong-numbers-syntactically-correct-json-passes-through-validate_math_fences-completely-unmodified-when-there-is-no-canonical-fence-of-the-same-type-to-substitute) **and** [Fence/Physics F6](./MATH_FENCE_PHYSICS_REVIEW_2026-09-06.md#f6--the-nth-fence-of-a-kind-beyond-the-per-kind-rewrite-cap-is-shipped-to-the-client-with-zero-schema-validation-and-zero-unverified-marker--including-literally-malformed-json--indistinguishable-from-a-verified-fence) (convergent finding — see §3) · **Effort:** S–M

The only guard on a model-emitted geometry/graph fence, when there's no canonical fence of
that exact type, is a **schema shape** check — it verifies the JSON parses and has the
right fields, not that the width/height/area/perimeter values are *true*. A model can
invent `{"type": "rectangle", "width": 47, "height": 13, "area": 999999}` and it ships to
the student byte-for-byte identical to a real solver-verified diagram, with zero visual or
textual distinction. **Two subagents reviewing different layers independently found this
same gap through different triggers** (see §3) — this is the single most important
architectural fix in this entire audit, because it is the one bug that defeats the fence
layer's entire reason for existing.

### P0-H — "Scan Math" silently deletes whatever the student had already typed
**Source:** [Input UX P0-1](./MATH_INPUT_UX_REVIEW_2026-09-06.md#p0-1--scan-math-silently-destroys-unsent-composer-text-data-loss) · **Effort:** S

`handleMathScanCaptured` unconditionally overwrites the composer with the boilerplate scan
prompt — 100% of the time, with no check for existing text, no warning, no undo. This is
not a math-correctness bug, but it is a hard, always-reproducible data-loss bug on one of
the two headline input features, in the exact "type context, then remember to attach a
photo" sequence a real student follows.

### P0-I — Pasting a bare `√9` (the single most common way a student copies a radical) corrupts it into an empty radical plus a stray digit
**Source:** [Input UX P0-2](./MATH_INPUT_UX_REVIEW_2026-09-06.md#p0-2--pasting-9-or-any-bare-n-corrupts-the-expression-instead-of-converting-it) · **Effort:** S

`normalizePastedMath("√9")` → `"$\\sqrt{}9$"`. The paste-normalizer only handles a
parenthesized radical (`√(9)`); the far more common bare form falls through to a rule that
discards the radicand entirely. This string is also what gets sent into the SymPy
verification pipeline as the student's literal input — a "verify √9=3" ask silently
becomes unparseable garbage.

---

## 3. Cross-cutting pattern: two independent reviews converged on the same gap

The [Routing/MCP review](./MATH_ROUTING_PROMPTS_MCP_REVIEW_2026-09-06.md) (reviewing prompt
enforcement) and the [Fence/Physics review](./MATH_FENCE_PHYSICS_REVIEW_2026-09-06.md)
(reviewing the fence-rewrite cap boundary) independently found the **same underlying
design gap** — "a geometry/graph fence with no matching canonical block passes through
`math_fence.py` with schema validation only, no truth check, no unverified marker" — via
two different trigger conditions (R3: no canonical fence of that *type* exists at all; F6:
the *(N+1)th* fence of a kind exceeds the per-kind rewrite cap). Both reports independently
recommend the same fix and both explicitly say to land it as one change, not two patches:
**fail closed (degrade to "Could not render that diagram") on *any* unmatched or
beyond-cap geometry/graph fence**, rather than the current "pass through if schema-valid."
This convergence from two subagents working on different files with no visibility into
each other's work is a strong signal this is the highest-leverage single fix in the audit.

---

## 4. P1 findings — fix soon after launch-blockers

| ID | Finding | Report |
|---|---|---|
| P1-1 | Kinematics height extractor binds an earlier stated mass to `h0` ("A 5 kg block is dropped from a height of 10 m" → uses 5, not 10) — arguably the median physics-homework phrasing | [Intent Extraction M3](./MATH_INTENT_EXTRACTION_REVIEW_2026-09-06.md) |
| P1-2 | No kinematics op checks whether the object already hit the ground before the requested time — "position after 5s" for an object that landed at 2s returns a nonsensical negative height as a flat verified fact | [Fence/Physics F3](./MATH_FENCE_PHYSICS_REVIEW_2026-09-06.md) |
| P1-3 | `work = F·d` has no angle term and no bail-out for "at an angle" phrasing (unlike the force extractor's explicit friction/tension refusal) — "10N at 30° over 5m" confidently returns 50J instead of the correct 43.3J | [Fence/Physics F4](./MATH_FENCE_PHYSICS_REVIEW_2026-09-06.md) |
| P1-4 | On a post-stream SymPy timeout/exception, the fallback only repairs an unclosed graph fence — closed hallucinated fences and missing canonical fences ship un-repaired, breaking the "client always gets a diagram/answer pill" promise | [Fence/Physics F5](./MATH_FENCE_PHYSICS_REVIEW_2026-09-06.md) |
| P1-5 | Comma-decimal locale input ("3,5 by 2 cm") is misparsed into two separate numbers, producing a wrong verified area — not a missed extraction, a *wrong* one | [Intent Extraction N2](./MATH_INTENT_EXTRACTION_REVIEW_2026-09-06.md) |
| P1-6 | Any three numbers in a sentence summing to ~180 that also mentions "triangle" trigger a fabricated angle-based geometry answer, even for a sentence about a sign's cost/materials | [Intent Extraction M4](./MATH_INTENT_EXTRACTION_REVIEW_2026-09-06.md) |
| P1-7 | "mode" matches as a substring of "model" — "the model 100 scored 20 points higher than the model 80" triggers a fabricated statistics block | [Intent Extraction M5](./MATH_INTENT_EXTRACTION_REVIEW_2026-09-06.md) |
| P1-8 | `_verified_math_stays_fast()`'s trivial-arithmetic check is substring-anywhere, not whole-message — a hard non-math question sharing a message with "what is 9*7" silently gets routed to the fast/weak model for its non-math half too | [Routing/MCP R1](./MATH_ROUTING_PROMPTS_MCP_REVIEW_2026-09-06.md) |
| P1-9 | No bound on computational *shape* (only expression character length) — `x^40=1`, an ordinary precalc roots-of-unity problem, reliably exceeds the 5s timeout and ties up the single-worker SymPy pool for every concurrent user | [SymPy Core M2](./MATH_SYMPY_CORE_REVIEW_2026-09-06.md) |
| P1-10 | The per-message crash boundary (`MarkdownErrorBoundary`) has no second line of defense — if the fallback renderer itself throws, the crash escapes to the whole-screen route-level boundary instead of staying scoped to one message | [Mobile Rendering M1](./MATH_MOBILE_RENDERING_REVIEW_2026-09-06.md) |
| P1-11 | Camera-scan photo → SymPy pipeline has no confirm/edit step — the vision extraction's read is never shown to the student before being spent as a verified turn; a misread digit becomes a confidently "verified" wrong answer | [Input UX P1-1](./MATH_INPUT_UX_REVIEW_2026-09-06.md) |
| P1-12 | Permanently-denied camera permission is a dead end — no `canAskAgain`/`Linking.openSettings()` fallback, so "Allow camera" silently does nothing once denied twice | [Input UX P1-2](./MATH_INPUT_UX_REVIEW_2026-09-06.md) |

---

## 5. P2/P3 — lower priority, full detail in source reports

- **Fence/Physics:** canonical-fence self-validation before substitution is missing (currently unreachable, defense-in-depth only); `solve_force` raises a raw `ZeroDivisionError` instead of the domain error type for zero mass.
- **Intent Extraction:** `"5C2"`-style alphanumeric codes (dorm rooms, product SKUs) read as combinatorics by design (tested, product tradeoff, not a bug); circle extractor shadows an explicit later graph request in a compound message; prose-wrapped "solve for X" equations extract the full sentence as `lhs` but fail safe; inverse-phrasing word problems ("rectangle has area 24, length 6, find width") aren't extracted at all (safe miss, not wrong); `needs_symbolic_math`'s cold-start pays ~1.3s importing the LiteLLM gateway on the first call per fresh worker.
- **Routing/MCP:** camera-math turns whose extracted kind isn't equation/system/inequality (most geometry/stats/graph homework photos) miss the richer math prompt hints, though the baseline safety hint still applies; the backtick-around-`$...$` rule has no server-side enforcement (fully mitigated client-side today, but a future web client wouldn't inherit that fix).
- **Mobile Rendering:** the documented "eager cut reduces math flicker" streaming fix has a reproducible gap — a closed math block followed by an in-progress next paragraph (no blank line yet) stays un-memoized and re-parses/remounts its WebView on every ~32ms flush tick for the length of that paragraph; unbalanced LaTeX braces render garbled-but-stable (expected, not a regression risk); `FunctionGraphBlock`'s chart width has no defensive floor (not reachable on any real device today).
- **SymPy Core:** `sample_function` throws an uncaught `TypeError` on any expression SymPy auto-simplifies to a constant (`0/x`, `x-x`) — contained everywhere it's reachable today, but the containment is accidental in the MCP tool path and produces a misleading "timed out" error; magnitude-1 imaginary roots render with a redundant explicit "1" (`x = ± 1 i` instead of `x = ± i`), cosmetic only.
- **Input UX:** the proactive math-keyboard discoverability chip misses the most common way students actually type a question ("what is 7 x 8") while also false-firing on any bare currency mention ("can I borrow $20"); the 20-second vision-extraction wait reuses generic "calculating" copy instead of a scan-specific "reading your photo" message; no post-capture photo preview before it's attached and sent.

---

## 6. What's solid — verified, not to be touched

Every reviewer was instructed to actually execute code and hand-verify correctness, not
just read and assume. The following held up under direct adversarial testing across all
six reports and should not be "fixed" as part of addressing the findings above:

- **RCE sandbox** (`math_service/parse.py`'s `_reject_unsafe_expr`) — re-verified fresh
  against dunder-chain, `__import__`, `getattr`, semicolon-injection, and f-string-shaped
  payloads by two independent reviewers; still fully closed.
- **SymPy subprocess executor's cancellation-safety and cross-request isolation** —
  verified by direct kill-and-respawn and concurrent-request reproduction, not just read;
  no cross-user contamination possible.
- **Canonical-fence/canonical-answer pairing cannot drift apart by construction** — both
  values are always built from the same solve result inside one function call.
- **Geometry Pydantic validation** (triangle inequality, positive dimensions, sector angle
  bounds, dimension caps) — rejects every degenerate input tried.
- **No-solution / infinite-solution / extraneous-root classification** — hand-verified
  correct against the classic traps (`sqrt(x)=-1`, removable poles, identities).
- **Inequality sign-flip on division by a negative, compound inequalities** — correct.
- **Projectile range/height, F=ma, KE, PE formulas** (when correctly extracted) — matched
  hand calculation exactly for every input tried.
- **Float-precision containment** — the raw, noisy SymPy result string is never
  user-facing; only the clean `.latex` field is ever surfaced.
- **Mobile parsers are all total** — no input found (malformed JSON, unbalanced braces,
  `NaN`/`Infinity`, 20-level nesting) that throws instead of degrading gracefully; the
  documented "crash fallback still draws SVG, not raw JSON" claim is true and verified.
- **Streaming stable-prefix scanner is provably correct** for append-only content, tested
  byte-by-byte against a one-shot reference render.
- **WebView/CSP** — fresh adversarial LaTeX (`</script>` injection, template-literal
  breakout, `\href{javascript:...}`) all correctly blocked by existing KaTeX `trust:false`
  and HTML-escaping.
- **Expo Go math rendering** is genuinely honest — `@expo/dom-webview` gives Expo Go the
  real KaTeX/MathJax WebView too, not just a degraded fallback.
- **Math keyboard template/slot logic** (`mathDraftSlots.ts`) — stateless-by-construction
  design (slots derived fresh from text every keystroke) means there is no separate model
  to desync, nest incorrectly, or lose state on backgrounding.
- **Unit converter** — exact SI conversion factors, verified against known values (miles,
  °F/°C, kg/lb) directly.
- **No double-computation race** between the pre-stream heuristic and tool-loop SymPy
  paths — traced precisely; they are mutually exclusive by construction (a real bug exists
  here, P0-F above, but it is not a race/inconsistency bug).
- **`calculating` status timing** is consistent across both the heuristic and tool-loop
  paths — always fires before computation starts, no "sometimes no indicator" gap.
- **The legacy MCP pre-stream round explicitly refuses to touch math**, avoiding
  double-injection of a verified block — by design and tested.

---

## 7. Sequenced fix plan

One concern per PR, matching this codebase's execution discipline. Grouped by dependency,
not strictly by severity — items in the same numbered step have no ordering constraint
between each other.

1. **Fail closed on any unmatched or beyond-cap geometry/graph fence** (P0-G, the
   convergent R3/F6 finding) — highest-leverage single fix; closes the one gap that most
   directly undermines the fence layer's purpose.
2. **Fix the two calculus/prose-sympify bugs together** (P0-A, P0-B) — same root cause
   (untranslated English reaching `sympify`), two entry points, one translate-or-reject
   fix.
3. **Fix the three kinematics extractor bugs together** (P0-D "at" substring, P0-E
   downward-throw sign, P1-1 mass-vs-height binding) — same file, same extractor, same
   `_find_value_with_unit`/`_find_value_with_specific_unit` pattern already used correctly
   elsewhere in the file for the fix.
4. **Fix `e`/`E` variable disambiguation** (P0-C) — isolated, `guess_variables`/
   `_requested_variable` only.
5. **Fix `has_verified_math` gate granularity** (P0-F) — needs a short design note first
   (detect multi-intent messages, or gate on matched-span coverage) before implementation;
   budget more time than the other P0s.
6. **Fix the two math-input data-loss/corruption bugs** (P0-H composer-wipe, P0-I bare-√
   paste) — independent, both small, both mobile-only.
7. **P1 batch — physics correctness** (P1-2 past-impact, P1-3 work-angle) — same file as
   step 3, can ride along.
8. **P1 batch — fence-timeout fallback scope** (P1-4) — pairs naturally with step 1's fix.
9. **P1 batch — extraction false-positive fixes** (P1-5 comma-decimal, P1-6 triangle-angle,
   P1-7 mode-substring) — three independent word-boundary/anchoring fixes, same file
   family.
10. **P1 batch — routing/UX polish** (P1-8 routing scope, P1-9 pool sizing/degree bound,
    P1-10 crash-boundary depth, P1-11 scan confirm step, P1-12 permission dead-end) —
    independent, can be parallelized across owners.
11. Everything in §5 (P2/P3) — opportunistic, not launch-blocking.

---

## 8. Explicit non-goals of this audit

- No source code was modified by any of the six subagents; this is a pure, read-only audit.
  Any scratch test files created to reproduce a finding were run and then deleted (verified
  via `git status` in each sub-report).
- Non-English locale phrasing was not systematically tested (one locale bug, P1-5, was found
  incidentally, not via a systematic sweep) — a full i18n math-correctness pass is a
  separate exercise.
- Accessibility (screen-reader labels, contrast) was not audited for the math-specific UI.
- On-device/simulator verification (actual WebView remount visual behavior, actual camera
  hardware behavior) was not performed — all claims are either pure-function-level
  reproductions or, where device behavior is asserted, explicitly labeled as resting on
  documented platform semantics rather than a live device test.
- Curriculum coverage breadth (which topics are verified vs. LLM-only) was not re-litigated
  — `docs/math.md`'s own coverage table is taken as the accurate, current statement of
  product scope; this audit is about whether what's covered is covered *correctly*.
- Load/concurrency testing of the SymPy subprocess pool under real production traffic was
  not performed (single-process reproduction only).
