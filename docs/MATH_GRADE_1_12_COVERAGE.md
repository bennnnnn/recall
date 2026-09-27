# Grade 1–12 mathematics coverage

This is a capability audit of the running Recall pipeline, not a list of topics a chat model can
discuss. The code and tests are the source of truth. A topic changes status only when its
extractor, solver, trace, presentation, and regression tests justify the change.

## Status vocabulary

| Status | Product meaning |
|---|---|
| **VERIFIED** | The server deterministically extracts and checks the complete requested result. Presentation must preserve that result. |
| **VERIFIED + PROCEDURE** | The server also owns the ordered school method or derivation. The model may explain the trace but may not recreate it. |
| **TEACH** | Recall can explain the topic using verified facts or examples, but the free-form explanation itself is not certified as a solver trace. |
| **LLM-ONLY** | Conceptual, construction, or proof work is handled as ordinary tutoring prose and must not receive a verification claim. |
| **MISSING** | The current student-facing behavior is not yet reliable or complete enough to claim coverage. |

`VERIFIED` is deliberately narrower than “SymPy knows this.” Extraction must consume the whole
request. A failed or partial extraction falls back without a verification chip.

## Grade-by-grade audit

Curricula vary by country and school. These rows describe the usual grade band and the Ethiopian
Grade 8–10 chapter lists supplied during the audit; they do not claim that every local syllabus
uses the same grade number.

