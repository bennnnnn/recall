"""Regeneration must retain the saved image bytes, owner scope, and text caption."""

import base64
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.orm import Chat, User
from app.services.chat import stream_entry
from app.services.chat.turn_prep.attachments import vision_reserve_tokens
from app.services.chat.turn_prep.context import (
    ClientGeoContext,
    TurnPromptBundle,
    stream_context_from_bundle,
)
from app.services.chat.turn_prep.regenerate_vision import inject_regenerated_image_content
from app.tests.services.chat_test_support import FakeSessionCM

_MODULE = "app.services.chat.turn_prep.regenerate_vision"
_SETTINGS = Settings(attachments_enabled=True)


def _row(uid, key="image", content_type="image/jpeg"):
    return SimpleNamespace(id=uid, storage_key=key, content_type=content_type)


async def _inject(messages, ids, rows, *, enabled=True, byte_map=None):
    user_id = uuid4()
    lookup = AsyncMock(return_value=rows)
    gateway = SimpleNamespace(
        read_bytes=AsyncMock(side_effect=lambda key: (byte_map or {}).get(key))
    )
    storage = MagicMock(return_value=gateway)
    with (
        patch(f"{_MODULE}.SessionLocal", FakeSessionCM),
        patch(f"{_MODULE}.attachments_repo.get_by_ids", lookup),
        patch(f"{_MODULE}.get_storage_gateway", storage),
    ):
        injected = await inject_regenerated_image_content(
            messages,
            settings=Settings(attachments_enabled=enabled),
            user_id=user_id,
            attachment_ids=ids,
        )
    return injected, lookup, storage, gateway, user_id


@pytest.mark.asyncio
async def test_saved_scanner_image_rehydrates_actual_bytes_and_preserves_safe_caption():
    uid = uuid4()
    caption = f"Solve step by step.\n\n[Image: /attachments/{uid}/file]\n<untrusted>file excerpt</untrusted>"
    messages = [{"role": "system", "content": "policy"}, {"role": "user", "content": caption}]
    result, lookup, _storage, gateway, owner = await _inject(
        messages,
        [uid, uid],
        [_row(uid)],
        byte_map={"image": b"saved-photo-bytes"},
    )
    assert result
    assert lookup.await_args.args[1:] == ([uid], owner)
    gateway.read_bytes.assert_awaited_once_with("image")
    parts = messages[-1]["content"]
    assert parts[0] == {
        "type": "text",
        "text": "Solve step by step.\n\n<untrusted>file excerpt</untrusted>",
    }
    assert parts[1] == {
        "type": "image_url",
        "image_url": {
            "url": "data:image/jpeg;base64," + base64.b64encode(b"saved-photo-bytes").decode()
        },
    }
    assert messages[0] == {"role": "system", "content": "policy"}


@pytest.mark.asyncio
async def test_multiple_current_images_keep_marker_order_despite_unordered_repository_result():
    first, second = uuid4(), uuid4()
    messages = [{"role": "user", "content": "Compare these images."}]
    result, *_ = await _inject(
        messages,
        [first, second],
        [_row(second, "b"), _row(first, "a")],
        byte_map={"a": b"first", "b": b"second"},
    )
    assert result
    urls = [
        part["image_url"]["url"] for part in messages[-1]["content"] if part["type"] == "image_url"
    ]
    assert urls == [
        f"data:image/jpeg;base64,{base64.b64encode(value).decode()}"
        for value in (b"first", b"second")
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["missing_or_unowned", "document", "unreadable"])
async def test_unavailable_current_image_gets_honest_note_without_fabricated_vision(kind):
    uid = uuid4()
    rows = (
        []
        if kind == "missing_or_unowned"
        else [_row(uid, content_type="application/pdf" if kind == "document" else "image/jpeg")]
    )
    messages = [{"role": "user", "content": "Solve this image."}]
    result, _lookup, storage, *_ = await _inject(messages, [uid], rows)
    assert not result
    assert "not available to look at again" in messages[-1]["content"]
    assert "Do not guess" in messages[-1]["content"]
    if kind != "unreadable":
        storage.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_row", [True, False])
async def test_partial_missing_or_unreadable_image_keeps_readable_one_and_reports_loss(missing_row):
    first, second = uuid4(), uuid4()
    rows = [_row(first, "readable")] + ([] if missing_row else [_row(second, "gone")])
    messages = [{"role": "user", "content": "Compare both images."}]
    result, *_ = await _inject(messages, [first, second], rows, byte_map={"readable": b"photo"})
    assert result
    assert sum(part["type"] == "image_url" for part in messages[-1]["content"]) == 1
    assert "not available" in messages[-1]["content"][-1]["text"]


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["disabled", "no_ids", "no_user"])
async def test_inactive_or_absent_current_image_has_no_database_or_storage_work(mode):
    uid = uuid4()
    messages = [{"role": "system" if mode == "no_user" else "user", "content": "text"}]
    result, lookup, storage, *_ = await _inject(
        messages, [] if mode == "no_ids" else [uid], [], enabled=mode != "disabled"
    )
    assert not result
    lookup.assert_not_awaited()
    storage.assert_not_called()
    assert messages[-1]["content"] == "text"


