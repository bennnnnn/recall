# Recall — SymPy Computation Core Review (Sep 2026)

Scope: the "math powerhouse" heuristic pre-stream verification core —
`services/sympy_executor.py`, `services/math_service/{__init__,parse,algebra,geometry,
graph,discrete,extract_eq}.py`, and their Pydantic contracts in `models/math_schemas/`.
Per `docs/math.md`, this layer runs *before* the model streams, produces
`canonical_fence`/`canonical_answer` data injected into the system prompt, and the model
is explicitly instructed **not** to recompute for verified kinds — it trusts this layer
completely. A wrong answer from this layer reaches the user with no LLM cross-check and
the visual/semantic weight of "verified." Callers of this core (`math_tools/`,
`services/mcp/sympy_adapter.py`, `math_fence.py`) are in scope only as far as needed to
trace exception propagation and reachability — their broader design was not re-audited.

Reviewed at `cursor/cross-domain-review-2026-09-05`. Builds on
`docs/MCP_TOOL_LOOP_SECURITY_REVIEW_2026-09-06.md`'s finding that the `sympify`/
`parse_expr` RCE vector is closed — **re-verified today, still true** (§B). This review
does not re-litigate that finding; it goes deeper on correctness, coverage, and
availability inside the computational core itself.

Every claim below is backed by a command actually run against
`/workspace/apps/api/.venv/bin/python` (SymPy 1.14.0) in this session, not by reading code
and assuming. Exact commands and their real output are inline.

---

## A. Verdict

**Baseline: the existing test suite is fully green.**

```
$ cd /workspace/apps/api && .venv/bin/python -m pytest \
    app/tests/services/test_math_service.py app/tests/services/test_sympy_executor.py \
    app/tests/services/test_math_advanced.py app/tests/services/test_math_geometry_advanced.py -v
...
175 passed in 3.87s
```

175/175. That is a real, useful baseline — but it is also a ceiling on what pre-existing
tests can tell you: every one of the bugs below produces a *result*, not a crash, so
nothing in that suite was positioned to catch them. The suite tests "does `solve_equation`
run and return a plausible-shaped `MathSolveResult`," not "does `guess_variables` ever
pick the wrong symbol."

**Headline finding: a single-letter variable name silently resolves to a SymPy constant
instead of the user's intended unknown, and this is not a corner case — it defeats even
an explicit "solve for e" instruction from the user.** `guess_variables()`
(`discrete.py:51`) intentionally excludes `'e'` and `'E'` from candidate variable letters
so that `sin(pi*x)` doesn't misfire on the exponential/pi constant letters — a real and
previously-fixed bug class (see the `test_guess_variables_ignores_function_name_letters`
history, and the "Solve for y" bug fix comment in `test_math_tools.py:56-58`). But the fix
overshot: when a student's equation is `e + 1 = 5` (meaning "find e, the unknown"),
`guess_variables` returns `[]` → the extractor falls back to the default `'x'`
(`extractors/algebra.py:125`), and `EquationInput(variables=['x'])` never overrides
`parse.py`'s `_LOCALS = {"e": math.e, ...}` (`parse.py:29`). SymPy solves `e+1=5` — where
`e` is literally `2.71828...` — and correctly reports **no solution** for what is, to the
student, a completely solvable one-step equation with answer `e=4`. This is delivered as
a `canonical_answer`/`canonical_fence` the model is told not to second-guess. Worse:
`extractors/algebra.py:61-62` explicitly `discard("e")` / `discard("E")` from the set of
letters an explicit **"solve for e"** cue is even allowed to match, so a user who
disambiguates by literally typing "solve for e" still gets `variable='x'` and the same
wrong contradiction. Reproduced end-to-end through the real production entrypoint
(`math_tools.extract_math_intent` → `math_tools.build_verified_math_context`), not a
synthetic unit test. This is the single most severe class of bug this audit was designed
to find — see **M1**.

