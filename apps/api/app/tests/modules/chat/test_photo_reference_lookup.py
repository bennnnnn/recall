"""Photo lookups that name someone earlier in the chat: "show me her image"."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.modules.chat.turn_outcome import TurnOutcome
from app.modules.images.lookup_intent import extract_image_lookup_query, is_reference_subject
from app.tests.modules.chat.chat_test_support import turn_deps


def _awaited(mock: AsyncMock) -> Any:
    """The last await of *mock*; fails the test when it was never awaited."""
    assert mock.await_args is not None
    return mock.await_args


_CALMENT_ROWS = [
    SimpleNamespace(id=uuid4(), role="user", content="Has anyone ever lived for 123 years?"),
    SimpleNamespace(
        id=uuid4(),
        role="assistant",
        content="No verified human has; the longest is Jeanne Calment, 122 years.",
        model="free-chat",
    ),
    SimpleNamespace(id=uuid4(), role="user", content="Where is she from"),
    SimpleNamespace(
        id=uuid4(),
        role="assistant",
        content="She was French, born in Arles, France.",
        model="free-chat",
    ),
]


@pytest.mark.parametrize(
    "text, subject",
    [
        ("Show me her image", "her"),
        ("show me a photo of her", "her"),
        ("can you show me her picture", "her"),
        ("show me his photo", "his"),
        ("what does she look like", "she"),
        ("show me what she looks like", "she"),
        ("please show me an ear", "ear"),
        ("send me a photo of the eiffel tower", "eiffel tower"),
        ("I'd like to see the Taj Mahal", "Taj Mahal"),
    ],
)
def test_lookup_reads_pronouns_and_polite_requests(text: str, subject: str) -> None:
    assert extract_image_lookup_query(text) == subject


@pytest.mark.parametrize(
    "text",
    ["show me my todos", "can you show me my todos", "find me a restaurant", "send me the notes"],
)
def test_lookup_leaves_app_content_alone(text: str) -> None:
    assert extract_image_lookup_query(text) is None


@pytest.mark.parametrize(
    "subject, expected",
    [
        ("her", True),
        ("she", True),
        ("it at night", True),
        ("another one", True),
        ("Jeanne Calment", False),
        ("ear", False),
        ("Eiffel Tower", False),
    ],
)
def test_is_reference_subject(subject: str, expected: bool) -> None:
    assert is_reference_subject(subject) is expected


def _found(asst_id) -> AsyncMock:
    asst_msg = MagicMock()
    asst_msg.id = asst_id
    asst_msg.content = "[Image: /attachments/x/file]"
    asst_msg.model = "image-search-model"
    return AsyncMock(return_value=(MagicMock(), asst_msg))


@pytest.mark.asyncio
async def test_show_me_her_image_searches_the_person_from_the_chat() -> None:
    """The screenshot: "Show me her image" after a chat about Jeanne Calment."""
    from app.modules.chat.turn_intercepts import try_image_lookup_for_turn

    user = MagicMock()
    user.id = uuid4()
    search_and_attach = _found(uuid4())
    resolve = AsyncMock(return_value="Jeanne Calment")

    deps = turn_deps(
        image_search={"search_and_attach_for_chat": search_and_attach},
        references={"resolve_reference": resolve},
    )
    handled = await try_image_lookup_for_turn(
        deps,
        Settings(image_search_enabled=True),
        user=user,
        chat_id=uuid4(),
        content="Show me her image",
        outcome=TurnOutcome(),
        create_user_message=True,
        recent_messages=list(_CALMENT_ROWS),
    )

    assert handled is True
    assert _awaited(search_and_attach).kwargs["query"] == "Jeanne Calment"
    kwargs = _awaited(resolve).kwargs
    assert kwargs["kind"] == "photo"
    assert kwargs["request"] == "Show me her image"
    assert ("user", "Where is she from") in kwargs["turns"]


@pytest.mark.asyncio
async def test_unclear_reference_falls_through_to_the_model() -> None:
    from app.modules.chat.turn_intercepts import try_image_lookup_for_turn

    user = MagicMock()
    user.id = uuid4()
    search_and_attach = _found(uuid4())

    deps = turn_deps(
        image_search={"search_and_attach_for_chat": search_and_attach},
        references={"resolve_reference": AsyncMock(return_value=None)},
    )
    handled = await try_image_lookup_for_turn(
        deps,
        Settings(image_search_enabled=True),
        user=user,
        chat_id=uuid4(),
        content="show me her image",
        outcome=TurnOutcome(),
        create_user_message=True,
        recent_messages=[],
    )

    assert handled is False
    search_and_attach.assert_not_awaited()


@pytest.mark.asyncio
async def test_after_a_generated_picture_it_is_left_to_the_editor() -> None:
    """ "show it at night" after a generated cat edits the cat; no stock photo of "it"."""
    from app.modules.chat.turn_intercepts import try_image_lookup_for_turn

    user = MagicMock()
    user.id = uuid4()
    rows = [
        SimpleNamespace(id=uuid4(), role="user", content="Generate image: black cat"),
        SimpleNamespace(
            id=uuid4(),
            role="assistant",
            content="[Image: /attachments/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/file]",
            model="image-gen-model",
        ),
    ]
    search_and_attach = _found(uuid4())
    resolve = AsyncMock()

    deps = turn_deps(
        image_search={"search_and_attach_for_chat": search_and_attach},
        references={"resolve_reference": resolve},
    )
    handled = await try_image_lookup_for_turn(
        deps,
        Settings(image_search_enabled=True),
        user=user,
        chat_id=uuid4(),
        content="Show it at night",
        outcome=TurnOutcome(),
        create_user_message=True,
        recent_messages=rows,
    )

    assert handled is False
    resolve.assert_not_awaited()
    search_and_attach.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_named_subject_needs_no_resolver() -> None:
    from app.modules.chat.turn_intercepts import try_image_lookup_for_turn

    user = MagicMock()
    user.id = uuid4()
    search_and_attach = _found(uuid4())
    resolve = AsyncMock()

    deps = turn_deps(
        image_search={"search_and_attach_for_chat": search_and_attach},
        references={"resolve_reference": resolve},
    )
    handled = await try_image_lookup_for_turn(
        deps,
        Settings(image_search_enabled=True),
        user=user,
        chat_id=uuid4(),
        content="can you show me a picture of Jeanne Calment",
        outcome=TurnOutcome(),
        create_user_message=True,
    )

    assert handled is True
    assert _awaited(search_and_attach).kwargs["query"] == "Jeanne Calment"
    resolve.assert_not_awaited()


@pytest.mark.asyncio
async def test_regenerating_a_reference_lookup_reads_history_without_the_old_photo() -> None:
    from app.modules.chat.turn_intercepts import try_image_lookup_for_turn

    user = MagicMock()
    user.id = uuid4()
    old_photo = SimpleNamespace(
        id=uuid4(), role="assistant", content="[Image: /a/file]", model="image-search-model"
    )
    rows = [*_CALMENT_ROWS, SimpleNamespace(id=uuid4(), role="user", content="Show me her image")]
    rows.append(old_photo)
    list_recent = AsyncMock(return_value=rows)
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    resolve = AsyncMock(return_value="Jeanne Calment")
    search_and_attach = _found(uuid4())

    deps = turn_deps(
        session_factory=MagicMock(return_value=session),
        messages={"list_recent": list_recent, "get_by_id": AsyncMock(return_value=None)},
        references={"resolve_reference": resolve},
        image_search={"search_and_attach_for_chat": search_and_attach},
    )
    handled = await try_image_lookup_for_turn(
        deps,
        Settings(image_search_enabled=True),
        user=user,
        chat_id=uuid4(),
        content="Show me her image",
        outcome=TurnOutcome(),
        create_user_message=False,
        replace_assistant_id=old_photo.id,
    )

    assert handled is True
    turns = _awaited(resolve).kwargs["turns"]
    assert ("assistant", "[Image: /a/file]") not in turns
    assert _awaited(search_and_attach).kwargs["query"] == "Jeanne Calment"
