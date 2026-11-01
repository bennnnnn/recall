"""A verified card whose solve did not read a count (or, in "all", a number) the question
states is dropped (``services/verified_numbers``).

The probes are the reviews' of #2172 and #2178 (``verified_numbers_probes.json``): every
card a solver gives them, and whether the ``counts`` gate drops it. Dropped: a count of
valued items read once ("thirty 60 W bulbs", "both of my phones charge at 20 W", "two
horses each pull ... 400 N"). Kept: counts the solve read (R1 = R2), parts with no value
each, totals, questions about one item, "some" meaning "about".
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Literal

import pytest

from app.core.config import Settings
from app.services import verified_numbers
from app.services.solving import VerifiedSolveBlock
from app.services.subject_solving import build_subject_augmentation
from app.services.verified_numbers import ReadInputs, check, gate_card

Gate = Literal["off", "counts", "all"]
PROBES: list[tuple[str, bool]] = [
    (text, dropped)
    for text, dropped in json.loads(
        Path(__file__).with_name("verified_numbers_probes.json").read_text()
    )
]


def _settings(gate: Gate) -> Settings:
    return Settings(
        math_llm_extract_enabled=False, math_word_problems_enabled=False, verified_numbers_gate=gate
    )


async def _card(text: str, gate: Gate) -> str | None:
    verified = (await build_subject_augmentation(text, _settings(gate))).verified
    return getattr(verified, "canonical_answer", None)


@pytest.mark.asyncio
@pytest.mark.parametrize(("text", "dropped"), PROBES, ids=[text[:60] for text, _ in PROBES])
async def test_the_counts_gate_drops_a_card_that_reads_one_of_many_items(
    thread_sympy_executor: None, text: str, dropped: bool
) -> None:
    assert await _card(text, "off") is not None
    assert (await _card(text, "counts") is None) is dropped


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "What is the total mass of 2 moles of NaCl and 3 moles of water?",
        "If you remove 5 from it, what is 25% of 80?",
    ],
)
async def test_a_card_that_skips_a_number_is_dropped_only_when_every_number_counts(
    thread_sympy_executor: None, text: str
) -> None:
    assert await _card(text, "counts") is not None
    assert await _card(text, "all") is None


@pytest.mark.parametrize(
    "text",
    [
        # A comma sets off what each item has (#2178 review).
        "Two horses, each pulling with 400 N, are attached to a 200 kg cart. Find the "
        "acceleration.",
        # Not read through another quantity's number: a 2000 kg cart is no second horse.
        "Two horses each pull a cart with a force of 400 N. The cart has a mass of 2000 kg.",
    ],
)
def test_one_horse_read_for_two_is_unread(text: str) -> None:
    mass = 2000.0 if "2000" in text else 200.0
    inputs = ReadInputs("physics", measured=((400.0, "N"), (mass, "kg")))
    assert check(text, inputs, "counts").missed == ("count",)


def test_a_count_is_read_only_through_its_own_quantity() -> None:
    """20 W and 20 hours are two numbers 20, not two phones' 20 W (#2178 review)."""
    inputs = ReadInputs("physics", measured=((20.0, "W"), (20.0, "h")))
    question = "Both of my phones charge at 20 W. How much energy do they use in 20 hours?"
    assert check(question, inputs, "counts").missed == ("count",)
    read_twice = ReadInputs("physics", measured=((20.0, "W"), (20.0, "W"), (20.0, "h")))
    assert check(question, read_twice, "counts").stands


@pytest.mark.parametrize(
    ("text", "count"),
    [
        ("Thirty 60 W bulbs are on for 5 hours.", "count"),
        ("30 60 W bulbs are on for 5 hours.", "count"),
        ("Twenty-one 60 W bulbs are on for 5 hours.", "count"),
        ("A hundred 60 W bulbs are on for 5 hours.", "count"),
        ("Several 60 W bulbs are on for 5 hours.", "vague"),
    ],
)
def test_any_count_of_valued_items_is_held(text: str, count: str) -> None:
    inputs = ReadInputs("physics", measured=((60.0, "W"), (5.0, "h")))
    assert check(text, inputs, "counts").missed == (count,)


def test_a_number_no_float_holds_fails_the_check_and_never_raises() -> None:
    inputs = ReadInputs("physics", measured=((3e8, "m/s"),))
    text = "A wave has a frequency of 1 × 10^1000 Hz and a speed of 3 × 10^8 m/s."
    assert check(text, inputs, "counts").missed == ("number",)


@pytest.mark.asyncio
async def test_a_check_that_fails_drops_the_card(
    thread_sympy_executor: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_args: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(verified_numbers.gate, "check", broken)
    block = VerifiedSolveBlock(text="R = 5 Ω", subject="physics", canonical_answer="5 Ω")
    result = await gate_card("Two 10 Ω resistors", block, _settings("counts"))
    assert not result.stands
    assert result.missed == ("error",)


@pytest.mark.wall_clock
@pytest.mark.parametrize(
    "text",
    [
        "Question" + " " * 3990,
        "two " + "9" * 3990 + " bulbs",
        "1 x 10^" + "9" * 3990,
        "several " + "1." * 1990,
        "Question" + " " * 30_000,
    ],
)
def test_a_hostile_message_is_read_in_bounded_time(text: str) -> None:
    started = time.perf_counter()
    check(text, ReadInputs("physics"), "all")
    assert time.perf_counter() - started < 0.5


@pytest.mark.asyncio
async def test_a_maths_follow_up_is_gated_on_the_problem_it_solved(
    thread_sympy_executor: None,
) -> None:
    """The follow-up line names numbers the solve never read; the problem it solved is
    what the gate reads (#2178 review)."""
    augmentation = await build_subject_augmentation(
        "now the same for 20 identical bulbs at 60 W",
        _settings("all"),
        math_user_content="what is 25% of 80",
        detected_subject="math",
    )
    assert getattr(augmentation.verified, "canonical_answer", None) == "20"


@pytest.mark.asyncio
async def test_a_dropped_card_does_not_come_back_through_the_models_own_solve(
    thread_sympy_executor: None,
) -> None:
    """The tool loop's own solve is held to the gate as the server's is (#2178 review)."""
    from app.modules.chat.tool_verified import with_tool_verified

    question = "Twenty 60 W bulbs are on for 5 hours. Find the energy used."
    tool = (await build_subject_augmentation(question, _settings("off"))).verified
    assert tool is not None
    assert await with_tool_verified(None, tool, question, _settings("counts")) is None
    assert await with_tool_verified(None, tool, question, _settings("off")) is tool
