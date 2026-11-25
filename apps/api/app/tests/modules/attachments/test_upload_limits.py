"""Every upload is held to the per-file size and to the Library total, photos and
documents alike (owner's limits, 2026-11-24).

With photos no longer counted a day on either plan, these two and the request limits
are what bound uploads: the size at presign, on the API's own upload, and on the stored
object an R2 upload left; the Library total at every presign, one at a time per account.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import fakeredis.aioredis
import pytest

from app.core.config import Settings
from app.gateways.storage_gateway import PresignedUpload
from app.modules.attachments import repository as attachments_repo
from app.modules.attachments import storage_quota
from app.modules.attachments import upload as attachment_upload
from app.modules.attachments.content import MAX_ATTACHMENT_SIZE, _stored_size_error
from app.modules.attachments.workflow import _read_local_upload
from app.tests.fakes import fake_session, make_user

MIB = 1024**2
_TYPES = ["image/png", "application/pdf"]
_PNG = b"\x89PNG\r\n\x1a\n"
_PDF = b"%PDF-1.4\n"


def test_the_per_file_limit_is_ten_megabytes() -> None:
    assert MAX_ATTACHMENT_SIZE == 10 * MIB


@pytest.mark.parametrize("plan", ["free", "pro"])
@pytest.mark.parametrize("content_type", _TYPES)
@pytest.mark.parametrize("size", [0, MAX_ATTACHMENT_SIZE + 1])
async def test_presign_refuses_a_file_outside_the_size(plan: str, content_type: str, size: int):
    gateway = MagicMock()
    gateway.presign_upload = AsyncMock(side_effect=AssertionError("never presigned"))
    with patch.object(attachment_upload, "get_storage_gateway", return_value=gateway):
        with pytest.raises(attachment_upload.AttachmentUploadError) as refused:
            await attachment_upload.create_presigned_upload(
                fake_session(),
                Settings(),
                user=make_user(plan=plan),
                content_type=content_type,
                size_bytes=size,
            )
    assert refused.value.code == "invalid_size"


async def _stream(data: bytes) -> AsyncIterator[bytes]:
    for start in range(0, len(data), MIB):
        yield data[start : start + MIB]


@pytest.mark.parametrize(
    ("content_type", "magic"), [("image/png", _PNG), ("application/pdf", _PDF)]
)
async def test_the_apis_own_upload_holds_the_size(content_type: str, magic: bytes) -> None:
    """The bytes are read no further than the declared size (itself at most 10 MB): a
    body past it, or one that is not the size declared, is refused."""
    row = MagicMock(size_bytes=1024, content_type=content_type)
    over = magic + b"\0" * (2048 - len(magic))
    _data, detail = await _read_local_upload(_stream(over), row)
    assert detail == "Invalid upload size"
    short = magic + b"\0" * (512 - len(magic))
    _data, detail = await _read_local_upload(_stream(short), row)
    assert detail == "Uploaded size does not match the declared size"
    # A row claiming more than the cap is read only up to the cap.
    huge = MagicMock(size_bytes=MAX_ATTACHMENT_SIZE + 5, content_type=content_type)
    _data, detail = await _read_local_upload(_stream(magic + b"\0" * MAX_ATTACHMENT_SIZE), huge)
    assert detail == "Invalid upload size"


@pytest.mark.parametrize(
    ("stored", "declared", "detail"),
    [
        (MAX_ATTACHMENT_SIZE + 1, MAX_ATTACHMENT_SIZE + 1, "Invalid upload size"),
        (2048, 1024, "Uploaded size does not match the declared size"),
        (1024, 1024, None),
    ],
)
def test_an_r2_upload_is_held_to_the_size_it_left(stored: int, declared: int, detail: str | None):
    """The presigned PUT is signed for the declared length, and the stored object is
    checked again (a HEAD) before the file is used: over the cap or not as declared, it
    is refused and removed."""
    assert _stored_size_error(stored, declared) == detail


@pytest.mark.parametrize("plan, total", [("free", 400 * MIB), ("pro", 4 * 1024**3)])
@pytest.mark.parametrize("content_type", _TYPES)
async def test_every_presign_checks_the_library_total(plan: str, total: int, content_type: str):
    """A file that would take the Library past the plan's total is refused, photo or
    document, before any slot or presign."""
    user = make_user(plan=plan)
    gateway = MagicMock()
    gateway.presign_upload = AsyncMock(side_effect=AssertionError("never presigned"))
    with (
        patch.object(storage_quota, "stored_bytes", AsyncMock(return_value=total - 100)),
        patch.object(attachment_upload, "get_storage_gateway", return_value=gateway),
        patch.object(
            attachment_upload,
            "get_redis_client",
            return_value=fakeredis.aioredis.FakeRedis(decode_responses=True),
        ),
        pytest.raises(attachment_upload.AttachmentUploadError) as refused,
    ):
        await attachment_upload.create_presigned_upload(
            fake_session(), Settings(), user=user, content_type=content_type, size_bytes=101
        )
    assert refused.value.code == "storage_full"


@pytest.mark.parametrize("content_type", _TYPES)
async def test_presigns_racing_the_library_total_pass_one_at_a_time(content_type: str):
    """Two uploads at once that each fit but not both: the second reads the first's
    pending row and is refused. Read together, both had passed."""
    user = make_user(plan="pro")
    total = Settings().library_storage_bytes_pro
    rows: list[int] = []
    already = total - 15 * MIB

    async def stored(*_args: Any) -> int:
        return already + sum(rows)

    async def presign(**kwargs: Any) -> PresignedUpload:
        await asyncio.sleep(0.01)  # a race's window: the other presign runs meanwhile
        attachment_id = str(uuid4())
        return PresignedUpload(
            attachment_id=attachment_id,
            upload_url=f"/attachments/{attachment_id}/upload",
            storage_key=f"{user.id}/{attachment_id}",
            headers={"Content-Type": kwargs["content_type"]},
            api_upload=True,
        )

    async def create_pending(_session: Any, **kwargs: Any) -> None:
        rows.append(kwargs["size_bytes"])

    gateway = MagicMock()
    gateway.presign_upload = presign
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with (
        patch.object(storage_quota, "stored_bytes", stored),
        patch.object(attachment_upload, "get_storage_gateway", return_value=gateway),
        patch.object(attachment_upload, "get_redis_client", return_value=redis),
        patch.object(attachments_repo, "create_pending", create_pending),
    ):
        results = await asyncio.gather(
            *(
                attachment_upload.create_presigned_upload(
                    fake_session(),
                    Settings(),
                    user=user,
                    content_type=content_type,
                    size_bytes=8 * MIB,
                )
                for _ in range(2)
            ),
            return_exceptions=True,
        )
    refused = [r for r in results if isinstance(r, attachment_upload.AttachmentUploadError)]
    assert len(rows) == 1
    assert [r.code for r in refused] == ["storage_full"]
    assert await redis.keys("recall:library_presign:*") == []


async def test_a_refund_gives_back_only_a_recorded_slot(fake_redis) -> None:
    """An upload that took no slot (its plan's uploads follow messages) has no record, so
    its refund lowers nothing, not even a counter a Pro day raised; one that took a slot
    gives it back once."""
    from app.modules.attachments.quota import record_upload_slot, refund_upload
    from app.services.quota import counters

    row = MagicMock(id=uuid4(), user_id=uuid4(), content_type="application/pdf")
    key = counters.daily_key("docup", row.user_id)
    await fake_redis.set(key, 5, ex=600)
    await refund_upload(fake_redis, row)
    assert await fake_redis.get(key) == "5"

    await record_upload_slot(fake_redis, row.id, counters.utc_today())
    await refund_upload(fake_redis, row)
    await refund_upload(fake_redis, row)
    assert await fake_redis.get(key) == "4"


async def test_a_redis_refusal_at_the_presign_lock_is_the_outage(fake_redis) -> None:
    """Upstash over its request quota answers a ResponseError: the 503 outage, not a 500."""
    from redis.exceptions import ResponseError

    from app.exceptions import RedisUnavailableError

    with (
        patch.object(storage_quota, "acquire_lock", AsyncMock(side_effect=ResponseError("max"))),
        pytest.raises(RedisUnavailableError),
    ):
        async with storage_quota.library_presign(fake_redis, uuid4()):
            pass


@pytest.mark.parametrize(
    ("plan", "content_type", "prefix", "left"),
    [
        # Free's upload took no slot: its failure lowers nothing a Pro day counted.
        ("free", "application/pdf", "docup", "5"),
        ("free", "image/png", "imgup", "5"),
        # Pro's document took one, given back when the presign fails.
        ("pro", "application/pdf", "docup", "5"),
    ],
)
async def test_a_failed_presign_gives_back_only_a_slot_it_took(
    plan: str, content_type: str, prefix: str, left: str
) -> None:
    from app.services.quota import counters

    user = make_user(plan=plan)
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    key = counters.daily_key(prefix, user.id)
    await redis.set(key, 5, ex=600)
    gateway = MagicMock()
    gateway.presign_upload = AsyncMock(side_effect=RuntimeError("storage down"))
    with (
        patch.object(storage_quota, "stored_bytes", AsyncMock(return_value=0)),
        patch.object(attachment_upload, "get_storage_gateway", return_value=gateway),
        patch.object(attachment_upload, "get_redis_client", return_value=redis),
        pytest.raises(RuntimeError),
    ):
        await attachment_upload.create_presigned_upload(
            fake_session(), Settings(), user=user, content_type=content_type, size_bytes=10
        )
    assert await redis.get(key) == left
