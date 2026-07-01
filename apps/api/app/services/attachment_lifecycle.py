"""Attachment storage cleanup — message deletes and orphan reaping."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import SessionLocal
from app.gateways.storage_gateway import get_storage_gateway
from app.repositories import attachments as attachments_repo

logger = logging.getLogger(__name__)


async def purge_attachments_for_messages(
    session: AsyncSession,
    settings: Settings,
    message_ids: list[UUID],
) -> int:
    """Delete stored bytes and DB rows for attachments linked to ``message_ids``."""
    if not message_ids:
        return 0
    rows = await attachments_repo.list_for_message_ids(session, message_ids)
    if not rows:
        return 0
    gateway = get_storage_gateway(settings)
    for row in rows:
        await gateway.delete_bytes(row.storage_key)
    return await attachments_repo.delete_rows(session, [row.id for row in rows])


async def reap_orphan_attachments(settings: Settings) -> int:
    """Delete bytes + rows for attachments never linked to a message past the grace window."""
    async with SessionLocal() as session:
        orphans = await attachments_repo.list_orphans(
            session, older_than_hours=settings.attachment_orphan_grace_hours
        )
    if not orphans:
        return 0
    gateway = get_storage_gateway(settings)
    for row in orphans:
        await gateway.delete_bytes(row.storage_key)
    async with SessionLocal() as session:
        deleted = await attachments_repo.delete_rows(session, [row.id for row in orphans])
    logger.info("Reaped %d orphan attachment(s)", deleted)
    return deleted
