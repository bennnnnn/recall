"""A model's reading of a problem is no verified answer unless it is the user's own maths.

SymPy checks the arithmetic of the equations it is given, not that they say what the problem
says (2026-11-01 live baseline). "The polynomial f(x) = A(x - 1)^2 + B(x + 2)^2 is divided by
x + 1 and x - 2. The remainders are 3 and -15" was read by the model as 9B = 3 and
A + 16B = -15, and the checked card said A = -61/3, B = 1/3 (right: A = 1, B = -1). "If this
process continues without end, find the total tax" was summed over three rounds, 3920 Birr
for 5000. A model's extraction is certified only when its equation or expression is one the
user wrote; a word problem's translation never is (the model gets it as an unchecked setup to
check against the words), and a process that never ends gets no setup at all. A setup the
server's own templates read keeps its card.
"""

from __future__ import annotations

import pickle
from typing import Any

import pytest

from app.core.config import Settings
from app.gateways import litellm_gateway
from app.modules.math.schemas.word_problem import WordProblemSetup
from app.modules.math.tools import prompt as math_prompt
from app.modules.math.tools.llm_extract import LLMMathExtract
from app.modules.math.tools.word_problem import word_problem_intent
from app.modules.math.tools.word_templates import word_template_setup

REMAINDERS = (
    "The polynomial f(x) = A(x - 1)^2 + B(x + 2)^2 is divided by x + 1 and x - 2. The "
    "remainders are 3 and -15 respectively. Find the values of A and B."
)
ENDLESS_TAX = (
    "Suppose you earn Birr 10,000.00 per month and pay 20% tax and spend 60% of it. Again the "
    "recipient of the money spent by you pays 20% tax and spends 60% of it. If this process "
    "continues without end, find the total amount that will be paid for the tax."
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
CONSECUTIVE = "Three consecutive integers add up to 72. Find the integers."


def _settings() -> Settings:
    return Settings(math_tools_enabled=True, math_llm_extract_enabled=True)


def _models(*, setup: dict[str, Any] | None = None, extract: LLMMathExtract | None = None) -> Any:
    """The structured calls: the word-problem translation and the maths extraction."""

    async def fake(*, schema: type, **_kwargs: Any) -> Any:
        if schema is WordProblemSetup:
            return None if setup is None else WordProblemSetup.model_validate(setup)
        return extract

    return fake


@pytest.mark.asyncio
async def test_a_translated_word_problem_is_an_unchecked_setup(
    monkeypatch: pytest.MonkeyPatch, thread_sympy_executor: None
) -> None:
    monkeypatch.setattr(litellm_gateway, "complete_structured", _models(setup=AGES_SETUP))
    note, verified = await math_prompt.build_math_augmentation(AGES, _settings())
    assert verified is None
    assert note is not None
    assert "read by a model (not checked against the problem)" in note
    assert '(from "Together their ages add up to 48")' in note
    assert "SymPy's solution of these equations: m = 36, s = 12" in note
    assert "Do NOT claim the answer was verified" in note


@pytest.mark.asyncio
async def test_a_setup_the_templates_read_keeps_its_card(
    monkeypatch: pytest.MonkeyPatch, thread_sympy_executor: None
) -> None:
    async def no_call(**_kwargs: Any) -> Any:
        raise AssertionError("a template reads this problem without a model")

    monkeypatch.setattr(litellm_gateway, "complete_structured", no_call)
    _note, verified = await math_prompt.build_math_augmentation(CONSECUTIVE, _settings())
    assert verified is not None and verified.canonical_answer is not None


@pytest.mark.asyncio
async def test_the_models_reading_of_a_remainder_problem_gets_no_card(
    monkeypatch: pytest.MonkeyPatch, thread_sympy_executor: None
) -> None:
    misread = LLMMathExtract(
        found=True,
        kind="system",
        equations=[("9*B", "3"), ("A + 16*B", "-15")],
        variables=["A", "B"],
    )
    monkeypatch.setattr(math_prompt, "extract_math_intent", lambda _text: None)
    monkeypatch.setattr(litellm_gateway, "complete_structured", _models(extract=misread))
    _note, verified = await math_prompt.build_math_augmentation(REMAINDERS, _settings())
    assert verified is None


@pytest.mark.asyncio
async def test_a_process_without_end_gets_no_setup(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_call(**_kwargs: Any) -> Any:
        raise AssertionError("an endless process is not translated")

    monkeypatch.setattr(litellm_gateway, "complete_structured", no_call)
    assert await word_problem_intent(ENDLESS_TAX, _settings()) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "certified"),
    [("Integrate x^2 please", True), ("Integrate x squared", False)],
)
async def test_the_models_extraction_is_certified_only_as_the_users_own_maths(
    monkeypatch: pytest.MonkeyPatch, thread_sympy_executor: None, text: str, certified: bool
) -> None:
    read = LLMMathExtract(found=True, kind="calculus", operation="integrate", expr="x^2")
    monkeypatch.setattr(math_prompt, "extract_math_intent", lambda _text: None)
    monkeypatch.setattr(litellm_gateway, "complete_structured", _models(extract=read))
    _note, verified = await math_prompt.build_math_augmentation(text, _settings())
    assert (verified is not None) is certified


def test_a_models_json_cannot_mark_its_setup_read_from_the_text() -> None:
    forged = WordProblemSetup.model_validate({**AGES_SETUP, "_read_from_text": True})
    assert not forged.read_from_text
    template = word_template_setup(CONSECUTIVE)
    assert template is not None and template.read_from_text
    # The SymPy pool gets the setup pickled: the mark goes with it.
    assert pickle.loads(pickle.dumps(template)).read_from_text  # noqa: S301 - our own object
