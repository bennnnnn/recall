"""The images a new turn's prompt carries: this turn's photos, or the previous turn's.

A photo sent now is injected from the bytes attachment processing already read. A
follow-up about an earlier photo reads that photo again, so the model looks at it
rather than at its marker, and is told plainly when it is gone.
"""

from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.core.db import SessionLocal
from app.gateways.storage_gateway import StorageGateway, get_storage_gateway
from app.models.orm import User
from app.modules.attachments import content as attachment_content
from app.modules.attachments import markers as attachment_markers
from app.modules.attachments import service as attachments_service
from app.modules.chat.turn_prep.attachments import _AttachmentProcessResult


def uses_vision_model(
    *,
    settings: Settings,
    has_image_attachment: bool,
    recent_messages: list[Any] | None,
) -> bool:
    """A photo in this turn, or one still in the history, needs the vision model."""
    if not settings.attachments_enabled:
        return False
    if has_image_attachment:
        return True
    if not recent_messages:
        return False
    return attachment_markers.history_has_image_marker(recent_messages)


async def inject_turn_images(
    prompt_messages: list[dict[str, Any]],
    attachments: _AttachmentProcessResult,
    *,
    caption: str,
    settings: Settings,
    user: User,
) -> bool:
    """Put this turn's images, or else the previous turn's, into the last user message.

    Returns True when the previous turn's images went back in: the turn must then
    run on the vision model.
    """
    if (
        attachments.has_image_attachment
        and attachments.image_attachments
        and attachments.gateway is not None
    ):
        await attachment_content.inject_vision_content(
            prompt_messages,
            attachments.gateway,
            attachments.image_attachments,
            caption=caption,
            bytes_by_key=attachments.bytes_by_key,
        )
        return False
    if attachments.has_image_attachment or not settings.attachments_enabled:
        return False
    return await _inject_prior_images(
        prompt_messages, attachments.gateway, caption=caption, settings=settings, user=user
    )


async def _inject_prior_images(
    prompt_messages: list[dict[str, Any]],
    gateway: StorageGateway | None,
    *,
    caption: str,
    settings: Settings,
    user: User,
) -> bool:
    prior_ids = attachment_markers.prior_image_attachment_ids(prompt_messages)
    if not prior_ids:
        return False
    rehydrate_gateway = gateway or get_storage_gateway(settings)
    async with SessionLocal() as session:
        rows = await attachments_service.get_by_ids(session, prior_ids, user.id)
    by_id = {row.id: row for row in rows}
    images = [
        (row.content_type, row.storage_key)
        for uid in prior_ids
        if (row := by_id.get(uid)) is not None
        and attachment_content.is_image_content_type(row.content_type)
    ]
    injected = False
    if images:
        injected = await attachment_content.inject_vision_content(
            prompt_messages, rehydrate_gateway, images, caption=caption
        )
    if not injected or len(images) < len(prior_ids):
        attachment_markers.append_image_unavailable_note(prompt_messages)
    return injected
