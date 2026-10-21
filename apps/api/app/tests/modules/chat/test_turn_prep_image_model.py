"""A turn uses a photo model only when it shows the model an image (R4.4).

A picture Recall generated earlier no longer moves later turns to the photo
model; an explicit pick that can read images keeps a photo turn; a re-sent
photo gets backups that can read it.
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models import model_catalog
from app.modules.chat.turn_prep.attachments import _AttachmentProcessResult
from app.modules.chat.turn_prep.context import await_user_message_persist
from app.modules.chat.turn_prep.persist import UserTurn, turn_model
from app.modules.chat.turn_prep.vision import inject_turn_images
from app.tests.modules.chat.chat_test_support import prompt_bundle

_SETTINGS = Settings(attachments_enabled=True, mock_llm_enabled=True, openrouter_api_key="")


def _pro_user() -> Any:
    return SimpleNamespace(id=uuid4(), plan="pro", enabled_models=None)


def _stand_in(**fields: object) -> Any:
    return SimpleNamespace(**fields)


def _generated_cat() -> list[SimpleNamespace]:
    return [
        SimpleNamespace(role="user", content="draw me a cat", model="qwen-3.7-flash"),
        SimpleNamespace(
            role="assistant", content=f"[Image: /attachments/{uuid4()}/file]", model=None
        ),
    ]


def _turn(content: str, *, recent: list[Any], image: bool = False, alias: str | None = None):
    return UserTurn(
        user_id=uuid4(),
        chat_id=uuid4(),
        message_id=uuid4(),
        content=content,
        stored_content=content,
        attachment_ids=None,
        has_image_attachment=image,
        model_alias=alias,
        recent_messages=recent,
        lesson_active=False,
    )


def _attachments(*, image: bool = False) -> _AttachmentProcessResult:
    return _AttachmentProcessResult(
        user=None,
        user_content="",
        content="",
        has_image_attachment=image,
        has_document_attachment=False,
        image_attachments=[],
        image_math_extract=None,
        gateway=None,
        bytes_by_key={},
    )


def test_a_generated_image_earlier_does_not_move_a_hard_question_to_the_photo_model() -> None:
    turn = _turn("prove that √2 is irrational", recent=_generated_cat())
    assert turn_model(turn, _pro_user(), _SETTINGS) == "smart-chat"


@pytest.mark.parametrize(
    "alias, expected",
    [
        (None, "vision-chat"),
        ("auto", "vision-chat"),
        ("gpt-6-luna", "gpt-6-luna"),
        ("free-chat", "free-chat"),
        ("smart-chat", "vision-chat"),
    ],
)
def test_a_photo_sent_now_runs_on_a_model_that_reads_it(alias: str | None, expected: str) -> None:
    turn = _turn("what's in this picture?", recent=[], image=True, alias=alias)
    model = turn_model(turn, _pro_user(), _SETTINGS)
    assert model == expected
    assert model_catalog.reads_images(model)


def test_a_photo_sent_now_with_attachments_off_keeps_the_routed_model() -> None:
    turn = _turn("what's in this picture?", recent=[], image=True)
    off = Settings(attachments_enabled=False, mock_llm_enabled=True, openrouter_api_key="")
    assert turn_model(turn, _pro_user(), off) == "qwen-3.7-flash"


@pytest.mark.asyncio
async def test_a_generated_image_is_not_sent_back_to_the_model() -> None:
    prompt = [
        {"role": "user", "content": "draw me a cat"},
        {"role": "assistant", "content": f"[Image: /attachments/{uuid4()}/file]"},
        {"role": "user", "content": "prove that √2 is irrational"},
    ]
    before = [dict(message) for message in prompt]
    lookup = AsyncMock(return_value=[])
    with patch("app.modules.chat.turn_prep.vision.attachments_service.get_by_ids", lookup):
        resent = await inject_turn_images(
            prompt, _attachments(), caption="prove it", settings=_SETTINGS, user=_pro_user()
        )
    assert resent is False
    lookup.assert_not_awaited()
    assert prompt == before


@pytest.mark.asyncio
async def test_a_resent_photo_moves_the_turn_and_its_backups_to_image_readers() -> None:
    from app.modules.chat.turn_prep import prepare

    user = _pro_user()
    bundle = prompt_bundle(
        prompt_messages=[{"role": "user", "content": "and the colour?"}],
        fallback_models=["glm-5.2"],
    )
    processed = _attachments()
    processed.user = user
    with (
        patch.object(prepare, "_process_attachments", AsyncMock(return_value=processed)),
        patch.object(prepare, "build_stream_prompt_context", AsyncMock(return_value=bundle)),
        patch.object(prepare, "_persist_and_report", AsyncMock(return_value=[])),
        patch.object(prepare, "inject_turn_images", AsyncMock(return_value=True)),
    ):
        ctx = await prepare.prepare_chat_turn(
            user_id=user.id,
            chat_id=uuid4(),
            content="and the colour?",
            model_alias=None,
            settings=_SETTINGS,
            redis=AsyncMock(),
            reserved_tokens=100,
            user=user,
            chat=_stand_in(id=uuid4()),
            turn_mode=_stand_in(lightweight=False, rich_context=True),
            prior_count=2,
            recent_messages=[],
            resolved_model="smart-chat",
            unhealthy=frozenset(),
        )
        await await_user_message_persist(ctx)
    # Auto's hard lane on a photo: the strongest image reader, not the text-only model.
    assert ctx.model == "glm-5.3-flash"
    assert ctx.fallback_models
    assert all(model_catalog.reads_images(alias) for alias in ctx.fallback_models)
