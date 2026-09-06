# Recall — Post-Stream Math Fence Rewrite / Physics Templates Review (Sep 2026)

Scope: **only** the post-stream fence-rewrite/validate/append engine
(`services/math_fence.py`), its call site and timeout/exception fallback in
`services/chat/stream_pipeline.py`, and the physics template layer
(`services/physics_solver.py`, `services/math_tools/physics.py`) plus the
verified-block builders that feed `math_fence.py` its trusted numbers
(`services/math_tools/block/{physics,geometry,graph,algebra,discrete,common}.py`).
The pre-stream heuristic-injection layer, mobile rendering, and chat
streaming transport are explicitly out of scope except where they explain
the post-stream data flow. This follows up on
`docs/OUTPUT_FORMAT_REVIEW_2026-09-05.md`, which reviewed fence
classification/dispatch and Pydantic-validation discipline more broadly and
found the geometry/graph Pydantic gate in `math_fence.py` sound (its O1/O2
findings were about the unrelated `places`/`vocab_quiz` fences) — this
review does not re-litigate that verdict; it goes one level deeper into the
same file's rewrite/append/cap/timeout logic and into the physics formulas
that logic trusts.

Reviewed at `main` tip `6da97671` (2026-09-06); `math_fence.py` /
`physics_solver.py` / `math_tools/physics.py` last touched by `b060bee5`
(2026-09-01) — verified via `git log`. SymPy 1.14.0,
`/workspace/apps/api/.venv/bin/python`.

---

## A. Verdict

**The fence-rewrite engine's core promise — "the model's own numbers are
never trusted once we have the real computed values" — holds for every
fence *within* the per-kind cap, and the canonical-fence/canonical-answer
pairing that feeds it is architecturally incapable of drifting apart**
(both come from one `PhysicsResult`/geometry-result object inside a single
`_diagram_block`/`_finish_with_answer` call — traced end to end, confirmed
with a passing physics fixture test). Schema validation via
`GeometryBlockSpec`/`GraphBlockSpec`/`*GeometryBlockSpec.model_validate`
is real and actually gates what reaches the client for every fence the cap
lets it touch. Number formatting is float-noise-safe (`:g`/`:.2f`
throughout) and fractions come back reduced (SymPy's own `Rational`
normalizes this before `math_fence.py` ever sees a number) — I could not
construct a case with visible floating-point noise or an unreduced
fraction.

**Everything else this review was asked to check turned up real, concrete,
reproducible bugs — several of them "wrong verified physics answer"
findings the task brief says to treat as P0/P1 regardless of trigger
rarity, and I reproduced all of them by running the actual code, not by
inspection.** Two are in the physics *extractor* (not the solver, which is
formula-correct everywhere I hand-checked it): the kinematics extractor
never flips the sign of `v0` for "thrown downward" / "thrown down" /
"launched downward" — three of its own listed trigger cues — so a
downward throw silently gets the *upward* answer (**F1**, P0); separately,
one of its velocity-keyword strings is the bare word `"at"`, which matches
as a **substring inside ordinary English words** (`"What"`, `"later"`,
`"that"`), so the extremely common phrasing "A ball is dropped from 20m.
**What** is its velocity after 3 seconds?" silently binds the drop height
(20) to the initial velocity instead of 0, and the "verified" answer comes
out wrong by a large margin (**F2**, P0). A third, adjacent gap: no
kinematics op checks whether the object has already hit the ground before
the requested time, so "height/velocity after N seconds" past impact
returns a negative height or a still-accelerating velocity as a flatly
stated verified fact (**F3**, P1). A fourth is a scope gap presented as a
verified answer rather than an honest "can't verify this": `work = F·d`
never has an angle term and the extractor has no bail-out for it (unlike
the force extractor's explicit friction/tension bail-out), so "10 N pulls
a box 5 m at 30°" is confidently answered 50 J instead of 43.3 J (**F4**,
P1).

On the fence-rewrite side specifically: the post-stream call's own
timeout/exception fallback (`replace_unclosed_graph_fence_safe`) only
repairs a truncated **unclosed** graph fence — on a timeout it does
**not** re-validate/replace any closed `` ```geometry ``/`` ```graph
``/`` ```answer `` fence the model already emitted, and does **not**
append the canonical fences the docs say the client "always gets" (**F5**,
P1) — there is no test anywhere in the suite for this path. And the
per-kind rewrite cap (`_MAX_GEOMETRY_FENCES=4`/`_MAX_GRAPH_FENCES=2`/
`_MAX_ANSWER_FENCES=4`) does not just leave the (N+1)th fence
*unverified* the way I expected going in — it leaves it **completely
unvalidated**, including literally malformed JSON, which the file's own
existing test already documents and accepts (`test_validate_math_fences_
caps_per_kind` asserts the surviving fence is still counted as `` ```
geometry ``/`` ```graph `` in the output) — there is no fallback to "Could
not render that diagram" and no textual/visual unverified marker for that
one fence, unlike every sibling fence within the cap (**F6**, P1).
Finally, a smaller defense-in-depth gap: if a `canonical_fence` dict ever
failed its own Pydantic schema (unreachable today — every call site passes
`model_dump()` of an already-validated instance — but checked per the
brief's "what if" instruction), the geometry substitution path writes it
to the client with **zero** validation, and the graph path's
`ValidationError` branch also falls through to writing the invalid JSON
verbatim rather than the "could not render" fallback used everywhere else
in the file (**F7**, P2, reproduced against both paths).

None of this is a sweeping indictment of the file's design — the cap, the
Pydantic gate, and the canonical-fence/canonical-answer pairing are all
sound *ideas*, correctly implemented for the path they were built for. The
bugs are specific, located, and independently fixable; none requires a
redesign.

---

## B. What's working (don't "fix" these)

- **Canonical-fence/canonical-answer fidelity cannot drift apart by
  construction.** Every `_diagram_block(lines, spec, answer)` /
  `_finish_with_answer(lines, answer)` call in
  `math_tools/block/{physics,geometry,graph,algebra,discrete}.py` builds
  both the diagram spec and the answer string from the *same* just-computed
  result object in one function (`math_tools/block/common.py:69-84`) — there
  is no code path where `canonical_fence` and `canonical_answer` are
  populated from two different solves. Confirmed with a runnable fixture
  (`test_appends_answer_and_graph_for_physics`,
  `tests/services/test_math_fence.py:569-585`) and by reading every block
  builder in scope; none constructs the pair from separate data.
- **Pydantic gating is real for every fence inside the cap.**
  `_validate_geometry` (`math_fence.py:81-113`) dispatches on `type` to one
  of eight `*GeometryBlockSpec` models; the graph path calls
  `GraphBlockSpec.model_validate` at three separate call sites
  (`math_fence.py:369,470,482`). I fed both a syntactically valid-but-wrong
  geometry payload and outright broken JSON through `validate_math_fences`
  and confirmed the corrupted/invalid ones inside the cap always degrade to
  `"Could not render that diagram."`, never to a partial or malformed fence.
- **Number formatting is float-noise-safe.** Every numeric answer in
  `physics_solver.py` and `math_tools/block/geometry.py` goes through `:g`
  or `:.2f` before it reaches a string — I could not produce visible
  floating-point noise (e.g. `0.1+0.2` style artifacts) in any answer or
  geometry label; Python's `:g` rounds to 6 significant digits by
  construction, which absorbs the class of noise this format could show.
- **Fractions come back reduced.** `math_service.solve_equation(EquationInput(
  lhs="1/2+1/3", rhs="x", ...))` returns `x = \frac{5}{6}` — SymPy's
  `Rational` normalizes before `math_fence.py`/the block builders ever see a
  number; I could not construct an unreduced-fraction case.
- **Densify protects even *unverified* sparse graphs, not just canonical
  ones.** Fed three model-emitted (non-canonical) `` ```graph `` fences with
  deliberately wrong/hallucinated `points` arrays but a correct `expr`; the
  first two (within the `_MAX_GRAPH_FENCES=2` cap) were silently
  **resampled from their own real `expr`** by `densify_sparse_graph`,
  discarding the fake points and replacing them with correctly computed
  ones — a stronger safety net than "canonical-only" for the common case of
  a sparse-but-correctly-labeled curve.
