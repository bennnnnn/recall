"""A photo or picture asked of "it" is the chat's latest subject (``turn_reading.latest_subject``).

Live (2026-11-09): "show it" after sin(x) searched photos for "it". A line whose subject is
only a pronoun ("show it", "show me that", "can I see it?", "a picture of it") is shown by
the subject the chat is on: a curve or a shape is maths' graph or figure, a projectile
physics' scene. Anything else is a photo of that subject, never one older.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.modules.chat.turn_outcome import TurnOutcome
from app.modules.images.gen_intent_thread import extract_image_gen_prompt_from_thread
from app.modules.images.intent import composer_image_intent
from app.services.subjects.dispatch import subject_shows_it
from app.tests.fakes import make_user
from app.tests.modules.chat.chat_test_support import turn_deps


def _rows(*pairs: tuple[str, str]) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(id=uuid4(), role=role, content=content, model="free-chat")
        for user, reply in pairs
        for role, content in (("user", user), ("assistant", reply))
    ]


_CURVE = _rows(("sin(x)", "The sine function."))
_EQUATION = _rows(("solve x^2 - 5x + 6 = 0", "x = 2 or x = 3"))
_SHAPE = _rows(("area of a triangle with sides 5, 4 and 3", "6 square units."))
_PROJECTILE = _rows(("A ball is thrown at 20 m/s at 30 degrees. How far does it go?", "35.3 m."))
_TOWER_AFTER_CURVE = _rows(
    ("sin(x)", "The sine function."), ("How tall is the Eiffel Tower?", "About 330 m.")
)


def _found() -> AsyncMock:
    reply = MagicMock()
    reply.id, reply.content, reply.model = uuid4(), "[Image: /attachments/x/file]", "image-search"
    return AsyncMock(return_value=(MagicMock(), reply))


async def _new_turn(
    rows: list[SimpleNamespace], content: str, resolved: str | None = None
) -> tuple[bool, AsyncMock, AsyncMock, set[str]]:
    from app.modules.chat.turn_intercepts import intercept_new_turn

    search, resolve = _found(), AsyncMock(return_value=resolved)
    deps = turn_deps(
        image_search={"search_and_attach_for_chat": search},
        references={"resolve_reference": resolve},
    )
    misses: set[str] = set()
    handled = await intercept_new_turn(
        deps,
        Settings(image_search_enabled=True, image_generation_enabled=True),
        user=make_user(plan="pro"),
        chat_id=uuid4(),
        content=content,
        outcome=TurnOutcome(),
        recent_messages=list(rows),
        prior_count=len(rows),
        misses=misses,
    )
    return handled, resolve, search, misses


@pytest.mark.parametrize("rows", [_CURVE, _EQUATION, _SHAPE, _PROJECTILE])
@pytest.mark.parametrize("content", ["show it", "show me that", "can I see it?", "a picture of it"])
@pytest.mark.asyncio
async def test_it_after_a_curve_a_shape_or_a_projectile_is_shown_not_searched(
    rows: list[SimpleNamespace], content: str, thread_sympy_executor: None
) -> None:
    handled, resolve, search, misses = await _new_turn(rows, content, resolved="sine wave")
    assert handled is False
    resolve.assert_not_awaited()
    search.assert_not_awaited()
    assert "photo" in misses
    # The composer reads it the same way: no photo lookup, no generated picture.
    assert await subject_shows_it(Settings(), content, rows)
    intent = composer_image_intent(content, rows, subject_shows=True)
    assert intent.lookup_query is None and intent.request is None


@pytest.mark.asyncio
async def test_a_named_photo_after_maths_is_still_looked_up(thread_sympy_executor: None) -> None:
    handled, resolve, search, _misses = await _new_turn(
        _CURVE, "show me a picture of the Eiffel Tower"
    )
    assert handled is True
    resolve.assert_not_awaited()
    assert search.await_args is not None
    assert "Eiffel Tower" in search.await_args.kwargs["query"]


@pytest.mark.asyncio
async def test_it_after_a_thing_is_a_photo_of_the_latest_subject_only(
    thread_sympy_executor: None,
) -> None:
    """The resolver reads the chat from its latest subject on: sin(x) is not "it"."""
    handled, resolve, search, _misses = await _new_turn(
        _TOWER_AFTER_CURVE, "show it", resolved="Eiffel Tower"
    )
    assert handled is True
    assert resolve.await_args is not None
    turns = resolve.await_args.kwargs["turns"]
    assert turns[0] == ("user", "How tall is the Eiffel Tower?")
    assert ("user", "sin(x)") not in turns
    assert search.await_args is not None


def test_a_picture_of_it_is_the_latest_subject_but_that_car_names_its_own() -> None:
    moved_on = ["draw a red car", "What is the capital of France?"]
    assert extract_image_gen_prompt_from_thread("a picture of it", moved_on) == "it"
    assert extract_image_gen_prompt_from_thread("a picture of it", ["draw a red car", "nice"]) == (
        "red car"
    )
    assert extract_image_gen_prompt_from_thread("a picture of that car", moved_on) == "red car"
