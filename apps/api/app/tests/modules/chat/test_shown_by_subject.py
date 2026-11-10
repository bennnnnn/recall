"""A photo or picture asked of "it", when a model read "it" as a curve, a shape or a scene.

Live (2026-11-09): "show it" after sin(x) searched photos for "it". The turn's read
(``chat.referent_read``) names the earlier message; when its subject draws it, no photo is
searched and no picture generated. Everything else keeps main's context: the photo resolver
reads the whole chat, and a picture of "it" takes the subject the chat last asked to draw.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.modules.chat import referent_read
from app.modules.chat.referent_read import ReferentPick
from app.modules.chat.turn_outcome import TurnOutcome
from app.modules.chat.turn_prep.followups import SubjectFollowup, resolve_subject_followup
from app.modules.images.gen_intent_thread import extract_image_gen_prompt_from_thread
from app.modules.images.intent import composer_image_intent
from app.tests.fakes import make_user
from app.tests.modules.chat.chat_test_support import turn_deps


def _rows(*pairs: tuple[str, str]) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(id=uuid4(), role=role, content=content, model="free-chat")
        for user, reply in pairs
        for role, content in (("user", user), ("assistant", reply))
    ]


_CURVE = ("sin(x)", "The sine function.")
_SHAPE = ("area of a triangle with sides 5, 4 and 3", "6 square units.")
_PROJECTILE = ("A ball is thrown at 20 m/s at 30 degrees. How far does it go?", "35.3 m.")
_COLOSSEUM = (
    ("Tell me about the Colosseum", "An amphitheatre in Rome."),
    ("Who built it?", "Vespasian."),
)


def _found() -> AsyncMock:
    reply = MagicMock()
    reply.id, reply.content, reply.model = uuid4(), "[Image: /attachments/x/file]", "image-search"
    return AsyncMock(return_value=(MagicMock(), reply))


async def _new_turn(
    rows: list[SimpleNamespace], content: str, pick: ReferentPick | None, resolved: str | None
) -> tuple[bool, AsyncMock, AsyncMock, set[str]]:
    """The turn's intercept, with the model's read of "it" (None: no read)."""
    from app.modules.chat.turn_intercepts import intercept_new_turn

    search, resolve = _found(), AsyncMock(return_value=resolved)
    deps = turn_deps(
        image_search={"search_and_attach_for_chat": search},
        references={"resolve_reference": resolve},
    )
    misses: set[str] = set()
    with patch.object(referent_read, "pick_referent", AsyncMock(return_value=pick)):
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


@pytest.mark.parametrize("pair", [_CURVE, _SHAPE, _PROJECTILE])
@pytest.mark.parametrize("content", ["show it", "show me that", "can I see it?", "a picture of it"])
@pytest.mark.asyncio
async def test_it_read_as_a_curve_a_shape_or_a_scene_is_shown_not_searched(
    pair: tuple[str, str], content: str, thread_sympy_executor: None
) -> None:
    handled, resolve, search, misses = await _new_turn(
        _rows(pair), content, ReferentPick(message=1), "sine wave"
    )
    assert handled is False
    resolve.assert_not_awaited()
    search.assert_not_awaited()
    assert "photo" in misses


@pytest.mark.parametrize("pick", [None, ReferentPick(message=None), ReferentPick(message=2)])
@pytest.mark.asyncio
async def test_it_read_as_a_thing_is_a_photo_read_from_the_whole_chat(
    pick: ReferentPick | None, thread_sympy_executor: None
) -> None:
    """The resolver reads the chat as main did: "it" in "Who built it?" is the Colosseum."""
    handled, resolve, search, _misses = await _new_turn(
        _rows(*_COLOSSEUM), "show me a picture of it", pick, "Colosseum"
    )
    assert handled is True
    assert resolve.await_args is not None
    turns = resolve.await_args.kwargs["turns"]
    assert ("user", "Tell me about the Colosseum") in turns
    assert search.await_args is not None


@pytest.mark.asyncio
async def test_a_named_photo_after_maths_is_still_looked_up(thread_sympy_executor: None) -> None:
    handled, resolve, search, _misses = await _new_turn(
        _rows(_CURVE), "show me a picture of the Eiffel Tower", ReferentPick(message=1), None
    )
    assert handled is True
    resolve.assert_not_awaited()
    assert search.await_args is not None
    assert "Eiffel Tower" in search.await_args.kwargs["query"]


def test_a_picture_of_it_keeps_the_subject_asked_for_earlier() -> None:
    """A local review (2026-11-10): narrowed to the newest line, "generate an image of it"
    after "lol so cool" sent the prompt "it"."""
    earlier = ["Generate an image of a red sports car", "lol so cool"]
    assert extract_image_gen_prompt_from_thread("generate an image of it", earlier) == (
        "a red sports car"
    )


@pytest.mark.parametrize("content", ["show it", "a picture of it", "draw it"])
def test_the_composer_leaves_a_picture_of_it_to_the_chat_turn(content: str) -> None:
    """What "it" is, the chat turn's read says; the composer never draws it first."""
    rows = _rows(_CURVE)
    intent = composer_image_intent(content, rows)
    assert intent.lookup_query is None and intent.request is None
    assert composer_image_intent("draw a red sports car", rows).request is not None


def _history(*pairs: tuple[str, str]) -> list[dict[str, str]]:
    return [{"role": row.role, "content": row.content} for row in _rows(*pairs)]


def test_show_it_is_what_the_read_named() -> None:
    history = _history(_CURVE, ("what is the domain?", "All real numbers."))
    assert resolve_subject_followup("show it", history, "sin(x)") == SubjectFollowup(
        math="graph sin(x)"
    )
    assert resolve_subject_followup("draw it", _history(_PROJECTILE), _PROJECTILE[0]) == (
        SubjectFollowup(physics=_PROJECTILE[0])
    )


@pytest.mark.parametrize(
    "referent", [None, "", "What's the capital of France?", "Solve 2x + 3 = 7"]
)
def test_show_me_that_after_a_solve_is_its_working_unless_read_as_a_picture(
    referent: str | None,
) -> None:
    """A local review (2026-11-10): "Show me that" after a solve was graphed; main gave the
    working. Whatever the read named, even the equation itself, it is the working."""
    history = _history(("Solve 2x + 3 = 7", "x = 2"))
    assert resolve_subject_followup("Show me that", history, referent or None) == (
        SubjectFollowup(math="Solve 2x + 3 = 7")
    )


def test_a_free_users_picture_of_it_keeps_the_composers_upgrade_prompt() -> None:
    """A user who cannot generate gets main's composer picture, whose generate answers with
    the upgrade prompt; only a user who can is sent to the chat turn's read."""
    rows = _rows(("Generate an image of a red sports car", "Here it is."))
    assert composer_image_intent("a picture of it", rows, can_generate=False).request is not None
    assert composer_image_intent("a picture of it", rows, can_generate=True).request is None