@pytest.mark.asyncio
@pytest.mark.parametrize("with_image", [True, False])
async def test_regenerate_actual_entry_retains_image_routing_reserve_and_backup(with_image):
    owner, chat_id, uid = uuid4(), uuid4(), uuid4()
    user = User(id=owner, email="test@example.com", name="Test")
    chat = Chat(id=chat_id, user_id=owner, project_id=None)
    caption = (
        "Solve the math problem in this image step by step."
        if with_image
        else "Explain the previous result."
    )
    if with_image:
        caption += f"\n\n[Image: /attachments/{uid}/file]"
    last_user = SimpleNamespace(id=uuid4(), content=caption)
    previous = SimpleNamespace(
        id=uuid4(), role="assistant", content="Original successful response", model="free-chat"
    )
    captured = {}
    resource = SimpleNamespace(
        reserve=AsyncMock(), reserved_tokens=100, lock_key="lock", lock_token="token"
    )

    @asynccontextmanager
    async def resources(*_args, **_kwargs):
        yield resource

    async def build(*args, **kwargs):
        captured["build_model"] = args[3]
        captured["build_kwargs"] = kwargs
        return TurnPromptBundle(
            prompt_messages=[
                {"role": "system", "content": "policy"},
                {"role": "user", "content": caption},
            ],
            meta={},
            instant_reply=None,
            search_sources=[],
            local_places=False,
            max_out=100,
            fallback_models=[],
            lightweight=False,
            rich_context=False,
            geo=ClientGeoContext(None, None, None, False, False, False, False),
            local_tz="UTC",
        )

    async def final_stream(_redis, _settings, ctx, **_kwargs):
        captured["ctx"] = ctx
        yield "Regenerated answer"

    async def passthrough(_redis, _key, _token, tokens):
        async for token in tokens:
            yield token

    seams = SimpleNamespace(
        wrap_stream_status=lambda _timing, status: status,
        turn_resources=resources,
        wait_for_pending_finalize=AsyncMock(),
        SessionLocal=FakeSessionCM,
        users_repo=SimpleNamespace(get_by_id=AsyncMock(return_value=user)),
        chats_repo=SimpleNamespace(get_by_id=AsyncMock(return_value=chat)),
        messages_repo=SimpleNamespace(
            get_last=AsyncMock(return_value=previous),
            get_last_user=AsyncMock(return_value=last_user),
            count_for_chat=AsyncMock(return_value=2),
        ),
        plan_service=SimpleNamespace(resolve_regenerate_model=lambda *_args: "free-chat"),
        _try_image_lookup_for_turn=AsyncMock(return_value=False),
        _try_image_gen_for_turn=AsyncMock(return_value=False),
        vision_reserve_tokens=vision_reserve_tokens,
        build_stream_prompt_context=build,
        stream_context_from_bundle=stream_context_from_bundle,
        _top_up_reserve_for_prompt=AsyncMock(),
        quota_service=SimpleNamespace(daily_limit_for_user=lambda *_args: 10000),
        _yield_with_chatprep_refresh=passthrough,
        stream_and_finalize=final_stream,
        restore_regenerate_backup=AsyncMock(),
    )
    lookup = AsyncMock(return_value=[_row(uid)])
    gateway = SimpleNamespace(read_bytes=AsyncMock(return_value=b"saved-scanner"))
    with (
        patch(
            "app.services.chat.stream_entry._classify_turn_mode",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(f"{_MODULE}.SessionLocal", FakeSessionCM),
        patch(f"{_MODULE}.attachments_repo.get_by_ids", lookup),
        patch(f"{_MODULE}.get_storage_gateway", return_value=gateway),
    ):
        result = [
            token
            async for token in stream_entry.stream_regenerate_response(
                seams, AsyncMock(), _SETTINGS, user_id=owner, chat_id=chat_id
            )
        ]
    assert result == ["Regenerated answer"]
    ctx = captured["ctx"]
    assert ctx.model == captured["build_model"] == ("vision-chat" if with_image else "free-chat")
    assert captured["build_kwargs"]["has_image_attachment"] is with_image
    assert captured["build_kwargs"]["omit_message_ids"] == {previous.id}
    assert resource.reserve.await_args.kwargs["vision_extra"] == vision_reserve_tokens(
        _SETTINGS, int(with_image)
    )
    assert ctx.regenerate_backup.message_id == previous.id
    assert ctx.regenerate_backup.content == "Original successful response"
    assert ctx.user_message_content == caption
    seams.restore_regenerate_backup.assert_not_awaited()
    if with_image:
        assert any(part["type"] == "image_url" for part in ctx.prompt_messages[-1]["content"])
        assert lookup.await_args.args[1:] == ([uid], owner)
    else:
        assert ctx.prompt_messages[-1]["content"] == caption
        lookup.assert_not_awaited()
        gateway.read_bytes.assert_not_awaited()
