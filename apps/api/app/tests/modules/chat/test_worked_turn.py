"""Which turns ask for a ```worked block, and a block's way from the model to the saved reply:
laid out while it streams, then carded under its Answer heading as not checked."""

from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.modules.chat.prompt_constants.worked import RESULT_CHECK_CONTRACT, WORKED_BLOCK_CONTRACT
from app.modules.chat.stream_paths import _apply_tool_rounds
from app.modules.chat.tool_loop.rounds import ToolRoundsOutcome
from app.modules.chat.turn_outcome import TurnOutcome
from app.modules.chat.turn_prep import StreamContext
from app.modules.chat.worked_render import WorkedLayout
from app.modules.chat.worked_turn import (
    checks_stated_results,
    with_result_check_contract,
    with_worked_contract,
    without_worked_contract,
    worked_layout,
)
from app.services.answer_fence import UNCHECKED_ANSWER_MARKER, VERIFIED_ANSWER_MARKER
from app.services.solving import VerifiedMathBlock
from app.tests.fakes import redis_mock
from app.tests.modules.chat.chat_test_support import offline_deps
from app.tests.modules.chat.test_verified_answer_card import _cards, _finalize
from app.tests.modules.chat.test_worked_block import DISPLACEMENT, POLES

DISPLACEMENT_ASK = (
    "A car moves at a speed of 20m/s for 120 seconds due East. What is the displacement of the car?"
)


@pytest.mark.parametrize(
    ("content", "subject", "law_heading"),
    [
        (DISPLACEMENT_ASK, None, False),  # a school exercise: quantities and a question
        ("A cyclist covers 12 km in 40 minutes. Find the average speed in m/s.", "physics", True),
        ("How many moles are in 36 g of water?", "chemistry", False),
        ("Solve 3x + 7 = 1 for x", "math", False),
        (
            "The distance between two electric poles measures 100 meters. What is this "
            "distance in: a. centimeter b. kilometer",
            None,
            False,
        ),
    ],
)
def test_a_calculation_nothing_verified_gets_the_block(
    content: str, subject: str | None, law_heading: bool
) -> None:
    layout = worked_layout(
        content, subject, Settings(), answered=False, lightweight=False, several_requests=False
    )
    assert layout == WorkedLayout(law_heading=law_heading)


@pytest.mark.parametrize(
    ("content", "subject", "flags"),
    [
        # A verified solve, an instant reply or a money card answers it.
        (DISPLACEMENT_ASK, "physics", {"answered": True}),
        ("hi 2 you", None, {"lightweight": True}),
        (DISPLACEMENT_ASK, None, {"several_requests": True}),
        # No number: an explanation, not a calculation.
        ("Why is displacement a vector?", "physics", {}),
        ("What is velocity?", None, {}),
        # Everyday messages with numbers.
        ("Remind me at 5 pm to call mom", None, {}),
        ("I have 3 meetings today, can you help me plan?", None, {}),
        # Taught: the lesson lays itself out.
        ("Teach me Ohm's law with an example: 2 A through 5 ohms", "physics", {}),
    ],
)
def test_other_turns_get_no_block(
    content: str, subject: str | None, flags: dict[str, bool]
) -> None:
    kwargs = {"answered": False, "lightweight": False, "several_requests": False, **flags}
    assert worked_layout(content, subject, Settings(), **kwargs) is None


# Live (2026-11-02): the worked contract on a message of answers to check made the model
# rework all four problems and say it could not see the answers.
_ANSWERS = "My answers: 1) 1 mol 2) 110 g 3) 4.5 x 10^23 molecules 4) 2 mol. Did I get them right?"
_FLAGS = {"answered": False, "lightweight": False, "several_requests": False}


@pytest.mark.parametrize(
    ("content", "subject"),
    [
        (_ANSWERS, "chemistry"),
        ("My answers:\n1. 4 m/s^2\n2. 12 N\nAre these right?", "physics"),
        ("I got x = 4 for 3x - 2 = 10, am I right?", "math"),
    ],
)
def test_results_to_check_get_the_check_not_the_block(content: str, subject: str) -> None:
    assert worked_layout(content, subject, Settings(), **_FLAGS) is None
    assert checks_stated_results(content, subject, answered=False, lightweight=False)


def test_a_question_beside_a_claim_keeps_its_block() -> None:
    content = "How many grams are in 0.5 mol of NaCl? I got 29.2 g, am I right?"
    assert worked_layout(content, "chemistry", Settings(), **_FLAGS) == WorkedLayout()
    assert not checks_stated_results(content, "chemistry", answered=False, lightweight=False)


@pytest.mark.parametrize(
    ("content", "subject", "flags"),
    [
        # Not a calculation turn: no subject, no exercise.
        ("My results from the 5k: 24 minutes. Is that ok?", None, {}),
        (_ANSWERS, "chemistry", {"lightweight": True}),
        # The solver checked it ("check my answer: x = 6"): its verified reply compares.
        ("check my answer: x = 6", "math", {"answered": True}),
        # A calculation to do, not results to check.
        ("How many moles are in 36 g of water?", "chemistry", {}),
    ],
)
def test_other_turns_get_no_check(
    content: str, subject: str | None, flags: dict[str, bool]
) -> None:
    kwargs = {"answered": False, "lightweight": False, **flags}
    assert not checks_stated_results(content, subject, **kwargs)


