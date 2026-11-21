"""A maths question that asks to see nothing still gets the figure that helps teach it.

The owner (2026-11-15): "we don't have to ask it openly to draw, but it must be able to draw
to teach." The figure read is told the user did not ask and to draw only a figure a student
follows the question better with; every number is held to the question as before.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.modules.math.figure import read
from app.modules.math.figure.request import FigureRequest

_TRIANGLE = "Find the area of a right triangle with legs 9 cm and 12 cm."


def _settings(**overrides: Any) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


def _calls() -> Any:
    return (
        patch("app.core.redis.get_redis_client", MagicMock()),
        patch("app.services.quota.global_spend_exceeded", AsyncMock(return_value=False)),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("asked", [True, False])
async def test_the_read_is_told_whether_the_user_asked(asked: bool) -> None:
    redis, spend = _calls()
    reading = FigureRequest(kind="none")
    with (
        redis,
        spend,
        patch(
            "app.gateways.structured_completion.complete_structured",
            AsyncMock(return_value=reading),
        ) as call,
    ):
        assert await read.read_figure(_settings(), _TRIANGLE, [], asked=asked) == reading
    assert call.await_args is not None
    system = call.await_args.kwargs["messages"][0]["content"]
    assert system == (read._ASKED if asked else read._TEACH) + read._BODY + read._COORDINATES
    # The rules that hold every number to the question are the same either way.
    assert system.endswith(read._BODY + read._COORDINATES)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "settings"),
    [
        ("Just the answer: area of a right triangle with legs 9 and 12?", _settings()),
        (_TRIANGLE, _settings(teaching_figures_enabled=False)),
    ],
    ids=["answer-only", "switched-off"],
)
async def test_no_unasked_figure_for_only_the_answer_or_with_the_switch_off(
    question: str, settings: Settings
) -> None:
    with patch.object(read, "read_figure", AsyncMock()) as reading:
        assert await read.draw_figure(question, [], settings, asked=False) is None
    reading.assert_not_awaited()


@pytest.mark.asyncio
async def test_an_unasked_figure_is_built_and_checked_like_an_asked_one() -> None:
    reading = FigureRequest.model_validate(
        {
            "kind": "polygon",
            "shape": "right_triangle",
            "unit": "cm",
            "measures": [{"what": "leg", "value": 9}, {"what": "leg", "value": 12}],
        }
    )
    with patch.object(read, "read_figure", AsyncMock(return_value=reading)) as reading_call:
        fence = await read.draw_figure(_TRIANGLE, [], _settings(), asked=False)
    assert fence is not None and fence.startswith("```geometry")
    assert reading_call.await_args is not None
    assert reading_call.await_args.kwargs == {"asked": False}


@pytest.mark.asyncio
async def test_an_unasked_figure_with_a_number_the_question_never_wrote_is_not_drawn() -> None:
    reading = FigureRequest.model_validate(
        {
            "kind": "polygon",
            "shape": "right_triangle",
            "measures": [{"what": "leg", "value": 9}, {"what": "leg", "value": 13}],
        }
    )
    with patch.object(read, "read_figure", AsyncMock(return_value=reading)):
        assert await read.draw_figure(_TRIANGLE, [], _settings(), asked=False) is None