**Everything else found is real but narrower.** The single-worker SymPy subprocess pool
(`sympy_executor.py`) is well-designed and its cancellation-safety/no-cross-request-
contamination properties held up under direct adversarial reproduction (kill-and-respawn,
concurrent racing, `CancelledError` mid-flight) — but it has **no bound on computational
complexity, only on expression character length**, and legitimate curriculum-level
requests (`x^40 = 1`, a standard roots-of-unity problem) reliably blow the 5-second budget,
degrading silently to "unverified" and tying up the single worker for the full timeout
window — a real shared-resource availability concern, not a wrong-answer one (**M2**).
Graph sampling crashes with an uncaught `TypeError` on any expression SymPy's parser
auto-simplifies to a plain constant (`0/x`, `x-x`) — contained by broad exception handlers
everywhere it's reachable today (fails closed, never a wrong "verified" answer), but the
containment is accidental in one path and produces a misleading "timed out" error instead
of the real cause (**M3**). One cosmetic formatting bug in complex-root display
(**M4**, low severity, mathematically unambiguous).

**Everything the previous review series already closed stayed closed.** The RCE
allowlist in `parse.py` rejected every fresh payload this review threw at it; the 256-char
cap and the geometry Pydantic bounds (triangle inequality, positive dimensions, sector
angle ∈ (0, 360]) held on every adversarial case tried; float-precision noise from
`0.1+0.2`-style arithmetic never reaches a user because only the `.latex` field (clean)
is surfaced, never the raw `.result` string (noisy) — verified by tracing every call site,
not assumed.

---

## B. RCE re-verification (quick check, not re-litigated)

`MCP_TOOL_LOOP_SECURITY_REVIEW_2026-09-06.md` found the `sympify`/`parse_expr` RCE vector
closed via `parse.py:_reject_unsafe_expr` (no `__`, no `[`/`]`, no bare `.` outside a
decimal, plus a strict character allowlist). Re-run today against fresh payloads:

```
$ .venv/bin/python /tmp/adversarial_parse.py
--- dunder RCE: 'x.__class__.__bases__[0]' ---
REJECTED (MathServiceError): Invalid expression
--- import RCE: "__import__('os').system('id')" ---
REJECTED (MathServiceError): Invalid expression
--- getattr RCE: "getattr(x,'__class__')" ---
REJECTED (MathServiceError): Invalid expression
--- semicolon injection: 'x; import os' ---
REJECTED (MathServiceError): Invalid expression
--- lambda-ish: 'lambda: 1' ---
REJECTED (MathServiceError): Invalid expression
--- percent op: '10%3' ---
REJECTED (MathServiceError): Invalid expression
--- bitwise and: '5&3' ---
REJECTED (MathServiceError): Invalid expression
--- f-string like: "f'{x}'" ---
REJECTED (MathServiceError): Invalid expression
```

Still closed. `math_max_expr_length` (256) is enforced inside `_parse_expression`
(`parse.py:423-424`) before `_reject_unsafe_expr` even runs, and independently at the
Pydantic layer (`EquationInput`, `SystemOfEquationsInput` both `max_length=256`) and in
the MCP tool schema (`SympyToolInput.expr`, same cap) — three independent enforcement
points, all confirmed live. Not re-litigating further; moving to what this review adds.

---

## C. Findings — ranked

### Correctness (wrong "verified" answers)

#### M1 — `e`/`E` silently resolve to Euler's number instead of the user's variable; this defeats even an explicit "solve for e" request and produces a confidently wrong "no solution"

**Severity:** P0 · **Area:** math_service/discrete.py, math_tools/extractors · **Effort:** S

**Evidence:**

`discrete.py:38-52`:

```python
def guess_variables(text: str) -> list[str]:
    stripped = _FUNCTION_NAME_RE.sub(" ", text)
    stripped = _CONSTANT_NAMES_RE.sub(" ", stripped)
    found = sorted(set(re.findall(r"[a-zA-Z]", stripped)))
    # Exclude single-letter constants: e (Euler's number) ...
    letters = [c for c in found if c not in {"e", "E"}]
    return letters[:4] if letters else ["x"]
```

`parse.py:27-31`:

```python
_LOCALS: dict[str, Any] = {
    "pi": math.pi,
    "e": math.e,
    "Abs": Abs,
}
```

`parse.py:426-429` — `local_dict` starts as a copy of `_LOCALS` and is only overridden per
declared variable name; if `"e"` is never in `variable_names`, `_LOCALS["e"] = math.e` wins:

```python
local_dict = dict(_LOCALS)
if variable_names:
    for name in variable_names:
        local_dict[name] = Symbol(name, real=True) if real else Symbol(name)
```

`extractors/algebra.py:52-63` — even an explicit disambiguation cue is defeated:

```python
def _requested_variable(cleaned: str, equation_text: str) -> str | None:
    m = _SOLVE_FOR_VAR_RE.search(cleaned)
    ...
    letters = {c for t in kept for c in t if c.isalpha()}
    letters.discard("e")
    letters.discard("E")
    return var if var in letters else None
```

Reproduced end-to-end through the real intent extractor (not a synthetic call):

```
$ .venv/bin/python -c "
from app.services import math_tools
intent = math_tools.extract_math_intent('Solve for e: e + 1 = 5')
print(intent.lhs, intent.rhs, intent.variable)
"
e + 1 5 x
```

```
$ .venv/bin/python -c "
from app.services.math_service.discrete import guess_variables
from app.services.math_service.algebra import solve_equation
from app.models.math_schemas import EquationInput
v = guess_variables('e + 1 5')            # -> []
r = solve_equation(EquationInput(lhs='e + 1', rhs='5', variables=v or ['x']))
print(r.solution_kind, r.steps)
"
none ['Equation: 4.71828182845905 = 5', 'No solutions found (equation is a contradiction).']
```

The equation the student wrote (`e + 1 = 5`, answer `e = 4`) is silently rewritten to
`2.71828... + 1 = 5`, correctly identified as a contradiction *of the rewritten equation*,
and reported to the user as a verified "no solution" for their original equation. Also
confirmed the wrong `canonical_answer`/`canonical_fence` actually reaches the fence-rewrite
layer (`math_fence.py`) unchanged — the model is told this is verified truth and is
instructed not to recompute it.

Confirmed the blast radius is narrow to exactly `e`/`E` — every other single capital
letter that collides with a SymPy global (`I`, `S`, `N`, `O`, `Q`, `C`) is **not**
excluded from `guess_variables` and resolves correctly once declared as a variable:

```
$ .venv/bin/python -c "
from app.services.math_service.discrete import guess_variables
from app.services.math_service.algebra import solve_equation
from app.models.math_schemas import EquationInput
for text in ['I + 1 = 5', 'S + 1 = 5', 'N + 1 = 5', 'O + 1 = 5', 'Q + 1 = 5', 'C + 1 = 5']:
    lhs, rhs = text.split(' = ')
    v = guess_variables(text)
    r = solve_equation(EquationInput(lhs=lhs, rhs=rhs, variables=v or ['x']))
    print(text, '->', v, r.solutions_latex)
"
I + 1 = 5 -> ['I'] ['I = 4']
S + 1 = 5 -> ['S'] ['S = 4']
N + 1 = 5 -> ['N'] ['N = 4']
O + 1 = 5 -> ['O'] ['O = 4']
Q + 1 = 5 -> ['Q'] ['Q = 4']
C + 1 = 5 -> ['C'] ['C = 4']
```

`pi` is handled correctly too — `guess_variables` strips the multi-letter constant name
via `_CONSTANT_NAMES_RE` and correctly falls back to `x` only when no genuine variable
letter remains, and `pi + 1 = 5` (a true contradiction, since π+1 ≈ 4.14 ≠ 5) is correctly
classified as "no solution" — that is the *right* answer, not a bug. The bug is isolated
to the single-letter `e`/`E` exclusion.

