"""Public attachment operations for other product modules.

Other modules may import this file. They may not import the repository or
the extractor directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.attachment_limits import MAX_ATTACHMENT_SIZE as MAX_ATTACHMENT_SIZE
from app.core.config import Settings
from app.gateways.storage_gateway import get_storage_gateway
from app.modules.attachments import repository as attachments_repo
from app.modules.attachments.content import (
    EXTRACTABLE_CONTENT_TYPES,
    extract_text_details_async,
    read_attachment_bytes,
)
from app.modules.attachments.content import bytes_match_claimed as bytes_match_claimed
from app.modules.attachments.content import is_image_content_type as is_image_content_type
from app.modules.attachments.content import normalize_content_type as normalize_content_type

create_pending = attachments_repo.create_pending
get_by_ids = attachments_repo.get_by_ids
insert_verified_clone = attachments_repo.insert_verified_clone
link_to_message = attachments_repo.link_to_message
mark_verified = attachments_repo.mark_verified


class OwnedDocumentError(Exception):
    """The caller cannot read this attachment. ``reason`` is a stable code."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class OwnedDocument:
    text: str
    filename: str | None


async def read_verified_document(
    session: AsyncSession,
    settings: Settings,
    *,
    user_id: UUID,
    attachment_id: UUID,
    max_chars: int,
    ocr_max_pages: int,
) -> OwnedDocument:
    """Return extracted text for an owned, verified document."""
    row = await attachments_repo.get_by_id(session, attachment_id, user_id)
    if row is None or row.verified_at is None:
        raise OwnedDocumentError("missing")
    if row.content_type not in EXTRACTABLE_CONTENT_TYPES:
        raise OwnedDocumentError("unsupported")
    data = await read_attachment_bytes(get_storage_gateway(settings), row.storage_key)
    if not data:
        raise OwnedDocumentError("unreadable")
    details = await extract_text_details_async(
        row.content_type,
        data,
        settings,
        max_chars=max_chars,
        ocr_max_pages=ocr_max_pages,
    )
    if details is None or not details.text.strip():
        raise OwnedDocumentError("empty")
    return OwnedDocument(text=details.text.strip()[:max_chars], filename=row.original_filename)
