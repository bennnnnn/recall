"""What "it" is: a fast model's pick of an earlier message (``chat.referent_read``)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.modules.chat import referent_read
from app.modules.chat.referent_read import (
    ContinuationPick,
    Referent,
    ReferentPick,
    read_continuation,
    read_referent,
)

_TRIANGLE_CHAT = [
    ("user", "Differentiate sin(x^2)cos(x^2)"),
    ("assistant", "2x cos(2x^2)"),
    ("user", "Triangle are with sides 5, 4,"),
    ("assistant", "What's the third side length? 🔺"),
    ("user", "3"),
    ("assistant", "Sides 3, 4 and 5 make a right triangle."),
    ("user", "The area"),
    ("assistant", "6 square units."),
    ("user", "Do it properly"),
    ("assistant", "Area = 6."),
    ("user", "Draw it"),
]


def _rows(pairs: list[tuple[str, str]]) -> list[SimpleNamespace]:
    return [SimpleNamespace(role=role, content=content) for role, content in pairs]


async def _read(
    line: str, rows: list[Any], pick: ReferentPick | None
) -> tuple[Referent | None, AsyncMock]:
    model = AsyncMock(return_value=pick)
    with patch.object(referent_read, "pick_referent", model):
        return await read_referent(Settings(), line, rows), model


@pytest.mark.parametrize("message", [2, 3, 4])
@pytest.mark.asyncio
async def test_draw_it_is_the_problem_the_model_names_whole(message: int) -> None:
    """Whichever piece of the triangle the model names, it is drawn with all three sides."""
    referent, model = await _read("Draw it", _rows(_TRIANGLE_CHAT), ReferentPick(message=message))
    assert referent == Referent("Triangle are with sides 5, 4, 3")
    assert model.await_args is not None
    conversation = model.await_args.args[2]
    assert "[1] User: Differentiate sin(x^2)cos(x^2)" in conversation
    assert "Draw it" not in conversation  # the turn's own line is the latest message


@pytest.mark.asyncio
async def test_none_and_no_read_are_told_apart() -> None:
    rows = _rows(_TRIANGLE_CHAT)
    assert (await _read("Draw it", rows, ReferentPick(message=None)))[0] == Referent(None)
    # A failed, mocked or late read, and a pick out of range: answered as before.
    assert (await _read("Draw it", rows, None))[0] is None
    assert (await _read("Draw it", rows, ReferentPick(message=9)))[0] is None


@pytest.mark.parametrize(
    "line",
    ["what is the domain?", "give me that", "send me that", "show me how", "画出来", "wow"],
)
@pytest.mark.asyncio
async def test_a_line_that_asks_to_see_nothing_is_not_read(line: str) -> None:
    referent, model = await _read(line, _rows(_TRIANGLE_CHAT[:-1]), ReferentPick(message=1))
    assert referent is None
    model.assert_not_awaited()


_BALL_CHAT = [
    ("user", "a ball is thrown straight up at 20 m/s. how high does it go?"),
    ("assistant", "It rises **20.4 m**."),
]


@pytest.mark.asyncio
async def test_a_line_the_turn_read_says_asks_to_see_it_is_read_whatever_its_words() -> None:
    """ "can u show me a picture" names nothing the words know: asked by the turn's read
    (``figure_turn.read_shows_it``), the model still reads what "it" is (QA, 2026-11-22)."""
    model = AsyncMock(return_value=ReferentPick(message=1))
    rows = _rows(_BALL_CHAT)
    with patch.object(referent_read, "pick_referent", model):
        assert await read_referent(Settings(), "can u show me a picture", rows) is None
        model.assert_not_awaited()
        referent = await read_referent(Settings(), "can u show me a picture", rows, asked=True)
    assert referent == Referent(_BALL_CHAT[0][1])


@pytest.mark.asyncio
async def test_a_turn_asked_on_its_words_first_reads_again_when_the_read_asks() -> None:
    """The photo intercept asks on the words alone, before the prep asks with the turn's
    read: its "no read" is no answer the prep's ask is held to."""
    from app.core import readings

    readings.begin_turn()
    model = AsyncMock(return_value=ReferentPick(message=1))
    rows = _rows(_BALL_CHAT)
    line = "can u show me a picture"
    with patch.object(referent_read, "pick_referent", model):
        assert await referent_read.referent_for_turn(Settings(), line, rows) is None
        asked = await referent_read.referent_for_turn(Settings(), line, rows, asked=True)
        again = await referent_read.referent_for_turn(Settings(), line, rows)
    assert asked == again == Referent(_BALL_CHAT[0][1])
    model.assert_awaited_once()


@pytest.mark.asyncio
async def test_a_read_off_or_with_no_earlier_line_asks_no_model() -> None:
    model = AsyncMock(return_value=ReferentPick(message=1))
    with patch.object(referent_read, "pick_referent", model):
        assert await read_referent(Settings(referent_read_enabled=False), "draw it", []) is None
        assert await read_referent(Settings(), "draw it", _rows([("user", "draw it")])) is None
    model.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_slow_model_leaves_the_turn_as_before() -> None:
    """The read's own deadline: past it there is no read, and the turn is read as main did."""
    settings = Settings(referent_read_timeout_seconds=0.01, mock_llm_enabled=False)
    with (
        patch("app.services.quota.global_spend_exceeded", AsyncMock(return_value=False)),
        patch("app.core.redis.get_redis_client", lambda: None),
        patch(
            "app.gateways.structured_completion.complete_structured",
            AsyncMock(side_effect=TimeoutError),
        ),
    ):
        assert await read_referent(settings, "Draw it", _rows(_TRIANGLE_CHAT)) is None