**Why it matters:** `e` is an extremely ordinary student/economics-context variable name
("let e be the number of eggs," "solve for e in the exponential model," a base-rate
variable in a word problem). Per `docs/math.md`, this layer's output is injected as
`canonical_answer` and the model is explicitly told not to recompute it — the wrong answer
ships with full "verified" confidence and zero LLM cross-check. This is precisely the
failure mode this audit was scoped to find as the worst possible bug in the feature, and
it is trivially reachable from ordinary, non-adversarial homework phrasing — no crafted
input required.

**Recommended fix:** Do not silently discard `e`/`E` as candidates. Instead, disambiguate
the way SymPy itself would: if the text contains `e` positioned as an exponential-context
token (adjacent to `^`, inside `exp(...)`, or as the literal token in `e^x`/`e**x`), treat
it as Euler's number; otherwise, if `e`/`E` appears as a bare additive/multiplicative term
(exactly the shape `guess_variables` already detects for every other letter), treat it as
a candidate variable like any other. At minimum, `_requested_variable`'s explicit
`solve for e` cue must not be defeated by the same blanket exclusion — an explicit user
instruction should always win over a heuristic default. A cheap, safe first step: when the
only candidate variable found is excluded solely because it was `e`/`E`, and the request
has an explicit "solve for e" / "find e" cue, honor it (construct `EquationInput` with
`variables=['e']`, which correctly overrides `_LOCALS['e']` in `parse.py:428` today —
the underlying solver already handles this correctly once the variable is declared, as
shown by the `I`/`S`/`N`/`O`/`Q`/`C` results above).

**Do not:** fix this by removing `e` from `_LOCALS` globally — that would break every
legitimate `e^x`/`exp` problem that relies on `e` resolving to Euler's number when it is
*not* declared as a variable. The fix belongs in the disambiguation heuristic
(`guess_variables` / `_requested_variable`), not in `parse.py`'s constant table.

---

### Availability / coverage (not wrong answers, but real product-quality gaps)

#### M2 — No bound on computational complexity (only on expression length) lets ordinary curriculum-level polynomial solves blow the 5s timeout, degrading verification coverage and tying up the single-worker pool

**Severity:** P1 · **Area:** sympy_executor.py, math_schemas/algebra.py · **Effort:** M

**Evidence:** `math_max_expr_length` (256 chars, `core/config.py`) bounds string length,
not computational cost, and nothing in `EquationInput`/`SystemOfEquationsInput` bounds
polynomial degree. `x^40 = 1` is 8 characters and a completely mainstream precalculus
roots-of-unity problem:

```
$ .venv/bin/python -c "
import signal, time
from app.services.math_service.algebra import solve_equation
from app.models.math_schemas import EquationInput
for deg in (30, 40, 50):
    t0 = time.monotonic()
    r = solve_equation(EquationInput(lhs=f'x**{deg}', rhs='1', variables=['x']))
    print(deg, 'took', round(time.monotonic() - t0, 2), 's,', len(r.solutions_latex), 'roots')
"
30 took 1.31 s, 30 roots
40 took 3.06 s, 40 roots
50 took 6.84 s, 50 roots        # already past the 5.0s production timeout
```

Confirmed via the real subprocess pool (not in-process — includes spawn/serialization
overhead), which is what production actually pays:

```
$ .venv/bin/python /tmp/adversarial_degree2.py
degree=40  ran=4.91s  -> OK (40 roots)
degree=50  ran=TIMEOUT at 5.0s
```

Also confirmed the single-worker pool is genuinely tied up for the entire timeout window
on a hostile-but-innocuous-looking short expression (a chained-exponent tower, 76 chars,
well under the 256 cap):

```
$ .venv/bin/python /tmp/adversarial_pool_timeout.py
submitted '2**2**2**2**2**2**2**2**2**2**2**2**2**2**2**2**2**2**2**2**2**2**2**2**2'
TimeoutError after 5.003s (worker SIGTERM'd, pool respawned)
second call after kill: ran fine, new PID confirmed different from first
```