- **Projectile range, max height, F=ma, KE, PE all matched hand
  calculation exactly.** `solve_projectile`'s `R = v0² sin(2θ)/g` and
  `H = v0² sin²(θ)/(2g)` (`physics_solver.py:188,196`) and `solve_force`'s
  three F/m/a branches (`:244-267`) and `solve_energy`'s KE/PE branches
  (`:280-293`) reproduced the textbook formula to the last decimal for
  every input I tried, including 45°/30° projectile angles and F/m/a in
  all three "solve for the missing one" directions.
- **The force extractor explicitly declines what it can't solve**, and
  that pattern should be the template for the energy extractor's gap
  (F4): `test_force_does_not_claim_unsupported_friction_or_tension`
  (`tests/services/test_physics_extractors.py:178-183`) — "friction"/
  "tension" cues correctly return `None` rather than silently answering
  with the wrong (F=ma-only) formula. This is exactly the discipline the
  `work` op in the energy extractor is missing for "at an angle" (F4).
- **`solve_kinematics` correctly rejects non-positive gravity**
  (`physics_solver.py:84-85`, `g <= 0` → `MathServiceError`) — a user typo
  of `g = -9.8` fails closed with a caught, logged, non-fatal skip rather
  than silently flipping the whole trajectory upside down.
- **The trajectory graph's ground-clamp is physically correct, not a
  bug.** `solve_kinematics`/`solve_projectile` clamp `hi`/`yi` to `0.0`
  once the object would go underground (`physics_solver.py:141-144,
  214-216`) so the plotted curve flatlines at the ground after impact
  instead of continuing through it — this is the right rendering choice
  for "time to ground" and does not contradict the *answer* value (which
  is exactly the landing time). Contrast with F3, which is about a
  *different* op (`position`/`velocity` "after N seconds") that has no
  equivalent clamp on the returned *number*.
- **The 99-test suite in scope passes outright** — see §C's exact command
  and output. Nothing here is "the tests are lying"; the gaps found are
  in scenarios the suite does not exercise at all (documented per-finding).

---

## C. Swept and clean — specific hypotheses checked, no bug found

The task brief asked several pointed "does X happen" questions. Recorded
here so the next reviewer doesn't have to re-derive them:

| Hypothesis | Checked how | Result |
|---|---|---|
| Diagram (`canonical_fence`) and answer pill (`canonical_answer`) show different numbers for the same problem | Read every `_diagram_block`/`_finish_with_answer` call site; ran `test_appends_answer_and_graph_for_physics` | **No** — architecturally same-source, cannot drift (see §B) |
| Floating-point noise in a rendered answer (`3.0000000000001`) | Hand-tried irrational-result geometry/physics inputs; all format through `:g`/`:.2f` | **No** — not reproducible |
| Unreduced fraction (`4/8` instead of `1/2`) | `solve_equation` on `1/2+1/3=x` | **No** — SymPy `Rational` returns `5/6` directly |
| A schema-invalid canonical fence silently crashes `math_fence.py` itself (Python-level exception) | Constructed a canonical dict missing required fields for both `geometry` and `graph` | **No Python exception** — but see F7: it's worse than a crash, it ships the invalid JSON to the client unfiltered |
| Cap boundary just means "the extra fence is left unverified" (with some marker) | Constructed a 3-graph-fence reply with `_MAX_GRAPH_FENCES=2` | **Confirmed, but worse than "unverified with a marker"** — see F6: zero validation, zero marker, indistinguishable from a verified fence |
| Projectile angle > 90° breaks the formula | `solve_projectile` with `angle=120` | Works — `sin(2θ)` correctly goes negative for range past 90°, `t_flight <= 0` guard (`physics_solver.py:184-185`) would catch a genuinely backwards launch |
| "Thrown upward" sign convention itself is wrong | `test_kinematics_thrown_upward` + direct hand calc | **Correct** — `v0` positive for upward matches the `h0 + v0·t - 0.5·g·t²` (up-positive) convention used throughout `solve_kinematics`. The bug is specifically that **downward** never gets the mirrored negative sign (F1) |

---

## D. Findings — ranked

### Physics extractor correctness (wrong verified answers)

---

**F1 — Kinematics extractor never negates `v0` for "thrown downward" / "thrown down" / "launched downward" — three of its own recognized cue phrases — so a downward throw silently gets the upward-throw answer**
**Severity:** P0 · **Area:** physics-extractor · **Effort:** S

**Evidence:**

