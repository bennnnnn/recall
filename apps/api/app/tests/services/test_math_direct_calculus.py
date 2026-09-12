"""Complete calculus requests retain all parameters without extra narration."""

from dataclasses import replace
from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.services.math_fence import validate_math_fences
from app.services.math_tools.block import _build_verified_block
from app.services.math_tools.direct import maybe_direct_math_reply
from app.services.math_tools.direct_calculus import calculus_direct_request
from app.services.math_tools.extract import extract_math_intent

_CASES = [
    ("Differentiate x^3", "3 x^{2}"),
    ("Find the second derivative of x^4", "12 x^{2}"),
    ("Find the third derivative of x^4", "24 x"),
    ("Find the partial derivative of x^2*y with respect to y", "x^{2}"),
    ("Integrate x^2", r"\frac{x^{3}}{3} + C"),
    ("Integrate x^2 from 0 to 1", r"\frac{1}{3}"),
    ("Find the limit of sin(x)/x as x approaches 0", "1"),
    ("Find the limit of 1/x as x approaches 0 from the left", r"-\infty"),
    ("Find the limit of 1/x as x approaches 0 from the right", r"\infty"),
    ("Sum n from n=1 to 10", "55"),
    ("Sum 1/n^2 from n=1 to infinity", r"\frac{\pi^{2}}{6}"),
    (
        "Find the Taylor series of exp(x) at 1 order 2",
        r"\frac{e \left(x - 1\right)^{2}}{2} + e \left(x - 1\right) + e",
    ),
    ("Find the Maclaurin series of sin(x) order 3", r"- \frac{x^{3}}{6} + x"),
]
_SETTINGS = Settings(math_tools_enabled=True)


def _verified(query):
    intent = extract_math_intent(query)
    assert intent is not None
    block = _build_verified_block(intent, _SETTINGS)
    assert block is not None
    return block


@pytest.mark.parametrize("query,answer", _CASES)
def test_complete_calculus_request_preserves_the_full_verified_answer(query, answer):
    block = _verified(query)
    assert block.canonical_answer == answer
    assert calculus_direct_request(query) is True
    reply = maybe_direct_math_reply(block, query)
    assert reply == f"```answer\n{answer}\n```\n"
    assert validate_math_fences(reply, verified=block).strip() == reply.strip()


@pytest.mark.parametrize("query,answer", _CASES)
@pytest.mark.parametrize(
    "suffix",
    [" and explain why", " and solve x+1=2", ", hint only", " with steps", " on the domain x>0"],
)
def test_extra_asks_domains_and_teaching_never_disappear(query, answer, suffix):
    assert maybe_direct_math_reply(_verified(query), query + suffix) is None


@pytest.mark.parametrize(
    "query",
    [
        "Find the fourth derivative of x^4",
        "Find the second derivative of x^4 at x=2",
        "Find twice the second derivative of x^4",
        "Differentiate x^3!",
        "Differentiate x^3; 2+2",
        "Differentiate x^3 + sin(x) and cos(x)",
        "Find the partial derivative of x^2*y with respect to y and x",
        "Find the partial derivative of x^2*y with respect to yy",
        "Integrate x^2 from 0 to 1 and 2",
        "Find the definite integral of x^2",
        "Find the indefinite integral of x^2 from 0 to 1",
        "Integrate x^2 with respect to x from 0 to 1, then evaluate at 3",
        "Find the limit of sin(x)/x as x approaches 0 along the complex plane",
        "Find the limit of sin(x)/x as x approaches 0 from both sides and compare them",
        "Sum n from n=1 to 10 excluding n=5",
        "Sum n from n=1 to 10 and n^2",
        "Sum n from n=1 to 10!",
        "Find the Taylor series of exp(x) at 1 order 2 and give the remainder",
        "Find the Taylor series of exp(x) at pi order 2",
        "Find the Maclaurin series of sin(x) order 3.5",
        "Find the Maclaurin series of sin(x) order 0",
    ],
)
def test_unsupported_or_partial_calculus_cannot_use_generic_prose_fallback(query):
    assert calculus_direct_request(query) is False
    assert maybe_direct_math_reply(_verified("Differentiate x^3"), query) is None


