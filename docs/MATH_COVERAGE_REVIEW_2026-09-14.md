# Recall — Math Review: coverage, level awareness, and how it answers (Sep 2026)

Three questions, asked of the math pipeline as a whole: **is the maths covered,
does the system know who it is talking to, and does it answer the way a
knowledgeable person would?** Probed by driving the real pre-stream pipeline
(`needs_symbolic_math` → `extract_math_intent` → `_build_verified_block` →
`maybe_direct_math_reply`), not by reading it.

Findings first, then what was fixed, then what is deliberately left.

## Overall verdict

The verified core is strong and the formatting discipline is unusually good.
Two things were not:

1. A **confidently wrong answer** was reachable — the worst outcome this
   architecture can produce, because a verified block tells the model not to
   recompute. Fixed.
2. The system has **no idea who it is talking to**, and its one relevant signal
   (`response_style`) was ignored on the path most math takes. Partly fixed.

## Findings

### 1. Second-order ODEs were certified wrong (fixed)

`solve y'' + y = 0` reached the algebra extractor, which took the equation as
`+ y = 0` — the `y''` silently dropped — solved the remnant, and published:

```
[BEGIN VERIFIED MATH]
Equation: y = 0
Verified result: y = 0
[END VERIFIED MATH]
```

The block no longer mentions a derivative at all, and the prompt instructs the
model to use verified numbers and not recompute. `y'' - y = 0` and
`y'' + 4y = 0` behaved the same. Reproduced identically on `88e75e9`, so it
predates the domain-package move.

### 2. Coverage: the enum says 36 kinds, the gate decides

`MathIntent.kind` lists 36 kinds and `needs_symbolic_math` is the real
boundary. What passes it is genuinely broad — algebra, calculus including
limits and series, 2D and 3D geometry, trig, coordinates and vectors,
statistics, combinatorics, number theory, matrices, complex numbers, units,
and four physics kinds. Logs, exponentials and fraction arithmetic all work.

What does not gate at all, and so gets **no verification** — accuracy is
whatever the model manages unaided:

| Topic | Probe | |
|---|---|---|
| Percentages | `increase 200 by 12%`, `what percent of 50 is 12` | ✗ (only `15% of 80` works) |
| Ratio / proportion | `split 120 in the ratio 2:3` | ✗ |
| Sequences | `10th term of 3, 7, 11, 15`, `sum of the first 20 even numbers` | ✗ |
| **Word problems** | `Tom has twice as many apples as Ann…` | ✗ |
| Financial | `compound interest on 1000 at 5% for 3 years` | ✗ |
| Set / logic | `union of {1,2,3} and {3,4}` | ✗ |

Word problems are the largest uncovered class and most of school maths.
Percentages, ratio and sequences are the everyday core for ages 11–16.

### 3. There is no notion of the user's level — and it is actively suppressed

No `level` field on `User`. No mention of grade, level, or age anywhere in the
math path. `math/school.py` is a *topic* bucket ("school ops beyond calc I"),
not a learner level.

The only two hits in the whole math and tone surface push the other way:

- `reply_policy.py` — *"A deadline or **difficulty** alone is not a request for
  a full worked solution"*
- `prompt_constants/format.py` — *"Never invent a '**beginner** choice' section"*

A stated level can reach the prompt by accident, as a memory fact, but nothing
tells the model to calibrate mathematical depth to it.

### 4. The one real signal was ignored where it mattered (fixed)

`response_style` (`short` | `balanced` | `detailed`) already exists and already
shapes the system prompt. But most math never reaches the model: a verified,
short answer goes straight to screen through `maybe_direct_math_reply`, and
that path did not consult `response_style` at all.

So a user who had explicitly asked for detailed answers still got:

```
```answer
x = 2 \text{ or } x = 3
```
```

for `x^2 - 5x + 6 = 0`, with no way to see the working except to spend a second
turn asking "how?".

## What changed

| Change | Effect |
|---|---|
| `solve_ode` generalized to linear ODEs with terms on both sides | `y'' + y = 0` → `C₁sin(x) + C₂cos(x)`; also mixed order and inhomogeneous right-hand sides |
| Guard: algebra may not claim an equation leaving a derivative behind | `y'''' + y = 0` yields no block; the model answers unverified, honestly |
| `factored_key_step` + `VerifiedMathBlock.key_step` | the factorization behind a root, computed by SymPy |
| `maybe_direct_math_reply` takes `response_style` | `short` unchanged; `balanced` shows the key step; `detailed` hands the turn to the model |
| `MATH_REPLY_POLICY` defers to the length preference | DETAILED now counts as asking for the working |

`x^2 - 5x + 6 = 0` at the default `balanced` style now answers:

```
Factors as $(x - 3)(x - 2)$.

```answer
x = 2 \text{ or } x = 3
```
```

One step problems stay bare in every style — `2x + 7 = 19` and `2 + 2` get no
lead-in, because a knowledgeable person does not explain those.

### Why the guard is scoped to derivative marks

The first version was general: *if any math is left over after blanking the
extracted equation, refuse*. It failed 15 existing tests, and the failures were
the point — the residue legitimately holds qualifiers like `Solve for x:`,
`for 0<=x<=2*pi` and `with a proof`, which are not dropped maths.

A true round-trip check needs the extractor to **report the span it consumed**.
Until it does, a general check cannot tell a dropped term from a qualifier.
That is the follow-up, and it would retire a whole bug class rather than one
signature.

## What is deliberately left

1. **Word problems** — the largest uncovered class. A model-extracted intent
   validated by Pydantic and then solved by SymPy would bring verification to
   it, and is the single highest-value thing left in the math pipeline.
2. **A real level signal.** `response_style` is a *length* preference standing
   in for a *level* one; they are not the same. Someone can want short answers
   and still be learning. This needs a product decision first — an inferred
   level is error-prone, a user-set one is honest but needs UI — so it was not
   invented here.
3. **The everyday gaps** — percentages beyond `X% of Y`, ratio, sequences.
   Cheap extractors on the existing seam.
4. **Key steps beyond factorization.** Only polynomial equations carry one.
   Systems, calculus and trig could each name their step (elimination, the
   power rule, the identity used) with the same mechanism.
5. **The general round-trip guard**, per the note above.