- `math_tools/physics.py:149-172`, `_KINEMATICS_CUES` explicitly lists
  `"thrown down"`, `"thrown downward"`, `"launched downward"` alongside
  `"thrown upward"`, `"launched upward"` as recognized triggers.
- `math_tools/physics.py:195-202`: `v0` is extracted as a bare magnitude
  from `_find_value_with_unit(..., ("velocity of", "velocity", "speed of",
  "speed", "at", "with", "initial"))` — nothing in the function inspects
  which of the up/down cue phrases matched, and no negation is ever
  applied.
- `physics_solver.py:88`: `h_sym = h0 + v0*t - 0.5*g*t**2` is a single,
  fixed up-positive convention for the whole file (confirmed correct for
  the "upward" case in §C) — it has no separate "downward" branch; it
  relies entirely on the extractor handing it a negative `v0` for a
  downward throw, which never happens.
- **Reproduced directly**, calling `solve_kinematics` with the identical
  `{h0: 20.0, v0: 15.0}` params that both an "upward" and a "downward"
  30 m/s-class phrasing produce:
  ```
  $ .venv/bin/python -c "
  from app.models.math_schemas import MathIntent
  from app.services import physics_solver
  intent = MathIntent(kind='kinematics', physics_op='time_to_ground',
      physics_params={'h0':20.0,'v0':15.0,'g':9.81},
      physics_units={'h0':'m','v0':'m/s','g':'m/s^2'}, operation='solve')
  print(physics_solver.solve_kinematics(intent).answer_value)
  "
  4.06 s
  ```
  Hand-computed correct answers for `h(t) = 20 ± 15t - 4.905t²= 0`:
  upward (`v0=+15`) → **4.06 s** (matches — correct for that case);
  downward (`v0=-15`, the physically correct sign for a downward throw)
  → **1.00 s**. The code returns **4.06 s for both** because the
  extractor hands the solver `v0=+15` regardless of throw direction.
- **No test exercises any "downward"/"down" cue.** `grep -rn "downward\|
  thrown down\|launched downward" app/tests` returns nothing across the
  whole test tree — the three cue phrases that trigger this exact bug are
  completely untested.

**Why it matters:** this is a "wrong verified physics answer," the class
the task brief says to treat as P0 regardless of how the trigger arises.
The extractor's own cue list documents that "thrown downward" is a
first-class, explicitly supported case — a student typing exactly that
phrase gets a confidently stated `Verified answer:` that is off by more
than 4× in this example, with the model instructed ("Do NOT recompute")
not to question it.

**Recommended fix:** in `_extract_kinematics_intent`, after extracting the
`v0` magnitude, check whether any of the "downward"/"down" cue substrings
matched (a small `_DOWNWARD_CUES` tuple mirroring the existing
`_KINEMATICS_CUES` down-entries) and negate `v0` in that case, symmetric
with how "upward" already implicitly gets a positive sign by doing
nothing. Add `test_kinematics_thrown_downward` and
`test_kinematics_launched_downward` asserting `physics_params["v0"] < 0`,
mirroring the existing `test_kinematics_thrown_upward`.

**Do not:** change the solver's `h0 + v0*t - 0.5*g*t**2` convention itself
— it is correct and shared correctly by the projectile solver's `+y`
convention; the fix belongs entirely in the extractor's sign assignment,
not in `physics_solver.py`.

---

**F2 — The kinematics extractor's `"at"` velocity keyword matches as a substring inside ordinary English words ("What", "later", "that"), so a completely standard homework phrasing extracts the wrong `v0`**
**Severity:** P0 · **Area:** physics-extractor · **Effort:** S

**Evidence:**

- `math_tools/physics.py:198-199`: the velocity keyword tuple is
  `("velocity of", "velocity", "speed of", "speed", "at", "with",
  "initial")` — a bare two-letter `"at"`.
- `math_tools/physics.py:40-66`, `_find_value_with_unit`: does
  `lower.find(kw)` — a plain substring search, not a word-boundary regex —
  then searches a 40-character window before/after that index for a
  number+unit.
- **Reproduced directly** with one of the most natural ways to phrase this
  kind of question — a two-sentence "setup, then question" form:
  ```
  $ .venv/bin/python -c "
  from app.services.math_tools.physics import _extract_kinematics_intent
  from app.services import physics_solver
  text = 'A ball is dropped from 20m. What is its velocity after 3 seconds?'
  intent = _extract_kinematics_intent(text)
  print(intent.physics_params)
  print(physics_solver.solve_kinematics(intent).answer_value)
  "
  {'g': 9.81, 'h0': 20.0, 'v0': 20.0, 't': 3.0}
  -9.43 m/s
  ```
  `lower.find("at")` matches inside `"What"` (confirmed: `text.lower().
  find("at") == 30`, landing inside `"...20m. what is..."`); the
  40-character before-window from that position then contains `"20m"`
  (the drop height, from the *first* sentence), which
  `_VALUE_UNIT_RE.search` picks up as the "velocity." The correct `v0` for
  a *dropped* object is `0`, not `20`.
