"""A scanned PDF's vision OCR takes one of its owner's daily image-upload slots.

A PDF with no text layer is read page by page with vision (up to
``ATTACHMENT_OCR_INDEX_MAX_PAGES`` calls), so it costs like a stack of photos,
but a PDF upload took no daily slot: one user could have the index job OCR
any number of them and spend the global cap for everyone. The index job now
takes one ``image_upload`` slot (``DAILY_IMAGE_LIMIT*``) before it may OCR.
At the cap the file stays attached and its text layer, if any, is still read;
a scanned one is just not searchable that day. A PDF that turns out to have a
text layer gets its slot back; one whose OCR found nothing keeps it spent,
since its vision calls already ran.
"""

from __future__ import annotations

import logging
from datetime import date
from uuid import UUID

from app.core.config import Settings
from app.core.db import SessionLocal
from app.core.redis import get_redis_client
from app.modules.attachments.content import ExtractedText
from app.repositories import users as users_repo
from app.services.quota import counters

logger = logging.getLogger(__name__)

_OCR_CONTENT_TYPE = "application/pdf"


async def reserve_ocr(settings: Settings, user_id: UUID, content_type: str) -> date | None:
    """The UTC day a slot was taken from, or None: OCR is off, not a PDF, or at the cap."""
    if content_type != _OCR_CONTENT_TYPE or not settings.attachment_ocr_enabled:
        return None
    async with SessionLocal() as session:
        user = await users_repo.get_by_id(session, user_id)
    if user is None:
        return None
    day = await counters.reserve("image_upload", get_redis_client(), user, settings)
    if day is None:
        logger.info("Scanned-PDF OCR skipped at the daily image limit user_id=%s", user_id)
    return day


async def release_unused_ocr(
    user_id: UUID, day: date | None, details: ExtractedText | None
) -> None:
    """Give the slot back when the PDF was read from its text layer (no vision call)."""
    if day is not None and details is not None and not details.via_ocr:
        await counters.refund("image_upload", get_redis_client(), user_id, day=day)