The kill-and-respawn mechanism itself works correctly (see §D) — the problem is that this
5-second window, however cleanly it fails, is spent occupying the *only* worker in the
pool (`max_workers=1`, `sympy_executor.py:84`), and `_QUEUE_WAIT_SECONDS = 60.0`
(`sympy_executor.py:51`) means a second, unrelated user's legitimate math request queues
behind it for up to 60 seconds before even starting its own clock.

**Why it matters:** Two distinct product-quality problems, not a wrong-answer problem
(the timeout path fails closed — traced through `math_tools/prompt.py`'s
`TimeoutError` → `None` → the model falls back to unverified prose, correctly, per the
existing containment). First, a routine curriculum request loses SymPy verification
coverage exactly the moment it stops being trivial — students doing standard precalc
"find all nth roots" homework are pushed onto the unverified LLM-only path for no reason
the docstring's stated limits (character length) would predict. Second, since the pool
has exactly one worker, *any* single request near or over budget (accidental or crafted)
degrades every other concurrent user's math request for up to a minute.

**Recommended fix:** Add an explicit, cheap pre-check on the *shape* of the input before
handing it to `solve()` — e.g. reject or route to a numeric-approximation fallback for
polynomial degree above a documented ceiling (bench a safe number, e.g. degree ≤ 20, which
comfortably fits the budget with margin for concurrent contention), and apply the same
kind of shape check to nested-exponentiation depth (the tetration case) rather than relying
solely on character count. Consider raising `max_workers` on `ProcessPoolSympyExecutor`
to 2–3 now that its cancellation-safety is independently verified (§D) so one slow/hostile
request does not serialize every other math request behind it.

**Do not:** raise `math_solve_timeout_seconds` to "fix" this — that just moves the
availability problem (a longer window for one request to hold the only worker) without
addressing the root cause (no bound on the actual computational shape of the input).

---

#### M3 — `sample_function` throws an uncaught `TypeError` on any expression SymPy auto-simplifies to a constant; contained everywhere reachable today, but the containment is accidental in one path and misreports the failure as a timeout

**Severity:** P2 · **Area:** math_service/graph.py · **Effort:** S

**Evidence:** `graph.py:74-86` calls `lambdify` then unconditionally iterates the result
as an array (`zip(xs, ys, ...)`, line 83). If SymPy's parser (`evaluate=True`) collapses
the input expression to a plain constant that does not depend on the sampling variable
(e.g. `0/x → 0`, `x - x → 0`, `5 - 5 + 0*x → 0`), `lambdify` returns a function that hands
back a bare scalar (a 0-d array), and the `try/except` at line 76-79 does not cover this —
it only wraps the `numpy_fn(xs)` call itself, not the loop that follows:

```
$ .venv/bin/python -c "
from app.services.math_service.graph import sample_function
from app.models.math_schemas import GraphSampleInput
sample_function(GraphSampleInput(expr='0/x', variable='x', x_min=-5, x_max=5, n=11))
"
Traceback (most recent call last):
  File '.../graph.py', line 83, in sample_function
    for x_val, y_val in zip(xs, ys, strict=False):
TypeError: iteration over a 0-d array
```

Reproduced for `0/x`, `x-x`, `5-5+0*x` (all crash) — `sin(x)**2+cos(x)**2` does **not**
crash, because SymPy's `evaluate=True` does not apply the Pythagorean identity at parse
time, so it stays as a genuine function of `x`; only expressions the parser itself folds
to a bare number trigger this.

Traced every reachable caller:

- **Heuristic pre-stream path** (`math_tools/block/graph.py` → `_build_verified_block`):
  wrapped in a broad `try/except Exception` (`math_tools/block/__init__.py`) that logs and
  returns `None` — degrades cleanly to unverified, no crash reaches the user. **Safe.**
- **MCP tool path** (`services/mcp/sympy_adapter.py`'s `_action_graph` → `_run_off_loop` →
  `run_sympy`): the `TypeError` propagates through the subprocess boundary inside
  `sympy_executor.run()`, which — because it is not a `TimeoutError` and not a normal
  return — falls into the generic `except BaseException` branch (`sympy_executor.py:155-161`),
  which **kills and respawns the pool** (unnecessary: a `TypeError` from bad input is not a
  runaway computation) and re-raises. `_run_off_loop` then catches the re-raised exception
  generically and returns `None`, and the caller reports **"Math error: timed out"** to the
  model — a real, reachable, misleading message, since the actual failure was an unhandled
  crash, not a timeout. **Fails closed (no wrong answer reaches the user), but the pool
  kill is wasted work and the error message is wrong.**
