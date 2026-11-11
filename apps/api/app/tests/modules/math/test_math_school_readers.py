"""More everyday homework read whole by the reader that owns it, and nothing beside it."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.math.function_analysis import inverse_function
from app.modules.math.match.discrete import word_arrangement_signal
from app.modules.math.solve import SolveServiceError
from app.modules.math.tools.extract import extract_math_intent
from app.modules.math.tools.extractors.fractions import extract_fraction_intent
from app.modules.math.tools.prompt import build_math_augmentation, needs_symbolic_math
from app.modules.math.tools.school.algebra_facts import extract_algebra_fact_intent
from app.modules.math.tools.school.geometry_measures import extract_geometry_measure_intent
from app.modules.math.tools.school.number_facts import extract_number_fact_intent
from app.modules.math.tools.school.probability import (
    _extract_probability_intent,
    extract_at_least_one_intent,
)
from app.modules.math.tools.school.units import extract_how_many_in_intent
from app.modules.math.tools.school.vectors import extract_vector_formulas


@pytest.mark.parametrize(
    ("text", "op", "expr"),
    [
        ("wats the squre root of 225", "root_words", "225"),
        ("cube root of -27", "root_words", "-27"),
        ("what is 0.375 as a fraction", "to_fraction", "0.375"),
        ("write 1.25 as a fraction in simplest form", "to_fraction", "1.25"),
        ("how many factors does 36 have", "factor_count", "36"),
        ("how many divisors are there of 100", "factor_count", "100"),
    ],
)
def test_extract_number_fact_intent_reads_everyday_forms(text: str, op: str, expr: str) -> None:
    intent = extract_number_fact_intent(text)
    assert intent is not None
    assert (intent.school_op, intent.expr) == (op, expr)


@pytest.mark.parametrize(
    "text",
    [
        # Not a real number: the model explains the imaginary root.
        "square root of -16",
        "what is 3/8 as a fraction",
        "how many factors in the success of a startup",
    ],
)
def test_extract_number_fact_intent_declines_what_it_cannot_read(text: str) -> None:
    assert extract_number_fact_intent(text) is None


@pytest.mark.parametrize(
    ("text", "op", "operands"),
    [
        ("divide 3/4 by 2/9", "fraction_divide", ["3/4", "2/9"]),
        ("divide 2 1/2 by 1/4", "fraction_divide", ["5/2", "1/4"]),
        ("what is half of 3/4", "fraction_multiply", ["1/2", "3/4"]),
        ("a third of 2 1/4", "fraction_multiply", ["1/3", "9/4"]),
    ],
)
def test_extract_fraction_intent_reads_spoken_operations(
    text: str, op: str, operands: list[str]
) -> None:
    intent = extract_fraction_intent(text)
    assert intent is not None
    assert (intent.school_op, intent.fraction_operands) == (op, operands)


@pytest.mark.parametrize("text", ["half of my 3/4 cup", "divide the 3/4 cake by 2"])
def test_extract_fraction_intent_declines_prose(text: str) -> None:
    assert extract_fraction_intent(text) is None


@pytest.mark.parametrize(
    ("text", "value", "source", "dest"),
    [
        ("how many seconds in a day", 1.0, "day", "seconds"),
        ("how many feet are in a mile", 1.0, "mile", "feet"),
        ("how many grams in 2 pounds", 2.0, "pound", "grams"),
        ("how many minutes in an hour?", 1.0, "hour", "minutes"),
    ],
)
def test_extract_how_many_in_intent_reads_fixed_units(
    text: str, value: float, source: str, dest: str
) -> None:
    intent = extract_how_many_in_intent(text)
    assert intent is not None
    assert (intent.percent_base, intent.unit_from, intent.unit_to) == (value, source, dest)


@pytest.mark.parametrize(
    "text",
    [
        # 365 or 366; 28 to 31: not one fixed size.
        "how many days in a year",
        "how many weeks in a month",
        "how many apples in a basket",
        "how many calories in a banana",
    ],
)
def test_extract_how_many_in_intent_declines_other_units(text: str) -> None:
    assert extract_how_many_in_intent(text) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("how many 4 letter arrangements of the word MATH", ("factorial", 4, None)),
        ("how many 2 letter arrangements of the word MATH", ("permutations", 4, 2)),
        (
            "how many ways can you arrange the letters in the word PENCIL",
            ("factorial", 6, None),
        ),
        # A repeated letter needs n! over the repeats; not read.
        ("how many arrangements of the letters of the word BOOK", None),
        # Not named as a word.
        ("how many arrangements of flowers", None),
    ],
)
def test_word_arrangement_signal_reads_distinct_letters(
    text: str, expected: tuple[str, int, int | None] | None
) -> None:
    assert word_arrangement_signal(text) == expected


@pytest.mark.parametrize(
    ("text", "n", "outcome"),
    [
        ("what is the probability of getting at least one head in 3 coin flips", 3, "heads"),
        ("probability of at least one six in 4 rolls of a die", 4, "sixes"),
    ],
)
def test_extract_at_least_one_intent_reads_repeated_fair_trials(
    text: str, n: int, outcome: str
) -> None:
    intent = extract_at_least_one_intent(text)
    assert intent is not None
    assert (intent.combo_n, intent.trial_outcome) == (n, outcome)


@pytest.mark.parametrize(
    "text",
    [
        "at least one head in 3 rolls",
        "probability of at least one six in 4 coin flips",
        "probability of at least one head in 3 coin flips and exactly 2 tails",
    ],
)
def test_extract_at_least_one_intent_declines_mismatched_trials(text: str) -> None:
    assert extract_at_least_one_intent(text) is None


@pytest.mark.parametrize(
    "text",
    ["expected value of a fair die roll", "what is the expected value of rolling a fair die"],
)
def test_extract_probability_intent_reads_a_fair_die_expectation(text: str) -> None:
    intent = _extract_probability_intent(text)
    assert intent is not None
    assert intent.school_op == "expected"
    assert intent.stats_numbers == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]


@pytest.mark.parametrize(
    ("text", "expr"),
    [
        ("what is the remainder when x^3 + 2x - 5 is divided by x - 2", "x**3 + 2*x - 5|x - 2"),
        ("find the remainder when x^4 - 1 is divided by x^2 + 1", "x**4 - 1|x**2 + 1"),
    ],
)
def test_extract_algebra_fact_intent_reads_polynomial_remainders(text: str, expr: str) -> None:
    intent = extract_algebra_fact_intent(text)
    assert intent is not None
    assert (intent.school_op, intent.expr) == ("polynomial_remainder", expr)


@pytest.mark.parametrize(
    "text",
    [
        "what is the remainder when 17 is divided by 5",
        "what is the remainder when x is divided by x^2 + 1",
        "the remainder when x^2 is divided by my friend",
    ],
)
def test_extract_algebra_fact_intent_declines_other_remainders(text: str) -> None:
    assert extract_algebra_fact_intent(text) is None


@pytest.mark.parametrize(
    ("text", "expr"),
    [
        # A capitalised verb once read nothing: the side readers matched "find" only.
        ("In triangle ABC, a = 5 cm, b = 8 cm and angle C = 30°. Find c.", "a,b,C,c"),
        ("In triangle ABC, a = 7, b = 9 and C = 60°. Calculate the length of c.", "a,b,C,c"),
        ("In triangle ABC, a = 7, b = 9 and C = 60°. What is c?", "a,b,C,c"),
        ("In triangle ABC, b = 4, c = 6 and A = 135°. Determine side a.", "b,c,A,a"),
    ],
)
def test_cosine_rule_reader_takes_the_verb_in_any_case(text: str, expr: str) -> None:
    intent = extract_algebra_fact_intent(text)
    assert intent is not None
    assert (intent.school_op, intent.expr) == ("cosine_rule", expr)


@pytest.mark.parametrize(
    ("text", "names"),
    [
        ("In triangle ABC, A = 40°, B = 60° and a = 10. Find b.", "a|b"),
        ("In triangle ABC, A = 40°, B = 60° and a = 10. Calculate the length of side b.", "a|b"),
        ("In triangle ABC, A = 40°, B = 60° and a = 10. Work out b.", "a|b"),
    ],
)
def test_sine_rule_reader_takes_the_verb_in_any_case(text: str, names: str) -> None:
    intent = extract_geometry_measure_intent(text)
    assert intent is not None
    assert (intent.school_op, intent.trial_outcome) == ("geometry_measure:sine_rule", names)


@pytest.mark.parametrize(
    "text",
    [
        # "C" names the angle and "c" the side opposite it, so the letter keeps its case.
        "In triangle ABC, a = 10, A = 40° and B = 60°. Find B.",
        "In triangle ABC, a = 10, A = 40° and B = 60°. FIND B",
    ],
)
def test_side_readers_keep_the_letters_case(text: str) -> None:
    assert extract_geometry_measure_intent(text) is None
    assert extract_algebra_fact_intent(text) is None


@pytest.mark.parametrize(
    ("expr", "inverse"),
    [
        ("(2*x+1)/(x-3)", r"\frac{3 x + 1}{x - 2}"),
        ("exp(x)", r"\ln{\left(x \right)}"),
        ("1/x", r"\frac{1}{x}"),
        ("2*x+1", r"\frac{x}{2} - \frac{1}{2}"),
    ],
)
def test_inverse_function_reads_one_candidate_under_domain_conditions(
    expr: str, inverse: str
) -> None:
    assert inverse_function(expr) == inverse


@pytest.mark.parametrize("expr", ["x**2", "sqrt(x)"])
def test_inverse_function_still_refuses_two_branches(expr: str) -> None:
    with pytest.raises(SolveServiceError):
        inverse_function(expr)


@pytest.mark.parametrize(
    ("text", "vectors"),
    [
        ("find the angle between vectors (1,0) and (1,1)", ([1.0, 0.0], [1.0, 1.0])),
        ("angle between the vectors (1,2,2) and (2,1,-2)", ([1.0, 2.0, 2.0], [2.0, 1.0, -2.0])),
    ],
)
def test_extract_vector_formulas_reads_round_brackets_named_as_vectors(
    text: str, vectors: tuple[list[float], list[float]]
) -> None:
    intent = extract_vector_formulas(text)
    assert intent is not None and intent.school_op == "angle"
    assert (intent.vec_a, intent.vec_b) == vectors


def test_extract_vector_formulas_leaves_round_brackets_as_points() -> None:
    assert extract_vector_formulas("find the angle between (1,0) and (1,1)") is None


@pytest.mark.parametrize(
    ("text", "kind", "expr"),
    [
        ("find the zeros of f(x) = x^2 - 4x", "equation", None),
        ("integrate by parts x e^x", "calculus", "x e^x"),
        ("integrate x e^x by parts", "calculus", "x e^x"),
    ],
)
def test_extract_math_intent_reads_function_zeros_and_method_words(
    text: str, kind: str, expr: str | None
) -> None:
    intent = extract_math_intent(text)
    assert intent is not None and intent.kind == kind
    if expr is not None:
        assert intent.expr == expr


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        ("wats the squre root of 225", "15"),
        ("cube root of -27", "-3"),
        ("what is 0.375 as a fraction", r"\frac{3}{8}"),
        ("how many factors does 36 have", "9"),
        ("divide 3/4 by 2/9", r"\frac{27}{8}"),
        ("what is half of 3/4", r"\frac{3}{8}"),
        ("how many seconds in a day", r"86400\ \mathrm{seconds}"),
        ("how many 4 letter arrangements of the word MATH", "4! = 4 × 3 × 2 × 1 = 24"),
        (
            "what is the probability of getting at least one head in 3 coin flips",
            r"\frac{7}{8} = 0.875",
        ),
        ("expected value of a fair die roll", "3.5"),
        ("what is the remainder when x^3 + 2x - 5 is divided by x - 2", "7"),
        ("find the inverse of f(x) = (2x+1)/(x-3)", r"\frac{3 x + 1}{x - 2}"),
        ("find the angle between vectors (1,0) and (1,1)", "45"),
        ("find the zeros of f(x) = x^2 - 4x", r"x = 0 \text{ or } x = 4"),
        ("integrate by parts x e^x", r"\left(x - 1\right) e^{x} + C"),
        ("find the period of y = sin(2x)", r"\pi"),
        ("find the period of y = 2sin(3x - 1) + 4", r"\frac{2 \pi}{3}"),
        ("find the amplitude of y = 3 sin(2x) + 1", "3"),
        ("amplitude of y = -2cos(x/2)", "2"),
        ("how many real roots does x^2 + 2x + 5 = 0 have", "0"),
        ("how many solutions does 2x + 3 = 2x + 5 have", "0"),
        ("how many solutions does x^2 - 5x + 6 = 0 have", "2"),
        ("how many solutions does 2(x+1) = 2x + 2 have", r"\text{infinitely many}"),
    ],
)
@pytest.mark.asyncio
async def test_build_math_augmentation_verifies_school_readers(text: str, answer: str) -> None:
    assert needs_symbolic_math(text)
    _, verified = await build_math_augmentation(text, Settings(math_tools_enabled=True))
    assert verified is not None
    assert verified.canonical_answer == answer


# How many solutions an equation has, in every form a student sends it: the maths
# keyboard's ``$…$`` (``\frac``, ``^{2}``, ``\cdot``), a capital or another letter for the
# unknown, "real" or not, roots, zeros or solutions, any equation form, any degree.
# "How many solutions does $4X^2 + 4 = 6$ have?" went to the model unverified (2026-11-10).
@pytest.mark.parametrize(
    ("text", "answer"),
    [
        ("How many solutions does $4X^2 + 4 = 6$ have?", "2"),
        ("how many real solutions does $4X^{2} + 4 = 6$ have?", "2"),
        ("How many roots does $X^{2} - 5X + 6 = 0$ have?", "2"),
        ("how many zeros does $x^{3} - x = 0$ have", "3"),
        ("how many solutions does $\\frac{x}{2} + 3 = 5$ have?", "1"),
        ("how many solutions does $\\frac{x^{2}}{2} = 8$ have?", "2"),
        ("how many solutions does $2 \\cdot x + 1 = 7$ have", "1"),
        ("how many solutions does 3T + 2 = 8 have", "1"),
        ("how many solutions does t^2 = 9 have", "2"),
        ("how many solutions are there to x^2 = 2x", "2"),
        ("how many real solutions are there for $x^{2} + 1 = 0$", "0"),
        ("find the number of real roots of x^2 + 2x + 5 = 0", "0"),
        ("what is the number of solutions of x^4 - 5x^2 + 4 = 0", "4"),
        ("how many distinct real roots does (x-2)^2 = 0 have", "1"),
        ("How many solutions does $x^{2} - 6x + 9 = 0$ have?", "1"),
        ("how many real roots does x^3 = 8 have", "1"),
        ("how many solutions does $2X + 3 = 2X + 5$ have?", "0"),
        ("how many solutions does $2(X+1) = 2X + 2$ have?", r"\text{infinitely many}"),
    ],
)
@pytest.mark.asyncio
async def test_build_math_augmentation_counts_solutions_in_every_form(
    text: str, answer: str
) -> None:
    assert needs_symbolic_math(text)
    _, verified = await build_math_augmentation(text, Settings(math_tools_enabled=True))
    assert verified is not None
    assert verified.canonical_answer == answer


@pytest.mark.parametrize(
    "text",
    [
        "how many days in a year",
        "how many calories in a banana",
        "how many arrangements of flowers for a wedding",
        "how many factors affect house prices",
        "what are the odds of at least one sunny day this week",
        "half of my 3/4 cup of sugar spilled",
    ],
)
def test_needs_symbolic_math_keeps_reader_lookalikes_out(text: str) -> None:
    assert not needs_symbolic_math(text)


@pytest.mark.parametrize(
    "text",
    [
        # Two waves added: no single period read here.
        "find the period of y = sin(x) + cos(2x)",
        # A tangent has no amplitude.
        "find the amplitude of y = tan(x)",
        # No real roots, two complex ones: "roots" alone is either count.
        "how many roots does x^2 + 1 = 0 have",
    ],
)
@pytest.mark.asyncio
async def test_build_math_augmentation_declines_features_it_cannot_read(text: str) -> None:
    _, verified = await build_math_augmentation(text, Settings(math_tools_enabled=True))
    assert verified is None


@pytest.mark.parametrize(
    "text",
    [
        "what was the period of the french revolution",
        "how many solutions does this puzzle have",
        "what is the amplitude of a wave in physics",
    ],
)
def test_needs_symbolic_math_keeps_feature_lookalikes_out(text: str) -> None:
    assert not needs_symbolic_math(text)


# The set the count is over: an interval, an inequality on the unknown, a sign word. A
# count that ignored one was a wrong verified answer (review of 2026-11-10): "how many
# solutions are there in [0, 5] to x^2 = 4" answered 2.
@pytest.mark.parametrize(
    ("text", "answer"),
    [
        ("how many solutions does x^2 = 4 have in [0, 5]", "1"),
        ("how many solutions are there in [0, 5] to x^2 = 4", "1"),
        ("the number of solutions of x^2 = 4 in [0, 5]", "1"),
        ("the number of roots of x^2 = 4 in (0, 5)", "1"),
        ("number of zeros of x^2 - 4 = 0 in [0, 3]", "1"),
        ("how many zeros of x^2 - 4 = 0 lie in [0, 3]", "1"),
        ("how many solutions to x^2 = 4 with x in [1,3]", "1"),
        ("how many solutions to x^2 = 4 where 1 <= x <= 3", "1"),
        ("how many solutions does x^2 = 4 have in 0 < x < 5", "1"),
        ("how many solutions does $x^{2} = 4$ have for $0 \\le x \\le 5$", "1"),
        ("how many solutions does x^2 = 4 have for x > 0", "1"),
        ("how many roots are there for x^2 = 4 for x > 0", "1"),
        ("number of real roots of x^2 = 4 for x > 0", "1"),
        ("number of solutions for x^2 = 4 if x >= 0", "1"),
        ("how many solutions does x^2 = 4 have where x > 0 and x < 1", "0"),
        ("how many solutions does x^2 = 4 have between 0 and 5", "1"),
        ("how many positive solutions does x^2 - x - 6 = 0 have", "1"),
        ("how many negative real roots does x^3 - x = 0 have", "1"),
        ("how many solutions of x^2 = 4 are positive", "1"),
    ],
)
@pytest.mark.asyncio
async def test_solution_count_is_over_the_stated_set(text: str, answer: str) -> None:
    _, verified = await build_math_augmentation(text, Settings(math_tools_enabled=True))
    assert verified is not None
    assert verified.canonical_answer == answer


# A bound is read whole, with the parser the equation is read with, and the condition is
# solved for the unknown: "for x > -2 + 3" was read as x > -2, and "for -x > 0" as x > 0
# (re-review of 2026-11-10). x^3 - 7x + 6 = 0 has the roots -3, 1 and 2.
@pytest.mark.parametrize(
    ("condition", "answer"),
    [
        ("for x > -2 + 3", "1"),
        ("for 0 < x < 1 + 1", "1"),
        ("for 0 < x <= 1 + 1", "2"),
        ("for x > 2 - 3", "2"),
        ("for x < 2^2", "3"),
        ("for x > 1e3", "0"),
        ("for -x > 0", "1"),
        ("for 2x > 3", "1"),
        ("for x^2 < 4", "1"),
        ("in [-1 + 1, 2 + 1]", "2"),
        ("for x > 0 and x < 3", "2"),
    ],
)
@pytest.mark.asyncio
async def test_solution_count_reads_each_bound_whole(condition: str, answer: str) -> None:
    text = f"how many solutions does x^3 - 7x + 6 = 0 have {condition}"
    _, verified = await build_math_augmentation(text, Settings(math_tools_enabled=True))
    assert verified is not None
    assert verified.canonical_answer == answer


@pytest.mark.parametrize(
    "condition",
    [
        # Two conditions joined only by a comma: "or" or "and" is not said.
        "for x < -1, x > 1",
        # Bounds given backwards.
        "in [5, 0]",
        "for 5 < x < 0",
        # Two intervals, a word in a bound, another letter.
        "for x^2 > 4",
        "for x > 2 apples",
        "for x > y",
    ],
)
@pytest.mark.asyncio
async def test_solution_count_declines_a_condition_it_cannot_read_whole(condition: str) -> None:
    text = f"how many solutions does x^3 - 7x + 6 = 0 have {condition}"
    _, verified = await build_math_augmentation(text, Settings(math_tools_enabled=True))
    assert verified is None or verified.canonical_answer not in {"0", "1", "2", "3"}


# A condition is read only from an allowlist: relations (``!=`` removes a point) between
# short polynomials of degree 4 at most with rational coefficients (third review of
# 2026-11-10: "x ≠ 2" was dropped, "sin(x) > 0" read as one period, and x^50 held a worker).
@pytest.mark.parametrize(
    ("text", "answer"),
    [
        ("how many solutions does x^2 = 4 have for x ≠ 2", "1"),
        ("how many solutions does x^2 = 4 have for x != 2", "1"),
        ("how many solutions does $x^{2} = 4$ have for $x \\neq 2$", "1"),
        ("how many solutions does x^2 = 4 have in [0, 5] and x ≠ 2", "0"),
        ("how many solutions does x^2 = 4 have for x ≠ 2 and x > 0", "0"),
    ],
)
@pytest.mark.asyncio
async def test_solution_count_removes_the_points_a_condition_excludes(
    text: str, answer: str
) -> None:
    _, verified = await build_math_augmentation(text, Settings(math_tools_enabled=True))
    assert verified is not None
    assert verified.canonical_answer == answer


@pytest.mark.parametrize(
    "condition",
    [
        "x^50 - 3x^7 + 2 > 0",
        "x^31 - x^17 + 5x^3 - 1 > 0",
        "sin(x) > 0",
        "x > sqrt(2)",
        "x^2 - 2 > 0",
        "|x| < 3",
    ],
)
@pytest.mark.wall_clock
def test_count_region_declines_off_the_allowlist_at_once(condition: str) -> None:
    import time

    from app.modules.math.tools.school.equation_features.count_conditions import (
        count_region,
        read_count_conditions,
    )

    started = time.monotonic()
    read = read_count_conditions(f"how many solutions does x^2 = 49 have for {condition}")
    region = None if read is None else count_region(read[1], "x")
    assert region is None
    assert time.monotonic() - started < 0.5


@pytest.mark.asyncio
async def test_a_trig_condition_is_no_count() -> None:
    text = "how many solutions does x^2 = 49 have for sin(x) > 0"
    _, verified = await build_math_augmentation(text, Settings(math_tools_enabled=True))
    assert verified is None or verified.canonical_answer not in {"0", "1", "2"}


# A reader that recognises its question and declines it returns a declined reading: the
# model's reading, a later reader and the sympy tool may not certify another answer in its
# place ("how many solutions ... for x^4 - 5x^2 + 4 <= 0" came back as the condition's set).
_DECLINED_TURNS = [
    "how many solutions does x^2 = 9 have for x^4 - 5x^2 + 4 <= 0",
    "how many solutions does x^2 = 4 have for x^4 - 5x^2 + 4 < 0",
    "how many solutions does x^2 = 4 have for x^2 - 2 > 0",
    "how many solutions does |x| = 2 have",
    "how many solutions of 3x = 6 mod 9",
    "find the vertex of y = x^2 - 4x + 3 for x > 5",
    "find the x-intercepts of y = x^2 - 4 for x > 0",
    "find the sum of the roots of x^2 - 5x + 6 = 0 for x > 2",
    "find k so that x^2 + kx + 9 = 0 has exactly one solution for x > 0",
    "what is the remainder when x^3 + 2x - 5 is divided by x - 2 for x > 1",
]


@pytest.mark.parametrize("text", _DECLINED_TURNS)
@pytest.mark.asyncio
async def test_a_declined_reading_is_never_answered_by_another_path(
    text: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.modules.math.schemas import is_declined
    from app.modules.math.tools import prompt

    async def no_model_reading(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the model's reading ran on a declined turn")

    monkeypatch.setattr(prompt, "_model_math_intent", no_model_reading)
    reading = extract_math_intent(text)
    # Declined, or read as the asked question whose solver then declines.
    assert reading is not None and (is_declined(reading) or reading.school_op is not None)
    note, verified = await build_math_augmentation(text, Settings(math_tools_enabled=True))
    assert verified is None
    assert note is not None and "could not be produced" in note


def test_the_sympy_tool_cannot_certify_a_declined_turns_condition() -> None:
    from app.modules.math.subject import MathTool

    text = "how many solutions does x^2 = 9 have for x^4 - 5x^2 + 4 <= 0"
    call = {"action": "inequality", "lhs": "x^4 - 5x^2 + 4", "rhs": "0", "comparator": "<="}
    assert MathTool().call_matches(call, [text]) is None
    # The same call on a turn that asks for the inequality is the user's own maths.
    assert MathTool().call_matches(call, ["solve x^4 - 5x^2 + 4 <= 0"]) is not None


# A value that makes a denominator of the written equation zero is no solution, as the
# solve card says; "counting multiplicity" counts a repeated root as often as it repeats.
@pytest.mark.parametrize(
    ("text", "answer"),
    [
        ("the number of solutions of x^2/x = 0", "0"),
        ("how many solutions does $\\frac{x^{3}}{x} = 0$ have?", "0"),
        ("how many solutions does $\\frac{x^{2}}{x} = 1$ have?", "1"),
        ("how many solutions does $\\frac{x^{2} - 4}{x - 2} = 0$ have?", "1"),
        ("how many solutions does (x^2-1)/(x-1) = 2 have", "0"),
        ("how many solutions does 1/x = 0 have", "0"),
        ("how many solutions does x/x = 1 have", r"\text{infinitely many}"),
        ("how many roots does x^3 - 3x + 2 = 0 have", "2"),
        ("how many roots does x^3 - 3x + 2 = 0 have counting multiplicity", "3"),
        ("how many solutions does x^2 + 2x + 1 = 0 have counting multiplicity", "2"),
    ],
)
@pytest.mark.asyncio
async def test_solution_count_excludes_denominators_and_reads_multiplicity(
    text: str, answer: str
) -> None:
    _, verified = await build_math_augmentation(text, Settings(math_tools_enabled=True))
    assert verified is not None
    assert verified.canonical_answer == answer


@pytest.mark.parametrize(
    "text",
    [
        # A condition no rule here reads: never a count over all the reals.
        "how many solutions does x^2 = 2 have in integers",
        "how many solutions does x^2 = 4 have in the range 0 to 5",
        "how many solutions of 3x = 6 in mod 5",
        # The condition is on another letter.
        "how many solutions does x^2 = 4 have for t > 0",
        # A root on an end of "between": the count depends on whether the ends count.
        "how many solutions does x^2 = 4 have between 0 and 2",
        # Two complex roots: no multiplicity count over the reals alone.
        "how many roots does x^2 + 1 = 0 have counting multiplicity",
    ],
)
@pytest.mark.asyncio
async def test_solution_count_declines_conditions_it_cannot_read(text: str) -> None:
    _, verified = await build_math_augmentation(text, Settings(math_tools_enabled=True))
    assert verified is None or verified.canonical_answer not in {"1", "2"}


@pytest.mark.asyncio
async def test_solution_count_working_shows_the_set_the_denominator_and_a_double_root() -> None:
    settings = Settings(math_tools_enabled=True)
    _, interval = await build_math_augmentation(
        "how many solutions are there in [0, 5] to x^2 = 4", settings
    )
    assert interval is not None and interval.worked_reply is not None
    assert r"x \in \left[0, 5\right]" in interval.worked_reply
    assert "$x = 2$ — the solution in $\\left[0, 5\\right]$" in interval.worked_reply
    _, cancelled = await build_math_augmentation("the number of solutions of x^2/x = 0", settings)
    assert cancelled is not None and cancelled.worked_reply is not None
    assert "**Given**  \n$\\frac{x^{2}}{x} = 0$" in cancelled.worked_reply
    assert "$x \\ne 0$ — a denominator cannot be zero" in cancelled.worked_reply
    assert "x = 0 is excluded" in cancelled.worked_reply
    _, double = await build_math_augmentation("how many roots does x^3 - 3x + 2 = 0 have", settings)
    assert double is not None and double.worked_reply is not None
    assert "$x = 1$ — a double root, counted once" in double.worked_reply


@pytest.mark.parametrize(
    "text",
    [
        "how many solutions does this company offer",
        "how many roots does a tree have",
        "how many zeros in a million",
        "how many zeros are there in the number one billion",
        "how many real solutions does the climate crisis have",
    ],
)
@pytest.mark.asyncio
async def test_solution_count_lookalikes_stay_unsolved(text: str) -> None:
    _, verified = await build_math_augmentation(text, Settings(math_tools_enabled=True))
    assert verified is None


@pytest.mark.asyncio
async def test_solution_count_working_shows_the_solutions() -> None:
    # The count alone tells a student nothing: the working solves the equation.
    query = "How many solutions does $4X^2 + 4 = 6$ have?"
    _, verified = await build_math_augmentation(query, Settings(math_tools_enabled=True))
    assert verified is not None and verified.worked_reply is not None
    reply = verified.worked_reply
    assert "**Given**  \n$4 x^{2} + 4 = 6$" in reply
    assert "$4 x^{2} = 2$ — subtract 4 from both sides" in reply
    assert "$x = \\pm \\frac{\\sqrt{2}}{2}$ — take the square root of both sides" in reply
    assert reply.rstrip().endswith("```answer\n2\n```")


@pytest.mark.asyncio
async def test_solution_count_working_lists_roots_it_cannot_trace() -> None:
    # No factor trace: the roots as the solve card writes them, approximate where so.
    query = "how many real solutions does x^3 + x + 1 = 0 have"
    _, verified = await build_math_augmentation(query, Settings(math_tools_enabled=True))
    assert verified is not None and verified.worked_reply is not None
    assert verified.canonical_answer == "1"
    assert "$x \\approx -0.682328$ — the solution" in verified.worked_reply


# The other school readers, sent from the maths keyboard: a capital unknown, ``$…$``
# spans, ``\le`` bounds, ``^{2}`` inside ``\frac`` and ``\ldots``.
@pytest.mark.parametrize(
    ("text", "answer"),
    [
        ("find the vertex of $Y = X^2 - 4X + 3$", r"\left(2, -1\right)"),
        ("what is the discriminant of $X^2 + 2X + 5$", "b^{2} - 4ac = -16"),
        ("find the x-intercepts of $y = X^2 - 4$", r"\left(-2, 0\right),\ \left(2, 0\right)"),
        ("what is the slope intercept form of $2X + Y = 6$", "y = -2x + 6"),
        ("find the amplitude of $y = 3\\sin(2X)$", "3"),
        ("find k so that $X^2 + kX + 9 = 0$ has exactly one solution", r"k = -6 \text{ or } k = 6"),
        ("what is the remainder when $X^3 + 2X - 5$ is divided by $X - 2$", "7"),
        ("if $f(X) = X^{2} + 1$ find f(2)", "5"),
        (
            "solve $\\sin(x) = \\frac{1}{2}$ for $0 \\le x \\le 2\\pi$",
            r"x = \frac{\pi}{6},\;\frac{5 \pi}{6}",
        ),
        ("find the 10th term of the arithmetic sequence $3, 7, 11, \\ldots$", "39"),
    ],
)
@pytest.mark.asyncio
async def test_school_readers_read_the_maths_keyboard(text: str, answer: str) -> None:
    _, verified = await build_math_augmentation(text, Settings(math_tools_enabled=True))
    assert verified is not None
    assert verified.canonical_answer == answer


@pytest.mark.asyncio
async def test_slope_intercept_form_solves_for_y_as_a_step() -> None:
    # Solving for the unknown is a line of its own over the result, not a note beside it.
    query = "write y - 2x = 5 in slope intercept form"
    _, verified = await build_math_augmentation(query, Settings(math_tools_enabled=True))
    assert verified is not None and verified.worked_reply is not None
    assert "**Required**  \n$y = mx + c$" in verified.worked_reply
    assert "**Steps**  \nSolve for $y$  \n$y = 2x + 5$\n" in verified.worked_reply
    assert "— solve for" not in verified.worked_reply
