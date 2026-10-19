"""A turn's photos reach the model: this turn's, or the previous turn's read again."""

import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.modules.chat.turn_prep.attachments import _AttachmentProcessResult
from app.modules.chat.turn_prep.vision import inject_turn_images
from app.tests.modules.chat.chat_test_support import FakeSessionCM

_MODULE = "app.modules.chat.turn_prep.vision"
_ON = Settings(attachments_enabled=True)


def _attachments(*, images: list[tuple[str, str]] | None = None, gateway=None):
    return _AttachmentProcessResult(
        user=None,
        user_content="",
        content="",
        has_image_attachment=bool(images),
        has_document_attachment=False,
        image_attachments=images or [],
        image_math_extract=None,
        gateway=gateway,
        bytes_by_key={key: b"sent-now" for _type, key in images or []},
    )


def _earlier(*ids):
    markers = "\n".join(f"[Image: /attachments/{uid}/file]" for uid in ids)
    return [
        {"role": "user", "content": f"What is this?\n\n{markers}"},
        {"role": "assistant", "content": "A cell."},
        {"role": "user", "content": "what colour is it?"},
    ]


def _row(uid, content_type="image/png"):
    return SimpleNamespace(id=uid, content_type=content_type, storage_key=f"key-{uid}")


async def _run(messages, attachments, rows, *, settings=_ON, byte_map=None):
    user = SimpleNamespace(id=uuid4())
    lookup = AsyncMock(return_value=rows)
    gateway = SimpleNamespace(
        read_bytes=AsyncMock(side_effect=lambda key: (byte_map or {}).get(key))
    )
    with (
        patch(f"{_MODULE}.SessionLocal", FakeSessionCM),
        patch(f"{_MODULE}.attachments_service.get_by_ids", lookup),
        patch(f"{_MODULE}.get_storage_gateway", return_value=gateway) as storage,
    ):
        needs_vision = await inject_turn_images(
            messages, attachments, caption="what colour is it?", settings=settings, user=user
        )
    return needs_vision, lookup, storage, user


@pytest.mark.asyncio
async def test_an_earlier_photo_is_read_again_and_asks_for_the_vision_model():
    first, second = uuid4(), uuid4()
    messages = _earlier(first, second)
    needs_vision, lookup, _storage, user = await _run(
        messages,
        _attachments(),
        [_row(second), _row(first)],
        byte_map={f"key-{first}": b"one", f"key-{second}": b"two"},
    )
    assert needs_vision is True
    assert lookup.await_args.args[1:] == ([first, second], user.id)
    urls = [
        part["image_url"]["url"] for part in messages[-1]["content"] if part["type"] == "image_url"
    ]
    assert urls == [
        f"data:image/png;base64,{base64.b64encode(b).decode()}" for b in (b"one", b"two")
    ]
    assert "not available" not in str(messages[-1]["content"])


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["missing", "document", "unreadable", "one_of_two_missing"])
async def test_an_earlier_photo_that_is_gone_is_named_not_guessed(kind):
    kept, gone = uuid4(), uuid4()
    ids = [kept, gone] if kind == "one_of_two_missing" else [gone]
    rows = {
        "missing": [],
        "document": [_row(gone, "application/pdf")],
        "unreadable": [_row(gone)],
        "one_of_two_missing": [_row(kept)],
    }[kind]
    messages = _earlier(*ids)
    needs_vision, *_ = await _run(messages, _attachments(), rows, byte_map={f"key-{kept}": b"ok"})
    assert needs_vision is (kind == "one_of_two_missing")
    assert "not available to look at again" in str(messages[-1]["content"])


@pytest.mark.asyncio
async def test_this_turns_photo_uses_the_bytes_already_read_and_skips_the_earlier_one():
    earlier = uuid4()
    gateway = MagicMock()
    messages = _earlier(earlier)
    needs_vision, lookup, storage, _user = await _run(
        messages, _attachments(images=[("image/png", "now")], gateway=gateway), [_row(earlier)]
    )
    assert needs_vision is False
    lookup.assert_not_awaited()
    storage.assert_not_called()
    image = next(part for part in messages[-1]["content"] if part["type"] == "image_url")
    assert (
        image["image_url"]["url"]
        == f"data:image/png;base64,{base64.b64encode(b'sent-now').decode()}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("earlier", [False, True])
async def test_a_photo_turn_says_what_to_do_with_an_unreadable_photo(earlier):
    """A blurry or cropped photo gets "what I can't read" and a request for a better one."""
    from app.modules.attachments.vision_notes import IMAGE_REAL_NOTE, UNCLEAR_IMAGE_NOTE

    uid = uuid4()
    if earlier:
        messages = _earlier(uid)
        attachments = _attachments()
    else:
        messages = _earlier()
        attachments = _attachments(images=[("image/png", "now")], gateway=MagicMock())
    await _run(messages, attachments, [_row(uid)], byte_map={f"key-{uid}": b"photo"})
    text = messages[-1]["content"][0]["text"]
    assert IMAGE_REAL_NOTE in text and UNCLEAR_IMAGE_NOTE in text
    assert "ask for a clearer photo instead of guessing" in UNCLEAR_IMAGE_NOTE
    assert "say what you cannot make out" in UNCLEAR_IMAGE_NOTE


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
async def test_no_earlier_photo_or_attachments_off_does_no_work(enabled):
    messages = _earlier(uuid4()) if not enabled else _earlier()
    before = [dict(message) for message in messages]
    needs_vision, lookup, storage, _user = await _run(
        messages, _attachments(), [], settings=Settings(attachments_enabled=enabled)
    )
    assert needs_vision is False
    lookup.assert_not_awaited()
    storage.assert_not_called()
    assert messages == before
