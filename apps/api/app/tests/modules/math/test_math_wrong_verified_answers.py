"""Answers a sweep found shown as server-verified although they were wrong.

Every row is a real prompt from the October 2026 STEM sweep (or a phrasing of
one). The rule for each family is the same: the server either answers the
question that was asked, correctly, or verifies nothing and leaves the turn to
the model. A green answer card that answers a different question is never an
option.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from app.core.config import Settings
from app.modules.math.followup import answer_claim_problem, pronoun_math_problem
from app.modules.math.request_consumption import request_consumption_complete
from app.modules.math.schemas import MathIntent
from app.modules.math.solve.key_steps import equation_key_steps
from app.modules.math.solve.parse import _parse_expression
from app.modules.math.solve.work_check import check_work
from app.modules.math.tools.block.work import format_work_check_reply
from app.modules.math.tools.extract import extract_math_intent
from app.modules.math.tools.prompt import needs_symbolic_math
from app.services.subject_solving import build_subject_augmentation, maybe_direct_subject_reply
from app.tests.behavior.cases import Case, Expect
from app.tests.behavior.harness import route_case

_NON_FINITE = re.compile(r"\\tilde\{\\infty\}|\bNaN\b|\bnan\b|\bzoo\b")


async def _verified(text: str) -> tuple[str | None, str | None]:
    """(canonical answer, direct reply) for one turn with no model call."""
    settings = Settings(math_llm_extract_enabled=False, math_word_problems_enabled=False)
    augmentation = await build_subject_augmentation(text, settings)
    verified = augmentation.verified
    answer = getattr(verified, "canonical_answer", None) if verified is not None else None
    return answer, maybe_direct_subject_reply(verified, text)


def _history(*turns: str) -> tuple[tuple[str, str], ...]:
    roles = ("user", "assistant")
    return tuple((roles[index % 2], text) for index, text in enumerate(turns))


# --- A. "find the X of <equation>" is not "solve for x" -------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "answer"),
    [
        ("find the vertex of y = x^2 - 6x + 5", r"\left(3, -4\right)"),
        ("find the vertex of the parabola y = 2x^2 + 8x - 1", r"\left(-2, -9\right)"),
        # The stationary-point rule already answers this one, and says which kind.
        ("what is the turning point of y = x^2 + 4x + 1", r"\left(-2, -3\right)\ \text{minimum}"),
        ("find the axis of symmetry of y = 2x^2 - 8x + 3", "x = 2"),
        ("find the y-intercept of y = 3x + 2", r"\left(0, 2\right)"),
        ("find the y-intercept of y = x^2 - 6x + 5", r"\left(0, 5\right)"),
        ("find the x-intercept of 2x + 3y = 6", r"\left(3, 0\right)"),
        ("find the x-intercepts of y = x^2 - 5x + 6", r"\left(2, 0\right),\ \left(3, 0\right)"),
        ("find the discriminant of 3x^2+2x+1=0", r"b^{2} - 4ac = -8"),
        ("discriminant of 3x^2 + 2x + 1", r"b^{2} - 4ac = -8"),
        ("what is the sum of the roots of x^2 - 5x + 6 = 0", r"x_{1} + x_{2} = 5"),
        ("find the sum of the roots of 2x^2 - 7x + 3 = 0", r"x_{1} + x_{2} = \frac{7}{2}"),
        ("what is the product of the roots of x^2 - 5x + 6 = 0", r"x_{1} x_{2} = 6"),
        (
            "find k so that x^2 + kx + 9 = 0 has exactly one solution",
            r"k = -6 \text{ or } k = 6",
        ),
        (
            "find the equation of the line parallel to y = 3x + 1 through (2, 5)",
            "y = 3x - 1",
        ),
        (
            "find the equation of the line perpendicular to y = 2x + 1 passing through (4, 3)",
            r"y = -\frac{1}{2}x + 5",
        ),
        ("what is the slope of the line 2x + 3y = 6", r"m = -\frac{2}{3}"),
        ("find the gradient of y = 4x - 3", "m = 4"),
        ("find the gradient of the line joining (-1, 4) and (3, -4)", "-2"),
    ],
)
async def test_a_feature_of_an_equation_is_answered_not_solved_for_x(
    text: str, answer: str
) -> None:
    canonical, _reply = await _verified(text)
    assert canonical == answer


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        # No vertex, no single intercept, no one solution: never the roots in x.
        "find the vertex of y = x^3 - 3x",
        "find the axis of symmetry of y = 4x + 1",
        "find the sum of the roots of x^2 + 2x + 1 = 0",
        "find k so that kx^2 + 4x + 1 = 0 has exactly one solution",
        "find the y-intercept of x = 4",
        "what is the domain of the solution of x^2 = 4",
    ],
)
async def test_a_feature_it_cannot_read_is_left_unverified(text: str) -> None:
    canonical, reply = await _verified(text)
    assert canonical is None
    assert reply is None


@pytest.mark.parametrize(
    "text",
    [
        "find the vertex of y = x^3 + 1",
        "find the y-intercept of y = 2^x",
        "what is the discriminant of x^2 + x + 1 = 0",
        "find the gradient of y = x^2",
        "find the line perpendicular to y = x through (1, 1)",
        "find c so that x^2 + 6x + c = 0 has equal roots",
    ],
)
def test_the_audit_refuses_solving_an_equation_when_a_feature_was_asked(text: str) -> None:
    solved = MathIntent(kind="equation", lhs="y", rhs="x^2 + 1", operation="solve")
    assert not request_consumption_complete(text, solved)


def test_the_audit_still_lets_a_plain_solve_through() -> None:
    solved = MathIntent(kind="equation", lhs="x^2 - 5x + 6", rhs="0", operation="solve")
    assert request_consumption_complete("solve x^2 - 5x + 6 = 0", solved)
    assert request_consumption_complete("find the roots of x^2 - 5x + 6 = 0", solved)


# --- B. a student's answer is checked, never certified ---------------------------------


@pytest.mark.parametrize("text", ["x = 6", "x=6", "6 = x", "x = -2.5", "y = 3/4"])
def test_an_equation_already_solved_for_its_variable_is_not_solved_again(text: str) -> None:
    assert extract_math_intent(text) is None


def test_a_list_of_given_values_is_not_a_system_to_solve() -> None:
    assert extract_math_intent("x = 3, y = 1") is None


@pytest.mark.parametrize(
    ("query", "history", "problem"),
    [
        (
            "check my answer: x = 6",
            _history("Solve 4x - 7 = 21", "```answer\nx = 7\n```"),
            "check my work:\n4x - 7 = 21\nx = 6",
        ),
        (
            "x = 6",
            _history("give me a practice problem", "Try this one: solve $4x - 7 = 21$."),
            "check my work:\n4x - 7 = 21\nx = 6",
        ),
        (
            "my answer is x = 6",
            _history(
                "give me a practice problem", "Here's one to try:\n\n**Solve:** $4x - 7 = 21$"
            ),
            "check my work:\n4x - 7 = 21\nx = 6",
        ),
        (
            "is x = 7 right?",
            _history("Solve 4x - 7 = 21", "```answer\nx = 7\n```"),
            "check my work:\n4x - 7 = 21\nx = 7",
        ),
    ],
)
def test_a_claimed_answer_is_checked_against_the_open_problem(
    query: str, history: tuple[tuple[str, str], ...], problem: str
) -> None:
    recent = [{"role": role, "content": text} for role, text in history]
    assert answer_claim_problem(query, recent) == problem


@pytest.mark.parametrize(
    ("query", "history"),
    [
        # No problem open, a different variable, or several equations to choose from.
        ("x = 6", ()),
        ("x = 6", _history("what's the weather like", "Sunny and 24 degrees.")),
        ("y = 6", _history("Solve 4x - 7 = 21", "```answer\nx = 7\n```")),
        ("x = 6", _history("solve x + y = 3 and x - y = 1", "```answer\nx = 2, y = 1\n```")),
        ("x = everything I want in life lol", _history("solve 2x = 4", "```answer\nx = 2\n```")),
    ],
)
def test_a_claim_with_no_single_open_problem_is_not_checked(
    query: str, history: tuple[tuple[str, str], ...]
) -> None:
    recent = [{"role": role, "content": text} for role, text in history]
    assert answer_claim_problem(query, recent) is None


@pytest.mark.asyncio
async def test_a_wrong_claimed_answer_gets_the_right_one(thread_sympy_executor: None) -> None:
    route = await route_case(
        Case(
            "claim",
            "math",
            "check my answer: x = 6",
            Expect(),
            "",
            history=_history("Solve 4x - 7 = 21", "```answer\nx = 7\n```"),
        )
    )
    assert route.solved
    assert "Verified result: x = 7" in route.system_prompt
    assert "Verified result: x = 6" not in route.system_prompt
    assert "does not satisfy" in route.system_prompt


@pytest.mark.asyncio
async def test_a_bare_claim_with_no_problem_is_left_to_the_model(
    thread_sympy_executor: None,
) -> None:
    route = await route_case(Case("bare", "math", "x = 6", Expect(), ""))
    assert not route.solved
    assert "```answer" not in route.instant_text


# --- C. "it" is a pronoun, never i times t --------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "simplify it",
        "can you simplify it?",
        "factor it",
        "expand it",
        "now differentiate it",
        "integrate it",
        "now integrate it",
        "differentiate it with respect to x",
    ],
)
def test_it_is_never_read_as_an_expression(text: str) -> None:
    assert extract_math_intent(text) is None
    assert not needs_symbolic_math(text)


@pytest.mark.parametrize(
    ("query", "history", "problem"),
    [
        (
            "simplify it",
            _history("(x^2-1)/(x-1)", "That is a rational expression in x."),
            "simplify (x^2-1)/(x-1)",
        ),
        (
            "factor it",
            _history("what about x^2 - 9", "That is a difference of squares."),
            "factor x^2 - 9",
        ),
        (
            "now integrate it",
            _history("expand (x+1)^2", "```answer\nx^{2} + 2 x + 1\n```"),
            "integrate (x+1)^2",
        ),
        (
            "integrate it",
            _history("what is x^2 + 3x", "It's an expression."),
            "integrate x^2 + 3x",
        ),
        (
            "now differentiate it",
            _history("expand (x+1)^2 + x^2", "```answer\n2 x^{2} + 2 x + 1\n```"),
            "differentiate (x+1)^2 + x^2",
        ),
    ],
)
def test_it_resolves_to_the_expression_in_the_thread(
    query: str, history: tuple[tuple[str, str], ...], problem: str
) -> None:
    recent = [{"role": role, "content": text} for role, text in history]
    assert pronoun_math_problem(query, recent) == problem


@pytest.mark.parametrize(
    ("query", "history"),
    [
        ("simplify it", ()),
        (
            "can you simplify it?",
            _history(
                "Here is my essay intro: The industrial revolution changed everything.",
                "Nice intro! It reads well.",
            ),
        ),
        ("expand it", _history("my business plan has 3 sections", "Sounds good.")),
        ("factor it into the budget", _history("the trip costs $400", "Got it.")),
        ("integrate it into the report", _history("here is a chart of q3 sales", "Looks good.")),
        ("simplify it", _history("solve 2x + 5 = 17", "```answer\nx = 6\n```")),
        # x^3 or its derivative 3x^2? Either reading is a guess.
        ("now integrate it", _history("derivative of x^3", "```answer\n3 x^{2}\n```")),
        ("integrate that", _history("differentiate x^3", "```answer\n3 x^{2}\n```")),
    ],
)
def test_it_with_no_expression_in_the_thread_stays_unresolved(
    query: str, history: tuple[tuple[str, str], ...]
) -> None:
    recent = [{"role": role, "content": text} for role, text in history]
    assert pronoun_math_problem(query, recent) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "history", "result"),
    [
        (
            "simplify it",
            _history("(x^2-1)/(x-1)", "That is a rational expression in x."),
            "Verified result: x + 1",
        ),
        (
            "now integrate it",
            _history("expand (x+1)^2", "```answer\nx^{2} + 2 x + 1\n```"),
            r"Verified result: x \left(\frac{x^{2}}{3} + x + 1\right) + C",
        ),
        (
            "now differentiate it",
            _history("expand (x+1)^2 + x^2", "```answer\n2 x^{2} + 2 x + 1\n```"),
            "Verified result: 4 x + 2",
        ),
    ],
)
async def test_it_in_a_thread_is_solved_from_that_expression(
    query: str,
    history: tuple[tuple[str, str], ...],
    result: str,
    thread_sympy_executor: None,
) -> None:
    route = await route_case(Case("it", "math", query, Expect(), "", history=history))
    assert route.solved
    assert result in route.system_prompt
    assert "i t" not in route.system_prompt


# --- D. the whole percent or arithmetic request, thousands commas included -------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "answer"),
    [
        ("7.5% of 1,200", "90"),
        ("what is 20% of 1,000", "200"),
        ("15% of 2,500", "375"),
        ("mean of 1,200, 1,500 and 1,800", "1500"),
        ("what is 25% of 80 plus 10", "30"),
        ("what is 25% of 80 minus 5", "15"),
        ("what is 10% of 10% of 500", "5"),
        ("solve 2x = 1,000", "x = 500"),
        # Unchanged neighbours.
        ("what is 25% of 80", "20"),
        ("7.5% of 1200", "90"),
        ("mode of 2,4,4,5,7,7,7,9", "7"),
        ("1,200 + 800", "2000"),
    ],
)
async def test_a_percent_or_arithmetic_request_is_read_whole(text: str, answer: str) -> None:
    canonical, _reply = await _verified(text)
    assert canonical == answer


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "what is 15% of 80 plus tax of 8%",
        "what is 20% of 80 and then double it",
        "what is 5 + 20% of 80",
    ],
)
async def test_a_percent_request_it_cannot_read_whole_is_not_verified(text: str) -> None:
    canonical, _reply = await _verified(text)
    assert canonical is None


@pytest.mark.asyncio
async def test_a_run_that_reads_as_a_list_stays_a_list() -> None:
    # "100,200,300" could be one number or three; the mean of one number is
    # not a question anyone asks, so it stays three values.
    canonical, _reply = await _verified("mean of 100,200,300")
    assert canonical == "200"


# --- E. undefined is undefined, never NaN or complex infinity ---------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    ["what is 0/0", "what is 5/0", "5/0", "what is 1/0", "tan 90°", "log(0)", "ln(0)", "cot 0°"],
)
async def test_a_non_finite_result_is_never_shown_as_an_answer(text: str) -> None:
    canonical, reply = await _verified(text)
    assert canonical in (None, r"\text{undefined}")
    for shown in (canonical or "", reply or ""):
        assert not _NON_FINITE.search(shown)


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["what is 5/0", "tan 90°", "log(0)"])
async def test_division_by_zero_says_undefined(text: str) -> None:
    canonical, reply = await _verified(text)
    assert canonical == r"\text{undefined}"
    assert reply is not None and "undefined" in reply


# --- F. pi, several given values, and powers of i ---------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "answer"),
    [
        ("find the area of a circle with circumference 10π", r"25\pi \approx 78.54"),
        ("find the radius of a circle with circumference 10π", "5"),
        ("area of a circle with circumference 31.4 cm", r"\approx 78.46\ \mathrm{cm}^{2}"),
        ("if x = 3 and y = -2 find x^2 - 2xy + y^2", "25"),
        ("evaluate x^2 - 2xy + y^2 when x = 3 and y = -2", "25"),
        ("if x = 2 find 3x + 1", "7"),
        ("simplify i^23", "- i"),
        ("what is i^23", "- i"),
        ("i^2", "-1"),
    ],
)
async def test_pi_given_values_and_powers_of_i(text: str, answer: str) -> None:
    canonical, _reply = await _verified(text)
    assert canonical == answer


# --- G. "1.8 x 10^-5" is a number --------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Find the pH of 0.10 M CH₃COOH, Ka = 1.8 x 10^-5",
        "whats the ph of 0.10 M acetic acid, Ka = 1.8 x 10^-5",
        "percent ionization of 0.10 M acetic acid, Ka = 1.8 x 10^-5",
        "Ka = 1.8 x 10^-5",
    ],
)
def test_scientific_notation_is_not_an_unknown_x(text: str) -> None:
    assert extract_math_intent(text) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "answer"),
    [
        ("1.8 x 10^-5 * 2", r"3.6 \cdot 10^{-5}"),
        ("3 x 10^4 + 2 x 10^3", "32000"),
        ("solve 3x + 10 = 4", "x = -2"),
    ],
)
async def test_scientific_notation_reads_as_a_number(text: str, answer: str) -> None:
    canonical, _reply = await _verified(text)
    assert canonical == answer


@pytest.mark.asyncio
async def test_scientific_notation_in_words_is_right_or_unverified() -> None:
    canonical, _reply = await _verified("what is 1.8 x 10^-5 times 2")
    assert canonical in (None, r"3.6 \cdot 10^{-5}")


# --- H. check my work grades the answer against the problem ---------------------------


@pytest.mark.parametrize(
    ("lines", "verdicts", "slip_line"),
    [
        (["4x+2=10", "4x=12", "x=2"], ("given", "wrong", "ok"), 2),
        (["2x+4=10", "2x=14", "x=3"], ("given", "wrong", "ok"), 2),
        (["2x+3=11", "2x=14", "x=7"], ("given", "wrong", "carried"), 2),
        (["2x+3=11", "2x=14", "x=6"], ("given", "wrong", "off"), 2),
    ],
)
def test_a_right_final_answer_is_marked_right_after_a_slip(
    lines: list[str], verdicts: tuple[str, ...], slip_line: int
) -> None:
    check = check_work(lines, "x")
    assert check is not None
    assert check.verdicts == verdicts
    assert check.mistake is not None and check.mistake.line == slip_line


def test_the_reply_says_the_answer_is_right_but_names_the_slip() -> None:
    check = check_work(["4x+2=10", "4x=12", "x=2"], "x")
    assert check is not None
    reply = format_work_check_reply(check)
    assert "$x=2$ — \u2713" in reply
    assert "Line 2:" in reply
    assert "final answer is right" in reply


@pytest.mark.asyncio
async def test_a_hint_for_fully_correct_work_says_it_is_right() -> None:
    text = "check my work: 2x+4=10, 2x=6, x=3. Just a hint please"
    _canonical, reply = await _verified(text)
    assert reply is not None
    assert "Every step checks out" in reply
    assert "Identify one reversible operation" not in reply


# --- I. every working line is true ------------------------------------------------------


def _steps(lhs: str, rhs: str, variable: str = "x") -> list[str]:
    left = _parse_expression(lhs, [variable, "y"], real=True)
    right = _parse_expression(rhs, [variable, "y"], real=True)
    return [step.formula for step in equation_key_steps(left, right, variable)]


def test_a_multi_term_is_subtracted_in_brackets() -> None:
    formulas = _steps("2*x + 3*y + 5", "0")
    assert formulas[0] == r"2 x + 3 y + 5 - \left(3 y + 5\right) = 0 - \left(3 y + 5\right)"


def test_a_negative_term_is_added_not_subtracted_twice() -> None:
    formulas = _steps("2*x - 3*y", "4")
    assert formulas[0] == "2 x - 3 y + 3 y = 4 + 3 y"


def test_every_shown_step_is_a_true_equation() -> None:
    from sympy import Symbol, nsimplify, simplify, solve

    x = Symbol("x", real=True)

    def side(tex: str) -> Any:
        return _parse_expression(tex, ["x", "y"], real=True)

    for lhs, rhs in [("2*x + 3*y + 5", "0"), ("0.4*x + 1.2", "2"), ("5 - 3*y - 2*x", "y")]:
        expected = solve(side(lhs) - side(rhs), x)
        for formula in _steps(lhs, rhs):
            left, right = re.sub(r"\\cancel\{([^{}]*)\}", r"\1", formula).split(" = ")
            got = solve(side(left) - side(right), x)
            assert len(got) == len(expected) == 1, formula
            assert simplify(nsimplify(got[0] - expected[0])) == 0, formula


@pytest.mark.asyncio
async def test_a_decimal_equation_ends_on_its_value() -> None:
    canonical, reply = await _verified("solve for x: 0.4x + 1.2 = 2")
    assert canonical == "x = 2"
    assert reply is not None
    assert r"\frac{0.4 x}{0.4} = \frac{0.8}{0.4}$  " + "\n$x = 2$" in reply


# --- J. a maths verb needs a maths object --------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "differentiate between weather and climate",
        "how do I integrate Slack with Notion",
        "factor in the cost of shipping too",
        "expand on that",
        "simplify this paragraph for a 10 year old",
        "simplify my morning routine",
        "x factor auditions near me",
        "factor it into the budget",
        "integrate it into the report",
        "can you expand on your last point",
    ],
)
def test_a_maths_verb_alone_is_not_maths(text: str) -> None:
    assert not needs_symbolic_math(text)


@pytest.mark.parametrize(
    "text",
    [
        "differentiate x^2 sin x",
        "integrate x^2",
        "integrate sin x",
        "factor x^2 + 5x + 6",
        "expand (x+1)(x+2)",
        "simplify 2x + 3x",
        "simplify √50",
        "differentiate y with respect to x",
        "derivative of ln x",
        "integrate e^x",
        "d/dx (x^2 e^x)",
        "∫ x^2 dx",
    ],
)
def test_a_maths_verb_with_a_maths_object_is_maths(text: str) -> None:
    assert needs_symbolic_math(text)
