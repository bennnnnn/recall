# Recall — Pre-Stream Math Intent Detection & Extraction Review (Sep 2026)

Scope: the "is this math, and what kind" gate that runs on every chat turn before the
model streams — `needs_symbolic_math()` (`math_text_match/needs.py` + its
`scan.py`/`calculus.py`/`geometry.py`/`graph.py`/`discrete.py` helpers) and the ordered
`MathIntent` extraction pipeline it feeds (`math_tools/extract.py`'s
`_INTENT_EXTRACTORS`, and every extractor module under `math_tools/extractors/` plus
`math_tools/school.py` and `math_tools/physics.py`). The core SymPy solvers
(`math_service/`) and the block-rendering layer (`math_tools/block/*.py`) are treated as
correct/out-of-scope except for the trust-boundary check in §C4 — this review is about
whether **natural-language text gets mapped to the right `MathIntent` with the right
parameters**, because a wrong mapping is presented to the student with exactly the same
"SymPy-verified, do not recompute" confidence as a correct one.

Reviewed at `cursor/cross-domain-review-2026-09-05`. Read-only: no source files were
modified. Every claim below was run against `apps/api/.venv/bin/python`, not inferred
from reading code; scripts and raw output are inlined.

---

## A. Verdict

**The gate/extractor architecture is sound and its test suite is real** — 344/344 tests
pass across `test_math_tools.py`, `test_math_text_match.py`, `test_math_school.py`, and
`test_math_school_units.py` (§B). The "first extractor to match wins, no cross-check"
design is a real, acknowledged risk (`extract.py`'s own `_extract_system_intent` has a
comment calling out "the most severe correctness bug found in the audit" from a *prior*
review — systems of equations silently collapsing to a single-equation answer — which is
now fixed). Several classes of adversarial input the team clearly already fought hard
against (bare shape words, unitless dimensions, prose containing an `=`) are correctly
rejected. This is not a naive regex grab-bag; it is a heavily hardened heuristic layer
with real scar tissue from past incidents.

**But three confirmed, reproducible misclassification bugs meet the P0/P1 bar set for
this review**, and all three produce the single worst outcome this feature can produce:
a `VerifiedMathBlock` telling the model *"Do NOT recompute — use this exact result"*
for a number that has nothing to do with the student's problem.