@pytest.mark.asyncio
async def test_past_the_spend_cap_no_model_is_asked() -> None:
    """Past the day's spend cap there is no read: the turn is read as main read it."""
    model = AsyncMock()
    with (
        patch("app.services.quota.global_spend_exceeded", AsyncMock(return_value=True)),
        patch("app.core.redis.get_redis_client", lambda: None),
        patch("app.gateways.structured_completion.complete_structured", model),
    ):
        settings = Settings(mock_llm_enabled=False)
        assert await read_referent(settings, "Draw it", _rows(_TRIANGLE_CHAT)) is None
    model.assert_not_awaited()


async def _continued(
    line: str, pairs: list[tuple[str, str]], pick: ContinuationPick | None
) -> tuple[str | None, AsyncMock]:
    model = AsyncMock(return_value=pick)
    with patch.object(referent_read, "pick_continuation", model):
        return await read_continuation(Settings(), line, _rows(pairs)), model


@pytest.mark.asyncio
async def test_a_short_line_continues_the_problem_the_model_names() -> None:
    pieces = _TRIANGLE_CHAT[2:4]
    assert (await _continued("3", pieces, ContinuationPick(kind="missing_value", message=1)))[
        0
    ] == ("Triangle are with sides 5, 4, 3")
    asked = [("user", "a rectangle 3 by 5"), ("assistant", "The area or the perimeter?")]
    assert (await _continued("the area", asked, ContinuationPick(kind="quantity", message=1)))[
        0
    ] == ("a rectangle 3 by 5. the area")
    # A quiz answer, none named, or no read: the turn is read as main read it.
    quiz = ContinuationPick(kind="answer", message=1)
    assert (await _continued("the area", asked, quiz))[0] is None
    assert (await _continued("the area", asked, ContinuationPick(kind="quantity")))[0] is None
    assert (await _continued("the area", asked, None))[0] is None


@pytest.mark.parametrize(
    "pairs",
    [
        # In a lesson the line answers its practice question: no read.
        [
            ("user", "teach me triangles"),
            ("assistant", "## Lesson 1: Triangles\n\nWhich side is longest?"),
        ],
        # No reply before it.
        [("user", "a rectangle 3 by 5")],
    ],
)
@pytest.mark.asyncio
async def test_no_read_in_a_lesson_or_with_no_reply_before(pairs: list[tuple[str, str]]) -> None:
    pick = ContinuationPick(kind="quantity", message=1)
    continued, model = await _continued("the hypotenuse", pairs, pick)
    assert continued is None
    model.assert_not_awaited()


@pytest.mark.parametrize(
    ("referent", "lines"),
    [
        # The model's pick alone is read.
        (Referent("y = x^2 - 4"), ["y = x^2 - 4"]),
        # None named, or no read: every earlier line, as main reads them (a re-review,
        # 2026-11-10: "graph it" to "Want me to graph it?" drew nothing).
        (Referent(None), ["y = x^2 - 4", "thanks"]),
        (None, ["y = x^2 - 4", "thanks"]),
    ],
)
def test_a_read_that_names_none_clears_no_earlier_line(
    referent: Referent | None, lines: list[str]
) -> None:
    from app.modules.chat.turn_prep.augment import _prior_user_lines
    from app.modules.chat.turn_prep.request import TurnRequest

    prompt = [
        {"role": "user", "content": "y = x^2 - 4"},
        {"role": "assistant", "content": "A parabola. Want me to graph it?"},
        {"role": "user", "content": "thanks"},
        {"role": "assistant", "content": "Sure."},
        {"role": "user", "content": "graph it"},
    ]
    request = TurnRequest(
        user_id=uuid4(),
        chat_id=uuid4(),
        content="graph it",
        model="free-chat",
        client_timezone=None,
        client_location=None,
        client_latitude=None,
        client_longitude=None,
    )
    assert _prior_user_lines(request, prompt, referent) == lines


@pytest.mark.parametrize(
    ("line", "small_talk", "waits"),
    [
        ("can u show me a picture", False, True),
        # A question a subject reads alone, and small talk, never wait for the read (review).
        ("solve 2x + 5 = 17", False, False),
        ("thanks!", True, False),
        # The words ask already: the referent read runs on them.
        ("draw it", False, False),
    ],
)
@pytest.mark.asyncio
async def test_only_a_line_with_no_problem_of_its_own_waits_for_the_read(
    line: str, small_talk: bool, waits: bool
) -> None:
    from uuid import uuid4

    from app.modules.chat.turn_prep import augment
    from app.modules.chat.turn_prep.request import TurnRequest

    request = TurnRequest(
        user_id=uuid4(),
        chat_id=uuid4(),
        content=line,
        model="free-chat",
        client_timezone=None,
        client_location=None,
        client_latitude=None,
        client_longitude=None,
    )
    asked = AsyncMock(return_value=True)
    with patch.object(augment, "read_shows_it", asked):
        said = await augment._asks_to_see_by_read(
            request, Settings(), _rows(_BALL_CHAT), small_talk=small_talk
        )
    assert said is waits and asked.await_count == int(waits)
