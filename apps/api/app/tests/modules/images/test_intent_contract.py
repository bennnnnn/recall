"""The contract for ``POST /images/intent``: what the composer does with a send.

The phone reads no image intent; before a send that might be a picture it asks
this endpoint. The words find what the send could ask of images (``images.intent``),
and the turn's read, the model that reads every chat turn, says whether it asks for a
photo, a picture or neither (``chat.picture_ask``). ``docs/fixtures/image_intent_cases.json``
is the server's case list: ``phrases``, ``threads`` and ``revision_contexts`` pin what the
words find, and ``composer`` pins the verdict the endpoint returns once the read answers
(each case's ``read``).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.deps import get_current_user, get_settings_dep
from app.main import create_app
from app.models.orm import User
from app.modules.images.gen_intent import extract_image_gen_prompt
from app.modules.images.gen_intent_thread import image_gen_revision_context
from app.modules.images.intent import image_gen_request
from app.modules.images.lookup_intent import extract_image_lookup_query

FIXTURE = Path(__file__).resolve().parents[6] / "docs" / "fixtures" / "image_intent_cases.json"
CASES: dict[str, Any] = json.loads(FIXTURE.read_text())
PREVIOUS_SUBJECT: str = CASES["revise_previous_subject"]
THREADS: dict[str, list[dict[str, Any]]] = CASES["composer_threads"]
AFTER_PICTURE = THREADS["after_picture"]


def _id(case: dict[str, Any]) -> str:
    return repr(case["text"])[:60]


def _rows(messages: list[dict[str, Any]]) -> list[SimpleNamespace]:
    return [SimpleNamespace(**{"id": uuid4(), "model": None, **message}) for message in messages]


def _user() -> User:
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.plan = "free"
    return user


@contextmanager
def _client(
    user: User,
    *,
    messages: list[dict[str, Any]] | None = None,
    owned: bool = True,
    settings: Settings | None = None,
    read: str | None = "image",
) -> Iterator[tuple[TestClient, AsyncMock, AsyncMock]]:
    """A signed-in client whose chat holds ``messages``; ``owned=False`` is someone else's."""
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_settings_dep] = lambda: settings or Settings()
    get_chat = AsyncMock(return_value=MagicMock() if owned else None)
    list_recent = AsyncMock(return_value=_rows(messages or []))
    with (
        patch("app.modules.images.intent.chat_history.get_chat", get_chat),
        patch("app.modules.images.intent.chat_history.recent_messages", list_recent),
        patch(_LABELS, AsyncMock(return_value={})),
        patch(_READ, AsyncMock(return_value=read)),
    ):
        yield TestClient(app), get_chat, list_recent


# The turn's read, as the endpoint asks it; and the pictures' labels, read from the database.
_READ = "app.modules.chat.picture_ask.read_picture_ask"
_LABELS = "app.modules.chat.picture_ask.picture_labels"


def _verdict(
    text: str,
    messages: list[dict[str, Any]] | None = None,
    *,
    attached: bool = False,
    settings: Settings | None = None,
    read: str | None = "image",
) -> dict[str, Any]:
    with _client(_user(), messages=messages, settings=settings, read=read) as (
        client,
        _get_chat,
        _recent,
    ):
        response = client.post(
            "/images/intent",
            headers={"Authorization": "Bearer tok"},
            json={"text": text, "chat_id": str(uuid4()), "image_attached": attached},
        )
    assert response.status_code == 200, response.text
    return response.json()


# ── The word rules ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("case", CASES["phrases"], ids=_id)
def test_intent_contract_phrase(case: dict[str, Any]) -> None:
    text = case["text"]
    assert extract_image_gen_prompt(text) == case["generate"]
    assert extract_image_lookup_query(text) == case["lookup"]
    # After a generated picture, the change it would make to it: the read says whether it does.
    after = _rows(
        [{"role": "user", "content": f"Generate image: {PREVIOUS_SUBJECT}"}, AFTER_PICTURE[1]]
    )
    request = image_gen_request(text, after)
    assert (request.prompt if request is not None and request.revision else None) == case["revise"]


@pytest.mark.parametrize("case", CASES["threads"], ids=_id)
def test_intent_contract_thread(case: dict[str, Any]) -> None:
    rows = _rows([{"role": "user", "content": prior} for prior in case["priors"]])
    request = image_gen_request(case["text"], rows)
    assert (request.prompt if request else None) == case["generate"]


@pytest.mark.parametrize("case", CASES["revision_contexts"])
def test_intent_contract_revision_context(case: dict[str, Any]) -> None:
    assert image_gen_revision_context(case["messages"]) == (
        case["last_assistant_is_image_only"],
        case["previous_subject"],
    )