1. **P0 — Calculus/limit/series extractors feed raw, un-parsed English words straight
   into SymPy's implicit-multiplication parser.** "What's the derivative of x squared
   plus 3x" is extracted as `expr='of x squared plus 3x'` and handed to
   `math_service.differentiate`, which treats every letter as its own symbol (and
   silently resolves `e` to Euler's number, `2.718...`) and returns
   `16.3096909707543 a d f l o p q r s^{2} u^{2} x` as a **verified, do-not-recompute
   answer** (§C1, reproduced below with exact output). This is the single most severe
   finding in this review: it fires on *any* spelled-out calculus phrase containing a
   letter run — "expand", "simplify", and "factor" share the same code path and are
   equally exposed.
2. **P0 — the same un-parsed-English path exists for `"roots of X"` / `"zeros of X"`
   prose that isn't math at all.** "the roots of my hair are 2 inches long" is rewritten
   to `solve my hair are 2 inches long = 0` by a regex in `extract.py`, gated into SymPy
   by `needs.py`'s `"roots of" in lower and any digit` check, and produces a **verified**
   `a = 0.0` — with the model instructed to show "worked steps" copying the (meaningless)
   isolate/take-square-root steps verbatim (§C1).
3. **P1 — the kinematics height extractor silently binds an unrelated quantity (mass)
   to the wrong physics variable (height) when it appears earlier in the sentence than
   the actual height.** "A 5 kg block is dropped from a height of 10 m" is extracted as
   `h0=5.0` (unit `"kg"`, silently ignored) instead of `h0=10.0`, because
   `_find_value_with_unit`'s "look up to 40 chars before the keyword" fallback finds the
   mass before it finds the height (§C2). This is arguably the single most common real
   physics-homework phrasing pattern (mass stated before height/velocity), so this isn't
   a narrow edge case — it's close to the median case for this problem type.

Two more confirmed misclassifications (triangle-angle false positive on unrelated
triple-of-numbers-summing-to-180 prose, and the "mode" substring statistics false
positive) are **P1** — they fire on plausible everyday sentences with no math intent and
produce a fully-formed, wrong "verified" numeric answer, but the trigger phrasing is more
contrived than the calculus/physics bugs above. Combinatorics on alphanumeric codes
("5C2") is a **P2 product-alignment issue, not a bug** — it is explicitly unit-tested as
intended behavior, but the reviewer flags it because the failure mode (misreading a dorm
room number, a product SKU, a flight seat) is a real false-positive surface a math-verify
feature shouldn't have.

Every other adversarial input tried — locale/unit edge cases, "false negative" homework
phrasing, extractor-ordering shadow candidates, and a `needs_symbolic_math` performance/
ReDoS stress test — either behaved safely (fell through to the honest "unverified, do not
claim SymPy" note) or did not reproduce at all. Full battery in §C and §E.

---

## B. What's working (verified, don't "fix" these)

- **The existing test suite is real and green.**

  ```
  $ cd apps/api && .venv/bin/python -m pytest app/tests/services/test_math_tools.py \
      app/tests/services/test_math_text_match.py app/tests/services/test_math_school.py \
      app/tests/services/test_math_school_units.py -q
  ........................................................................ [ 20%]
  ........................................................................ [ 41%]
  ........................................................................ [ 62%]
  ........................................................................ [ 83%]
  ........................................................                 [100%]
  344 passed in 16.06s
  ```

- **Word-problem numeric extraction correctly ignores decoy numbers when the pattern is
  the one it was built for.** "a triangle with base 5 and height 3, cost $20 per square
  meter, what is the area" correctly extracts `base=5.0, height=3.0` (not `$20`) and
  returns a correct verified area of `7.5`:

  ```python
  >>> extract_math_intent("a triangle with base 5 and height 3, cost $20 per square meter, what is the area")
  kind='triangle' base=5.0 height=3.0 wants_angle=True
  >>> _build_verified_block(intent, settings).text
  "Triangle: base=5 cm height=3 cm area=7.5 cm²\nDo NOT recompute area. ..."
  ```

  Keyword-anchored `number_after(text, "base")` / `number_after(text, "height")`
  extraction (`scan.py`) is doing its job here — it is specifically the *unit-specific,
  keyword-anchored* extractors (triangle base/height, force `_find_value_with_specific_unit`
  with `unit_pattern` restricted to that quantity's units) that hold up under adversarial
  testing. The bugs found in §C are concentrated in the *looser* extractors
  (kinematics' generic `_find_value_with_unit`, and the un-parsed-prose calculus path).

- **Real false positives are correctly rejected.** All three of "I got 100% on my last 3
  tests", "my phone number is 555-1234, call me", and "chapter 7, problem 12: solve for
  x" return `needs_symbolic() == False` — confirmed by direct call, not inferred:

  ```
  'I got 100% on my last 3 tests'                    needs_symbolic: False
  'my phone number is 555-1234, call me'              needs_symbolic: False
  'chapter 7, problem 12: solve for x'                needs_symbolic: False
  ```

  Note the third case: it contains the literal string `"solve for x"`, which is exactly
  the phrase `_SOLVE_FOR_VAR_RE` looks for elsewhere in the pipeline — it's correctly
  rejected only because `needs.py`'s gate requires `has_equation(cleaned)` and there is no
  `=` in the text. This is a real, working guard, not an accident — but it means the
  safety margin here is exactly one missing character; see §C5 for why this doesn't
  currently extend to a ReDoS concern.

- **`needs.py`'s own comments document three now-fixed false-positive incidents** (bare
  shape words inventing dimensions, `"sector"` matching "the tech sector", bare `x>4`
  needing a math keyword it didn't have) — read as evidence the team is actively hunting
  this exact bug class, not first-time-discovered issues.

- **The canonical-answer trust boundary is clean.** Every block builder in
  `math_tools/block/*.py` delegates the actual computation to `math_service`:

  ```
  $ rg 'math_service\.\w+\(' apps/api/app/services/math_tools/block/algebra.py
  33:    result = math_service.solve_equation(eq)
  62:    result = math_service.solve_compound_inequality(...)
  71:    result = math_service.solve_inequality(...)
  92:    line_spec = math_service.number_line_spec_from_expr(...)
  120:   sys_result = math_service.solve_system(sys_input)
  142:   newton_result = math_service.newton_method(newton_input)
  ```

  Grepping all of `math_tools/block/` for inline arithmetic (`+`/`-`/`*`/`/` outside a
  `math_service.*()` call) turns up only prompt-text strings ("area = (top + bottom) / 2
  \times height" is an instruction to the *model*, not a computation) and one legitimate
  input-normalization case in the *extractor* layer (`geometry_graph.py:133`:
  `radius=diameter / 2` — converting a diameter measurement into the radius parameter
  `math_service`'s circle solver expects, before any answer is computed). There is no
  second place a math bug can hide in this layer.

- **`needs_symbolic_math` has no ReDoS surface.** See §C5 — a stress battery of six
  pathological inputs up to 15,000 characters (repeated `=`, nested parens, repeated
  digits/commas) all returned in well under 1ms, and the 1000-character `prepare()` cap
  (`scan.py:9`) means anything longer never reaches a single regex in this module at all.

---

## C. Findings — ranked

### Misclassification — confidently-wrong verified answers

#### M1 — Calculus/limit/series extractors sympify raw English prose, producing a nonsense "verified" symbolic result

**Severity:** P0 · **Area:** math_tools/extractors/calculus.py, math_text_match/calculus.py · **Effort:** M

**Evidence:**

```python
# math_tools/extractors/calculus.py:16-45
def _extract_calculus_intent(cleaned: str) -> MathIntent | None:
    op_word = mtm.calc_op(cleaned)
    ...
    tail = _calc_expr_tail(cleaned)
    expr = _strip_trailing_filler(tail) if tail is not None else cleaned
    ...
    return MathIntent(kind="calculus", expr=expr, operation=calc_op, ...)
```

`_calc_expr_tail` / `_strip_trailing_filler` (`math_tools/helpers.py`) do lightweight
string trimming — they strip leading filler words and trailing punctuation, but they do
**not** translate English math vocabulary ("squared", "plus", "times") into operators.
Reproduced directly against the real extractor and the real `math_service` solver (not
a mock):

```
$ .venv/bin/python - <<'EOF'
from app.services.math_tools.extract import extract_math_intent
from app.services.math_tools.block import _build_verified_block
from app.core.config import Settings

intent = extract_math_intent("what's the derivative of x squared plus 3x")
print(intent.expr, intent.operation)
# -> 'of x squared plus 3x' differentiate

block = _build_verified_block(intent, Settings())
print(block.text)
EOF

of x squared plus 3x differentiate
Symbolic math results (verified by SymPy — use these exact values in your answer):
Constant multiple: $\frac{d}{dx}\left[8.15484548537714 a d f l o p q r s^{2} u^{2} x^{2}\right] = 8.15484548537714 a d f l o p q r s^{2} u^{2} \cdot \frac{d}{dx}\left[x^{2}\right] = 16.3096909707543 a d f l o p q r s^{2} u^{2} x$
Result: $\frac{d}{dx}\left[8.15484548537714 a d f l o p q r s^{2} u^{2} x^{2}\right] = 16.3096909707543 a d f l o p q r s^{2} u^{2} x$
Do NOT recompute. Explain in plain language with $...$ for formulas. Do NOT emit ```answer, ```graph, or ```geometry fences — Recall attaches the verified result after your answer.
Verified result: 16.3096909707543 a d f l o p q r s^{2} u^{2} x
```

Mechanism: `math_service/parse.py`'s `_LOCALS` maps `"e": math.e` for legitimate
Euler's-number support, and SymPy's parser applies implicit multiplication between
adjacent symbols with no operator. `"of x squared plus 3x"` sympifies as the product of
the single-letter symbols `o`, `f`, `x`, `s`, `q`, `u`, `a`, `r`, `e`(→2.718…), `d`,
`p`, `l`, `u`, `s`, `3`, `x` — literally every letter in "of", "squared", "plus" becomes
its own free variable, multiplied together, with the one letter that happens to be
`"e"` silently contributing a transcendental constant instead of erroring. The
`differentiate` "worked step" text is completely fabricated correctness theater: it *is*
a real derivative of a real (nonsense) expression, so it passes any internal
"did SymPy solve without raising" check.

This is not narrow to one phrasing — every calculus cue word in
`math_text_match/calculus.py`'s `calc_op()` (simplify/differentiate/derivative/
integrate/integral/factor/expand) shares this same `_extract_calculus_intent` code path,
and `_extract_limit_intent` / `_extract_series_intent` share the same pattern via
`_normalize_latex_expr` (which handles LaTeX `\frac`/`\sqrt` but not English words).
Confirmed the same failure class on limits:

```
mtm.parse_limit("find the limit as x approaches 2 of x squared plus one")
```

returns a `LimitHit` whose `.expr` is the untranslated English tail, which
`_extract_limit_intent` passes straight to sympify after only `^`→`**` substitution.

**Why it matters:** this is exactly the scenario the task brief calls the most
safety-critical outcome in the whole feature — a "verified, do NOT recompute" block for
a completely different problem than the one the student asked, indistinguishable in
formatting/confidence from a correct one. It fires on the single most natural way a
student types a calculus question ("what's the derivative of X" in plain English,
not LaTeX or `d/dx` notation) — this is not a rare adversarial trigger, it is close to
the median phrasing for this problem type.

**Recommended fix:** before this ships as "verified," `_calc_expr_tail`'s output needs
either (a) a dedicated English-math-phrase→SymPy-expression translator (a bounded
dictionary substitution: "squared"→"**2", "cubed"→"**3", "plus"→"+", "minus"→"-",
"times"/"multiplied by"→"*", "divided by"→"/", run *before* sympify, not left to
SymPy's parser) or (b) a hard rejection: if the candidate expression, after stripping
digits/operators/known single-letter variables, still contains multi-letter English
words that aren't LaTeX macros, treat it as an extraction failure and fall through to
`_unverified_math_note` rather than risk-sympifying prose. (b) is the smaller, safer
change and matches the existing "fail safe, don't claim verification" pattern already
used elsewhere in this file (`if not expr: return None`). Whichever is chosen, add a
regression test asserting that `"derivative of x squared plus 3x"` extracts to
`x**2 + 3*x` (or is rejected), not a 6-letter-symbol product.

**Do not:** patch this by adding `"of"`, `"plus"`, `"squared"` etc. to `_LOCALS` or
special-casing them as removed stopwords in `_strip_trailing_filler` — that treats
symptoms word-by-word and will always be one phrasing behind (e.g. "cubed", "over",
"to the power of"). The fix belongs before sympify, as an explicit translate-or-reject
step, not as an ever-growing stopword blocklist.

---

#### M2 — "roots of X" / "zeros of X" prose rewrite feeds non-math English into the same un-parsed sympify path

**Severity:** P0 · **Area:** math_tools/extract.py, math_text_match/needs.py · **Effort:** S

**Evidence:**

```python
# math_tools/extract.py:35, 44-48
_ROOTS_RE = re.compile(r"\b(?:find(?:\s+the)?\s+)?(?:roots|zeros)\s+of\s+(.+)", re.IGNORECASE)
...
roots_match = _ROOTS_RE.search(cleaned)
if roots_match:
    tail = roots_match.group(1).strip()
    if "=" not in tail and any(c.isdigit() for c in tail):
        cleaned = f"solve {tail} = 0"
```

Gated into the pipeline by `needs.py:199`: `("roots of" in lower or "zeros of" in lower)
and any(ch.isdigit() for ch in cleaned)` — the *only* guard is "the text contains the
phrase and at least one digit anywhere in the whole message", not that the phrase's
object looks like an expression.

```
$ .venv/bin/python - <<'EOF'
from app.services import math_text_match as mtm
from app.services.math_tools.extract import extract_math_intent
from app.services.math_tools.block import _build_verified_block
from app.core.config import Settings

t = "roots of my hair are 2 inches long"
print("needs_symbolic:", mtm.needs_symbolic(t))
intent = extract_math_intent(t)
print(intent.lhs, "=", intent.rhs)
print(_build_verified_block(intent, Settings()).text)
EOF

needs_symbolic: True
my hair are 2 inches long = 0
Symbolic math results (verified by SymPy — use these exact values in your answer):
Equation: 14.7781121978613 a^{2} c g h^{2} i^{2} l m n^{2} o r^{2} s y = 0
Isolate: a^{2} = 0
Take square root: a = \pm 0
Solutions: a = 0.0
Formula shape: ... Do NOT recompute the solutions. Show worked steps by COPYING the
verified steps above verbatim ...
Verified result: a = 0.0
```

Same finding replicated with "the zeros of my patience are at an all time low, i have 2
kids" → rewritten to `solve i have 2 kids = 0` → also produces a fully-formed verified
solve block.

**Why it matters:** same class as M1 — a completely unrelated, non-mathematical sentence
produces a formatted, "do not recompute" numeric answer. The trigger phrase ("roots of
my ...", "zeros of my ...") is a common English idiom pattern ("get to the root of the
problem", "roots of my anxiety", "zeros" is rarer but "root cause", "root of the issue"
are everyday phrasing), and the only gate is "contains a digit somewhere in the message"
— a student could easily have an unrelated number anywhere else in the same message
(a date, a page number, an unrelated homework number) and trip this.

**Recommended fix:** tighten both the `needs.py` gate and the `_ROOTS_RE` rewrite to
require the *captured tail* (not "anywhere in the message") to look like an algebraic
expression — e.g. require it to consist predominantly of digits/operators/single-letter
variables (the same character-class check already proposed for M1's rejection path would
directly cover this, since `"my hair are 2 inches long"` is exactly the kind of
multi-word-English-with-an-embedded-number the check needs to reject). This can share
the fix with M1 — both bugs are the same root cause (untranslated English handed to
sympify) hitting two different entry points (`_extract_calculus_intent` and the
`_ROOTS_RE` rewrite in `extract.py`).

**Do not:** fix this by requiring "roots of" to be followed immediately by a bare
expression with no filler words — real math phrasing legitimately includes filler
("find the roots of the polynomial x^2 - 4"); the fix needs to validate the *content*,
not the syntax around it.

---

#### M3 — Kinematics height extraction binds an earlier unrelated quantity (mass) to `h0` when it precedes the actual height

**Severity:** P1 · **Area:** math_tools/physics.py · **Effort:** S

**Evidence:**

```python
# math_tools/physics.py:188-193
hu = _find_value_with_unit(
    cleaned,
    ("from", "initial height", "height of", "high", "above", "cliff"),
)
if hu is not None:
    h0, h0_unit = hu
```

```python
# math_tools/physics.py:40-66
def _find_value_with_unit(text, keywords):
    for kw in keywords:
        idx = lower.find(kw)
        ...
        after = text[idx + len(kw): idx + len(kw) + 40]
        m = _VALUE_UNIT_RE.match(after.strip())   # requires number to start immediately
        if m: ...
        before = text[max(0, idx - 40): idx]
        m = _VALUE_UNIT_RE.search(before)          # searches ANY number+unit in the 40 chars before
        if m: ...
```

`"from"` is checked first (it's first in the keyword tuple) and is the loosest possible
keyword — it matches the "dropped **from**" clause of the sentence even when the actual
height is stated later via "height of". Because `_VALUE_UNIT_RE.match(after.strip())`
requires the number to start *immediately* after the keyword (no intervening words), the
common phrasing "dropped from **a height of** 10 m" fails that immediate match (there's
"a height of" between "from" and "10"), so the code falls through to the `before`-window
search — which finds "5 kg" (stated earlier in the sentence, before "dropped from") and
silently accepts it as the height:

```
$ .venv/bin/python - <<'EOF'
from app.services.math_tools.physics import _extract_kinematics_intent
t = "A 5 kg block is dropped from a height of 10 m. How long until it hits the ground?"
print(_extract_kinematics_intent(t))
EOF
physics_params={'g': 9.81, 'h0': 5.0, 'v0': 0.0}
physics_units={'g': 'm/s^2', 'h0': 'kg', 'v0': 'm/s'}
```

`h0=5.0` (the mass, unit incorrectly recorded as `"kg"` too) instead of `h0=10.0`. Control
cases confirm the extractor works correctly once the confounding "before" quantity is
removed:

```
"A ball is dropped from a height of 10 m..."        -> h0=10.0, unit='m'   (correct)
"A 5 kg ball is dropped from 20m..."                 -> h0=20.0, unit='m'  (correct — no "height of" filler this time)
```

The bug is specifically the combination of (1) a mass or other quantity stated *before*
the kinematics cue, and (2) "height **of**" (or similarly-filler-worded) phrasing after
it that defeats the immediate-match "after" search.

**Why it matters:** "an N kg object/block/ball is dropped from a height of H m" is
close to the single most common way this exact problem type is phrased in a physics
textbook — mass is conventionally stated first because it's the "given" that sets up the
scenario, height follows as the specific quantity for this sub-question. The resulting
answer (time to fall 5m vs. 10m) is a different number with the same "verified, do not
recompute" framing, so the student has no way to tell it's wrong.

**Recommended fix:** compare the physics extractors already in this same file —
`_extract_force_intent` and `_extract_energy_intent` both use
`_find_value_with_specific_unit(text, unit_pattern, keywords)`, which restricts the
*unit* pattern (only mass units for mass, only force units for force) rather than
searching an open 40-character window for any number+any-unit near a loose keyword like
"from". Port `_extract_kinematics_intent`'s height search to the same
`_find_value_with_specific_unit` pattern, restricting to length units
(`km|cm|mm|m|mi|ft|yd|in`) so a `kg`-suffixed number can never satisfy it, exactly as
`_extract_energy_intent`'s own height search already does at line 458-464 of this same
file. This is a small, local, already-precedented change — the correct pattern exists
three functions below the buggy one.

**Do not:** fix this by reordering the keyword tuple (e.g. moving "height of" before
"from") — that only fixes this one sentence shape; "from" needs to stay as a fallback
for "dropped from 20m" (no "height of" wording at all), and any keyword-order fix leaves
the same open-unit-window bug reachable from a different sentence shape (e.g. "A 5 kg,
10 m/s ball falls from 20m" could just as easily bind the velocity to height under a
reordered-but-still-unit-unrestricted search). Restrict the *unit*, not the keyword
order.

---

### Misclassification — narrow but confirmed

#### M4 — Any three numbers summing to ~180 in a triangle-adjacent-but-unrelated sentence trigger a verified equilateral-triangle answer

**Severity:** P1 · **Area:** math_text_match/geometry.py (`triangle_angles_signal`) · **Effort:** S

**Evidence:**

```
$ .venv/bin/python - <<'EOF'
from app.services import math_text_match as mtm
from app.services.math_tools.extract import extract_math_intent
from app.services.math_tools.block import _build_verified_block
from app.core.config import Settings

t = "A triangle-shaped sign costs $60, needs 60 screws, and covers 60 square feet."
print("needs_symbolic:", mtm.needs_symbolic(t))
intent = extract_math_intent(t)
print(intent.kind)
print(_build_verified_block(intent, Settings()).text[:200])
EOF

needs_symbolic: True
triangle_sides
Symbolic math results (verified by SymPy — use these exact values in your answer):
Triangle: a=1 units b=1 units c=1 units area=0.433 units² perimeter=3 units angles=60°/60°/60°
The user gave interior angles only. Sides are relative (law of sines) ...
```

`triangle_angles_signal` (`math_text_match/geometry.py`) matches any three numbers in
`(0, 180)` in the text that sum to ~180, with no requirement that those numbers be
labeled as angles, or even be near the word "angle" — here `$60` (a price), `60` (a
screw count), and `60` (a square-footage) are read as three 60° interior angles purely
because they happen to sum to 180 and the sentence contains the word "triangle".

**Why it matters:** this is a real everyday-language false positive — a word problem
about a triangular sign's cost/materials, not its angles, is answered with a fabricated
angle-derived geometry result. The specific trigger (three numbers 0–180 summing to 180,
in a sentence that happens to mention "triangle") is more contrived than M1–M3 but is
not exotic — three quantities in a word problem summing to a round number is not rare.

**Recommended fix:** require `triangle_angles_signal` to bind each of its three numbers
to the word "angle"/"degrees"/"°" in proximity (the same anchoring pattern
`number_after`/`two_numbers_after` already use elsewhere in this module), not a bare
"any 3 numbers in the sentence sum to 180" scan.

**Do not:** raise the qualifying digit count only, or add price ("$") stripping as a
special case — that just narrows this one reproduction without fixing the underlying
unanchored heuristic; any other unrelated triple summing to 180 (percentages, page
counts, ages) reproduces the same bug.

---

#### M5 — "mode" as a substring of an unrelated word (model/moderate/modem) plus two numbers triggers a fabricated statistics block

**Severity:** P1 · **Area:** math_text_match/discrete.py (`stats_signal`) · **Effort:** S

**Evidence:**

```
$ .venv/bin/python - <<'EOF'
from app.services import math_text_match as mtm
from app.services.math_tools.extract import extract_math_intent
from app.services.math_tools.block import _build_verified_block
from app.core.config import Settings

t = "The model 100 scored 20 points higher than the model 80 in testing."
print("needs_symbolic:", mtm.needs_symbolic(t))
intent = extract_math_intent(t)
print(intent.kind)
print(_build_verified_block(intent, Settings()).text[:250])
EOF

needs_symbolic: True
statistics
Data (3 values): 100, 20, 80
mean=66.6667 median=80 mode=none range=80 population variance=1155.56 population stdev=33.9935 sample stdev=41.6333
Do NOT recompute any of these values — use the verified numbers above. ...
```

A sentence about comparing two ML/product models ("model 100" vs. "model 80") — with no
statistical intent at all — is read as a `mean`/`median`/`mode`/`variance` request over
the three loose numbers `100, 20, 80` because "model" contains "mode" as a substring.

**Why it matters:** same class as M4 — a common, benign sentence pattern (comparing two
named/numbered things: "model 80", "iPhone 15", "Room 204", "chapter 12") that happens to
contain a few numbers is misread as a request for statistics on those numbers, with full
"verified" framing.

**Recommended fix:** anchor `stats_signal`'s "mode" cue on a word boundary (`\bmode\b`)
rather than substring containment, and require it (or "mean"/"median"/"average") to be
followed by a data-list pattern (numbers separated by commas/"and", not scattered
arbitrarily through unrelated prose) before treating scattered numbers as a dataset.

**Do not:** solve this by blocklisting the specific words "model"/"moderate"/"modem" —
that is an ever-growing whack-a-mole list; word-boundary matching is the general fix.

---

### Product-alignment (not a bug — behavior is intentional and tested)

#### M6 — Alphanumeric codes ("5C2") are read as combinatorics notation by design

**Severity:** P2 · **Area:** math_text_match/discrete.py (`_ncr_npr_signal`) · **Effort:** — (documented, not recommended to change without a product call)

**Evidence:** `test_math_text_match.py`'s `TestCombinatoricsSignal` explicitly
parametrizes `("5C2", "combinations")` and `("5P2", "permutations")` as expected-pass
cases — this is intended behavior (support for compact "nCr"/"nPr" homework notation),
confirmed by re-running the suite (§B) and by direct call:

```
"My dorm room is 5C2 this semester, is it a good room?"
  needs_symbolic: True  intent.kind: combinatorics
  C(5,2) = 5! / (2! \times (5-2)!) = 10
```

**Why it matters:** flagging this per the review brief's instruction to check false
positives on superficially-math-looking text — a dorm room number, product SKU, or
flight seat assignment matching the `\dC\d` / `\dP\d` shape is misread as a combinatorics
problem. This is a real, reproducible false-positive surface, but it is the deliberate
cost of supporting genuinely common "nCr"/"nPr" shorthand, and the team already made
this trade-off explicitly (it's in the test file, not an oversight).

**Recommended fix (if the product wants to narrow this):** require the `\dC\d`/`\dP\d`
token to be either standalone (not glued inside a larger alphanumeric identifier via a
word-boundary check — "5C2" mid-sentence with a following word like "semester" is
weaker evidence than "5C2" as an isolated token) or accompanied by a combinatorics cue
word ("choose", "arrange", "combinations", "permutations") elsewhere in the message.
This is a product/precision-vs-recall tradeoff, not a correctness bug — do not treat it
as urgent.

**Do not:** silently narrow or remove this without confirming with product — this is
tested, intentional coverage for real homework notation, and narrowing it will
regress genuine "5C2" / "how many ways" homework questions.

---

### Extractor ordering / shadowing

#### O1 — Compound "draw circle... then graph..." requests: the earlier circle extractor wins over the later, more specific graph request

**Severity:** P2 · **Area:** math_tools/extractors/geometry_graph.py, extract.py ordering · **Effort:** S

**Evidence:** `_INTENT_EXTRACTORS`'s actual order (`extract.py:24-33`):

```
SOLID_EXTRACTOR, *SCHOOL_EXTRACTORS, *PHYSICS_EXTRACTORS, *GEOMETRY_GRAPH_EXTRACTORS,
*CALCULUS_EXTRACTORS, *PRE_DISCRETE_ALGEBRA_EXTRACTORS, *DISCRETE_STATISTICS_EXTRACTORS,
*ALGEBRA_EXTRACTORS
```

`GEOMETRY_GRAPH_EXTRACTORS` registers the circle extractor ahead of the graph extractor
within that same group. When a single message contains both a plain circle-drawing cue
and an explicit graph request with its own equation:

```
'graph the circle x^2 + y^2 = 25'                              -> graph   (correct)
'plot x^2 + y^2 = 25 from x=-5 to x=5'                          -> graph   (correct)
'draw a circle with radius 5, then graph x^2+y^2=25'            -> circle (shadowed!)
```

The third case's explicit `graph_x_min`/`graph_x_max`-free "then graph x^2+y^2=25" clause
is never reached — the earlier circle extractor already matched on "draw a circle with
radius 5" and returned first. (Note the first two single-clause cases work correctly —
this only reproduces when the message contains *both* a standalone circle cue and a
separate graph request in the same turn.)

**Why it matters:** low severity — both a static circle diagram and a parametric graph
of `x^2+y^2=25` are mathematically valid, correct representations of the same circle, so
this is a UX/intent miss (wrong sub-feature triggered) rather than a wrong-answer bug.
Flagging per the review brief's explicit request to test ordering/shadowing pairs.

**Recommended fix:** low priority. If addressed, check for an explicit "graph"/"plot"
verb with its own expression anywhere in the message before falling into the earlier
circle-only match — the graph extractor's expression pattern is already more specific
than the circle extractor's bare "draw a circle" cue, so a cheap fix is to run
`GEOMETRY_GRAPH_EXTRACTORS`' graph-family checks (which require an actual expression
containing both `x` and `y`) before its shape-family checks (which only require a shape
word) inside that group.

**Do not:** reorder the entire `GEOMETRY_GRAPH_EXTRACTORS` group wholesale — most shape
vs. graph pairs don't collide (a message rarely asks for both); a narrow "does an
explicit graph-with-expression cue exist anywhere in the text" pre-check is safer than a
global reorder that could introduce new shadowing in the other direction.

#### O2 — Prose wrapped around a "solve for X" equation extracts the whole sentence (not just the equation) as `lhs`, but fails safe

**Severity:** P3 (informational — confirmed to degrade safely) · **Area:** math_tools/extractors/algebra.py, math_service equation splitting · **Effort:** —

**Evidence:**

```
$ .venv/bin/python - <<'EOF'
from app.services.math_tools.extract import extract_math_intent
from app.services.math_tools.block import _build_verified_block
from app.core.config import Settings

t = "A right triangle has legs 3 and 4. Solve for c in c^2 = 3^2 + 4^2"
intent = extract_math_intent(t)
print(intent.kind, "lhs=", intent.lhs, "rhs=", intent.rhs, "var=", intent.variable)
print(_build_verified_block(intent, Settings()))
EOF

equation lhs='A right triangle has legs 3 and 4. Solve for c in c^2' rhs='3^2 + 4^2' var='c'
None
```

`math_service.try_extract_equations_from_text` splits on the message's only `=`, so
`lhs` is the *entire sentence up to and including* `"c^2"` (including the English prose
before it), not just `"c^2"`. `_requested_variable` correctly identifies `variable='c'`
from the "solve for c" phrase, but the `lhs` itself still contains unparseable English
and punctuation. Confirmed this degrades safely — `_build_verified_block` returns `None`
(sympify fails on the prose-laden `lhs`), which correctly routes to the honest
`_unverified_math_note` in `build_math_augmentation` rather than fabricating an answer.
Two similar formula-assignment cases ("find A in A = pi * r^2 when r = 3", "solve for A
if A = l * w, l = 4, w = 5") are misclassified as `system` (2+ `=` signs → treated as
simultaneous equations rather than sequential formula substitution) and also correctly
fail closed to `None`.

**Why it matters:** informational only — this is a real extraction miss (a
right-triangle Pythagorean word problem that legitimately could be verified is not), but
it does **not** produce a wrong "verified" answer; it correctly falls through to the
unverified note. Included because the review brief asked for confirmed
shadowing/misclassification pairs regardless of outcome — this is the "safe" half of
that risk, in contrast to M1–M5's "unsafe" half.

**Recommended fix:** none required for safety. If product wants to recover verification
on Pythagorean-theorem-style word problems, that's a net-new extractor (recognize
"legs A and B... solve for C" as a right-triangle hypotenuse pattern, already adjacent
to the existing `_extract_right_triangle_intent` in `geometry_graph.py`) rather than a
fix to the generic equation splitter — teaching the generic splitter to strip leading
prose risks *creating* an M1/M2-style bug (prose reaching sympify) rather than fixing
this one.

**Do not:** patch `try_extract_equations_from_text` to strip everything before the last
sentence boundary before the `=` — that is exactly the kind of "loosen the acceptance
criteria" change that created M1/M2; keep the current fail-closed behavior.

---

### False negatives (confirmed safe, but a product gap vs. `docs/math.md`'s coverage table)

#### N1 — Common inverse-phrasing rectangle/algebra word problems are not extracted at all

**Severity:** P2 (product gap, not a safety bug) · **Area:** math_tools/school.py, extractors/geometry_graph.py, extractors/algebra.py · **Effort:** M

**Evidence:**

```
"if 3 times a number plus 5 equals 20, what is the number"        needs_symbolic: False
"a rectangle has an area of 24 and a length of 6, find the width" needs_symbolic: False
"a rectangle is 3 1/2 cm by 2 cm, find the area"                  needs_symbolic: False
```

All three fall through cleanly to `needs_symbolic() == False` → unverified, LLM-only
answer. No wrong-answer risk (confirmed safe), but per `docs/math.md`'s own coverage
table these are exactly the algebra/geometry categories the feature claims to verify —
they're just not phrased in the "3x + 5 = 20" / "width W height H" shapes the extractors
look for. The rectangle case is specifically the *inverse* of the supported pattern
(given area + one side, solve for the other side, vs. the supported given-both-sides
pattern); the algebra case is a fully-spelled-out linear equation with no digits-and-
operator shorthand at all; the mixed-fraction case ("3 1/2") is a number-format the
extractors' numeric scanners don't recognize as a single value.

**Why it matters:** not a safety issue — flagged because the review brief specifically
asked to check whether phrasing that "clearly should be verified per docs/math.md's own
coverage table" is missed. This measurably narrows the "math powerhouse" promise for
common inverse/word-problem phrasing, even though it never produces a wrong answer.

**Recommended fix:** lower priority than M1–M5 (safety > coverage). If pursued: (1) add
an inverse-rectangle pattern to the rectangle extractor (`area of N` + `length of M` →
solve `width = N/M`, mirroring the existing given-two-sides case); (2) extend
`_calc_expr_tail`-style English-to-symbolic translation (recommended jointly for M1) to
also cover simple word-problem algebra ("3 times a number plus 5 equals 20" →
`3*x + 5 = 20`); (3) extend the numeric scanner in `scan.py` to recognize `"N M/D"` mixed
fractions as a single decimal value.

**Do not:** treat this as equally urgent to M1–M5 — a missed verification silently and
correctly degrades to an honest, uncertain LLM answer; a wrong verification degrades to
a confidently wrong one. Fix the latter first.

#### N2 — Comma as a decimal separator (European locale) is misparsed into two separate numbers

**Severity:** P2 · **Area:** math_text_match/scan.py numeric parsing · **Effort:** S

**Evidence:**

```
$ .venv/bin/python - <<'EOF'
from app.services.math_tools.extract import extract_math_intent
from app.services.math_tools.block import _build_verified_block
from app.core.config import Settings

intent = extract_math_intent("the width is 3,5 by 2 cm rectangle, find the area")
print(intent.width, intent.height)
print(_build_verified_block(intent, Settings()).text[:120])
EOF

5.0 2.0
Rectangle: width=5 cm height=2 cm diagonal=5.3852 angle=21.8°
```

"3,5" (European decimal notation for 3.5) is misread as the digit "5" (the "3" is
dropped from the dimension pair, likely because the comma is treated as punctuation
that breaks the pair-scan rather than a decimal point), so a `3.5 × 2` rectangle
(area 7) is verified as `5 × 2` (area 10) — a **wrong verified numeric answer**, not
just a missed extraction. This is the one false-negative-adjacent case in this section
that is actually a wrong-answer bug, not a safe fall-through — included here rather than
in the M-numbered section only because the trigger is a locale/formatting edge case
rather than a semantic misclassification.

**Why it matters:** this is a real, silent wrong-answer bug for any student typing in a
comma-decimal locale (most of continental Europe, Brazil, and others) — the app has no
locale detection, so this reproduces for any such user typing measurements naturally.

**Recommended fix:** treat this with the same urgency as M3–M5 despite being filed in
the "false negative" section — it is not a false negative, it silently returns a wrong
verified answer. Normalize `\d,\d` as a decimal separator in the numeric scanner
(`scan.py`'s `_parse_unsigned_number` / `_NUM` regex) when it's unambiguous (a single
digit on each side of the comma with no surrounding thousands-grouping pattern like
`1,234`), before dimension-pair extraction runs.

**Do not:** blanket-treat every comma as a decimal point — `"1,234"` (thousands
separator) and `"a, b"` (list separator) must not be broken; scope the fix to the
`\d,\d(?!\d)` shape (comma between exactly one digit on each side, not part of a longer
digit run) to avoid a new class of misparse.

---

### Performance / DoS surface

#### P1 — `needs_symbolic_math` cold-start pays ~1.3s importing the LiteLLM gateway on the first call in a fresh worker, on a hot path that runs on every chat turn

**Severity:** P2 · **Area:** math_text_match/needs.py → math_image_extract → litellm_gateway import chain · **Effort:** S

**Evidence:**

```
$ .venv/bin/python - <<'EOF'
import time
from app.services import math_text_match as mtm
t0 = time.perf_counter(); mtm.needs_symbolic("solve x + 2 = 5"); t1 = time.perf_counter()
print(f"First call: {(t1-t0)*1000:.1f}ms")
t2 = time.perf_counter(); mtm.needs_symbolic("solve x + 2 = 5"); t3 = time.perf_counter()
print(f"Second call: {(t3-t2)*1000:.1f}ms")
EOF

First call: 1373.7ms
Second call: 0.0ms
```

`needs.py:86` unconditionally does `from app.services.math_image_extract import
is_math_camera_prompt` inside `needs_symbolic()` on *every* call — regardless of whether
`has_image_attachment` is even `True` — and that module transitively imports
`litellm_gateway`. The import is Python-cached after the first call (hence 0.0ms on the
second), but the first chat turn handled by any freshly-started worker process pays this
tax inline, on a function that is by design called on every single chat turn.

**Why it matters:** this is a one-time-per-process cost, not a per-request cost, so it
is not a sustained throughput problem — but it lands as ~1.3s of added latency on
whichever unlucky user's message happens to be the first one a fresh worker/pod handles
after a deploy or autoscale-up event, on a path with no user-facing indication that
anything unusual is happening (the chat just streams late).

**Recommended fix:** move the `is_math_camera_prompt` import inside the
`if has_image_attachment:` branch (it already only matters when `has_image_attachment`
is true) so the litellm import cost is paid only on the (rarer) image-attached path, not
on every text-only chat turn.

**Do not:** try to eagerly warm this import at process startup as an alternative fix —
that just moves the 1.3s to cold-start/readiness-probe time for every worker, which is
worse for autoscaling responsiveness than a lazy import that most turns never pay at all
once the module cache is warm.

---

### Swept and clean (checked, not reproduced)

- **ReDoS**: a stress battery of 6 pathological inputs (10,000–15,000 chars: repeated
  `=`, repeated digits, repeated commas, nested parens, long "roots of" prefixes, long
  runs of a single repeated letter) against `needs_symbolic()` directly — all returned
  in 0.07–0.25ms, no backtracking blowup:

  ```
  adv[0] len=10000 ("x=" * 5000)                    -> 0.16ms
  adv[1] len=10000 ("3" * 10000)                     -> 0.16ms
  adv[2] len=10020 (("a"*500+" ")*20)                 -> 0.17ms
  adv[3] len=4001  ("("*2000 + "1" + ")"*2000)        -> 0.07ms
  adv[4] len=6024  ("the roots of " + "a "*3000 + "are unknown") -> 0.14ms
  adv[5] len=15000 ("1,0"*5000)                       -> 0.25ms
  ```

  and none of it matters in practice regardless, because `scan.py:9`'s `_MAX = 1000`
  hard length cap in `prepare()` means any input over 1000 characters returns `None`
  immediately, before a single regex in this module runs. `math_text_match`'s own
  documented design goal (CodeQL-safe linear scans, confirmed in `scan.py`'s module
  docstring) held up under direct stress testing — the ReDoS class found and fixed
  elsewhere in this codebase (the tool-loop code-fence detector) does not reproduce here.

- **`extract_math_intent`'s ordering was checked for the shadowing pairs the review
  brief specifically asked for** (school vs. physics, geometry vs. algebra, calculus vs.
  algebra, discrete vs. algebra) beyond the one confirmed case (O1). No other pair
  produced a reproducible wrong-kind result in this battery — most extractor pairs have
  disjoint, cue-word-gated triggers (e.g. physics requires one of ~25 specific phrases
  like "dropped"/"projectile"/"net force" that geometry/algebra extractors don't share)
  so accidental double-matches are structurally rare by design, not by luck.

---

## D. Findings inventory

| ID | Finding | Severity | Confirmed wrong verified answer? |
|----|---------|----------|-----------------------------------|
| M1 | Calculus/limit/series sympify raw English prose | **P0** | Yes — reproduced |
| M2 | "roots of"/"zeros of" prose rewrite hits same sympify path | **P0** | Yes — reproduced |
| M3 | Kinematics height extractor binds mass to `h0` | **P1** | Yes — reproduced |
| M4 | Triangle-angle false positive on unrelated 3-numbers-sum-180 | P1 | Yes — reproduced |
| M5 | "mode" substring statistics false positive | P1 | Yes — reproduced |
| M6 | "5C2"-style alphanumeric codes read as combinatorics | P2 | By design (tested) |
| N2 | Comma decimal separator misparsed | P2 | Yes — reproduced (wrong number, not just missed) |
| O1 | Circle extractor shadows explicit graph request | P2 | No — different valid representation |
| O2 | Prose-wrapped equation extracts full sentence as lhs | P3 | No — fails safe to unverified |
| N1 | Inverse-phrasing word problems not extracted | P2 | No — fails safe to unverified |
| P1 | Cold-start LiteLLM import on hot path | P2 | N/A — latency only |
| — | ReDoS on `needs_symbolic_math` | — | Not reproduced; capped + linear |

---

## E. Adversarial battery run (full list, for traceability)

All of the following were run directly against `needs_symbolic()` / `extract_math_intent()`
/ `_build_verified_block()` during this review, in addition to the specific repros
inlined above:

- Ambiguous "find x": "find A in A = pi * r^2 when r = 3", "solve for A if A = l * w, l
  = 4, w = 5" → misclassified as `system` (2 equals-signs), fails safe to `None` (see O2).
- Word problem mixing a triangle mention and an equation: covered by M4.
- False positives: "I got 100% on my last 3 tests", "my phone number is 555-1234, call
  me", "chapter 7, problem 12: solve for x" → all correctly `needs_symbolic() == False`
  (§B).
- Numeric extraction correctness in word problems: "a triangle with base 5 and height 3,
  cost $20 per square meter" → correct (§B); the "model 100 ... model 80" case →
  incorrect (M5).
- Unit/locale: comma-decimal (N2, wrong-answer bug), mixed fraction "3 1/2" (N1, safe
  miss), "3,5 by 2 cm" (N2).
- Extractor ordering: circle-vs-graph (O1, confirmed shadow), equation-vs-triangle prose
  (O2, fails safe).
- Full existing suite: 344/344 passing (§B).

---

## F. Explicit non-goals of this review

- **The core SymPy solve/differentiate/integrate correctness inside `math_service/`**
  is out of scope — this review only checked whether the *input* handed to those
  functions is the input the student actually intended. A prior/parallel review of
  `math_service` itself is assumed to cover solver correctness given a correct
  `MathIntent`.
- **The block-rendering/formatting layer's prompt-instruction wording** (e.g. whether
  "Do NOT recompute" phrasing is optimally worded to prevent the model from
  hallucinating around a verified block) is out of scope beyond the trust-boundary
  delegation check in §B.
- **`math_image_extract`'s vision/OCR extraction quality** (mapping a photographed
  problem to a `MathImageExtract`) is out of scope — this review only checked
  `_intent_from_image_extract`'s mapping from an already-Pydantic-validated extract to a
  `MathIntent`, not the vision model's own accuracy.
- **Load/concurrency testing of the `ProcessPoolExecutor` SymPy sandbox
  (`sympy_executor.py`)** under real production concurrency is out of scope — this
  review only exercised the extraction layer synchronously and in-process.
- **Non-English locale phrasing** (the app is i18n'd; this review only tested English
  student phrasing, per the review brief's own adversarial-battery examples) — the one
  locale-adjacent bug found (N2, comma decimals) was discovered incidentally, not via a
  systematic non-English sweep.
- **No source code was modified as part of this review** — all findings are read-only
  observations with runnable reproductions; fixes are recommendations only.