@pytest.mark.parametrize(
    "query",
    [
        "Find the limit of 1/x as x approaches 0",
        "Sum (-1)^n from n=0 to infinity",
        "Find the critical points of x^3-3x",
        "Use Newton method to solve x^2-2=0 starting at 1",
    ],
)
def test_outcomes_without_complete_answer_or_method_presentation_keep_model(query):
    assert maybe_direct_math_reply(_verified(query), query) is None


def test_existing_simple_ode_keeps_its_constant_and_direct_behavior():
    query = "Solve dy/dx=2x"
    assert calculus_direct_request(query) is None
    block = _verified(query)
    reply = maybe_direct_math_reply(block, query)
    assert reply is not None and block.canonical_answer in reply
    assert "C_{1}" in reply


@pytest.mark.parametrize(
    "query",
    [
        "Find the second derivative of t^4",
        "Find the partial derivative of x^2*y wrt x",
        "Integrate t^2 dt from -1 to 2",
        "Find the limit of 1/t as t approaches 0 from the left",
        "Sum k^2 from k=2 to 5",
        "Find the Taylor series of exp(x) at -1 order 3",
    ],
)
def test_nonfixture_variables_bounds_and_centers_are_preserved(query):
    block = _verified(query)
    assert calculus_direct_request(query) is True
    assert maybe_direct_math_reply(block, query) == f"```answer\n{block.canonical_answer}\n```\n"


@pytest.mark.parametrize(
    "query,updates",
    [
        ("Find the second derivative of x^4", {"derivative_order": 1}),
        ("Find the second derivative of x^4", {"expr": "x^3"}),
        ("Find the partial derivative of x^2*y wrt y", {"variable": "x"}),
        ("Integrate x^2 from 0 to 1", {"integral_upper": "2"}),
        ("Find the limit of 1/x as x approaches 0 from the left", {"limit_direction": "+"}),
        ("Sum n from n=1 to 10", {"series_end": "11"}),
        ("Find the Taylor series of exp(x) at 1 order 2", {"limit_point": "0"}),
        ("Find the Maclaurin series of sin(x) order 3", {"taylor_n": 2}),
    ],
)
def test_whole_query_must_agree_with_every_extracted_parameter(query, updates):
    intent = extract_math_intent(query)
    assert intent is not None
    with patch(
        "app.services.math_tools.direct_calculus.extract_math_intent",
        return_value=intent.model_copy(update=updates),
    ):
        assert calculus_direct_request(query) is False


def test_images_incomplete_fences_and_unevaluated_results_keep_model():
    query = "Find the second derivative of x^4"
    block = _verified(query)
    assert maybe_direct_math_reply(block, query, has_image_attachment=True) is None
    assert maybe_direct_math_reply(replace(block, canonical_fence=None), query) is None
    assert maybe_direct_math_reply(replace(block, canonical_answer="different"), query) is None
    for answer in (r"\lim_{x\to0}f(x)", r"\int x dx", r"\sum n", r"\frac{d}{dx}f(x)"):
        unresolved = replace(
            block, canonical_answer=answer, canonical_fence={"type": "answer", "content": answer}
        )
        assert maybe_direct_math_reply(unresolved, query) is None


@pytest.mark.parametrize("query", ["Sum n from n=1 to infinity", "Sum -n from n=1 to infinity"])
def test_infinite_sums_retain_the_divergence_explanation(query):
    block = _verified(query)
    assert block.canonical_answer is not None and r"\infty" in block.canonical_answer
    assert maybe_direct_math_reply(block, query) is None


@pytest.mark.parametrize(
    "query",
    [
        "Find the limit of sin(1/x) as x approaches 0",
        "Find the limit of cos(x) as x approaches infinity",
    ],
)
def test_accumulation_bounds_are_not_a_closed_scalar_limit(query):
    block = _verified(query)
    assert block.canonical_answer is not None and r"\langle" in block.canonical_answer
    assert maybe_direct_math_reply(block, query) is None


@pytest.mark.parametrize(
    "query",
    [
        "Integrate 1/x from -1 to 1",
        "Integrate 1/x^2 from -1 to 1",
    ],
)
def test_undefined_or_divergent_improper_integrals_keep_explanation(query):
    block = _verified(query)
    assert block.canonical_answer is not None
    assert "NaN" in block.canonical_answer or r"\infty" in block.canonical_answer
    assert maybe_direct_math_reply(block, query) is None