# ── The endpoint ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("case", CASES["composer"], ids=_id)
def test_intent_contract_composer(case: dict[str, Any]) -> None:
    read = None if case.get("read") in (None, "none") else case["read"]
    verdict = _verdict(
        case["text"], THREADS[case["thread"]], attached=case.get("attached", False), read=read
    )
    assert verdict == {
        "subject": case.get("subject"),
        "lookup_query": case.get("lookup"),
        "generate_prompt": case.get("generate"),
        "revision": case.get("revision", False),
        "reference_attachment_ids": case.get("reference", []),
    }


def test_intent_requires_sign_in() -> None:
    client = TestClient(create_app())
    assert client.post("/images/intent", json={"text": "draw me a cat"}).status_code == 401


@pytest.mark.parametrize(
    "text, subject, prompt",
    [
        ("draw ethanol", "chemistry", None),
        ("A lens has focal length 15 cm. Where's the image?", "physics", None),
        ("draw me a cat", None, "cat"),
        ("Generate an image of a lighthouse", None, "a lighthouse"),
    ],
)
def test_intent_answers_a_phone_that_sends_only_text(
    text: str, subject: str | None, prompt: str | None
) -> None:
    """Phones before ES-05 send ``{text}`` and read ``subject``; that still works, unread."""
    with _client(_user()) as (client, get_chat, list_recent):
        response = client.post(
            "/images/intent", headers={"Authorization": "Bearer tok"}, json={"text": text}
        )
    assert response.status_code == 200
    assert response.json()["subject"] == subject
    assert response.json()["generate_prompt"] == prompt
    get_chat.assert_not_awaited()
    list_recent.assert_not_awaited()


def test_intent_leaves_a_structure_to_the_picture_when_chemistry_is_off() -> None:
    verdict = _verdict("draw ethanol", settings=Settings(chemistry_enabled=False))
    assert verdict["subject"] is None
    assert verdict["generate_prompt"] == "ethanol"


def test_intent_looks_no_photo_up_when_image_search_is_off() -> None:
    verdict = _verdict("show me an ear", settings=Settings(image_search_enabled=False))
    assert verdict["lookup_query"] is None
    assert verdict["generate_prompt"] is None


@pytest.mark.parametrize("whose", ["someone else's", "nobody's"])
def test_intent_reads_no_chat_but_the_users_own(whose: str) -> None:
    """A chat that is someone else's, or nobody's, is not found, and none of its turns are read."""
    user, owner = _user(), _user()
    owned_chat = uuid4()

    async def get_by_id(_session: Any, chat_id: UUID, user_id: UUID) -> MagicMock | None:
        return MagicMock() if (chat_id, user_id) == (owned_chat, owner.id) else None

    chat_id = owned_chat if whose == "someone else's" else uuid4()
    with _client(user, messages=AFTER_PICTURE) as (client, get_chat, list_recent):
        get_chat.side_effect = get_by_id
        response = client.post(
            "/images/intent",
            headers={"Authorization": "Bearer tok"},
            json={"text": "make it blue", "chat_id": str(chat_id)},
        )
    assert response.status_code == 404
    assert response.json() == {"detail": {"code": "not_found", "message": "Chat not found"}}
    get_chat.assert_awaited_once()
    list_recent.assert_not_awaited()


