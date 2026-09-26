"""Word problems: translated by a model, trusted only once SymPy closes them."""

from __future__ import annotations

from typing import Any

import pytest

from app.core.config import Settings
from app.gateways import litellm_gateway
from app.models.schemas.math import MathIntent
from app.models.schemas.math.word_problem import WordProblemSetup
from app.modules.math import tools as mt
from app.modules.math.solve.word_problem import solve_word_problem
from app.modules.math.tools import prompt as math_prompt
from app.modules.math.tools.direct import maybe_direct_math_reply
from app.modules.math.tools.word_problem import (
    grounded,
    word_problem_candidate,
    word_problem_intent,
)

AGES = (
    "Maria is three times as old as her son. Together their ages add up to 48. How old is her son?"
)
AGES_SETUP: dict[str, Any] = {
    "found": True,
    "unknowns": [
        {"symbol": "m", "meaning": "Maria's age now", "unit": "years"},
        {"symbol": "s", "meaning": "her son's age now", "unit": "years"},
    ],
    "equations": [
        {"equation": "m = 3*s", "source": "Maria is three times as old as her son"},
        {"equation": "m + s = 48", "source": "Together their ages add up to 48"},
    ],
    "targets": [{"expr": "s", "meaning": "her son's age", "unit": "years"}],
    "whole_numbers": True,
    "positive": True,
}
TICKETS = (
    "Tickets cost $5 for kids and $8 for adults. 20 people paid $124 in total. "
    "How many adults went?"
)
TICKETS_SETUP: dict[str, Any] = {
    "found": True,
    "unknowns": [
        {"symbol": "k", "meaning": "number of kids"},
        {"symbol": "a", "meaning": "number of adults"},
    ],
    "equations": [{"equation": "k + a = 20"}, {"equation": "5*k + 8*a = 124"}],
    "targets": [{"expr": "a", "meaning": "adults who went"}],
    "whole_numbers": True,
    "positive": True,
}
CONSECUTIVE = "Three consecutive integers add up to 72. Find the integers."
CONSECUTIVE_SETUP: dict[str, Any] = {
    "found": True,
    "unknowns": [{"symbol": "n", "meaning": "the smallest integer"}],
    "equations": [{"equation": "n + (n + 1) + (n + 2) = 72"}],
    "targets": [
        {"expr": "n", "meaning": "first"},
        {"expr": "n + 1", "meaning": "second"},
        {"expr": "n + 2", "meaning": "third"},
    ],
    "whole_numbers": True,
}
PENCIL = (
    "A pen costs $1.50 more than a pencil. Together they cost $2.10. What does the pencil cost?"
)
PENCIL_SETUP: dict[str, Any] = {
    "found": True,
    "unknowns": [{"symbol": "p", "meaning": "price of the pencil", "unit": "$"}],
    "equations": [{"equation": "p + (p + 1.50) = 2.10"}],
    "targets": [{"expr": "p", "meaning": "the pencil costs", "unit": "$"}],
    "positive": True,
}


def _setup(base: dict[str, Any], **overrides: Any) -> WordProblemSetup:
    return WordProblemSetup.model_validate({**base, **overrides})


def _settings(**overrides: Any) -> Settings:
    return Settings(**{"math_tools_enabled": True, **overrides})


def _gateway(payload: dict[str, Any] | None) -> Any:
    async def fake(*, schema: type, **kwargs: Any) -> Any:
        if schema is not WordProblemSetup or payload is None:
            return None
        return WordProblemSetup.model_validate(payload)

    return fake


# --- the gate ------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        AGES,
        TICKETS,
        CONSECUTIVE,
        PENCIL,
        "A number plus 7 is 19. What is the number?",
        "The sum of two numbers is 30 and their difference is 6. What are the numbers?",
        "John has 5 more apples than Sam. Together they have 23 apples. How many does Sam have?",
    ],
)
def test_candidate_fires_for_algebra_word_problems(text: str) -> None:
    assert word_problem_candidate(text)


@pytest.mark.parametrize(
    "text",
    [
        "How many people live in Paris?",
        "How many calories are in two eggs and three slices of bacon in total?",
        "I have 3 cats and 2 dogs, what should I name them?",
        "solve 2x+3=11",
        "Find 2 + 2",
        "A ball is thrown straight up at 20 m/s. How high does it go in total?",
        "What is the sum of 3 and 4? " * 40,
    ],
)
def test_candidate_declines(text: str) -> None:
    assert not word_problem_candidate(text)


def test_gate_opens_for_a_word_problem() -> None:
    assert mt.needs_symbolic_math(AGES)


# --- the number guard ------------------------------------------------------------


