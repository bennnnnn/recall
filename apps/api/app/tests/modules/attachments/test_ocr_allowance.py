"""Scanned-PDF OCR in the index job takes one of the owner's daily scanned-document slots
(Pro 100 a day); Free's is covered by the message the PDF was sent with."""

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


def _user(plan: str = "pro") -> MagicMock:
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
    key = counters.daily_key(counters.COUNTERS["document_ocr"].prefix, user.id)
    return int(await fake_redis.get(key) or 0)


@pytest.mark.parametrize(
    "content_type, ocr_enabled, used, plan, reserved",
    [
        (_PDF, True, 0, "pro", True),
        (_PDF, True, 99, "pro", True),  # the last of a hundred
        (_PDF, True, 100, "pro", False),  # at the cap: no OCR today
        (_PDF, False, 0, "pro", False),  # OCR switched off
        ("text/plain", True, 0, "pro", False),  # nothing to OCR
    ],
)
async def test_reserve_ocr_takes_a_scanned_document_slot_for_a_pdf(
    fake_redis, content_type: str, ocr_enabled: bool, used: int, plan: str, reserved: bool
) -> None:
    user = _user(plan)
    settings = Settings(attachment_ocr_enabled=ocr_enabled)
    for _ in range(used):
        assert await counters.reserve("document_ocr", fake_redis, user, settings)

    with _owner(fake_redis, user):
        day = await ocr_allowance.reserve_ocr(settings, user.id, content_type, uuid4())

    assert (day is not None) is reserved
    assert await _slots_used(fake_redis, user) == used + int(reserved)


async def test_pro_resending_scanned_pdfs_stops_at_a_hundred(fake_redis) -> None:
    """A resend from the Library makes a new copy that skips the presign's document count,
    and the index job reads each copy again: every copy takes its own slot, so a Pro user
    resending the same ten scanned PDFs on every message stops at 100 OCR'd a day."""
    user = _user("pro")
    settings = Settings(attachment_ocr_enabled=True)
    with _owner(fake_redis, user):
        days = [
            await ocr_allowance.reserve_ocr(settings, user.id, _PDF, uuid4()) for _ in range(110)
        ]

    assert sum(day is not None for day in days) == 100
    assert days[99] is not None and days[100] is None
    assert await _slots_used(fake_redis, user) == 100


async def test_free_ocr_is_covered_by_its_message_and_its_refund_lowers_nothing(
    fake_redis,
) -> None:
    """Free's scanned documents follow its messages: no slot is taken, so the refund of a
    reserved file gives nothing back, even to a counter another plan's day raised."""
    user = _user("free")
    settings = Settings(attachment_ocr_enabled=True)
    key = counters.daily_key(counters.COUNTERS["document_ocr"].prefix, user.id)
    await fake_redis.set(key, 7, ex=600)  # counted earlier today, on Pro
    first = uuid4()
    with _owner(fake_redis, user):
        days = [await ocr_allowance.reserve_ocr(settings, user.id, _PDF, first)]
        days += [
            await ocr_allowance.reserve_ocr(settings, user.id, _PDF, uuid4()) for _ in range(40)
        ]
        await ocr_allowance.refund_ocr(user.id, first, days[0])

    assert all(day is not None for day in days)
    assert await fake_redis.get(key) == "7"


async def test_reserve_ocr_skips_a_deleted_owner(fake_redis) -> None:
    with _owner(fake_redis, None):
        assert await ocr_allowance.reserve_ocr(Settings(), uuid4(), _PDF, uuid4()) is None


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
    attachment_id = uuid4()
    with _owner(fake_redis, user):
        day = await ocr_allowance.reserve_ocr(Settings(), user.id, _PDF, attachment_id)
        await ocr_allowance.release_unused_ocr(user.id, attachment_id, day, details)

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
        patch.object(ocr_allowance, "recall_ocr_text", AsyncMock(return_value=None)),
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


async def test_reserve_ocr_charges_one_slot_per_file_across_retries(fake_redis) -> None:
    user = _user()
    attachment_id = uuid4()
    with _owner(fake_redis, user):
        counted = Settings()
        first = await ocr_allowance.reserve_ocr(counted, user.id, _PDF, attachment_id)
        retry = await ocr_allowance.reserve_ocr(counted, user.id, _PDF, attachment_id)
        other = await ocr_allowance.reserve_ocr(counted, user.id, _PDF, uuid4())

    assert first is not None and retry == first and other is not None
    assert await _slots_used(fake_redis, user) == 2


async def test_refund_ocr_gives_the_slot_back_once(fake_redis) -> None:
    user = _user()
    attachment_id = uuid4()
    with _owner(fake_redis, user):
        day = await ocr_allowance.reserve_ocr(Settings(), user.id, _PDF, attachment_id)
        await ocr_allowance.refund_ocr(user.id, attachment_id, day)
        await ocr_allowance.refund_ocr(user.id, attachment_id, day)
        assert await _slots_used(fake_redis, user) == 0
        # The next run of the same file pays again: its slot was returned.
        assert await ocr_allowance.reserve_ocr(Settings(), user.id, _PDF, attachment_id)

    assert await _slots_used(fake_redis, user) == 1