| Grade | Topic | Status | Current behavior | Priority / gap |
|---:|---|---|---|---|
| 1 | Counting and comparing small whole numbers | **TEACH** | The model can teach from ordinary number facts. | **P1:** typed number-line/counter representation. |
| 1 | Single-digit addition and subtraction | **VERIFIED + PROCEDURE** | Exact result and column trace; concise prompts may show only the result. | Add number-bond and ten-frame representations (**P1**). |
| 1 | Place value, expanded form, number bonds | **MISSING** | No first-class base-ten/place-value teaching schema. | **P1**. |
| 1 | Shapes, length, time, money, simple picture data | **LLM-ONLY** | Ordinary tutoring; no grade-specific manipulative/clock/coin trace. | **P1** for time/money and picture/bar data. |
| 2 | Multi-digit addition and subtraction | **VERIFIED + PROCEDURE** | Carries and regrouping are server-owned, including consecutive borrowing through zero. | Covered for supported numeric grammar. |
| 2 | Skip counting, equal groups, arrays | **MISSING** | Can be discussed, but has no authoritative visual teaching representation. | **P1**. |
| 2 | Measurement, money, clocks, elementary graphs | **TEACH** | Closed arithmetic is verified; interpretation and visuals are prose. | **P1** typed units/time/data teaching. |
| 3 | Multiplication and division facts | **VERIFIED + PROCEDURE** | Exact product/quotient; school working available on request. | Covered. |
| 3 | Multi-digit multiplication and long division | **VERIFIED + PROCEDURE** | Carries, partial products, place shifts, quotient placement, subtract/bring-down cycles, and remainder are typed data. | Covered for integer and supported terminating-decimal cases. |
| 3 | Introductory fractions and fraction of a quantity | **VERIFIED + PROCEDURE** | Exact rational result and typed fraction steps. | Fraction bars/number-line placement are **MISSING (P1)**. |
| 3 | Area/perimeter and elementary data | **VERIFIED** | Closed supported shapes and descriptive statistics are checked. A request for two quantities is declined unless both are represented. | Teaching models incomplete (**P1**). |
| 4 | Whole-number written algorithms | **VERIFIED + PROCEDURE** | Multi-addend addition, subtraction across zero, multiplication, and long division. | Covered. |
| 4 | Factors, multiples, primes | **VERIFIED** | GCD/LCM, primality, factorization, and related number theory. | Explanation remains **TEACH**. |
| 4 | Equivalent/compared/simplified fractions | **VERIFIED + PROCEDURE** | Exact rational arithmetic and common-denominator reasoning. | Visual models are **MISSING (P1)**. |
| 4 | Angles, lines, area/perimeter | **VERIFIED** for supported numeric shapes; **LLM-ONLY** for definitions/proofs | Canonical geometry result/diagram where the dimensions are complete. | Constructions and theorem teaching **P1**. |
| 5 | Decimal place-value operations | **VERIFIED + PROCEDURE** for written operations | Exact decimal alignment is retained in typed arithmetic work. | Comparing/rounding place-value trace is **MISSING (P1)**. |
| 5 | Fraction operations and mixed numbers | **VERIFIED + PROCEDURE** | Simplify, equivalence, compare, four operations, mixed/improper conversion, quantity. | Robust visual models **P1**. |
| 5 | Percent conversions and applications | **VERIFIED** | Percent-of, change, markup/discount/tax, fraction/decimal expressions in supported grammar. | Unified conversion procedure is **TEACH (P1)**. |
| 5 | Volume and coordinate plane | **VERIFIED** | Supported solids and coordinate computations are checked. | Nets and composed-solid teaching incomplete (**P1**). |
| 6 | Integers and rational-number arithmetic | **VERIFIED** | Exact arithmetic and simplification. | Negative-number line teaching is **MISSING (P1)**. |
| 6 | Ratios, rates, proportions, percentages | **VERIFIED** | Ratios, splits, direct/inverse proportion, percent applications, and unit conversion. Physical distance/rate/time belongs to physics. | Multi-step ratio stories remain fail-closed unless setup is complete. |
| 6 | Expressions, one-step equations/inequalities | **VERIFIED + PROCEDURE** | Solver-checked transformations and answer/domain guards. | Covered for supported grammar. |
| 6 | Statistics and probability | **VERIFIED** | Descriptive statistics, combinatorics, and supported probability templates. | Histograms/box plots/sampling concepts are **LLM-ONLY or MISSING (P1)**. |
| 7 | Rational numbers, exponents, scientific notation | **VERIFIED** | Exact simplification/evaluation and supported unit/scientific forms. | Grade-specific procedure narration is **TEACH**. |
| 7 | Proportions and percent word problems | **VERIFIED** when every quantity is traceable | Unsupported/underdetermined stories decline verification. | Broader story grammar **P1**. |
| 7 | Equations, inequalities, coordinate geometry | **VERIFIED + PROCEDURE** for equations/inequalities; **VERIFIED** for coordinate formulas | Number-line/region fences use the canonical result. | Covered within closed grammars. |
| 7 | Geometry, transformations, probability | **VERIFIED** for supported calculations; **LLM-ONLY** for proofs/constructions | No invented dimensions. | Transformation/construction visuals **P1**. |
| 8 | Linear equations and systems | **VERIFIED + PROCEDURE** | Equation equivalence and 2×2 substitution/elimination traces are checked line by line. | Larger-system answers are verified but teaching is less complete. |
| 8 | Linear inequalities and Cartesian graphs | **VERIFIED + PROCEDURE** / **VERIFIED** | Correct open/closed endpoints, sign reversal, graph/region output. | Covered for supported linear/rational forms. |
| 8 | Squares, roots, cubes, exponents | **VERIFIED** | Exact radicals/powers and equation domains/branches are checked. | First-class radical procedure trace is **TEACH (P1)**. |
| 8 | Similarity, circles, right triangles, trigonometry | **VERIFIED** for closed calculations | Pythagorean, supported circle/triangle/trig results; no fake proof claim. | Formal theorem/construction lessons **LLM-ONLY (P1)**. |
| 8 | Introductory probability | **VERIFIED** | Supported exact probability, expected value, combinations/permutations. | Tree/table visuals **MISSING (P1)**. |
| 9 | Real numbers, radicals, absolute value, quadratics | **VERIFIED + PROCEDURE** for supported equations/inequalities | Domain exclusions, extraneous-root checks, branches, and intervals are retained. | More explicit radical/absolute-value case traces **P1**. |
| 9 | Sets, relations, functions and graphs | **VERIFIED** for set operations and supported function analysis/graphs | Domain/range/inverse/composition where closed and safe. | Relation mapping pedagogy **TEACH**. |
| 9 | Geometry/measurement and trigonometry | **VERIFIED** for supported numeric problems | Canonical formulas, diagrams, units. | Proofs, constructions, composed solids **P1**. |
| 9 | Statistics, probability, vectors | **VERIFIED** for supported calculations | Descriptive/bivariate statistics, probability templates, vector operations. | Sampling/data visual teaching **P1**. |
| 10 | Polynomial functions, zeros, factoring and graphs | **VERIFIED** | Expand/factor/solve/graph and function analysis in supported grammar. | Polynomial/synthetic long-division procedure is **MISSING (P1)**. |
| 10 | Exponential and logarithmic functions/equations | **VERIFIED** | Symbolic simplification/solution/domain checking where SymPy closes the request. | School-method log/exponential trace is **TEACH (P1)**. |
| 10 | Absolute, linear-system and quadratic inequalities | **VERIFIED + PROCEDURE** for supported forms | Correct unions, excluded poles, number lines/regions. | Covered within grammar. |
| 10 | Coordinate geometry and trigonometric functions | **VERIFIED** | Lines, distances, exact trig values, periodic solution branches, graphs. | Unit-circle/identity teaching needs fuller traces (**P1**). |
| 10 | Plane geometry and measurement | **VERIFIED** for supported calculations; **LLM-ONLY** for proofs | Triangles, quadrilaterals, circles, regular numeric geometry, solids. | Theorem proofs/constructions/composed solids **P1**. |
| 11 | Algebra II: rational/radical/complex expressions | **VERIFIED** | Exact solve/simplify with domain restrictions and complex arithmetic. | Structured derivations vary; rational/radical procedure **P1**. |
| 11 | Sequences and series | **VERIFIED** | AP/GP terms/sums, infinite GP constraints, supported symbolic series. | Induction/proof is **LLM-ONLY**. |
| 11 | Matrices and vectors | **VERIFIED** | Core matrix and vector operations, eigendata, projections. | Row-operation teaching is **TEACH (P1)**. |
| 11 | Conics, transformations, trig identities/equations | **VERIFIED** for supported closed requests | Canonical expressions/graphs and exact solutions; identities are certified only when symbolic difference is zero. | Conic construction/unit-circle pedagogy **P1**. |
| 11 | Probability/statistics | **VERIFIED** for supported templates | Conditional probability/Bayes, distributions, descriptive/bivariate statistics. | Regression interpretation and sampling design **LLM-ONLY (P1)**. |
| 12 | Limits and derivatives | **VERIFIED + PROCEDURE** | Limits are checked; common derivative rules have validated ordered steps. | Advanced epsilon-delta proofs are **LLM-ONLY**. |
| 12 | Integrals and applications | **VERIFIED + PROCEDURE** for supported antiderivatives; **VERIFIED** for supported applications | Trace is differentiated back; areas/volumes require complete bounds. | Broader techniques/applications **P2**. |
| 12 | Parametric/polar and introductory multivariable calculus | **VERIFIED** for supported closed requests | Parametric/polar graphs, partial derivatives, gradients, multiple integrals where grammar is complete. | Detailed teaching traces **P2**. |
| 12 | Advanced sequences/series and differential equations | **VERIFIED** where the symbolic solver closes | Exact result with explicit bounds/conditions retained. | Convergence-proof teaching and broad ODE classes **LLM-ONLY/P2**. |