@pytest.mark.parametrize(
    "text, equation",
    [
        (AGES, "m = 3*s"),
        (AGES, "m + s = 48"),
        (CONSECUTIVE, "n + (n + 1) + (n + 2) = 72"),
        (PENCIL, "p + (p + 1.5) = 2.1"),
        ("Half of a number is 9. What is the number?", "0.5*n = 9"),
        ("Half of a number is 9. What is the number?", "n/2 = 9"),
        ("After a 20% discount a shirt costs $40. What was the price?", "p - 0.2*p = 40"),
        ("After a 20% discount a shirt costs $40. What was the price?", "p*(100 - 20)/100 = 40"),
        ("A dozen eggs cost $3 more than 6 apples. Find the cost.", "c = 12"),
    ],
)
def test_grounded_accepts_numbers_the_problem_states(text: str, equation: str) -> None:
    setup = _setup(
        AGES_SETUP, equations=[{"equation": equation}], targets=[{"expr": "1", "meaning": "x"}]
    )
    assert grounded(setup, text)


def test_grounded_refuses_a_smuggled_number() -> None:
    text = "John has 5 more apples than Sam. Together they have 23 apples. How many does Sam have?"
    setup = _setup(
        AGES_SETUP,
        equations=[{"equation": "s + (s + 7) = 23"}],
        targets=[{"expr": "s", "meaning": "Sam's apples"}],
    )
    assert not grounded(setup, text)


def test_grounded_checks_targets_too() -> None:
    setup = _setup(AGES_SETUP, targets=[{"expr": "s + 4", "meaning": "age in 4 years"}])
    assert not grounded(setup, AGES)


# --- solving ---------------------------------------------------------------------


def test_solve_ages() -> None:
    solution = solve_word_problem(_setup(AGES_SETUP))
    assert solution is not None
    assert dict(solution.values) == {"m": 36, "s": 12}
    assert solution.answers == (12,)
    assert solution.steps and solution.check is not None
    assert solution.equations == ("m = 3 \\cdot s", "m + s = 48")


def test_solve_tickets_as_a_system() -> None:
    solution = solve_word_problem(_setup(TICKETS_SETUP))
    assert solution is not None
    assert dict(solution.values) == {"k": 12, "a": 8}
    assert solution.steps[0].label == "Solve equation (1) for k"


def test_solve_consecutive_integers_shows_the_combining_step() -> None:
    solution = solve_word_problem(_setup(CONSECUTIVE_SETUP))
    assert solution is not None
    assert solution.answers == (23, 24, 25)
    assert solution.steps[0].label == "Simplify"
    assert solution.steps[0].formula == "3 n + 3 = 72"
    assert solution.equations == ("n + (n + 1) + (n + 2) = 72",)


def test_solve_keeps_one_root_that_fits_the_domain() -> None:
    setup = _setup(
        AGES_SETUP,
        unknowns=[{"symbol": "w", "meaning": "width"}],
        equations=[{"equation": "w*(w + 3) = 40"}],
        targets=[{"expr": "w", "meaning": "width"}],
    )
    solution = solve_word_problem(setup)
    assert solution is not None and solution.answers == (5,)


@pytest.mark.parametrize(
    "overrides",
    [
        # A fractional count is a misreading, not an answer.
        {"equations": [{"equation": "k + a = 20"}, {"equation": "5*k + 8*a = 125"}]},
        # Two roots both fit: the problem is ambiguous as read.
        {
            "unknowns": [{"symbol": "n", "meaning": "n"}],
            "equations": [{"equation": "n^2 + 6 = 5*n"}],
            "targets": [{"expr": "n", "meaning": "n"}],
        },
        # A negative age.
        {"equations": [{"equation": "k + 30 = 20"}, {"equation": "a = 1"}]},
        # An unknown the setup never declared.
        {"equations": [{"equation": "k + q = 20"}, {"equation": "5*k + 8*a = 124"}]},
        # Fewer equations than unknowns.
        {"equations": [{"equation": "k + a = 20"}]},
        # No equals sign, or two.
        {"equations": [{"equation": "k + a"}, {"equation": "5*k + 8*a = 124"}]},
        {"equations": [{"equation": "k = a = 20"}, {"equation": "5*k + 8*a = 124"}]},
        # Inconsistent.
        {"equations": [{"equation": "k + a = 20"}, {"equation": "k + a = 21"}]},
        # A reserved letter.
        {"unknowns": [{"symbol": "e", "meaning": "e"}, {"symbol": "a", "meaning": "a"}]},
        # Nothing asked.
        {"targets": []},
        {"found": False},
    ],
)
def test_solve_refuses(overrides: dict[str, Any]) -> None:
    assert solve_word_problem(_setup(TICKETS_SETUP, **overrides)) is None


# --- replies ---------------------------------------------------------------------


def _reply(payload: dict[str, Any], text: str) -> str | None:
    intent = MathIntent(
        kind="word_problem",
        word_problem=WordProblemSetup.model_validate(payload),
        operation="solve",
    )
    block = mt._build_verified_block(intent, _settings())
    assert block is not None
    return maybe_direct_math_reply(block, text)