@pytest.mark.parametrize(
    "details, kept",
    [
        (ExtractedText(text="scanned pages", page_capped=True, via_ocr=True), True),
        (ExtractedText(text="typed pages"), False),  # a text layer is cheap to read again
        (ExtractedText(text="", via_ocr=True), False),
    ],
)
async def test_ocr_text_is_kept_for_a_retry(fake_redis, details: ExtractedText, kept: bool) -> None:
    attachment_id = uuid4()
    with patch.object(ocr_allowance, "get_redis_client", return_value=fake_redis):
        await ocr_allowance.remember_ocr_text(attachment_id, details)
        recalled = await ocr_allowance.recall_ocr_text(attachment_id)

    assert (recalled == details) is kept
    assert (recalled is not None) is kept


async def test_unreadable_kept_ocr_text_is_ignored(fake_redis) -> None:
    attachment_id = uuid4()
    await fake_redis.set(ocr_allowance._text_key(attachment_id), "not base64 zlib")
    with patch.object(ocr_allowance, "get_redis_client", return_value=fake_redis):
        assert await ocr_allowance.recall_ocr_text(attachment_id) is None


def _index_patches(row: MagicMock, extract: AsyncMock, recalled: ExtractedText | None):
    return (
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
        patch.object(ocr_allowance, "recall_ocr_text", AsyncMock(return_value=recalled)),
    )


def _pdf_row() -> MagicMock:
    row = MagicMock()
    row.id = uuid4()
    row.user_id = uuid4()
    row.storage_key = "user/scan"
    row.content_type = _PDF
    return row


async def test_index_attachment_refunds_the_slot_when_the_parse_times_out() -> None:
    from datetime import date

    from app.modules.attachments.content import ExtractTimeoutError
    from app.modules.attachments.rag import AttachmentUnreadableError

    row = _pdf_row()
    day = date(2026, 10, 16)
    refund = AsyncMock()
    extract = AsyncMock(side_effect=ExtractTimeoutError(_PDF))
    first, second, third, fourth, fifth = _index_patches(row, extract, None)
    with (
        first,
        second,
        third,
        fourth,
        fifth,
        patch.object(ocr_allowance, "reserve_ocr", AsyncMock(return_value=day)),
        patch.object(ocr_allowance, "refund_ocr", refund),
        # Not retried: the same file would run past its budget the same way.
        pytest.raises(AttachmentUnreadableError),
    ):
        await index_attachment(
            Settings(attachment_rag_enabled=True), user_id=row.user_id, attachment_id=row.id
        )

    assert extract.await_args is not None
    assert extract.await_args.kwargs["raise_on_timeout"] is True
    refund.assert_awaited_once_with(row.user_id, row.id, day)


async def test_index_attachment_reuses_kept_ocr_text_without_reading_again() -> None:
    row = _pdf_row()
    extract = AsyncMock()
    reserve = AsyncMock()
    first, second, third, fourth, fifth = _index_patches(
        row, extract, ExtractedText(text="", via_ocr=True)
    )
    with (
        first,
        second,
        third,
        fourth,
        fifth,
        patch.object(ocr_allowance, "reserve_ocr", reserve),
    ):
        count = await index_attachment(
            Settings(attachment_rag_enabled=True), user_id=row.user_id, attachment_id=row.id
        )

    assert count == 0
    extract.assert_not_awaited()
    reserve.assert_not_awaited()


async def test_a_busy_document_pool_is_retried_not_dead_lettered() -> None:
    from datetime import date

    from app.core.sympy_executor import WorkerBusyError
    from app.modules.attachments.rag import AttachmentIndexError

    row = _pdf_row()
    refund = AsyncMock()
    extract = AsyncMock(side_effect=WorkerBusyError("no document worker free"))
    first, second, third, fourth, fifth = _index_patches(row, extract, None)
    with (
        first,
        second,
        third,
        fourth,
        fifth,
        patch.object(ocr_allowance, "reserve_ocr", AsyncMock(return_value=date(2026, 10, 16))),
        patch.object(ocr_allowance, "refund_ocr", refund),
        pytest.raises(AttachmentIndexError),
    ):
        await index_attachment(
            Settings(attachment_rag_enabled=True), user_id=row.user_id, attachment_id=row.id
        )
    refund.assert_awaited_once()


async def test_the_index_job_dead_letters_a_file_it_cannot_read_in_time() -> None:
    from app.core.jobs import JobDiscardError
    from app.modules.attachments import jobs as attachment_jobs
    from app.modules.attachments.rag import AttachmentUnreadableError

    payload = {"attachment_id": str(uuid4()), "user_id": str(uuid4())}
    with (
        patch.object(
            attachment_jobs.attachment_rag,
            "index_attachment",
            AsyncMock(side_effect=AttachmentUnreadableError("could not read in time")),
        ),
        pytest.raises(JobDiscardError),
    ):
        await attachment_jobs.index_attachment_job(Settings(attachment_rag_enabled=True), payload)