## Deterministic procedure inventory

| Procedure | Authoritative data | Verification invariant |
|---|---|---|
| Addition | `ArithmeticWorkSpec` columns with place, addends, carry-in/out, written digit | Rendered result equals the exact sum. |
| Subtraction | Columns with top/bottom digit, borrow source, regrouped value, written digit | Rendered result equals minuend minus subtrahend, including borrowing through zero. |
| Multiplication | Per-row carries, partial product, and decimal/place shift | Sum of shifted partial products equals the exact product. |
| Long division | Quotient digit, partial dividend, multiplication, subtraction, bring-down, remainder | `dividend = divisor × quotient + remainder`; `0 ≤ remainder < |divisor|`. |
| Fractions | `FractionWorkSpec` with exact source/operation/intermediate/result | The reduced rational result is equivalent to the original operation. |
| Equations | Ordered `KeyStep` transformations plus substitution/check | Returned roots satisfy the original equation and restrictions. |
| Inequalities | Ordered trace plus canonical interval/number-line data | Sampled points agree with the original relation; poles remain excluded. |
| Systems | Substitution/elimination trace and canonical tuples | Every tuple satisfies every original equation. |
| Derivatives | Rule-labeled ordered steps | The canonical derivative is symbolically equivalent to differentiating the source. |
| Integrals | Method-labeled ordered steps | Differentiating the reported antiderivative recovers the integrand. |

## Important unsupported or incomplete areas

These are not hidden behind a “complete K–12” percentage:

- **P1 elementary representations:** number bonds, counters/ten frames, equal-group arrays,
  base-ten blocks, negative/fraction number lines, and fraction bars.
- **P1 decimal pedagogy:** first-class place-value comparison and rounding traces, separate from
  the already verified aligned decimal arithmetic.
- **P1 geometry:** formal constructions and proof teaching, transformations, and composed solids.
  Supported area-plus-perimeter requests retain both values in one canonical geometry spec and
  stay off the one-answer direct path.
- **P1 algebra/precalculus:** polynomial long division, synthetic division, fuller radical and
  rational-expression procedures, and unit-circle teaching.
- **P1 data literacy:** authoritative histogram/box-plot/scatter-plot teaching, regression
  interpretation, sampling design, and probability trees.
- **P2 advanced mathematics:** broader integration techniques, convergence proofs, ODE families,
  and detailed parametric/polar/multivariable procedures.

Unsupported multipart prompts are intentionally unverified. For example, if Recall cannot
represent both area and perimeter as one canonical result, it does not certify only one half.

## Maintenance rule

To upgrade a row, add all of the following:

1. a complete-request extractor with meaningful-leftover validation;
2. a deterministic solver and typed result/trace where a procedure is claimed;
3. direct/prompt/fence behavior that cannot change the canonical mathematics;
4. mobile render, reopen, Copy, and read-aloud checks where the representation applies;
5. original, nearby-variant, negative/trap, metamorphic, and invariant tests.

The implementation map and safety boundaries live in [math.md](./math.md). Subject ownership is
locked down in [SUBJECT_SEPARATION_TICKETS.md](./SUBJECT_SEPARATION_TICKETS.md).
