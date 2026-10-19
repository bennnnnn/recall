"""Scanned-PDF OCR in the index job takes one of the owner's daily image-upload slots."""

from contextlib import asynccontextmanager, contextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.modules.attachments import ocr_allowance
from app.modules.attachments.content import ExtractedText
from app.modules.attachments.rag import index_attachment
from app.services.quota import counters

_PDF = "application/pdf"


def _user(plan: str = "free") -> MagicMock:
    user = MagicMock()
    user.id = uuid4()
    user.plan = plan
    return user


@asynccontextmanager
async def _session(*_args, **_kwargs):
    yield MagicMock()


@contextmanager
def _owner(fake_redis, user):
    with (
        patch.object(ocr_allowance, "SessionLocal", _session),
        patch.object(ocr_allowance.users_repo, "get_by_id", AsyncMock(return_value=user)),
        patch.object(ocr_allowance, "get_redis_client", return_value=fake_redis),
    ):
        yield


async def _slots_used(fake_redis, user) -> int:
    key = counters.daily_key(counters.COUNTERS["image_upload"].prefix, user.id)
    return int(await fake_redis.get(key) or 0)


@pytest.mark.parametrize(
    "content_type, ocr_enabled, used, plan, reserved",
    [
        (_PDF, True, 0, "free", True),
        (_PDF, True, 4, "free", True),  # the fifth of five
        (_PDF, True, 5, "free", False),  # at the cap: no OCR today
        (_PDF, True, 5, "pro", True),  # paid plans have more slots
        (_PDF, False, 0, "free", False),  # OCR switched off
        ("text/plain", True, 0, "free", False),  # nothing to OCR
    ],
)
async def test_reserve_ocr_takes_an_image_slot_for_a_pdf(
    fake_redis, content_type: str, ocr_enabled: bool, used: int, plan: str, reserved: bool
) -> None:
    user = _user(plan)
    settings = Settings(attachment_ocr_enabled=ocr_enabled)
    for _ in range(used):
        assert await counters.reserve("image_upload", fake_redis, user, settings)

    with _owner(fake_redis, user):
        day = await ocr_allowance.reserve_ocr(settings, user.id, content_type)

    assert (day is not None) is reserved
    assert await _slots_used(fake_redis, user) == used + int(reserved)


async def test_reserve_ocr_skips_a_deleted_owner(fake_redis) -> None:
    with _owner(fake_redis, None):
        assert await ocr_allowance.reserve_ocr(Settings(), uuid4(), _PDF) is None


@pytest.mark.parametrize(
    "details, refunded",
    [
        (ExtractedText(text="typed pages"), True),  # text layer: no vision call ran
        (ExtractedText(text="scanned pages", via_ocr=True), False),
        (None, False),  # OCR found nothing, or extraction timed out: keep it spent
    ],
)
async def test_release_unused_ocr_refunds_only_a_text_layer_pdf(
    fake_redis, details: ExtractedText | None, refunded: bool
) -> None:
    user = _user()
    with _owner(fake_redis, user):
        day = await ocr_allowance.reserve_ocr(Settings(), user.id, _PDF)
        await ocr_allowance.release_unused_ocr(user.id, day, details)

    assert await _slots_used(fake_redis, user) == int(not refunded)


@pytest.mark.parametrize("slot, allow_ocr", [(True, True), (False, False)])
async def test_index_attachment_ocrs_a_pdf_only_with_a_slot(slot: bool, allow_ocr: bool) -> None:
    from datetime import date

    row = MagicMock()
    row.id = uuid4()
    row.user_id = uuid4()
    row.storage_key = "user/scan"
    row.content_type = _PDF
    extract = AsyncMock(return_value=None)
    release = AsyncMock()

    with (
        patch("app.modules.attachments.rag.SessionLocal", _session),
        patch(
            "app.modules.attachments.rag.attachments_repo.get_by_id",
            AsyncMock(return_value=row),
        ),
        patch(
            "app.modules.attachments.rag.attachment_content_service.read_attachment_bytes",
            AsyncMock(return_value=b"%PDF"),
        ),
        patch(
            "app.modules.attachments.rag.attachment_content_service.extract_text_details_async",
            extract,
        ),
        patch.object(
            ocr_allowance,
            "reserve_ocr",
            AsyncMock(return_value=date(2026, 10, 16) if slot else None),
        ),
        patch.object(ocr_allowance, "release_unused_ocr", release),
    ):
        count = await index_attachment(
            Settings(attachment_rag_enabled=True),
            user_id=row.user_id,
            attachment_id=row.id,
        )

    assert count == 0
    assert extract.await_args is not None
    assert extract.await_args.kwargs["allow_ocr"] is allow_ocr
    release.assert_awaited_once()
