"""A question in parts: each solve part of the turn's plan is solved on its own.

"A ball is dropped from 20 m. What is its speed after 1 s? How long does it take to reach
the ground?" is two questions about one problem (``turn_prep.intents``). Read whole, physics
verified neither; each part, with the setup it carries, verifies, and the reply lays them out
lettered (``services.subjects.dispatch.build_subject_augmentation``'s ``parts``).
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from app.core.config import Settings
from app.services.subjects.dispatch import build_subject_augmentation
from app.services.worked_parts import answers_in_parts

_SETTINGS = Settings.model_validate({})
_SETUP = "A ball is dropped from 20 m."
_PARTS = (
    f"{_SETUP} What is its speed after 1 s?",
    f"{_SETUP} How long does it take to reach the ground?",
)


def test_the_parts_are_lettered_under_their_own_questions() -> None:
    text = answers_in_parts(_PARTS, ["**Answer**\n\n9.81 m/s", "**Answer**\n\n2.02 s"])

    assert text.startswith("**(a) What is its speed after 1 s?**")
    assert "**(b) How long does it take to reach the ground?**" in text
    assert re.findall(r"\*\*Answer \(([ab])\)\*\*", text) == ["a", "b"]
    assert _SETUP not in text


async def test_every_part_of_a_question_in_parts_is_worked() -> None:
    whole = " ".join([_SETUP, "What is its speed after 1 s?", _PARTS[1].removeprefix(_SETUP)])

    found = await build_subject_augmentation(whole, _SETTINGS, parts=_PARTS, parts_answer_all=True)

    assert found.verified is not None and found.verified.subject == "physics"
    assert found.direct_text is not None
    assert "**Answer (a)**" in found.direct_text and "**Answer (b)**" in found.direct_text
    assert "9.81" in found.direct_text and "2.02" in found.direct_text


async def test_a_part_beside_another_request_keeps_its_card() -> None:
    whole = f"{_PARTS[0]} {_PARTS[1].removeprefix(_SETUP).strip()} What's the weather today?"

    found = await build_subject_augmentation(whole, _SETTINGS, parts=_PARTS, parts_answer_all=False)

    # The weather is the model's: no reply is written here, but a part's card stands.
    assert found.direct_text is None
    assert found.verified is not None and found.verified.subject == "physics"


async def test_a_part_whose_read_gives_up_leaves_the_others_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One part's read timing out is that part unsolved: it never declines the readings of
    the parts after it, nor the rest of the turn's (audit 2026-11-25)."""
    from app.core import readings, sympy_executor
    from app.services.subjects import dispatch

    real = sympy_executor.run_sympy

    async def first_part_times_out(fn: Any, *args: Any, **kwargs: Any) -> Any:
        if fn is readings._record and args[0] is dispatch._subject_of_text:
            if args[1][0] == _PARTS[0]:
                raise TimeoutError
        return await real(fn, *args, **kwargs)

    monkeypatch.setattr(sympy_executor, "run_sympy", first_part_times_out)
    readings.begin_turn()
    whole = f"{_PARTS[0]} {_PARTS[1].removeprefix(_SETUP).strip()}"

    found = await build_subject_augmentation(whole, _SETTINGS, parts=_PARTS, parts_answer_all=False)

    assert not readings.readings_declined()
    assert found.verified is not None and found.verified.subject == "physics"


async def test_a_maths_part_whose_solve_read_gives_up_leaves_the_others_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A subject's own reads in a part's solve are the part's too: maths reading its first
    part timing out leaves the second part and the whole message read (review of #2589)."""
    from app.core import readings, sympy_executor

    real = sympy_executor.run_sympy
    parts = ("Solve 2x + 3 = 11.", "Solve 3x - 4 = 5.")

    async def first_read_times_out(fn: Any, *args: Any, **kwargs: Any) -> Any:
        if fn is readings._record and getattr(args[0], "__name__", "") == "read_math_request":
            if args[1][0] == parts[0]:
                raise TimeoutError
        return await real(fn, *args, **kwargs)

    monkeypatch.setattr(sympy_executor, "run_sympy", first_read_times_out)
    readings.begin_turn()

    found = await build_subject_augmentation(
        " ".join(parts), _SETTINGS, parts=parts, parts_answer_all=False
    )

    assert not readings.readings_declined()
    assert found.verified is not None and found.verified.subject == "math"