- Removing only the trailing question ("A ball is dropped from 20m,
  height after 5 seconds?" — no `"what"`) extracts the correct `v0=0.0`,
  isolating the cause to the `"at"`-inside-`"What"` collision, not to
  anything else in the sentence:
  ```
  A ball is dropped from 20m, height after 5 seconds? → v0=0.0 (correct)
  A ball is dropped from 20m. What is its height after 5 seconds? → v0=20.0 (wrong)
  A rock is dropped from a 20m cliff. How long...? → v0=0.0 (correct — no "what")
  A stone falls from 30m. Find its height after 1 second. → v0=0.0 (correct — no "what")
  ```
- The resulting "verified" answer (`-9.43 m/s`) is wrong for **two
  compounding reasons**: the extraction bug (`v0` should be `0`, giving
  `v(3) = -29.43 m/s` by the same formula) **and** the ground-crossing gap
  (F3) — the ball, correctly modeled, already landed at `t≈2.02 s`, so
  "velocity after 3 seconds" is asking about a state that doesn't
  physically exist. Either bug alone would make this answer wrong; both
  are present simultaneously in this realistic example.

**Why it matters:** "[Object] is dropped/thrown from [height]. What is
its [velocity/height/position] after [time]?" is one of the single most
common phrasings for exactly this class of homework problem — this isn't
an adversarial or unusual input, it's the two-sentence "setup, then ask"
form any textbook or LLM-generated word problem naturally uses. The bug
fires whenever the word "What" (or "later," "that," or any other common
word containing "at") appears anywhere within 40 characters of a
height/velocity number in the sentence, which is close to "whenever there
is a second sentence."

**Recommended fix:** replace the bare `"at"` entry in the velocity keyword
tuple with a word-boundary-anchored match (e.g. require the character
before and after `"at"` to be non-alphanumeric, similar to the
`(?![A-Za-z0-9/^])` negative lookahead already used in
`_find_value_with_specific_unit`'s regex at `math_tools/physics.py:80`),
or drop `"at"` from the plain-substring keyword list entirely and instead
require it as part of a `\bat\s+\d` regex the way the projectile
extractor's primary path already does (`math_tools/physics.py:282-286`,
which anchors on a *unit* immediately following the number, not a loose
keyword search — that path is not vulnerable to this class of bug and is
the pattern to copy). Add regression tests for the two-sentence
"dropped/thrown... What is its [op] after..." phrasing for all three ops
(`velocity`, `position`, and the default `time_to_ground`).

**Do not:** just delete `"at"` from the keyword tuple without a
replacement — some genuine phrasings ("initial velocity at 15 m/s") rely
on a keyword-based match when the number isn't immediately unit-adjacent;
the fix is to make the keyword match word-bounded, not to remove velocity
detection for `"at"`-based phrasings altogether.

---

**F3 — No kinematics op checks whether the object has already hit the ground before the requested time; "position"/"velocity after N seconds" past impact returns a nonsensical number as a flatly-stated verified fact**
**Severity:** P1 · **Area:** physics-solver · **Effort:** S

**Evidence:**

- `physics_solver.py:117-124` (`op == "position"`) and `:104-116`
  (`op == "velocity"`): both compute `h_val`/`v_val` directly from the
  closed-form kinematic equations with **no check** against the
  object's actual time-to-ground, unlike the *graph* points a few lines
  away in the same function which do clamp (`:141-144`, `if hi < 0: hi =
  0.0` — but that clamp only affects the plotted curve, never the
  returned `answer_value` for `position`/`velocity` ops).
- **Reproduced directly**, using correctly-extracted params (no F1/F2
  bug in play) — a ball dropped from 20 m (`h0=20, v0=0`) lands at
  `t=√(2·20/9.81)≈2.02 s`; asking its position/velocity at `t=5 s` (well
  past landing):
  ```
  $ .venv/bin/python -c "
  from app.models.math_schemas import MathIntent
  from app.services import physics_solver
  intent = MathIntent(kind='kinematics', physics_op='position',
      physics_params={'h0':20.0,'v0':0.0,'g':9.81,'t':5.0},
      physics_units={'h0':'m','v0':'m/s','g':'m/s^2','t':'s'}, operation='solve')
  print(physics_solver.solve_kinematics(intent).answer_value)
  "
  -102.62 m
  ```
  and for velocity at the same `t`: `-49.05 m/s` — i.e. the "verified"
  answer states the ball is 102.62 m *underground*, still accelerating,
  five seconds after being dropped from a 20 m height. There is no
  caveat, no "already landed" note, and `ctx.math_unverified` (the flag
  that triggers `append_unverified_math_note`) is never set for this
  case — it's set only by the *pre-stream* heuristic gate finding no
  matching kind at all (`turn_prep/context.py:596-598`), which is a
  different condition entirely; this path found a matching kind and
  "solved" it, just for a physically impossible scenario.
- No test in `test_physics_solver.py` or `test_physics_extractors.py`
  exercises a `t` value at or beyond the ground-impact time for
  `position`/`velocity` ops.

**Why it matters:** "How far/fast is it after N seconds?" without the
student first checking whether N is before or after impact is exactly the
kind of follow-up question a homework word-problem generator (human or
LLM) produces, especially in multi-part problems ("part a) how long until
it lands; part b) what is its velocity after 3 seconds" where the student
picked 3 without checking against part a's own answer). Recall states the
wrong, physically-impossible number as fact with no verification caveat.

**Recommended fix:** in `solve_kinematics`, for `op in ("position",
"velocity")`, compute the ground-impact time the same way `time_to_ground`
already does, and either (a) raise `MathServiceError` when the requested
`t` exceeds it — falling back to unverified LLM prose the same way a
missing param already does (`op == "position"` with no `t` at
`:120`) — or (b) clamp the returned value to the ground state (height 0,
velocity at impact) and note in `answer_latex` that the object has
already landed. (a) is simpler and matches this file's existing
fail-closed pattern elsewhere (e.g. `g <= 0` at `:84-85`); prefer it
unless product wants the clamp-and-note UX.

**Do not:** silently clamp the number to `0`/impact-velocity with no
indication in the returned `answer_value` — a silently-clamped wrong
number is barely better than today's negative-height number; either
refuse to verify or say so in the answer text.

---

**F4 — `work = F·d` has no angle term and no bail-out for "at an angle" phrasings, unlike the force extractor's explicit friction/tension refusal — a standard angled-force homework problem is confidently answered wrong**
**Severity:** P1 · **Area:** physics-extractor / physics-solver · **Effort:** S

**Evidence:**

- `physics_solver.py:294-300` (`op == "work"`): `w_val = p["F"] * p["d"]`
  — no `cos(θ)` term anywhere in the function; correct only when the
  force is parallel to the displacement.
- `math_tools/physics.py:426-540`, `_extract_energy_intent`: extracts
  mass/velocity/height/force/distance but **never looks for an angle at
  all** for any energy op, and the `elif "work" in lower: op = "work";
  if force is None or distance is None: return None` guard (`:494-497`)
  has no equivalent to the force extractor's explicit refusal for
  friction/tension (`math_tools/physics.py:347-350`, tested by
  `test_force_does_not_claim_unsupported_friction_or_tension`,
  `tests/services/test_physics_extractors.py:178-183`) — there is no
  "angle" cue check that would make this extractor return `None` and
  defer to the (unverified but at-least-not-confidently-wrong) LLM.
- **Reproduced directly**, a canonical angled-work homework phrasing:
  ```
  $ .venv/bin/python -c "
  from app.services.math_tools.physics import _extract_energy_intent
  from app.services import physics_solver
  import math
  text = 'A 10 N force pulls a box 5 m at an angle of 30 degrees above the horizontal. How much work is done?'
  intent = _extract_energy_intent(text)
  print(intent.physics_params)
  r = physics_solver.solve_energy(intent)
  print(r.answer_value)
  print('correct:', round(10*5*math.cos(math.radians(30)), 2), 'J')
  "
  {'F': 10.0, 'd': 5.0}
  50.00 J
  correct: 43.3 J
  ```
  The angle is present in the text, is not extracted at all, and the
  extractor proceeds anyway — a 6.7 J (13%) error stated as `Verified
  answer:`.
- The same gap applies to `power = F·v` (`physics_solver.py:301-307`),
  which has the identical implicit "force parallel to velocity"
  assumption and the identical missing angle extraction/bail-out — lower
  priority to fix first since "power at an angle" homework phrasings are
  less common than "work at an angle," but the same fix pattern applies.

**Why it matters:** "at an angle" work problems are standard intro-physics
curriculum (the very next topic after F=ma and plain W=Fd), and this is
another wrong-verified-answer finding. Contrast with the force
extractor's `friction`/`tension` bail-out immediately above it in the
same file — the pattern for "decline rather than confidently answer
wrong" already exists in this codebase; the energy extractor's `work` op
just doesn't use it.

**Recommended fix:** add an angle cue check (e.g. `"at an angle" in
lower or "angle of" in lower`) to the `work`/`power` branches of
`_extract_energy_intent` and `return None` when present (deferring to
LLM, matching the force extractor's pattern), **or** — the more complete
fix — extract the angle the same way the projectile extractor already
does (`math_tools/physics.py:295-310`) and pass it through
`physics_params["angle"]`, then have `solve_energy`'s `work`/`power`
branches multiply by `cos(radians(angle))` when present (defaulting to 0°
i.e. `cos=1` when absent, preserving today's correct behavior for the
common parallel-force case).

**Do not:** ship the angle-aware formula without also fixing the
extraction gap, or vice versa — either half alone still leaves the other
half of the "10 N at 30°" example silently wrong (extracting the angle
without using it, or using it without ever populating it, both reproduce
today's bug).

---

### Post-stream fence-rewrite integration (`math_fence.py` / `stream_pipeline.py`)

---

**F5 — On a post-stream SymPy timeout or exception, the fallback path repairs only an unclosed graph fence: closed model-emitted geometry/graph/answer fences are never re-validated against canonical, and the promised "always attach the diagram/answer" fences are never appended**
**Severity:** P1 · **Area:** fence-rewrite · **Effort:** S–M

**Evidence:**

- `stream_pipeline.py:255-275`, `enrich_final_content`: the real call is
  ```python
  assistant_text = await run_sympy(
      seams.math_fence_service.validate_math_fences_worker,
      assistant_text, ctx.verified_math,
      timeout=settings.math_solve_timeout_seconds,
  )
  ```
  wrapped in `try`/`except TimeoutError`/`except Exception`, and **both**
  exception branches fall back to:
  ```python
  assistant_text = seams.math_fence_service.replace_unclosed_graph_fence_safe(
      assistant_text, canonical
  )
  ```
- `math_fence.py:378-391`, `replace_unclosed_graph_fence_safe`'s own
  docstring is explicit about its narrow scope: *"SymPy-free fallback for
  an unclosed ```graph fence... a truncated graph fence the model left at
  EOS still needs to be cleaned up... No SymPy, no sampling."* It calls
  only `_replace_unclosed_graph_fence(..., densify=False)`
  (`math_fence.py:328-376`), which explicitly looks only for an **unclosed**
  `` ```graph `` opener (`find_lang_opener`) — it does nothing for a
  closed `` ```geometry ``, closed `` ```graph ``, or any `` ```answer ``
  fence, and it never calls `_append_missing_canonical_fences` (the
  function that attaches the diagram/answer pill the model was told not
  to emit itself).
- Concretely: if the model emitted a **closed** `` ```geometry `` fence
  with hallucinated numbers, and the post-stream solve then times out
  (5s shared SymPy budget, `settings.math_solve_timeout_seconds`, default
  `5.0` — `core/config.py:137`) — e.g. because a graph fence elsewhere in
  the same reply needed an expensive densify resample — that hallucinated
  `` ```geometry `` fence is shipped to the client **exactly as the model
  wrote it**, with the same fence tag a verified one would carry, no
  Pydantic check, no unverified marker. Separately, if this turn's
  `VerifiedMathBlock` had a canonical answer/diagram to attach and the
  model (correctly, per its own prompt instructions) emitted **no**
  fence at all, the timeout path never appends it — the user gets neither
  the model's own attempt nor Recall's verified one; per `docs/math.md`'s
  own claim ("the client always gets a diagram/answer pill"), this is a
  silent contract break specifically on the slow-path, not the happy
  path.
- **No test exercises either exception branch.** `grep -n "TimeoutError\|
  timeout" app/tests/services/test_enrich_final_content.py` returns
  nothing — the file that owns this call site has zero coverage of what
  actually happens to a *closed* fence or a *missing* canonical fence when
  `validate_math_fences_worker` times out or raises.

**Why it matters:** this is the exact "unverified geometry data shown to
the user with no indication it's unverified" scenario the task brief
flags, arising from a documented, intentional design constraint (the
shared 5s budget) rather than a rare edge case — any turn whose *other*
graph fence needs an expensive resample can push the *whole* validation
call over budget, at which point *every* fence in that reply, not just
the slow one, loses its safety net.

**Recommended fix:** on `TimeoutError`/`Exception`, in addition to
`replace_unclosed_graph_fence_safe`, run the cheap, SymPy-free parts of
the safety net that don't need a fresh solve: (1) schema-validate any
*closed* geometry/graph/answer fence against canonical using the already-
computed `ctx.verified_math` (no new SymPy call — `_canonical_replacement`
and `_validate_geometry` are pure Python/Pydantic, not SymPy, so they are
safe to run outside the timeout-guarded call), and (2) call
`_append_missing_canonical_fences` unconditionally in the exception
handler so a missing diagram/answer still gets attached even when the
densify/resample step is what actually timed out. Only the SymPy-dependent
pieces (`densify_sparse_graph`'s resampling, `_sample_function_graph_
from_json`) need to stay out of the no-SymPy fallback.

**Do not:** raise the 5s timeout to "fix" this by making timeouts rarer —
that trades one failure mode for degraded latency on every turn and does
not close the gap for the turns that still do time out; the fix belongs in
what the fallback does, not in avoiding the fallback.

---

**F6 — The (N+1)th fence of a kind beyond the per-kind rewrite cap is shipped to the client with zero schema validation and zero unverified marker — including literally malformed JSON — indistinguishable from a verified fence**
**Severity:** P1 · **Area:** fence-rewrite · **Effort:** S–M

**Evidence:**

- `math_fence.py:58-62`: `_MAX_ANSWER_FENCES = 4`, `_MAX_GEOMETRY_FENCES =
  4`, `_MAX_GRAPH_FENCES = 2`, with the comment *"Shared 5s SymPy budget
  for the whole reply — bound how many fences we rewrite so one long
  message degrades per-fence instead of timing out all."*
- `md_fence_scan.py:94-113`, `map_closed_fences`: `for start, end, body in
  iter_closed_fences(text, lang): if max_count is not None and count >=
  max_count: break` — fences beyond `max_count` are **never passed to the
  `replace` callback at all**; they are copied through verbatim by the
  trailing `pieces.append(text[cursor:])`.
- **Reproduced directly**, appending a 3rd model-emitted `` ```graph ``
  fence beyond the `_MAX_GRAPH_FENCES=2` cap, with no canonical fences
  provided at all (`verified=None`):
  ```
  $ .venv/bin/python -c "
  from app.services.math_fence import validate_math_fences
  import json
  content = ('Part 1...\n\n\`\`\`graph\n' + json.dumps({'type':'function','expr':'x^2','variable':'x','x_min':-10.0,'x_max':10.0,'points':[[i,i*i] for i in range(-10,11)]}) + '\n\`\`\`\n\n'
    + 'Part 2...\n\n\`\`\`graph\n' + json.dumps({'type':'function','expr':'x^3','variable':'x','x_min':-10.0,'x_max':10.0,'points':[[1,999],[2,999]]}) + '\n\`\`\`\n\n'
    + 'Part 3 (should be capped)...\n\n\`\`\`graph\n' + json.dumps({'type':'function','expr':'x^4','variable':'x','x_min':-10.0,'x_max':10.0,'points':[[1,-12345],[2,-12345]]}) + '\n\`\`\`')
  print(validate_math_fences(content, verified=None))
  " | tail -6
  ```
  The first two `` ```graph `` fences (within the cap) got picked up by
  `densify_sparse_graph` and had their sparse/wrong `points` arrays
  **resampled from the real `expr`** (a nice side benefit, see §B) — but
  the third fence's obviously-fake `[[1,-12345],[2,-12345]]` payload was
  emitted completely untouched, character for character.
- The file's **own existing test already documents and accepts this
  exact shape** for the case of *invalid* JSON, which is the more
  dangerous variant: `test_validate_math_fences_caps_per_kind`
  (`tests/services/test_math_fence.py:484-497`) feeds
  `_MAX_GEOMETRY_FENCES + 1` copies of `` ```geometry\n{bad json\n``` ``
  (deliberately malformed — an unterminated JSON object) and asserts
  `out_geo.count("Could not render that diagram") == _MAX_GEOMETRY_FENCES`
  **and** `out_geo.count("```geometry") == 1` — i.e. the test explicitly
  confirms that the one fence beyond the cap keeps its raw, syntactically
  broken `` ```geometry `` body verbatim, with the same fence tag a
  successfully-validated one carries.
- There is **no visual or textual distinction** anywhere in the output
  string for that surviving fence — same three backticks, same `geometry`/
  `graph` language tag, same position in the document a client-side
  renderer would treat identically to a verified one.

**Why it matters:** the task brief's exact concern — "a long multi-part
homework answer could show a mix of verified and silently-unverified
diagrams with no visual distinction" — is confirmed, and the cap's own
existing test shows the failure mode is actually worse than "unverified":
for fences beyond the cap, even the schema-validation step that would
normally degrade broken JSON to a safe "Could not render" prose note
never runs, so literally malformed JSON (an unterminated object, in the
existing test's own fixture) reaches whatever renders `` ```geometry ``/
`` ```graph `` fences client-side with no server-side safety net at all —
a materially different (and worse) risk profile than a merely-unverified
fence.

**Recommended fix:** two complementary changes: (1) even beyond
`max_count`, still run the cheap, already-available schema validation
(`_validate_geometry` / `GraphBlockSpec.model_validate`) on the
surviving fences so malformed JSON degrades to "Could not render" the
same as it does within the cap — this does not need a fresh SymPy call,
only the existing Pydantic check, so it does not touch the 5s budget
`_MAX_*_FENCES` was designed to protect; (2) for fences beyond the cap
that *do* pass schema validation (well-formed but unverified — the model
followed the JSON shape correctly but Recall didn't have budget to
cross-check the numbers), attach a short, honest note (reusing the
existing `_UNVERIFIED_MATH_NOTE` pattern, e.g. "additional diagrams
below weren't double-checked") rather than silence.

**Do not:** raise `_MAX_*_FENCES` to "fix" this by making the cap less
likely to bind — that increases worst-case SymPy time per reply, which is
exactly the risk the cap exists to bound; the fix is in what happens to
the fences beyond the cap, not in moving the cap.

---

### Defense-in-depth (currently unreachable, but checked per the brief)

---

**F7 — If a `canonical_fence` dict ever failed its own Pydantic schema, the geometry substitution path writes it to the client with zero validation, and the graph path's `ValidationError` branch also falls through to writing the invalid JSON verbatim instead of "Could not render"**
**Severity:** P2 (defense-in-depth; not reachable via any call site read in
this review) · **Area:** fence-rewrite · **Effort:** S

**Evidence:**

- `math_fence.py:455-476`, `_replace_fence`: `corrected =
  _canonical_replacement(...)`; if not `None`:
  ```python
  if label != "graph":
      return f"```{label}\n{corrected}\n```"   # geometry/answer: no validation at all
  try:
      parsed = GraphBlockSpec.model_validate(json.loads(corrected))
  except (json.JSONDecodeError, ValidationError, TypeError):
      return f"```{label}\n{corrected}\n```"   # graph: still writes the invalid JSON on failure
  ```
- **Reproduced directly** for both branches — a `canonical_fence` missing
  a required field for its own declared `type`:
  ```
  $ .venv/bin/python -c "
  from app.services.math_fence import validate_math_fences
  from app.services.math_tools import VerifiedMathBlock
  import json
  malformed = {'type':'rectangle','unit':'cm'}  # GeometryBlockSpec requires width+height
  v = VerifiedMathBlock(text='hint', canonical_fence=malformed, canonical_answer=None)
  content = '\`\`\`geometry\n' + json.dumps({'type':'rectangle','width':4,'height':5,'unit':'cm'}) + '\n\`\`\`'
  print(validate_math_fences(content, verified=v))
  "
  \`\`\`geometry
  {"type": "rectangle", "unit": "cm"}
  \`\`\`
  ```
  and confirmed independently that this exact dict fails
  `GeometryBlockSpec.model_validate` with *"rectangle requires width and
  height"` — yet it was written to the client verbatim. The equivalent
  graph-path repro (a `type: function` canonical dict missing the
  required `expr` field) produces the identical result: the invalid dict
  is written, not `"Could not render that diagram."`.
- **Not reachable today**: every call site that populates
  `canonical_fence` in scope goes through `_diagram_block`'s
  `dump = spec.model_dump() if hasattr(spec, "model_dump") else spec`
  (`math_tools/block/common.py:79`), and every caller I found in
  `math_tools/block/{physics,geometry,graph,algebra}.py` passes an actual
  Pydantic model instance, never a raw dict — so `model_dump()` always
  runs and the dump is always schema-valid by construction. The `else
  spec` branch exists but nothing currently exercises it with a raw dict.

**Why it matters:** this is the one place in `math_fence.py` where "the
canonical fence is trusted absolutely, no re-check" is load-bearing on an
invariant enforced only by convention (every block builder happens to
pass a validated model) rather than by the file itself. Everywhere else
in this file, a validation failure degrades to a safe placeholder; this
is the one path where a future block builder that constructs
`canonical_fence` from a raw dict (the `else spec` branch already exists
for exactly that possibility) would silently regress this file's own
safety invariant, and the failure mode is "ship whatever the malformed
canonical dict says to the client," not a crash that would get noticed in
a stack trace.

**Recommended fix:** in `_canonical_replacement`'s callers (`_replace_
fence`), validate the *canonical* fence against the matching schema
before substituting it — for `geometry`, run it through
`_validate_geometry`'s same dispatch; for `graph`, the code already
attempts `GraphBlockSpec.model_validate` but should degrade to `"Could
not render that diagram."` on failure instead of writing the invalid JSON
through in the `except` branch (a one-line change — replace the
`return f"```{label}\n{corrected}\n```"` fallback with the same "could
not render" string used elsewhere in the file).

**Do not:** add this validation as a hot-path SymPy call — this is a pure
Pydantic check (already imported in this file), so it costs microseconds
and does not touch the 5s SymPy budget that F5/F6's fixes are careful to
respect.

---

### Minor / logging quality

---

**F8 — `solve_force` raises a raw `ZeroDivisionError` for zero mass/zero acceleration instead of the domain's own `MathServiceError`, landing in the noisier "unexpected" log branch instead of the clean "skipped" one**
**Severity:** P3 · **Area:** physics-solver · **Effort:** XS

**Evidence:**

- `physics_solver.py:244-267`, `solve_force`: `a_val = p["F"] / p["m"]`
  (and the `m = F/a` branch) has no zero-check, unlike
  `solve_kinematics`'s explicit `if g <= 0: raise MathServiceError(...)`
  (`:84-85`).
- **Reproduced:** `solve_force` with `{"F": 20.0, "m": 0.0}` raises
  `ZeroDivisionError: float division by zero`, not `MathServiceError`.
- `math_tools/block/physics.py:30-47`, `_build_physics_block`: this is
  caught (not a crash) by the broad `except Exception:` branch, logged at
  `WARNING` with `"physics verification failed"` and `exc_info=True`,
  and the block builder correctly returns `None` (deferring to
  unverified LLM prose) — the same safe outcome as the `except
  MathServiceError` branch just above it, just noisier in the logs and
  without the domain-specific message.

**Why it matters:** purely a diagnostics/log-hygiene issue — there is no
user-facing wrong-answer risk here (the broad `except Exception` already
makes this safe), and a mass of exactly `0` is unlikely to be extracted
from realistic phrasing (`_extract_force_intent` requires a unit-anchored
`kg|g|mg|lb|lbs|oz` match, so a user would have to write "0 kg mass"
verbatim). Included for completeness per the brief's domain-restriction
checklist, not because it poses real risk.

**Recommended fix:** add `if p.get("m") == 0: raise MathServiceError("mass
must be nonzero")` (and the equivalent for `a == 0` in the `m = F/a`
branch) alongside the existing `g <= 0` check, so this lands in the same
clean, INFO-level "physics verification skipped" log path as every other
expected-rejection case.

**Do not:** treat this as urgent or bundle it with F1–F7 in the same fix —
it's an independent, one-line, zero-risk cleanup.

---

## E. Weak / unwanted / missing inventory

| Item | Status | Evidence | Recommend |
|---|---|---|---|
| Canonical-fence / canonical-answer same-source pairing | **Solid** | `math_tools/block/common.py:69-84`; every block builder | Keep as-is |
| Pydantic gating inside the per-kind cap | **Solid** | `math_fence.py:81-113,369,470,482` | Keep as-is |
| Number formatting (`:g`/`:.2f`) | **Solid** | no float noise reproducible across geometry/physics | Keep as-is |
| Fraction reduction | **Solid** | SymPy `Rational` normalizes before this layer | Keep as-is |
| Densify protection for unverified sparse graphs | **Solid, a nice bonus** | reproduced — fake points replaced by real resample within the cap | Keep as-is |
| Projectile / F=ma / KE / PE formulas | **Solid** | matched hand calc for every input tried | Keep as-is |
| Force extractor's friction/tension bail-out | **Solid — the template to copy for F4** | `tests/services/test_physics_extractors.py:178-183` | Keep as-is; copy the pattern into the energy extractor (F4) |
| Kinematics "thrown downward"/"thrown down"/"launched downward" sign | **Broken** — same magnitude as upward | `math_tools/physics.py:149-172,195-202`; reproduced | Fix (F1) |
| Kinematics `"at"` velocity keyword | **Broken** — substring-matches inside "What"/"that"/"later" | `math_tools/physics.py:198-199`; reproduced | Fix (F2) |
| Kinematics `position`/`velocity` ops past ground impact | **Broken** — no domain check, returns negative depth as fact | `physics_solver.py:104-124`; reproduced | Fix (F3) |
| Energy `work`/`power` at an angle | **Broken** — no angle term, no bail-out | `physics_solver.py:294-307`; `math_tools/physics.py:426-540`; reproduced | Fix (F4) |
| Post-stream timeout/exception fallback scope | **Weak** — repairs only unclosed graph fences | `stream_pipeline.py:255-275`; `math_fence.py:378-391` | Fix (F5) |
| Per-kind rewrite cap boundary (fences beyond `_MAX_*_FENCES`) | **Weak** — zero validation, zero marker, own test documents it | `md_fence_scan.py:94-113`; `tests/services/test_math_fence.py:484-497`; reproduced | Fix (F6) |
| Canonical-fence self-validation before substitution | **Weak (unreachable today)** | `math_fence.py:455-476`; reproduced | Fix (F7) |
| `solve_force` zero-mass/zero-accel handling | **Weak (log hygiene only)** | `physics_solver.py:244-267`; reproduced | Fix (F8) |
| `test_math_fence.py`/`test_physics_solver.py`/`test_physics_extractors.py`/`test_math_graph_pair.py` (99 tests) | **All passing** | see §F command output | Keep running; add the tests named in F1–F6 |

---

## F. Test run (exact command + output)

```
$ cd /workspace/apps/api && .venv/bin/python -m pytest \
    app/tests/services/test_math_fence.py \
    app/tests/services/test_physics_solver.py \
    app/tests/services/test_physics_extractors.py \
    app/tests/services/test_math_graph_pair.py -v

============================= test session starts ==============================
platform linux -- Python 3.13.15, pytest-9.1.1, pluggy-1.6.0
collected 99 items

... (99 tests, all PASSED — full names in transcript) ...

============================== 99 passed in 3.22s ==============================
```

All 99 pre-existing tests pass; every bug in §D was found in scenarios
**not** covered by this suite (confirmed by `grep` for the relevant cue
words/paths returning nothing in the test tree, cited per-finding above),
not by a failing test.

---

## G. Sequenced fix plan

One concern per PR, matching this codebase's own execution discipline.

1. **`fix(api): negate v0 for downward kinematics throws`** — F1. Smallest,
   most isolated; add the two named regression tests.
2. **`fix(api): word-bound the kinematics 'at' velocity keyword`** — F2.
   Independent of F1; both touch `_extract_kinematics_intent` but different
   lines — land separately so each is bisectable.
3. **`fix(api): reject kinematics position/velocity queries past ground
   impact`** — F3. Independent; touches `solve_kinematics`'s `position`/
   `velocity` branches only.
4. **`fix(api): bail out of (or extend) the work/power angle gap in the
   energy extractor`** — F4. Independent; pick the "extract angle" variant
   over the "bail out" variant only if product wants angled-work verified
   rather than deferred to the LLM.
5. **`fix(api): run schema-validate-against-canonical and append-missing
   in the post-stream timeout/exception fallback`** — F5. Land after 1–4
   so the physics fixes it might expose don't get confused with this
   change's own review.
6. **`fix(api): schema-validate fences beyond the per-kind rewrite cap`**
   — F6. Independent of F5 though they're both in `math_fence.py`/
   `md_fence_scan.py` — keep as separate PRs since one is about the
   timeout path and the other about the count-cap path.
7. **`fix(api): degrade to "could not render" on canonical-fence schema
   failure instead of writing invalid JSON`** — F7. Small, independent,
   no behavior change on any reachable path today.
8. **`fix(api): raise MathServiceError for zero mass/acceleration in
   solve_force`** — F8. Trivial, independent, log-hygiene only.

---

## H. Explicit non-goals

Considered and deliberately not raised as findings:

- **Re-litigating `docs/OUTPUT_FORMAT_REVIEW_2026-09-05.md`'s O1
  (`places` fence) / O2 (`vocab_quiz`) findings.** Out of this review's
  named scope (geometry/graph/answer post-stream rewrite and physics
  templates only); that review's verdict on the geometry/graph Pydantic
  gate itself is confirmed correct here, not re-derived from scratch.
- **The pre-stream heuristic-injection layer** (`math_tools/extract.py`'s
  intent-ordering, the system-prompt hint text, camera OCR). Explicitly
  assigned to a different reviewer per the task brief; this review only
  read enough of `math_tools/block/*` to establish where `canonical_fence`/
  `canonical_answer` come from, not to audit intent extraction for the
  non-physics kinds (equation, geometry-shape, calculus, etc.).
- **The shared, process-wide `ProcessPoolExecutor(max_workers=1)`
  (`sympy_executor.py`) that both the pre-stream heuristic solve and this
  post-stream fence validation submit to.** I confirmed both layers submit
  to the *same* singleton pool (`get_sympy_executor()`), which means a slow
  turn's post-stream densify can, in principle, queue behind or compete
  with a concurrent request's pre-stream solve — this is a cross-request
  concurrency/perf question about the executor itself, not about the
  fence-rewrite logic in scope here, and belongs with a jobs/infra-style
  review (see `docs/BACKGROUND_JOBS_INFRA_REVIEW_2026-09-06.md` for that
  review's methodology) rather than this one.
- **Mobile-side rendering of `` ```geometry ``/`` ```graph `` JSON**
  (`GeometryBlock`/`FunctionGraphBlock`, crash-fallback SVG). This review
  traced the data *up to* what `math_fence.py` writes into the assistant
  message string; whether the mobile renderer crashes, silently drops, or
  gracefully degrades on a malformed fence that reaches it (relevant to
  F6/F7) is a separate, mobile-side question this review did not verify
  by running the mobile app.
- **Negative-mass / negative-time inputs reaching the solver from
  realistic user phrasing.** Checked and noted only in passing (F8's
  evidence) — the regex extractors' unit-anchored patterns make a
  genuinely negative extracted mass or a negative "after N seconds" time
  unlikely from normal phrasing (nobody types "a mass of -5 kg" or "after
  -2 seconds" in a homework question), so this was not elevated to a
  standalone finding the way F1–F4 were (all four of which fire on
  ordinary, common phrasings).
- **Physics kinds beyond the six templates in scope** (friction, tension,
  momentum/collisions, rotation, circuits, waves, thermodynamics,
  relativity) — `docs/math.md`'s own "School-homework gaps" section
  already documents these as intentionally LLM-only, out of scope by the
  product's own design, not a gap in this review's target.