def test_intent_reads_the_recent_window_of_the_users_chat() -> None:
    user = _user()
    chat_id = uuid4()
    with _client(user, messages=AFTER_PICTURE) as (client, get_chat, list_recent):
        response = client.post(
            "/images/intent",
            headers={"Authorization": "Bearer tok"},
            json={"text": "make it blue", "chat_id": str(chat_id)},
        )
    assert response.status_code == 200
    chat_call, recent_call = get_chat.await_args, list_recent.await_args
    assert chat_call is not None and recent_call is not None
    assert chat_call.args[1:] == (chat_id, user.id)
    assert recent_call.args[1] == chat_id
    assert recent_call.kwargs == {"limit": Settings().recent_message_window}
    assert response.json()["reference_attachment_ids"] == [
        str(UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"))
    ]


def test_intent_reads_a_draft_chat_as_an_empty_thread() -> None:
    """A draft chat has no id yet: "make it blue" edits nothing, "Image" names nothing."""
    with _client(_user(), messages=AFTER_PICTURE) as (client, get_chat, list_recent):
        for text in ("make it blue", "Image"):
            response = client.post(
                "/images/intent", headers={"Authorization": "Bearer tok"}, json={"text": text}
            )
            assert response.status_code == 200
            assert response.json()["generate_prompt"] is None
    get_chat.assert_not_awaited()
    list_recent.assert_not_awaited()


def test_intent_looks_a_photo_up_before_it_edits_the_last_picture() -> None:
    """After a picture, "send me a photo of X" still wants a real photo, not an edit: the
    read says so, and the lookup words say what to search for."""
    text = "send me a photo of the eiffel tower"
    rows = _rows(AFTER_PICTURE)
    edit = image_gen_request(text, rows)
    assert edit is not None and edit.revision  # the edit reading alone would draw it
    verdict = _verdict(text, AFTER_PICTURE, read="photo")
    assert verdict["lookup_query"] == "eiffel tower"
    assert verdict["generate_prompt"] is None


# The owner's chat (2026-11-22): after one painted picture, each of these got another.
OWNER_LINES = [
    "No you displayed an image",
    "You keep generating an image",
    "What?🤔 did i ask about an image?",
    "Man this is so bad",
]


@pytest.mark.parametrize("text", OWNER_LINES)
@pytest.mark.parametrize("read", ["none", None])
def test_intent_paints_nothing_the_read_does_not_ask_for(text: str, read: str | None) -> None:
    """Words that could change the last picture are asked of the read; a read that says
    none, or gives no answer in time, draws nothing."""
    with _client(_user(), messages=AFTER_PICTURE, read=read) as (client, _get_chat, _recent):
        response = client.post(
            "/images/intent",
            headers={"Authorization": "Bearer tok"},
            json={"text": text, "chat_id": str(uuid4())},
        )
    assert response.status_code == 200
    assert response.json()["generate_prompt"] is None
    assert response.json()["lookup_query"] is None


def test_intent_draws_only_when_the_read_answers() -> None:
    """ "draw me a cat" with the read late is a chat send: a missed picture is better than
    one nobody asked for."""
    assert _verdict("draw me a cat", read=None)["generate_prompt"] is None
    assert _verdict("draw me a cat", read="image")["generate_prompt"] == "cat"


def test_intent_asks_the_read_only_about_a_send_that_could_be_a_picture() -> None:
    """A plain message never waits for the read; one that could ask for a picture is read
    with the chat's turns. After a picture any short line could change it, so it is read."""
    with _client(_user(), messages=AFTER_PICTURE) as (client, _get_chat, _recent):
        with patch(_READ, AsyncMock(return_value=None)) as read:
            client.post(
                "/images/intent",
                headers={"Authorization": "Bearer tok"},
                json={"text": "what is the capital of France?"},
            )
            read.assert_not_awaited()
            client.post(
                "/images/intent",
                headers={"Authorization": "Bearer tok"},
                json={"text": "now at night", "chat_id": str(uuid4())},
            )
    read.assert_awaited_once()
    assert read.await_args is not None
    assert read.await_args.args[1] == "now at night"
    assert [row.content for row in read.await_args.args[2]] == [
        row["content"] for row in AFTER_PICTURE
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {"text": ""},
        {"text": "x" * 2001},
        {"text": "draw a cat", "chat_id": "not-a-uuid"},
    ],
)
def test_intent_refuses_a_malformed_request(payload: dict[str, Any]) -> None:
    with _client(_user()) as (client, _get_chat, _recent):
        response = client.post(
            "/images/intent", headers={"Authorization": "Bearer tok"}, json=payload
        )
    assert response.status_code == 422


# ── Limits ─────────────────────────────────────────────────────────────────


def test_intent_is_limited_per_user_and_reads_nothing_past_the_limit() -> None:
    """Each ask reads the text in the SymPy pool chat turns share; only the global REST
    limit (240 a minute) bounded it."""
    from app.modules.images.api import INTENT_ASKS_PER_MINUTE

    nothing = SimpleNamespace(subject=None, lookup_query=None, request=None)
    with (
        _client(_user()) as (client, _get_chat, _recent),
        patch(
            "app.modules.images.intent.composer_candidates", MagicMock(return_value=nothing)
        ) as read,
    ):
        responses = [
            client.post(
                "/images/intent", headers={"Authorization": "Bearer t"}, json={"text": "a cat"}
            )
            for _ in range(INTENT_ASKS_PER_MINUTE + 1)
        ]
    assert [r.status_code for r in responses] == [200] * INTENT_ASKS_PER_MINUTE + [429]
    assert responses[-1].json()["detail"]["code"] == "rate_limited"
    assert responses[-1].headers["retry-after"] == "60"
    assert read.call_count == INTENT_ASKS_PER_MINUTE
    # Another user keeps their own budget.
    assert _verdict("draw a cat")["generate_prompt"] == "cat"


def test_intent_reads_in_the_pool_under_the_users_id() -> None:
    """The pool runs one job per user id at a time (``core/sympy_executor``): without the
    id, one user's asks could hold every slot chat turns need."""
    from app.core.log_context import current_log_ids

    user = _user()
    seen: list[str | None] = []

    async def read_subject(*_args: Any, **_kwargs: Any) -> None:
        seen.append(current_log_ids().get("user_id"))

    with (
        _client(user) as (client, _get_chat, _recent),
        patch("app.services.subjects.dispatch.read_subject", read_subject),
    ):
        response = client.post(
            "/images/intent", headers={"Authorization": "Bearer t"}, json={"text": "draw a cat"}
        )
    assert response.status_code == 200
    assert seen == [str(user.id)]