- **`math_fence.py`'s `_resample_curve`**: has its own explicit `except (MathServiceError,
  ValueError, TypeError)` around the resample call — this suggests a prior author already
  knew about this exact failure shape and defended against it locally, without fixing the
  root cause in `graph.py` itself. **Safe**, but the duplication is a signal the bug should
  be fixed once at the source.

**Why it matters:** Not a wrong-verified-answer bug — every path that can reach it fails
closed today. It is a latent crash whose blast radius depends entirely on incidental
exception-handling choices made in three different, independently-written call sites; the
MCP path's containment is a side effect of generic `except BaseException`/`except
Exception` handling, not a deliberate design decision, and it currently produces a
user-facing lie ("timed out") about what happened, plus an unnecessary subprocess
respawn cost shared by every concurrent math request.

**Recommended fix:** Fix at the source in `graph.py:81-86` — after `ys =
np.asarray(ys, dtype=float)`, check `ys.ndim == 0` (or use `np.broadcast_to(ys, xs.shape)`)
and, if the expression does not depend on the variable, emit the constant `y` value at
every sampled `x` (mathematically correct: `y = x - x` really is the horizontal line
`y = 0`) instead of crashing. This makes the "graph a constant" case a legitimate verified
answer instead of a silent `None` fallback, and removes the misleading "timed out" message
and the spurious pool kill in the MCP path.

**Do not:** "fix" this by adding another local `try/except TypeError` at the MCP call site
— that's the third independent patch for the same root cause; fix `sample_function` itself
so every caller benefits and the constant case renders correctly instead of falling back to
"can't verify this."

---

### Cosmetic (correct math, confusing presentation)

#### M4 — Magnitude-1 imaginary coefficients render with a redundant explicit "1" (`x = ± 1 i` instead of `x = ± i`)

**Severity:** P3 · **Area:** math_service/algebra.py (`compact_root_answer_lines`) · **Effort:** S

**Evidence:**

```
$ .venv/bin/python -c "
from app.services.math_service.algebra import solve_equation
from app.models.math_schemas import EquationInput
r = solve_equation(EquationInput(lhs='x**2+1', rhs='0', variables=['x']))
print(r.solutions_latex, r.canonical_solutions_latex)
"
['x = -i', 'x = i'] ['x = \\pm 1 i']
```

`algebra.py:120-122` computes `imag_abs = simplify(Abs(simplify(imag)))` (here, `1`) and
always renders it: `f"{var_l} = \\pm {_solution_value_latex(imag_abs)} i"`. Unlike the
real-pairing branch (lines 66-72 in `_solution_value_latex`, which special-cases
`imag == 1` → `"i"` and `imag == -1` → `"-i"`), the complex-conjugate-pairing branch never
special-cases a magnitude of exactly 1.

**Why it matters:** Purely cosmetic — `x = \pm 1 i` and `x = \pm i` are the identical
number, and this only affects the compact "canonical" display line
(`canonical_solutions_latex`), not the individually-correct `solutions_latex` entries. Low
severity, but worth a one-line fix since it is the line most likely to be quoted verbatim
by the model.

**Recommended fix:** In the branch at `algebra.py:121-122`, special-case `imag_abs == 1`
the same way `_solution_value_latex` already does (drop the explicit coefficient).

**Do not:** touch `_solution_value_latex` itself — it already handles this correctly; only
the compact-pairing branch in `compact_root_answer_lines` needs the same special case.

---

## D. What's working (verified today, not assumed)

- **RCE sandbox intact.** Every fresh adversarial payload tried in this session
  (dunder-chain, `__import__`, `getattr`, semicolon injection, `lambda`, bitwise/percent
  operators, f-string-shaped input) was rejected by `_reject_unsafe_expr`. Three
  independent length-cap enforcement points (`parse.py:423`, Pydantic schema
  `max_length=256`, MCP tool schema) all confirmed live. See §B.

- **Executor cancellation-safety and no-cross-request-contamination hold up under direct
  reproduction**, not just by reading the code. `max_workers=1` means every call is fully
  serialized through one subprocess at a time, and the future returned by
  `pool.submit()` is 1:1 with the `asyncio.wrap_future` the awaiting coroutine owns — there
  is no path for one request's abandoned/killed computation to be delivered to a different
  request. Verified: a hard timeout kills the worker and the *next* call gets a
  demonstrably different PID (fresh worker, no leaked state); a mid-flight
  `asyncio.CancelledError` (simulating a WS disconnect/cancel) hits the same
  `except BaseException` branch (`sympy_executor.py:155-161`) and also kills+respawns
  rather than orphaning a runaway process; a queued-but-not-yet-running call is exempt from
  the solve timeout entirely (`sympy_executor.py:124-132`) so a call that merely waited
  behind another does not get punished with a spurious timeout and does not kill the
  occupant it was waiting on. All of this matches `test_sympy_executor.py`'s own coverage
  (`test_timeout_raises_and_kills_worker`, `test_cancel_kills_worker`,
  `test_timeout_excludes_queue_wait`) — read closely, that file is genuinely testing the
  properties it claims to, not just "does it run."

- **Float-precision noise never reaches a user.** `simplify_expression("0.1+0.2")` returns
  `result='0.300000000000000'` (raw, noisy) alongside `latex='0.3'` (clean) — traced every
  block-builder and the MCP adapter's output-formatting path (`sympy_adapter.py` prefers
  `.latex` over `.result` explicitly) and confirmed `.result` is never surfaced to the end
  user anywhere in scope.

- **No-solution / infinite-solution / extraneous-root classification is mathematically
  correct**, verified against hand-checked cases, not assumed: `x = x+1` → contradiction
  (correct), `x = x` and `2x+4 = 2(x+2)` → identity/infinite (correct),
  `(x**2-1)/(x-1) = 2` → correctly excludes the extraneous pole at `x=1` and reports "no
  solution" (SymPy's `solve()` already respects the domain restriction; confirmed
  `simplify(lhs-rhs)` does not spuriously cancel to zero), `sqrt(x) = -1` → correctly "no
  solution" (the classic extraneous-root trap, handled correctly because SymPy's radical
  solve does not introduce the spurious `x=1`). Improper integrals through an
  interior singularity (`∫1/x dx from -1 to 1`, `∫1/(x-2) dx from 0 to 4`) correctly
  evaluate to `nan`/`oo` rather than silently returning a finite-looking wrong value from
  naively evaluating the antiderivative at the bounds.

- **Inequality sign-flip on division by a negative is correct**: `-2x > 4` → `x < -2`;
  `-x < 3` → `x > -3`. Compound inequalities (`1 < x <= 3`) parse and solve correctly.

- **Geometry input validation is airtight before any computation runs.** Every degenerate
  case tried (triangle inequality violation, zero/negative dimensions, sector angle 0/361°,
  interior angles not summing to 180°, dimensions over the 1e6 cap) is rejected by Pydantic
  validators or explicit checks *before* reaching the raw `geometry.py` math functions,
  which correctly have zero validation of their own — confirmed every call site in
  `math_tools/block/geometry.py` and `sympy_adapter.py` constructs input exclusively
  through the validated schema, never a bypassing raw dict.

- **Parser correctly accepts common student notation**: `2x` → `2*x`, `x^2` → `x**2`,
  `2(x+1)` → `2*x+2`, `xy` → `x*y`, `(x+1)(x-1)` → correct expansion, `|x-2|` → `Abs(x-2)`,
  unicode `×`/`÷`/`−` all normalize correctly.

- **Discrete/combinatorics bounds are all enforced and prevent runaway computation**:
  factorial capped at 170 (`discrete.py:104`), `n`/`k` capped at 1000 each with an explicit
  `k > n` rejection (`discrete.py:113`), number theory capped at ±1e8 keeping `factorint`'s
  worst case fast, `MatrixInput` bounded to 2×2–4×4 with a square-matrix cross-field
  validator, `StatisticsInput` rejects non-finite values and enforces `min_length=1` (no
  empty-list mean/median crash). Matrix entries convert via `Rational(str(v))`, not
  `Rational(v)`, specifically to avoid binary-float noise (`str(0.1) == '0.1'` →
  `Rational('0.1') == 1/10` exactly) — a deliberate, correct mitigation.

- **Test suite baseline: 175/175 passing**, and the executor test file in particular
  (`test_sympy_executor.py`) tests real behavioral properties (kill-and-respawn, PID
  change, queue-wait exclusion, concurrent serialization) rather than superficial
  "did it not crash" assertions.

---

## E. Swept and clean (previously flagged, re-verified, still true)

- **`sympify`/`parse_expr` RCE vector** (`MCP_TOOL_LOOP_SECURITY_REVIEW_2026-09-06.md`):
  re-verified with fresh adversarial payloads this session (§B). Still closed.
- **`core/jobs.py` layering** and other cross-domain findings from
  `docs/CODEBASE_REVIEW_2026-08.md` / `docs/BACKGROUND_JOBS_INFRA_REVIEW_2026-09-06.md` are
  out of scope here and were not re-tested — no claims made about them in this document.

---

## F. Explicit non-goals

- **`services/physics_solver.py` / `services/school.py`** and any other numeric-template
  solver outside `math_service/` were not reviewed — confirmed only that `solve_equation`
  itself (the file in scope) is not reachable from physics word-problem intent extraction
  (that path uses a separate, already-templated solver), so the complex-roots-in-a-
  real-world-context concern raised in the task brief does not apply to the files in
  scope. A dedicated physics-solver review is a separate exercise.
- **`math_tools/block/*.py` and `math_tools/extractors/*.py` beyond exception-tracing.**
  These were read only as far as needed to establish reachability and exception handling
  for the findings above (most centrally, M1's `guess_variables`/`_requested_variable`
  call sites). Their broader intent-extraction quality (regex robustness, phrasing
  coverage) was not systematically audited.
- **`services/mcp/sympy_adapter.py`'s RCE posture** — re-verified, not re-audited from
  scratch; see §B and the prior review it builds on.
- **General code architecture/layering** (file size, naming, DRY) — this review is
  correctness-first per the task brief; no style/architecture findings are reported.
- **Performance tuning beyond the specific M2 pool-sizing/degree-bound recommendation** —
  no broader profiling of `math_service/` was done.
- **Non-English locales / i18n of math output** — not exercised.

---

## G. Summary table

| ID | Severity | Area | Effort | One-line |
|----|----------|------|--------|----------|
| M1 | **P0** | discrete.py / extractors | S | `e`/`E` silently shadow Euler's number, defeating even an explicit "solve for e" and producing a wrong "verified" no-solution |
| M2 | P1 | sympy_executor.py | M | No bound on computational shape (only char length) — curriculum-level polynomial degree (`x^40=1`) blows the 5s budget and ties up the single worker for everyone |
| M3 | P2 | graph.py | S | `sample_function` crashes (uncaught `TypeError`) on any expression that auto-simplifies to a constant; contained today but mislabels the error and wastes a pool respawn |
| M4 | P3 | algebra.py | S | Cosmetic: `x = \pm 1 i` should be `x = \pm i` |

**Bottom line:** the RCE sandbox, geometry validation, executor cancellation-safety, and
float-precision containment are all genuinely solid and re-verified today. The one finding
that matters most for a "math powerhouse" trust claim is **M1** — it is exactly the
"confident wrong verified answer with no LLM cross-check" failure mode the audit was
scoped to hunt, it requires no adversarial input to trigger (an ordinary student writing
"solve for e" is enough), and it should be fixed before launch.
