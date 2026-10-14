"""Public attachment operations for other product modules.

Other modules may import this file. They may not import the repository or
the extractor directly.
"""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from types import ModuleType
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.attachment_limits import MAX_ATTACHMENT_SIZE as MAX_ATTACHMENT_SIZE
from app.core.config import Settings
from app.gateways.storage_gateway import get_storage_gateway
from app.modules.attachments import chunks_repository as _chunks_repo
from app.modules.attachments import lifecycle as _lifecycle
from app.modules.attachments import repository as attachments_repo
from app.modules.attachments.content import extract_text_details_async, read_attachment_bytes
from app.modules.attachments.content_types import EXTRACTABLE_CONTENT_TYPES
from app.modules.attachments.content_types import bytes_match_claimed as bytes_match_claimed
from app.modules.attachments.content_types import is_image_content_type as is_image_content_type
from app.modules.attachments.content_types import (
    normalize_content_type as normalize_content_type,
)


def _call_through(module: ModuleType, name: str) -> Callable[..., Awaitable[Any]]:
    """Look ``module.name`` up on every call, so a patch on the owning file applies."""
    target = getattr(module, name)

    @functools.wraps(target)
    async def call(*args: Any, **kwargs: Any) -> Any:
        return await getattr(module, name)(*args, **kwargs)

    return call


create_pending = _call_through(attachments_repo, "create_pending")
get_by_id = _call_through(attachments_repo, "get_by_id")
get_by_ids = _call_through(attachments_repo, "get_by_ids")
has_chunks_for_chat = _call_through(_chunks_repo, "has_chunks_for_chat")
hide_from_gallery = _call_through(attachments_repo, "hide_from_gallery")
insert_verified_clone = _call_through(attachments_repo, "insert_verified_clone")
link_to_message = _call_through(attachments_repo, "link_to_message")
list_for_message_ids = _call_through(attachments_repo, "list_for_message_ids")
list_for_user = _call_through(attachments_repo, "list_for_user")
mark_verified = _call_through(attachments_repo, "mark_verified")
purge_attachments_for_user = _call_through(_lifecycle, "purge_attachments_for_user")


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
