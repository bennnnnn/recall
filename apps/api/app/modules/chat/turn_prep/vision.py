"""The images a new turn's prompt carries: this turn's photos, or the user's earlier ones.

A photo sent now is injected from the bytes attachment processing already read. A
follow-up about an earlier photo reads that photo again, so the model looks at it
rather than at its marker, and is told plainly when it is gone. Only the user's own
photos go back in: a picture Recall generated is the model's own work, and sending
it again would move every later turn onto a photo model for nothing.
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
    user_turns = [message for message in prompt_messages if message.get("role") == "user"]
    prior_ids = attachment_markers.prior_image_attachment_ids(user_turns)
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