def test_reply_shows_setup_steps_and_answer() -> None:
    reply = _reply(AGES_SETUP, AGES)
    assert reply is not None
    assert "**Let**\n$m$ = Maria's age now (years)\n$s$ = her son's age now (years)" in reply
    assert '$m = 3 \\cdot s$ (from "Maria is three times as old as her son")' in reply
    assert "**Solve**" in reply and "Check: $" in reply
    assert "**Answer:** her son's age: $12$ years" in reply
    assert reply.rstrip().endswith("```answer\n12\\ \\text{years}\n```")


def test_money_answer_reads_as_dollars() -> None:
    reply = _reply(PENCIL_SETUP, PENCIL)
    assert reply is not None
    assert "**Answer:** the pencil costs: $0.30$ dollars" in reply
    assert "```answer\n\\$0.30\n```" in reply
    assert "**1. Simplify**" in reply
    assert "**2. Subtract $\\frac{3}{2}$ from both sides**" in reply


def test_reply_strips_markup_from_the_translation() -> None:
    payload = {
        **AGES_SETUP,
        "unknowns": [
            {"symbol": "m", "meaning": "**Maria** `age` [link](x) $\\evil$"},
            {"symbol": "s", "meaning": "son", "unit": "years}\\"},
        ],
    }
    reply = _reply(payload, AGES)
    assert reply is not None
    for leaked in ("**Maria**", "`age`", "[link]", "\\evil", "(years}\\)"):
        assert leaked not in reply


def test_photo_attached_keeps_the_model_path() -> None:
    intent = MathIntent(
        kind="word_problem",
        word_problem=WordProblemSetup.model_validate(AGES_SETUP),
        operation="solve",
    )
    block = mt._build_verified_block(intent, _settings())
    assert block is not None
    assert maybe_direct_math_reply(block, AGES, has_image_attachment=True) is None


# --- extraction and the turn --------------------------------------------------------


@pytest.mark.asyncio
async def test_intent_makes_no_call_when_off_or_not_a_word_problem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def boom(**kwargs: Any) -> None:
        raise AssertionError("the model must not be called")

    monkeypatch.setattr(litellm_gateway, "complete_structured", boom)
    assert await word_problem_intent(AGES, _settings(math_word_problems_enabled=False)) is None
    assert await word_problem_intent("How many people live in Paris?", _settings()) is None


@pytest.mark.asyncio
async def test_intent_uses_one_bounded_call(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    async def fake(**kwargs: Any) -> WordProblemSetup:
        seen.update(kwargs)
        return WordProblemSetup.model_validate(AGES_SETUP)

    monkeypatch.setattr(litellm_gateway, "complete_structured", fake)
    intent = await word_problem_intent(AGES, _settings())
    assert intent is not None and intent.kind == "word_problem"
    assert seen["model_alias"] == "title-model"
    assert seen["schema"] is WordProblemSetup
    assert seen["allow_fallback"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        None,
        {"found": False},
        {**AGES_SETUP, "equations": [{"equation": "m = 7*s"}, {"equation": "m + s = 48"}]},
    ],
)
async def test_intent_refuses_missing_or_ungrounded(
    monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any] | None
) -> None:
    monkeypatch.setattr(litellm_gateway, "complete_structured", _gateway(payload))
    assert await word_problem_intent(AGES, _settings()) is None


@pytest.mark.asyncio
async def test_intent_survives_a_gateway_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def raises(**kwargs: Any) -> None:
        raise RuntimeError("provider down")

    monkeypatch.setattr(litellm_gateway, "complete_structured", raises)
    assert await word_problem_intent(AGES, _settings()) is None


@pytest.mark.asyncio
async def test_turn_verifies_and_replies_directly(
    monkeypatch: pytest.MonkeyPatch, thread_sympy_executor: None
) -> None:
    monkeypatch.setattr(litellm_gateway, "complete_structured", _gateway(TICKETS_SETUP))
    _note, verified = await math_prompt.build_math_augmentation(TICKETS, _settings())
    assert verified is not None and verified.canonical_answer == "8"
    reply = maybe_direct_math_reply(verified, TICKETS)
    assert reply is not None and "**Answer:** adults who went: $8$" in reply


@pytest.mark.asyncio
async def test_turn_with_an_unverifiable_translation_keeps_the_honesty_note(
    monkeypatch: pytest.MonkeyPatch, thread_sympy_executor: None
) -> None:
    # Every number is stated, but the reading gives 140/3 kids: SymPy refuses it.
    payload = {
        **TICKETS_SETUP,
        "equations": [{"equation": "k + a = 20"}, {"equation": "5*k + 8*a = 20"}],
    }
    monkeypatch.setattr(litellm_gateway, "complete_structured", _gateway(payload))
    note, verified = await math_prompt.build_math_augmentation(TICKETS, _settings())
    assert verified is None
    assert note is not None and "could not be produced" in note