def test_the_check_contract_sits_beside_the_message() -> None:
    prompt = [{"role": "system", "content": "rules"}, {"role": "user", "content": _ANSWERS}]
    with_contract = with_result_check_contract(prompt)
    assert with_contract[-2] == {"role": "system", "content": RESULT_CHECK_CONTRACT}
    assert with_contract[-1] == {"role": "user", "content": _ANSWERS}


def test_the_setting_turns_the_block_off() -> None:
    settings = Settings(worked_layout_enabled=False)
    kwargs = {"answered": False, "lightweight": False, "several_requests": False}
    assert worked_layout(DISPLACEMENT_ASK, "physics", settings, **kwargs) is None


def test_the_contract_sits_beside_the_message_and_goes_when_a_tool_verifies() -> None:
    prompt = [{"role": "system", "content": "rules"}, {"role": "user", "content": DISPLACEMENT_ASK}]
    with_contract = with_worked_contract(prompt)
    assert with_contract[-2] == {"role": "system", "content": WORKED_BLOCK_CONTRACT}
    assert with_contract[-1]["role"] == "user"
    assert without_worked_contract(with_contract) == prompt


def _ctx(worked: WorkedLayout | None, prompt: str = DISPLACEMENT_ASK) -> StreamContext:
    return StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=with_worked_contract([{"role": "user", "content": prompt}]),
        run_title=False,
        user_message_content=prompt,
        reserved_tokens=0,
        max_output_tokens=50,
        skip_memory_jobs=True,
        worked=worked,
    )


def test_a_tool_that_verifies_the_turn_withdraws_the_block() -> None:
    ctx = _ctx(WorkedLayout())
    verified = VerifiedMathBlock(
        text="unused",
        canonical_fence={"type": "answer", "content": "x = 6"},
        canonical_answer="x = 6",
    )
    _apply_tool_rounds(ctx, ToolRoundsOutcome(ctx.prompt_messages, verified, None, []))
    assert ctx.worked is None
    assert all(message["content"] != WORKED_BLOCK_CONTRACT for message in ctx.prompt_messages)


async def _streamed(reply: str, worked: WorkedLayout | None) -> tuple[list[str], str]:
    """The model writes ``reply`` in small chunks: what the phone was sent, and the reply
    the stream hands the finalize passes."""
    from app.modules.chat.stream_accum import StreamAccum
    from app.modules.chat.stream_paths import run_llm_token_stream

    async def fake_stream(**_kwargs: object) -> AsyncIterator[str]:
        for start in range(0, len(reply), 9):
            yield reply[start : start + 9]
            await asyncio.sleep(0)

    accum = StreamAccum()
    yielded: list[str] = []
    deps = offline_deps(llm={"stream_chat_completion": fake_stream})
    async for token in run_llm_token_stream(
        deps,
        redis_mock(),
        Settings(max_output_tokens=100, mcp_tool_loop_enabled=False),
        _ctx(worked),
        usage={},
        should_cancel=None,
        outcome=TurnOutcome(),
        on_reasoning=None,
        accum=accum,
    ):
        yielded.append(token)
    return yielded, accum.reply_text()


@pytest.mark.asyncio
async def test_the_phone_is_sent_the_layout_and_the_reply_saves_with_a_not_checked_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    yielded, sent = await _streamed(DISPLACEMENT, WorkedLayout(law_heading=True))
    streamed = "".join(yielded)
    assert sent == streamed.strip()
    saved = await _finalize(monkeypatch, sent, prompt=DISPLACEMENT_ASK)
    assert streamed.startswith("**Given**  \n$v = 20\\,\\mathrm{m/s}$")
    assert "given:" not in streamed and "```worked" not in streamed
    assert len(yielded) > 3  # section by section, not all at the end
    assert (
        "**Answer**\n\n```answer\nverified: false\n$2400\\,\\mathrm{m}\\ \\text{east}$\n```"
        in saved
    )
    assert VERIFIED_ANSWER_MARKER not in saved
    # Every section survives the finalize passes (the prompt-leak pass among them).
    for heading in (
        "**Given**",
        "**Required**",
        "**Solution**",
        "**Constant velocity formula**",
        "**Substitution**",
    ):
        assert heading in saved


@pytest.mark.asyncio
async def test_a_turn_without_the_block_streams_the_model_text() -> None:
    yielded, _saved = await _streamed(DISPLACEMENT, None)
    assert "".join(yielded) == DISPLACEMENT


@pytest.mark.asyncio
async def test_a_question_in_parts_saves_a_card_per_part(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.modules.chat.worked_stream import WorkedFilter

    worked = WorkedFilter(WorkedLayout())
    worked.feed(POLES)
    worked.close()
    out = await _finalize(monkeypatch, worked.text, prompt="What is 100 m in cm and km?")
    assert _cards(out) == [
        f"{UNCHECKED_ANSWER_MARKER}\n$d_{{cm}} = 10000\\,\\mathrm{{cm}}$",
        f"{UNCHECKED_ANSWER_MARKER}\n$d_{{km}} = 0.1\\,\\mathrm{{km}}$",
    ]
    assert re.search(r"\*\*Answer \(a\)\*\*\n\n```answer\n", out)


@pytest.mark.asyncio
async def test_the_model_cannot_mark_its_own_card_checked_or_unchecked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reply = "**Given**  \n$x + 2 = 5$\n\n**Answer**\n\n```answer\nverified: false\nx = 3\n```"
    out = await _finalize(monkeypatch, reply, prompt="x + 2 = 5, explain each step")
    assert VERIFIED_ANSWER_MARKER not in out
    assert _cards(out) == [f"{UNCHECKED_ANSWER_MARKER}\nx = 3"]
