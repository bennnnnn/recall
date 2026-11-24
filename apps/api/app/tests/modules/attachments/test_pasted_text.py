"""Text pasted as a file reads as the same text typed: a message's length inline, never cut silently."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest

from app.core.config import Settings
from app.exceptions import AttachmentValidationError
from app.models.schemas.chats import MESSAGE_MAX_CHARS
from app.modules.attachments import storage_quota
from app.modules.attachments import upload as attachment_upload
from app.modules.attachments.content import format_attachment_lines
from app.modules.attachments.pasted_text import (
    PASTED_TEXT_FILENAME,
    PASTED_TEXT_INLINE_CHARS,
    PASTED_TEXT_MAX_BYTES,
    PASTED_TEXT_MAX_CHARS,
    is_pasted_text,
    pasted_text_too_long,
)
from app.modules.attachments.text_extract import MAX_EXTRACT_CHARS, MAX_INDEX_EXTRACT_CHARS
from app.tests.fakes import fake_session, make_user

_ID = "550e8400-e29b-41d4-a716-446655440000"


def test_the_limits_are_a_message_inline_and_a_searchable_document_in_all() -> None:
    assert PASTED_TEXT_INLINE_CHARS == MESSAGE_MAX_CHARS == 32_000
    assert PASTED_TEXT_MAX_CHARS == MAX_INDEX_EXTRACT_CHARS == 200_000
    assert MAX_EXTRACT_CHARS == 12_000  # another document's excerpt is unchanged


@pytest.mark.parametrize(
    "content_type, filename, pasted",
    [
        ("text/plain", PASTED_TEXT_FILENAME, True),
        ("text/plain; charset=utf-8", PASTED_TEXT_FILENAME, True),
        ("text/plain", "notes.txt", False),
        ("text/plain", None, False),
        ("text/markdown", PASTED_TEXT_FILENAME, False),
        ("application/pdf", PASTED_TEXT_FILENAME, False),
    ],
)
def test_is_pasted_text_needs_the_phones_name_and_plain_text(
    content_type: str, filename: str | None, pasted: bool
) -> None:
    assert is_pasted_text(content_type, filename) is pasted


@pytest.mark.parametrize(
    "text, too_long",
    [
        ("a" * PASTED_TEXT_MAX_CHARS, False),
        ("a" * (PASTED_TEXT_MAX_CHARS + 1), True),
        # Four bytes each: well past the byte count, not past the characters.
        ("😀" * PASTED_TEXT_MAX_CHARS, False),
        ("é" * (PASTED_TEXT_MAX_CHARS + 1), True),
    ],
)
def test_pasted_text_too_long_counts_characters_not_bytes(text: str, too_long: bool) -> None:
    assert pasted_text_too_long(text.encode()) is too_long


async def _format(data: bytes, *, filename: str | None) -> list[str]:
    gateway = MagicMock()
    gateway.read_bytes = AsyncMock(return_value=data)
    lines, is_image = await format_attachment_lines(
        gateway,
        attachment_id=_ID,
        content_type="text/plain",
        storage_key="key",
        size_bytes=len(data),
        settings=Settings(),
        data=data,
        filename=filename,
    )
    assert is_image is False
    return lines


def _body(lines: list[str]) -> str:
    assert lines[0] == f"[File: /attachments/{_ID}/file]"
    head, _, body = lines[1].partition("\n")
    assert head == "[File (text/plain)]"
    return body


@pytest.mark.asyncio
async def test_pasted_text_is_read_inline_up_to_a_messages_length() -> None:
    text = "w" * MESSAGE_MAX_CHARS
    assert _body(await _format(text.encode(), filename=PASTED_TEXT_FILENAME)) == text


@pytest.mark.asyncio
async def test_a_longer_paste_says_only_its_first_part_was_read() -> None:
    text = "w" * MESSAGE_MAX_CHARS + "tail"
    body = _body(await _format(text.encode(), filename=PASTED_TEXT_FILENAME))
    note, _, excerpt = body.partition("\n")
    assert note.startswith("[File note: only the first 32000 characters were read")
    assert excerpt == "w" * MESSAGE_MAX_CHARS


@pytest.mark.asyncio
async def test_another_text_file_keeps_the_document_excerpt() -> None:
    text = "w" * MESSAGE_MAX_CHARS
    body = _body(await _format(text.encode(), filename="notes.txt"))
    note, _, excerpt = body.partition("\n")
    assert note.startswith("[File note: only the first 12000 characters were read")
    assert excerpt == "w" * MAX_EXTRACT_CHARS


@pytest.mark.asyncio
async def test_a_paste_past_the_limit_refuses_the_turn() -> None:
    data = ("a" * (PASTED_TEXT_MAX_CHARS + 1)).encode()
    with pytest.raises(AttachmentValidationError, match="Attach it as a file"):
        await _format(data, filename=PASTED_TEXT_FILENAME)


@pytest.mark.asyncio
async def test_a_long_text_file_not_pasted_is_still_read() -> None:
    data = ("a" * (PASTED_TEXT_MAX_CHARS + 1)).encode()
    assert _body(await _format(data, filename="book.txt"))


async def _presign(*, size: int, filename: str | None) -> AsyncMock:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    gateway = MagicMock()
    gateway.presign_upload = AsyncMock(side_effect=RuntimeError("stop after the checks"))
    user: Any = make_user()
    with (
        patch.object(storage_quota, "stored_bytes", AsyncMock(return_value=0)),
        patch.object(attachment_upload, "get_storage_gateway", return_value=gateway),
        patch.object(attachment_upload, "get_redis_client", return_value=redis),
    ):
        try:
            await attachment_upload.create_presigned_upload(
                fake_session(),
                Settings(),
                user=user,
                content_type="text/plain",
                size_bytes=size,
                filename=filename,
            )
        except RuntimeError:
            pass
    return gateway.presign_upload


@pytest.mark.asyncio
async def test_presign_refuses_a_paste_too_large_to_be_in_bounds() -> None:
    with pytest.raises(attachment_upload.AttachmentUploadError) as refused:
        await _presign(size=PASTED_TEXT_MAX_BYTES + 1, filename=PASTED_TEXT_FILENAME)
    assert refused.value.code == "paste_too_long"
    assert refused.value.status_code == 400


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "size, filename",
    [(PASTED_TEXT_MAX_BYTES, PASTED_TEXT_FILENAME), (PASTED_TEXT_MAX_BYTES + 1, "book.txt")],
)
async def test_presign_takes_a_paste_in_bounds_and_any_other_text_file(
    size: int, filename: str
) -> None:
    (await _presign(size=size, filename=filename)).assert_awaited_once()
